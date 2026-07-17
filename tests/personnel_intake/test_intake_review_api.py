# tests/personnel_intake/test_intake_review_api.py
"""API integration tests for Personnel Intake review + transfer (WP-PPR-INTAKE-002)."""
from __future__ import annotations

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.personnel_applications.domain.status import (
    APPLICATION_STATUS_REVIEW_COMPLETED,
    APPLICATION_STATUS_UNDER_REVIEW,
    VACANCY_CHECK_CONFIRMED_VISUALLY,
)
from app.personnel_intake.domain.models import empty_intake_draft_payload
from app.personnel_intake.domain.review_status import INTAKE_REVIEW_SECTIONS
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
def intake_review_schema_ready():
    if not ppr_db_available():
        pytest.skip("PostgreSQL not available")
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_intake_section_reviews"):
            pytest.skip("personnel_intake_section_reviews missing — run: alembic upgrade head")


def _register_application(client, headers, *, iin: str | None = None) -> dict:
    iin = iin or _unique_iin()
    payload = {
        "iin": iin,
        "full_name": "Review Test Applicant",
        "application_received_at": "2026-07-17",
        "vacancy_check_status": VACANCY_CHECK_CONFIRMED_VISUALLY,
        "idempotency_key": f"intake-review-{uuid4().hex}",
    }
    reg = client.post("/directory/personnel-applications", json=payload, headers=headers)
    assert reg.status_code == 200, reg.text
    return reg.json()


def _filled_payload() -> dict:
    payload = empty_intake_draft_payload()
    payload["personal"]["last_name"] = "Иванов"
    payload["personal"]["first_name"] = "Иван"
    payload["personal"]["birth_date"] = "1990-05-15"
    payload["contacts"]["mobile_phone"] = "+77001234567"
    payload["contacts"]["email"] = "ivan@example.com"
    payload["education"] = [
        {
            "institution": "КазНУ",
            "year_from": "2018",
            "year_to": "2022",
            "specialty": "IT",
            "qualification": "Бакалавр",
            "diploma_number": "123",
        }
    ]
    return payload


def _submit_intake(client, headers) -> tuple[dict, dict]:
    reg = _register_application(client, headers)
    app_id = reg["application_id"]
    issue = client.post(
        f"/directory/personnel-applications/{app_id}/intake-link",
        headers=headers,
    )
    assert issue.status_code == 200, issue.text
    token = issue.json()["intake_url_path"].split("/intake/")[-1]
    payload = _filled_payload()
    client.patch(f"/intake/{token}", json={"payload": payload})
    submit = client.post(f"/intake/{token}/submit", json={"payload": payload})
    assert submit.status_code == 200, submit.text
    return reg, payload


def _accept_required_and_skip_optional(client, headers, app_id: int) -> None:
    for section in ("personal", "contacts", "education"):
        res = client.post(
            f"/directory/personnel-applications/{app_id}/intake/review/sections/{section}/accept",
            headers=headers,
        )
        assert res.status_code == 200, res.text
    for section in ("training", "relatives", "employment_biography", "military"):
        res = client.post(
            f"/directory/personnel-applications/{app_id}/intake/review/sections/{section}/skip",
            headers=headers,
        )
        assert res.status_code == 200, res.text


def test_review_routes_registered(client, intake_review_schema_ready) -> None:
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/directory/personnel-applications/{application_id}/intake/review" in paths
    assert "/directory/personnel-applications/{application_id}/intake/transfer" in paths
    assert "/directory/personnel-applications/intake/transfers" in paths


