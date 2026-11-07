#!/usr/bin/env python3
"""Zip the plugin folder for claude.ai's Customize → Plugins → Upload plugin.

The archive holds the `scio/` folder as its single top-level entry, so
`.claude-plugin/plugin.json` sits one level down, as the upload expects.
Writes dist/<plugin name>-<version>.zip and prints its path and SHA-256.

    python3 scripts/build_zip.py               # local build
    python3 scripts/build_zip.py --tag v0.1.1  # CI: refuse unless the tag matches the version

The manifest's `version` and the skill's `metadata.version` must agree.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "scio"
SKILL = PLUGIN / "skills" / "scio" / "SKILL.md"
REFUSED = {".DS_Store", "Thumbs.db", "desktop.ini", "__MACOSX", "__pycache__", "evals"}


def versions() -> tuple[str, str]:
    manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
    front = SKILL.read_text().split("---", 2)[1]
    match = re.search(r'^\s+version:\s*"?([^"\s]+)"?\s*$', front, re.MULTILINE)
    if not match:
        raise SystemExit(f"no metadata.version in {SKILL.relative_to(ROOT)}")
    if manifest["version"] != match.group(1):
        raise SystemExit(f"plugin.json version {manifest['version']} != skill metadata.version {match.group(1)}")
    return manifest["name"], manifest["version"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", help="release tag; must be v<version>")
    args = parser.parse_args()

    name, version = versions()
    if args.tag is not None and args.tag != f"v{version}":
        raise SystemExit(f"tag {args.tag} does not match plugin version {version} (expected v{version})")

    files = sorted(p for p in PLUGIN.rglob("*") if p.is_file())
    for path in files:
        rel = path.relative_to(PLUGIN)
        if REFUSED & set(rel.parts) or path.is_symlink():
            raise SystemExit(f"refusing to package {rel}")
    output = ROOT / "dist" / f"{name}-{version}.zip"
    output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            info = zipfile.ZipInfo(str(Path("scio") / path.relative_to(PLUGIN)), date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(f"{output}  {len(files)} files  sha256 {digest}")
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as out:
            out.write(f"zip={output.relative_to(ROOT)}\nsha256={digest}\nversion={version}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
