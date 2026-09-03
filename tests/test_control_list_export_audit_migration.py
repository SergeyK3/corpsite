from __future__ import annotations

from contextlib import contextmanager
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text

from app.db.engine import engine

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT
    / "alembic"
    / "versions"
    / "x7y8z9a0b1c2_wp_cl_003_control_list_export_audit.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("wp_cl_003_audit", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@contextmanager
def _ephemeral_database():
    database_name = f"corpsite_wpcl003_migration_{uuid4().hex[:10]}_test"
    admin_url = (
        str(engine.url.render_as_string(hide_password=False)).rsplit("/", 1)[0]
        + "/postgres"
    )
    database_url = admin_url.rsplit("/", 1)[0] + f"/{database_name}"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    test_engine = create_engine(database_url)
    with admin_engine.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{database_name}"'))
    try:
        with test_engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE public.security_audit_log (
                        audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                        event_type TEXT NOT NULL,
                        CONSTRAINT chk_sal_event_type CHECK (event_type IN ('LOGIN_SUCCESS'))
                    )
                    """
                )
            )
        yield test_engine
    finally:
        test_engine.dispose()
        with admin_engine.connect() as conn:
            conn.execute(
                text(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname=:database_name AND pid <> pg_backend_pid()
                    """
                ),
                {"database_name": database_name},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
        admin_engine.dispose()


def _run(conn, operation: str) -> None:
    migration = _load_migration()
    with Operations.context(MigrationContext.configure(conn)):
        getattr(migration, operation)()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_real_postgresql_upgrade_and_clean_downgrade() -> None:
    with _ephemeral_database() as test_engine:
        with test_engine.begin() as conn:
            _run(conn, "upgrade")
            conn.execute(
                text("INSERT INTO security_audit_log(event_type) VALUES ('LOGIN_SUCCESS')")
            )
            conn.execute(
                text(
                    "INSERT INTO security_audit_log(event_type) "
                    "VALUES ('CONTROL_LIST_EXPORT')"
                )
            )
            conn.execute(
                text(
                    "DELETE FROM security_audit_log "
                    "WHERE event_type='CONTROL_LIST_EXPORT'"
                )
            )
            _run(conn, "downgrade")
            with pytest.raises(Exception):
                with conn.begin_nested():
                    conn.execute(
                        text(
                            "INSERT INTO security_audit_log(event_type) "
                            "VALUES ('CONTROL_LIST_EXPORT')"
                        )
                    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_real_postgresql_downgrade_preserves_audit_history_and_constraint() -> None:
    with _ephemeral_database() as test_engine:
        with test_engine.begin() as conn:
            _run(conn, "upgrade")
            conn.execute(
                text(
                    "INSERT INTO security_audit_log(event_type) "
                    "VALUES ('CONTROL_LIST_EXPORT')"
                )
            )

        with pytest.raises(RuntimeError, match="audit history must be preserved"):
            with test_engine.begin() as conn:
                _run(conn, "downgrade")

        with test_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO security_audit_log(event_type) "
                    "VALUES ('CONTROL_LIST_EXPORT')"
                )
            )
            assert conn.execute(
                text(
                    "SELECT count(*) FROM security_audit_log "
                    "WHERE event_type='CONTROL_LIST_EXPORT'"
                )
            ).scalar_one() == 2
