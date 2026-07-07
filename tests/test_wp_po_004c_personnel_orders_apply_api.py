# tests/test_wp_po_004c_personnel_orders_apply_api.py
"""API tests for WP-PO-004C personnel orders apply endpoint."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers, get_columns, insert_returning_id, table_exists
from tests.test_wp_po_003_personnel_orders_schema import (
    _pick_employee_id,
    _require_schema,
)

pytestmark = pytest.mark.usefixtures("_require_wp_po_003_schema")


@pytest.fixture(scope="module", autouse=True)
def _require_wp_po_003_schema():
    _require_schema()


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


def _count_events_for_order(order_id: int) -> int:
    with engine.begin() as conn:
        return int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.employee_events
                    WHERE order_id = :order_id
                    """
                ),
                {"order_id": order_id},
            ).scalar_one()
        )


def _cleanup_order(order_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.employee_events WHERE order_id = :order_id"),
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


def _create_test_employee(conn, *, org_unit_id: int, position_id: int, rate: float = 1.0) -> int:
    return insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values={
            "full_name": f"WPPO4C {uuid4().hex[:8]}",
            "org_unit_id": org_unit_id,
            "position_id": position_id,
            "employment_rate": rate,
            "is_active": True,
        },
    )


def _create_position(conn, *, name: str) -> int:
    cols = get_columns(conn, "positions")
    values: Dict[str, Any] = {"name": name}
    if "category" in cols:
        values["category"] = "other"
    return insert_returning_id(conn, table="positions", id_col="position_id", values=values)


def _create_registered_order_with_item(
    client,
    privileged_headers,
    *,
    order_type_code: str,
    item_type_code: str,
    employee_id: int,
    payload: Dict[str, Any],
    target_status: str = "REGISTERED",
) -> tuple[int, int, str]:
    suffix = uuid4().hex[:8]
    order_number = f"WPPO4C-{suffix}"

    create_resp = client.post(
        "/directory/personnel-orders",
        json={
            "order_number": order_number,
            "order_date": "2026-07-07",
            "order_type_code": order_type_code,
            "source_mode": "PAPER",
        },
        headers=privileged_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    order_id = create_resp.json()["order"]["order_id"]

    item_resp = client.post(
        f"/directory/personnel-orders/{order_id}/items",
        json={
            "item_type_code": item_type_code,
            "employee_id": employee_id,
            "effective_date": "2026-07-07",
            "payload": payload,
        },
        headers=privileged_headers,
    )
    assert item_resp.status_code == 200, item_resp.text
    item_id = item_resp.json()["items"][0]["item_id"]

    register_resp = client.post(
        f"/directory/personnel-orders/{order_id}/register",
        json={"target_status": target_status},
        headers=privileged_headers,
    )
    assert register_resp.status_code == 200, register_resp.text

    return order_id, item_id, order_number


def test_apply_registered_hire_order_creates_linked_event(client, privileged_headers, seed):
    pos_ids: List[int] = []
    employee_id = 0
    with engine.begin() as conn:
        org_unit_id = int(seed["unit_id"])
        position_id = _create_position(conn, name=f"WPPO4C-hire-{uuid4().hex[:8]}")
        pos_ids.append(position_id)
        employee_id = _create_test_employee(
            conn,
            org_unit_id=org_unit_id,
            position_id=position_id,
        )
        row = conn.execute(
            text(
                """
                SELECT org_unit_id, position_id, employment_rate
                FROM public.employees
                WHERE employee_id = :employee_id
                """
            ),
            {"employee_id": employee_id},
        ).mappings().one()

    order_id, item_id, order_number = _create_registered_order_with_item(
        client,
        privileged_headers,
        order_type_code="HIRE",
        item_type_code="HIRE",
        employee_id=employee_id,
        payload={
            "org_unit_id": int(row["org_unit_id"]),
            "position_id": int(row["position_id"]),
            "employment_rate": float(row["employment_rate"] or 1.0),
        },
    )

    try:
        apply_resp = client.post(
            f"/directory/personnel-orders/{order_id}/apply",
            headers=privileged_headers,
        )
        assert apply_resp.status_code == 200, apply_resp.text
        body = apply_resp.json()
        assert len(body["events"]) == 1
        event = body["events"][0]
        assert event["event_type"] == "HIRE"
        assert event["order_id"] == order_id
        assert event["order_item_id"] == item_id
        assert event["order_ref"] == f"№{order_number} от 2026-07-07"
        assert _count_events_for_order(order_id) == 1
    finally:
        _cleanup_order(order_id)
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public.employees WHERE employee_id = :employee_id"),
                {"employee_id": employee_id},
            )
            if pos_ids:
                conn.execute(
                    text("DELETE FROM public.positions WHERE position_id = ANY(:ids)"),
                    {"ids": pos_ids},
                )


