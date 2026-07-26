"""Read-only HIRE apply readiness checks (WP-ADR061-001D post-review)."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.models.personnel_orders import (
    ITEM_STATUS_ACTIVE,
    ORDER_STATUS_REGISTERED,
    ORDER_STATUS_SIGNED,
    ORDER_TYPE_HIRE,
)
from app.services.personnel_order_archive_guard import assert_order_not_archived
from app.services.personnel_order_hire_from_person_service import parse_person_id_from_payload
from app.services.personnel_orders_command_service import _fetch_order_row
from app.services.personnel_orders_query_service import PersonnelOrderValidationError

_APPLYABLE_ORDER_STATUSES = {
    ORDER_STATUS_SIGNED,
    ORDER_STATUS_REGISTERED,
}


def _parse_payload(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    return {}


def _fetch_active_items(conn: Connection, order_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT
                item_id,
                item_type_code,
                employee_id,
                effective_date,
                payload
            FROM public.personnel_order_items
            WHERE order_id = :order_id
              AND item_status = :item_status
            ORDER BY item_number ASC, item_id ASC
            """
        ),
        {"order_id": int(order_id), "item_status": ITEM_STATUS_ACTIVE},
    ).mappings().all()
    return [dict(row) for row in rows]


def _lookup_person_id_for_employee(conn: Connection, employee_id: int) -> int | None:
    row = conn.execute(
        text(
            """
            SELECT person_id
            FROM public.employees
            WHERE employee_id = :employee_id
            LIMIT 1
            """
        ),
        {"employee_id": int(employee_id)},
    ).mappings().first()
    if row is None or row.get("person_id") is None:
        return None
    return int(row["person_id"])


def resolve_hire_item_target_person_id(conn: Connection, item: dict[str, Any]) -> int:
    """Resolve authoritative HIRE item target person_id from payload and employee sources."""
    item_id = int(item["item_id"])
    item_type = str(item.get("item_type_code") or "").strip().upper()
    if item_type != ORDER_TYPE_HIRE:
        raise PersonnelOrderValidationError(f"Order item {item_id} is not HIRE.")

    payload = _parse_payload(item.get("payload"))
    payload_person_id = parse_person_id_from_payload(payload)

    employee_person_id: int | None = None
    employee_raw = item.get("employee_id")
    if employee_raw is not None:
        employee_person_id = _lookup_person_id_for_employee(conn, int(employee_raw))
        if employee_person_id is None:
            raise PersonnelOrderValidationError(
                f"Order item {item_id} employee_id={int(employee_raw)} has no linked person_id."
            )

    if payload_person_id is not None and employee_person_id is not None:
        if payload_person_id != employee_person_id:
            raise PersonnelOrderValidationError(
                f"Order item {item_id} HIRE target sources conflict: "
                f"payload.person_id={payload_person_id}, "
                f"employee.person_id={employee_person_id}."
            )
        return payload_person_id

    if payload_person_id is not None:
        return payload_person_id
    if employee_person_id is not None:
        return employee_person_id

    raise PersonnelOrderValidationError(
        f"Order item {item_id} HIRE requires resolvable target person_id."
    )


def _validate_hire_item_fields_readonly(item: dict[str, Any]) -> None:
    item_id = int(item["item_id"])
    if item.get("effective_date") is None:
        raise PersonnelOrderValidationError(
            f"Order item {item_id} requires effective_date."
        )

    item_type = str(item.get("item_type_code") or "").strip().upper()
    if item_type != ORDER_TYPE_HIRE:
        return

    payload = _parse_payload(item.get("payload"))
    org_unit_id = payload.get("org_unit_id")
    position_id = payload.get("position_id")
    if org_unit_id is None or position_id is None:
        raise PersonnelOrderValidationError(
            f"Order item {item_id} HIRE payload requires org_unit_id and position_id."
        )

    rate_raw = payload.get("employment_rate")
    if rate_raw is not None:
        rate = float(rate_raw)
        if rate <= 0 or rate > 2:
            raise PersonnelOrderValidationError("employment_rate must be > 0 and <= 2.")


def validate_authoritative_hire_target(
    conn: Connection,
    *,
    order_id: int,
    linked_application_person_id: int | None = None,
) -> int:
    """Validate single authoritative HIRE target and optional linked application match."""
    items = _fetch_active_items(conn, order_id)
    hire_items = [
        item
        for item in items
        if str(item.get("item_type_code") or "").strip().upper() == ORDER_TYPE_HIRE
    ]
    if not hire_items:
        raise PersonnelOrderValidationError(
            f"Personnel order {order_id} has no active HIRE items."
        )

    hire_targets: set[int] = set()
    for item in hire_items:
        hire_targets.add(resolve_hire_item_target_person_id(conn, item))

    if len(hire_targets) > 1:
        raise PersonnelOrderValidationError(
            "Personnel order "
            f"{order_id} has multiple distinct HIRE target person_ids: {sorted(hire_targets)}."
        )

    target_person_id = next(iter(hire_targets))
    if (
        linked_application_person_id is not None
        and target_person_id != int(linked_application_person_id)
    ):
        raise PersonnelOrderValidationError(
            "HIRE target person_id="
            f"{target_person_id} does not match linked application person_id="
            f"{linked_application_person_id}."
        )
    return target_person_id


def validate_hire_order_ready_for_apply_readonly(
    conn: Connection,
    *,
    order_id: int,
    linked_application_person_id: int | None = None,
) -> int:
    """Read-only order/application pre-check before photo hook or HIRE apply."""
    order = _fetch_order_row(conn, int(order_id))
    assert_order_not_archived(order)

    if str(order.get("order_type_code") or "").strip().upper() != ORDER_TYPE_HIRE:
        raise PersonnelOrderValidationError(
            f"Personnel order {order_id} is not HIRE."
        )

    status = str(order["status"])
    if status not in _APPLYABLE_ORDER_STATUSES:
        raise PersonnelOrderValidationError(
            f"Personnel order {order_id} cannot be applied in status {status}. "
            f"Allowed: SIGNED, REGISTERED."
        )

    items = _fetch_active_items(conn, int(order_id))
    if not items:
        raise PersonnelOrderValidationError(
            "At least one active order item is required to apply."
        )

    for item in items:
        _validate_hire_item_fields_readonly(item)

    return validate_authoritative_hire_target(
        conn,
        order_id=int(order_id),
        linked_application_person_id=linked_application_person_id,
    )
