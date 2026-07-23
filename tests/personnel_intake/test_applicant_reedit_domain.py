"""Unit tests for applicant intake re-edit eligibility."""
from __future__ import annotations

from app.personnel_intake.domain.applicant_reedit import can_applicant_reedit_submitted_intake


def test_can_reedit_when_section_rework_requested() -> None:
    assert can_applicant_reedit_submitted_intake(
        application_status="under_review",
        section_statuses=["accepted", "rework_requested", "pending"],
    )


def test_cannot_reedit_under_review_without_rework() -> None:
    assert not can_applicant_reedit_submitted_intake(
        application_status="under_review",
        section_statuses=["accepted", "pending"],
    )


def test_can_reedit_when_revision_requested() -> None:
    assert can_applicant_reedit_submitted_intake(
        application_status="revision_requested",
        section_statuses=[],
    )


def test_cannot_reedit_after_intake_submitted_without_return() -> None:
    assert not can_applicant_reedit_submitted_intake(
        application_status="intake_submitted",
        section_statuses=[],
    )
