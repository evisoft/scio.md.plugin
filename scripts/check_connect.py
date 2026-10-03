#!/usr/bin/env python3
"""Probe Scio's OAuth MCP endpoint against Claude's connector requirements.

Anonymous checks only — no credentials are read or sent, and nothing changes state:
  - an unauthenticated MCP request to /connect gets 401 with WWW-Authenticate: Bearer resource_metadata=…
  - protected-resource metadata names the exact MCP URL as `resource`
  - the first authorization server serves RFC 8414 metadata with S256 PKCE and CIMD or DCR
  - the tool list (read anonymously from the key-based route, which serves the same tools) has a
    title, readOnlyHint or destructiveHint, a name of at most 64 characters and a description of at
    most 2,048 characters for every tool, and server instructions within 2,048 characters

Whether /connect hides the registration tool needs a signed-in client; Scio's own server tests cover it.

Usage: python3 scripts/check_connect.py [--url https://scio.md/connect] [--tools-url https://scio.md/mcp]
Exit code: 0 when every check passes, 1 otherwise.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request

UA = "scio-plugin-check/0.1"
MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2025-06-18",
    "User-Agent": UA,
}
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "scio-plugin-check", "version": "0.1"},
    },
}

failures = []


def check(ok, label, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {label}{(' — ' + detail) if detail and not ok else ''}")
    if not ok:
        failures.append(label)
    return ok


def request(url, body=None, headers=None, timeout=15):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers or {"User-Agent": UA}, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), err.read().decode("utf-8", "replace")


def parse_mcp(text):
    """A Streamable HTTP response is JSON or an SSE stream of JSON-RPC messages."""
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    for line in text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    raise ValueError("no JSON-RPC message in response")


def anonymous(url):
    status, headers, _ = request(url, INITIALIZE, MCP_HEADERS)
    check(status == 401, "unauthenticated initialize answers 401", f"got {status}")
    challenge = next((v for k, v in headers.items() if k.lower() == "www-authenticate"), "")
    match = re.search(r'resource_metadata="([^"]+)"', challenge)
    check(challenge.lower().startswith("bearer") and match, "401 carries WWW-Authenticate: Bearer resource_metadata", challenge)
    prm_url = match.group(1) if match else url.split("/", 3)[0] + "//" + url.split("/")[2] + "/.well-known/oauth-protected-resource"

    status, _, body = request(prm_url)
    if not check(status == 200, "protected-resource metadata is served", f"{prm_url} → {status}"):
        return
    prm = json.loads(body)
    check(prm.get("resource") == url, "PRM resource equals the MCP URL exactly", f"{prm.get('resource')!r} vs {url!r}")
    servers = prm.get("authorization_servers") or []
    if not check(bool(servers), "PRM lists an authorization server (Claude uses only the first)"):
        return
    issuer = servers[0].rstrip("/")
    print(f"      scopes_supported: {prm.get('scopes_supported')}")

    status, _, body = request(issuer + "/.well-known/oauth-authorization-server")
    if status != 200:
        status, _, body = request(issuer + "/.well-known/openid-configuration")
    if not check(status == 200, "authorization-server metadata is served", f"{issuer} → {status}"):
        return
    asm = json.loads(body)
    check(asm.get("issuer", "").rstrip("/") == issuer, "issuer matches the PRM entry (Claude Code's v2 runtime rejects a mismatch)", asm.get("issuer"))
    check("S256" in (asm.get("code_challenge_methods_supported") or []), "PKCE S256 advertised")
    check(str(asm.get("token_endpoint", "")).startswith("https://"), "token endpoint is HTTPS")
    cimd = asm.get("client_id_metadata_document_supported") is True and "none" in (asm.get("token_endpoint_auth_methods_supported") or [])
    dcr = bool(asm.get("registration_endpoint"))
    check(cimd or dcr, "Claude can identify itself (CIMD with public-client auth, or DCR)", f"cimd={cimd} dcr={dcr}")
    print(f"      client identity: {'CIMD (preferred by Claude)' if cimd else 'DCR only'}{' + DCR' if cimd and dcr else ''}")
    grants = asm.get("grant_types_supported") or ["authorization_code"]
    check("authorization_code" in grants, "authorization_code grant supported")
    check("refresh_token" in grants, "refresh_token grant supported (Claude refreshes tokens)", str(grants))
    if "offline_access" not in (asm.get("scopes_supported") or []):
        print("      note: offline_access is not advertised; Claude appends it only when listed")


def audit_tools(url):
    headers = dict(MCP_HEADERS)
    status, resp_headers, body = request(url, INITIALIZE, headers)
    if not check(status == 200, "anonymous initialize on the tools route succeeds", f"got {status}"):
        return
    session = next((v for k, v in resp_headers.items() if k.lower() == "mcp-session-id"), None)
    if session:
        headers["Mcp-Session-Id"] = session
    init = parse_mcp(body).get("result", {})
    instructions = init.get("instructions") or ""
    check(len(instructions) <= 2048, "server instructions fit Claude Code's 2,048-character cut", str(len(instructions)))
    request(url, {"jsonrpc": "2.0", "method": "notifications/initialized"}, headers)

    tools, cursor = [], None
    while True:
        params = {"cursor": cursor} if cursor else {}
        status, _, body = request(url, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": params}, headers)
        if not check(status == 200, "tools/list succeeds", f"got {status}"):
            return
        result = parse_mcp(body).get("result", {})
        tools += result.get("tools", [])
        cursor = result.get("nextCursor")
        if not cursor:
            break
    print(f"      {len(tools)} tools")
    for tool in tools:
        ann = tool.get("annotations") or {}
        name = tool["name"]
        check(len(name) <= 64, f"{name}: name ≤ 64 characters")
        check(bool(tool.get("title") or ann.get("title")), f"{name}: has a title")
        check("readOnlyHint" in ann or "destructiveHint" in ann, f"{name}: declares readOnlyHint or destructiveHint", json.dumps(ann))
        check(len(tool.get("description") or "") <= 2048, f"{name}: description ≤ 2,048 characters")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="https://scio.md/connect")
    parser.add_argument("--tools-url", default="https://scio.md/mcp")
    args = parser.parse_args()
    print(f"Checking {args.url}")
    anonymous(args.url)
    audit_tools(args.tools_url)
    print(f"\n{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
