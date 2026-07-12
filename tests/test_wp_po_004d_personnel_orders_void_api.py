# tests/test_wp_po_004d_personnel_orders_void_api.py
"""API tests for WP-PO-004D personnel orders void/cancel endpoints."""
from __future__ import annotations

from typing import Any, Dict, List
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers, get_columns, insert_returning_id
from tests.test_wp_po_003_personnel_orders_schema import _delete_personnel_order_audit_rows, _require_schema

pytestmark = pytest.mark.usefixtures("_require_wp_po_003_schema")


@pytest.fixture(scope="module", autouse=True)
def _require_wp_po_003_schema():
    _require_schema()


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


def _cleanup_order(order_id: int) -> None:
    with engine.begin() as conn:
        _delete_personnel_order_audit_rows(conn, order_id)
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


def _create_position(conn, *, name: str) -> int:
    cols = get_columns(conn, "positions")
    values: Dict[str, Any] = {"name": name}
    if "category" in cols:
        values["category"] = "other"
    return insert_returning_id(conn, table="positions", id_col="position_id", values=values)


def _create_test_employee(conn, *, org_unit_id: int, position_id: int, rate: float = 1.0) -> int:
    return insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values={
            "full_name": f"WPPO4D {uuid4().hex[:8]}",
            "org_unit_id": org_unit_id,
            "position_id": position_id,
            "employment_rate": rate,
            "is_active": True,
        },
    )


def _create_registered_order(
    client,
    privileged_headers,
    *,
    order_type_code: str,
    target_status: str = "REGISTERED",
) -> tuple[int, str]:
    suffix = uuid4().hex[:8]
    order_number = f"WPPO4D-{suffix}"
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
    return create_resp.json()["order"]["order_id"], order_number


def _add_item(
    client,
    privileged_headers,
    *,
    order_id: int,
    item_type_code: str,
    employee_id: int,
    payload: Dict[str, Any],
    item_number: int | None = None,
) -> int:
    body: Dict[str, Any] = {
        "item_type_code": item_type_code,
        "employee_id": employee_id,
        "effective_date": "2026-07-07",
        "payload": payload,
    }
    if item_number is not None:
        body["item_number"] = item_number
    item_resp = client.post(
        f"/directory/personnel-orders/{order_id}/items",
        json=body,
        headers=privileged_headers,
    )
    assert item_resp.status_code == 200, item_resp.text
    items = item_resp.json()["items"]
    return items[-1]["item_id"]


def test_cancel_draft_order_without_events(client, privileged_headers, seed):
    pos_ids: List[int] = []
    employee_ids: List[int] = []
    with engine.begin() as conn:
        org_unit_id = int(seed["unit_id"])
        position_id = _create_position(conn, name=f"WPPO4D-draft-{uuid4().hex[:8]}")
        pos_ids.append(position_id)
        employee_ids.append(
            _create_test_employee(conn, org_unit_id=org_unit_id, position_id=position_id)
        )

    order_id, _ = _create_registered_order(
        client,
        privileged_headers,
        order_type_code="HIRE",
    )
    try:
        _add_item(
            client,
            privileged_headers,
            order_id=order_id,
            item_type_code="HIRE",
            employee_id=employee_ids[0],
            payload={"employment_rate": 1.0},
        )

        void_resp = client.post(
            f"/directory/personnel-orders/{order_id}/void",
            json={"void_reason": "Draft cancelled by test"},
            headers=privileged_headers,
        )
        assert void_resp.status_code == 200, void_resp.text
        body = void_resp.json()
        assert body["order"]["status"] == "VOIDED"
        assert body["order"]["void_reason"] == "Draft cancelled by test"
        assert body["order"]["voided_at"] is not None
        assert body["order"]["voided_by"] is not None
        assert all(item["item_status"] == "VOIDED" for item in body["items"])
        assert body["events"] == []

        repeat = client.post(
            f"/directory/personnel-orders/{order_id}/void",
            json={"void_reason": "Again"},
            headers=privileged_headers,
        )
        assert repeat.status_code == 409, repeat.text
    finally:
        _cleanup_order(order_id)
        with engine.begin() as conn:
            for employee_id in employee_ids:
                conn.execute(
                    text("DELETE FROM public.employees WHERE employee_id = :employee_id"),
                    {"employee_id": employee_id},
                )
            if pos_ids:
                conn.execute(
                    text("DELETE FROM public.positions WHERE position_id = ANY(:ids)"),
                    {"ids": pos_ids},
                )


