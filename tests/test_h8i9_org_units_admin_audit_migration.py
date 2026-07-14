# tests/test_h8i9_org_units_admin_audit_migration.py
"""Migration behavior tests for h8i9j0k1l2m3 org_units admin audit events."""
from __future__ import annotations

import os
from contextlib import contextmanager
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from app.db.engine import engine

REVISION_H8I9 = "h8i9j0k1l2m3"
REVISION_D4E5 = "d4e5f6a7b8c9"

_ORG_UNIT_EVENT_TYPES = (
    "ORG_UNIT_CREATED",
    "ORG_UNIT_UPDATED",
    "ORG_UNIT_ACTIVATED",
    "ORG_UNIT_DEACTIVATED",
    "ORG_UNIT_DELETED",
    "ORG_UNIT_DELETE_REJECTED",
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _alembic_config(*, database_url: str | None = None) -> Config:
    cfg = Config("alembic.ini")
    url = database_url or str(engine.url.render_as_string(hide_password=False))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def _migration_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "h8i9j0k1l2m3_org_units_admin_audit_events.py"
    )
    spec = spec_from_file_location("h8i9_org_units_admin_audit_migration", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load migration from {path}")
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _org_unit_audit_count(*, database_url: str | None = None) -> int:
    target = create_engine(database_url or str(engine.url.render_as_string(hide_password=False)))
    with target.connect() as conn:
        types_sql = ", ".join(f"'{event_type}'" for event_type in _ORG_UNIT_EVENT_TYPES)
        return int(
            conn.execute(
                text(
                    f"""
                    SELECT COUNT(*)::bigint
                    FROM public.security_audit_log
                    WHERE event_type IN ({types_sql})
                    """
                )
            ).scalar()
            or 0
        )


def _alembic_version(*, database_url: str | None = None) -> str:
    target = create_engine(database_url or str(engine.url.render_as_string(hide_password=False)))
    with target.connect() as conn:
        return str(conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one())


def _sal_constraint_has_org_unit_types(*, database_url: str | None = None) -> bool:
    target = create_engine(database_url or str(engine.url.render_as_string(hide_password=False)))
    with target.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conname = 'chk_sal_event_type'
                """
            )
        ).scalar()
    return bool(row and "ORG_UNIT_CREATED" in str(row))


@contextmanager
def _database_url_override(database_url: str):
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


@contextmanager
def _ephemeral_database_without_org_unit_audit_rows():
    db_name = f"corpsite_h8i9_{uuid4().hex[:12]}"
    admin_url = str(engine.url.render_as_string(hide_password=False)).rsplit("/", 1)[0] + "/postgres"
    test_url = str(engine.url.render_as_string(hide_password=False)).rsplit("/", 1)[0] + f"/{db_name}"
    engine.dispose()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    test_engine = create_engine(test_url)

    with admin_engine.connect() as conn:
        conn.execute(
            text(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = 'corpsite' AND pid <> pg_backend_pid()
                """
            )
        )
        conn.execute(text(f'CREATE DATABASE "{db_name}" TEMPLATE corpsite'))

    try:
        with test_engine.begin() as conn:
            conn.execute(
                text(
                    """
                    DELETE FROM public.security_audit_log
                    WHERE event_type LIKE 'ORG_UNIT_%'
                    """
                )
            )
        assert _org_unit_audit_count(database_url=test_url) == 0
        yield test_url, test_engine
    finally:
        test_engine.dispose()
        with admin_engine.connect() as conn:
            conn.execute(
                text(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = :db_name AND pid <> pg_backend_pid()
                    """
                ),
                {"db_name": db_name},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
        admin_engine.dispose()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_revision_chain() -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    rev = script.get_revision(REVISION_H8I9)
    assert rev is not None
    assert rev.down_revision == REVISION_D4E5


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_downgrade_blocked_when_org_unit_audit_rows_exist() -> None:
    cfg = _alembic_config()
    before_count = _org_unit_audit_count()
    assert before_count > 0

    with pytest.raises(RuntimeError, match="Downgrade of revision h8i9j0k1l2m3 is blocked"):
        command.downgrade(cfg, REVISION_D4E5)

    assert _alembic_version() == REVISION_H8I9
    assert _org_unit_audit_count() == before_count
    assert _sal_constraint_has_org_unit_types()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_downgrade_blocked_preserves_schema_before_constraint_change() -> None:
    mod = _migration_module()
    before_count = _org_unit_audit_count()
    before_has_org_unit = _sal_constraint_has_org_unit_types()

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            with pytest.raises(RuntimeError, match="Downgrade of revision h8i9j0k1l2m3 is blocked"):
                mod.downgrade()

    assert _alembic_version() == REVISION_H8I9
    assert _org_unit_audit_count() == before_count
    assert _sal_constraint_has_org_unit_types() == before_has_org_unit


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_downgrade_succeeds_and_reupgrade_on_isolated_database() -> None:
    with _ephemeral_database_without_org_unit_audit_rows() as (test_url, _test_engine):
        with _database_url_override(test_url):
            cfg = _alembic_config(database_url=test_url)
            assert _alembic_version(database_url=test_url) == REVISION_H8I9
            assert _sal_constraint_has_org_unit_types(database_url=test_url)

            command.downgrade(cfg, REVISION_D4E5)
            assert _alembic_version(database_url=test_url) == REVISION_D4E5
            assert not _sal_constraint_has_org_unit_types(database_url=test_url)

            command.upgrade(cfg, REVISION_H8I9)
            assert _alembic_version(database_url=test_url) == REVISION_H8I9
            assert _sal_constraint_has_org_unit_types(database_url=test_url)
