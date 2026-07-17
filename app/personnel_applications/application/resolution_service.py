"""Director resolution workflow (WP-PPR-APPLICANT-002)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.engine import Connection

from app.personnel_applications.domain.errors import PersonnelApplicationResolutionError
from app.personnel_applications.domain.models import PersonnelApplicationSnapshot, ResolutionAuditSnapshot
from app.personnel_applications.domain.resolution_status import (
    RESOLUTION_ACTION_CHANGED,
    RESOLUTION_ACTION_OPENED,
    RESOLUTION_ACTION_RECORDED,
    RESOLUTION_ACTION_REOPENED,
    RESOLUTION_OUTCOME_APPROVED,
    RESOLUTION_OUTCOME_REJECTED,
    RESOLUTION_OUTCOME_REVISION_REQUESTED,
    RESOLUTION_OUTCOMES_REQUIRING_COMMENT,
)
from app.personnel_applications.domain.status import (
    APPLICATION_STATUS_APPROVED,
    APPLICATION_STATUS_REJECTED,
    APPLICATION_STATUS_RESOLUTION_PENDING,
    APPLICATION_STATUS_REVIEW_COMPLETED,
    APPLICATION_STATUS_REVISION_REQUESTED,
    DIRECTOR_RESOLUTION_PENDING,
)
from app.personnel_applications.infrastructure.repository import SqlAlchemyPersonnelApplicationRepository
from app.personnel_applications.infrastructure.resolution_repository import (
    SqlAlchemyPersonnelApplicationResolutionRepository,
)


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _require_comment(outcome: str, comment: str | None) -> str:
    text = str(comment or "").strip()
    if outcome in RESOLUTION_OUTCOMES_REQUIRING_COMMENT and not text:
        raise PersonnelApplicationResolutionError(
            f"Comment is required for resolution outcome '{outcome}'.",
            code="RESOLUTION_COMMENT_REQUIRED",
        )
    return text or ""


def _application_status_for_outcome(outcome: str) -> str:
    if outcome == RESOLUTION_OUTCOME_APPROVED:
        return APPLICATION_STATUS_APPROVED
    if outcome == RESOLUTION_OUTCOME_REJECTED:
        return APPLICATION_STATUS_REJECTED
    if outcome == RESOLUTION_OUTCOME_REVISION_REQUESTED:
        return APPLICATION_STATUS_REVISION_REQUESTED
    raise PersonnelApplicationResolutionError(
        f"Unsupported resolution outcome: {outcome}",
        code="RESOLUTION_OUTCOME_INVALID",
    )


@dataclass(frozen=True, slots=True)
class ResolutionActionResult:
    application: PersonnelApplicationSnapshot
    audit: ResolutionAuditSnapshot


def open_director_resolution(
    conn: Connection,
    *,
    application_id: int,
    actor_user_id: int,
) -> ResolutionActionResult:
    app_repo = SqlAlchemyPersonnelApplicationRepository(conn)
    audit_repo = SqlAlchemyPersonnelApplicationResolutionRepository(conn)
    app = app_repo.require_by_id(application_id)
    if app.status != APPLICATION_STATUS_REVIEW_COMPLETED:
        raise PersonnelApplicationResolutionError(
            f"Resolution can only be opened from review_completed (status={app.status}).",
            code="RESOLUTION_OPEN_NOT_ALLOWED",
        )
    now = _now_utc()
    updated = app_repo.update_application_fields(
        application_id,
        status=APPLICATION_STATUS_RESOLUTION_PENDING,
        director_resolution_status=DIRECTOR_RESOLUTION_PENDING,
        director_resolution_at=now,
        director_resolution_by_user_id=actor_user_id,
        director_resolution_note=None,
        now=now,
    )
    audit = audit_repo.append_audit(
        application_id=application_id,
        action=RESOLUTION_ACTION_OPENED,
        previous_application_status=app.status,
        new_application_status=updated.status,
        previous_resolution_status=app.director_resolution_status,
        new_resolution_status=updated.director_resolution_status,
        comment=None,
        actor_user_id=actor_user_id,
        created_at=now,
    )
    return ResolutionActionResult(application=updated, audit=audit)


def record_director_resolution(
    conn: Connection,
    *,
    application_id: int,
    outcome: str,
    comment: str | None,
    actor_user_id: int,
) -> ResolutionActionResult:
    normalized = str(outcome or "").strip().lower()
    comment_text = _require_comment(normalized, comment)
    app_repo = SqlAlchemyPersonnelApplicationRepository(conn)
    audit_repo = SqlAlchemyPersonnelApplicationResolutionRepository(conn)
    app = app_repo.require_by_id(application_id)
    if app.status != APPLICATION_STATUS_RESOLUTION_PENDING:
        raise PersonnelApplicationResolutionError(
            f"Resolution can only be recorded while pending (status={app.status}).",
            code="RESOLUTION_RECORD_NOT_ALLOWED",
        )
    new_status = _application_status_for_outcome(normalized)
    now = _now_utc()
    updated = app_repo.update_application_fields(
        application_id,
        status=new_status,
        director_resolution_status=normalized,
        director_resolution_at=now,
        director_resolution_by_user_id=actor_user_id,
        director_resolution_note=comment_text or None,
        now=now,
    )
    audit = audit_repo.append_audit(
        application_id=application_id,
        action=RESOLUTION_ACTION_RECORDED,
        previous_application_status=app.status,
        new_application_status=updated.status,
        previous_resolution_status=app.director_resolution_status,
        new_resolution_status=updated.director_resolution_status,
        comment=comment_text or None,
        actor_user_id=actor_user_id,
        created_at=now,
    )
    from app.personnel_applications.application.lifecycle_service import record_terminal_from_resolution

    record_terminal_from_resolution(
        conn,
        application_id=application_id,
        previous_status=app.status,
        new_status=updated.status,
        actor_user_id=actor_user_id,
        comment=comment_text or None,
    )
    return ResolutionActionResult(application=updated, audit=audit)


def change_director_resolution(
    conn: Connection,
    *,
    application_id: int,
    outcome: str,
    comment: str | None,
    actor_user_id: int,
) -> ResolutionActionResult:
    normalized = str(outcome or "").strip().lower()
    comment_text = _require_comment(normalized, comment)
    app_repo = SqlAlchemyPersonnelApplicationRepository(conn)
    audit_repo = SqlAlchemyPersonnelApplicationResolutionRepository(conn)
    app = app_repo.require_by_id(application_id)
    if app.status not in {
        APPLICATION_STATUS_APPROVED,
        APPLICATION_STATUS_REJECTED,
        APPLICATION_STATUS_REVISION_REQUESTED,
    }:
        raise PersonnelApplicationResolutionError(
            f"Resolution can only be changed after a decision (status={app.status}).",
            code="RESOLUTION_CHANGE_NOT_ALLOWED",
        )
    if app.director_resolution_status == normalized and (app.director_resolution_note or "") == comment_text:
        raise PersonnelApplicationResolutionError(
            "Resolution outcome and comment are unchanged.",
            code="RESOLUTION_UNCHANGED",
        )
    new_status = _application_status_for_outcome(normalized)
    now = _now_utc()
    updated = app_repo.update_application_fields(
        application_id,
        status=new_status,
        director_resolution_status=normalized,
        director_resolution_at=now,
        director_resolution_by_user_id=actor_user_id,
        director_resolution_note=comment_text or None,
        now=now,
    )
    audit = audit_repo.append_audit(
        application_id=application_id,
        action=RESOLUTION_ACTION_CHANGED,
        previous_application_status=app.status,
        new_application_status=updated.status,
        previous_resolution_status=app.director_resolution_status,
        new_resolution_status=updated.director_resolution_status,
        comment=comment_text or None,
        actor_user_id=actor_user_id,
        created_at=now,
    )
    from app.personnel_applications.application.lifecycle_service import record_terminal_from_resolution

    record_terminal_from_resolution(
        conn,
        application_id=application_id,
        previous_status=app.status,
        new_status=updated.status,
        actor_user_id=actor_user_id,
        comment=comment_text or None,
    )
    return ResolutionActionResult(application=updated, audit=audit)


def reopen_director_resolution(
    conn: Connection,
    *,
    application_id: int,
    actor_user_id: int,
) -> ResolutionActionResult:
    app_repo = SqlAlchemyPersonnelApplicationRepository(conn)
    audit_repo = SqlAlchemyPersonnelApplicationResolutionRepository(conn)
    app = app_repo.require_by_id(application_id)
    if app.status != APPLICATION_STATUS_REVISION_REQUESTED:
        raise PersonnelApplicationResolutionError(
            f"Resolution can only be reopened from revision_requested (status={app.status}).",
            code="RESOLUTION_REOPEN_NOT_ALLOWED",
        )
    now = _now_utc()
    updated = app_repo.update_application_fields(
        application_id,
        status=APPLICATION_STATUS_RESOLUTION_PENDING,
        director_resolution_status=DIRECTOR_RESOLUTION_PENDING,
        director_resolution_at=now,
        director_resolution_by_user_id=actor_user_id,
        director_resolution_note=None,
        now=now,
    )
    audit = audit_repo.append_audit(
        application_id=application_id,
        action=RESOLUTION_ACTION_REOPENED,
        previous_application_status=app.status,
        new_application_status=updated.status,
        previous_resolution_status=app.director_resolution_status,
        new_resolution_status=updated.director_resolution_status,
        comment=None,
        actor_user_id=actor_user_id,
        created_at=now,
    )
    return ResolutionActionResult(application=updated, audit=audit)


def list_resolution_audit(conn: Connection, application_id: int) -> list[ResolutionAuditSnapshot]:
    repo = SqlAlchemyPersonnelApplicationResolutionRepository(conn)
    return repo.list_audit(application_id)
