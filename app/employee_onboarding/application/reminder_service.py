"""Onboarding task reminder runner (WP-ONBOARDING-002).

Designed to be invoked by ops cron (mirrors regular-tasks pattern).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.employee_onboarding.application.notification_service import (
    notify_task_due_soon,
    notify_task_overdue,
)
from app.employee_onboarding.infrastructure.repository import SqlAlchemyEmployeeOnboardingRepository


@dataclass(frozen=True, slots=True)
class ReminderRunResult:
    due_soon_sent: int
    overdue_sent: int


def run_onboarding_reminders(conn: Connection, *, now: datetime | None = None) -> ReminderRunResult:
    effective_now = now or datetime.now(UTC)
    due_soon_cutoff = effective_now + timedelta(days=3)
    repo = SqlAlchemyEmployeeOnboardingRepository(conn)

    due_soon_item_ids = conn.execute(
        text(
            """
            SELECT ci.item_id
            FROM public.employee_onboarding_checklist_items ci
            JOIN public.employee_onboardings o ON o.onboarding_id = ci.onboarding_id
            WHERE o.status = 'active'
              AND ci.status = 'pending'
              AND ci.due_date IS NOT NULL
              AND ci.due_date >= :now
              AND ci.due_date <= :due_soon_cutoff
            """
        ),
        {"now": effective_now, "due_soon_cutoff": due_soon_cutoff},
    ).scalars().all()

    overdue_item_ids = conn.execute(
        text(
            """
            SELECT ci.item_id
            FROM public.employee_onboarding_checklist_items ci
            JOIN public.employee_onboardings o ON o.onboarding_id = ci.onboarding_id
            WHERE o.status = 'active'
              AND ci.status = 'pending'
              AND ci.due_date IS NOT NULL
              AND ci.due_date::date < (:now)::date
            """
        ),
        {"now": effective_now},
    ).scalars().all()

    due_soon_sent = 0
    for raw_item_id in due_soon_item_ids:
        item = repo.require_checklist_item(int(raw_item_id))
        onboarding = repo.require_by_id(item.onboarding_id)
        dedup_key = item.due_date.date().isoformat() if item.due_date else "unknown"
        notification_id = notify_task_due_soon(
            conn,
            onboarding=onboarding,
            item=item,
            dedup_key=dedup_key,
        )
        if notification_id is not None:
            due_soon_sent += 1

    overdue_sent = 0
    for raw_item_id in overdue_item_ids:
        item = repo.require_checklist_item(int(raw_item_id))
        onboarding = repo.require_by_id(item.onboarding_id)
        if item.due_date is None:
            continue
        dedup_key = item.due_date.date().isoformat()
        notification_id = notify_task_overdue(
            conn,
            onboarding=onboarding,
            item=item,
            dedup_key=dedup_key,
        )
        if notification_id is not None:
            overdue_sent += 1

    return ReminderRunResult(due_soon_sent=due_soon_sent, overdue_sent=overdue_sent)
