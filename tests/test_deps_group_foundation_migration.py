# tests/test_deps_group_foundation_migration.py
"""Migration tests for a0b1c2d3e4f6 deps_group_foundation."""
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
from app.medical_org_groups import MEDICAL_ORG_GROUPS
from tests.conftest import get_columns, table_exists
from tests.db_sequence_helpers import assert_sequence_not_behind

REVISION = "a0b1c2d3e4f6"
PREVIOUS_REVISION = "z8a9b0c1d2e3"
NEXT_REVISION = "b0c1d2e3f4a5"
MIGRATION_FILE = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "a0b1c2d3e4f6_deps_group_foundation.py"
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _admin_database_url() -> str:
    return str(engine.url.render_as_string(hide_password=False)).rsplit("/", 1)[0] + "/postgres"


def _alembic_config(*, database_url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return cfg


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
def _ephemeral_database():
    db_name = f"corpsite_dgf_{uuid4().hex[:12]}"
    admin_url = _admin_database_url()
    test_url = admin_url.rsplit("/", 1)[0] + f"/{db_name}"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    test_engine = create_engine(test_url)

    with admin_engine.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))

    try:
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


def _migration_module():
    spec = spec_from_file_location("deps_group_foundation_migration", MIGRATION_FILE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load migration from {MIGRATION_FILE}")
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _canonical_group_rows(conn) -> list[tuple[int, str]]:
    rows = conn.execute(
        text(
            """
            SELECT group_id, group_name
            FROM public.deps_group
            WHERE group_id IN (1, 2, 3)
            ORDER BY group_id
            """
        )
    ).all()
    return [(int(group_id), str(group_name)) for group_id, group_name in rows]


def _org_units_fk_exists(conn) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT 1
                FROM pg_constraint
                WHERE conrelid = 'public.org_units'::regclass
                  AND conname = 'fk_org_units_group'
                LIMIT 1
                """
            )
        ).scalar()
    )


def _decoy_fk_exists(conn) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT 1
                FROM pg_constraint c
                JOIN pg_class rel ON rel.oid = c.conrelid
                JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
                WHERE nsp.nspname = 'decoy_dgf'
                  AND rel.relname = 'other_units'
                  AND c.conname = 'fk_org_units_group'
                LIMIT 1
                """
            )
        ).scalar()
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_revision_chain() -> None:
    script = ScriptDirectory.from_config(_alembic_config(database_url=str(engine.url)))
    rev = script.get_revision(REVISION)
    assert rev is not None
    assert rev.down_revision == PREVIOUS_REVISION

    next_rev = script.get_revision(NEXT_REVISION)
    assert next_rev is not None
    assert next_rev.down_revision == REVISION


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_upgrade_on_empty_database_creates_table_seeds_and_fk() -> None:
    with _ephemeral_database() as (test_url, test_engine):
        cfg = _alembic_config(database_url=test_url)
        with _database_url_override(test_url):
            command.upgrade(cfg, REVISION)

        with test_engine.connect() as conn:
            assert table_exists(conn, "deps_group")
            cols = get_columns(conn, "deps_group")
            assert {"group_id", "group_name"}.issubset(cols)
            assert _canonical_group_rows(conn) == [
                (group.group_id, group.display_name_ru) for group in MEDICAL_ORG_GROUPS
            ]
            assert _org_units_fk_exists(conn)
            assert_sequence_not_behind(conn, "deps_group", "group_id")


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_upgrade_is_idempotent_with_existing_compatible_table() -> None:
    mod = _migration_module()
    custom_name = "Пользовательское имя группы 1"

    with _ephemeral_database() as (test_url, test_engine):
        cfg = _alembic_config(database_url=test_url)
        with _database_url_override(test_url):
            command.upgrade(cfg, PREVIOUS_REVISION)

        with test_engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE public.deps_group (
                        group_id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                        group_name TEXT NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO public.deps_group (group_id, group_name)
                    VALUES (1, :group_name), (99, 'Дополнительная группа')
                    """
                ),
                {"group_name": custom_name},
            )

        with test_engine.connect() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                mod.upgrade()
            conn.commit()
            with Operations.context(MigrationContext.configure(conn)):
                mod.upgrade()
            conn.commit()

            rows = conn.execute(
                text(
                    """
                    SELECT group_id, group_name
                    FROM public.deps_group
                    ORDER BY group_id
                    """
                )
            ).all()
            assert rows[0] == (1, custom_name)
            assert rows[1] == (2, MEDICAL_ORG_GROUPS[1].display_name_ru)
            assert rows[2] == (3, MEDICAL_ORG_GROUPS[2].display_name_ru)
            assert rows[3] == (99, "Дополнительная группа")
            assert _org_units_fk_exists(conn)
            assert_sequence_not_behind(conn, "deps_group", "group_id")


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_upgrade_rejects_incompatible_existing_table() -> None:
    mod = _migration_module()

    with _ephemeral_database() as (test_url, test_engine):
        cfg = _alembic_config(database_url=test_url)
        with _database_url_override(test_url):
            command.upgrade(cfg, PREVIOUS_REVISION)

        with test_engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE public.deps_group (
                        group_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                        label TEXT NOT NULL
                    )
                    """
                )
            )

        with test_engine.connect() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                with pytest.raises(Exception, match="group_name is missing"):
                    mod.upgrade()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_upgrade_rejects_group_id_without_unique_or_primary_key() -> None:
    mod = _migration_module()

    with _ephemeral_database() as (test_url, test_engine):
        cfg = _alembic_config(database_url=test_url)
        with _database_url_override(test_url):
            command.upgrade(cfg, PREVIOUS_REVISION)

        with test_engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE public.deps_group (
                        group_id BIGINT NOT NULL,
                        group_name TEXT NOT NULL
                    )
                    """
                )
            )

        with test_engine.connect() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                with pytest.raises(Exception, match="UNIQUE constraint/index on group_id alone"):
                    mod.upgrade()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_upgrade_adds_org_units_fk_when_same_name_exists_on_other_table() -> None:
    mod = _migration_module()

    with _ephemeral_database() as (test_url, test_engine):
        cfg = _alembic_config(database_url=test_url)
        with _database_url_override(test_url):
            command.upgrade(cfg, PREVIOUS_REVISION)

        with test_engine.begin() as conn:
            conn.execute(text("CREATE SCHEMA decoy_dgf"))
            conn.execute(
                text(
                    """
                    CREATE TABLE decoy_dgf.other_units (
                        unit_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                        group_id BIGINT NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    ALTER TABLE decoy_dgf.other_units
                        ADD CONSTRAINT fk_org_units_group
                            CHECK (group_id > 0)
                    """
                )
            )

        with test_engine.connect() as conn:
            assert _decoy_fk_exists(conn)
            assert not _org_units_fk_exists(conn)

            with Operations.context(MigrationContext.configure(conn)):
                mod.upgrade()
            conn.commit()

            assert _decoy_fk_exists(conn)
            assert _org_units_fk_exists(conn)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_downgrade_drops_fk_only_and_preserves_table() -> None:
    mod = _migration_module()

    with _ephemeral_database() as (test_url, test_engine):
        cfg = _alembic_config(database_url=test_url)
        with _database_url_override(test_url):
            command.upgrade(cfg, PREVIOUS_REVISION)

        with test_engine.connect() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                mod.upgrade()
            conn.commit()

            assert table_exists(conn, "deps_group")
            assert _org_units_fk_exists(conn)

            with Operations.context(MigrationContext.configure(conn)):
                mod.downgrade()
            conn.commit()

            assert table_exists(conn, "deps_group")
            assert not _org_units_fk_exists(conn)
            assert len(_canonical_group_rows(conn)) == 3
