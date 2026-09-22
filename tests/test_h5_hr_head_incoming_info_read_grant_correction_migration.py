"""Isolated PostgreSQL tests for historical revision h5c6d7e8f9a0."""
from __future__ import annotations

import runpy
from pathlib import Path

import pytest
from sqlalchemy import text

from app.db.engine import engine


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_FILE = "h5c6d7e8f9a0_hr_head_incoming_info_read_grant_correction.py"
REASON = "h5c6d7e8f9a0: HR_HEAD Incoming Information read grant correction"


def _migration() -> dict:
    return runpy.run_path(str(ROOT / "alembic" / "versions" / MIGRATION_FILE))


def _requires_g4_schema(conn) -> None:
    required = (
        "roles",
        "users",
        "access_roles",
        "access_grants",
    )
    available = set(conn.execute(text("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema='public'
    """)).scalars())
    if not set(required).issubset(available):
        current_database = conn.execute(text("SELECT current_database()")).scalar_one()
        missing = sorted(set(required) - available)
        pytest.skip(
            f"h5 migration prerequisite schema missing in {current_database}: {missing}; "
            "upgrade test DB to g4b5c6d7e8f9"
        )
    permission = conn.execute(text("""
        SELECT access_role_id FROM public.access_roles
        WHERE code='INCOMING_INFO_READ' AND is_active IS TRUE
    """)).scalar_one_or_none()
    if permission is None:
        pytest.skip("INCOMING_INFO_READ prerequisite missing — upgrade test DB to g4b5c6d7e8f9")


@pytest.fixture
def h5_connection(monkeypatch):
    migration = _migration()
    with engine.connect() as conn:
        _requires_g4_schema(conn)
        conn.rollback()
        transaction = conn.begin()
        monkeypatch.setattr(migration["op"], "execute", lambda statement: conn.execute(text(statement)))
        try:
            yield conn, migration
        finally:
            transaction.rollback()


def _insert_hr_head(conn) -> int:
    return int(conn.execute(text("""
        INSERT INTO public.roles (name, code)
        VALUES ('H5 synthetic HR head', 'HR_HEAD')
        RETURNING role_id
    """)).scalar_one())


def _insert_active_grantor(conn) -> int:
    role_id = int(conn.execute(text("""
        INSERT INTO public.roles (name, code)
        VALUES ('H5 synthetic grantor role', 'H5_TEST_GRANTOR')
        RETURNING role_id
    """)).scalar_one())
    return int(conn.execute(text("""
        INSERT INTO public.users (full_name, role_id, login, is_active)
        VALUES ('H5 synthetic grantor', :role_id, 'h5.synthetic.grantor', TRUE)
        RETURNING user_id
    """), {"role_id": role_id}).scalar_one())


def _correction_count(conn) -> int:
    return int(conn.execute(text("""
        SELECT COUNT(*) FROM public.access_grants WHERE reason=:reason
    """), {"reason": REASON}).scalar_one())


def test_h5_clean_schema_without_hr_head_or_users_skips(h5_connection):
    conn, migration = h5_connection
    assert conn.execute(text("SELECT COUNT(*) FROM public.roles WHERE code='HR_HEAD'")).scalar_one() == 0
    assert conn.execute(text("SELECT COUNT(*) FROM public.users")).scalar_one() == 0
    migration["upgrade"]()
    assert _correction_count(conn) == 0
    migration["downgrade"]()
    assert _correction_count(conn) == 0


def test_h5_hr_head_without_active_user_skips(h5_connection):
    conn, migration = h5_connection
    _insert_hr_head(conn)
    migration["upgrade"]()
    assert _correction_count(conn) == 0
    migration["downgrade"]()
    assert _correction_count(conn) == 0


def test_h5_correction_applies_once_and_downgrades(h5_connection):
    conn, migration = h5_connection
    hr_head_id = _insert_hr_head(conn)
    grantor_id = _insert_active_grantor(conn)
    migration["upgrade"]()
    migration["upgrade"]()
    rows = conn.execute(text("""
        SELECT target_id, granted_by_user_id
        FROM public.access_grants WHERE reason=:reason
    """), {"reason": REASON}).mappings().all()
    assert [dict(row) for row in rows] == [{"target_id": hr_head_id, "granted_by_user_id": grantor_id}]
    migration["downgrade"]()
    assert _correction_count(conn) == 0
