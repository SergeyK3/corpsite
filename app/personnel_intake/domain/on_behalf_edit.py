"""Eligibility rules for HR editing applicant intake draft on behalf of applicant."""
from __future__ import annotations

from app.personnel_applications.domain.status import (
    APPLICATION_STATUS_APPROVED,
    APPLICATION_STATUS_AWAITING_DIRECTOR_RESOLUTION,
    APPLICATION_STATUS_COMPLETED,
    APPLICATION_STATUS_ORDER_DRAFT_CREATED,
    APPLICATION_STATUS_RESOLUTION_PENDING,
    APPLICATION_STATUS_REVISION_REQUESTED,
    APPLICATION_STATUS_UNDER_REVIEW,
    is_terminal_application_status,
)
from app.personnel_intake.domain.review_status import INTAKE_SECTION_REVIEW_REWORK_REQUESTED

APPROVAL_STAGE_STATUSES: frozenset[str] = frozenset(
    {
        APPLICATION_STATUS_RESOLUTION_PENDING,
        APPLICATION_STATUS_AWAITING_DIRECTOR_RESOLUTION,
        APPLICATION_STATUS_APPROVED,
        APPLICATION_STATUS_ORDER_DRAFT_CREATED,
    }
)

ON_BEHALF_EDIT_BLOCKED_APPROVAL = (
    "Редактирование недоступно: обращение на этапе согласования."
)
ON_BEHALF_EDIT_BLOCKED_COMPLETED = (
    "Редактирование недоступно: обращение завершено или закрыто."
)
ON_BEHALF_EDIT_BLOCKED_NOT_RETURNED = (
    "Редактирование доступно только после возврата обращения HR или претенденту на уточнение."
)
ON_BEHALF_EDIT_BLOCKED_NO_REWORK = (
    "Редактирование доступно только для разделов, возвращённых на уточнение."
)
ON_BEHALF_EDIT_BLOCKED_NO_DRAFT = "Анкета претендента ещё не создана или не отправлена."


def has_rework_requested_sections(section_statuses: list[str]) -> bool:
    return INTAKE_SECTION_REVIEW_REWORK_REQUESTED in section_statuses


def evaluate_on_behalf_edit_eligibility(
    *,
    application_status: str,
    draft_exists: bool,
    draft_submitted: bool,
    section_statuses: list[str] | None = None,
) -> tuple[bool, str | None, str | None]:
    """Return (allowed, blocked_reason, reason_code)."""
    status = str(application_status or "").strip()

    if not draft_exists:
        return False, ON_BEHALF_EDIT_BLOCKED_NO_DRAFT, "DRAFT_NOT_FOUND"

    if is_terminal_application_status(status) or status == APPLICATION_STATUS_COMPLETED:
        return False, ON_BEHALF_EDIT_BLOCKED_COMPLETED, "APPLICATION_TERMINAL"

    if status in APPROVAL_STAGE_STATUSES:
        return False, ON_BEHALF_EDIT_BLOCKED_APPROVAL, "APPROVAL_STAGE"

    if status == APPLICATION_STATUS_REVISION_REQUESTED:
        if not draft_submitted:
            return False, ON_BEHALF_EDIT_BLOCKED_NO_DRAFT, "DRAFT_NOT_SUBMITTED"
        return True, None, None

    if status == APPLICATION_STATUS_UNDER_REVIEW:
        if not draft_submitted:
            return False, ON_BEHALF_EDIT_BLOCKED_NO_DRAFT, "DRAFT_NOT_SUBMITTED"
        sections = section_statuses or []
        if has_rework_requested_sections(sections):
            return True, None, None
        return False, ON_BEHALF_EDIT_BLOCKED_NO_REWORK, "NO_REWORK_SECTIONS"

    return False, ON_BEHALF_EDIT_BLOCKED_NOT_RETURNED, "NOT_RETURNED_FOR_CLARIFICATION"
