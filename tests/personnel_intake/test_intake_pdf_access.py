# tests/personnel_intake/test_intake_pdf_access.py
"""Access-control tests for intake PDF data sources (WP-PPR-INTAKE PDF)."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.personnel_applications.domain.status import VACANCY_CHECK_CONFIRMED_VISUALLY
from app.personnel_intake.domain.models import empty_intake_draft_payload
from tests.conftest import auth_headers, table_exists
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
def intake_schema_ready():
    if not ppr_db_available():
        pytest.skip("PostgreSQL not available")
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_intake_links"):
            pytest.skip("personnel_intake_links missing — run: alembic upgrade head")


def _register_application(client, headers, *, iin: str | None = None) -> dict:
    iin = iin or _unique_iin()
    payload = {
        "iin": iin,
        "full_name": "PDF Access Applicant",
        "application_received_at": "2026-07-17",
        "vacancy_check_status": VACANCY_CHECK_CONFIRMED_VISUALLY,
        "idempotency_key": f"intake-pdf-{uuid4().hex}",
    }
    reg = client.post("/directory/personnel-applications", json=payload, headers=headers)
    assert reg.status_code == 200, reg.text
    return reg.json()


def _filled_payload() -> dict:
    payload = empty_intake_draft_payload()
    payload["personal"]["last_name"] = "Петров"
    payload["personal"]["first_name"] = "Пётр"
    payload["contacts"]["mobile_phone"] = "+77001234567"
    return payload


def test_intake_pdf_data_routes_registered(client) -> None:
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/intake/{token}" in paths
    assert "/directory/personnel-applications/{application_id}/intake/draft" in paths


def test_invalid_intake_token_denied_for_pdf_data(client, intake_schema_ready, privileged_headers) -> None:
    person_ids: list[int] = []
    reg = _register_application(client, privileged_headers)
    person_ids.append(reg["person_id"])
    app_id = reg["application_id"]

    issue = client.post(
        f"/directory/personnel-applications/{app_id}/intake-link",
        headers=privileged_headers,
    )
    assert issue.status_code == 200, issue.text

    denied = client.get("/intake/not-a-valid-token-value")
    assert denied.status_code == 403

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_hr_intake_draft_requires_personnel_admin(
    client,
    intake_schema_ready,
    privileged_headers,
    seed,
) -> None:
    person_ids: list[int] = []
    reg = _register_application(client, privileged_headers)
    person_ids.append(reg["person_id"])
    app_id = reg["application_id"]

    issue = client.post(
        f"/directory/personnel-applications/{app_id}/intake-link",
        headers=privileged_headers,
    )
    token = issue.json()["intake_url_path"].split("/intake/")[-1]
    client.get(f"/intake/{token}")
    client.patch(f"/intake/{token}", json={"payload": _filled_payload()})

    denied = client.get(
        f"/directory/personnel-applications/{app_id}/intake/draft",
        headers=auth_headers(seed["executor_user_id"]),
    )
    assert denied.status_code == 403

    allowed = client.get(
        f"/directory/personnel-applications/{app_id}/intake/draft",
        headers=privileged_headers,
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["payload"]["personal"]["last_name"] == "Петров"

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_hr_intake_draft_not_found_for_foreign_application(
    client,
    intake_schema_ready,
    privileged_headers,
) -> None:
    person_ids: list[int] = []
    first = _register_application(client, privileged_headers)
    person_ids.append(first["person_id"])
    second = _register_application(client, privileged_headers)
    person_ids.append(second["person_id"])

    missing = client.get(
        f"/directory/personnel-applications/{second['application_id'] + 999_999}/intake/draft",
        headers=privileged_headers,
    )
    assert missing.status_code == 404

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])
