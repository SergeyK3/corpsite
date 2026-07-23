"""HR editing of submitted intake draft on behalf of applicant."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from copy import deepcopy
from typing import Any

from sqlalchemy.engine import Connection

from app.personnel_applications.application.lifecycle_service import append_lifecycle_audit
from app.personnel_applications.domain.errors import PersonnelApplicationNotFoundError
from app.personnel_applications.domain.lifecycle_audit import LIFECYCLE_ACTION_INTAKE_EDITED_ON_BEHALF
from app.personnel_applications.infrastructure.repository import SqlAlchemyPersonnelApplicationRepository
from app.personnel_intake.application.intake_service import _validate_submit_payload
from app.personnel_intake.application.payload_diff import compute_intake_payload_field_changes
from app.personnel_intake.domain.errors import PersonnelIntakeNotFoundError, PersonnelIntakeOnBehalfEditError
from app.personnel_intake.domain.models import IntakeDraftSnapshot, IntakeLinkSnapshot
from app.personnel_intake.domain.on_behalf_edit import evaluate_on_behalf_edit_eligibility
from app.personnel_intake.domain.status import INTAKE_DRAFT_STATUS_SUBMITTED
from app.personnel_intake.infrastructure.repository import SqlAlchemyPersonnelIntakeRepository
from app.personnel_intake.infrastructure.review_repository import SqlAlchemyPersonnelIntakeReviewRepository


def _now_utc() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class OnBehalfEditSession:
    application_id: int
    draft: IntakeDraftSnapshot
    link: IntakeLinkSnapshot
    editable: bool
    blocked_reason: str | None
    reason_code: str | None


@dataclass(frozen=True, slots=True)
class SaveOnBehalfEditResult:
    application_id: int
    draft: IntakeDraftSnapshot
    saved_at: datetime
    changed_fields: tuple[str, ...]


def _load_eligibility_context(
    conn: Connection,
    application_id: int,
) -> tuple[str, IntakeDraftSnapshot | None, list[str]]:
    app_repo = SqlAlchemyPersonnelApplicationRepository(conn)
    app = app_repo.require_by_id(application_id)
    intake_repo = SqlAlchemyPersonnelIntakeRepository(conn)
    draft = intake_repo.get_draft_by_application_id(application_id)
    section_statuses: list[str] = []
    if draft is not None:
        review_repo = SqlAlchemyPersonnelIntakeReviewRepository(conn)
        sections = review_repo.list_section_reviews(application_id)
        section_statuses = [section.status for section in sections]
    return app.status, draft, section_statuses


def load_on_behalf_edit_session(conn: Connection, application_id: int) -> OnBehalfEditSession:
    status, draft, section_statuses = _load_eligibility_context(conn, application_id)

    if draft is None:
        _, blocked_reason, reason_code = evaluate_on_behalf_edit_eligibility(
            application_status=status,
            draft_exists=False,
            draft_submitted=False,
        )
        raise PersonnelIntakeNotFoundError("Intake draft not found.")

    allowed, blocked_reason, reason_code = evaluate_on_behalf_edit_eligibility(
        application_status=status,
        draft_exists=True,
        draft_submitted=draft.status == INTAKE_DRAFT_STATUS_SUBMITTED,
        section_statuses=section_statuses,
    )

    intake_repo = SqlAlchemyPersonnelIntakeRepository(conn)
    link = intake_repo.get_link_by_id(draft.link_id)
    if link is None:
        raise PersonnelIntakeNotFoundError("Intake link not found.")

    return OnBehalfEditSession(
        application_id=application_id,
        draft=draft,
        link=link,
        editable=allowed,
        blocked_reason=blocked_reason,
        reason_code=reason_code,
    )


def save_on_behalf_intake_draft(
    conn: Connection,
    *,
    application_id: int,
    payload: dict[str, Any],
    actor_user_id: int,
) -> SaveOnBehalfEditResult:
    session = load_on_behalf_edit_session(conn, application_id)
    if not session.editable:
        raise PersonnelIntakeOnBehalfEditError(
            session.blocked_reason or "On-behalf edit is not allowed.",
            code=session.reason_code or "EDIT_NOT_ALLOWED",
        )

    _validate_submit_payload(payload)

    now = _now_utc()
    before_payload = deepcopy(session.draft.payload)
    changed_fields = compute_intake_payload_field_changes(before_payload, payload)
    if not changed_fields:
        return SaveOnBehalfEditResult(
            application_id=application_id,
            draft=session.draft,
            saved_at=now,
            changed_fields=(),
        )

    intake_repo = SqlAlchemyPersonnelIntakeRepository(conn)
    updated = intake_repo.update_draft_payload(
        session.draft.draft_id,
        payload=payload,
        updated_at=now,
    )

    app_repo = SqlAlchemyPersonnelApplicationRepository(conn)
    app = app_repo.require_by_id(application_id)

    append_lifecycle_audit(
        conn,
        application_id=application_id,
        action=LIFECYCLE_ACTION_INTAKE_EDITED_ON_BEHALF,
        previous_status=app.status,
        new_status=app.status,
        actor_user_id=actor_user_id,
        comment="Анкета отредактирована HR от имени претендента",
        metadata={
            "on_behalf_of": "applicant",
            "actor_user_id": int(actor_user_id),
            "changed_fields": changed_fields,
            "edited_at": now.isoformat(),
        },
        created_at=now,
    )

    return SaveOnBehalfEditResult(
        application_id=application_id,
        draft=updated,
        saved_at=now,
        changed_fields=tuple(changed_fields),
    )
