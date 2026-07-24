# tests/personnel_intake/test_on_behalf_edit_domain.py
"""Unit tests for HR on-behalf intake edit eligibility."""
from __future__ import annotations

from app.personnel_intake.application.payload_diff import compute_intake_payload_field_changes
from app.personnel_intake.domain.on_behalf_edit import evaluate_on_behalf_edit_eligibility


def test_evaluate_on_behalf_edit_allows_intake_pending_with_editable_draft() -> None:
    allowed, reason, code = evaluate_on_behalf_edit_eligibility(
        application_status="intake_pending",
        draft_exists=True,
        draft_status="editable",
    )
    assert allowed is True
    assert reason is None
    assert code is None


def test_evaluate_on_behalf_edit_blocks_intake_pending_without_editable_draft() -> None:
    allowed, reason, code = evaluate_on_behalf_edit_eligibility(
        application_status="intake_pending",
        draft_exists=True,
        draft_status="submitted",
    )
    assert allowed is False
    assert reason is not None
    assert code == "DRAFT_NOT_EDITABLE"


def test_evaluate_on_behalf_edit_allows_under_review_with_rework() -> None:
    allowed, reason, code = evaluate_on_behalf_edit_eligibility(
        application_status="under_review",
        draft_exists=True,
        draft_status="submitted",
        section_statuses=["accepted", "rework_requested", "pending"],
    )
    assert allowed is True
    assert reason is None
    assert code is None


def test_evaluate_on_behalf_edit_blocks_under_review_without_rework() -> None:
    allowed, reason, code = evaluate_on_behalf_edit_eligibility(
        application_status="under_review",
        draft_exists=True,
        draft_status="submitted",
        section_statuses=["accepted", "pending"],
    )
    assert allowed is False
    assert reason is not None
    assert code == "NO_REWORK_SECTIONS"


def test_evaluate_on_behalf_edit_allows_revision_requested() -> None:
    allowed, reason, code = evaluate_on_behalf_edit_eligibility(
        application_status="revision_requested",
        draft_exists=True,
        draft_status="submitted",
        section_statuses=["accepted"],
    )
    assert allowed is True
    assert reason is None
    assert code is None


def test_evaluate_on_behalf_edit_allows_revision_requested_with_editable_draft() -> None:
    allowed, reason, code = evaluate_on_behalf_edit_eligibility(
        application_status="revision_requested",
        draft_exists=True,
        draft_status="editable",
        section_statuses=["accepted"],
    )
    assert allowed is True
    assert reason is None
    assert code is None


def test_evaluate_on_behalf_edit_allows_under_review_with_editable_draft_after_rework() -> None:
    allowed, reason, code = evaluate_on_behalf_edit_eligibility(
        application_status="under_review",
        draft_exists=True,
        draft_status="editable",
        section_statuses=["accepted", "rework_requested", "pending"],
    )
    assert allowed is True
    assert reason is None
    assert code is None


def test_evaluate_on_behalf_edit_blocks_approval_stage() -> None:
    allowed, reason, code = evaluate_on_behalf_edit_eligibility(
        application_status="awaiting_director_resolution",
        draft_exists=True,
        draft_status="submitted",
        section_statuses=["rework_requested"],
    )
    assert allowed is False
    assert "согласования" in (reason or "")
    assert code == "APPROVAL_STAGE"


def test_evaluate_on_behalf_edit_blocks_terminal_application() -> None:
    allowed, reason, code = evaluate_on_behalf_edit_eligibility(
        application_status="completed",
        draft_exists=True,
        draft_status="submitted",
    )
    assert allowed is False
    assert code == "APPLICATION_TERMINAL"


def test_compute_intake_payload_field_changes_lists_nested_paths() -> None:
    before = {
        "personal": {"last_name": "Иванов", "first_name": "Иван"},
        "employment_biography": [{"organization": "A", "position": "X"}],
    }
    after = {
        "personal": {"last_name": "Петров", "first_name": "Иван"},
        "employment_biography": [{"organization": "B", "position": "X"}],
    }
    changes = compute_intake_payload_field_changes(before, after)
    assert "personal.last_name" in changes
    assert "employment_biography[0].organization" in changes
    assert "personal.first_name" not in changes


def test_compute_intake_payload_field_changes_detects_military_and_employment() -> None:
    before = {
        "employment_biography": [
            {
                "organization": "Клиника А",
                "position": "Медсестра",
                "year_from": "2020",
                "year_to": "2024",
                "reason_for_leaving": "Переезд",
            }
        ],
        "military": {
            "status": "",
            "rank": "",
            "category": "",
            "composition": "soldiers",
            "specialty_code": "",
            "specialty_name": "",
            "fitness_category": "",
            "commissariat": "",
            "registration_group": "",
            "registration_category": "",
        },
        "current_step": "review",
    }
    after = {
        "employment_biography": [
            {
                "organization": "Клиника Б",
                "position": "Старшая медсестра",
                "year_from": "2020",
                "year_to": "2024",
                "reason_for_leaving": "Переезд",
            }
        ],
        "military": {
            "status": "В запасе",
            "rank": "Сержант",
            "category": "",
            "composition": "soldiers",
            "specialty_code": "1234567",
            "specialty_name": "",
            "fitness_category": "",
            "commissariat": "",
            "registration_group": "",
            "registration_category": "",
        },
        "current_step": "employment_biography",
    }
    changes = compute_intake_payload_field_changes(before, after)
    assert "employment_biography[0].organization" in changes
    assert "employment_biography[0].position" in changes
    assert "military.status" in changes
    assert "military.rank" in changes
    assert "military.specialty_code" in changes
    assert "current_step" not in changes