def test_void_applied_order_cascades_events(client, privileged_headers, seed):
    pos_ids: List[int] = []
    employee_id = 0
    with engine.begin() as conn:
        org_unit_id = int(seed["unit_id"])
        position_id = _create_position(conn, name=f"WPPO4D-full-{uuid4().hex[:8]}")
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

    order_id, _ = _create_registered_order(client, privileged_headers, order_type_code="HIRE")
    try:
        _add_item(
            client,
            privileged_headers,
            order_id=order_id,
            item_type_code="HIRE",
            employee_id=employee_id,
            payload={
                "org_unit_id": int(row["org_unit_id"]),
                "position_id": int(row["position_id"]),
                "employment_rate": float(row["employment_rate"] or 1.0),
            },
        )
        client.post(f"/directory/personnel-orders/{order_id}/register", json={"target_status": "REGISTERED"}, headers=privileged_headers)
        apply_resp = client.post(f"/directory/personnel-orders/{order_id}/apply", headers=privileged_headers)
        assert apply_resp.status_code == 200, apply_resp.text
        assert len(apply_resp.json()["events"]) == 1

        void_resp = client.post(
            f"/directory/personnel-orders/{order_id}/void",
            json={"void_reason": "Full order void test"},
            headers=privileged_headers,
        )
        assert void_resp.status_code == 200, void_resp.text
        body = void_resp.json()
        assert body["order"]["status"] == "VOIDED"
        assert body["order"]["void_reason"] == "Full order void test"
        assert all(item["item_status"] == "VOIDED" for item in body["items"])
        assert all(event["lifecycle_status"] == "VOIDED" for event in body["events"])

        repeat = client.post(
            f"/directory/personnel-orders/{order_id}/void",
            json={"void_reason": "Repeat"},
            headers=privileged_headers,
        )
        assert repeat.status_code == 409, repeat.text
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


def test_partial_item_void_keeps_order_active(client, privileged_headers, seed):
    pos_ids: List[int] = []
    employee_ids: List[int] = []
    with engine.begin() as conn:
        org_unit_id = int(seed["unit_id"])
        for label in ("a", "b"):
            position_id = _create_position(conn, name=f"WPPO4D-partial-{label}-{uuid4().hex[:8]}")
            pos_ids.append(position_id)
            employee_ids.append(
                _create_test_employee(conn, org_unit_id=org_unit_id, position_id=position_id)
            )

    payloads: List[Dict[str, Any]] = []
    with engine.begin() as conn:
        for employee_id in employee_ids:
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
            payloads.append(
                {
                    "org_unit_id": int(row["org_unit_id"]),
                    "position_id": int(row["position_id"]),
                    "employment_rate": float(row["employment_rate"] or 1.0),
                }
            )

    order_id, _ = _create_registered_order(client, privileged_headers, order_type_code="HIRE")
    try:
        item_ids = []
        for idx, employee_id in enumerate(employee_ids):
            item_ids.append(
                _add_item(
                    client,
                    privileged_headers,
                    order_id=order_id,
                    item_type_code="HIRE",
                    employee_id=employee_id,
                    payload=payloads[idx],
                    item_number=idx + 1,
                )
            )

        client.post(
            f"/directory/personnel-orders/{order_id}/register",
            json={"target_status": "REGISTERED"},
            headers=privileged_headers,
        )
        apply_resp = client.post(f"/directory/personnel-orders/{order_id}/apply", headers=privileged_headers)
        assert apply_resp.status_code == 200, apply_resp.text
        assert len(apply_resp.json()["events"]) == 2

        void_item_resp = client.post(
            f"/directory/personnel-orders/{order_id}/items/{item_ids[0]}/void",
            json={"void_reason": "Partial item void"},
            headers=privileged_headers,
        )
        assert void_item_resp.status_code == 200, void_item_resp.text
        body = void_item_resp.json()
        assert body["order"]["status"] == "REGISTERED"
        assert body["order"]["void_reason"] is None

        items_by_id = {item["item_id"]: item for item in body["items"]}
        assert items_by_id[item_ids[0]]["item_status"] == "VOIDED"
        assert items_by_id[item_ids[0]]["void_reason"] == "Partial item void"
        assert items_by_id[item_ids[1]]["item_status"] == "ACTIVE"

        events_by_item = {event["order_item_id"]: event for event in body["events"]}
        assert events_by_item[item_ids[0]]["lifecycle_status"] == "VOIDED"
        assert events_by_item[item_ids[1]]["lifecycle_status"] == "APPROVED"

        repeat_item = client.post(
            f"/directory/personnel-orders/{order_id}/items/{item_ids[0]}/void",
            json={"void_reason": "Again"},
            headers=privileged_headers,
        )
        assert repeat_item.status_code == 409, repeat_item.text
    finally:
        _cleanup_order(order_id)
        with engine.begin() as conn:
            for employee_id in employee_ids:
                conn.execute(
                    text("DELETE FROM public.employees WHERE employee_id = :employee_id"),
                    {"employee_id": employee_id},
                )
            if pos_ids:
                conn.execute(
                    text("DELETE FROM public.positions WHERE position_id = ANY(:ids)"),
                    {"ids": pos_ids},
                )
