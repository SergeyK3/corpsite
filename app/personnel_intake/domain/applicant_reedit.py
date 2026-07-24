"""Rules for reopening a submitted intake form to the applicant."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.personnel_applications.domain.status import (
    APPLICATION_STATUS_REVISION_REQUESTED,
    APPLICATION_STATUS_UNDER_REVIEW,
)
from app.personnel_intake.domain.review_status import INTAKE_SECTION_REVIEW_REWORK_REQUESTED
from app.personnel_intake.domain.status import (
    INTAKE_DRAFT_STATUS_EDITABLE,
    INTAKE_DRAFT_STATUS_SUBMITTED,
    INTAKE_LINK_STATUS_OPENED,
    INTAKE_LINK_STATUS_SUBMITTED,
)


class _SectionReviewTiming(Protocol):
    status: str
    reviewed_at: datetime | None
    updated_at: datetime


def has_rework_requested_sections(section_statuses: list[str]) -> bool:
    return INTAKE_SECTION_REVIEW_REWORK_REQUESTED in section_statuses


def can_applicant_reedit_submitted_intake(
    *,
    application_status: str,
    section_statuses: list[str] | None = None,
) -> bool:
    status = str(application_status or "").strip()
    if status == APPLICATION_STATUS_REVISION_REQUESTED:
        return True
    if status == APPLICATION_STATUS_UNDER_REVIEW:
        return has_rework_requested_sections(section_statuses or [])
    return False


def rework_reopen_cutoff_at(
    *,
    application_status: str,
    director_resolution_at: datetime | None = None,
    section_reviews: list[_SectionReviewTiming] | None = None,
) -> datetime | None:
    """Return the timestamp after which a (re)submit satisfies the current rework request."""
    status = str(application_status or "").strip()
    if status == APPLICATION_STATUS_REVISION_REQUESTED:
        return director_resolution_at
    if status == APPLICATION_STATUS_UNDER_REVIEW:
        cutoffs = [
            section.reviewed_at or section.updated_at
            for section in section_reviews or []
            if section.status == INTAKE_SECTION_REVIEW_REWORK_REQUESTED
        ]
        return max(cutoffs) if cutoffs else None
    return None


def should_reopen_submitted_intake_for_applicant_edit(
    *,
    application_status: str,
    draft_status: str,
    link_status: str,
    draft_submitted_at: datetime | None,
    director_resolution_at: datetime | None = None,
    section_reviews: list[_SectionReviewTiming] | None = None,
) -> bool:
    """Whether a submitted link/draft pair should transition back to editable."""
    draft_status_value = str(draft_status or "").strip()
    link_status_value = str(link_status or "").strip()
    section_statuses = [section.status for section in section_reviews or []]

    if draft_status_value == INTAKE_DRAFT_STATUS_EDITABLE or link_status_value == INTAKE_LINK_STATUS_OPENED:
        return False

    if draft_status_value != INTAKE_DRAFT_STATUS_SUBMITTED or link_status_value != INTAKE_LINK_STATUS_SUBMITTED:
        return False

    if not can_applicant_reedit_submitted_intake(
        application_status=application_status,
        section_statuses=section_statuses,
    ):
        return False

    cutoff = rework_reopen_cutoff_at(
        application_status=application_status,
        director_resolution_at=director_resolution_at,
        section_reviews=section_reviews,
    )
    if cutoff is None or draft_submitted_at is None:
        return True
    return draft_submitted_at <= cutoff
