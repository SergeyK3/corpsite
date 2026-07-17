"""Build personnel application lifecycle timeline (WP-PPR-APPLICANT-004)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.personnel_applications.domain.lifecycle_audit import (
    LIFECYCLE_ACTION_CANCELLED,
    LIFECYCLE_ACTION_COMPLETED,
    LIFECYCLE_ACTION_EXPIRED,
    LIFECYCLE_ACTION_HIRE_APPLIED,
    LIFECYCLE_ACTION_HIRE_ORDER_DRAFT_CREATED,
    LIFECYCLE_ACTION_INTAKE_LINK_ISSUED,
    LIFECYCLE_ACTION_INTAKE_OPENED,
    LIFECYCLE_ACTION_INTAKE_SUBMITTED,
    LIFECYCLE_ACTION_INTAKE_TRANSFERRED,
    LIFECYCLE_ACTION_REGISTERED,
    LIFECYCLE_ACTION_REJECTED,
    LIFECYCLE_ACTION_RESOLUTION_CHANGED,
    LIFECYCLE_ACTION_RESOLUTION_OPENED,
    LIFECYCLE_ACTION_RESOLUTION_RECORDED,
    LIFECYCLE_ACTION_RESOLUTION_REOPENED,
    LIFECYCLE_ACTION_REVIEW_COMPLETED,
    LIFECYCLE_ACTION_REVIEW_STARTED,
)
from app.personnel_applications.domain.models import TimelineEvent
from app.personnel_applications.infrastructure.lifecycle_repository import (
    SqlAlchemyPersonnelApplicationLifecycleRepository,
)
from app.personnel_applications.infrastructure.repository import SqlAlchemyPersonnelApplicationRepository
from app.personnel_applications.infrastructure.resolution_repository import (
    SqlAlchemyPersonnelApplicationResolutionRepository,
)
from app.personnel_intake.infrastructure.repository import SqlAlchemyPersonnelIntakeRepository

_TIMELINE_LABELS: dict[str, str] = {
    LIFECYCLE_ACTION_REGISTERED: "Регистрация обращения",
    LIFECYCLE_ACTION_INTAKE_LINK_ISSUED: "Выдана ссылка на анкету",
    LIFECYCLE_ACTION_INTAKE_OPENED: "Анкета открыта претендентом",
    LIFECYCLE_ACTION_INTAKE_SUBMITTED: "Анкета отправлена",
    LIFECYCLE_ACTION_REVIEW_STARTED: "Начата проверка HR",
    LIFECYCLE_ACTION_REVIEW_COMPLETED: "Проверка завершена",
    LIFECYCLE_ACTION_INTAKE_TRANSFERRED: "Данные перенесены в PPR",
    LIFECYCLE_ACTION_RESOLUTION_OPENED: "Открыта резолюция директора",
    LIFECYCLE_ACTION_RESOLUTION_RECORDED: "Зафиксирована резолюция директора",
    LIFECYCLE_ACTION_RESOLUTION_CHANGED: "Изменена резолюция директора",
    LIFECYCLE_ACTION_RESOLUTION_REOPENED: "Резолюция возобновлена",
    LIFECYCLE_ACTION_HIRE_ORDER_DRAFT_CREATED: "Создан черновик приказа о приёме",
    LIFECYCLE_ACTION_HIRE_APPLIED: "Применён приказ о приёме",
    LIFECYCLE_ACTION_COMPLETED: "Принят на работу",
    LIFECYCLE_ACTION_REJECTED: "Отказ",
    LIFECYCLE_ACTION_CANCELLED: "Обращение отменено",
    LIFECYCLE_ACTION_EXPIRED: "Срок анкеты истёк",
    "resolution_opened": "Открыта резолюция директора",
    "resolution_recorded": "Зафиксирована резолюция директора",
    "resolution_changed": "Изменена резолюция директора",
    "resolution_reopened": "Резолюция возобновлена",
}


def _label(code: str) -> str:
    return _TIMELINE_LABELS.get(code, code)


def _append_event(
    events: list[TimelineEvent],
    *,
    code: str,
    occurred_at: datetime | None,
    actor_user_id: int | None = None,
    detail: str | None = None,
    metadata: dict | None = None,
) -> None:
    if occurred_at is None:
        return
    events.append(
        TimelineEvent(
            code=code,
            label=_label(code),
            occurred_at=occurred_at,
            actor_user_id=actor_user_id,
            detail=detail,
            metadata=metadata,
        )
    )


def build_application_timeline(conn: Connection, application_id: int) -> list[TimelineEvent]:
    app_repo = SqlAlchemyPersonnelApplicationRepository(conn)
    app = app_repo.require_by_id(application_id)
    events: list[TimelineEvent] = []

    _append_event(
        events,
        code=LIFECYCLE_ACTION_REGISTERED,
        occurred_at=app.registered_at,
        actor_user_id=app.registered_by_user_id,
    )

    intake_repo = SqlAlchemyPersonnelIntakeRepository(conn)
    summary = intake_repo.load_intake_summary(application_id)
    if summary is not None:
        if summary.issued_at:
            _append_event(
                events,
                code=LIFECYCLE_ACTION_INTAKE_LINK_ISSUED,
                occurred_at=summary.issued_at,
            )
        if summary.opened_at:
            _append_event(
                events,
                code=LIFECYCLE_ACTION_INTAKE_OPENED,
                occurred_at=summary.opened_at,
            )
        if summary.submitted_at:
            _append_event(
                events,
                code=LIFECYCLE_ACTION_INTAKE_SUBMITTED,
                occurred_at=summary.submitted_at,
            )

    review_rows = conn.execute(
        text(
            """
            SELECT MIN(reviewed_at) AS first_review_at, MAX(reviewed_at) AS last_review_at
            FROM public.personnel_intake_section_reviews
            WHERE application_id = :application_id
              AND reviewed_at IS NOT NULL
            """
        ),
        {"application_id": int(application_id)},
    ).mappings().first()
    if review_rows:
        _append_event(
            events,
            code=LIFECYCLE_ACTION_REVIEW_STARTED,
            occurred_at=review_rows.get("first_review_at"),
        )

    transfer_row = conn.execute(
        text(
            """
            SELECT transferred_at, transferred_by_user_id, status, result
            FROM public.personnel_intake_transfers
            WHERE application_id = :application_id
              AND status = 'completed'
            ORDER BY transferred_at DESC NULLS LAST, transfer_id DESC
            LIMIT 1
            """
        ),
        {"application_id": int(application_id)},
    ).mappings().first()
    if transfer_row and transfer_row.get("transferred_at"):
        _append_event(
            events,
            code=LIFECYCLE_ACTION_INTAKE_TRANSFERRED,
            occurred_at=transfer_row["transferred_at"],
            actor_user_id=transfer_row.get("transferred_by_user_id"),
            detail=str(transfer_row.get("result") or "") or None,
        )
        _append_event(
            events,
            code=LIFECYCLE_ACTION_REVIEW_COMPLETED,
            occurred_at=transfer_row["transferred_at"],
            actor_user_id=transfer_row.get("transferred_by_user_id"),
        )

    for audit in SqlAlchemyPersonnelApplicationResolutionRepository(conn).list_audit(application_id):
        _append_event(
            events,
            code=f"resolution_{audit.action}",
            occurred_at=audit.created_at,
            actor_user_id=audit.actor_user_id,
            detail=audit.comment,
            metadata={
                "new_application_status": audit.new_application_status,
                "new_resolution_status": audit.new_resolution_status,
            },
        )

    if app.personnel_order_id is not None:
        order_row = conn.execute(
            text(
                """
                SELECT order_id, created_at
                FROM public.personnel_orders
                WHERE order_id = :order_id
                LIMIT 1
                """
            ),
            {"order_id": int(app.personnel_order_id)},
        ).mappings().first()
        if order_row:
            _append_event(
                events,
                code=LIFECYCLE_ACTION_HIRE_ORDER_DRAFT_CREATED,
                occurred_at=order_row.get("created_at"),
                metadata={"personnel_order_id": int(app.personnel_order_id)},
            )

        hire_event = conn.execute(
            text(
                """
                SELECT employee_id, created_at, created_by
                FROM public.employee_events
                WHERE order_id = :order_id
                  AND event_type = 'HIRE'
                ORDER BY event_id ASC
                LIMIT 1
                """
            ),
            {"order_id": int(app.personnel_order_id)},
        ).mappings().first()
        if hire_event:
            _append_event(
                events,
                code=LIFECYCLE_ACTION_HIRE_APPLIED,
                occurred_at=hire_event.get("created_at"),
                actor_user_id=hire_event.get("created_by"),
                metadata={
                    "employee_id": int(hire_event["employee_id"]),
                    "personnel_order_id": int(app.personnel_order_id),
                },
            )

    lifecycle_repo = SqlAlchemyPersonnelApplicationLifecycleRepository(conn)
    for audit in lifecycle_repo.list_audit(application_id, limit=200):
        _append_event(
            events,
            code=audit.action,
            occurred_at=audit.created_at,
            actor_user_id=audit.actor_user_id,
            detail=audit.comment,
            metadata=audit.metadata,
        )

    lifecycle_row = conn.execute(
        text(
            """
            SELECT completed_at, closed_at, cancel_reason, status
            FROM public.personnel_applications
            WHERE application_id = :application_id
            LIMIT 1
            """
        ),
        {"application_id": int(application_id)},
    ).mappings().first()
    if lifecycle_row:
        status = str(lifecycle_row.get("status") or app.status)
        if status == "completed" and lifecycle_row.get("completed_at"):
            _append_event(
                events,
                code=LIFECYCLE_ACTION_COMPLETED,
                occurred_at=lifecycle_row["completed_at"],
            )
        elif status in {"rejected", "resolution_rejected"} and lifecycle_row.get("closed_at"):
            _append_event(
                events,
                code=LIFECYCLE_ACTION_REJECTED,
                occurred_at=lifecycle_row["closed_at"],
            )
        elif status == "cancelled" and lifecycle_row.get("closed_at"):
            _append_event(
                events,
                code=LIFECYCLE_ACTION_CANCELLED,
                occurred_at=lifecycle_row["closed_at"],
                detail=lifecycle_row.get("cancel_reason"),
            )
        elif status == "expired" and lifecycle_row.get("closed_at"):
            _append_event(
                events,
                code=LIFECYCLE_ACTION_EXPIRED,
                occurred_at=lifecycle_row["closed_at"],
            )

    events.sort(key=lambda item: (item.occurred_at, item.code))
    return _dedupe_timeline(events)


def _dedupe_timeline(events: list[TimelineEvent]) -> list[TimelineEvent]:
    seen: set[tuple[str, datetime, str | None]] = set()
    unique: list[TimelineEvent] = []
    for event in events:
        key = (event.code, event.occurred_at, event.detail)
        if key in seen:
            continue
        seen.add(key)
        unique.append(event)
    return unique


def list_combined_audit(conn: Connection, application_id: int) -> list[dict]:
    """Merge lifecycle and resolution audit for archive detail view."""
    lifecycle = SqlAlchemyPersonnelApplicationLifecycleRepository(conn).list_audit(application_id)
    resolution = SqlAlchemyPersonnelApplicationResolutionRepository(conn).list_audit(application_id)
    combined: list[dict] = []
    for item in lifecycle:
        combined.append(
            {
                "source": "lifecycle",
                "audit_id": item.audit_id,
                "action": item.action,
                "previous_status": item.previous_status,
                "new_status": item.new_status,
                "comment": item.comment,
                "actor_user_id": item.actor_user_id,
                "metadata": item.metadata,
                "created_at": item.created_at,
            }
        )
    for item in resolution:
        combined.append(
            {
                "source": "resolution",
                "audit_id": item.audit_id,
                "action": item.action,
                "previous_status": item.previous_application_status,
                "new_status": item.new_application_status,
                "comment": item.comment,
                "actor_user_id": item.actor_user_id,
                "metadata": {
                    "previous_resolution_status": item.previous_resolution_status,
                    "new_resolution_status": item.new_resolution_status,
                },
                "created_at": item.created_at,
            }
        )
    combined.sort(key=lambda row: row["created_at"], reverse=True)
    return combined
