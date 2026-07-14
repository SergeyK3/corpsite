"""Apply service for personnel orders (WP-PO-004C).

Creates APPROVED employee_events for SIGNED/REGISTERED orders with P0 item types.
Apply is allowed once per order (idempotent guard via existing linked events).
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_orders import (
    ITEM_STATUS_ACTIVE,
    MVP_ITEM_TYPE_CODES,
    ORDER_STATUS_REGISTERED,
    ORDER_STATUS_SIGNED,
    ORDER_TYPE_CONCURRENT_DUTY_END,
    ORDER_TYPE_CONCURRENT_DUTY_START,
    ORDER_TYPE_HIRE,
    ORDER_TYPE_TERMINATION,
    ORDER_TYPE_TRANSFER,
)
from app.services.directory_service import _insert_employee_event
from app.services.hr_event_registry import get_event_class
from app.services.personnel_order_archive_guard import assert_order_not_archived
from app.services.personnel_orders_command_service import (
    PersonnelOrderConflictError,
    _fetch_order_row,
)
from app.services.personnel_orders_query_service import (
    PersonnelOrderNotFoundError,
    PersonnelOrderValidationError,
    get_personnel_order,
    personnel_orders_available,
)

APPLYABLE_ORDER_STATUSES = {
    ORDER_STATUS_SIGNED,
    ORDER_STATUS_REGISTERED,
}


class PersonnelOrderAlreadyAppliedError(PersonnelOrderConflictError):
    """Order already has linked employee_events from a prior apply."""


def _require_available() -> None:
    if not personnel_orders_available():
        raise PersonnelOrderValidationError("Personnel orders schema is not available.")


def _format_order_ref(order_number: str, order_date: date) -> str:
    return f"№{order_number} от {order_date.isoformat()}"


def _count_linked_events(conn, order_id: int) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.employee_events
                WHERE order_id = :order_id
                """
            ),
            {"order_id": int(order_id)},
        ).scalar_one()
    )


def _fetch_active_items(conn, order_id: int) -> List[Dict[str, Any]]:
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


def _fetch_employee_snapshot(conn, employee_id: int) -> Dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT
                employee_id,
                org_unit_id,
                position_id,
                employment_rate,
                is_active,
                date_from,
                date_to
            FROM public.employees
            WHERE employee_id = :employee_id
            FOR UPDATE
            """
        ),
        {"employee_id": int(employee_id)},
    ).mappings().first()
    if row is None:
        raise PersonnelOrderValidationError(f"Employee {employee_id} not found.")
    return dict(row)


def _count_prior_approved_events(conn, employee_id: int) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.employee_events
                WHERE employee_id = :employee_id
                  AND lifecycle_status = 'APPROVED'
                """
            ),
            {"employee_id": int(employee_id)},
        ).scalar_one()
    )


def _build_pre_apply_state(conn, snapshot: Dict[str, Any]) -> Dict[str, Any]:
    org_raw = snapshot.get("org_unit_id")
    position_raw = snapshot.get("position_id")
    rate_raw = snapshot.get("employment_rate")
    date_from_raw = snapshot.get("date_from")
    if date_from_raw is not None and hasattr(date_from_raw, "isoformat"):
        date_from_value: Optional[str] = date_from_raw.isoformat()
    elif date_from_raw is not None:
        date_from_value = str(date_from_raw)
    else:
        date_from_value = None

    date_to_raw = snapshot.get("date_to")
    if date_to_raw is not None and hasattr(date_to_raw, "isoformat"):
        date_to_value: Optional[str] = date_to_raw.isoformat()
    elif date_to_raw is not None:
        date_to_value = str(date_to_raw)
    else:
        date_to_value = None

    return {
        "org_unit_id": int(org_raw) if org_raw is not None else None,
        "position_id": int(position_raw) if position_raw is not None else None,
        "employment_rate": float(rate_raw) if rate_raw is not None else None,
        "is_active": bool(snapshot.get("is_active")),
        "date_from": date_from_value,
        "date_to": date_to_value,
        "had_prior_employment_events": _count_prior_approved_events(
            conn, int(snapshot["employee_id"])
        )
        > 0,
    }


