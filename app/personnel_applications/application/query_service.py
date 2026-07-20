"""Personnel Application journal query service (WP-PPR-APPLICANT-001C, 004 archive)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.personnel_applications.domain.lifecycle_audit import (
    JOURNAL_VIEW_ACTIVE,
    JOURNAL_VIEW_ARCHIVE,
    JOURNAL_VIEWS,
)
from app.personnel_applications.domain.status import terminal_statuses_for_partial_index
from app.personnel_intake.application.hr_link_access_service import batch_hr_intake_link_displays
from app.personnel_intake.infrastructure.repository import SqlAlchemyPersonnelIntakeRepository

_TERMINAL_SQL = ", ".join(f"'{s}'" for s in terminal_statuses_for_partial_index())

_ALLOWED_SORT = {
    "application_received_at_desc": "pa.application_received_at DESC, pa.application_id DESC",
    "application_received_at_asc": "pa.application_received_at ASC, pa.application_id ASC",
    "registered_at_desc": "pa.registered_at DESC, pa.application_id DESC",
    "registered_at_asc": "pa.registered_at ASC, pa.application_id ASC",
    "closed_at_desc": "pa.closed_at DESC NULLS LAST, pa.application_id DESC",
    "closed_at_asc": "pa.closed_at ASC NULLS LAST, pa.application_id ASC",
    "full_name_asc": "LOWER(p.full_name) ASC, pa.application_id ASC",
    "full_name_desc": "LOWER(p.full_name) DESC, pa.application_id DESC",
    "status_asc": "pa.status ASC, pa.application_id ASC",
    "status_desc": "pa.status DESC, pa.application_id DESC",
}


@dataclass(frozen=True, slots=True)
class PersonnelApplicationListItem:
    application_id: int
    person_id: int
    full_name: str | None
    iin: str | None
    status: str
    application_received_at: Any
    intended_org_group_id: int | None
    intended_org_unit_id: int | None
    intended_position_id: int | None
    intended_org_group_name: str | None
    intended_org_unit_name: str | None
    intended_position_name: str | None
    registered_at: Any
    registered_by_user_id: int
    registered_by_name: str | None
    director_resolution_status: str | None
    personnel_order_id: int | None
    is_active: bool
    employee_id: int | None = None
    employee_full_name: str | None = None
    completed_at: Any | None = None
    closed_at: Any | None = None
    intake_link_status: str | None = None
    intake_draft_status: str | None = None
    intake_opened_at: Any | None = None
    intake_submitted_at: Any | None = None
    intake_link_display_state: str | None = None
    intake_url_path: str | None = None


def list_personnel_applications(
    conn: Connection,
    *,
    q: str | None = None,
    status: str | None = None,
    view: str = JOURNAL_VIEW_ACTIVE,
    org_group_id: int | None = None,
    org_unit_id: int | None = None,
    position_id: int | None = None,
    sort: str = "application_received_at_desc",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PersonnelApplicationListItem], int]:
    journal_view = str(view or JOURNAL_VIEW_ACTIVE).strip()
    if journal_view not in JOURNAL_VIEWS:
        journal_view = JOURNAL_VIEW_ACTIVE

    where = ["1=1"]
    params: dict[str, Any] = {
        "limit": max(1, min(int(limit), 200)),
        "offset": max(0, int(offset)),
    }

    if journal_view == JOURNAL_VIEW_ARCHIVE:
        where.append(f"pa.status IN ({_TERMINAL_SQL})")
    else:
        where.append(f"pa.status NOT IN ({_TERMINAL_SQL})")

    if q and str(q).strip():
        params["q"] = f"%{str(q).strip().lower()}%"
        where.append(
            "(LOWER(p.full_name) LIKE :q OR LOWER(COALESCE(p.iin, '')) LIKE :q "
            "OR CAST(pa.application_id AS TEXT) LIKE :q OR CAST(p.person_id AS TEXT) LIKE :q)"
        )
    if status and str(status).strip():
        params["status"] = str(status).strip()
        where.append("pa.status = :status")
    if org_group_id is not None:
        params["org_group_id"] = int(org_group_id)
        where.append("pa.intended_org_group_id = :org_group_id")
    if org_unit_id is not None:
        params["org_unit_id"] = int(org_unit_id)
        where.append("pa.intended_org_unit_id = :org_unit_id")
    if position_id is not None:
        params["position_id"] = int(position_id)
        where.append("pa.intended_position_id = :position_id")

    order_sql = _ALLOWED_SORT.get(sort, _ALLOWED_SORT["application_received_at_desc"])
    where_sql = " AND ".join(where)

    total = int(
        conn.execute(
            text(
                f"""
                SELECT COUNT(*) AS cnt
                FROM public.personnel_applications pa
                JOIN public.persons p ON p.person_id = pa.person_id
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
                pa.application_id,
                pa.person_id,
                p.full_name,
                p.iin,
                pa.status,
                pa.application_received_at,
                pa.intended_org_group_id,
                pa.intended_org_unit_id,
                pa.intended_position_id,
                dg.group_name AS intended_org_group_name,
                ou.name AS intended_org_unit_name,
                pos.name AS intended_position_name,
                pa.registered_at,
                pa.registered_by_user_id,
                u.full_name AS registered_by_name,
                pa.director_resolution_status,
                pa.personnel_order_id,
                pa.completed_at,
                pa.closed_at,
                ee.employee_id,
                e.full_name AS employee_full_name,
                CASE
                    WHEN pa.status IN ({_TERMINAL_SQL}) THEN FALSE
                    ELSE TRUE
                END AS is_active
            FROM public.personnel_applications pa
            JOIN public.persons p ON p.person_id = pa.person_id
            LEFT JOIN public.deps_group dg ON dg.group_id = pa.intended_org_group_id
            LEFT JOIN public.org_units ou ON ou.unit_id = pa.intended_org_unit_id
            LEFT JOIN public.positions pos ON pos.position_id = pa.intended_position_id
            LEFT JOIN public.users u ON u.user_id = pa.registered_by_user_id
            LEFT JOIN LATERAL (
                SELECT employee_id
                FROM public.employee_events
                WHERE order_id = pa.personnel_order_id
                  AND event_type = 'HIRE'
                ORDER BY event_id ASC
                LIMIT 1
            ) ee ON pa.personnel_order_id IS NOT NULL
            LEFT JOIN public.employees e ON e.employee_id = ee.employee_id
            WHERE {where_sql}
            ORDER BY {order_sql}
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()

    items = [
        PersonnelApplicationListItem(
            application_id=int(row["application_id"]),
            person_id=int(row["person_id"]),
            full_name=str(row["full_name"]).strip() if row.get("full_name") else None,
            iin=str(row["iin"]).strip() if row.get("iin") else None,
            status=str(row["status"]),
            application_received_at=row["application_received_at"],
            intended_org_group_id=(
                int(row["intended_org_group_id"])
                if row.get("intended_org_group_id") is not None
                else None
            ),
            intended_org_unit_id=(
                int(row["intended_org_unit_id"])
                if row.get("intended_org_unit_id") is not None
                else None
            ),
            intended_position_id=(
                int(row["intended_position_id"])
                if row.get("intended_position_id") is not None
                else None
            ),
            intended_org_group_name=(
                str(row["intended_org_group_name"]).strip()
                if row.get("intended_org_group_name")
                else None
            ),
            intended_org_unit_name=(
                str(row["intended_org_unit_name"]).strip()
                if row.get("intended_org_unit_name")
                else None
            ),
            intended_position_name=(
                str(row["intended_position_name"]).strip()
                if row.get("intended_position_name")
                else None
            ),
            registered_at=row["registered_at"],
            registered_by_user_id=int(row["registered_by_user_id"]),
            registered_by_name=(
                str(row["registered_by_name"]).strip() if row.get("registered_by_name") else None
            ),
            director_resolution_status=(
                str(row["director_resolution_status"])
                if row.get("director_resolution_status") is not None
                else None
            ),
            personnel_order_id=(
                int(row["personnel_order_id"])
                if row.get("personnel_order_id") is not None
                else None
            ),
            is_active=bool(row["is_active"]),
            employee_id=int(row["employee_id"]) if row.get("employee_id") is not None else None,
            employee_full_name=(
                str(row["employee_full_name"]).strip() if row.get("employee_full_name") else None
            ),
            completed_at=row.get("completed_at"),
            closed_at=row.get("closed_at"),
        )
        for row in rows
    ]

    app_ids = [item.application_id for item in items]
    intake_repo = SqlAlchemyPersonnelIntakeRepository(conn)
    summaries = intake_repo.load_intake_summaries(app_ids)
    link_displays = batch_hr_intake_link_displays(conn, app_ids)
    enriched: list[PersonnelApplicationListItem] = []
    for item in items:
        summary = summaries.get(item.application_id)
        link_display = link_displays.get(item.application_id)
        if summary is None and link_display is None:
            enriched.append(item)
            continue
        enriched.append(
            PersonnelApplicationListItem(
                application_id=item.application_id,
                person_id=item.person_id,
                full_name=item.full_name,
                iin=item.iin,
                status=item.status,
                application_received_at=item.application_received_at,
                intended_org_group_id=item.intended_org_group_id,
                intended_org_unit_id=item.intended_org_unit_id,
                intended_position_id=item.intended_position_id,
                intended_org_group_name=item.intended_org_group_name,
                intended_org_unit_name=item.intended_org_unit_name,
                intended_position_name=item.intended_position_name,
                registered_at=item.registered_at,
                registered_by_user_id=item.registered_by_user_id,
                registered_by_name=item.registered_by_name,
                director_resolution_status=item.director_resolution_status,
                personnel_order_id=item.personnel_order_id,
                is_active=item.is_active,
                employee_id=item.employee_id,
                employee_full_name=item.employee_full_name,
                completed_at=item.completed_at,
                closed_at=item.closed_at,
                intake_link_status=summary.link_status if summary else None,
                intake_draft_status=summary.draft_status if summary else None,
                intake_opened_at=summary.opened_at if summary else None,
                intake_submitted_at=summary.submitted_at if summary else None,
                intake_link_display_state=link_display.display_state if link_display else None,
                intake_url_path=link_display.intake_url_path if link_display else None,
            )
        )
    return enriched, total
