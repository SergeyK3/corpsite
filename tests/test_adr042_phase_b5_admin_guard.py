# tests/test_adr042_phase_b5_admin_guard.py
"""Tests for ADR-042 Phase B5 admin guard modes."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.security.admin_guard import admin_guard_mode, evaluate_admin_access
from app.services.access_grant_service import grant_access
from tests.conftest import auth_headers, get_columns, insert_returning_id, table_exists

PHASE_B2_TABLES = (
    "access_roles",
    "access_grants",
    "security_audit_log",
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_b2() -> None:
    with engine.begin() as conn:
        for table in PHASE_B2_TABLES:
            if not table_exists(conn, table):
                pytest.skip(f"ADR-042 B2 table missing: {table}")


@pytest.fixture
def admin_headers(seed, monkeypatch):
    monkeypatch.delenv("ADR042_ADMIN_GUARD_MODE", raising=False)
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def non_admin_headers(seed, monkeypatch):
    monkeypatch.delenv("ADR042_ADMIN_GUARD_MODE", raising=False)
    monkeypatch.delenv("DIRECTORY_PRIVILEGED_USER_IDS", raising=False)
    monkeypatch.delenv("DIRECTORY_PRIVILEGED_IDS", raising=False)
    return auth_headers(seed["executor_user_id"])


def _get_access_role_id(conn, code: str) -> int:
    row = conn.execute(
        text("SELECT access_role_id FROM public.access_roles WHERE code = :code LIMIT 1"),
        {"code": code},
    ).scalar_one()
    return int(row)


def _grant_sysadmin_cabinet(grantor_user_id: int, target_user_id: int) -> int:
    with engine.begin() as conn:
        role_id = _get_access_role_id(conn, "SYSADMIN_CABINET")
    result = grant_access(
        access_role_id=role_id,
        target_type="USER",
        target_id=int(target_user_id),
        granted_by_user_id=int(grantor_user_id),
        reason="b5 test grant",
    )
    return int(result["grant_id"])


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_default_guard_mode_is_legacy(monkeypatch):
    monkeypatch.delenv("ADR042_ADMIN_GUARD_MODE", raising=False)
    assert admin_guard_mode() == "legacy"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_legacy_admin_can_call_admin_api(client: TestClient, seed, admin_headers):
    _require_b2()
    resp = client.get("/admin/users", headers=admin_headers, params={"limit": 5})
    assert resp.status_code == 200


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_shadow_mode_does_not_deny_legacy_admin(client: TestClient, seed, admin_headers, monkeypatch):
    _require_b2()
    monkeypatch.setenv("ADR042_ADMIN_GUARD_MODE", "access_grants_shadow")
    resp = client.get("/admin/users", headers=admin_headers, params={"limit": 5})
    assert resp.status_code == 200


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_enforced_mode_allows_emergency_fallback(client: TestClient, seed, admin_headers, monkeypatch):
    _require_b2()
    monkeypatch.setenv("ADR042_ADMIN_GUARD_MODE", "access_grants_enforced")
    resp = client.get("/admin/users", headers=admin_headers, params={"limit": 5})
    assert resp.status_code == 200


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_enforced_mode_allows_sysadmin_cabinet_grant(client: TestClient, seed, monkeypatch):
    _require_b2()
    monkeypatch.setenv("ADR042_ADMIN_GUARD_MODE", "access_grants_enforced")
    monkeypatch.delenv("DIRECTORY_PRIVILEGED_USER_IDS", raising=False)
    monkeypatch.delenv("DIRECTORY_PRIVILEGED_IDS", raising=False)

    grant_id = None
    try:
        grant_id = _grant_sysadmin_cabinet(
            grantor_user_id=int(seed["initiator_user_id"]),
            target_user_id=int(seed["executor_user_id"]),
        )
        headers = auth_headers(seed["executor_user_id"])
        resp = client.get("/admin/users", headers=headers, params={"limit": 5})
        assert resp.status_code == 200
    finally:
        if grant_id is not None:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM public.security_audit_log WHERE metadata->>'grant_id' = :gid"),
                    {"gid": str(grant_id)},
                )
                conn.execute(
                    text("DELETE FROM public.access_grants WHERE grant_id = :gid"),
                    {"gid": grant_id},
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_enforced_mode_denies_non_admin_without_grant(client: TestClient, seed, non_admin_headers, monkeypatch):
    _require_b2()
    monkeypatch.setenv("ADR042_ADMIN_GUARD_MODE", "access_grants_enforced")
    resp = client.get("/admin/users", headers=non_admin_headers, params={"limit": 5})
    assert resp.status_code == 403


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_evaluate_admin_access_break_glass_user(seed, monkeypatch):
    _require_b2()
    monkeypatch.setenv("ADR042_ADMIN_GUARD_MODE", "legacy")
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT user_id, role_id
                FROM public.users
                WHERE user_id = :uid
                """
            ),
            {"uid": int(seed["initiator_user_id"])},
        ).mappings().first()
    user_ctx = {"user_id": int(row["user_id"]), "role_id": row["role_id"]}
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    assert evaluate_admin_access(user_ctx) is True
