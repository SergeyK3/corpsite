# tests/personnel_intake/test_on_behalf_edit_api.py
"""API integration tests for HR on-behalf intake draft editing."""
from __future__ import annotations

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.personnel_applications.domain.lifecycle_audit import LIFECYCLE_ACTION_INTAKE_EDITED_ON_BEHALF
from app.personnel_applications.domain.status import (
    APPLICATION_STATUS_INTAKE_PENDING,
    APPLICATION_STATUS_UNDER_REVIEW,
    VACANCY_CHECK_CONFIRMED_VISUALLY,
)
from app.personnel_intake.domain.models import empty_intake_draft_payload
from tests.conftest import auth_headers, table_exists
from tests.ppr.conftest import ppr_db_available


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
def intake_on_behalf_schema_ready():
    if not ppr_db_available():
        pytest.skip("PostgreSQL not available")
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_intake_section_reviews"):
            pytest.skip("personnel_intake_section_reviews missing — run: alembic upgrade head")
        if not table_exists(conn, "personnel_application_lifecycle_audit"):
            pytest.skip("personnel_application_lifecycle_audit missing — run: alembic upgrade head")


def _register_application(client, headers, *, iin: str | None = None) -> dict:
    iin = iin or _unique_iin()
    payload = {
        "iin": iin,
        "full_name": "On Behalf Applicant",
        "application_received_at": "2026-07-17",
        "vacancy_check_status": VACANCY_CHECK_CONFIRMED_VISUALLY,
        "idempotency_key": f"on-behalf-{uuid4().hex}",
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
            "education_type": "basic",
            "institution": "КазНУ",
            "year_from": "2018-09-01",
            "year_to": "2022-06-30",
            "specialty": "IT",
            "qualification": "Бакалавр",
            "diploma_number": "123",
        }
    ]
    payload["employment_biography"] = [
        {
            "organization": "Клиника А",
            "position": "Медсестра",
            "year_from": "2020-01-15",
            "year_to": "2024-08-01",
            "reason_for_leaving": "Переезд",
        }
    ]
    return payload


def _submit_intake(client, headers) -> tuple[int, dict]:
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
    return app_id, payload


def _start_editable_intake(client, headers) -> tuple[int, str, dict]:
    reg = _register_application(client, headers, iin=_unique_iin())
    app_id = reg["application_id"]
    issue = client.post(
        f"/directory/personnel-applications/{app_id}/intake-link",
        headers=headers,
    )
    assert issue.status_code == 200, issue.text
    token = issue.json()["intake_url_path"].split("/intake/")[-1]
    payload = empty_intake_draft_payload()
    payload["personal"]["last_name"] = "Петров"
    payload["personal"]["first_name"] = "Пётр"
    autosave = client.patch(f"/intake/{token}", json={"payload": payload})
    assert autosave.status_code == 200, autosave.text
    return app_id, token, payload


def _on_behalf_session(client, headers, app_id: int) -> dict:
    session = client.get(
        f"/directory/personnel-applications/{app_id}/intake/draft/on-behalf-edit",
        headers=headers,
    )
    assert session.status_code == 200, session.text
    return session.json()


