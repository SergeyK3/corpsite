"""Onboarding task journal queries (WP-ONBOARDING-002)."""
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.employee_onboarding.domain.models import OnboardingTaskListItemSnapshot


def _row_to_task_item(row) -> OnboardingTaskListItemSnapshot:
    return OnboardingTaskListItemSnapshot(
        item_id=int(row["item_id"]),
        onboarding_id=int(row["onboarding_id"]),
        title=str(row["title"]),
        status=str(row["status"]),
        due_date=row.get("due_date"),
        priority=str(row.get("priority") or "normal"),
        assignee_kind=row.get("assignee_kind"),
        assignee_user_id=int(row["assignee_user_id"]) if row.get("assignee_user_id") is not None else None,
        assignee_employee_id=(
            int(row["assignee_employee_id"]) if row.get("assignee_employee_id") is not None else None
        ),
        assignee_name=str(row["assignee_name"]).strip() if row.get("assignee_name") else None,
        employee_id=int(row["employee_id"]),
        employee_full_name=str(row["employee_full_name"]).strip() if row.get("employee_full_name") else None,
        org_unit_name=str(row["org_unit_name"]).strip() if row.get("org_unit_name") else None,
        onboarding_status=str(row["onboarding_status"]),
        is_overdue=bool(row.get("is_overdue")),
    )


def list_onboarding_tasks(
    conn: Connection,
    *,
    q: str | None = None,
    status: str | None = None,
    org_unit_id: int | None = None,
    assignee_user_id: int | None = None,
    due_before: date | None = None,
    due_after: date | None = None,
    overdue_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[OnboardingTaskListItemSnapshot], int]:
    where = ["o.status = 'active'"]
    params: dict[str, Any] = {
        "limit": max(1, min(int(limit), 200)),
        "offset": max(0, int(offset)),
        "now": datetime.now(UTC),
    }

    if q and str(q).strip():
        params["q"] = f"%{str(q).strip().lower()}%"
        where.append(
            "(LOWER(e.full_name) LIKE :q OR CAST(e.employee_id AS TEXT) LIKE :q "
            "OR LOWER(ci.title) LIKE :q)"
        )
    if status and str(status).strip():
        params["status"] = str(status).strip()
        where.append("ci.status = :status")
    if org_unit_id is not None:
        params["org_unit_id"] = int(org_unit_id)
        where.append("e.org_unit_id = :org_unit_id")
    if assignee_user_id is not None:
        params["assignee_user_id"] = int(assignee_user_id)
        where.append(
            """
            (
                ci.assignee_user_id = :assignee_user_id
                OR (ci.assignee_kind = 'hr' AND o.responsible_hr_id = :assignee_user_id)
                OR (
                    ci.assignee_kind = 'mentor'
                    AND EXISTS (
                        SELECT 1 FROM public.users mu
                        WHERE mu.employee_id = o.mentor_employee_id
                          AND mu.user_id = :assignee_user_id
                    )
                )
                OR (
                    ci.assignee_kind = 'employee'
                    AND EXISTS (
                        SELECT 1 FROM public.users eu
                        WHERE eu.employee_id = ci.assignee_employee_id
                          AND eu.user_id = :assignee_user_id
                    )
                )
            )
            """
        )
    if due_before is not None:
        params["due_before"] = due_before
        where.append("ci.due_date IS NOT NULL AND ci.due_date::date <= :due_before")
    if due_after is not None:
        params["due_after"] = due_after
        where.append("ci.due_date IS NOT NULL AND ci.due_date::date >= :due_after")
    if overdue_only:
        where.append("ci.status = 'pending' AND ci.due_date IS NOT NULL AND ci.due_date < :now")

    where_sql = " AND ".join(where)
    base_from = f"""
        FROM public.employee_onboarding_checklist_items ci
        JOIN public.employee_onboardings o ON o.onboarding_id = ci.onboarding_id
        JOIN public.employees e ON e.employee_id = o.employee_id
        LEFT JOIN public.org_units ou ON ou.unit_id = e.org_unit_id
        LEFT JOIN public.users au ON au.user_id = ci.assignee_user_id
        LEFT JOIN public.employees ae ON ae.employee_id = ci.assignee_employee_id
        WHERE {where_sql}
    """

    total = int(
        conn.execute(
            text(f"SELECT COUNT(*) AS cnt {base_from}"),
            params,
        ).scalar_one()
    )

    rows = conn.execute(
        text(
            f"""
            SELECT
                ci.item_id,
                ci.onboarding_id,
                ci.title,
                ci.status,
                ci.due_date,
                ci.priority,
                ci.assignee_kind,
                ci.assignee_user_id,
                ci.assignee_employee_id,
                COALESCE(au.full_name, ae.full_name) AS assignee_name,
                o.employee_id,
                e.full_name AS employee_full_name,
                ou.name AS org_unit_name,
                o.status AS onboarding_status,
                (
                    ci.status = 'pending'
                    AND ci.due_date IS NOT NULL
                    AND ci.due_date < :now
                ) AS is_overdue
            {base_from}
            ORDER BY ci.due_date ASC NULLS LAST, ci.priority DESC, ci.item_id ASC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()

    return [_row_to_task_item(row) for row in rows], total
