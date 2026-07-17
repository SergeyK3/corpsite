"""Personnel Application lifecycle — cancel, expire, terminal closure (WP-PPR-APPLICANT-004)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.personnel_applications.application.envelope_projection import sync_envelope_intended_projection
from app.personnel_applications.domain.errors import PersonnelApplicationLifecycleError
from app.personnel_applications.domain.lifecycle_audit import (
    LIFECYCLE_ACTION_CANCELLED,
    LIFECYCLE_ACTION_COMPLETED,
    LIFECYCLE_ACTION_EXPIRED,
    LIFECYCLE_ACTION_REJECTED,
)
from app.personnel_applications.domain.models import LifecycleAuditSnapshot, PersonnelApplicationSnapshot
from app.personnel_applications.domain.status import (
    APPLICATION_STATUS_CANCELLED,
    APPLICATION_STATUS_COMPLETED,
    APPLICATION_STATUS_EXPIRED,
    APPLICATION_STATUS_REJECTED,
    APPLICATION_STATUS_RESOLUTION_REJECTED,
    is_terminal_application_status,
    terminal_statuses_for_partial_index,
)
from app.personnel_applications.infrastructure.lifecycle_repository import (
    SqlAlchemyPersonnelApplicationLifecycleRepository,
)
from app.personnel_applications.infrastructure.repository import SqlAlchemyPersonnelApplicationRepository
from app.personnel_intake.domain.status import INTAKE_DRAFT_STATUS_SUBMITTED, INTAKE_LINK_STATUS_SUBMITTED
from app.personnel_intake.infrastructure.repository import SqlAlchemyPersonnelIntakeRepository


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _terminal_status_sql() -> str:
    return ", ".join(f"'{s}'" for s in terminal_statuses_for_partial_index())


def _person_has_employee(conn: Connection, person_id: int) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM public.employees
            WHERE person_id = :person_id
            LIMIT 1
            """
        ),
        {"person_id": int(person_id)},
    ).first()
    return row is not None


