# tests/personnel_intake/test_intake_prefill.py
"""Unit and integration tests for intake draft prefill from personnel application."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.personnel_applications.domain.status import VACANCY_CHECK_CONFIRMED_VISUALLY
from app.personnel_intake.domain.prefill import (
    build_initial_intake_draft_payload,
    resolve_person_name_parts,
    split_russian_full_name,
)
from tests.conftest import auth_headers, table_exists
from tests.ppr.conftest import cleanup_person_graph, ppr_db_available


def test_split_russian_full_name() -> None:
    assert split_russian_full_name("Иванов Иван Иванович") == ("Иванов", "Иван", "Иванович")
    assert split_russian_full_name("Иванов Иван") == ("Иванов", "Иван", "")
    assert split_russian_full_name("Иванов") == ("Иванов", "", "")


def test_resolve_person_name_parts_prefers_structured_fields_over_full_name() -> None:
    assert resolve_person_name_parts(
        last_name="Алиев",
        first_name="Али",
        middle_name="Алиевич",
        full_name="Петров Пётр Петрович",
    ) == ("Алиев", "Али", "Алиевич")


def test_resolve_person_name_parts_falls_back_to_full_name_when_structured_missing() -> None:
    assert resolve_person_name_parts(
        last_name="",
        first_name="",
        middle_name="",
        full_name="Петров Пётр Петрович",
    ) == ("Петров", "Пётр", "Петрович")


def test_resolve_person_name_parts_does_not_shift_incomplete_structured_name() -> None:
    assert resolve_person_name_parts(
        last_name="Иванов",
        first_name="",
        middle_name="",
        full_name="Иванов Иван Иванович",
    ) == ("Иванов", "", "")
    assert resolve_person_name_parts(
        last_name="",
        first_name="Иван",
        middle_name="",
        full_name="Петров Пётр Петрович",
    ) == ("", "Иван", "")


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
        if not table_exists(conn, "personnel_intake_drafts"):
            pytest.skip("personnel_intake_drafts missing — run: alembic upgrade head")


def test_issue_link_prefills_draft_from_application(
    client, intake_schema_ready, privileged_headers
) -> None:
    person_ids: list[int] = []
    reg = client.post(
        "/directory/personnel-applications",
        json={
            "iin": f"8{uuid4().int % 10_000_000_000_000:011d}"[:12],
            "full_name": "Петров Пётр Петрович",
            "birth_date": "1990-05-20",
            "contact_mobile_phone": "+77005554433",
            "contact_email": "petrov@example.test",
            "application_received_at": "2026-07-17",
            "vacancy_check_status": VACANCY_CHECK_CONFIRMED_VISUALLY,
            "idempotency_key": f"prefill-{uuid4().hex}",
        },
        headers=privileged_headers,
    )
    assert reg.status_code == 200, reg.text
    person_ids.append(reg.json()["person_id"])
    app_id = reg.json()["application_id"]

    issue = client.post(
        f"/directory/personnel-applications/{app_id}/intake-link",
        headers=privileged_headers,
    )
    assert issue.status_code == 200, issue.text
    token = issue.json()["intake_url_path"].split("/intake/")[-1]

    opened = client.get(f"/intake/{token}")
    assert opened.status_code == 200, opened.text
    payload = opened.json()["payload"]
    assert payload["personal"]["last_name"] == "Петров"
    assert payload["personal"]["first_name"] == "Пётр"
    assert payload["personal"]["middle_name"] == "Петрович"
    assert payload["personal"]["birth_date"] == "1990-05-20"
    assert payload["contacts"]["mobile_phone"] == "+77005554433"
    assert payload["contacts"]["email"] == "petrov@example.test"

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_reopen_preserves_applicant_changes_over_prefill(
    client, intake_schema_ready, privileged_headers
) -> None:
    person_ids: list[int] = []
    reg = client.post(
        "/directory/personnel-applications",
        json={
            "iin": f"8{uuid4().int % 10_000_000_000_000:011d}"[:12],
            "full_name": "Сидоров Сидор Сидорович",
            "birth_date": "1985-01-01",
            "contact_mobile_phone": "+77001112233",
            "contact_email": "sidorov@example.test",
            "application_received_at": "2026-07-17",
            "vacancy_check_status": VACANCY_CHECK_CONFIRMED_VISUALLY,
            "idempotency_key": f"prefill-edit-{uuid4().hex}",
        },
        headers=privileged_headers,
    )
    assert reg.status_code == 200, reg.text
    person_ids.append(reg.json()["person_id"])
    app_id = reg.json()["application_id"]

    issue = client.post(
        f"/directory/personnel-applications/{app_id}/intake-link",
        headers=privileged_headers,
    )
    token = issue.json()["intake_url_path"].split("/intake/")[-1]

    opened = client.get(f"/intake/{token}")
    payload = opened.json()["payload"]
    payload["personal"]["last_name"] = "Изменён"
    payload["contacts"]["email"] = "changed@example.test"
    saved = client.patch(f"/intake/{token}", json={"payload": payload})
    assert saved.status_code == 200, saved.text

    reopened = client.get(f"/intake/{token}")
    assert reopened.status_code == 200, reopened.text
    next_payload = reopened.json()["payload"]
    assert next_payload["personal"]["last_name"] == "Изменён"
    assert next_payload["contacts"]["email"] == "changed@example.test"
    assert next_payload["personal"]["first_name"] == "Сидор"

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_prefill_uses_structured_person_name_when_present(
    intake_schema_ready, privileged_headers, client
) -> None:
    person_ids: list[int] = []
    reg = client.post(
        "/directory/personnel-applications",
        json={
            "iin": f"8{uuid4().int % 10_000_000_000_000:011d}"[:12],
            "full_name": "Петров Пётр Петрович",
            "birth_date": "1990-05-20",
            "contact_mobile_phone": "+77005554433",
            "contact_email": "petrov@example.test",
            "application_received_at": "2026-07-17",
            "vacancy_check_status": VACANCY_CHECK_CONFIRMED_VISUALLY,
            "idempotency_key": f"prefill-structured-{uuid4().hex}",
        },
        headers=privileged_headers,
    )
    assert reg.status_code == 200, reg.text
    person_ids.append(reg.json()["person_id"])
    app_id = reg.json()["application_id"]
    person_id = reg.json()["person_id"]

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE public.persons
                SET last_name = :last_name,
                    first_name = :first_name,
                    middle_name = :middle_name,
                    full_name = :full_name
                WHERE person_id = :person_id
                """
            ),
            {
                "person_id": person_id,
                "last_name": "Алиев",
                "first_name": "Али",
                "middle_name": "Алиевич",
                "full_name": "Петров Пётр Петрович",
            },
        )
        payload = build_initial_intake_draft_payload(conn, app_id)
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])

    assert payload["personal"]["last_name"] == "Алиев"
    assert payload["personal"]["first_name"] == "Али"
    assert payload["personal"]["middle_name"] == "Алиевич"


