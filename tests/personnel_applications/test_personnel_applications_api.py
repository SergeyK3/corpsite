# tests/personnel_applications/test_personnel_applications_api.py
"""API integration tests for Personnel Application endpoints."""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.personnel_applications.domain.status import VACANCY_CHECK_CONFIRMED_VISUALLY
from tests.conftest import auth_headers, table_exists
from tests.personnel_applications.conftest import insert_person_with_iin, materialize_envelope
from tests.ppr.conftest import cleanup_person_graph, ppr_db_available


def _unique_iin() -> str:
    return f"8{uuid4().int % 10_000_000_000_000:011d}"[:12]


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def schema_ready():
    if not ppr_db_available():
        pytest.skip("PostgreSQL not available")
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_applications"):
            pytest.skip("personnel_applications missing — run: alembic upgrade head")


def test_directory_routes_registered(client, schema_ready) -> None:
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/directory/personnel-applications/preview" in paths
    assert "/directory/personnel-applications" in paths
    assert "/directory/personnel-applications/{application_id}" in paths
    assert "/api/ppr/persons/{person_id}/applications" in paths


def test_register_and_get_application(client, schema_ready, privileged_headers, seed) -> None:
    iin = _unique_iin()
    person_ids: list[int] = []
    payload = {
        "iin": iin,
        "full_name": "API Register Test",
        "application_received_at": "2026-07-17",
        "vacancy_check_status": VACANCY_CHECK_CONFIRMED_VISUALLY,
        "idempotency_key": f"api-{uuid4().hex}",
    }
    reg = client.post(
        "/directory/personnel-applications",
        json=payload,
        headers=privileged_headers,
    )
    assert reg.status_code == 200, reg.text
    body = reg.json()
    assert body["action"] == "created"
    assert body["card_href"] == f"/directory/personnel/persons/{body['person_id']}/card"
    person_ids.append(body["person_id"])

    detail = client.get(
        f"/directory/personnel-applications/{body['application_id']}",
        headers=privileged_headers,
    )
    assert detail.status_code == 200
    assert detail.json()["status"] == "registered"

    history = client.get(
        f"/api/ppr/persons/{body['person_id']}/applications",
        headers=privileged_headers,
    )
    assert history.status_code == 200
    assert len(history.json()["items"]) >= 1

    preview = client.post(
        "/directory/personnel-applications/preview",
        json={"iin": iin},
        headers=privileged_headers,
    )
    assert preview.status_code == 200
    assert preview.json()["has_active_application"] is True

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_preview_new_person(client, schema_ready, privileged_headers) -> None:
    iin = _unique_iin()
    resp = client.post(
        "/directory/personnel-applications/preview",
        json={"iin": iin},
        headers=privileged_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["person_exists"] is False
    assert data["can_register"] is True


def test_register_requires_personnel_admin(client, schema_ready, seed) -> None:
    headers = auth_headers(seed["executor_user_id"])
    resp = client.post(
        "/directory/personnel-applications/preview",
        json={"iin": _unique_iin()},
        headers=headers,
    )
    assert resp.status_code == 403
