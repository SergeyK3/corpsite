# tests/test_adr042_phase_c1_2_sysadmin_ux.py
"""Tests for ADR-042 Phase C1.2 bulk admin endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers, table_exists

PHASE_B2_TABLES = ("access_roles", "person_assignments", "employees", "enrollment_queue")


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


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_bulk_reconcile_dry_run(client: TestClient, seed, admin_headers):
    _require_b2()
    resp = client.post(
        "/admin/assignments/reconcile/bulk",
        headers=admin_headers,
        json={"employee_ids": [], "all_drift": True, "dry_run": True, "limit": 10},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["dry_run"] is True
    assert "processed" in body
    assert "results" in body


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_enrollment_explain_not_found(client: TestClient, seed, admin_headers):
    _require_b2()
    resp = client.get("/admin/enrollment/queue/999999999/explain", headers=admin_headers)
    assert resp.status_code == 400


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_security_audit_includes_actor_label(client: TestClient, seed, admin_headers):
    _require_b2()
    resp = client.get("/admin/security-audit", headers=admin_headers, params={"limit": 5})
    assert resp.status_code == 200
    body = resp.json()
    if body["items"]:
        item = body["items"][0]
        assert "actor_user_id" in item
        assert "actor_label" in item or item.get("actor_user_id") is None
