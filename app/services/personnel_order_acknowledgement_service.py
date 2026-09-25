"""Append-only acknowledgement state for unique personnel-order subjects."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import text

from app.db.engine import engine
from app.services.personnel_orders_query_service import PersonnelOrderNotFoundError

TABLE = "personnel_order_acknowledgement_events"


class PersonnelOrderAcknowledgementError(ValueError):
    pass


def _organization_timezone():
    """Reuse the organisation setting lazily to avoid an API-package import cycle."""
    from app.control_list_projection.service import organization_timezone

    return organization_timezone()


def _available(conn: Any) -> bool:
    return conn.execute(text("SELECT to_regclass('public.personnel_order_acknowledgement_events')")).scalar_one() is not None


def _active_subject(conn: Any, order_id: int, employee_id: int) -> bool:
    return conn.execute(text("""
        SELECT 1 FROM public.personnel_order_items
        WHERE order_id=:order_id AND employee_id=:employee_id AND item_status='ACTIVE'
        LIMIT 1
    """), {"order_id": order_id, "employee_id": employee_id}).first() is not None


def _current(conn: Any, order_id: int, employee_id: int) -> Optional[dict[str, Any]]:
    row = conn.execute(text("""
        SELECT acknowledgement_event_id, order_id, employee_id, event_type, acknowledged_on, created_at, created_by_user_id
        FROM public.personnel_order_acknowledgement_events
        WHERE order_id=:order_id AND employee_id=:employee_id
        ORDER BY created_at DESC, acknowledgement_event_id DESC LIMIT 1
    """), {"order_id": order_id, "employee_id": employee_id}).mappings().first()
    return dict(row) if row else None


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    return {**row, "acknowledged_on": row["acknowledged_on"].isoformat() if row.get("acknowledged_on") else None,
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None}


def list_current(order_id: int) -> dict[str, Any]:
    with engine.begin() as conn:
        if conn.execute(text("SELECT 1 FROM public.personnel_orders WHERE order_id=:id"), {"id": order_id}).first() is None:
            raise PersonnelOrderNotFoundError(f"Personnel order {order_id} not found.")
        if not _available(conn): return {"items": []}
        rows = conn.execute(text("""
            SELECT DISTINCT ON (e.employee_id) e.acknowledgement_event_id, e.order_id, e.employee_id,
                e.event_type, e.acknowledged_on, e.created_at, e.created_by_user_id
            FROM public.personnel_order_acknowledgement_events e
            WHERE e.order_id=:order_id
            ORDER BY e.employee_id, e.created_at DESC, e.acknowledgement_event_id DESC
        """), {"order_id": order_id}).mappings().all()
        return {"items": [_serialize(dict(row)) for row in rows]}


def record(order_id: int, employee_id: int, acknowledged_on: date, actor_user_id: int) -> dict[str, Any]:
    with engine.begin() as conn:
        order = conn.execute(text("SELECT order_date FROM public.personnel_orders WHERE order_id=:id"), {"id": order_id}).mappings().first()
        if order is None: raise PersonnelOrderNotFoundError(f"Personnel order {order_id} not found.")
        if not _available(conn): raise PersonnelOrderAcknowledgementError("ACKNOWLEDGEMENT_SCHEMA_UNAVAILABLE")
        if not _active_subject(conn, order_id, employee_id): raise PersonnelOrderAcknowledgementError("ACKNOWLEDGEMENT_EMPLOYEE_NOT_IN_ACTIVE_ORDER")
        # Date limits follow the configured organization calendar, never the
        # process host's UTC/local clock.
        _, timezone = _organization_timezone()
        today = datetime.now(timezone).date()
        if (order["order_date"] and acknowledged_on < order["order_date"]) or acknowledged_on > today:
            raise PersonnelOrderAcknowledgementError("ACKNOWLEDGEMENT_DATE_OUT_OF_RANGE")
        previous = _current(conn, order_id, employee_id)
        if previous and previous.get("acknowledged_on") == acknowledged_on and previous.get("event_type") != "CLEARED":
            return {"item": _serialize(previous), "idempotent": True}
        event_type = "RECORDED" if previous is None or previous.get("event_type") == "CLEARED" else "CORRECTED"
        row = conn.execute(text("""
          INSERT INTO public.personnel_order_acknowledgement_events
            (order_id,employee_id,event_type,acknowledged_on,created_by_user_id)
          VALUES (:order_id,:employee_id,:event_type,:acknowledged_on,:actor)
          RETURNING acknowledgement_event_id,order_id,employee_id,event_type,acknowledged_on,created_at,created_by_user_id
        """), {"order_id":order_id,"employee_id":employee_id,"event_type":event_type,"acknowledged_on":acknowledged_on,"actor":actor_user_id}).mappings().one()
        return {"item": _serialize(dict(row)), "idempotent": False}


def clear(order_id: int, employee_id: int, actor_user_id: int) -> dict[str, Any]:
    with engine.begin() as conn:
        if not _available(conn): raise PersonnelOrderAcknowledgementError("ACKNOWLEDGEMENT_SCHEMA_UNAVAILABLE")
        if not _active_subject(conn, order_id, employee_id): raise PersonnelOrderAcknowledgementError("ACKNOWLEDGEMENT_EMPLOYEE_NOT_IN_ACTIVE_ORDER")
        previous = _current(conn, order_id, employee_id)
        if previous is None or previous.get("event_type") == "CLEARED": return {"item": _serialize(previous) if previous else None, "idempotent": True}
        row = conn.execute(text("""
          INSERT INTO public.personnel_order_acknowledgement_events
            (order_id,employee_id,event_type,acknowledged_on,created_by_user_id)
          VALUES (:order_id,:employee_id,'CLEARED',NULL,:actor)
          RETURNING acknowledgement_event_id,order_id,employee_id,event_type,acknowledged_on,created_at,created_by_user_id
        """), {"order_id":order_id,"employee_id":employee_id,"actor":actor_user_id}).mappings().one()
        return {"item": _serialize(dict(row)), "idempotent": False}
