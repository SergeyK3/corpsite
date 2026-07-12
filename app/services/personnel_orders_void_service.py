"""Void/cancel service for personnel orders (WP-PO-004D).

Cancel DRAFT/READY orders without touching employee_events.
Void SIGNED/REGISTERED orders and items with cascade void of linked APPROVED events
and snapshot rollback.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_orders import (
    ITEM_STATUS_ACTIVE,
    ITEM_STATUS_VOIDED,
    ORDER_STATUS_DRAFT,
    ORDER_STATUS_READY_FOR_SIGNATURE,
    ORDER_STATUS_REGISTERED,
    ORDER_STATUS_SIGNED,
    ORDER_STATUS_VOIDED,
)
from app.services.personnel_orders_command_service import (
    PersonnelOrderConflictError,
    PersonnelOrderItemNotFoundError,
    _fetch_order_row,
)
from app.services.personnel_orders_query_service import (
    PersonnelOrderNotFoundError,
    PersonnelOrderValidationError,
    get_personnel_order,
    personnel_orders_available,
)
from app.services.personnel_order_lifecycle_audit_service import (
    append_void_order_audit,
    resolve_void_kind,
)

CANCELABLE_ORDER_STATUSES = {
    ORDER_STATUS_DRAFT,
    ORDER_STATUS_READY_FOR_SIGNATURE,
}
VOIDABLE_ORDER_STATUSES = {
    ORDER_STATUS_SIGNED,
    ORDER_STATUS_REGISTERED,
}


class PersonnelOrderAlreadyVoidedError(PersonnelOrderConflictError):
    """Order is already voided."""


class PersonnelOrderItemAlreadyVoidedError(PersonnelOrderConflictError):
    """Order item is already voided."""


class PersonnelOrderVoidChainError(PersonnelOrderConflictError):
    """Void blocked by newer APPROVED employee events (ADR-035 void chain)."""


def _require_available() -> None:
    if not personnel_orders_available():
        raise PersonnelOrderValidationError("Personnel orders schema is not available.")


def _normalize_void_reason(void_reason: str) -> str:
    normalized = str(void_reason or "").strip()
    if not normalized:
        raise PersonnelOrderValidationError("void_reason is required.")
    return normalized


def _fetch_items(conn, order_id: int, *, item_status: Optional[str] = None) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {"order_id": int(order_id)}
    status_filter = ""
    if item_status is not None:
        status_filter = "AND item_status = :item_status"
        params["item_status"] = item_status

    rows = conn.execute(
        text(
            f"""
            SELECT
                item_id,
                order_id,
                item_number,
                item_type_code,
                item_status,
                employee_id,
                effective_date,
                payload
            FROM public.personnel_order_items
            WHERE order_id = :order_id
              {status_filter}
            ORDER BY item_number ASC, item_id ASC
            """
        ),
        params,
    ).mappings().all()
    return [dict(row) for row in rows]


def _fetch_item(conn, order_id: int, item_id: int) -> Dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT
                item_id,
                order_id,
                item_number,
                item_type_code,
                item_status,
                employee_id,
                effective_date,
                payload
            FROM public.personnel_order_items
            WHERE order_id = :order_id
              AND item_id = :item_id
            """
        ),
        {"order_id": int(order_id), "item_id": int(item_id)},
    ).mappings().first()
    if row is None:
        raise PersonnelOrderItemNotFoundError(
            f"Personnel order item {item_id} not found for order {order_id}."
        )
    return dict(row)