def test_reissue_intake_link_does_not_overwrite_existing_draft(
    client, intake_schema_ready, privileged_headers
) -> None:
    person_ids: list[int] = []
    reg = client.post(
        "/directory/personnel-applications",
        json={
            "iin": f"8{uuid4().int % 10_000_000_000_000:011d}"[:12],
            "full_name": "Кузнецов Кузьма Кузьмич",
            "birth_date": "1988-03-15",
            "contact_mobile_phone": "+77003332211",
            "contact_email": "kuznetsov@example.test",
            "application_received_at": "2026-07-17",
            "vacancy_check_status": VACANCY_CHECK_CONFIRMED_VISUALLY,
            "idempotency_key": f"prefill-reissue-{uuid4().hex}",
        },
        headers=privileged_headers,
    )
    assert reg.status_code == 200, reg.text
    person_ids.append(reg.json()["person_id"])
    app_id = reg.json()["application_id"]

    first_issue = client.post(
        f"/directory/personnel-applications/{app_id}/intake-link",
        headers=privileged_headers,
    )
    assert first_issue.status_code == 200, first_issue.text
    token = first_issue.json()["intake_url_path"].split("/intake/")[-1]

    opened = client.get(f"/intake/{token}")
    payload = opened.json()["payload"]
    payload["personal"]["last_name"] = "Сохранён"
    payload["contacts"]["email"] = "saved@example.test"
    saved = client.patch(f"/intake/{token}", json={"payload": payload})
    assert saved.status_code == 200, saved.text

    reissue = client.post(
        f"/directory/personnel-applications/{app_id}/intake-link/reissue",
        headers=privileged_headers,
    )
    assert reissue.status_code == 200, reissue.text
    new_token = reissue.json()["intake_url_path"].split("/intake/")[-1]

    reopened = client.get(f"/intake/{new_token}")
    assert reopened.status_code == 200, reopened.text
    next_payload = reopened.json()["payload"]
    assert next_payload["personal"]["last_name"] == "Сохранён"
    assert next_payload["contacts"]["email"] == "saved@example.test"

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_build_initial_intake_draft_payload_reads_application_row(
    intake_schema_ready, privileged_headers, client
) -> None:
    person_ids: list[int] = []
    reg = client.post(
        "/directory/personnel-applications",
        json={
            "iin": f"8{uuid4().int % 10_000_000_000_000:011d}"[:12],
            "full_name": "Козлов Козел Козлович",
            "birth_date": "1992-11-03",
            "contact_mobile_phone": "+77009998877",
            "contact_email": "kozlov@example.test",
            "application_received_at": "2026-07-17",
            "vacancy_check_status": VACANCY_CHECK_CONFIRMED_VISUALLY,
            "idempotency_key": f"prefill-domain-{uuid4().hex}",
        },
        headers=privileged_headers,
    )
    assert reg.status_code == 200, reg.text
    person_ids.append(reg.json()["person_id"])
    app_id = reg.json()["application_id"]

    with engine.begin() as conn:
        payload = build_initial_intake_draft_payload(conn, app_id)
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])

    assert payload["personal"]["last_name"] == "Козлов"
    assert payload["contacts"]["mobile_phone"] == "+77009998877"