def test_repeat_apply_returns_409(client, privileged_headers, seed):
    pos_ids: List[int] = []
    employee_id = 0
    with engine.begin() as conn:
        org_unit_id = int(seed["unit_id"])
        position_id = _create_position(conn, name=f"WPPO4C-repeat-{uuid4().hex[:8]}")
        pos_ids.append(position_id)
        employee_id = _create_test_employee(
            conn,
            org_unit_id=org_unit_id,
            position_id=position_id,
        )
        row = conn.execute(
            text(
                """
                SELECT org_unit_id, position_id, employment_rate
                FROM public.employees
                WHERE employee_id = :employee_id
                """
            ),
            {"employee_id": employee_id},
        ).mappings().one()

    order_id, _, _ = _create_registered_order_with_item(
        client,
        privileged_headers,
        order_type_code="HIRE",
        item_type_code="HIRE",
        employee_id=employee_id,
        payload={
            "org_unit_id": int(row["org_unit_id"]),
            "position_id": int(row["position_id"]),
            "employment_rate": float(row["employment_rate"] or 1.0),
        },
    )

    try:
        first = client.post(
            f"/directory/personnel-orders/{order_id}/apply",
            headers=privileged_headers,
        )
        assert first.status_code == 200, first.text

        second = client.post(
            f"/directory/personnel-orders/{order_id}/apply",
            headers=privileged_headers,
        )
        assert second.status_code == 409, second.text
        assert _count_events_for_order(order_id) == 1
    finally:
        _cleanup_order(order_id)
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public.employees WHERE employee_id = :employee_id"),
                {"employee_id": employee_id},
            )
            if pos_ids:
                conn.execute(
                    text("DELETE FROM public.positions WHERE position_id = ANY(:ids)"),
                    {"ids": pos_ids},
                )


def test_apply_combo_transfer_item_creates_transfer_and_rate_change(client, privileged_headers, seed):
    pos_ids: List[int] = []
    with engine.begin() as conn:
        if not table_exists(conn, "employee_events"):
            pytest.skip("employee_events table required")
        org_unit_id = int(seed["unit_id"])
        from_pos_id = _create_position(conn, name=f"WPPO4C-from-{uuid4().hex[:8]}")
        to_pos_id = _create_position(conn, name=f"WPPO4C-to-{uuid4().hex[:8]}")
        pos_ids.extend([from_pos_id, to_pos_id])

        employee_id = insert_returning_id(
            conn,
            table="employees",
            id_col="employee_id",
            values={
                "full_name": f"WPPO4C Combo {uuid4().hex[:8]}",
                "org_unit_id": org_unit_id,
                "position_id": from_pos_id,
                "employment_rate": 1.0,
                "is_active": True,
            },
        )

    order_id, item_id, _ = _create_registered_order_with_item(
        client,
        privileged_headers,
        order_type_code="TRANSFER",
        item_type_code="TRANSFER",
        employee_id=employee_id,
        payload={
            "to_position_id": to_pos_id,
            "includes_concurrent_duty": True,
            "concurrent_rate": 0.25,
            "total_rate": 1.25,
        },
        target_status="SIGNED",
    )

    try:
        apply_resp = client.post(
            f"/directory/personnel-orders/{order_id}/apply",
            headers=privileged_headers,
        )
        assert apply_resp.status_code == 200, apply_resp.text
        events = apply_resp.json()["events"]
        assert len(events) == 2
        event_types = sorted(event["event_type"] for event in events)
        assert event_types == ["RATE_CHANGE", "TRANSFER"]
        for event in events:
            assert event["order_id"] == order_id
            assert event["order_item_id"] == item_id
            assert event["order_ref"] is not None

        with engine.begin() as conn:
            rate = conn.execute(
                text(
                    """
                    SELECT employment_rate, position_id
                    FROM public.employees
                    WHERE employee_id = :employee_id
                    """
                ),
                {"employee_id": employee_id},
            ).mappings().one()
            assert int(rate["position_id"]) == to_pos_id
            assert float(rate["employment_rate"]) == 1.25
    finally:
        _cleanup_order(order_id)
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public.employees WHERE employee_id = :employee_id"),
                {"employee_id": employee_id},
            )
            if pos_ids:
                conn.execute(
                    text("DELETE FROM public.positions WHERE position_id = ANY(:ids)"),
                    {"ids": pos_ids},
                )


def test_apply_draft_order_returns_409(client, privileged_headers):
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        employee_id = _pick_employee_id(conn)

    create_resp = client.post(
        "/directory/personnel-orders",
        json={
            "order_number": f"WPPO4C-DRAFT-{suffix}",
            "order_date": "2026-07-07",
            "order_type_code": "HIRE",
        },
        headers=privileged_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    order_id = create_resp.json()["order"]["order_id"]

    try:
        client.post(
            f"/directory/personnel-orders/{order_id}/items",
            json={
                "item_type_code": "HIRE",
                "employee_id": employee_id,
                "effective_date": "2026-07-07",
                "payload": {"employment_rate": 1.0},
            },
            headers=privileged_headers,
        )

        apply_resp = client.post(
            f"/directory/personnel-orders/{order_id}/apply",
            headers=privileged_headers,
        )
        assert apply_resp.status_code == 409, apply_resp.text
        assert _count_events_for_order(order_id) == 0
    finally:
        _cleanup_order(order_id)
