"""Enrich Personnel Application detail with display names."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.personnel_applications.domain.models import PersonnelApplicationSnapshot


def load_application_detail_enrichment(
    conn: Connection,
    snapshot: PersonnelApplicationSnapshot,
) -> dict[str, str | int | None]:
    row = conn.execute(
        text(
            """
            SELECT
                p.full_name,
                p.iin,
                dg.group_name AS intended_org_group_name,
                ou.name AS intended_org_unit_name,
                pos.name AS intended_position_name,
                u.full_name AS registered_by_name,
                ee.employee_id,
                e.full_name AS employee_full_name,
                ee.created_at AS hire_applied_at,
                po.order_number AS personnel_order_number,
                po.order_date AS personnel_order_date
            FROM public.persons p
            LEFT JOIN public.deps_group dg ON dg.group_id = :org_group_id
            LEFT JOIN public.org_units ou ON ou.unit_id = :org_unit_id
            LEFT JOIN public.positions pos ON pos.position_id = :position_id
            LEFT JOIN public.users u ON u.user_id = :registered_by_user_id
            LEFT JOIN public.personnel_orders po ON po.order_id = :personnel_order_id
            LEFT JOIN LATERAL (
                SELECT employee_id, created_at
                FROM public.employee_events
                WHERE order_id = :personnel_order_id
                  AND event_type = 'HIRE'
                ORDER BY event_id ASC
                LIMIT 1
            ) ee ON TRUE
            LEFT JOIN public.employees e ON e.employee_id = ee.employee_id
            WHERE p.person_id = :person_id
            LIMIT 1
            """
        ),
        {
            "person_id": snapshot.person_id,
            "org_group_id": snapshot.intended_org_group_id,
            "org_unit_id": snapshot.intended_org_unit_id,
            "position_id": snapshot.intended_position_id,
            "registered_by_user_id": snapshot.registered_by_user_id,
            "personnel_order_id": snapshot.personnel_order_id,
        },
    ).mappings().first()
    if row is None:
        return {
            "full_name": None,
            "iin": None,
            "intended_org_group_name": None,
            "intended_org_unit_name": None,
            "intended_position_name": None,
            "registered_by_name": None,
            "employee_id": None,
            "employee_full_name": None,
            "employee_created_at": None,
            "personnel_order_number": None,
            "personnel_order_date": None,
            "hire_applied_at": None,
        }
    return {
        "full_name": str(row["full_name"]).strip() if row.get("full_name") else None,
        "iin": str(row["iin"]).strip() if row.get("iin") else None,
        "intended_org_group_name": (
            str(row["intended_org_group_name"]).strip()
            if row.get("intended_org_group_name")
            else None
        ),
        "intended_org_unit_name": (
            str(row["intended_org_unit_name"]).strip()
            if row.get("intended_org_unit_name")
            else None
        ),
        "intended_position_name": (
            str(row["intended_position_name"]).strip()
            if row.get("intended_position_name")
            else None
        ),
        "registered_by_name": (
            str(row["registered_by_name"]).strip() if row.get("registered_by_name") else None
        ),
        "employee_id": int(row["employee_id"]) if row.get("employee_id") is not None else None,
        "employee_full_name": (
            str(row["employee_full_name"]).strip() if row.get("employee_full_name") else None
        ),
        "employee_created_at": row.get("hire_applied_at"),
        "personnel_order_number": (
            str(row["personnel_order_number"]).strip()
            if row.get("personnel_order_number")
            else None
        ),
        "personnel_order_date": row.get("personnel_order_date"),
        "hire_applied_at": row.get("hire_applied_at"),
    }


def load_application_lifecycle_fields(
    conn: Connection,
    application_id: int,
) -> dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT
                completed_at,
                closed_at,
                cancel_reason,
                cancelled_by_user_id,
                closed_by_user_id
            FROM public.personnel_applications
            WHERE application_id = :application_id
            LIMIT 1
            """
        ),
        {"application_id": int(application_id)},
    ).mappings().first()
    if row is None:
        return {
            "completed_at": None,
            "closed_at": None,
            "cancel_reason": None,
            "cancelled_by_user_id": None,
            "closed_by_user_id": None,
        }
    return {
        "completed_at": row.get("completed_at"),
        "closed_at": row.get("closed_at"),
        "cancel_reason": row.get("cancel_reason"),
        "cancelled_by_user_id": row.get("cancelled_by_user_id"),
        "closed_by_user_id": row.get("closed_by_user_id"),
    }
