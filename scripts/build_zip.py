#!/usr/bin/env python3
"""Zip the plugin folder for claude.ai's Customize → Plugins → Upload plugin.

The archive holds the `scio/` folder as its single top-level entry, so
`.claude-plugin/plugin.json` sits one level down, as the upload expects.
Writes dist/scio-plugin.zip and prints its path and SHA-256.
"""

import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "scio"
OUTPUT = ROOT / "dist" / "scio-plugin.zip"
REFUSED = {".DS_Store", "Thumbs.db", "desktop.ini", "__MACOSX", "__pycache__", "evals"}


def main() -> int:
    files = sorted(p for p in PLUGIN.rglob("*") if p.is_file())
    for path in files:
        rel = path.relative_to(PLUGIN)
        if REFUSED & set(rel.parts) or path.is_symlink():
            raise SystemExit(f"refusing to package {rel}")
    OUTPUT.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            info = zipfile.ZipInfo(str(Path("scio") / path.relative_to(PLUGIN)), date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    print(f"{OUTPUT}  {len(files)} files  sha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