def test_review_workflow_load_accept_rework_skip(
    client, intake_review_schema_ready, privileged_headers
) -> None:
    person_ids: list[int] = []
    try:
        reg, _payload = _submit_intake(client, privileged_headers)
        person_ids.append(reg["person_id"])
        app_id = reg["application_id"]

        review = client.get(
            f"/directory/personnel-applications/{app_id}/intake/review",
            headers=privileged_headers,
        )
        assert review.status_code == 200, review.text
        body = review.json()
        assert body["application_id"] == app_id
        assert len(body["sections"]) == len(INTAKE_REVIEW_SECTIONS)
        assert body["can_transfer"] is False

        detail = client.get(f"/directory/personnel-applications/{app_id}", headers=privileged_headers)
        assert detail.json()["status"] == APPLICATION_STATUS_UNDER_REVIEW

        accept_personal = client.post(
            f"/directory/personnel-applications/{app_id}/intake/review/sections/personal/accept",
            headers=privileged_headers,
        )
        assert accept_personal.status_code == 200
        personal = next(s for s in accept_personal.json()["sections"] if s["section_code"] == "personal")
        assert personal["status"] == "accepted"

        rework = client.post(
            f"/directory/personnel-applications/{app_id}/intake/review/sections/contacts/rework",
            json={"comment": "Уточните email"},
            headers=privileged_headers,
        )
        assert rework.status_code == 200
        contacts = next(s for s in rework.json()["sections"] if s["section_code"] == "contacts")
        assert contacts["status"] == "rework_requested"
        assert contacts["rework_comment"] == "Уточните email"
        assert rework.json()["can_transfer"] is False

        skip_training = client.post(
            f"/directory/personnel-applications/{app_id}/intake/review/sections/training/skip",
            headers=privileged_headers,
        )
        assert skip_training.status_code == 200

        accept_contacts = client.post(
            f"/directory/personnel-applications/{app_id}/intake/review/sections/contacts/accept",
            headers=privileged_headers,
        )
        assert accept_contacts.status_code == 200

        skip_education_fail = client.post(
            f"/directory/personnel-applications/{app_id}/intake/review/sections/education/skip",
            headers=privileged_headers,
        )
        assert skip_education_fail.status_code == 422
        assert skip_education_fail.json()["detail"]["code"] == "SECTION_NOT_EMPTY"
    finally:
        if person_ids:
            with engine.begin() as conn:
                cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_transfer_success_idempotent_audit_and_draft_immutable(
    client, intake_review_schema_ready, privileged_headers
) -> None:
    person_ids: list[int] = []
    reg, payload = _submit_intake(client, privileged_headers)
    person_ids.append(reg["person_id"])
    app_id = reg["application_id"]
    person_id = reg["person_id"]

    _accept_required_and_skip_optional(client, privileged_headers, app_id)

    ready = client.get(
        f"/directory/personnel-applications/{app_id}/intake/review",
        headers=privileged_headers,
    )
    assert ready.json()["can_transfer"] is True

    transfer = client.post(
        f"/directory/personnel-applications/{app_id}/intake/transfer",
        headers=privileged_headers,
    )
    assert transfer.status_code == 200, transfer.text
    transfer_body = transfer.json()
    assert transfer_body["idempotent_replay"] is False
    assert transfer_body["transfer"]["status"] == "completed"
    assert "general" in transfer_body["transfer"]["sections_transferred"]
    assert "education" in transfer_body["transfer"]["sections_transferred"]
    assert transfer_body["transfer"]["transferred_by_user_id"] is not None
    assert transfer_body["transfer"]["transferred_at"] is not None

    detail = client.get(f"/directory/personnel-applications/{app_id}", headers=privileged_headers)
    assert detail.json()["status"] == APPLICATION_STATUS_REVIEW_COMPLETED

    replay = client.post(
        f"/directory/personnel-applications/{app_id}/intake/transfer",
        headers=privileged_headers,
    )
    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True

    accept_after = client.post(
        f"/directory/personnel-applications/{app_id}/intake/review/sections/personal/accept",
        headers=privileged_headers,
    )
    assert accept_after.status_code == 422
    assert accept_after.json()["detail"]["code"] == "REVIEW_ALREADY_COMPLETED"

    audit = client.get(
        "/directory/personnel-applications/intake/transfers",
        headers=privileged_headers,
    )
    assert audit.status_code == 200
    items = audit.json()["items"]
    assert any(item["application_id"] == app_id and item["status"] == "completed" for item in items)

    with engine.begin() as conn:
        draft_row = conn.execute(
            text(
                """
                SELECT payload::text
                FROM public.personnel_intake_drafts
                WHERE application_id = :app_id
                """
            ),
            {"app_id": app_id},
        ).scalar_one()
        assert json.loads(draft_row)["personal"]["last_name"] == payload["personal"]["last_name"]

        person_name = conn.execute(
            text("SELECT full_name FROM public.persons WHERE person_id = :pid"),
            {"pid": person_id},
        ).scalar_one()
        assert "Иванов" in person_name

        exec_count = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.ppr_command_executions
                WHERE person_id = :pid AND command_id LIKE :prefix
                """
            ),
            {"pid": person_id, "prefix": f"intake-transfer:{app_id}:%"},
        ).scalar_one()
        assert exec_count >= 1

        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_transfer_blocked_until_all_sections_finalized(
    client, intake_review_schema_ready, privileged_headers
) -> None:
    person_ids: list[int] = []
    reg, _ = _submit_intake(client, privileged_headers)
    person_ids.append(reg["person_id"])
    app_id = reg["application_id"]

    blocked = client.post(
        f"/directory/personnel-applications/{app_id}/intake/transfer",
        headers=privileged_headers,
    )
    assert blocked.status_code == 422
    assert blocked.json()["detail"]["code"] == "TRANSFER_NOT_ALLOWED"

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_review_not_available_before_submit(client, intake_review_schema_ready, privileged_headers) -> None:
    person_ids: list[int] = []
    reg = _register_application(client, privileged_headers)
    person_ids.append(reg["person_id"])
    app_id = reg["application_id"]

    res = client.get(
        f"/directory/personnel-applications/{app_id}/intake/review",
        headers=privileged_headers,
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "REVIEW_NOT_AVAILABLE"

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_rework_requires_comment(client, intake_review_schema_ready, privileged_headers) -> None:
    person_ids: list[int] = []
    reg, _ = _submit_intake(client, privileged_headers)
    person_ids.append(reg["person_id"])
    app_id = reg["application_id"]

    res = client.post(
        f"/directory/personnel-applications/{app_id}/intake/review/sections/personal/rework",
        json={"comment": "   "},
        headers=privileged_headers,
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "REWORK_COMMENT_REQUIRED"

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])
