"""OPS-009.18c — unit/integration tests for admin unlock ops script."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine

ROOT = Path(__file__).resolve().parents[1]
_SCRIPT_PATH = ROOT / "scripts" / "ops" / "ops_009_18c_admin_unlock.py"


def _load_ops_module():
    spec = importlib.util.spec_from_file_location("ops_009_18c_admin_unlock", _SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ops = _load_ops_module()


def test_build_unlock_update_sql_includes_required_fields():
    sql = ops.build_unlock_update_sql(
        {"locked_until", "failed_login_count", "token_version", "locked_at", "locked_reason"}
    )
    assert "locked_at = NULL" in sql
    assert "locked_until = NULL" in sql
    assert "locked_reason = NULL" in sql
    assert "failed_login_count = 0" in sql
    assert "token_version = COALESCE(token_version, 1) + 1" in sql
    assert "password_hash" not in sql
    assert "role_id" not in sql


def test_user_verify_view_exposes_required_fields():
    row = {
        "user_id": 25,
        "login": "admin",
        "role_id": 2,
        "role_code": "ADMIN",
        "is_active": True,
        "failed_login_count": 5,
        "locked_at": "2026-06-22T10:00:00+00:00",
        "locked_until": None,
        "locked_reason": "brute_force",
        "token_version": 3,
        "must_change_password": False,
        "password_hash": "secret",
    }
    view = ops.user_verify_view(row)
    assert view is not None
    assert view["login"] == "admin"
    assert view["role_id"] == 2
    assert view["is_active"] is True
    assert view["failed_login_count"] == 5
    assert view["token_version"] == 3
    assert view["must_change_password"] is False
    assert "password_hash" not in view


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _adr042_lock_columns(conn) -> bool:
    cols = {
        r[0]
        for r in conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'users'
                """
            )
        ).fetchall()
    }
    needed = {"locked_at", "failed_login_count", "token_version"}
    return needed.issubset(cols)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_unlock_user_tx_resets_only_lock_fields(seed):
    with engine.connect() as conn:
        if not _adr042_lock_columns(conn):
            pytest.skip("ADR-042 lock columns not present")

    suffix = uuid4().hex[:8]
    login = f"ops018c_{suffix}@pytest.local"
    user_id = int(seed["executor_user_id"])

    with engine.connect() as conn:
        before = conn.execute(
            text(
                """
                SELECT login, role_id, unit_id, is_active, must_change_password, password_hash, token_version
                FROM public.users
                WHERE user_id = :uid
                """
            ),
            {"uid": user_id},
        ).mappings().one()
        original_login = before["login"]

    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE public.users SET login = :login WHERE user_id = :uid"),
                {"login": login, "uid": user_id},
            )
            conn.execute(
                text(
                    """
                    UPDATE public.users
                    SET locked_at = now(),
                        locked_reason = 'brute_force',
                        failed_login_count = 5
                    WHERE user_id = :uid
                    """
                ),
                {"uid": user_id},
            )

        with engine.begin() as conn:
            rows = ops.unlock_user_tx(conn, login=login, actor_user_id=1)
        assert rows == 1

        with engine.connect() as conn:
            after = conn.execute(
                text(
                    """
                    SELECT
                        login,
                        role_id,
                        unit_id,
                        is_active,
                        must_change_password,
                        password_hash,
                        token_version,
                        locked_at,
                        locked_reason,
                        failed_login_count
                    FROM public.users
                    WHERE user_id = :uid
                    """
                ),
                {"uid": user_id},
            ).mappings().one()

        assert after["locked_at"] is None
        assert after["locked_reason"] is None
        assert int(after["failed_login_count"]) == 0
        assert int(after["token_version"]) == int(before["token_version"]) + 1
        assert after["role_id"] == before["role_id"]
        assert after["unit_id"] == before["unit_id"]
        assert after["is_active"] == before["is_active"]
        assert after["must_change_password"] == before["must_change_password"]
        assert after["password_hash"] == before["password_hash"]
    finally:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE public.users
                    SET login = :login,
                        locked_at = NULL,
                        locked_reason = NULL,
                        failed_login_count = 0
                    WHERE user_id = :uid
                    """
                ),
                {"login": original_login, "uid": user_id},
            )
