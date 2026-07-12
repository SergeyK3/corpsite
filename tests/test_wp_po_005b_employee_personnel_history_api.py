# tests/test_wp_po_005b_employee_personnel_history_api.py
"""API tests for WP-PO-005B employee personnel history tab."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers, get_columns, insert_returning_id, table_exists
from tests.test_wp_po_003_personnel_orders_schema import _delete_personnel_order_audit_rows, _require_schema

pytestmark = pytest.mark.usefixtures("_require_wp_po_003_schema")


@pytest.fixture(scope="module", autouse=True)
def _require_wp_po_003_schema():
    _require_schema()


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


def _db_available() -> bool:
    try:
        with engine.begin() as conn:
            return table_exists(conn, "employee_events")
    except Exception:
        return False


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
    values = {"name": name}
    if "category" in cols:
        values["category"] = "other"
    return insert_returning_id(conn, table="positions", id_col="position_id", values=values)


def _create_test_employee(conn, *, org_unit_id: int, position_id: int) -> int:
    return insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values={
            "full_name": f"WPPO5B {uuid4().hex[:8]}",
            "org_unit_id": org_unit_id,
            "position_id": position_id,
            "employment_rate": 1.0,
            "is_active": True,
        },
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_employee_events_includes_order_linkage(client, seed, privileged_headers):
    pos_ids: list[int] = []
    employee_id = 0
    with engine.begin() as conn:
        if not table_exists(conn, "employee_events"):
            pytest.skip("employee_events table not available")
        cols = get_columns(conn, "employee_events")
        if "order_id" not in cols or "order_item_id" not in cols:
            pytest.skip("employee_events order linkage columns not available")

        org_unit_id = int(seed["unit_id"])
        position_id = _create_position(conn, name=f"WPPO5B pos {uuid4().hex[:6]}")
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

    order_id: int | None = None
    try:
        suffix = uuid4().hex[:8]
        order_number = f"WPPO5B-{suffix}"
        create_resp = client.post(
            "/directory/personnel-orders",
            json={
                "order_number": order_number,
                "order_date": "2026-07-07",
                "order_type_code": "HIRE",
                "source_mode": "PAPER",
            },
            headers=privileged_headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        order_id = create_resp.json()["order"]["order_id"]

        item_resp = client.post(
            f"/directory/personnel-orders/{order_id}/items",
            json={
                "item_type_code": "HIRE",
                "employee_id": employee_id,
                "effective_date": "2026-07-07",
                "payload": {
                    "org_unit_id": int(row["org_unit_id"]),
                    "position_id": int(row["position_id"]),
                    "employment_rate": float(row["employment_rate"] or 1.0),
                },
            },
            headers=privileged_headers,
        )
        assert item_resp.status_code == 200, item_resp.text
        item_id = item_resp.json()["items"][0]["item_id"]

        register_resp = client.post(
            f"/directory/personnel-orders/{order_id}/register",
            json={"target_status": "REGISTERED"},
            headers=privileged_headers,
        )
        assert register_resp.status_code == 200, register_resp.text

        apply_resp = client.post(
            f"/directory/personnel-orders/{order_id}/apply",
            headers=privileged_headers,
        )
        assert apply_resp.status_code == 200, apply_resp.text

        resp = client.get(
            f"/directory/employees/{employee_id}/events",
            headers=privileged_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] >= 1

        linked = next((item for item in body["items"] if item.get("order_id") == order_id), None)
        assert linked is not None, body["items"]
        assert linked["order_item_id"] == item_id
        assert linked["order_number"] == order_number
        assert linked["order_date"] == "2026-07-07"
        assert linked["order_status"] == "REGISTERED"
        assert linked["order_item_number"] == 1
    finally:
        if order_id is not None:
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