def test_on_behalf_edit_session_allows_intake_pending_editable_draft(
    client,
    intake_on_behalf_schema_ready,
    privileged_headers,
) -> None:
    app_id, _, _ = _start_editable_intake(client, privileged_headers)
    body = _on_behalf_session(client, privileged_headers, app_id)
    assert body["editable"] is True
    assert body["reason_code"] is None
    assert body["draft"]["status"] == "editable"
    assert body["draft"]["updated_at"] is not None

    detail = client.get(f"/directory/personnel-applications/{app_id}", headers=privileged_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["status"] == APPLICATION_STATUS_INTAKE_PENDING


def test_on_behalf_edit_save_updates_shared_draft_during_intake_pending_without_submit(
    client,
    intake_on_behalf_schema_ready,
    privileged_headers,
    seed,
) -> None:
    app_id, token, payload = _start_editable_intake(client, privileged_headers)
    session = _on_behalf_session(client, privileged_headers, app_id)

    updated_payload = dict(payload)
    updated_payload["contacts"] = {**payload["contacts"], "mobile_phone": "+77009998877"}

    save = client.patch(
        f"/directory/personnel-applications/{app_id}/intake/draft/on-behalf",
        headers=privileged_headers,
        json={
            "payload": updated_payload,
            "expected_updated_at": session["draft"]["updated_at"],
        },
    )
    assert save.status_code == 200, save.text
    save_body = save.json()
    assert "contacts.mobile_phone" in save_body["changed_fields"]
    assert save_body["status"] == "editable"
    assert save_body["draft_updated_at"] is not None

    applicant_view = client.get(f"/intake/{token}")
    assert applicant_view.status_code == 200, applicant_view.text
    assert applicant_view.json()["payload"]["contacts"]["mobile_phone"] == "+77009998877"

    detail = client.get(f"/directory/personnel-applications/{app_id}", headers=privileged_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["status"] == APPLICATION_STATUS_INTAKE_PENDING

    with engine.connect() as conn:
        audit_row = conn.execute(
            text(
                """
                SELECT action, actor_user_id, previous_status, new_status, metadata
                FROM public.personnel_application_lifecycle_audit
                WHERE application_id = :application_id
                  AND action = :action
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {
                "application_id": app_id,
                "action": LIFECYCLE_ACTION_INTAKE_EDITED_ON_BEHALF,
            },
        ).mappings().one()
        metadata = audit_row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        assert audit_row["actor_user_id"] == seed["initiator_user_id"]
        assert audit_row["previous_status"] == APPLICATION_STATUS_INTAKE_PENDING
        assert audit_row["new_status"] == APPLICATION_STATUS_INTAKE_PENDING
        assert metadata["on_behalf_of"] == "applicant"
        assert "contacts.mobile_phone" in metadata["changed_fields"]


def test_on_behalf_edit_save_returns_version_conflict_on_stale_expected_updated_at(
    client,
    intake_on_behalf_schema_ready,
    privileged_headers,
) -> None:
    app_id, token, payload = _start_editable_intake(client, privileged_headers)
    session = _on_behalf_session(client, privileged_headers, app_id)
    stale_updated_at = session["draft"]["updated_at"]

    applicant_payload = dict(payload)
    applicant_payload["personal"]["middle_name"] = "Петрович"
    autosave = client.patch(f"/intake/{token}", json={"payload": applicant_payload})
    assert autosave.status_code == 200, autosave.text

    hr_payload = dict(applicant_payload)
    hr_payload["contacts"] = {**payload["contacts"], "email": "hr-help@example.com"}
    save = client.patch(
        f"/directory/personnel-applications/{app_id}/intake/draft/on-behalf",
        headers=privileged_headers,
        json={
            "payload": hr_payload,
            "expected_updated_at": stale_updated_at,
        },
    )
    assert save.status_code == 409, save.text
    assert save.json()["detail"]["code"] == "DRAFT_VERSION_CONFLICT"


def test_on_behalf_edit_save_returns_version_conflict_for_two_hr_stale_sessions(
    client,
    intake_on_behalf_schema_ready,
    privileged_headers,
) -> None:
    app_id, token, payload = _start_editable_intake(client, privileged_headers)
    session_a = _on_behalf_session(client, privileged_headers, app_id)
    session_b = _on_behalf_session(client, privileged_headers, app_id)
    stale_updated_at = session_a["draft"]["updated_at"]
    assert session_b["draft"]["updated_at"] == stale_updated_at

    payload_one = dict(payload)
    payload_one["employment_biography"] = [
        {
            "organization": "Городская поликлиника №1",
            "position": "Медсестра",
            "year_from": "2020-01-15",
            "year_to": "2024-08-01",
            "reason_for_leaving": "Переезд",
        }
    ]
    save_one = client.patch(
        f"/directory/personnel-applications/{app_id}/intake/draft/on-behalf",
        headers=privileged_headers,
        json={"payload": payload_one, "expected_updated_at": stale_updated_at},
    )
    assert save_one.status_code == 200, save_one.text

    payload_two = dict(payload)
    payload_two["employment_biography"] = [
        {
            "organization": "Городская поликлиника №2",
            "position": "Медсестра",
            "year_from": "2020-01-15",
            "year_to": "2024-08-01",
            "reason_for_leaving": "Переезд",
        }
    ]
    save_two = client.patch(
        f"/directory/personnel-applications/{app_id}/intake/draft/on-behalf",
        headers=privileged_headers,
        json={"payload": payload_two, "expected_updated_at": stale_updated_at},
    )
    assert save_two.status_code == 409, save_two.text
    assert save_two.json()["detail"]["code"] == "DRAFT_VERSION_CONFLICT"

    applicant_view = client.get(f"/intake/{token}")
    assert applicant_view.status_code == 200, applicant_view.text
    assert (
        applicant_view.json()["payload"]["employment_biography"][0]["organization"]
        == "Городская поликлиника №1"
    )


def test_on_behalf_edit_session_blocked_without_rework(
    client,
    intake_on_behalf_schema_ready,
    privileged_headers,
) -> None:
    app_id, _ = _submit_intake(client, privileged_headers)
    client.get(f"/directory/personnel-applications/{app_id}/intake/review", headers=privileged_headers)

    session = client.get(
        f"/directory/personnel-applications/{app_id}/intake/draft/on-behalf-edit",
        headers=privileged_headers,
    )
    assert session.status_code == 200, session.text
    body = session.json()
    assert body["editable"] is False
    assert body["reason_code"] == "NO_REWORK_SECTIONS"


def test_on_behalf_edit_save_updates_draft_and_audit_without_status_change(
    client,
    intake_on_behalf_schema_ready,
    privileged_headers,
    seed,
) -> None:
    app_id, payload = _submit_intake(client, privileged_headers)
    client.get(f"/directory/personnel-applications/{app_id}/intake/review", headers=privileged_headers)
    rework = client.post(
        f"/directory/personnel-applications/{app_id}/intake/review/sections/contacts/rework",
        headers=privileged_headers,
        json={"comment": "Уточните email"},
    )
    assert rework.status_code == 200, rework.text

    session = client.get(
        f"/directory/personnel-applications/{app_id}/intake/draft/on-behalf-edit",
        headers=privileged_headers,
    )
    assert session.status_code == 200, session.text
    assert session.json()["editable"] is True

    updated_payload = dict(payload)
    updated_payload["contacts"] = {**payload["contacts"], "email": "new-email@example.com"}
    updated_payload["employment_biography"] = [
        {
            "organization": "Клиника Б",
            "position": "Старшая медсестра",
            "year_from": "2020-01-15",
            "year_to": "2024-08-01",
            "reason_for_leaving": "Переезд",
        }
    ]

    save = client.patch(
        f"/directory/personnel-applications/{app_id}/intake/draft/on-behalf",
        headers=privileged_headers,
        json={
            "payload": updated_payload,
            "expected_updated_at": session.json()["draft"]["updated_at"],
        },
    )
    assert save.status_code == 200, save.text
    save_body = save.json()
    assert "contacts.email" in save_body["changed_fields"]
    assert any(field.startswith("employment_biography[0].") for field in save_body["changed_fields"])

    detail = client.get(f"/directory/personnel-applications/{app_id}", headers=privileged_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["status"] == APPLICATION_STATUS_UNDER_REVIEW

    with engine.connect() as conn:
        audit_row = conn.execute(
            text(
                """
                SELECT action, actor_user_id, previous_status, new_status, metadata
                FROM public.personnel_application_lifecycle_audit
                WHERE application_id = :application_id
                  AND action = :action
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {
                "application_id": app_id,
                "action": LIFECYCLE_ACTION_INTAKE_EDITED_ON_BEHALF,
            },
        ).mappings().one()
        metadata = audit_row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        assert audit_row["actor_user_id"] == seed["initiator_user_id"]
        assert audit_row["previous_status"] == APPLICATION_STATUS_UNDER_REVIEW
        assert audit_row["new_status"] == APPLICATION_STATUS_UNDER_REVIEW
        assert metadata["on_behalf_of"] == "applicant"
        assert metadata["actor_user_id"] == seed["initiator_user_id"]
        assert "contacts.email" in metadata["changed_fields"]


def test_on_behalf_edit_save_detects_military_and_employment_changes(
    client,
    intake_on_behalf_schema_ready,
    privileged_headers,
) -> None:
    app_id, payload = _submit_intake(client, privileged_headers)
    client.get(f"/directory/personnel-applications/{app_id}/intake/review", headers=privileged_headers)
    rework = client.post(
        f"/directory/personnel-applications/{app_id}/intake/review/sections/employment_biography/rework",
        headers=privileged_headers,
        json={"comment": "Уточните стаж"},
    )
    assert rework.status_code == 200, rework.text

    updated_payload = dict(payload)
    updated_payload["employment_biography"] = [
        {
            "organization": "Клиника Б",
            "position": "Старшая медсестра",
            "year_from": "2020-01-15",
            "year_to": "2024-08-01",
            "reason_for_leaving": "Переезд",
        }
    ]
    updated_payload["military"] = {
        **payload["military"],
        "status": "В запасе",
        "rank": "Сержант",
        "composition": "soldiers",
        "specialty_code": "1234567",
    }

    save = client.patch(
        f"/directory/personnel-applications/{app_id}/intake/draft/on-behalf",
        headers=privileged_headers,
        json={
            "payload": updated_payload,
            "expected_updated_at": _on_behalf_session(client, privileged_headers, app_id)["draft"]["updated_at"],
        },
    )
    assert save.status_code == 200, save.text
    changed_fields = save.json()["changed_fields"]
    assert any(field.startswith("employment_biography[0].") for field in changed_fields)
    assert "military.status" in changed_fields
    assert "military.rank" in changed_fields
    assert "military.specialty_code" in changed_fields


def test_on_behalf_edit_requires_personnel_admin(
    client,
    intake_on_behalf_schema_ready,
    privileged_headers,
    seed,
) -> None:
    app_id, _ = _submit_intake(client, privileged_headers)
    response = client.get(
        f"/directory/personnel-applications/{app_id}/intake/draft/on-behalf-edit",
        headers=auth_headers(seed["executor_user_id"]),
    )
    assert response.status_code == 403
