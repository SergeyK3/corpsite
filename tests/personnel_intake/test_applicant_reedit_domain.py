"""Unit tests for applicant intake re-edit eligibility."""
from __future__ import annotations

from datetime import UTC, datetime

from app.personnel_intake.domain.applicant_reedit import (
    can_applicant_reedit_submitted_intake,
    should_reopen_submitted_intake_for_applicant_edit,
)


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


def test_should_reopen_before_resubmit_after_director_revision() -> None:
    resolution_at = datetime(2026, 7, 23, 4, 11, 26, tzinfo=UTC)
    original_submit = datetime(2026, 7, 22, 10, 0, 0, tzinfo=UTC)
    assert should_reopen_submitted_intake_for_applicant_edit(
        application_status="revision_requested",
        draft_status="submitted",
        link_status="submitted",
        draft_submitted_at=original_submit,
        director_resolution_at=resolution_at,
    )


def test_should_not_reopen_after_resubmit_since_director_revision() -> None:
    resolution_at = datetime(2026, 7, 23, 4, 11, 26, tzinfo=UTC)
    resubmit_at = datetime(2026, 7, 23, 5, 28, 59, tzinfo=UTC)
    assert not should_reopen_submitted_intake_for_applicant_edit(
        application_status="revision_requested",
        draft_status="submitted",
        link_status="submitted",
        draft_submitted_at=resubmit_at,
        director_resolution_at=resolution_at,
    )


def test_should_not_reopen_when_already_editing() -> None:
    assert not should_reopen_submitted_intake_for_applicant_edit(
        application_status="revision_requested",
        draft_status="editable",
        link_status="opened",
        draft_submitted_at=datetime(2026, 7, 23, 5, 28, 59, tzinfo=UTC),
        director_resolution_at=datetime(2026, 7, 23, 4, 11, 26, tzinfo=UTC),
    )
