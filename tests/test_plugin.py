"""Package checks for the Scio plugin.

They mirror the directory's validation rules (docs: plugins/pre-submission-checklist) and
the plugin's own design constraints: remote OAuth MCP only, no local runtime, portable
skill frontmatter, links that resolve, and tool names that exist in Scio's contract.
Run: python3 -m unittest discover -s tests -v
"""

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - the checks below need PyYAML
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "scio"
CONTRACT = ROOT.parent / "scio" / "contracts" / "tools.json"

PORTABLE_SKILL_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
COMMAND_KEYS = {"description", "argument-hint"}
AGENT_KEYS = {"name", "description", "disallowedTools", "tools", "model", "color"}
IGNORED_FOR_PLUGIN_AGENTS = {"hooks", "mcpServers", "permissionMode", "initialPrompt"}
SYSTEM_FILES = {".DS_Store", "Thumbs.db", "desktop.ini", "__MACOSX"}
WINDOWS_DEVICES = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
TEXT_SUFFIXES = {".md", ".json", ".svg", ".txt", ""}
LOCAL_RUNTIME = (
    "scio-local", "scio_bridge", "scio_local", "build_proposal", "check_proposal", "scan_injection",
    "verify_rules", "show_claims", "use_agent", "workdir(", "write_file", "read_file", "SCIO_API_KEY",
    "SCIO_KEYS_FILE", "SCIO_ROLES", "keys file", "python3", "CLAUDE_PLUGIN_ROOT", "supervise.py", "proposal_file",
)
SECRET_PATTERNS = (
    re.compile(r"sk_[A-Za-z0-9_-]{16,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/-]{20,}"),
    re.compile(r"(?i)client_secret\"?\s*[:=]"),
)


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def plugin_files():
    """Text files of the plugin; the listing icon is checked on its own."""
    return sorted(p for p in PLUGIN.rglob("*") if p.is_file() and p.suffix not in IMAGE_SUFFIXES)


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise AssertionError(f"{path}: front matter must open on line 1")
    end = text.index("\n---\n", 4)
    data = yaml.safe_load(text[4:end])
    if not isinstance(data, dict):
        raise AssertionError(f"{path}: front matter is not a mapping")
    return data, text[end + 5:]


def words_outside_code(markdown):
    without_fences = re.sub(r"```.*?```", " ", markdown, flags=re.S)
    without_inline = re.sub(r"`[^`]*`", " ", without_fences)
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9'’.-]*", without_inline)


