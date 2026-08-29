"""Read-only aggregate report for the personnel orders journal."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Iterable

from sqlalchemy import text

from app.db.models.personnel_orders import (
    ITEM_STATUS_ACTIVE,
    ORDER_STATUS_VOIDED,
    ORDER_TYPE_COMPOSITE,
    ORDER_TYPE_HIRE,
    ORDER_TYPE_TERMINATION,
    ORDER_TYPE_TRANSFER,
)
from app.services.hr_event_registry import (
    EVENT_CATEGORY_LEAVE,
    HR_EVENT_REGISTRY,
    get_event_label,
)


class PersonnelOrdersSummaryFilterError(ValueError):
    """Invalid date interval for the orders summary report."""


CATEGORY_HIRE = "hire"
CATEGORY_TERMINATION = "termination"
CATEGORY_TRANSFER = "transfer"
CATEGORY_LEAVE = "leave"
CATEGORY_OTHER = "other"

CATEGORY_DEFINITIONS = (
    (CATEGORY_HIRE, "Приём"),
    (CATEGORY_TERMINATION, "Увольнение"),
    (CATEGORY_TRANSFER, "Перевод"),
    (CATEGORY_LEAVE, "Отпуска"),
    (CATEGORY_OTHER, "Прочие"),
)

# Canonical codes are authoritative. Display text is never used for classification.
ORDER_CATEGORY_BY_TYPE = {
    ORDER_TYPE_HIRE: CATEGORY_HIRE,
    ORDER_TYPE_TERMINATION: CATEGORY_TERMINATION,
    ORDER_TYPE_TRANSFER: CATEGORY_TRANSFER,
    **{
        code: CATEGORY_LEAVE
        for code, definition in HR_EVENT_REGISTRY.items()
        if definition.category == EVENT_CATEGORY_LEAVE
    },
}

STATUS_LABELS = {
    "DRAFT": "Черновик",
    "READY_FOR_SIGNATURE": "Готов к подписанию",
    "SIGNED": "Подписан",
    "REGISTERED": "Зарегистрирован",
}

TYPE_LABELS = {
    "CONCURRENT_DUTY_START": "Начало совмещения",
    "CONCURRENT_DUTY_END": "Прекращение совмещения",
    ORDER_TYPE_COMPOSITE: "Составной приказ",
}


def classify_order_category(header_type: str, item_types: Iterable[str]) -> str:
    """Map canonical header/subtype codes to exactly one report category.

    A specific recognized header is authoritative. Composite and unknown headers
    use their active item subtypes only when all subtypes resolve to one category;
    mixed or unknown combinations intentionally fall back to ``other``.
    """
    normalized_header = str(header_type or "").strip().upper()
    direct = ORDER_CATEGORY_BY_TYPE.get(normalized_header)
    if direct is not None:
        return direct

    resolved = {
        ORDER_CATEGORY_BY_TYPE.get(str(item_type or "").strip().upper(), CATEGORY_OTHER)
        for item_type in item_types
    }
    if len(resolved) == 1:
        return next(iter(resolved))
    return CATEGORY_OTHER


def _type_label(code: str) -> str:
    normalized = str(code or "").strip().upper()
    return TYPE_LABELS.get(normalized, get_event_label(normalized))


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _iso_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _serialize_order(row: dict[str, Any]) -> dict[str, Any]:
    item_types = sorted(
        {str(value).strip().upper() for value in _as_list(row.get("item_type_codes")) if value}
    )
    header_type = str(row.get("order_type_code") or "").strip().upper()
    if header_type == ORDER_TYPE_COMPOSITE and item_types:
        type_label = "; ".join(_type_label(code) for code in item_types)
    else:
        type_label = _type_label(header_type)
    raw_number = row.get("order_number")
    number = str(raw_number).strip() if raw_number is not None and str(raw_number).strip() else None
    status = str(row.get("status") or "").strip().upper()
    return {
        "order_id": int(row["order_id"]),
        "order_number": number,
        "order_date": _iso_date(row.get("order_date")),
        "order_type_code": header_type,
        "item_type_codes": item_types,
        "type_label": type_label,
        "employee_names": [str(value) for value in _as_list(row.get("employee_names")) if value],
        "department_names": [str(value) for value in _as_list(row.get("department_names")) if value],
        "status": status,
        "status_label": STATUS_LABELS.get(status, status or "—"),
        "category_code": classify_order_category(header_type, item_types),
    }


def _order_sort_key(order: dict[str, Any]) -> tuple[Any, ...]:
    raw_date = order.get("order_date")
    parsed_date = date.fromisoformat(raw_date) if raw_date else None
    return (
        parsed_date is None,
        -(parsed_date.toordinal() if parsed_date else 0),
        order.get("order_number") is None,
        (order.get("order_number") or "").casefold(),
        int(order["order_id"]),
    )


def _fetch_order_rows(
    db_engine: Any,
    *,
    date_from: date | None,
    date_to: date | None,
) -> list[dict[str, Any]]:
    where_parts = ["po.archived_at IS NULL", "po.status <> :voided_status"]
    params: dict[str, Any] = {"voided_status": ORDER_STATUS_VOIDED}
    if date_from is not None:
        where_parts.append("po.order_date >= :date_from")
        params["date_from"] = date_from
    if date_to is not None:
        where_parts.append("po.order_date <= :date_to")
        params["date_to"] = date_to

    statement = text(
        f"""
        SELECT
            po.order_id,
            po.order_number,
            po.order_date,
            po.order_type_code,
            po.status,
            ARRAY(
                SELECT DISTINCT poi_type.item_type_code
                FROM public.personnel_order_items poi_type
                WHERE poi_type.order_id = po.order_id
                  AND poi_type.item_status = :active_item_status
                ORDER BY poi_type.item_type_code
            ) AS item_type_codes,
            ARRAY(
                SELECT DISTINCT e.full_name
                FROM public.personnel_order_items poi_employee
                JOIN public.employees e ON e.employee_id = poi_employee.employee_id
                WHERE poi_employee.order_id = po.order_id
                  AND poi_employee.item_status = :active_item_status
                ORDER BY e.full_name
            ) AS employee_names,
            ARRAY(
                SELECT DISTINCT ou.name
                FROM public.personnel_order_items poi_department
                JOIN public.employees e ON e.employee_id = poi_department.employee_id
                LEFT JOIN public.org_units ou ON ou.unit_id = e.org_unit_id
                WHERE poi_department.order_id = po.order_id
                  AND poi_department.item_status = :active_item_status
                  AND ou.name IS NOT NULL
                ORDER BY ou.name
            ) AS department_names
        FROM public.personnel_orders po
        WHERE {" AND ".join(where_parts)}
        """
    )
    params["active_item_status"] = ITEM_STATUS_ACTIVE
    with db_engine.connect() as connection:
        return [dict(row) for row in connection.execute(statement, params).mappings().all()]


def build_personnel_orders_summary(
    db_engine: Any,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build summary and details from one de-duplicated set of order headers."""
    if date_from is not None and date_to is not None and date_from > date_to:
        raise PersonnelOrdersSummaryFilterError("Дата с не может быть позже даты по.")

    unique_orders: dict[int, dict[str, Any]] = {}
    for row in _fetch_order_rows(db_engine, date_from=date_from, date_to=date_to):
        order = _serialize_order(row)
        unique_orders[order["order_id"]] = order
    orders = sorted(unique_orders.values(), key=_order_sort_key)

    categories = []
    for code, name in CATEGORY_DEFINITIONS:
        category_orders = [order for order in orders if order["category_code"] == code]
        categories.append(
            {
                "code": code,
                "name": name,
                "count": len(category_orders),
                "incomplete_count": sum(
                    1
                    for order in category_orders
                    if order["order_number"] is None or order["order_date"] is None
                ),
                "orders": category_orders,
            }
        )

    timestamp = generated_at or datetime.now(timezone.utc)
    return {
        "report_code": "personnel_orders_summary",
        "report_name": "Общая сводка по приказам",
        "generated_at": timestamp.isoformat(),
        "filters": {
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
        },
        "period_note": (
            "При заданном периоде приказы без официальной даты не включаются."
            if date_from is not None or date_to is not None
            else None
        ),
        "categories": categories,
        "total_count": sum(category["count"] for category in categories),
        "total_incomplete_count": sum(category["incomplete_count"] for category in categories),
    }
