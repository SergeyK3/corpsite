"""Shared helpers for Personnel Orders characterization tests (UDE-007)."""
from __future__ import annotations

from typing import Any, Dict
from uuid import uuid4

from sqlalchemy import text

from app.db.engine import engine
from tests.test_wp_po_003_personnel_orders_schema import (
    _delete_personnel_order_audit_rows,
    _pick_employee_id,
)
from tests.test_wp_po_edit_002_migration import _require_schema as _require_edit_002_schema
from tests.test_wp_po_lc_del_005_archive_api import (
    _archive_payload,
    _cleanup_order,
    _create_draft_order,
    _set_order_status,
)


def require_edit_002_schema() -> None:
    _require_edit_002_schema()


def cancel_payload(**overrides: Any) -> Dict[str, Any]:
    payload = {"reason_code": "created_by_mistake", "reason_text": "Characterization cancel"}
    payload.update(overrides)
    return payload


def create_draft_order(
    client,
    headers,
    *,
    suffix: str | None = None,
    created_by: int | None = None,
) -> int:
    order_id = _create_draft_order(client, headers, suffix=suffix)
    if created_by is not None:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE public.personnel_orders
                    SET created_by = :created_by
                    WHERE order_id = :order_id
                    """
                ),
                {"created_by": int(created_by), "order_id": order_id},
            )
    return order_id


def cleanup_order(order_id: int) -> None:
    _cleanup_order(order_id)


def set_order_status(order_id: int, status: str, *, void_reason: str | None = None) -> None:
    _set_order_status(order_id, status, void_reason=void_reason)


def archive_payload(**overrides: Any) -> Dict[str, Any]:
    return _archive_payload(**overrides)


def create_hire_item(
    client,
    headers,
    order_id: int,
    *,
    employee_id: int | None = None,
    item_type: str = "HIRE",
) -> int:
    payload: Dict[str, Any] = {
        "item_type_code": item_type,
        "effective_date": "2026-07-12",
        "payload": {
            "employment_rate": 1.0,
            "org_unit_name": "Synthetic Unit",
            "position_name": "Synthetic Position",
        },
    }
    if employee_id is not None:
        payload["employee_id"] = employee_id

    item_resp = client.post(
        f"/directory/personnel-orders/{order_id}/items",
        json=payload,
        headers=headers,
    )
    assert item_resp.status_code == 200, item_resp.text
    return int(item_resp.json()["items"][0]["item_id"])


def create_draft_with_item(
    client,
    headers,
    *,
    order_type: str = "HIRE",
    employee_id: int | None = None,
    suffix: str | None = None,
) -> tuple[int, int]:
    order_id = create_draft_order(client, headers, suffix=suffix)
    try:
        if employee_id is None and order_type != "HIRE":
            with engine.begin() as conn:
                employee_id = _pick_employee_id(conn)
        item_id = create_hire_item(
            client,
            headers,
            order_id,
            employee_id=employee_id,
            item_type=order_type,
        )
        return order_id, item_id
    except Exception:
        cleanup_order_with_editorial(order_id)
        raise


def cleanup_order_with_editorial(order_id: int | None) -> None:
    if order_id is None:
        return
    with engine.begin() as conn:
        exists = conn.execute(
            text(
                """
                SELECT 1 FROM public.personnel_orders
                WHERE order_id = :order_id
                LIMIT 1
                """
            ),
            {"order_id": order_id},
        ).first()
        if not exists:
            return
        _delete_personnel_order_audit_rows(conn, order_id)
        conn.execute(
            text("DELETE FROM public.employee_events WHERE order_id = :order_id"),
            {"order_id": order_id},
        )
        editorial_exists = conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'personnel_order_editorial_blocks'
                LIMIT 1
                """
            )
        ).first()
        if editorial_exists:
            conn.execute(
                text(
                    """
                    DELETE FROM public.personnel_order_item_editorial_blocks
                    WHERE order_item_id IN (
                        SELECT item_id FROM public.personnel_order_items WHERE order_id = :order_id
                    )
                    """
                ),
                {"order_id": order_id},
            )
            conn.execute(
                text(
                    """
                    DELETE FROM public.personnel_order_item_bases
                    WHERE order_item_id IN (
                        SELECT item_id FROM public.personnel_order_items WHERE order_id = :order_id
                    )
                    """
                ),
                {"order_id": order_id},
            )
            conn.execute(
                text(
                    "DELETE FROM public.personnel_order_editorial_blocks WHERE order_id = :order_id"
                ),
                {"order_id": order_id},
            )
        conn.execute(
            text("DELETE FROM public.personnel_order_localized_texts WHERE order_id = :order_id"),
            {"order_id": order_id},
        )
        conn.execute(
            text("DELETE FROM public.personnel_order_items WHERE order_id = :order_id"),
            {"order_id": order_id},
        )
        conn.execute(
            text("DELETE FROM public.personnel_orders WHERE order_id = :order_id"),
            {"order_id": order_id},
        )


def unique_suffix() -> str:
    return uuid4().hex[:8]
