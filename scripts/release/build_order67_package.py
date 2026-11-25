"""Build a deterministic source overlay for the electronic HIRE release."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILE_LIST = ROOT / "docs/deploy/order-67-source-files.json"
TEXT_SUFFIXES = {".py", ".ts", ".tsx", ".json", ".txt", ".md", ".ini"}


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def source_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix in TEXT_SUFFIXES or path.name == "requirements.txt":
        data = data.replace(b"\r\n", b"\n")
    return data


def archive_name(name: str) -> str:
    if name.startswith("corpsite-ui/"):
        return "frontend/" + name.removeprefix("corpsite-ui/")
    if name.startswith(("app/", "alembic/", "scripts/")) or name == "requirements.txt":
        return "backend/" + name
    if name.startswith("tests/"):
        return "checks/" + name
    if name.startswith("docs/deploy/"):
        return "docs/" + name.removeprefix("docs/")
    raise ValueError(f"Unapproved release path: {name}")


def initialize() -> None:
    names = git("ls-files", "-m", "-o", "--exclude-standard").splitlines()
    names = sorted(set(name for name in names if name and (ROOT / name).is_file()
                       and name.startswith(("app/", "alembic/", "corpsite-ui/", "tests/", "scripts/", "docs/deploy/"))
                       or name == "requirements.txt"))
    names = [name for name in names if name not in {
        "docs/deploy/order-67-source-files.json",
        "docs/deploy/order-67-release-readiness-20261125.md",
    }]
    for name in names:
        archive_name(name)
    FILE_LIST.write_text(json.dumps({"base": git("rev-parse", "origin/master"), "files": names},
                                    ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {FILE_LIST} with {len(names)} source files")


def add_member(tar: tarfile.TarFile, name: str, data: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mtime = 0
    info.mode = 0o644
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    tar.addfile(info, io.BytesIO(data))


def build(output: Path) -> None:
    listed = json.loads(FILE_LIST.read_text(encoding="utf-8"))
    if listed["base"] != git("rev-parse", "origin/master"):
        raise SystemExit("origin/master has changed; rebase and review the file list")
    files = sorted(set(listed["files"]))
    members: list[tuple[str, bytes]] = []
    for name in files:
        path = ROOT / name
        if not path.is_file():
            raise SystemExit(f"Missing source file: {name}")
        members.append((archive_name(name), source_bytes(path)))
    manifest = {
        "kind": "electronic-hire-source-overlay",
        "base_commit": listed["base"],
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in members},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as handle, gzip.GzipFile(fileobj=handle, mode="wb", filename="", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as tar:
            add_member(tar, "release-manifest.json", json.dumps(manifest, ensure_ascii=False,
                       sort_keys=True, indent=2).encode("utf-8") + b"\n")
            for name, data in members:
                add_member(tar, name, data)
    print(json.dumps({"package": str(output), "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                      "source_files": len(members)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--initialize", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "runtime/order67-release/source-overlay.tar.gz")
    args = parser.parse_args()
    if args.initialize:
        initialize()
    else:
        build(args.output)
