"""Eligibility rules for HR editing applicant intake draft on behalf of applicant."""
from __future__ import annotations

from app.personnel_applications.domain.status import (
    APPLICATION_STATUS_APPROVED,
    APPLICATION_STATUS_AWAITING_DIRECTOR_RESOLUTION,
    APPLICATION_STATUS_COMPLETED,
    APPLICATION_STATUS_INTAKE_PENDING,
    APPLICATION_STATUS_ORDER_DRAFT_CREATED,
    APPLICATION_STATUS_RESOLUTION_PENDING,
    APPLICATION_STATUS_REVISION_REQUESTED,
    APPLICATION_STATUS_UNDER_REVIEW,
    is_terminal_application_status,
)
from app.personnel_intake.domain.applicant_reedit import (
    can_applicant_reedit_submitted_intake,
    has_rework_requested_sections,
)
from app.personnel_intake.domain.status import INTAKE_DRAFT_STATUS_EDITABLE, INTAKE_DRAFT_STATUS_SUBMITTED

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


def _draft_open_for_post_submit_on_behalf(
    *,
    draft_status: str,
    application_status: str,
    section_statuses: list[str] | None,
) -> bool:
    draft_status_value = str(draft_status or "").strip()
    if draft_status_value == INTAKE_DRAFT_STATUS_SUBMITTED:
        return True
    if draft_status_value == INTAKE_DRAFT_STATUS_EDITABLE:
        return can_applicant_reedit_submitted_intake(
            application_status=application_status,
            section_statuses=section_statuses or [],
        )
    return False


def evaluate_on_behalf_edit_eligibility(
    *,
    application_status: str,
    draft_exists: bool,
    draft_status: str | None = None,
    section_statuses: list[str] | None = None,
) -> tuple[bool, str | None, str | None]:
    """Return (allowed, blocked_reason, reason_code)."""
    status = str(application_status or "").strip()
    draft_status_value = str(draft_status or "").strip()

    if not draft_exists:
        return False, ON_BEHALF_EDIT_BLOCKED_NO_DRAFT, "DRAFT_NOT_FOUND"

    if is_terminal_application_status(status) or status == APPLICATION_STATUS_COMPLETED:
        return False, ON_BEHALF_EDIT_BLOCKED_COMPLETED, "APPLICATION_TERMINAL"

    if status in APPROVAL_STAGE_STATUSES:
        return False, ON_BEHALF_EDIT_BLOCKED_APPROVAL, "APPROVAL_STAGE"

    if status == APPLICATION_STATUS_INTAKE_PENDING:
        if draft_status_value == INTAKE_DRAFT_STATUS_EDITABLE:
            return True, None, None
        return False, ON_BEHALF_EDIT_BLOCKED_NO_DRAFT, "DRAFT_NOT_EDITABLE"

    if status == APPLICATION_STATUS_REVISION_REQUESTED:
        if not _draft_open_for_post_submit_on_behalf(
            draft_status=draft_status_value,
            application_status=status,
            section_statuses=section_statuses,
        ):
            return False, ON_BEHALF_EDIT_BLOCKED_NO_DRAFT, "DRAFT_NOT_SUBMITTED"
        return True, None, None

    if status == APPLICATION_STATUS_UNDER_REVIEW:
        sections = section_statuses or []
        if not _draft_open_for_post_submit_on_behalf(
            draft_status=draft_status_value,
            application_status=status,
            section_statuses=sections,
        ):
            return False, ON_BEHALF_EDIT_BLOCKED_NO_DRAFT, "DRAFT_NOT_SUBMITTED"
        if has_rework_requested_sections(sections):
            return True, None, None
        return False, ON_BEHALF_EDIT_BLOCKED_NO_REWORK, "NO_REWORK_SECTIONS"

    return False, ON_BEHALF_EDIT_BLOCKED_NOT_RETURNED, "NOT_RETURNED_FOR_CLARIFICATION"
