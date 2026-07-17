"""Employee onboarding journal queries (WP-ONBOARDING-001)."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.employee_onboarding.domain.models import OnboardingListItemSnapshot

_ALLOWED_SORT = {
    "started_at_desc": "o.started_at DESC, o.onboarding_id DESC",
    "started_at_asc": "o.started_at ASC, o.onboarding_id ASC",
    "employee_name_asc": "LOWER(e.full_name) ASC, o.onboarding_id ASC",
    "status_asc": "o.status ASC, o.onboarding_id ASC",
}


def list_employee_onboardings(
    conn: Connection,
    *,
    q: str | None = None,
    status: str | None = None,
    org_unit_id: int | None = None,
    responsible_hr_id: int | None = None,
    sort: str = "started_at_desc",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[OnboardingListItemSnapshot], int]:
    where = ["1=1"]
    params: dict[str, Any] = {
        "limit": max(1, min(int(limit), 200)),
        "offset": max(0, int(offset)),
    }

    if q and str(q).strip():
        params["q"] = f"%{str(q).strip().lower()}%"
        where.append(
            "(LOWER(e.full_name) LIKE :q OR CAST(o.employee_id AS TEXT) LIKE :q "
            "OR CAST(o.onboarding_id AS TEXT) LIKE :q)"
        )
    if status and str(status).strip():
        params["status"] = str(status).strip()
        where.append("o.status = :status")
    if org_unit_id is not None:
        params["org_unit_id"] = int(org_unit_id)
        where.append("e.org_unit_id = :org_unit_id")
    if responsible_hr_id is not None:
        params["responsible_hr_id"] = int(responsible_hr_id)
        where.append("o.responsible_hr_id = :responsible_hr_id")

    where_sql = " AND ".join(where)
    order_sql = _ALLOWED_SORT.get(sort, _ALLOWED_SORT["started_at_desc"])

    total = int(
        conn.execute(
            text(
                f"""
                SELECT COUNT(*) AS cnt
                FROM public.employee_onboardings o
                JOIN public.employees e ON e.employee_id = o.employee_id
                WHERE {where_sql}
                """
            ),
            params,
        ).scalar_one()
    )

    rows = conn.execute(
        text(
            f"""
            SELECT
                o.onboarding_id,
                o.employee_id,
                o.application_id,
                o.status,
                o.started_at,
                o.planned_end_at,
                o.completed_at,
                o.responsible_hr_id,
                o.mentor_employee_id,
                e.full_name AS employee_full_name,
                ou.name AS org_unit_name,
                u.full_name AS responsible_hr_name,
                (
                    SELECT COUNT(*) FILTER (
                        WHERE ci.status IN ('completed', 'skipped')
                    )::float
                    / NULLIF(COUNT(*)::float, 0) * 100
                    FROM public.employee_onboarding_checklist_items ci
                    WHERE ci.onboarding_id = o.onboarding_id
                ) AS progress_raw
            FROM public.employee_onboardings o
            JOIN public.employees e ON e.employee_id = o.employee_id
            LEFT JOIN public.org_units ou ON ou.unit_id = e.org_unit_id
            LEFT JOIN public.users u ON u.user_id = o.responsible_hr_id
            WHERE {where_sql}
            ORDER BY {order_sql}
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()

    items = [
        OnboardingListItemSnapshot(
            onboarding_id=int(row["onboarding_id"]),
            employee_id=int(row["employee_id"]),
            application_id=int(row["application_id"]) if row.get("application_id") is not None else None,
            status=str(row["status"]),
            started_at=row["started_at"],
            planned_end_at=row.get("planned_end_at"),
            completed_at=row.get("completed_at"),
            responsible_hr_id=int(row["responsible_hr_id"]),
            mentor_employee_id=(
                int(row["mentor_employee_id"]) if row.get("mentor_employee_id") is not None else None
            ),
            progress_percent=int(round(float(row["progress_raw"] or 0))),
            employee_full_name=(
                str(row["employee_full_name"]).strip() if row.get("employee_full_name") else None
            ),
            org_unit_name=str(row["org_unit_name"]).strip() if row.get("org_unit_name") else None,
            responsible_hr_name=(
                str(row["responsible_hr_name"]).strip() if row.get("responsible_hr_name") else None
            ),
        )
        for row in rows
    ]
    return items, total
