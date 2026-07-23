"""HR review workflow for submitted intake drafts (WP-PPR-INTAKE-002)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.personnel_applications.domain.errors import PersonnelApplicationNotFoundError
from app.personnel_applications.domain.status import (
    APPLICATION_STATUS_INTAKE_SUBMITTED,
    APPLICATION_STATUS_REVIEW_COMPLETED,
    APPLICATION_STATUS_UNDER_REVIEW,
)
from app.personnel_applications.infrastructure.repository import SqlAlchemyPersonnelApplicationRepository
from app.personnel_intake.application.intake_section_utils import (
    extract_section_payload,
    is_intake_section_empty,
)
from app.personnel_intake.domain.errors import (
    PersonnelIntakeNotFoundError,
    PersonnelIntakeReviewError,
)
from app.personnel_intake.domain.models import IntakeReviewState, IntakeSectionReviewSnapshot
from app.personnel_intake.domain.review_status import (
    INTAKE_REQUIRED_SECTIONS,
    INTAKE_SECTION_REVIEW_ACCEPTED,
    INTAKE_SECTION_REVIEW_REWORK_REQUESTED,
    INTAKE_SECTION_REVIEW_SKIPPED,
    INTAKE_TRANSFER_STATUS_COMPLETED,
    is_section_review_terminal,
)
from app.personnel_intake.domain.status import INTAKE_DRAFT_STATUS_EDITABLE, INTAKE_DRAFT_STATUS_SUBMITTED
from app.personnel_intake.domain.applicant_reedit import can_applicant_reedit_submitted_intake
from app.personnel_intake.application.intake_service import reopen_intake_for_applicant_rework
from app.personnel_intake.infrastructure.repository import SqlAlchemyPersonnelIntakeRepository
from app.personnel_intake.infrastructure.review_repository import SqlAlchemyPersonnelIntakeReviewRepository


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _transition_application_status(
    conn: Connection,
    *,
    application_id: int,
    new_status: str,
    now: datetime,
) -> None:
    conn.execute(
        text(
            """
            UPDATE public.personnel_applications
            SET status = :status, updated_at = :now
            WHERE application_id = :application_id
            """
        ),
        {"status": new_status, "now": now, "application_id": int(application_id)},
    )


def _require_submitted_draft(conn: Connection, application_id: int, *, allow_completed: bool = False):
    app_repo = SqlAlchemyPersonnelApplicationRepository(conn)
    app = app_repo.require_by_id(application_id)
    if app.status == APPLICATION_STATUS_REVIEW_COMPLETED:
        if allow_completed:
            intake_repo = SqlAlchemyPersonnelIntakeRepository(conn)
            draft = intake_repo.get_draft_by_application_id(application_id)
            if draft is None:
                raise PersonnelIntakeNotFoundError("Intake draft not found.")
            return app, draft
        raise PersonnelIntakeReviewError(
            "Application review is already completed.",
            code="REVIEW_ALREADY_COMPLETED",
        )
    if app.status not in {
        APPLICATION_STATUS_INTAKE_SUBMITTED,
        APPLICATION_STATUS_UNDER_REVIEW,
    }:
        raise PersonnelIntakeReviewError(
            f"Review is only available after intake submission (status={app.status}).",
            code="REVIEW_NOT_AVAILABLE",
        )
    intake_repo = SqlAlchemyPersonnelIntakeRepository(conn)
    draft = intake_repo.get_draft_by_application_id(application_id)
    if draft is None:
        raise PersonnelIntakeNotFoundError("Submitted intake draft not found.")
    if draft.status == INTAKE_DRAFT_STATUS_SUBMITTED:
        return app, draft
    if draft.status == INTAKE_DRAFT_STATUS_EDITABLE:
        review_repo = SqlAlchemyPersonnelIntakeReviewRepository(conn)
        sections = review_repo.list_section_reviews(application_id)
        if can_applicant_reedit_submitted_intake(
            application_status=app.status,
            section_statuses=[section.status for section in sections],
        ):
            return app, draft
    raise PersonnelIntakeNotFoundError("Submitted intake draft not found.")


def _evaluate_can_transfer(
    sections: list[IntakeSectionReviewSnapshot],
    payload: dict,
) -> tuple[bool, str | None]:
    if not sections:
        return False, "Section reviews are not initialized."
    for section in sections:
        if not is_section_review_terminal(section.status):
            return False, f"Section {section.section_code} is not finalized."
        if (
            section.section_code in INTAKE_REQUIRED_SECTIONS
            and section.status != INTAKE_SECTION_REVIEW_ACCEPTED
        ):
            return False, f"Required section {section.section_code} must be accepted."
        if section.status == INTAKE_SECTION_REVIEW_SKIPPED and not is_intake_section_empty(
            section.section_code, payload
        ):
            return False, f"Non-empty section {section.section_code} cannot be skipped."
        if section.status == INTAKE_SECTION_REVIEW_REWORK_REQUESTED:
            return False, f"Section {section.section_code} requires rework."
    return True, None


@dataclass(frozen=True, slots=True)
class SectionReviewActionResult:
    section: IntakeSectionReviewSnapshot
    review_state: IntakeReviewState


def load_intake_review_state(conn: Connection, application_id: int) -> IntakeReviewState:
    app, draft = _require_submitted_draft(conn, application_id, allow_completed=True)
    now = _now_utc()
    review_repo = SqlAlchemyPersonnelIntakeReviewRepository(conn)
    sections = review_repo.ensure_section_reviews(application_id, now=now)
    transfer = review_repo.get_transfer(application_id)

    if app.status == APPLICATION_STATUS_INTAKE_SUBMITTED:
        _transition_application_status(
            conn,
            application_id=application_id,
            new_status=APPLICATION_STATUS_UNDER_REVIEW,
            now=now,
        )

    can_transfer, blocked = _evaluate_can_transfer(sections, draft.payload)
    if transfer is not None and transfer.status == INTAKE_TRANSFER_STATUS_COMPLETED:
        can_transfer = False
        blocked = "Transfer already completed."
    if app.status == APPLICATION_STATUS_REVIEW_COMPLETED:
        can_transfer = False
        blocked = blocked or "Review completed."

    return IntakeReviewState(
        application_id=application_id,
        draft=draft,
        sections=sections,
        transfer=transfer,
        can_transfer=can_transfer,
        transfer_blocked_reason=blocked,
    )


def accept_intake_section(
    conn: Connection,
    *,
    application_id: int,
    section_code: str,
    reviewed_by_user_id: int,
) -> SectionReviewActionResult:
    _, draft = _require_submitted_draft(conn, application_id)
    if is_intake_section_empty(section_code, draft.payload):
        raise PersonnelIntakeReviewError(
            f"Section {section_code} is empty; use skip instead.",
            code="SECTION_EMPTY_USE_SKIP",
        )
    now = _now_utc()
    review_repo = SqlAlchemyPersonnelIntakeReviewRepository(conn)
    review_repo.ensure_section_reviews(application_id, now=now)
    section = review_repo.update_section_review(
        application_id,
        section_code,
        status=INTAKE_SECTION_REVIEW_ACCEPTED,
        reviewed_by_user_id=reviewed_by_user_id,
        reviewed_at=now,
        rework_comment=None,
    )
    state = load_intake_review_state(conn, application_id)
    return SectionReviewActionResult(section=section, review_state=state)


def rework_intake_section(
    conn: Connection,
    *,
    application_id: int,
    section_code: str,
    reviewed_by_user_id: int,
    comment: str,
) -> SectionReviewActionResult:
    _require_submitted_draft(conn, application_id)
    comment_text = str(comment or "").strip()
    if not comment_text:
        raise PersonnelIntakeReviewError(
            "Rework comment is required.",
            code="REWORK_COMMENT_REQUIRED",
        )
    now = _now_utc()
    review_repo = SqlAlchemyPersonnelIntakeReviewRepository(conn)
    review_repo.ensure_section_reviews(application_id, now=now)
    section = review_repo.update_section_review(
        application_id,
        section_code,
        status=INTAKE_SECTION_REVIEW_REWORK_REQUESTED,
        reviewed_by_user_id=reviewed_by_user_id,
        reviewed_at=now,
        rework_comment=comment_text,
    )
    reopen_intake_for_applicant_rework(conn, application_id)
    state = load_intake_review_state(conn, application_id)
    return SectionReviewActionResult(section=section, review_state=state)


def skip_intake_section(
    conn: Connection,
    *,
    application_id: int,
    section_code: str,
    reviewed_by_user_id: int,
) -> SectionReviewActionResult:
    _, draft = _require_submitted_draft(conn, application_id)
    if not is_intake_section_empty(section_code, draft.payload):
        raise PersonnelIntakeReviewError(
            f"Section {section_code} is not empty and cannot be skipped.",
            code="SECTION_NOT_EMPTY",
        )
    if section_code in INTAKE_REQUIRED_SECTIONS:
        raise PersonnelIntakeReviewError(
            f"Required section {section_code} cannot be skipped.",
            code="REQUIRED_SECTION_CANNOT_SKIP",
        )
    now = _now_utc()
    review_repo = SqlAlchemyPersonnelIntakeReviewRepository(conn)
    review_repo.ensure_section_reviews(application_id, now=now)
    section = review_repo.update_section_review(
        application_id,
        section_code,
        status=INTAKE_SECTION_REVIEW_SKIPPED,
        reviewed_by_user_id=reviewed_by_user_id,
        reviewed_at=now,
        rework_comment=None,
    )
    state = load_intake_review_state(conn, application_id)
    return SectionReviewActionResult(section=section, review_state=state)


def get_section_display_payload(section_code: str, payload: dict) -> dict | list:
    return extract_section_payload(section_code, payload)
