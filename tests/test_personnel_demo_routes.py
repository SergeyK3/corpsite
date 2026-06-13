# tests/test_personnel_demo_routes.py
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers, table_exists


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


def test_list_personnel_events_privileged(client, seed, privileged_headers):
    with engine.begin() as conn:
        if not table_exists(conn, "employee_events"):
            pytest.skip("employee_events table not available")

    resp = client.get("/directory/personnel-events", headers=privileged_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert isinstance(body["items"], list)


def test_list_personnel_events_unprivileged_returns_403(client, seed):
    resp = client.get(
        "/directory/personnel-events",
        headers=auth_headers(seed["executor_user_id"]),
    )
    assert resp.status_code == 403


def test_list_professional_documents_privileged(client, seed, privileged_headers):
    with engine.begin() as conn:
        if not table_exists(conn, "certificate_types") or not table_exists(conn, "employee_certificates"):
            pytest.skip("professional documents tables not available")

    resp = client.get("/directory/professional-documents", headers=privileged_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body.get("items"), list)
    if body["items"]:
        row = body["items"][0]
        assert "employee_name" in row
        assert "status" in row
