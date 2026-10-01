"""Safely back up and remove explicitly named local Corpsite test databases.

The default is a non-mutating dry run.  This tool deliberately has no wildcard
or prefix expansion: every database to act on must be passed with ``--database``.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
from psycopg2 import sql
from sqlalchemy.engine import make_url


CONFIRMATION = "DELETE LOCAL TEST DATABASES"
PROTECTED_DATABASES = frozenset({"corpsite", "postgres", "template0", "template1"})
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class SafetyError(RuntimeError):
    """Raised before any destructive SQL is issued."""


def _database_url(value: str | None) -> str:
    if value:
        return value.strip()
    try:
        from dotenv import load_dotenv

        load_dotenv(REPOSITORY_ROOT / ".env", override=False)
    except ImportError:
        pass
    value = os.environ.get("DATABASE_URL", "").strip()
    if not value:
        raise SafetyError("DATABASE_URL is required (or pass --database-url).")
    return value


def _validated_url(value: str):
    url = make_url(value)
    if url.get_backend_name() != "postgresql":
        raise SafetyError("Only PostgreSQL URLs are allowed.")
    if url.host not in LOOPBACK_HOSTS:
        raise SafetyError("Refusing non-loopback PostgreSQL host.")
    if not url.database:
        raise SafetyError("Database name is required in DATABASE_URL.")
    return url


def _is_test_database(name: str) -> bool:
    """Permit only clearly test-named exact targets, never a production-like name."""
    lowered = name.lower()
    return lowered == "corpsite_test" or lowered.endswith("_test") or lowered.startswith("corpsite_h8i9_")


def _validate_targets(targets: list[str]) -> list[str]:
    if not targets:
        raise SafetyError("At least one exact --database name is required.")
    if len(set(targets)) != len(targets):
        raise SafetyError("Duplicate --database names are not allowed.")
    for name in targets:
        if not name or any(char in name for char in "*?[]"):
            raise SafetyError("Wildcards are forbidden; pass exact database names only.")
        if name in PROTECTED_DATABASES:
            raise SafetyError(f"Protected database cannot be removed: {name}")
        if not _is_test_database(name):
            raise SafetyError(f"Database name is not recognised as a local test target: {name}")
    return targets


def _connect(url, database: str):
    return psycopg2.connect(
        host=url.host,
        port=url.port or 5432,
        user=url.username,
        password=url.password,
        dbname=database,
        connect_timeout=10,
    )


def _listed_databases(conn) -> set[str]:
    with conn.cursor() as cursor:
        cursor.execute("SELECT datname FROM pg_database WHERE datallowconn")
        return {str(row[0]) for row in cursor.fetchall()}


def _outside_repository(path: Path) -> None:
    try:
        path.resolve().relative_to(REPOSITORY_ROOT.resolve())
    except ValueError:
        return
    raise SafetyError("Backup directory must be outside the Git repository.")


def _pg_dump_command(args, url, database: str) -> list[str]:
    common = [
        "pg_dump", "--format=custom", "--host=127.0.0.1", f"--port={url.port or 5432}",
        f"--username={url.username}", "--no-owner", "--no-privileges", database,
    ]
    if args.docker_container:
        return ["docker", "exec", "-e", "PGPASSWORD", args.docker_container, *common]
    return common


def _backup_all(args, url, targets: list[str], backup_dir: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    environment = os.environ.copy()
    if url.password:
        environment["PGPASSWORD"] = url.password
    for database in targets:
        output = backup_dir / f"{database}.dump"
        command = _pg_dump_command(args, url, database)
        with output.open("wb") as stream:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.PIPE, env=environment, check=False)
        size = output.stat().st_size if output.exists() else 0
        if result.returncode != 0 or size == 0:
            output.unlink(missing_ok=True)
            detail = result.stderr.decode("utf-8", errors="replace").strip().splitlines()[-1:]
            raise SafetyError(f"Backup failed for {database}: {' '.join(detail)}")
        records.append({"database": database, "backup": str(output), "bytes": size})
    return records


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", action="append", required=True, help="Exact local test database name; repeat for each target.")
    parser.add_argument("--database-url", help="Local maintenance URL; defaults to DATABASE_URL/.env.")
    parser.add_argument("--backup-dir", help="Existing-or-new directory outside this repository for pg_dump files and reports.")
    parser.add_argument("--docker-container", default="corpsite-pg", help="Docker container used to run pg_dump; pass an empty value to use host pg_dump.")
    parser.add_argument("--execute", action="store_true", help="Actually back up and delete after all checks succeed.")
    parser.add_argument("--confirm", default="", help=f"Required with --execute: {CONFIRMATION!r}")
    args = parser.parse_args()

    url = _validated_url(_database_url(args.database_url))
    targets = _validate_targets(args.database)
    maintenance = _connect(url, "postgres")
    maintenance.autocommit = True  # DROP DATABASE cannot run in a transaction.
    try:
        existing = _listed_databases(maintenance)
        missing = [name for name in targets if name not in existing]
        if missing:
            raise SafetyError(f"Target database does not exist: {', '.join(missing)}")
        manifest = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mode": "execute" if args.execute else "dry-run",
            "server": {"host": url.host, "port": url.port or 5432},
            "targets": targets,
            "protected": sorted(PROTECTED_DATABASES),
        }
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        if not args.execute:
            return 0
        if args.confirm != CONFIRMATION:
            raise SafetyError(f"--confirm must be exactly: {CONFIRMATION}")
        if not args.backup_dir:
            raise SafetyError("--backup-dir is required with --execute.")
        backup_dir = Path(args.backup_dir).expanduser().resolve()
        _outside_repository(backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        _write_json(backup_dir / "manifest.json", manifest)

        backups = _backup_all(args, url, targets, backup_dir)
        # Every backup is complete and non-empty before the first termination/DROP.
        for database in targets:
            with maintenance.cursor() as cursor:
                cursor.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (database,))
                cursor.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))
        remaining = sorted(_listed_databases(maintenance))
        report = {**manifest, "backups": backups, "deleted": targets, "remaining_databases": remaining}
        _write_json(backup_dir / "report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    finally:
        maintenance.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SafetyError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        raise SystemExit(2)
