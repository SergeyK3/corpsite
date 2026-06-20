# tests/test_adr042_phase_c1_1_admin_reference.py
"""Tests for ADR-042 Phase C1.1 admin reference endpoints."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers, insert_returning_id, table_exists

PHASE_B2_TABLES = ("access_roles", "access_grants", "security_audit_log", "users", "persons")


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
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def non_admin_headers(seed):
    return auth_headers(seed["executor_user_id"])


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_roles_endpoint_returns_seeded_roles(client: TestClient, seed, admin_headers):
    _require_b2()
    resp = client.get("/admin/access/roles", headers=admin_headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    codes = {r["code"] for r in rows}
    assert "SYSADMIN_CABINET" in codes
    assert "ACCESS_MANAGER" in codes
    first = rows[0]
    assert "access_role_id" in first
    assert "label" in first
    assert "level_rank" in first


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_guard_mode_endpoint(client: TestClient, seed, admin_headers):
    _require_b2()
    resp = client.get("/admin/access/guard-mode", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["guard_mode"] in ("legacy", "access_grants_shadow", "access_grants_enforced")
    assert "message" in body


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_target_search_user(client: TestClient, seed, admin_headers):
    _require_b2()
    resp = client.get(
        "/admin/access/targets/search",
        headers=admin_headers,
        params={"target_type": "USER", "q": str(seed["initiator_user_id"]), "limit": 5},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["target_type"] == "USER"
    assert len(body["items"]) >= 1
    item = body["items"][0]
    assert item["target_type"] == "USER"
    assert "target_id" in item
    assert "label" in item


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_target_search_person(client: TestClient, seed, admin_headers):
    _require_b2()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_returning_id(
            conn,
            table="persons",
            id_col="person_id",
            values={
                "full_name": f"C11 Person {suffix}",
                "match_key": f"name:c11 {suffix}",
                "source": "manual",
                "person_status": "active",
            },
        )
    try:
        resp = client.get(
            "/admin/access/targets/search",
            headers=admin_headers,
            params={"target_type": "PERSON", "q": suffix, "limit": 5},
        )
        assert resp.status_code == 200
        ids = [i["target_id"] for i in resp.json()["items"]]
        assert person_id in ids
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM public.persons WHERE person_id = :pid"), {"pid": person_id})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_target_search_org_unit(client: TestClient, seed, admin_headers):
    _require_b2()
    resp = client.get(
        "/admin/access/targets/search",
        headers=admin_headers,
        params={"target_type": "ORG_UNIT", "q": "", "limit": 5},
    )
    assert resp.status_code == 200
    assert "items" in resp.json()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_non_admin_denied_reference_endpoints(client: TestClient, seed, non_admin_headers, monkeypatch):
    _require_b2()
    monkeypatch.setenv("ADR042_ADMIN_GUARD_MODE", "access_grants_enforced")
    for path in (
        "/admin/access/roles",
        "/admin/access/guard-mode",
        "/admin/access/targets/search?target_type=USER&q=1",
    ):
        resp = client.get(path, headers=non_admin_headers)
        assert resp.status_code == 403, path
