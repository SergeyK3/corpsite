"""WP-PPR-MIG-005C HTTP contract and authorization tests (no database data)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import ppr_migration_status_router as status_router
from app.auth import get_current_user
from app.main import app
from app.services.ppr_migration_status_projection_service import SECTIONS
from app.services.ppr_migration_status_report_service import ProjectionIntegrityError, build_presentation_status_summary


@pytest.fixture
def client(monkeypatch):
    app.dependency_overrides.clear()
    monkeypatch.setattr(status_router, "compute_scope", lambda *_a, **_k: {"privileged": True, "scope_unit_ids": None})
    monkeypatch.setattr(status_router, "require_personnel_visibility_or_403", lambda *_a: None)
    yield TestClient(app)
    app.dependency_overrides.clear()


def _authorize(monkeypatch, user_id: int, allowed: bool) -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id, "role_code": "HR_HEAD"}
    monkeypatch.setattr(status_router, "has_admin_permission", lambda uid, _permission: uid == user_id and allowed)


def test_unauthenticated_request_is_401(client):
    assert client.get("/directory/personnel/migration-status/universes").status_code == 401


def test_permission_is_required_and_admin_has_no_implicit_bypass(client, monkeypatch):
    _authorize(monkeypatch, 101, False)
    assert client.get("/directory/personnel/migration-status/universes").status_code == 403
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 102, "role_code": "ADMIN"}
    assert client.get("/directory/personnel/migration-status", params={"universe_id": 1}).status_code == 403


@pytest.mark.parametrize("user_id", [201, 202], ids=["hr_head_role_grant", "personal_grant"])
def test_role_and_personal_grant_authorize_both_read_endpoints(client, monkeypatch, user_id):
    _authorize(monkeypatch, user_id, True)
    monkeypatch.setattr(status_router, "list_universes", lambda *_a: [{"universe_id": 7, "base_cohort_run_id": 4, "supplemental_cohort_run_ids": [], "calculated_at": "2026-01-01T00:00:00Z"}])
    monkeypatch.setattr(status_router, "matrix", lambda *_a, **_k: {"universe_id": 7, "page": 1, "page_size": 50, "total": 0, "items": [], "counts": []})
    assert client.get("/directory/personnel/migration-status/universes").status_code == 200
    response = client.get("/directory/personnel/migration-status", params={"universe_id": 7})
    assert response.status_code == 200
    assert response.json()["universe_id"] == 7


def test_matrix_contract_rejects_missing_or_oversized_page_and_hides_unknown_universe(client, monkeypatch):
    _authorize(monkeypatch, 301, True)
    # The parameter-less route resolves the latest visible persisted universe.
    monkeypatch.setattr(status_router, "list_universes", lambda *_a: [{
        "universe_id": 7,
        "base_cohort_run_id": 4,
        "supplemental_cohort_run_ids": [],
        "calculated_at": "2026-01-01T00:00:00Z",
    }])
    monkeypatch.setattr(status_router, "matrix", lambda *_a, **kwargs: {
        "universe_id": kwargs["universe_id"], "page": 1, "page_size": 50,
        "total": 0, "items": [], "counts": [],
    })
    assert client.get("/directory/personnel/migration-status").status_code == 200
    assert client.get("/directory/personnel/migration-status", params={"universe_id": 1, "page_size": 101}).status_code == 422
    monkeypatch.setattr(status_router, "matrix", lambda *_a, **_k: None)
    response = client.get("/directory/personnel/migration-status", params={"universe_id": 999})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "MIGRATION_STATUS_UNIVERSE_NOT_FOUND"


def test_response_contains_only_safe_status_reason_and_evidence_fields(client, monkeypatch):
    _authorize(monkeypatch, 401, True)
    safe = {"universe_id": 3, "page": 1, "page_size": 1, "total": 1, "counts": [{"section_code": "general", "status_code": "ACCEPTED", "status_label": "Согласовано", "count": 1}], "items": [{"person_id": 8, "employee_context_id": 9, "org_unit_id": 10, "full_name": "Canonical Name", "cells": {"general": {"status_code": "ACCEPTED", "status_label": "Согласовано", "reason_code": "RUN_PARTICIPANT_ACCEPTED", "reason_label": "Результат сотрудника подтверждён.", "calculated_at": "2026-01-01T00:00:00Z", "stage_run_id": None, "stage1_run_id": 11, "stage_participant_id": None, "stage1_participant_id": 12, "pmf_run_id": None}}}]}
    monkeypatch.setattr(status_router, "matrix", lambda *_a, **_k: safe)
    body = client.get("/directory/personnel/migration-status", params={"universe_id": 3, "section": "general", "status": "ACCEPTED", "reason": "RUN_PARTICIPANT_ACCEPTED", "org_unit_id": 10, "q": "Canonical"}).json()
    serialized = str(body).lower()
    assert body["items"][0]["cells"]["general"]["status_label"]
    assert body["items"][0]["cells"]["general"]["reason_label"]
    assert not any(secret in serialized for secret in ("iin", "fingerprint", "raw_payload", "document", "traceback", "select "))


def test_new_section_filter_person_endpoint_and_integrity_error_are_safe(client, monkeypatch):
    _authorize(monkeypatch, 501, True)
    safe_cell = {"status_code": "NOT_STARTED", "status_label": "Не начато",
                 "reason_code": "SECTION_PROCESSING_NOT_CONNECTED",
                 "reason_label": "Обработка раздела ещё не подключена.",
                 "calculated_at": "2026-01-01T00:00:00Z", "stage_run_id": None,
                 "stage1_run_id": None, "stage_participant_id": None,
                 "stage1_participant_id": None, "pmf_run_id": None}
    cells = {section: dict(safe_cell) for section in SECTIONS}
    monkeypatch.setattr(status_router, "matrix", lambda *_a, **kwargs: {
        "universe_id": kwargs["universe_id"], "page": 1, "page_size": 50, "total": 1,
        "items": [], "counts": []})
    monkeypatch.setattr(status_router, "person_cells", lambda *_a, **_k: {"universe_id": 7, "cells": cells})
    assert client.get("/directory/personnel/migration-status", params={"universe_id": 7, "section": "awards"}).status_code == 200
    person = client.get("/directory/personnel/migration-status/persons/8", params={"universe_id": 7})
    assert person.status_code == 200
    assert tuple(person.json()["cells"]) == SECTIONS
    monkeypatch.setattr(status_router, "person_cells", lambda *_a, **_k: (_ for _ in ()).throw(ProjectionIntegrityError()))
    assert client.get("/directory/personnel/migration-status/persons/8", params={"universe_id": 7}).status_code == 409


def test_presentation_status_summary_counts_full_filtered_set_and_missing_cells() -> None:
    items = [
        {"person_id": 1, "cells": {"general": {"status_code": "AUTO_READY"}, "employment_biography": {"status_code": "NO_SOURCE_DATA"}, "employment_history": {"status_code": "NO_SOURCE_DATA"}}},
        {"person_id": 2, "cells": {"general": {"status_code": "REVIEW_REQUIRED"}, "employment_biography": {"status_code": "NO_SOURCE_DATA"}, "employment_history": {"status_code": "NO_SOURCE_DATA"}}},
    ]
    summary = build_presentation_status_summary(items)
    counts = {(item["section_code"], item["status_code"]): item["count"] for item in summary["counts"]}
    assert counts[("general", "AUTO_READY")] == 1
    assert counts[("general", "REVIEW_REQUIRED")] == 1
    assert counts[("employment_biography", "NO_SOURCE_DATA")] == 2
    assert counts[("employment_history", "NO_SOURCE_DATA")] == 2
    assert sum(counts[("general", status["code"])] for status in summary["statuses"]) == len(items)
    assert {section["code"] for section in summary["sections"]} >= {
        "employment_biography", "employment_history", "personnel_orders", "personnel_appeals", "adaptation",
        "foreign_languages", "additional", "awards", "academic_degrees_titles",
    }


def test_awards_and_academic_degrees_are_independent_summary_columns() -> None:
    summary = build_presentation_status_summary([{
        "person_id": 1,
        "cells": {
            "foreign_languages": {"status_code": "NO_SOURCE_DATA"},
            "awards": {"status_code": "REVIEW_REQUIRED"},
            "academic_degrees_titles": {"status_code": "AUTO_READY"},
        },
    }])
    counts = {(item["section_code"], item["status_code"]): item["count"] for item in summary["counts"]}
    assert counts[("foreign_languages", "NO_SOURCE_DATA")] == 1
    assert counts[("additional", "NO_SOURCE_DATA")] == 1
    assert counts[("awards", "REVIEW_REQUIRED")] == 1
    assert counts[("academic_degrees_titles", "AUTO_READY")] == 1


@pytest.mark.parametrize(
    ("record_statuses", "expected"),
    [
        ({"pending"}, ("REVIEW_REQUIRED", "IMPORT_NORMALIZED_RECORDS_REVIEW_REQUIRED")),
        ({"approved"}, ("ACCEPTED", "IMPORT_NORMALIZED_RECORDS_REVIEWED")),
        ({"promoted"}, ("ACCEPTED", "IMPORT_NORMALIZED_RECORDS_REVIEWED")),
        ({"rejected"}, ("REJECTED", "IMPORT_NORMALIZED_RECORDS_REJECTED")),
        ({"approved", "pending"}, ("REVIEW_REQUIRED", "IMPORT_NORMALIZED_RECORDS_REVIEW_REQUIRED")),
    ],
)
def test_normalized_section_status_keeps_multiple_records_and_prioritizes_review(record_statuses, expected) -> None:
    assert status_router._section_status_from_review_statuses(record_statuses) == expected


def test_normalized_section_aggregates_multiple_diplomas_without_treating_count_as_conflict(monkeypatch) -> None:
    monkeypatch.setattr(
        status_router,
        "classify_education_kind",
        lambda *_args: type("Classification", (), {"outcome": "AUTO_READY"})(),
    )
    diplomas = [
        {"review_status": "pending", "title": "Диплом 1", "source_text": "", "specialty_text": "", "confidence": 0.9},
        {"review_status": "pending", "title": "Диплом 2", "source_text": "", "specialty_text": "", "confidence": 0.8},
    ]
    assert status_router._aggregate_normalized_section(diplomas, record_kind="education") == (
        "AUTO_READY", "IMPORT_NORMALIZED_RECORDS_AUTO_READY",
    )


def test_normalized_section_requires_review_for_incomplete_course() -> None:
    course = [{"review_status": "pending", "title": "Курс", "confidence": 0.9, "hours": None, "end_date": None, "issue_date": None}]
    assert status_router._aggregate_normalized_section(course, record_kind="training") == (
        "REVIEW_REQUIRED", "IMPORT_NORMALIZED_RECORDS_REVIEW_REQUIRED",
    )
