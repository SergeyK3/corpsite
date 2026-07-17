"""Onboarding task notification helpers (WP-ONBOARDING-002)."""
from __future__ import annotations

from sqlalchemy.engine import Connection

from app.employee_onboarding.domain.models import (
    EmployeeOnboardingSnapshot,
    OnboardingChecklistItemSnapshot,
)
from app.employee_onboarding.domain.status import (
    NOTIFICATION_TASK_ASSIGNED,
    NOTIFICATION_TASK_COMPLETED,
    NOTIFICATION_TASK_DUE_SOON,
    NOTIFICATION_TASK_OVERDUE,
)
from app.employee_onboarding.infrastructure.notification_repository import create_onboarding_notification_tx
from app.employee_onboarding.infrastructure.repository import SqlAlchemyEmployeeOnboardingRepository


def _notification_payload(
    *,
    onboarding: EmployeeOnboardingSnapshot,
    item: OnboardingChecklistItemSnapshot,
) -> dict:
    return {
        "onboarding_id": onboarding.onboarding_id,
        "item_id": item.item_id,
        "item_title": item.title,
        "employee_id": onboarding.employee_id,
        "due_date": item.due_date.isoformat() if item.due_date else None,
        "priority": item.priority,
    }


def _resolve_recipients(
    conn: Connection,
    *,
    onboarding: EmployeeOnboardingSnapshot,
    item: OnboardingChecklistItemSnapshot,
) -> list[int]:
    repo = SqlAlchemyEmployeeOnboardingRepository(conn)
    uid = repo.resolve_assignee_user_id(onboarding=onboarding, item=item)
    return [uid] if uid is not None else []


def notify_task_assigned(
    conn: Connection,
    *,
    onboarding: EmployeeOnboardingSnapshot,
    item: OnboardingChecklistItemSnapshot,
    actor_user_id: int | None,
) -> int | None:
    recipients = _resolve_recipients(conn, onboarding=onboarding, item=item)
    return create_onboarding_notification_tx(
        conn,
        onboarding_id=onboarding.onboarding_id,
        item_id=item.item_id,
        event_type=NOTIFICATION_TASK_ASSIGNED,
        actor_user_id=actor_user_id,
        recipient_user_ids=recipients,
        payload=_notification_payload(onboarding=onboarding, item=item),
    )


def notify_task_completed(
    conn: Connection,
    *,
    onboarding: EmployeeOnboardingSnapshot,
    item: OnboardingChecklistItemSnapshot,
    actor_user_id: int | None,
) -> int | None:
    recipients = [int(onboarding.responsible_hr_id)]
    assignee_uid = _resolve_recipients(conn, onboarding=onboarding, item=item)
    recipients.extend(assignee_uid)
    return create_onboarding_notification_tx(
        conn,
        onboarding_id=onboarding.onboarding_id,
        item_id=item.item_id,
        event_type=NOTIFICATION_TASK_COMPLETED,
        actor_user_id=actor_user_id,
        recipient_user_ids=recipients,
        payload=_notification_payload(onboarding=onboarding, item=item),
    )


def notify_task_due_soon(
    conn: Connection,
    *,
    onboarding: EmployeeOnboardingSnapshot,
    item: OnboardingChecklistItemSnapshot,
    dedup_key: str,
) -> int | None:
    recipients = _resolve_recipients(conn, onboarding=onboarding, item=item)
    return create_onboarding_notification_tx(
        conn,
        onboarding_id=onboarding.onboarding_id,
        item_id=item.item_id,
        event_type=NOTIFICATION_TASK_DUE_SOON,
        actor_user_id=None,
        recipient_user_ids=recipients,
        payload=_notification_payload(onboarding=onboarding, item=item),
        dedup_key=dedup_key,
    )


def notify_task_overdue(
    conn: Connection,
    *,
    onboarding: EmployeeOnboardingSnapshot,
    item: OnboardingChecklistItemSnapshot,
    dedup_key: str,
) -> int | None:
    recipients = _resolve_recipients(conn, onboarding=onboarding, item=item)
    recipients.append(int(onboarding.responsible_hr_id))
    return create_onboarding_notification_tx(
        conn,
        onboarding_id=onboarding.onboarding_id,
        item_id=item.item_id,
        event_type=NOTIFICATION_TASK_OVERDUE,
        actor_user_id=None,
        recipient_user_ids=recipients,
        payload=_notification_payload(onboarding=onboarding, item=item),
        dedup_key=dedup_key,
    )
