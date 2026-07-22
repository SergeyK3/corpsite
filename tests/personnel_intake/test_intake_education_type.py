# tests/personnel_intake/test_intake_education_type.py
"""Tests for intake education_type contract and PPR mapping."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_migration import (
    EDUCATION_KIND_BASIC,
    EDUCATION_KIND_INTERNSHIP,
    EDUCATION_KIND_RESIDENCY,
)
from app.main import app
from app.personnel_applications.domain.status import (
    APPLICATION_STATUS_REVIEW_COMPLETED,
    VACANCY_CHECK_CONFIRMED_VISUALLY,
)
from app.personnel_intake.application.intake_mapper import map_education_records
from app.personnel_intake.application.intake_service import _validate_submit_payload
from app.personnel_intake.domain.education_type import normalize_intake_education_type
from app.personnel_intake.domain.errors import PersonnelIntakeValidationError
from app.personnel_intake.domain.models import empty_intake_draft_payload
from scripts.ops.reference_person_fixture_mapper import fixture_to_intake_draft, load_reference_fixture
from tests.conftest import auth_headers, table_exists
from tests.ppr.conftest import cleanup_person_graph, ppr_db_available


def _unique_iin() -> str:
    return f"8{uuid4().int % 10_000_000_000_000:011d}"[:12]


def _education_row(
    *,
    institution: str,
    education_type: str | None = "basic",
    specialty: str = "Med",
) -> dict[str, str]:
    row = {
        "institution": institution,
        "year_from": "2010",
        "year_to": "2015",
        "specialty": specialty,
        "qualification": "Spec",
        "diploma_number": "1",
    }
    if education_type is not None:
        row["education_type"] = education_type
    return row


def test_map_education_records_basic_and_internship_same_institution() -> None:
    institution = "КазНМУ им. С.Д. Асфендиярова (тест)"
    mapped = map_education_records(
        [
            _education_row(institution=institution, education_type="basic"),
            _education_row(institution=institution, education_type="internship", specialty="Cardio"),
        ]
    )
    assert mapped[0]["education_kind"] == EDUCATION_KIND_BASIC
    assert mapped[1]["education_kind"] == EDUCATION_KIND_INTERNSHIP
    assert mapped[0]["institution_name"] == institution
    assert mapped[1]["institution_name"] == institution


def test_map_education_records_missing_education_type_defaults_basic() -> None:
    mapped = map_education_records([_education_row(institution="КазНУ", education_type=None)])
    assert mapped[0]["education_kind"] == EDUCATION_KIND_BASIC


def test_normalize_intake_education_type_fallback() -> None:
    assert normalize_intake_education_type(None) == "basic"
    assert normalize_intake_education_type("") == "basic"
    assert normalize_intake_education_type("  ") == "basic"


def test_validate_submit_rejects_unknown_education_type() -> None:
    payload = empty_intake_draft_payload()
    payload["personal"]["last_name"] = "Test"
    payload["personal"]["first_name"] = "User"
    payload["contacts"]["mobile_phone"] = "+77001234567"
    payload["education"] = [_education_row(institution="ВУЗ", education_type="other")]

    with pytest.raises(PersonnelIntakeValidationError, match="education\\[0\\]\\.education_type"):
        _validate_submit_payload(payload)


def test_validate_submit_rejects_duplicate_kind_and_institution() -> None:
    payload = empty_intake_draft_payload()
    payload["personal"]["last_name"] = "Test"
    payload["personal"]["first_name"] = "User"
    payload["contacts"]["mobile_phone"] = "+77001234567"
    payload["education"] = [
        _education_row(institution="КазНМУ", education_type="basic"),
        _education_row(institution="КазНМУ", education_type="basic"),
    ]

    with pytest.raises(PersonnelIntakeValidationError, match="Duplicate education records"):
        _validate_submit_payload(payload)


def test_validate_submit_accepts_different_kind_same_institution() -> None:
    payload = empty_intake_draft_payload()
    payload["personal"]["last_name"] = "Test"
    payload["personal"]["first_name"] = "User"
    payload["contacts"]["mobile_phone"] = "+77001234567"
    payload["education"] = [
        _education_row(institution="КазНМУ", education_type="basic"),
        _education_row(institution="КазНМУ", education_type="internship"),
    ]

    _validate_submit_payload(payload)


def test_reference_fixture_mapper_preserves_internship_at_same_institution() -> None:
    draft = fixture_to_intake_draft(load_reference_fixture())
    education = draft["education"]
    assert len(education) == 3
    institution_counts: dict[str, list[str]] = {}
    for row in education:
        institution_counts.setdefault(row["institution"], []).append(row["education_type"])
    kaznmu = "КазНМУ им. С.Д. Асфендиярова (тест)"
    assert set(institution_counts[kaznmu]) == {"basic", "internship"}
    assert "residency" in institution_counts["Республиканский центр кардиохирургии (тест)"]


def test_reference_fixture_mapper_maps_education_kind_to_education_type() -> None:
    draft = fixture_to_intake_draft(load_reference_fixture())
    mapped = map_education_records(draft["education"])
    kinds = {row["education_kind"] for row in mapped}
    assert kinds == {EDUCATION_KIND_BASIC, EDUCATION_KIND_INTERNSHIP, EDUCATION_KIND_RESIDENCY}


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
        "full_name": "Education Intake Applicant",
        "application_received_at": "2026-07-17",
        "vacancy_check_status": VACANCY_CHECK_CONFIRMED_VISUALLY,
        "idempotency_key": f"intake-edu-{uuid4().hex}",
    }
    reg = client.post("/directory/personnel-applications", json=payload, headers=headers)
    assert reg.status_code == 200, reg.text
    return reg.json()


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


def test_intake_api_two_education_same_institution_transfer_creates_distinct_records(
    client, intake_review_schema_ready, privileged_headers
) -> None:
    person_ids: list[int] = []
    institution = "КазНМУ Education Flow Test"
    try:
        reg = _register_application(client, privileged_headers)
        person_ids.append(reg["person_id"])
        app_id = reg["application_id"]
        person_id = reg["person_id"]

        issue = client.post(
            f"/directory/personnel-applications/{app_id}/intake-link",
            headers=privileged_headers,
        )
        assert issue.status_code == 200, issue.text
        token = issue.json()["intake_url_path"].split("/intake/")[-1]

        payload = empty_intake_draft_payload()
        payload["personal"]["last_name"] = "Петров"
        payload["personal"]["first_name"] = "Пётр"
        payload["personal"]["birth_date"] = "1990-01-01"
        payload["contacts"]["mobile_phone"] = "+77005556677"
        payload["education"] = [
            _education_row(institution=institution, education_type="basic"),
            _education_row(institution=institution, education_type="internship", specialty="Therapy"),
        ]

        save = client.patch(f"/intake/{token}", json={"payload": payload})
        assert save.status_code == 200, save.text

        submit = client.post(f"/intake/{token}/submit", json={"payload": payload})
        assert submit.status_code == 200, submit.text

        _accept_required_and_skip_optional(client, privileged_headers, app_id)

        transfer = client.post(
            f"/directory/personnel-applications/{app_id}/intake/transfer",
            headers=privileged_headers,
        )
        assert transfer.status_code == 200, transfer.text
        assert transfer.json()["transfer"]["status"] == "completed"

        detail = client.get(f"/directory/personnel-applications/{app_id}", headers=privileged_headers)
        assert detail.json()["status"] == APPLICATION_STATUS_REVIEW_COMPLETED

        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT education_kind, institution_name
                    FROM public.person_education
                    WHERE person_id = :person_id
                      AND lifecycle_status = 'active'
                    ORDER BY education_kind
                    """
                ),
                {"person_id": person_id},
            ).all()
            assert len(rows) == 2
            assert rows[0].education_kind == EDUCATION_KIND_BASIC
            assert rows[1].education_kind == EDUCATION_KIND_INTERNSHIP
            assert rows[0].institution_name == institution
            assert rows[1].institution_name == institution
    finally:
        if person_ids:
            with engine.begin() as conn:
                cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_intake_api_submit_rejects_duplicate_education_type_and_institution(
    client, intake_review_schema_ready, privileged_headers
) -> None:
    person_ids: list[int] = []
    try:
        reg = _register_application(client, privileged_headers)
        person_ids.append(reg["person_id"])
        app_id = reg["application_id"]

        issue = client.post(
            f"/directory/personnel-applications/{app_id}/intake-link",
            headers=privileged_headers,
        )
        token = issue.json()["intake_url_path"].split("/intake/")[-1]

        payload = empty_intake_draft_payload()
        payload["personal"]["last_name"] = "Дубль"
        payload["personal"]["first_name"] = "Тест"
        payload["contacts"]["mobile_phone"] = "+77007778899"
        payload["education"] = [
            _education_row(institution="Same Uni", education_type="basic"),
            _education_row(institution="Same Uni", education_type="basic"),
        ]

        client.patch(f"/intake/{token}", json={"payload": payload})
        submit = client.post(f"/intake/{token}/submit", json={"payload": payload})
        assert submit.status_code == 422, submit.text
        assert "Duplicate education records" in submit.json()["detail"]["message"]
    finally:
        if person_ids:
            with engine.begin() as conn:
                cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])
