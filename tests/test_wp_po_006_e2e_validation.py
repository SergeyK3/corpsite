# tests/test_wp_po_006_e2e_validation.py
"""WP-PO-006 end-to-end validation for personnel orders P0 flow."""
from __future__ import annotations

from typing import Any, Dict, List
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
            "full_name": f"WPPO6 {uuid4().hex[:8]}",
            "org_unit_id": org_unit_id,
            "position_id": position_id,
            "employment_rate": rate,
            "is_active": True,
        },
    )


def _employee_snapshot(conn, employee_id: int) -> Dict[str, Any]:
    return dict(
        conn.execute(
            text(
                """
                SELECT org_unit_id, position_id, employment_rate, is_active
                FROM public.employees
                WHERE employee_id = :employee_id
                """
            ),
            {"employee_id": employee_id},
        ).mappings().one()
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_wp_po_006_p0_transfer_apply_history_journal_void_rollback(client, seed, privileged_headers):
    """Full P0 path: create → item → register → apply → history/journal → void → rollback."""
    pos_ids: List[int] = []
    employee_id = 0
    from_position_id = 0
    to_position_id = 0

    with engine.begin() as conn:
        cols = get_columns(conn, "employee_events")
        if "order_id" not in cols or "order_item_id" not in cols:
            pytest.skip("employee_events order linkage columns not available")

        org_unit_id = int(seed["unit_id"])
        from_position_id = _create_position(conn, name=f"WPPO6-from-{uuid4().hex[:6]}")
        to_position_id = _create_position(conn, name=f"WPPO6-to-{uuid4().hex[:6]}")
        pos_ids.extend([from_position_id, to_position_id])
        employee_id = _create_test_employee(
            conn,
            org_unit_id=org_unit_id,
            position_id=from_position_id,
            rate=1.0,
        )
        before_snapshot = _employee_snapshot(conn, employee_id)

    order_id: int | None = None
    order_number = f"WPPO6-{uuid4().hex[:8]}"
    try:
        create_resp = client.post(
            "/directory/personnel-orders",
            json={
                "order_number": order_number,
                "order_date": "2026-07-07",
                "order_type_code": "TRANSFER",
                "source_mode": "PAPER",
            },
            headers=privileged_headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        order_id = create_resp.json()["order"]["order_id"]
        assert create_resp.json()["order"]["status"] == "DRAFT"

        item_resp = client.post(
            f"/directory/personnel-orders/{order_id}/items",
            json={
                "item_type_code": "TRANSFER",
                "employee_id": employee_id,
                "effective_date": "2026-07-07",
                "payload": {
                    "to_position_id": to_position_id,
                    "includes_concurrent_duty": False,
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
        assert register_resp.json()["order"]["status"] == "REGISTERED"

        apply_resp = client.post(
            f"/directory/personnel-orders/{order_id}/apply",
            headers=privileged_headers,
        )
        assert apply_resp.status_code == 200, apply_resp.text
        apply_body = apply_resp.json()
        assert len(apply_body["events"]) == 1
        assert apply_body["events"][0]["event_type"] == "TRANSFER"
        assert apply_body["events"][0]["order_id"] == order_id
        assert apply_body["events"][0]["order_item_id"] == item_id

        with engine.begin() as conn:
            after_apply_snapshot = _employee_snapshot(conn, employee_id)
        assert int(after_apply_snapshot["position_id"]) == to_position_id
        assert int(after_apply_snapshot["org_unit_id"]) == int(before_snapshot["org_unit_id"])

        history_resp = client.get(
            f"/directory/employees/{employee_id}/events",
            headers=privileged_headers,
        )
        assert history_resp.status_code == 200, history_resp.text
        history_body = history_resp.json()
        linked_event = next(
            (item for item in history_body["items"] if item.get("order_id") == order_id),
            None,
        )
        assert linked_event is not None, history_body["items"]
        assert linked_event["order_item_id"] == item_id
        assert linked_event["order_number"] == order_number
        assert linked_event["lifecycle_status"] == "APPROVED"

        journal_resp = client.get(
            "/directory/personnel-orders",
            params={"employee_id": employee_id},
            headers=privileged_headers,
        )
        assert journal_resp.status_code == 200, journal_resp.text
        journal_items = journal_resp.json()["items"]
        journal_row = next((row for row in journal_items if row["order_id"] == order_id), None)
        assert journal_row is not None, journal_items
        assert journal_row["order_number"] == order_number
        assert journal_row["status"] == "REGISTERED"
        assert employee_id in journal_row["employee_ids"]

        detail_resp = client.get(
            f"/directory/personnel-orders/{order_id}",
            headers=privileged_headers,
        )
        assert detail_resp.status_code == 200, detail_resp.text
        assert len(detail_resp.json()["events"]) == 1

        void_resp = client.post(
            f"/directory/personnel-orders/{order_id}/void",
            json={"void_reason": "WP-PO-006 rollback validation"},
            headers=privileged_headers,
        )
        assert void_resp.status_code == 200, void_resp.text
        void_body = void_resp.json()
        assert void_body["order"]["status"] == "VOIDED"
        assert all(item["item_status"] == "VOIDED" for item in void_body["items"])
        assert all(event["lifecycle_status"] == "VOIDED" for event in void_body["events"])

        history_after_void = client.get(
            f"/directory/employees/{employee_id}/events",
            headers=privileged_headers,
        ).json()
        voided_event = next(
            (item for item in history_after_void["items"] if item.get("order_id") == order_id),
            None,
        )
        assert voided_event is not None
        assert voided_event["lifecycle_status"] == "VOIDED"

        journal_after_void = client.get(
            "/directory/personnel-orders",
            params={"employee_id": employee_id, "status": "VOIDED"},
            headers=privileged_headers,
        ).json()
        assert any(row["order_id"] == order_id for row in journal_after_void["items"])

        with engine.begin() as conn:
            after_void_snapshot = _employee_snapshot(conn, employee_id)
        assert int(after_void_snapshot["position_id"]) == int(before_snapshot["position_id"])
        assert float(after_void_snapshot["employment_rate"]) == float(before_snapshot["employment_rate"])
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


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_wp_po_006_p0_cancel_draft_without_side_effects(client, seed, privileged_headers):
    """Cancel path: draft order void does not create employee_events or mutate snapshot."""
    pos_ids: List[int] = []
    employee_id = 0

    with engine.begin() as conn:
        org_unit_id = int(seed["unit_id"])
        position_id = _create_position(conn, name=f"WPPO6-cancel-{uuid4().hex[:6]}")
        pos_ids.append(position_id)
        employee_id = _create_test_employee(
            conn,
            org_unit_id=org_unit_id,
            position_id=position_id,
        )
        before_snapshot = _employee_snapshot(conn, employee_id)

    order_id: int | None = None
    try:
        create_resp = client.post(
            "/directory/personnel-orders",
            json={
                "order_number": f"WPPO6-CANCEL-{uuid4().hex[:8]}",
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
                    "org_unit_id": int(before_snapshot["org_unit_id"]),
                    "position_id": int(before_snapshot["position_id"]),
                    "employment_rate": float(before_snapshot["employment_rate"] or 1.0),
                },
            },
            headers=privileged_headers,
        )
        assert item_resp.status_code == 200, item_resp.text

        void_resp = client.post(
            f"/directory/personnel-orders/{order_id}/void",
            json={"void_reason": "Draft cancelled in WP-PO-006"},
            headers=privileged_headers,
        )
        assert void_resp.status_code == 200, void_resp.text
        assert void_resp.json()["order"]["status"] == "VOIDED"
        assert void_resp.json()["events"] == []

        history_resp = client.get(
            f"/directory/employees/{employee_id}/events",
            headers=privileged_headers,
        )
        assert history_resp.status_code == 200, history_resp.text
        assert not any(item.get("order_id") == order_id for item in history_resp.json()["items"])

        with engine.begin() as conn:
            after_snapshot = _employee_snapshot(conn, employee_id)
        assert int(after_snapshot["position_id"]) == int(before_snapshot["position_id"])
        assert bool(after_snapshot["is_active"]) == bool(before_snapshot["is_active"])
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
