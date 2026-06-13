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


def _professional_documents_tables_available() -> bool:
    with engine.begin() as conn:
        return table_exists(conn, "certificate_types") and table_exists(
            conn, "employee_certificates"
        )


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


def test_professional_documents_availability(client, seed):
    expected = _professional_documents_tables_available()
    resp = client.get(
        "/directory/professional-documents/availability",
        headers=auth_headers(seed["initiator_user_id"]),
    )
    assert resp.status_code == 200
    assert resp.json() == {"available": expected}


def test_list_professional_documents_graceful_without_tables(client, seed, privileged_headers):
    resp = client.get("/directory/professional-documents", headers=privileged_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("available") is _professional_documents_tables_available()
    assert isinstance(body.get("items"), list)
    assert body.get("total") == len(body["items"])
    if not body["available"]:
        assert body["items"] == []
        assert body["total"] == 0


def test_list_professional_documents_with_tables_returns_rows(client, seed, privileged_headers):
    if not _professional_documents_tables_available():
        pytest.skip("professional documents tables not available")

    resp = client.get("/directory/professional-documents", headers=privileged_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("available") is True
    if body["items"]:
        row = body["items"][0]
        assert "employee_name" in row
        assert "status" in row
