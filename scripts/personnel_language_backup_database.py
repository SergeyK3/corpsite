"""Back up the server database using its existing .env, without logging secrets."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import make_url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--container", default="corpsite-pg")
    args = parser.parse_args()
    url = make_url(dotenv_values(args.repo.resolve() / ".env")["DATABASE_URL"])
    if url.host not in {"localhost", "127.0.0.1", "::1"} or url.database != "corpsite":
        raise SystemExit("STOP: expected loopback corpsite database from server .env")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    native = shutil.which("pg_dump")
    if native:
        command = [native, "--format=custom", "--host", url.host, "--port", str(url.port or 5432),
                   "--username", url.username, "--dbname", url.database]
        env = dict(os.environ, PGPASSWORD=url.password or "")
    else:
        ports = json.loads(subprocess.check_output([
            "docker", "inspect", "--format", "{{json .NetworkSettings.Ports}}", args.container
        ]))
        bindings = ports.get("5432/tcp") or []
        if not any(binding["HostPort"] == str(url.port or 5432) and binding["HostIp"] in {"127.0.0.1", "::1", "0.0.0.0", "::"} for binding in bindings):
            raise SystemExit("STOP: Docker PostgreSQL port does not match server .env")
        command = ["docker", "exec", args.container, "pg_dump", "--format=custom", "--username", url.username, "--dbname", url.database]
        env = os.environ.copy()
    with args.output.open("xb") as handle:
        subprocess.run(command, env=env, stdout=handle, check=True)
    if not args.output.stat().st_size:
        raise SystemExit("STOP: empty database backup")
    digest = hashlib.sha256()
    with args.output.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    args.output.with_suffix(args.output.suffix + ".sha256").write_text(digest.hexdigest() + "  " + args.output.name + "\n", encoding="ascii")
    print("Database backup:", args.output, "bytes:", args.output.stat().st_size)


if __name__ == "__main__":
    main()