def _order_has_hire_event(conn: Connection, order_id: int | None) -> bool:
    if order_id is None:
        return False
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM public.employee_events
            WHERE order_id = :order_id
              AND event_type = 'HIRE'
            LIMIT 1
            """
        ),
        {"order_id": int(order_id)},
    ).first()
    return row is not None


@dataclass(frozen=True, slots=True)
class CancelApplicationResult:
    application_id: int
    status: str
    closed_at: datetime
    audit: LifecycleAuditSnapshot


@dataclass(frozen=True, slots=True)
class ExpireApplicationsResult:
    expired_application_ids: tuple[int, ...]


def append_lifecycle_audit(
    conn: Connection,
    *,
    application_id: int,
    action: str,
    previous_status: str | None,
    new_status: str | None,
    comment: str | None = None,
    actor_user_id: int | None = None,
    metadata: dict | None = None,
    created_at: datetime | None = None,
) -> LifecycleAuditSnapshot:
    return SqlAlchemyPersonnelApplicationLifecycleRepository(conn).append_audit(
        application_id=application_id,
        action=action,
        previous_status=previous_status,
        new_status=new_status,
        comment=comment,
        actor_user_id=actor_user_id,
        metadata=metadata,
        created_at=created_at,
    )


def cancel_application(
    conn: Connection,
    *,
    application_id: int,
    reason: str,
    actor_user_id: int,
) -> CancelApplicationResult:
    cleaned_reason = str(reason or "").strip()
    if not cleaned_reason:
        raise PersonnelApplicationLifecycleError(
            "Cancel reason is required.",
            code="CANCEL_REASON_REQUIRED",
        )

    app_repo = SqlAlchemyPersonnelApplicationRepository(conn)
    app = app_repo.require_by_id(application_id)

    if is_terminal_application_status(app.status):
        raise PersonnelApplicationLifecycleError(
            f"Application is already terminal (status={app.status}).",
            code="APPLICATION_ALREADY_TERMINAL",
        )

    if _person_has_employee(conn, app.person_id):
        raise PersonnelApplicationLifecycleError(
            "Cannot cancel application after Employee was created.",
            code="EMPLOYEE_EXISTS",
        )

    if _order_has_hire_event(conn, app.personnel_order_id):
        raise PersonnelApplicationLifecycleError(
            "Cannot cancel application after HIRE order was applied.",
            code="HIRE_ALREADY_APPLIED",
        )

    now = _now_utc()
    _close_active_intake_link(conn, application_id=application_id, now=now)

    conn.execute(
        text(
            """
            UPDATE public.personnel_applications
            SET status = :status,
                updated_at = :updated_at,
                closed_at = :closed_at,
                cancel_reason = :cancel_reason,
                cancelled_by_user_id = :cancelled_by_user_id,
                closed_by_user_id = :closed_by_user_id
            WHERE application_id = :application_id
            """
        ),
        {
            "application_id": int(application_id),
            "status": APPLICATION_STATUS_CANCELLED,
            "updated_at": now,
            "closed_at": now,
            "cancel_reason": cleaned_reason,
            "cancelled_by_user_id": int(actor_user_id),
            "closed_by_user_id": int(actor_user_id),
        },
    )
    audit = append_lifecycle_audit(
        conn,
        application_id=application_id,
        action=LIFECYCLE_ACTION_CANCELLED,
        previous_status=app.status,
        new_status=APPLICATION_STATUS_CANCELLED,
        comment=cleaned_reason,
        actor_user_id=actor_user_id,
        created_at=now,
    )
    sync_envelope_intended_projection(conn, app.person_id)
    return CancelApplicationResult(
        application_id=application_id,
        status=APPLICATION_STATUS_CANCELLED,
        closed_at=now,
        audit=audit,
    )


def _close_active_intake_link(
    conn: Connection,
    *,
    application_id: int,
    now: datetime,
) -> None:
    intake_repo = SqlAlchemyPersonnelIntakeRepository(conn)
    link = intake_repo.get_active_link_for_application(application_id)
    if link is None:
        return
    if link.status == INTAKE_LINK_STATUS_SUBMITTED:
        return
    intake_repo.mark_link_expired(link.link_id, expired_at=now)


def expire_due_applications(conn: Connection, *, now: datetime | None = None) -> ExpireApplicationsResult:
    """Expire active applications whose intake link passed TTL without submission."""
    effective_now = now or _now_utc()
    terminal_sql = _terminal_status_sql()

    rows = conn.execute(
        text(
            f"""
            SELECT
                pa.application_id,
                pa.status,
                pa.person_id,
                l.link_id,
                d.status AS draft_status
            FROM public.personnel_applications pa
            JOIN public.personnel_intake_links l
              ON l.application_id = pa.application_id
            LEFT JOIN public.personnel_intake_drafts d
              ON d.application_id = pa.application_id
             AND d.link_id = l.link_id
            WHERE pa.status NOT IN ({terminal_sql})
              AND l.expires_at <= :now
              AND l.status IN ('issued', 'opened')
              AND COALESCE(d.status, 'draft') <> :submitted_draft
            ORDER BY pa.application_id ASC
            """
        ),
        {
            "now": effective_now,
            "submitted_draft": INTAKE_DRAFT_STATUS_SUBMITTED,
        },
    ).mappings().all()

    expired_ids: list[int] = []
    intake_repo = SqlAlchemyPersonnelIntakeRepository(conn)
    for row in rows:
        application_id = int(row["application_id"])
        previous_status = str(row["status"])
        link_id = int(row["link_id"])
        intake_repo.mark_link_expired(link_id, expired_at=effective_now)
        conn.execute(
            text(
                """
                UPDATE public.personnel_applications
                SET status = :status,
                    updated_at = :updated_at,
                    closed_at = :closed_at
                WHERE application_id = :application_id
                  AND status = :previous_status
                """
            ),
            {
                "application_id": application_id,
                "status": APPLICATION_STATUS_EXPIRED,
                "updated_at": effective_now,
                "closed_at": effective_now,
                "previous_status": previous_status,
            },
        )
        append_lifecycle_audit(
            conn,
            application_id=application_id,
            action=LIFECYCLE_ACTION_EXPIRED,
            previous_status=previous_status,
            new_status=APPLICATION_STATUS_EXPIRED,
            comment="Intake link expired without submission.",
            actor_user_id=None,
            created_at=effective_now,
        )
        sync_envelope_intended_projection(conn, int(row["person_id"]))
        expired_ids.append(application_id)

    return ExpireApplicationsResult(expired_application_ids=tuple(expired_ids))


def record_terminal_from_resolution(
    conn: Connection,
    *,
    application_id: int,
    previous_status: str,
    new_status: str,
    actor_user_id: int,
    comment: str | None = None,
) -> None:
    if new_status not in {
        APPLICATION_STATUS_REJECTED,
        APPLICATION_STATUS_RESOLUTION_REJECTED,
    }:
        return
    now = _now_utc()
    conn.execute(
        text(
            """
            UPDATE public.personnel_applications
            SET closed_at = COALESCE(closed_at, :closed_at),
                closed_by_user_id = COALESCE(closed_by_user_id, :closed_by_user_id)
            WHERE application_id = :application_id
            """
        ),
        {
            "application_id": int(application_id),
            "closed_at": now,
            "closed_by_user_id": int(actor_user_id),
        },
    )
    append_lifecycle_audit(
        conn,
        application_id=application_id,
        action=LIFECYCLE_ACTION_REJECTED,
        previous_status=previous_status,
        new_status=new_status,
        comment=comment,
        actor_user_id=actor_user_id,
        created_at=now,
    )


def record_completed_from_apply(
    conn: Connection,
    *,
    application_id: int,
    previous_status: str,
    actor_user_id: int,
    employee_id: int,
    personnel_order_id: int,
) -> None:
    now = _now_utc()
    conn.execute(
        text(
            """
            UPDATE public.personnel_applications
            SET completed_at = COALESCE(completed_at, :completed_at),
                closed_at = COALESCE(closed_at, :closed_at),
                closed_by_user_id = COALESCE(closed_by_user_id, :closed_by_user_id)
            WHERE application_id = :application_id
            """
        ),
        {
            "application_id": int(application_id),
            "completed_at": now,
            "closed_at": now,
            "closed_by_user_id": int(actor_user_id),
        },
    )
    append_lifecycle_audit(
        conn,
        application_id=application_id,
        action=LIFECYCLE_ACTION_COMPLETED,
        previous_status=previous_status,
        new_status=APPLICATION_STATUS_COMPLETED,
        actor_user_id=actor_user_id,
        metadata={
            "employee_id": int(employee_id),
            "personnel_order_id": int(personnel_order_id),
        },
        created_at=now,
    )
