"""Read-only checks for the orgkk001 -> hrlang001 release.

Run from the extracted package with --repo pointing to the server checkout.
Never writes the database. Keeps server template files and personnel data intact.
"""
import argparse
import hashlib
import json
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def snapshot(repo, engine):
    protected_files = sorted(set(
        list((repo / "app/services").rglob("*.py"))
        + [repo / "corpsite-ui/app/directory/personnel/_lib/personnelOrderCanonicalTitles.ts",
           repo / "corpsite-ui/app/directory/personnel/_components/personnelOrderDocumentTemplates.ts"]
    ))
    files = {str(path.relative_to(repo)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in protected_files if path.is_file()}
    tables = {}
    with engine.connect() as conn:
        names = conn.execute(text("""
            SELECT tablename FROM pg_tables WHERE schemaname='public'
            AND (tablename LIKE 'personnel_order%' OR tablename='employee_events')
            ORDER BY tablename
        """)).scalars().all()
        for name in names:
            # Identifier comes exclusively from pg_catalog; quote it explicitly.
            quoted = conn.dialect.identifier_preparer.quote(name)
            rows = conn.execute(text(f"SELECT row_to_json(t)::text FROM public.{quoted} t ORDER BY row_to_json(t)::text")).scalars().all()
            tables[name] = {"rows": len(rows), "sha256": hashlib.sha256("\n".join(rows).encode()).hexdigest()}
    return {"files": files, "tables": tables}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    values = dotenv_values(repo / ".env")
    url = make_url(values["DATABASE_URL"])
    if url.host not in {"localhost", "127.0.0.1", "::1"} or url.database != "corpsite":
        raise SystemExit("STOP: expected the server's loopback corpsite database from its .env")
    engine = create_engine(url, hide_parameters=True)
    config = Config(str(repo / "alembic.ini"))
    config.set_main_option("script_location", str(repo / "alembic"))
    script = ScriptDirectory.from_config(config)
    with engine.connect() as conn:
        current = list(MigrationContext.configure(conn).get_current_heads())
    expected = "orgkk001" if args.phase == "before" else "hrlang001"
    if current != [expected] or script.get_heads() != [expected]:
        raise SystemExit(f"STOP: expected one current revision and one repository head {expected}; current={current}, heads={script.get_heads()}")
    if args.phase == "after" and script.get_revision("hrlang001").down_revision != "orgkk001":
        raise SystemExit("STOP: unexpected hrlang001 parent")
    actual = snapshot(repo, engine)
    if args.phase == "before":
        args.state.parent.mkdir(parents=True, exist_ok=True)
        with args.state.open("x", encoding="utf-8") as handle:
            json.dump(actual, handle, ensure_ascii=False, indent=2)
    else:
        previous = json.loads(args.state.read_text(encoding="utf-8"))
        if actual != previous:
            changed_files = sorted(key for key in set(actual["files"]) | set(previous["files"]) if actual["files"].get(key) != previous["files"].get(key))
            changed_tables = sorted(key for key in set(actual["tables"]) | set(previous["tables"]) if actual["tables"].get(key) != previous["tables"].get(key))
            raise SystemExit(f"STOP: protected data changed; files={changed_files}, tables={changed_tables}")
        with engine.connect() as conn:
            setting = conn.execute(text("SELECT language FROM public.personnel_section_settings WHERE settings_id=1")).scalar_one()
        if setting != "kk":
            raise SystemExit("STOP: expected initial shared language kk")
    engine.dispose()
    print(f"OK: {expected}; {len(actual['files'])} protected files; {len(actual['tables'])} personnel tables; no database writes")


if __name__ == "__main__":
    main()
