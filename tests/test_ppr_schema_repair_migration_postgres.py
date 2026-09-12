"""PostgreSQL contracts for the stamped PPR-prefix repair migration."""
from __future__ import annotations

from contextlib import contextmanager
from importlib.util import module_from_spec, spec_from_file_location
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from app.db.engine import engine


PRODUCTION_REVISION = "iq2a1b2c3d4"
HEAD = "ppr005iadd01"
REPAIR_TABLES = (
    "ppr_stage0_cohort_runs",
    "ppr_stage0_cohort_participants",
    "ppr_stage0_cohort_blockers",
    "ppr_stage1_general_runs",
    "ppr_stage1_general_participants",
    "ppr_stage_runs",
    "ppr_stage_run_participants",
    "ppr_migration_status_universes",
    "ppr_migration_status_universe_cohorts",
    "ppr_migration_section_status_projection",
)


def _repair_module():
    spec = spec_from_file_location(
        "ppr005drepair01",
        Path("alembic/versions/ppr005drepair01_restore_missing_ppr_schema.py"),
    )
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _apply_repair(conn) -> None:
    with Operations.context(MigrationContext.configure(conn)):
        _repair_module().upgrade()


def _exists(conn) -> set[str]:
    return set(
        conn.execute(
            text(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                "AND tablename = ANY(:names)"
            ),
            {"names": list(REPAIR_TABLES)},
        ).scalars()
    )


def _test_url() -> str:
    parsed = make_url(os.environ["TEST_DATABASE_URL"])
    if parsed.host not in {"127.0.0.1", "localhost", "::1"} or parsed.database != "corpsite_test":
        raise RuntimeError("PPR repair tests require loopback corpsite_test")
    return parsed.render_as_string(hide_password=False)


@contextmanager
def _clone_iq2_database():
    source = make_url(_test_url())
    name = f"corpsite_ppr_repair_{uuid4().hex[:16]}_test"
    target = source.set(database=name)
    admin_engine = create_engine(source.set(database="postgres"), isolation_level="AUTOCOMMIT")
    target_engine = create_engine(target)
    engine.dispose()
    try:
        with admin_engine.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{name}" TEMPLATE "{source.database}"'))
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", target.render_as_string(hide_password=False).replace("%", "%%"))
        yield target_engine, cfg
    finally:
        target_engine.dispose()
        with admin_engine.connect() as conn:
            conn.execute(
                text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:name AND pid <> pg_backend_pid()"),
                {"name": name},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        admin_engine.dispose()


def test_production_iq2_full_prefix_upgrades_without_recreating_ppr_schema() -> None:
    """The production-shaped IQ-2 revision executes only the new child revision."""
    with _clone_iq2_database() as (target_engine, cfg):
        with target_engine.connect() as conn:
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == PRODUCTION_REVISION
            assert _exists(conn) == set(REPAIR_TABLES)
        command.upgrade(cfg, "head")
        with target_engine.connect() as conn:
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == HEAD
            assert _exists(conn) == set(REPAIR_TABLES)
            assert conn.execute(text("SELECT to_regclass('public.person_status_facts')")).scalar_one() == "person_status_facts"


def test_repair_accepts_full_prefix_restores_absent_prefix_and_rejects_partial_prefix() -> None:
    """Repair is idempotent for full schema, restorative for none and fail-closed for partial."""
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            assert _exists(conn) == set(REPAIR_TABLES)
            _apply_repair(conn)
            assert _exists(conn) == set(REPAIR_TABLES)

            for table_name in reversed(REPAIR_TABLES):
                conn.execute(text(f"DROP TABLE IF EXISTS public.{table_name} CASCADE"))
            assert not _exists(conn)
            _apply_repair(conn)
            assert _exists(conn) == set(REPAIR_TABLES)

            conn.execute(text("DROP TABLE public.ppr_migration_status_universes CASCADE"))
            with pytest.raises(DBAPIError, match="partially present") as exc_info:
                _apply_repair(conn)
            assert getattr(exc_info.value.orig, "pgcode", None) == "P0001"
        finally:
            transaction.rollback()
            engine.dispose()