@unittest.skipIf(yaml is None, "PyYAML is required for the front-matter checks")
class PluginPackageTests(unittest.TestCase):
    def test_folder_layout_matches_directory_rules(self):
        files = sorted(p for p in PLUGIN.rglob("*") if p.is_file())
        self.assertLessEqual(len(files), 512)
        self.assertEqual(sorted(p.name for p in (PLUGIN / ".claude-plugin").iterdir()), ["plugin.json"])
        self.assertFalse((PLUGIN / "bin").exists(), "a top-level bin/ stops claude.ai and Cowork from installing")
        self.assertFalse((PLUGIN / "hooks").exists(), "chat ignores hooks; this plugin ships none")
        names_seen = set()
        for path in files:
            rel = path.relative_to(PLUGIN)
            self.assertFalse(path.is_symlink(), rel)
            self.assertLess(path.stat().st_size, 256 * 1024, f"{rel} would be held for a reviewer")
            self.assertIn(path.suffix, TEXT_SUFFIXES | {".png", ".jpg", ".jpeg", ".gif", ".webp"}, rel)
            for part in rel.parts:
                self.assertNotIn(part, SYSTEM_FILES, rel)
                self.assertNotIn(":", part, rel)
                self.assertFalse(part.endswith((".", " ")), rel)
                self.assertNotIn(part.split(".")[0].lower(), WINDOWS_DEVICES, rel)
            for part in rel.parts[:-1]:
                self.assertRegex(part, r"^[A-Za-z0-9._-]+$", rel)
            lowered = str(rel).lower()
            self.assertNotIn(lowered, names_seen, f"{rel} differs from another name only by case")
            names_seen.add(lowered)

    def test_manifest_has_directory_fields(self):
        manifest = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text())
        self.assertEqual(manifest["name"], "scio-knowledge")
        self.assertRegex(manifest["name"], r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
        for key in ("displayName", "description", "license"):
            self.assertTrue(manifest.get(key), key)
        self.assertTrue(manifest["author"]["name"])
        self.assertTrue(manifest["homepage"].startswith("https://"))
        for key in ("hooks", "mcpServers", "experimental", "userConfig", "dependencies"):
            self.assertNotIn(key, manifest, f"{key}: components load from their default locations")
        skill_meta, _ = frontmatter(PLUGIN / "skills/scio/SKILL.md")
        self.assertEqual(skill_meta["metadata"]["version"], manifest["version"], "skill metadata tracks the release")

    def test_directory_listing_fields(self):
        manifest = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text())
        for key in ("documentationUrl", "supportUrl", "privacyPolicyUrl", "termsOfServiceUrl"):
            self.assertTrue(manifest[key].startswith("https://"), key)
        icon = PLUGIN / manifest["icon"]
        self.assertTrue(icon.resolve().is_relative_to(PLUGIN.resolve()))
        data = icon.read_bytes()
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"), "PNG or JPEG only; SVG and WebP are refused")
        width, height = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
        self.assertEqual(width, height, "the icon must be square")
        self.assertTrue(512 <= width <= 2048, width)
        self.assertLess(len(data), 2 * 1024 * 1024)

    def test_readme_and_license(self):
        readme = (PLUGIN / "README.md").read_text(encoding="utf-8")
        self.assertGreaterEqual(len(words_outside_code(readme)), 40)
        for disclosure in ("https://scio.md/connect", "## Data", "privacy", "OAuth"):
            self.assertIn(disclosure, readme)
        self.assertIn("Apache License", (PLUGIN / "LICENSE").read_text())
        # Directory policy 3B, 3C, 3E: support and security contact, troubleshooting, three or more example prompts.
        for section in ("## Examples", "## Troubleshooting", "## Security", "support@scio.md"):
            self.assertIn(section, readme)
        examples = readme.split("## Examples", 1)[1].split("\n## ", 1)[0]
        self.assertGreaterEqual(examples.count('\n- "'), 3)

    def test_mcp_is_one_remote_oauth_server(self):
        config = json.loads((PLUGIN / ".mcp.json").read_text())
        self.assertEqual(config, {"mcpServers": {"scio": {"type": "http", "url": "https://scio.md/connect"}}})

    def test_skill_frontmatter_is_portable(self):
        skills = sorted((PLUGIN / "skills").glob("*/SKILL.md"))
        self.assertEqual([p.parent.name for p in skills], ["scio"])
        for path in skills:
            meta, body = frontmatter(path)
            self.assertLessEqual(set(meta), PORTABLE_SKILL_KEYS, "claude.ai rejects other keys")
            self.assertEqual(meta["name"], path.parent.name)
            self.assertRegex(meta["name"], r"^[a-z0-9-]{1,64}$")
            self.assertIsInstance(meta["description"], str)
            self.assertLessEqual(len(meta["description"]), 1024)
            self.assertLess(len(body.splitlines()), 500)

    def test_commands_have_text_descriptions(self):
        commands = sorted((PLUGIN / "commands").glob("*.md"))
        self.assertEqual([p.stem for p in commands], ["review", "start", "status", "tasks", "write"])
        for path in commands:
            meta, body = frontmatter(path)
            self.assertLessEqual(set(meta), COMMAND_KEYS, path.name)
            self.assertIsInstance(meta["description"], str)
            self.assertIn("Use when", meta["description"], "chat loads commands as skills, triggered by description")
            self.assertIn("`scio` skill", body, "commands route to the skill's references")

    def test_agents_load_as_plugin_agents(self):
        agents = sorted((PLUGIN / "agents").glob("*.md"))
        self.assertEqual([p.stem for p in agents], ["scio-refuter", "scio-researcher", "scio-reviewer", "scio-writer"])
        contract = self.contract_tools()
        for path in agents:
            meta, body = frontmatter(path)
            self.assertEqual(meta["name"], path.stem)
            self.assertNotIn(":", meta["name"])
            self.assertIsInstance(meta["description"], str)
            self.assertLessEqual(set(meta), AGENT_KEYS, path.name)
            self.assertFalse(set(meta) & IGNORED_FOR_PLUGIN_AGENTS)
            self.assertNotIn("tools", meta, "an allowlist that resolves to nothing stops the agent from launching")
            denied = [t.strip() for t in meta["disallowedTools"].split(",")]
            for tool in ("scio_propose_edit", "scio_contest", "scio_suspend", "scio_register", "scio_report"):
                self.assertIn(f"mcp__plugin_scio-knowledge_scio__{tool}", denied, f"{path.name} must not {tool}")
            for tool in denied:
                self.assertTrue(tool.startswith("mcp__plugin_scio-knowledge_scio__scio_"), tool)
                if contract:
                    self.assertIn(tool.removeprefix("mcp__plugin_scio-knowledge_scio__"), contract)
            self.assertIn("data", body)
        reviewer, _ = frontmatter(PLUGIN / "agents/scio-reviewer.md")
        self.assertNotIn("mcp__plugin_scio-knowledge_scio__scio_review", reviewer["disallowedTools"])

    def test_relative_links_resolve(self):
        link = re.compile(r"\]\(([^)\s]+)\)")
        for path in plugin_files():
            if path.suffix != ".md":
                continue
            prose = re.sub(r"```.*?```", " ", path.read_text(encoding="utf-8"), flags=re.S)
            prose = re.sub(r"`[^`\n]*`", " ", prose)
            for target in link.findall(prose):
                if re.match(r"^[a-z]+:", target) or target.startswith("#"):
                    continue
                resolved = (path.parent / target.split("#")[0]).resolve()
                self.assertTrue(resolved.exists(), f"{path.relative_to(PLUGIN)} → {target}")
                self.assertTrue(resolved.is_relative_to(PLUGIN), f"{target} leaves the plugin folder")

    def test_no_local_runtime_or_credentials(self):
        for path in plugin_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            rel = path.relative_to(PLUGIN)
            for marker in LOCAL_RUNTIME:
                self.assertNotIn(marker, text, f"{rel} depends on the local multi-harness runtime")
            for pattern in SECRET_PATTERNS:
                self.assertIsNone(pattern.search(text), f"{rel} looks like it contains a credential")
            self.assertIsNone(re.search(r"(?m)^\s*!`", text), f"{rel}: shell injection does not run in chat or Cowork")

    def test_register_is_only_ever_forbidden(self):
        for path in plugin_files():
            if path.suffix != ".md":
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if "scio_register" in line and not path.parent.name == "agents":
                    self.assertRegex(line.lower(), r"never call|never ask|do not call", f"{path.name}: {line[:120]}")

    def test_tool_names_exist_and_workflows_cover_the_contract(self):
        contract = self.contract_tools()
        if not contract:
            self.skipTest("the sibling Scio platform contract is not available")
        mentioned = set()
        for path in plugin_files():
            if path.suffix == ".md":
                mentioned |= set(re.findall(r"\bscio_[a-z_]+\b", path.read_text(encoding="utf-8")))
        unknown = mentioned - set(contract)
        self.assertFalse(unknown, f"not tools of the contract: {sorted(unknown)}")
        self.assertEqual(set(contract) - mentioned, set(), "every tool has guidance")
        self.assertTrue(contract["scio_get_article"]["readOnly"] is False, "article reads can debit points")
        rules_parts = contract["scio_get_rules"]["input"]["properties"]["part"]["enum"]
        skill = (PLUGIN / "skills/scio/SKILL.md").read_text()
        self.assertIn("numbers", rules_parts)
        self.assertIn('part: "numbers"', skill)

    def test_policy_section_2_wording(self):
        # Directory policy 2D-2F: no trigger on generic questions, no restriction of other sources,
        # no instructions pulled from the server.
        meta, _ = frontmatter(PLUGIN / "skills/scio/SKILL.md")
        self.assertNotIn("encyclopedic facts", meta["description"])
        for path in plugin_files():
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("other sources only if", text, path.relative_to(PLUGIN))
            self.assertNotIn("follow the served", text, path.relative_to(PLUGIN))
            self.assertNotIn("served version is authoritative", text, path.relative_to(PLUGIN))
            # 2F: the constitution text is bundled, never fetched at runtime to steer behaviour.
            self.assertNotIn('part: "constitution"', text, path.relative_to(PLUGIN))
        # 2D/2B: every report is filed only on the person's yes.
        for path in plugin_files():
            if path.name == "rules.md":  # the signed constitution, quoted verbatim
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if re.search(r"\b(is reported|report it)\b", line):
                    self.assertRegex(line, r"offer|person's yes|agreement|person agrees", f"{path.name}: {line[:100]}")

    def test_claude_named_only_where_needed(self):
        # Anthropic's marks appear only as surface names, URLs, required paths and harness ids — never as
        # our branding or as the subject of the plugin's prose.
        allowed = re.compile(r"claude\.ai|Claude Code|\.claude-plugin|claude-code")
        targets = plugin_files() + [ROOT / ".claude-plugin/marketplace.json"]
        for path in targets:
            remainder = allowed.sub("", path.read_text(encoding="utf-8"))
            self.assertNotRegex(remainder, r"(?i)claude", path.relative_to(ROOT))

    def test_no_promise_of_a_server_side_scan(self):
        # The old local bridge annotated content; the remote server does not, so the skill must not say it does.
        for path in plugin_files():
            text = path.read_text(encoding="utf-8").lower()
            for claim in ("prepends its findings", "prepends a scanner note", "server runs an injection scanner"):
                self.assertNotIn(claim, text, path.relative_to(PLUGIN))

    def test_idempotency_guidance_matches_the_contract(self):
        contract = self.contract_tools()
        if not contract:
            self.skipTest("the sibling Scio platform contract is not available")
        keyed = {name for name, tool in contract.items() if "idempotency_key" in tool["input"].get("properties", {})}
        line = next(l for l in (PLUGIN / "skills/scio/SKILL.md").read_text().splitlines() if "**Idempotency.**" in l)
        named = set(re.findall(r"`(scio_[a-z_]+)`", line.split("take an `idempotency_key`")[0]))
        self.assertEqual(named, keyed)

    def test_portal_scan_patterns(self):
        # UNREAD_ASSET_REFERENCED: a bundled image is named only from plugin.json, never in Markdown.
        # MCP_FORWARDS_CREDENTIAL_ENV: no credential vocabulary in a file that also names the Scio host.
        credential = re.compile(r"(?i)api key|access tokens?|bearer|credentials?|\bpass(ed|es|ing|word)?\b|log ?in\b|\$\{[A-Za-z_]+\}")
        bundled = [p for p in PLUGIN.rglob("*") if p.is_file() and p.suffix in IMAGE_SUFFIXES]
        for path in plugin_files():
            text = path.read_text(encoding="utf-8")
            rel = path.relative_to(PLUGIN)
            if path.suffix == ".md":
                for image in bundled:
                    self.assertNotIn(image.name, text, f"{rel} names the bundled image {image.name}")
            if "scio.md" in text and path.name != "rules.md":  # rules.md is the signed constitution, verbatim
                self.assertIsNone(credential.search(text), rel)

    def test_review_reads_every_page_of_a_panel(self):
        contract = self.contract_tools()
        if not contract:
            self.skipTest("the sibling Scio platform contract is not available")
        if "next_cursor" not in contract["scio_get_panel"]["output"]["properties"]:
            self.skipTest("this contract does not page panels")
        for rel in ("skills/scio/references/review.md", "agents/scio-reviewer.md", "commands/review.md"):
            text = (PLUGIN / rel).read_text(encoding="utf-8")
            self.assertIn("next_cursor", text, rel)
            self.assertNotIn("no paging", text, rel)

    def test_marketplace_lists_the_plugin_folder(self):
        market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        self.assertEqual(market["name"], "scio")
        self.assertEqual([(p["name"], p["source"]) for p in market["plugins"]], [("scio-knowledge", "./scio")])

    @unittest.skipUnless(shutil.which("claude"), "Claude Code CLI not installed")
    def test_claude_plugin_validate(self):
        for target in (PLUGIN, ROOT):
            result = subprocess.run(["claude", "plugin", "validate", str(target)], capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Validation passed", result.stdout)

    @staticmethod
    def contract_tools():
        if not CONTRACT.exists():
            return {}
        return {tool["name"]: tool for tool in json.loads(CONTRACT.read_text())["tools"]}


if __name__ == "__main__":
    unittest.main()
