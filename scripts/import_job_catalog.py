"""Local-only dry-run by default. Never mutates employee assignments or old positions."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from app.services.job_catalog_service import read_catalog, plan_catalog, database_plan, apply_catalog, source_sha256


def migration_preflight(conn, config_path="alembic.ini", required_revision="jobcat001"):
    versions = list(conn.execute(text("SELECT version_num FROM public.alembic_version")).scalars())
    config = Config(str(Path(__file__).resolve().parents[1] / config_path))
    scripts = ScriptDirectory.from_config(config)
    result = {"current_revisions": versions, "required_revision": required_revision, "blockers": []}
    ancestors = set()
    for version in versions:
        try:
            scripts.get_revision(version)
            ancestors.update(revision.revision for revision in scripts.iterate_revisions(version, "base"))
        except CommandError:
            result["blockers"].append(f"Unknown Alembic revision: {version}")
    if not versions:
        result["blockers"].append("Database has no Alembic revision")
    if required_revision not in ancestors:
        result["blockers"].append(f"Required migration is not applied: {required_revision}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="reference-data/job-positions/catalog-v1.json")
    parser.add_argument("--alembic-config", default="alembic.ini")
    parser.add_argument("--required-revision", default="jobcat001")
    parser.add_argument("--report", default="docs-work/job_catalog_dry_run.json")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    rows = read_catalog(args.source)
    plan = plan_catalog(rows)
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    url = make_url(os.environ["DATABASE_URL"])
    if url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("Only a loopback database is allowed")
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 3}, hide_parameters=True)
        with engine.connect() as conn:
            with conn.begin():
                if not args.apply:
                    conn.execute(text("SET TRANSACTION READ ONLY"))
                migration = migration_preflight(conn, args.alembic_config, args.required_revision)
                if args.apply and migration["blockers"]:
                    raise SystemExit("Import blocked: " + str(migration))
                plan = apply_catalog(conn, rows) if args.apply else database_plan(conn, rows)
                plan["migration"] = migration
                plan["target"] = {"host": url.host, "port": url.port or 5432, "database": url.database}
                plan["can_apply"] = plan["can_apply"] and not migration["blockers"]
    except OperationalError:
        if args.apply:
            raise SystemExit("Local database unavailable; nothing applied")
        plan["database_error"] = "Local database unavailable; existing IDs and database conflicts NOT checked"
    plan["source_sha256"] = source_sha256(args.source)
    plan["applied"] = args.apply
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in plan.items() if k != "mappings"}, ensure_ascii=True, indent=2))
    print(f"Full mapping: {path}")


if __name__ == "__main__":
    main()
