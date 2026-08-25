"""Focused apply coverage for annual-leave personnel-order items."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.personnel_orders_apply_service import _resolve_event_types
from tests.conftest import auth_headers, create_user, get_columns, insert_returning_id, table_exists
from tests.test_wp_po_003_personnel_orders_schema import _delete_personnel_order_audit_rows, _require_schema


pytestmark = pytest.mark.usefixtures("_require_wp_po_003_schema")


@pytest.fixture(scope="module", autouse=True)
def _require_wp_po_003_schema():
    _require_schema()


@pytest.fixture
def annual_leave_context():
    suffix = uuid4().hex[:8]
    group_id = unit_id = role_id = user_id = None
    try:
        with engine.begin() as conn:
            group_id = insert_returning_id(
                conn, table="deps_group", id_col="group_id", values={"group_name": f"annual leave group {suffix}"}
            )
            unit_id = insert_returning_id(
                conn,
                table="org_units",
                id_col="unit_id",
                values={"name": f"annual leave unit {suffix}", "code": f"annual_leave_{suffix}", "group_id": group_id},
            )
            role_id = insert_returning_id(
                conn, table="roles", id_col="role_id", values={"name": f"annual leave role {suffix}", "code": f"annual_leave_{suffix}"}
            )
            user_id = create_user(conn, full_name=f"annual leave user {suffix}", role_id=role_id, unit_id=unit_id)
        yield {"group_id": group_id, "unit_id": unit_id, "role_id": role_id, "user_id": user_id}
    finally:
        with engine.begin() as conn:
            if user_id is not None:
                if table_exists(conn, "access_grants"):
                    conn.execute(text("DELETE FROM public.access_grants WHERE (target_type = 'USER' AND target_id = :user_id) OR granted_by_user_id = :user_id"), {"user_id": user_id})
                if table_exists(conn, "user_roles"):
                    conn.execute(text("DELETE FROM public.user_roles WHERE user_id = :user_id"), {"user_id": user_id})
                conn.execute(text("DELETE FROM public.users WHERE user_id = :user_id"), {"user_id": user_id})
            if role_id is not None:
                conn.execute(text("DELETE FROM public.roles WHERE role_id = :role_id"), {"role_id": role_id})
            if unit_id is not None:
                conn.execute(text("DELETE FROM public.org_units WHERE unit_id = :unit_id"), {"unit_id": unit_id})
            if group_id is not None:
                conn.execute(text("DELETE FROM public.deps_group WHERE group_id = :group_id"), {"group_id": group_id})


@pytest.fixture
def privileged_headers(annual_leave_context, monkeypatch):
    user_id = int(annual_leave_context["user_id"])
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(user_id))
    return auth_headers(user_id)


def _cleanup_order(order_id: int) -> None:
    with engine.begin() as conn:
        _delete_personnel_order_audit_rows(conn, order_id)
        conn.execute(text("DELETE FROM public.employee_events WHERE order_id = :order_id"), {"order_id": order_id})
        conn.execute(text("DELETE FROM public.personnel_order_items WHERE order_id = :order_id"), {"order_id": order_id})
        conn.execute(text("DELETE FROM public.personnel_order_evidence_scopes WHERE order_id = :order_id"), {"order_id": order_id})
        conn.execute(text("DELETE FROM public.personnel_orders WHERE order_id = :order_id"), {"order_id": order_id})


def _create_employee(conn, *, unit_id: int, suffix: str) -> tuple[int, int]:
    values: dict[str, Any] = {"name": f"annual-leave-position-{suffix}"}
    if "category" in get_columns(conn, "positions"):
        values["category"] = "other"
    position_id = insert_returning_id(conn, table="positions", id_col="position_id", values=values)
    employee_id = insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values={
            "full_name": f"Annual leave employee {suffix}",
            "org_unit_id": unit_id,
            "position_id": position_id,
            "employment_rate": 1.0,
            "is_active": True,
        },
    )
    return employee_id, position_id


def _leave_payload(*, start: str, end: str, days: int, description: str = "Source leave description") -> dict[str, Any]:
    return {
        "leave_start": start,
        "leave_end": end,
        "leave_days": days,
        "work_period_start": "2025-07-01",
        "work_period_end": "2026-06-30",
        "source_description": description,
        "acknowledged_at": None,
    }


def _create_registered_order(client, headers, *, items: list[dict[str, Any]]) -> tuple[int, list[int], str]:
    order_number = f"ANNUAL-LEAVE-{uuid4().hex[:8]}"
    created = client.post(
        "/directory/personnel-orders",
        json={
            "order_number": order_number,
            "order_date": "2026-07-08",
            "order_type_code": "COMPOSITE",
            "source_mode": "PAPER",
            "comment": "Еңбек демалысы туралы",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    order_id = int(created.json()["order"]["order_id"])
    item_ids: list[int] = []
    for item in items:
        response = client.post(f"/directory/personnel-orders/{order_id}/items", json=item, headers=headers)
        assert response.status_code == 200, response.text
        item_ids.append(int(response.json()["items"][-1]["item_id"]))
    registered = client.post(
        f"/directory/personnel-orders/{order_id}/register",
        json={"target_status": "REGISTERED"},
        headers=headers,
    )
    assert registered.status_code == 200, registered.text
    return order_id, item_ids, order_number


def _leave_item(employee_id: int, *, start: str, end: str, days: int) -> dict[str, Any]:
    return {
        "item_type_code": "LEAVE.ANNUAL.GRANT",
        "employee_id": employee_id,
        "effective_date": start,
        "period_start": start,
        "period_end": end,
        "payload": _leave_payload(start=start, end=end, days=days),
    }


def test_annual_leave_mapping_does_not_change_existing_apply_mappings():
    assert _resolve_event_types("HIRE", {}) == ["HIRE"]
    assert _resolve_event_types("TERMINATION", {}) == ["TERMINATION"]
    assert _resolve_event_types("TRANSFER", {}) == ["TRANSFER"]
    assert _resolve_event_types("TRANSFER", {"includes_concurrent_duty": True, "concurrent_rate": 0.25}) == [
        "TRANSFER",
        "RATE_CHANGE",
    ]
    assert _resolve_event_types("LEAVE.ANNUAL.GRANT", {}) == ["ANNUAL_LEAVE"]


def test_grouped_annual_leave_apply_creates_one_event_per_item_without_snapshot_changes(
    client, privileged_headers, annual_leave_context
):
    employee_ids: list[int] = []
    position_ids: list[int] = []
    order_id = 0
    try:
        with engine.begin() as conn:
            for _ in range(2):
                employee_id, position_id = _create_employee(conn, unit_id=int(annual_leave_context["unit_id"]), suffix=uuid4().hex[:8])
                employee_ids.append(employee_id)
                position_ids.append(position_id)
            before = {
                int(row["employee_id"]): dict(row)
                for row in conn.execute(
                    text("SELECT employee_id, org_unit_id, position_id, employment_rate FROM public.employees WHERE employee_id = ANY(:ids)"),
                    {"ids": employee_ids},
                ).mappings()
            }

        order_id, item_ids, order_number = _create_registered_order(
            client,
            privileged_headers,
            items=[
                _leave_item(employee_ids[0], start="2026-07-20", end="2026-08-08", days=20),
                _leave_item(employee_ids[1], start="2026-07-27", end="2026-08-16", days=21),
            ],
        )
        applied = client.post(f"/directory/personnel-orders/{order_id}/apply", headers=privileged_headers)
        assert applied.status_code == 200, applied.text
        events = applied.json()["events"]
        assert len(events) == 2
        assert {event["event_type"] for event in events} == {"ANNUAL_LEAVE"}
        assert {event["order_id"] for event in events} == {order_id}
        assert {event["order_item_id"] for event in events} == set(item_ids)
        assert {event["effective_date"] for event in events} == {"2026-07-20", "2026-07-27"}
        for event in events:
            metadata = event["metadata"]
            assert metadata["personnel_order_id"] == order_id
            assert metadata["personnel_order_item_id"] == event["order_item_id"]
            assert metadata["leave_days"] in {20, 21}
            assert "acknowledged_at" not in metadata
            assert event["comment"] == "Source leave description"

        detail = client.get(f"/directory/personnel-orders/{order_id}", headers=privileged_headers)
        assert detail.status_code == 200, detail.text
        assert detail.json()["order"]["comment"] == "Еңбек демалысы туралы"
        assert all(item["payload"]["acknowledged_at"] is None for item in detail.json()["items"])

        journal = client.get("/directory/personnel-events?event_category=LEAVE", headers=privileged_headers)
        assert journal.status_code == 200, journal.text
        assert {event["event_id"] for event in journal.json()["items"]}.issuperset(
            {event["event_id"] for event in events}
        )

        with engine.begin() as conn:
            after = {
                int(row["employee_id"]): dict(row)
                for row in conn.execute(
                    text("SELECT employee_id, org_unit_id, position_id, employment_rate FROM public.employees WHERE employee_id = ANY(:ids)"),
                    {"ids": employee_ids},
                ).mappings()
            }
            author_rows = conn.execute(
                text("SELECT created_by, created_at FROM public.employee_events WHERE order_id = :order_id"),
                {"order_id": order_id},
            ).mappings().all()
        assert after == before
        assert len(author_rows) == 2
        assert all(int(row["created_by"]) == int(annual_leave_context["user_id"]) and row["created_at"] is not None for row in author_rows)

        repeated = client.post(f"/directory/personnel-orders/{order_id}/apply", headers=privileged_headers)
        assert repeated.status_code == 409, repeated.text
        with engine.connect() as conn:
            assert int(conn.execute(text("SELECT count(*) FROM public.employee_events WHERE order_id = :order_id"), {"order_id": order_id}).scalar_one()) == 2
    finally:
        if order_id:
            _cleanup_order(order_id)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM public.employees WHERE employee_id = ANY(:ids)"), {"ids": employee_ids})
            conn.execute(text("DELETE FROM public.positions WHERE position_id = ANY(:ids)"), {"ids": position_ids})


def test_annual_leave_apply_rolls_back_the_whole_group_when_one_item_is_invalid(
    client, privileged_headers, annual_leave_context
):
    employee_ids: list[int] = []
    position_ids: list[int] = []
    order_id = 0
    try:
        with engine.begin() as conn:
            for _ in range(2):
                employee_id, position_id = _create_employee(conn, unit_id=int(annual_leave_context["unit_id"]), suffix=uuid4().hex[:8])
                employee_ids.append(employee_id)
                position_ids.append(position_id)
        order_id, _, _ = _create_registered_order(
            client,
            privileged_headers,
            items=[
                _leave_item(employee_ids[0], start="2026-07-20", end="2026-08-08", days=20),
                _leave_item(employee_ids[1], start="2026-07-27", end="2026-08-16", days=20),
            ],
        )
        applied = client.post(f"/directory/personnel-orders/{order_id}/apply", headers=privileged_headers)
        assert applied.status_code == 422, applied.text
        with engine.connect() as conn:
            assert int(conn.execute(text("SELECT count(*) FROM public.employee_events WHERE order_id = :order_id"), {"order_id": order_id}).scalar_one()) == 0
    finally:
        if order_id:
            _cleanup_order(order_id)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM public.employees WHERE employee_id = ANY(:ids)"), {"ids": employee_ids})
            conn.execute(text("DELETE FROM public.positions WHERE position_id = ANY(:ids)"), {"ids": position_ids})
