"""Employee-level personnel actions from the same linked orders as the self cabinet."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import text

from app.services.personnel_orders_summary_report_service import STATUS_LABELS, _type_label


_ACTION_LABELS = {
    "PERSONAL_DATA_CHANGE": "Изменение персональных данных",
    "EDUCATION_INFORMATION_CHANGE": "Сведения об образовании",
    "SERVICE_LENGTH_CHANGE": "Изменение стажа",
    "QUALIFICATION_CATEGORY": "Квалификационная категория",
    "SUPPLEMENTARY_PAY": "Доплата",
    "RETURN_FROM_CHILDCARE_LEAVE": "Выход из отпуска по уходу за ребёнком",
}


def _iso_date(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value) if value is not None else None


def _actions(counts: dict[str, int]) -> list[dict[str, Any]]:
    return [
        {"code": code, "label": _ACTION_LABELS.get(code, _type_label(code)), "count": count}
        for code, count in sorted(counts.items())
    ]


def build_personnel_employee_actions_report(db_engine: Any) -> dict[str, Any]:
    """Return every active employee and all linked signed/registered item rows.

    One unpaginated query supplies both totals and drill-down.  A left join
    preserves employees without orders; item text and other document content
    are unnecessary for this report.
    """
    statement = text("""
        WITH active_employees AS (
            SELECT e.employee_id,
                   COALESCE(NULLIF(BTRIM(p.full_name), ''), NULLIF(BTRIM(e.full_name), '')) AS full_name,
                   ou.unit_id AS org_unit_id, ou.name AS org_unit_name
            FROM public.employees e
            LEFT JOIN public.persons p ON p.person_id = e.person_id
            LEFT JOIN LATERAL (
                SELECT pa.org_unit_id
                FROM public.person_assignments pa
                WHERE pa.person_id = e.person_id
                  AND pa.active_flag IS TRUE AND pa.is_primary IS TRUE
                  AND pa.lifecycle_status = 'active'
                  AND pa.start_date <= CURRENT_DATE
                  AND (pa.end_date IS NULL OR pa.end_date >= CURRENT_DATE)
                ORDER BY pa.start_date DESC, pa.assignment_id DESC
                LIMIT 1
            ) current_assignment ON TRUE
            LEFT JOIN public.org_units ou
              ON ou.unit_id = COALESCE(current_assignment.org_unit_id, e.org_unit_id)
            WHERE COALESCE(e.is_active, FALSE) IS TRUE
              AND e.operational_status = 'active'
              AND COALESCE(e.date_from, CURRENT_DATE) <= CURRENT_DATE
              AND (e.date_to IS NULL OR e.date_to >= CURRENT_DATE)
              AND COALESCE(p.person_status, 'active') = 'active'
        )
        SELECT ae.employee_id, ae.full_name, ae.org_unit_id, ae.org_unit_name,
               po.order_id, po.order_number, po.order_date, po.status, po.order_type_code,
               poi.item_id, poi.item_number, poi.item_type_code
        FROM active_employees ae
        LEFT JOIN public.personnel_order_items poi ON poi.employee_id = ae.employee_id
        LEFT JOIN public.personnel_orders po
          ON po.order_id = poi.order_id
         AND po.status IN ('SIGNED', 'REGISTERED')
         AND po.deleted_at IS NULL AND po.archived_at IS NULL
        ORDER BY LOWER(ae.full_name), ae.full_name, ae.employee_id,
                 po.order_date DESC NULLS LAST, po.order_id DESC, poi.item_number
    """)
    with db_engine.connect() as connection:
        rows = connection.execute(statement).mappings().all()

    employees: dict[int, dict[str, Any]] = {}
    order_maps: dict[int, dict[int, dict[str, Any]]] = {}
    item_ids: set[int] = set()
    for row in rows:
        employee_id = int(row["employee_id"])
        employee = employees.setdefault(employee_id, {
            "employee_id": employee_id,
            "full_name": str(row["full_name"] or ""),
            "org_unit_id": int(row["org_unit_id"]) if row["org_unit_id"] is not None else None,
            "org_unit_name": row["org_unit_name"],
            "order_count": 0,
            "ordinary_order_count": 0,
            "composite_order_count": 0,
            "action_count": 0,
            "actions_by_type": [],
            "orders": [],
        })
        if row["order_id"] is None or row["item_id"] is None:
            continue
        item_id = int(row["item_id"])
        if item_id in item_ids:
            continue
        item_ids.add(item_id)
        order_id = int(row["order_id"])
        orders = order_maps.setdefault(employee_id, {})
        order = orders.setdefault(order_id, {
            "order_id": order_id,
            "order_number": row["order_number"],
            "order_date": _iso_date(row["order_date"]),
            "status": row["status"],
            "status_label": STATUS_LABELS.get(row["status"], row["status"]),
            "is_composite": row["order_type_code"] == "COMPOSITE",
            "actions": [],
            "_counts": {},
        })
        code = str(row["item_type_code"] or "").strip().upper()
        order["_counts"][code] = order["_counts"].get(code, 0) + 1
        employee["action_count"] += 1

    for employee_id, employee in employees.items():
        counts: dict[str, int] = {}
        orders = list(order_maps.get(employee_id, {}).values())
        for order in orders:
            order["actions"] = _actions(order.pop("_counts"))
            for action in order["actions"]:
                counts[action["code"]] = counts.get(action["code"], 0) + action["count"]
        employee["order_count"] = len(orders)
        employee["composite_order_count"] = sum(order["is_composite"] for order in orders)
        employee["ordinary_order_count"] = len(orders) - employee["composite_order_count"]
        employee["orders"] = orders
        employee["actions_by_type"] = _actions(counts)

    return {"report_code": "personnel_employee_actions", "employees": list(employees.values())}
