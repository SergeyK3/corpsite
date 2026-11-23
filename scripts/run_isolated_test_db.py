"""Run PostgreSQL tests against a disposable database with project seed data.

The historical grant migrations expect populated role/user and organization
catalogs.  These live outside Alembic in the project's initial-data SQL files.
Only a newly generated loopback ``corpsite_test_*_test`` database is touched.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TESTS = (
    "tests/test_personnel_order_termination_reason.py",
    "tests/test_personnel_order_numeric_search_readonly.py",
)


def _base_url(value: str) -> URL:
    if not value:
        raise ValueError("TEST_DATABASE_URL is required")
    url = make_url(value)
    if url.get_backend_name() != "postgresql" or url.host not in {"localhost", "127.0.0.1"}:
        raise ValueError("TEST_DATABASE_URL must target loopback PostgreSQL")
    if url.database != "corpsite_test":
        raise ValueError("TEST_DATABASE_URL must name the corpsite_test base database")
    return url


def _alembic_config(url: URL) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False).replace("%", "%%"))
    return config


def _apply_sql(url: URL, sql: str) -> None:
    engine = create_engine(url)
    try:
        connection = engine.raw_connection()
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(sql)
                connection.commit()
            finally:
                cursor.close()
        finally:
            connection.close()
    finally:
        engine.dispose()


def _read_sql(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _seed_catalogs(url: URL) -> None:
    canonical_seed = _read_sql("db/init/020_seed_roles_users_employees.sql")
    role_statement = re.search(
        r"(?ms)^INSERT INTO public\.roles\s*\(code, name\).*?^SET name = EXCLUDED\.name;",
        canonical_seed,
    )
    if role_statement is None or "('HR_HEAD'" not in role_statement.group():
        raise RuntimeError("Canonical HR_HEAD role seed was not found")

    # The legacy seed's employee IDs are text, while the current schema uses
    # numeric identities. Apply its canonical role catalog, then the maintained
    # pilot seed for real-schema users and employees.
    _apply_sql(url, role_statement.group())
    _apply_sql(
        url,
        """
        INSERT INTO public.roles(code, name)
        VALUES ('ADMIN', 'Isolated test administrator')
        ON CONFLICT (code) DO NOTHING;
        INSERT INTO public.org_units(unit_id, name, code)
        OVERRIDING SYSTEM VALUE
        VALUES (44, 'Isolated test unit', 'ISOLATED_TEST_UNIT')
        ON CONFLICT (unit_id) DO NOTHING;
        """,
    )
    _apply_sql(url, _read_sql("scripts/pilot/directory_prereq_bootstrap.sql"))
    _apply_sql(url, _read_sql("scripts/pilot/qm_roles_users_bootstrap.sql"))
    _apply_sql(url, _read_sql("tests/personnel_lk/adr065_test_org_bootstrap.sql"))

    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            counts = connection.execute(
                text(
                    """
                    SELECT
                      (SELECT COUNT(*) FROM roles WHERE code = 'HR_HEAD'),
                      (SELECT COUNT(*) FROM roles WHERE code = 'ADMIN'),
                      (SELECT COUNT(*) FROM users WHERE is_active),
                      (SELECT COUNT(*) FROM employees e
                       JOIN positions p ON p.position_id = e.position_id
                       JOIN org_units o ON o.unit_id = e.org_unit_id),
                      (SELECT COUNT(*) FROM org_units WHERE code = 'DISP'
                       AND parent_unit_id IS NOT NULL)
                    """
                )
            ).one()
            if counts[0] != 1 or counts[1] != 1 or min(counts[2:]) < 1:
                raise RuntimeError(f"Incomplete isolated test seed: {tuple(counts)}")
    finally:
        engine.dispose()


def run(base_url: URL, pytest_args: list[str]) -> int:
    database = f"corpsite_test_{uuid4().hex[:12]}_test"
    if not re.fullmatch(r"corpsite_test_[0-9a-f]{12}_test", database):
        raise RuntimeError("Unsafe generated database name")
    test_url = base_url.set(database=database)
    maintenance = create_engine(base_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    created = False
    try:
        with maintenance.connect() as connection:
            if connection.execute(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": database}).first():
                raise RuntimeError("Generated test database already exists")
            connection.exec_driver_sql(f"CREATE DATABASE {database}")
            created = True

        config = _alembic_config(test_url)
        command.upgrade(config, "h5c6d7e8f9a0")
        _seed_catalogs(test_url)
        command.upgrade(config, "head")
        print(f"Prepared isolated {database} at Alembic head", flush=True)

        env = os.environ.copy()
        env["TEST_DATABASE_URL"] = test_url.render_as_string(hide_password=False)
        env["DATABASE_URL"] = base_url.set(database="corpsite_guard_unused").render_as_string(hide_password=False)
        env["CORPSITE_SKIP_DOTENV"] = "1"
        args = pytest_args or list(DEFAULT_TESTS)
        if args and args[0] == "--":
            args = args[1:]
        return subprocess.run([sys.executable, "-m", "pytest", *args], cwd=ROOT, env=env, check=False).returncode
    finally:
        try:
            if created:
                with maintenance.connect() as connection:
                    connection.exec_driver_sql(f"DROP DATABASE {database} WITH (FORCE)")
                print(f"Removed isolated {database}", flush=True)
        finally:
            maintenance.dispose()


def main() -> int:
    load_dotenv(ROOT / ".env", override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER, help="pytest arguments after --")
    args = parser.parse_args()
    try:
        return run(_base_url(os.environ.get("TEST_DATABASE_URL", "")), args.pytest_args)
    except (RuntimeError, ValueError) as exc:
        parser.exit(2, f"{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