def _parse_payload(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    return {}


def _optional_rate(value: Any) -> Optional[float]:
    if value is None:
        return None
    rate = float(value)
    if rate <= 0 or rate > 2:
        raise PersonnelOrderValidationError("employment_rate must be > 0 and <= 2.")
    return rate


def _resolve_event_types(item_type_code: str, payload: Dict[str, Any]) -> List[str]:
    normalized = str(item_type_code or "").strip().upper()
    if normalized not in MVP_ITEM_TYPE_CODES:
        raise PersonnelOrderValidationError(f"Unsupported item_type_code: {item_type_code}")

    if normalized == ORDER_TYPE_HIRE:
        return ["HIRE"]
    if normalized == ORDER_TYPE_TRANSFER:
        event_types = ["TRANSFER"]
        if payload.get("includes_concurrent_duty") and payload.get("concurrent_rate") is not None:
            event_types.append("RATE_CHANGE")
        return event_types
    if normalized == ORDER_TYPE_TERMINATION:
        return ["TERMINATION"]
    if normalized in {ORDER_TYPE_CONCURRENT_DUTY_START, ORDER_TYPE_CONCURRENT_DUTY_END}:
        return ["RATE_CHANGE"]
    raise PersonnelOrderValidationError(f"Unsupported item_type_code: {item_type_code}")


def _build_item_metadata(
    *,
    item_id: int,
    item_type_code: str,
    payload: Dict[str, Any],
    pre_apply_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {
        "order_item_id": int(item_id),
        "order_type_code": str(item_type_code).strip().upper(),
    }
    for key in ("concurrent_position_id", "concurrent_rate", "total_rate"):
        if key in payload and payload[key] is not None:
            metadata[key] = payload[key]
    if pre_apply_state is not None:
        metadata["pre_apply_state"] = pre_apply_state
    return metadata


def _apply_hire(
    conn,
    *,
    item: Dict[str, Any],
    order_id: int,
    order_ref: str,
    created_by: int,
) -> None:
    employee_id = int(item["employee_id"])
    effective_date = item["effective_date"]
    payload = _parse_payload(item.get("payload"))

    org_unit_id = payload.get("org_unit_id")
    position_id = payload.get("position_id")
    if org_unit_id is None or position_id is None:
        raise PersonnelOrderValidationError(
            f"Order item {item['item_id']} HIRE payload requires org_unit_id and position_id."
        )

    to_org_unit_id = int(org_unit_id)
    to_position_id = int(position_id)
    to_rate = _optional_rate(payload.get("employment_rate")) or 1.0

    snapshot = _fetch_employee_snapshot(conn, employee_id)
    pre_apply_state = _build_pre_apply_state(conn, snapshot)
    from_org_unit_id = int(snapshot["org_unit_id"]) if snapshot.get("org_unit_id") is not None else None
    from_position_raw = snapshot.get("position_id")
    from_position_id = int(from_position_raw) if from_position_raw is not None else None
    from_rate_raw = snapshot.get("employment_rate")
    from_rate = float(from_rate_raw) if from_rate_raw is not None else None

    conn.execute(
        text(
            """
            UPDATE public.employees
            SET org_unit_id = :org_unit_id,
                position_id = :position_id,
                employment_rate = :employment_rate,
                is_active = TRUE,
                date_from = COALESCE(date_from, :effective_date)
            WHERE employee_id = :employee_id
            """
        ),
        {
            "employee_id": employee_id,
            "org_unit_id": to_org_unit_id,
            "position_id": to_position_id,
            "employment_rate": to_rate,
            "effective_date": effective_date,
        },
    )

    _insert_employee_event(
        conn,
        employee_id=employee_id,
        event_type="HIRE",
        event_class=get_event_class("HIRE"),
        lifecycle_status="APPROVED",
        metadata=_build_item_metadata(
            item_id=int(item["item_id"]),
            item_type_code=str(item["item_type_code"]),
            payload=payload,
            pre_apply_state=pre_apply_state,
        ),
        effective_date=effective_date,
        from_org_unit_id=from_org_unit_id,
        from_position_id=from_position_id,
        from_rate=from_rate,
        to_org_unit_id=to_org_unit_id,
        to_position_id=to_position_id,
        to_rate=to_rate,
        order_ref=order_ref,
        comment=None,
        created_by=created_by,
        order_id=order_id,
        order_item_id=int(item["item_id"]),
    )


def _apply_transfer(
    conn,
    *,
    item: Dict[str, Any],
    order_id: int,
    order_ref: str,
    created_by: int,
) -> None:
    employee_id = int(item["employee_id"])
    effective_date = item["effective_date"]
    payload = _parse_payload(item.get("payload"))

    snapshot = _fetch_employee_snapshot(conn, employee_id)
    pre_apply_state = _build_pre_apply_state(conn, snapshot)
    if snapshot.get("is_active") is False:
        raise PersonnelOrderConflictError(f"Employee {employee_id} is inactive.")

    from_org_unit_id = int(snapshot["org_unit_id"])
    from_position_raw = snapshot.get("position_id")
    from_position_id = int(from_position_raw) if from_position_raw is not None else None
    from_rate_raw = snapshot.get("employment_rate")
    from_rate = float(from_rate_raw) if from_rate_raw is not None else None

    to_org_unit_raw = payload.get("to_org_unit_id")
    to_org_unit_id = int(to_org_unit_raw) if to_org_unit_raw is not None else from_org_unit_id

    to_position_raw = payload.get("to_position_id")
    if to_position_raw is not None:
        to_position_id = int(to_position_raw)
    elif from_position_id is not None:
        to_position_id = from_position_id
    else:
        raise PersonnelOrderValidationError(
            f"Order item {item['item_id']} TRANSFER requires to_position_id when employee has no position."
        )

    to_rate = _optional_rate(payload.get("to_rate", payload.get("to_employment_rate")))
    effective_to_rate = to_rate if to_rate is not None else (from_rate if from_rate is not None else 1.0)

    if to_org_unit_id == from_org_unit_id and to_position_id == from_position_id and effective_to_rate == from_rate:
        raise PersonnelOrderValidationError(
            f"Order item {item['item_id']} TRANSFER must change org unit, position, or rate."
        )

    conn.execute(
        text(
            """
            UPDATE public.employees
            SET org_unit_id = :org_unit_id,
                position_id = :position_id,
                employment_rate = :employment_rate
            WHERE employee_id = :employee_id
            """
        ),
        {
            "employee_id": employee_id,
            "org_unit_id": to_org_unit_id,
            "position_id": to_position_id,
            "employment_rate": effective_to_rate,
        },
    )
    if to_org_unit_id != from_org_unit_id:
        conn.execute(
            text(
                """
                UPDATE public.users
                SET unit_id = :unit_id
                WHERE employee_id = :employee_id
                """
            ),
            {"employee_id": employee_id, "unit_id": to_org_unit_id},
        )

    _insert_employee_event(
        conn,
        employee_id=employee_id,
        event_type="TRANSFER",
        event_class=get_event_class("TRANSFER"),
        lifecycle_status="APPROVED",
        metadata=_build_item_metadata(
            item_id=int(item["item_id"]),
            item_type_code=str(item["item_type_code"]),
            payload=payload,
            pre_apply_state=pre_apply_state,
        ),
        effective_date=effective_date,
        from_org_unit_id=from_org_unit_id,
        from_position_id=from_position_id,
        from_rate=from_rate,
        to_org_unit_id=to_org_unit_id,
        to_position_id=to_position_id,
        to_rate=effective_to_rate,
        order_ref=order_ref,
        comment=None,
        created_by=created_by,
        order_id=order_id,
        order_item_id=int(item["item_id"]),
    )


def _apply_termination(
    conn,
    *,
    item: Dict[str, Any],
    order_id: int,
    order_ref: str,
    created_by: int,
) -> None:
    employee_id = int(item["employee_id"])
    effective_date = item["effective_date"]
    payload = _parse_payload(item.get("payload"))

    snapshot = _fetch_employee_snapshot(conn, employee_id)
    pre_apply_state = _build_pre_apply_state(conn, snapshot)
    from_org_unit_id = int(snapshot["org_unit_id"])
    from_position_raw = snapshot.get("position_id")
    from_position_id = int(from_position_raw) if from_position_raw is not None else None
    from_rate_raw = snapshot.get("employment_rate")
    from_rate = float(from_rate_raw) if from_rate_raw is not None else None

    conn.execute(
        text(
            """
            UPDATE public.employees
            SET is_active = FALSE,
                date_to = :date_to
            WHERE employee_id = :employee_id
            """
        ),
        {"employee_id": employee_id, "date_to": effective_date},
    )
    conn.execute(
        text(
            """
            UPDATE public.users
            SET is_active = FALSE
            WHERE employee_id = :employee_id
            """
        ),
        {"employee_id": employee_id},
    )

    _insert_employee_event(
        conn,
        employee_id=employee_id,
        event_type="TERMINATION",
        event_class=get_event_class("TERMINATION"),
        lifecycle_status="APPROVED",
        metadata=_build_item_metadata(
            item_id=int(item["item_id"]),
            item_type_code=str(item["item_type_code"]),
            payload=payload,
            pre_apply_state=pre_apply_state,
        ),
        effective_date=effective_date,
        from_org_unit_id=from_org_unit_id,
        from_position_id=from_position_id,
        from_rate=from_rate,
        to_org_unit_id=None,
        to_position_id=None,
        to_rate=None,
        order_ref=order_ref,
        comment=payload.get("comment"),
        created_by=created_by,
        order_id=order_id,
        order_item_id=int(item["item_id"]),
    )


def _resolve_rate_change_target(
    *,
    item_type_code: str,
    payload: Dict[str, Any],
    from_rate: Optional[float],
) -> float:
    normalized = str(item_type_code).strip().upper()
    explicit_total = _optional_rate(payload.get("total_rate"))
    if explicit_total is not None:
        return explicit_total

    if normalized == ORDER_TYPE_CONCURRENT_DUTY_START:
        concurrent_rate = _optional_rate(payload.get("concurrent_rate"))
        if concurrent_rate is None:
            raise PersonnelOrderValidationError(
                "CONCURRENT_DUTY_START payload requires concurrent_rate or total_rate."
            )
        base_rate = from_rate if from_rate is not None else 0.0
        return base_rate + concurrent_rate

    if normalized == ORDER_TYPE_CONCURRENT_DUTY_END:
        remaining = _optional_rate(payload.get("remaining_rate"))
        if remaining is not None:
            return remaining
        removed = _optional_rate(payload.get("concurrent_rate"))
        if removed is None:
            raise PersonnelOrderValidationError(
                "CONCURRENT_DUTY_END payload requires remaining_rate, total_rate, or concurrent_rate."
            )
        base_rate = from_rate if from_rate is not None else 0.0
        return max(base_rate - removed, 0.0)

    combo_total = _optional_rate(payload.get("total_rate"))
    if combo_total is not None:
        return combo_total
    combo_rate = _optional_rate(payload.get("concurrent_rate"))
    if combo_rate is not None:
        base_rate = from_rate if from_rate is not None else 0.0
        return base_rate + combo_rate

    to_rate = _optional_rate(payload.get("to_rate", payload.get("to_employment_rate")))
    if to_rate is None:
        raise PersonnelOrderValidationError("RATE_CHANGE payload requires to_rate or total_rate.")
    return to_rate


def _apply_rate_change(
    conn,
    *,
    item: Dict[str, Any],
    order_id: int,
    order_ref: str,
    created_by: int,
    item_type_code: Optional[str] = None,
) -> None:
    employee_id = int(item["employee_id"])
    effective_date = item["effective_date"]
    payload = _parse_payload(item.get("payload"))
    effective_item_type = item_type_code or str(item["item_type_code"])

    snapshot = _fetch_employee_snapshot(conn, employee_id)
    pre_apply_state = _build_pre_apply_state(conn, snapshot)
    if snapshot.get("is_active") is False:
        raise PersonnelOrderConflictError(f"Employee {employee_id} is inactive.")

    from_org_unit_id = int(snapshot["org_unit_id"])
    from_position_raw = snapshot.get("position_id")
    from_position_id = int(from_position_raw) if from_position_raw is not None else None
    from_rate_raw = snapshot.get("employment_rate")
    from_rate = float(from_rate_raw) if from_rate_raw is not None else None

    to_rate = _resolve_rate_change_target(
        item_type_code=effective_item_type,
        payload=payload,
        from_rate=from_rate,
    )
    if from_rate is not None and to_rate == from_rate:
        raise PersonnelOrderValidationError(
            f"Order item {item['item_id']} RATE_CHANGE must change employment rate."
        )

    conn.execute(
        text(
            """
            UPDATE public.employees
            SET employment_rate = :employment_rate
            WHERE employee_id = :employee_id
            """
        ),
        {"employee_id": employee_id, "employment_rate": to_rate},
    )

    _insert_employee_event(
        conn,
        employee_id=employee_id,
        event_type="RATE_CHANGE",
        event_class=get_event_class("RATE_CHANGE"),
        lifecycle_status="APPROVED",
        metadata=_build_item_metadata(
            item_id=int(item["item_id"]),
            item_type_code=effective_item_type,
            payload=payload,
            pre_apply_state=pre_apply_state,
        ),
        effective_date=effective_date,
        from_org_unit_id=from_org_unit_id,
        from_position_id=from_position_id,
        from_rate=from_rate,
        to_org_unit_id=from_org_unit_id,
        to_position_id=from_position_id,
        to_rate=to_rate,
        order_ref=order_ref,
        comment=None,
        created_by=created_by,
        order_id=order_id,
        order_item_id=int(item["item_id"]),
    )


def _apply_item_events(
    conn,
    *,
    item: Dict[str, Any],
    order_id: int,
    order_ref: str,
    created_by: int,
) -> None:
    payload = _parse_payload(item.get("payload"))
    event_types = _resolve_event_types(str(item["item_type_code"]), payload)

    for event_type in event_types:
        if event_type == "HIRE":
            _apply_hire(conn, item=item, order_id=order_id, order_ref=order_ref, created_by=created_by)
        elif event_type == "TRANSFER":
            _apply_transfer(conn, item=item, order_id=order_id, order_ref=order_ref, created_by=created_by)
        elif event_type == "TERMINATION":
            _apply_termination(conn, item=item, order_id=order_id, order_ref=order_ref, created_by=created_by)
        elif event_type == "RATE_CHANGE":
            _apply_rate_change(
                conn,
                item=item,
                order_id=order_id,
                order_ref=order_ref,
                created_by=created_by,
                item_type_code=str(item["item_type_code"]),
            )
        else:
            raise PersonnelOrderValidationError(f"Unsupported event_type mapping: {event_type}")


def apply_personnel_order(*, order_id: int, created_by: int) -> Dict[str, Any]:
    """Apply a signed/registered personnel order once, creating employee_events."""
    _require_available()

    with engine.begin() as conn:
        order = _fetch_order_row(conn, order_id)
        assert_order_not_archived(order)
        status = str(order["status"])
        if status not in APPLYABLE_ORDER_STATUSES:
            raise PersonnelOrderConflictError(
                f"Personnel order {order_id} cannot be applied in status {status}. "
                f"Allowed: SIGNED, REGISTERED."
            )

        if _count_linked_events(conn, order_id) > 0:
            raise PersonnelOrderAlreadyAppliedError(
                f"Personnel order {order_id} has already been applied."
            )

        items = _fetch_active_items(conn, order_id)
        if not items:
            raise PersonnelOrderValidationError("At least one active order item is required to apply.")

        order_ref = _format_order_ref(str(order["order_number"]), order["order_date"])

        for item in items:
            if item.get("employee_id") is None:
                raise PersonnelOrderValidationError(
                    f"Order item {item['item_id']} requires employee_id."
                )
            if item.get("effective_date") is None:
                raise PersonnelOrderValidationError(
                    f"Order item {item['item_id']} requires effective_date."
                )
            _apply_item_events(
                conn,
                item=item,
                order_id=int(order_id),
                order_ref=order_ref,
                created_by=int(created_by),
            )

    return get_personnel_order(int(order_id))
