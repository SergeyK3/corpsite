"""Rules for reopening a submitted intake form to the applicant."""
from __future__ import annotations

from app.personnel_applications.domain.status import (
    APPLICATION_STATUS_REVISION_REQUESTED,
    APPLICATION_STATUS_UNDER_REVIEW,
)
from app.personnel_intake.domain.review_status import INTAKE_SECTION_REVIEW_REWORK_REQUESTED


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
