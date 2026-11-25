"""Create a deterministic, secret-free source snapshot from the accepted test stage."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import sys
import tarfile
from pathlib import Path

OVERLAY_SHA = "0cf613ec338b674ddfd2534760432271c76759f51f7486e903245f6830d0f3cd"
ROOT = Path("/opt/projects/corpsite-hire-prep/releases")
PREFIX = f"20261125-order67-prod-base-{OVERLAY_SHA[:12]}"
SOURCES = {"backend": ROOT / f"{PREFIX}-backend", "frontend": ROOT / f"{PREFIX}-frontend"}
EXCLUDE_DIRS = {".git", ".venv", "node_modules", ".next", "runtime", ".vscode", "__pycache__",
                ".pytest_cache", "secrets", ".aws", ".codex", ".agents", "docs-work"}
EXCLUDE_FILES = {"order67-build.log", "stage0.png", "release-manifest.json"}


def files():
    for area, root in SOURCES.items():
        if not root.is_dir():
            raise SystemExit(f"Missing accepted source: {root}")
        for path in sorted(root.rglob("*")):
            if any(part in EXCLUDE_DIRS for part in path.relative_to(root).parts):
                continue
            if path.is_symlink() or not path.is_file():
                continue
            if path.name in EXCLUDE_FILES or path.name.startswith(".env") or path.suffix == ".pyc":
                continue
            yield f"{area}/{path.relative_to(root).as_posix()}", path


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: snapshot_order67_verified.py output.tar.gz")
    output = Path(sys.argv[1])
    if output.exists():
        raise SystemExit(f"Output exists: {output}")
    members = list(files())
    manifest = {"overlay_sha256": OVERLAY_SHA,
                "accepted_test_source": PREFIX,
                "files": {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in members}}
    with output.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as archive:
            for name, path in members:
                data = path.read_bytes()
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mode = 0o644
                info.mtime = info.uid = info.gid = 0
                archive.addfile(info, io.BytesIO(data))
            data = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
            info = tarfile.TarInfo("release-source-manifest.json")
            info.size = len(data)
            info.mode = 0o644
            info.mtime = info.uid = info.gid = 0
            archive.addfile(info, io.BytesIO(data))
    print(json.dumps({"package": str(output), "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                      "files": len(members), "size": output.stat().st_size}))


if __name__ == "__main__":
    main()