def _fetch_approved_events_for_item(conn, order_item_id: int) -> List[Dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT
                event_id,
                employee_id,
                event_type,
                lifecycle_status,
                effective_date,
                from_org_unit_id,
                from_position_id,
                from_rate,
                to_org_unit_id,
                to_position_id,
                to_rate
            FROM public.employee_events
            WHERE order_item_id = :order_item_id
              AND lifecycle_status = 'APPROVED'
            ORDER BY event_id ASC
            """
        ),
        {"order_item_id": int(order_item_id)},
    ).mappings().all()
    return [dict(row) for row in rows]


def _assert_void_chain_allowed(
    conn,
    *,
    employee_id: int,
    events_to_void: List[Dict[str, Any]],
) -> None:
    if not events_to_void:
        return

    event_ids = [int(event["event_id"]) for event in events_to_void]
    max_effective = max(event["effective_date"] for event in events_to_void)
    max_event_id = max(
        int(event["event_id"])
        for event in events_to_void
        if event["effective_date"] == max_effective
    )

    conflict = conn.execute(
        text(
            """
            SELECT event_id
            FROM public.employee_events
            WHERE employee_id = :employee_id
              AND lifecycle_status = 'APPROVED'
              AND event_id <> ALL(:event_ids)
              AND (
                    effective_date > :max_effective
                    OR (
                        effective_date = :max_effective
                        AND event_id > :max_event_id
                    )
              )
            LIMIT 1
            """
        ),
        {
            "employee_id": int(employee_id),
            "event_ids": event_ids,
            "max_effective": max_effective,
            "max_event_id": max_event_id,
        },
    ).first()
    if conflict is not None:
        raise PersonnelOrderVoidChainError(
            f"Void chain violation for employee {employee_id}: newer APPROVED events exist."
        )


def _rollback_snapshot_for_event(conn, event: Dict[str, Any]) -> None:
    employee_id = int(event["employee_id"])
    event_type = str(event["event_type"])

    conn.execute(
        text(
            """
            SELECT employee_id
            FROM public.employees
            WHERE employee_id = :employee_id
            FOR UPDATE
            """
        ),
        {"employee_id": employee_id},
    )

    if event_type == "HIRE":
        from_org = event.get("from_org_unit_id")
        from_position = event.get("from_position_id")
        from_rate = event.get("from_rate")
        if from_org is None and from_position is None:
            conn.execute(
                text(
                    """
                    UPDATE public.employees
                    SET is_active = FALSE
                    WHERE employee_id = :employee_id
                    """
                ),
                {"employee_id": employee_id},
            )
        else:
            conn.execute(
                text(
                    """
                    UPDATE public.employees
                    SET org_unit_id = :org_unit_id,
                        position_id = :position_id,
                        employment_rate = COALESCE(:employment_rate, employment_rate),
                        is_active = TRUE
                    WHERE employee_id = :employee_id
                    """
                ),
                {
                    "employee_id": employee_id,
                    "org_unit_id": int(from_org) if from_org is not None else None,
                    "position_id": int(from_position) if from_position is not None else None,
                    "employment_rate": float(from_rate) if from_rate is not None else None,
                },
            )
        return

    if event_type == "TRANSFER":
        from_org = event.get("from_org_unit_id")
        from_position = event.get("from_position_id")
        from_rate = event.get("from_rate")
        to_org = event.get("to_org_unit_id")
        conn.execute(
            text(
                """
                UPDATE public.employees
                SET org_unit_id = :org_unit_id,
                    position_id = :position_id,
                    employment_rate = COALESCE(:employment_rate, employment_rate)
                WHERE employee_id = :employee_id
                """
            ),
            {
                "employee_id": employee_id,
                "org_unit_id": int(from_org),
                "position_id": int(from_position) if from_position is not None else None,
                "employment_rate": float(from_rate) if from_rate is not None else None,
            },
        )
        if (
            from_org is not None
            and to_org is not None
            and int(from_org) != int(to_org)
        ):
            conn.execute(
                text(
                    """
                    UPDATE public.users
                    SET unit_id = :unit_id
                    WHERE employee_id = :employee_id
                    """
                ),
                {"employee_id": employee_id, "unit_id": int(from_org)},
            )
        return

    if event_type == "TERMINATION":
        conn.execute(
            text(
                """
                UPDATE public.employees
                SET is_active = TRUE,
                    date_to = NULL
                WHERE employee_id = :employee_id
                """
            ),
            {"employee_id": employee_id},
        )
        conn.execute(
            text(
                """
                UPDATE public.users
                SET is_active = TRUE
                WHERE employee_id = :employee_id
                """
            ),
            {"employee_id": employee_id},
        )
        return

    if event_type == "RATE_CHANGE":
        from_rate = event.get("from_rate")
        if from_rate is not None:
            conn.execute(
                text(
                    """
                    UPDATE public.employees
                    SET employment_rate = :employment_rate
                    WHERE employee_id = :employee_id
                    """
                ),
                {"employee_id": employee_id, "employment_rate": float(from_rate)},
            )
        return

    raise PersonnelOrderValidationError(f"Unsupported event_type for void rollback: {event_type}")


def _void_employee_events(
    conn,
    *,
    events: List[Dict[str, Any]],
) -> None:
    events_by_employee: Dict[int, List[Dict[str, Any]]] = {}
    for event in events:
        employee_id = int(event["employee_id"])
        events_by_employee.setdefault(employee_id, []).append(event)

    for employee_id, employee_events in events_by_employee.items():
        _assert_void_chain_allowed(conn, employee_id=employee_id, events_to_void=employee_events)

    for event in sorted(events, key=lambda row: int(row["event_id"]), reverse=True):
        _rollback_snapshot_for_event(conn, event)
        conn.execute(
            text(
                """
                UPDATE public.employee_events
                SET lifecycle_status = 'VOIDED'
                WHERE event_id = :event_id
                  AND lifecycle_status = 'APPROVED'
                """
            ),
            {"event_id": int(event["event_id"])},
        )


def _mark_item_voided(
    conn,
    *,
    item_id: int,
    order_id: int,
    void_reason: str,
    voided_by: int,
) -> None:
    conn.execute(
        text(
            """
            UPDATE public.personnel_order_items
            SET item_status = :item_status,
                void_reason = :void_reason,
                voided_at = now(),
                voided_by = :voided_by
            WHERE item_id = :item_id
              AND order_id = :order_id
              AND item_status = :active_status
            """
        ),
        {
            "item_id": int(item_id),
            "order_id": int(order_id),
            "item_status": ITEM_STATUS_VOIDED,
            "void_reason": void_reason,
            "voided_by": int(voided_by),
            "active_status": ITEM_STATUS_ACTIVE,
        },
    )


def _mark_order_voided(
    conn,
    *,
    order_id: int,
    void_reason: str,
    voided_by: int,
    void_kind: str,
) -> None:
    conn.execute(
        text(
            """
            UPDATE public.personnel_orders
            SET status = :status,
                void_kind = :void_kind,
                void_reason = :void_reason,
                voided_at = now(),
                voided_by = :voided_by,
                updated_at = now()
            WHERE order_id = :order_id
              AND status <> :voided_status
            """
        ),
        {
            "order_id": int(order_id),
            "status": ORDER_STATUS_VOIDED,
            "void_kind": str(void_kind),
            "void_reason": void_reason,
            "voided_by": int(voided_by),
            "voided_status": ORDER_STATUS_VOIDED,
        },
    )


def _void_item_with_events(
    conn,
    *,
    item: Dict[str, Any],
    void_reason: str,
    voided_by: int,
) -> None:
    if str(item["item_status"]) == ITEM_STATUS_VOIDED:
        raise PersonnelOrderItemAlreadyVoidedError(
            f"Personnel order item {item['item_id']} is already voided."
        )

    events = _fetch_approved_events_for_item(conn, int(item["item_id"]))
    if events:
        _void_employee_events(conn, events=events)

    _mark_item_voided(
        conn,
        item_id=int(item["item_id"]),
        order_id=int(item["order_id"]),
        void_reason=void_reason,
        voided_by=voided_by,
    )


def _all_items_voided(conn, order_id: int) -> bool:
    active_count = conn.execute(
        text(
            """
            SELECT COUNT(*)
            FROM public.personnel_order_items
            WHERE order_id = :order_id
              AND item_status = :item_status
            """
        ),
        {"order_id": int(order_id), "item_status": ITEM_STATUS_ACTIVE},
    ).scalar_one()
    return int(active_count or 0) == 0


def _maybe_promote_order_void(
    conn,
    *,
    order_id: int,
    void_reason: str,
    voided_by: int,
    void_kind: str,
) -> None:
    if _all_items_voided(conn, order_id):
        _mark_order_voided(
            conn,
            order_id=order_id,
            void_reason=void_reason,
            voided_by=voided_by,
            void_kind=void_kind,
        )


def void_personnel_order(*, order_id: int, void_reason: str, voided_by: int) -> Dict[str, Any]:
    """Cancel a draft/ready order or void a signed/registered order."""
    _require_available()
    normalized_reason = _normalize_void_reason(void_reason)

    with engine.begin() as conn:
        order = _fetch_order_row(conn, order_id)
        status = str(order["status"])
        if status == ORDER_STATUS_VOIDED:
            raise PersonnelOrderAlreadyVoidedError(
                f"Personnel order {order_id} is already voided."
            )

        if status in CANCELABLE_ORDER_STATUSES:
            void_kind = resolve_void_kind(status)
            previous_void_kind = order.get("void_kind")
            items = _fetch_items(conn, order_id, item_status=ITEM_STATUS_ACTIVE)
            for item in items:
                _mark_item_voided(
                    conn,
                    item_id=int(item["item_id"]),
                    order_id=int(order_id),
                    void_reason=normalized_reason,
                    voided_by=int(voided_by),
                )
            _mark_order_voided(
                conn,
                order_id=int(order_id),
                void_reason=normalized_reason,
                voided_by=int(voided_by),
                void_kind=void_kind,
            )
            append_void_order_audit(
                conn,
                order_id=int(order_id),
                previous_status=status,
                previous_void_kind=previous_void_kind,
                void_kind=void_kind,
                void_reason=normalized_reason,
                actor_user_id=int(voided_by),
            )
        elif status in VOIDABLE_ORDER_STATUSES:
            void_kind = resolve_void_kind(status)
            previous_void_kind = order.get("void_kind")
            items = _fetch_items(conn, order_id, item_status=ITEM_STATUS_ACTIVE)
            if not items:
                raise PersonnelOrderValidationError(
                    f"Personnel order {order_id} has no active items to void."
                )
            for item in items:
                _void_item_with_events(
                    conn,
                    item=item,
                    void_reason=normalized_reason,
                    voided_by=int(voided_by),
                )
            _mark_order_voided(
                conn,
                order_id=int(order_id),
                void_reason=normalized_reason,
                voided_by=int(voided_by),
                void_kind=void_kind,
            )
            append_void_order_audit(
                conn,
                order_id=int(order_id),
                previous_status=status,
                previous_void_kind=previous_void_kind,
                void_kind=void_kind,
                void_reason=normalized_reason,
                actor_user_id=int(voided_by),
            )
        else:
            raise PersonnelOrderConflictError(
                f"Personnel order {order_id} cannot be voided from status {status}."
            )

    return get_personnel_order(int(order_id))


def void_personnel_order_item(
    *,
    order_id: int,
    item_id: int,
    void_reason: str,
    voided_by: int,
) -> Dict[str, Any]:
    """Void a single active item and cascade void its linked employee_events."""
    _require_available()
    normalized_reason = _normalize_void_reason(void_reason)

    with engine.begin() as conn:
        order = _fetch_order_row(conn, order_id)
        status = str(order["status"])
        if status == ORDER_STATUS_VOIDED:
            raise PersonnelOrderAlreadyVoidedError(
                f"Personnel order {order_id} is already voided."
            )
        if status in CANCELABLE_ORDER_STATUSES:
            raise PersonnelOrderConflictError(
                f"Personnel order {order_id} must be voided at order level while in status {status}."
            )
        if status not in VOIDABLE_ORDER_STATUSES:
            raise PersonnelOrderConflictError(
                f"Personnel order item cannot be voided while order is in status {status}."
            )

        item = _fetch_item(conn, order_id, item_id)
        void_kind = resolve_void_kind(status)
        previous_void_kind = order.get("void_kind")
        _void_item_with_events(
            conn,
            item=item,
            void_reason=normalized_reason,
            voided_by=int(voided_by),
        )
        before_voided = status != ORDER_STATUS_VOIDED
        _maybe_promote_order_void(
            conn,
            order_id=int(order_id),
            void_reason=normalized_reason,
            voided_by=int(voided_by),
            void_kind=void_kind,
        )
        if before_voided:
            order_after = _fetch_order_row(conn, order_id)
            if str(order_after["status"]) == ORDER_STATUS_VOIDED:
                append_void_order_audit(
                    conn,
                    order_id=int(order_id),
                    previous_status=status,
                    previous_void_kind=previous_void_kind,
                    void_kind=void_kind,
                    void_reason=normalized_reason,
                    actor_user_id=int(voided_by),
                )

    return get_personnel_order(int(order_id))
