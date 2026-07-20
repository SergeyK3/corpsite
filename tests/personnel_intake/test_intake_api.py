# tests/personnel_intake/test_intake_api.py
"""API integration tests for Personnel Intake (WP-PPR-INTAKE-001)."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.personnel_applications.domain.status import (
    APPLICATION_STATUS_INTAKE_PENDING,
    APPLICATION_STATUS_INTAKE_SUBMITTED,
    APPLICATION_STATUS_REGISTERED,
    VACANCY_CHECK_CONFIRMED_VISUALLY,
)
from app.personnel_intake.application.intake_service import _hash_token
from app.personnel_intake.domain.models import empty_intake_draft_payload
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
        "full_name": "Intake Test Applicant",
        "application_received_at": "2026-07-17",
        "vacancy_check_status": VACANCY_CHECK_CONFIRMED_VISUALLY,
        "idempotency_key": f"intake-{uuid4().hex}",
    }
    reg = client.post("/directory/personnel-applications", json=payload, headers=headers)
    assert reg.status_code == 200, reg.text
    return reg.json()


def _filled_payload() -> dict:
    payload = empty_intake_draft_payload()
    payload["personal"]["last_name"] = "Иванов"
    payload["personal"]["first_name"] = "Иван"
    payload["contacts"]["mobile_phone"] = "+77001234567"
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


def test_intake_routes_registered(client, intake_schema_ready) -> None:
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/directory/personnel-applications/{application_id}/intake-link" in paths
    assert "/directory/personnel-applications/{application_id}/intake-link/active" in paths
    assert "/intake/{token}" in paths
    assert "/intake/{token}/submit" in paths


def test_token_lifecycle_issue_open_autosave_submit(
    client, intake_schema_ready, privileged_headers
) -> None:
    person_ids: list[int] = []
    reg = _register_application(client, privileged_headers)
    person_ids.append(reg["person_id"])
    app_id = reg["application_id"]

    issue = client.post(
        f"/directory/personnel-applications/{app_id}/intake-link",
        headers=privileged_headers,
    )
    assert issue.status_code == 200, issue.text
    issue_body = issue.json()
    token = issue_body["intake_url_path"].split("/intake/")[-1]
    assert issue_body["status"] == "issued"

    detail = client.get(f"/directory/personnel-applications/{app_id}", headers=privileged_headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == APPLICATION_STATUS_INTAKE_PENDING

    open_res = client.get(f"/intake/{token}")
    assert open_res.status_code == 200, open_res.text
    open_body = open_res.json()
    assert open_body["link_status"] == "opened"
    assert open_body["read_only"] is False

    payload = _filled_payload()
    save = client.patch(f"/intake/{token}", json={"payload": payload})
    assert save.status_code == 200, save.text
    assert save.json()["payload"]["personal"]["last_name"] == "Иванов"

    submit = client.post(f"/intake/{token}/submit", json={"payload": payload})
    assert submit.status_code == 200, submit.text
    assert submit.json()["status"] == "submitted"

    detail_after = client.get(f"/directory/personnel-applications/{app_id}", headers=privileged_headers)
    assert detail_after.json()["status"] == APPLICATION_STATUS_INTAKE_SUBMITTED
    assert detail_after.json()["intake_draft_status"] == "submitted"
    assert detail_after.json()["intake_submitted_at"] is not None

    readonly = client.patch(f"/intake/{token}", json={"payload": payload})
    assert readonly.status_code == 403

    reopen = client.get(f"/intake/{token}")
    assert reopen.status_code == 200
    assert reopen.json()["read_only"] is True

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_hr_active_intake_link_persists_without_browser_cache(
    client, intake_schema_ready, privileged_headers
) -> None:
    person_ids: list[int] = []
    reg = _register_application(client, privileged_headers)
    person_ids.append(reg["person_id"])
    app_id = reg["application_id"]

    issue = client.post(
        f"/directory/personnel-applications/{app_id}/intake-link",
        headers=privileged_headers,
    )
    assert issue.status_code == 200, issue.text
    issue_path = issue.json()["intake_url_path"]

    active = client.get(
        f"/directory/personnel-applications/{app_id}/intake-link/active",
        headers=privileged_headers,
    )
    assert active.status_code == 200, active.text
    active_body = active.json()
    assert active_body["display_state"] == "active"
    assert active_body["intake_url_path"] == issue_path

    listing = client.get("/directory/personnel-applications", headers=privileged_headers)
    assert listing.status_code == 200, listing.text
    row = next(item for item in listing.json()["items"] if item["application_id"] == app_id)
    assert row["intake_link_display_state"] == "active"
    assert row["intake_url_path"] == issue_path

    token = issue_path.split("/intake/")[-1]
    open_res = client.get(f"/intake/{token}")
    assert open_res.status_code == 200, open_res.text
    assert open_res.json()["application_id"] == app_id

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_legacy_hash_only_link_requires_reissue(
    client, intake_schema_ready, privileged_headers, seed
) -> None:
    person_ids: list[int] = []
    reg = _register_application(client, privileged_headers)
    person_ids.append(reg["person_id"])
    app_id = reg["application_id"]
    raw_token = "legacy-hash-only-token"
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO public.personnel_intake_links (
                    application_id, token_hash, status, issued_by_user_id, expires_at
                )
                VALUES (
                    :application_id, :token_hash, 'issued', :issued_by_user_id, NOW() + INTERVAL '7 days'
                )
                """
            ),
            {
                "application_id": app_id,
                "token_hash": _hash_token(raw_token),
                "issued_by_user_id": seed["initiator_user_id"],
            },
        )

    active = client.get(
        f"/directory/personnel-applications/{app_id}/intake-link/active",
        headers=privileged_headers,
    )
    assert active.status_code == 200, active.text
    assert active.json()["display_state"] == "reissue_required"
    assert active.json()["intake_url_path"] is None

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_revoke_link(client, intake_schema_ready, privileged_headers) -> None:
    person_ids: list[int] = []
    reg = _register_application(client, privileged_headers)
    person_ids.append(reg["person_id"])
    app_id = reg["application_id"]

    issue = client.post(
        f"/directory/personnel-applications/{app_id}/intake-link",
        headers=privileged_headers,
    )
    token = issue.json()["intake_url_path"].split("/intake/")[-1]

    revoke = client.post(
        f"/directory/personnel-applications/{app_id}/intake-link/revoke",
        headers=privileged_headers,
    )
    assert revoke.status_code == 200
    assert revoke.json()["status"] == "revoked"

    active = client.get(
        f"/directory/personnel-applications/{app_id}/intake-link/active",
        headers=privileged_headers,
    )
    assert active.status_code == 200, active.text
    assert active.json()["display_state"] == "revoked"
    assert active.json()["intake_url_path"] is None

    denied = client.get(f"/intake/{token}")
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "TOKEN_REVOKED"

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_revoke_submitted_link(client, intake_schema_ready, privileged_headers) -> None:
    person_ids: list[int] = []
    reg = _register_application(client, privileged_headers)
    person_ids.append(reg["person_id"])
    app_id = reg["application_id"]

    issue = client.post(
        f"/directory/personnel-applications/{app_id}/intake-link",
        headers=privileged_headers,
    )
    token = issue.json()["intake_url_path"].split("/intake/")[-1]
    payload = _filled_payload()
    client.get(f"/intake/{token}")
    client.patch(f"/intake/{token}", json={"payload": payload})
    client.post(f"/intake/{token}/submit", json={"payload": payload})

    revoke = client.post(
        f"/directory/personnel-applications/{app_id}/intake-link/revoke",
        headers=privileged_headers,
    )
    assert revoke.status_code == 200
    assert revoke.json()["status"] == "revoked"

    active = client.get(
        f"/directory/personnel-applications/{app_id}/intake-link/active",
        headers=privileged_headers,
    )
    assert active.json()["display_state"] == "revoked"
    assert active.json()["intake_url_path"] is None

    denied = client.get(f"/intake/{token}")
    assert denied.status_code == 403

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_reissue_link(client, intake_schema_ready, privileged_headers) -> None:
    person_ids: list[int] = []
    reg = _register_application(client, privileged_headers)
    person_ids.append(reg["person_id"])
    app_id = reg["application_id"]

    first = client.post(
        f"/directory/personnel-applications/{app_id}/intake-link",
        headers=privileged_headers,
    )
    old_token = first.json()["intake_url_path"].split("/intake/")[-1]

    reissue = client.post(
        f"/directory/personnel-applications/{app_id}/intake-link/reissue",
        headers=privileged_headers,
    )
    assert reissue.status_code == 200
    assert reissue.json()["reissued"] is True
    new_token = reissue.json()["intake_url_path"].split("/intake/")[-1]
    assert new_token != old_token

    old_denied = client.get(f"/intake/{old_token}")
    assert old_denied.status_code == 403

    new_ok = client.get(f"/intake/{new_token}")
    assert new_ok.status_code == 200

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_expired_token(client, intake_schema_ready, privileged_headers, monkeypatch) -> None:
    person_ids: list[int] = []
    reg = _register_application(client, privileged_headers)
    person_ids.append(reg["person_id"])
    app_id = reg["application_id"]

    issue = client.post(
        f"/directory/personnel-applications/{app_id}/intake-link",
        headers=privileged_headers,
    )
    token = issue.json()["intake_url_path"].split("/intake/")[-1]
    token_hash = _hash_token(token)

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE public.personnel_intake_links
                SET expires_at = :past
                WHERE token_hash = :token_hash
                """
            ),
            {"past": datetime.now(UTC) - timedelta(hours=1), "token_hash": token_hash},
        )

    expired = client.get(f"/intake/{token}")
    assert expired.status_code == 403
    assert expired.json()["detail"]["code"] == "TOKEN_EXPIRED"

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_invalid_token_denied(client, intake_schema_ready) -> None:
    res = client.get("/intake/not-a-valid-token-at-all")
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "TOKEN_INVALID"


def test_reopen_preserves_draft(client, intake_schema_ready, privileged_headers) -> None:
    person_ids: list[int] = []
    reg = _register_application(client, privileged_headers)
    person_ids.append(reg["person_id"])
    app_id = reg["application_id"]

    issue = client.post(
        f"/directory/personnel-applications/{app_id}/intake-link",
        headers=privileged_headers,
    )
    token = issue.json()["intake_url_path"].split("/intake/")[-1]

    payload = _filled_payload()
    client.patch(f"/intake/{token}", json={"payload": payload})

    first = client.get(f"/intake/{token}")
    assert first.status_code == 200

    second = client.get(f"/intake/{token}")
    assert second.status_code == 200
    assert second.json()["payload"]["personal"]["last_name"] == "Иванов"
    assert second.json()["link_status"] == "opened"

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])
