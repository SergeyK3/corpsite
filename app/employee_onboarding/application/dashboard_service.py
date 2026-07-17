"""Onboarding dashboard aggregates (WP-ONBOARDING-002)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.employee_onboarding.application.task_query_service import list_onboarding_tasks
from app.employee_onboarding.domain.models import OnboardingDashboardSnapshot


def load_onboarding_dashboard(conn: Connection) -> OnboardingDashboardSnapshot:
    now = datetime.now(UTC)
    due_soon_cutoff = now + timedelta(days=3)

    active_programs_count = int(
        conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.employee_onboardings
                WHERE status = 'active'
                """
            )
        ).scalar_one()
    )

    overdue_tasks_count = int(
        conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.employee_onboarding_checklist_items ci
                JOIN public.employee_onboardings o ON o.onboarding_id = ci.onboarding_id
                WHERE o.status = 'active'
                  AND ci.status = 'pending'
                  AND ci.due_date IS NOT NULL
                  AND ci.due_date < :now
                """
            ),
            {"now": now},
        ).scalar_one()
    )

    due_soon_tasks_count = int(
        conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.employee_onboarding_checklist_items ci
                JOIN public.employee_onboardings o ON o.onboarding_id = ci.onboarding_id
                WHERE o.status = 'active'
                  AND ci.status = 'pending'
                  AND ci.due_date IS NOT NULL
                  AND ci.due_date >= :now
                  AND ci.due_date <= :due_soon_cutoff
                """
            ),
            {"now": now, "due_soon_cutoff": due_soon_cutoff},
        ).scalar_one()
    )

    completion_row = conn.execute(
        text(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'completed') AS completed_count,
                COUNT(*) AS total_count
            FROM public.employee_onboardings
            WHERE status IN ('active', 'completed')
            """
        )
    ).mappings().one()
    completed_count = int(completion_row["completed_count"] or 0)
    total_count = int(completion_row["total_count"] or 0)
    completion_percent = int(round(completed_count * 100 / total_count)) if total_count else 0

    overdue_tasks, _ = list_onboarding_tasks(conn, overdue_only=True, limit=10, offset=0)
    due_soon_items, _ = list_onboarding_tasks(
        conn,
        status="pending",
        due_after=now.date(),
        due_before=due_soon_cutoff.date(),
        limit=10,
        offset=0,
    )

    return OnboardingDashboardSnapshot(
        active_programs_count=active_programs_count,
        overdue_tasks_count=overdue_tasks_count,
        due_soon_tasks_count=due_soon_tasks_count,
        completion_percent=completion_percent,
        overdue_tasks=tuple(overdue_tasks),
        due_soon_tasks=tuple(due_soon_items),
    )
