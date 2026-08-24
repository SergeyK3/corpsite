"""Focused API coverage for the two allowed leave DRAFT item codes."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.personnel_orders_command_service import (
    PersonnelOrderConflictError,
    _ensure_order_editable,
)
from tests.conftest import (
    auth_headers,
    create_user,
    get_columns,
    insert_returning_id,
    table_exists,
)


def _scope_exists(order_id: int) -> bool:
    with engine.connect() as conn:
        return bool(
            conn.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM public.personnel_order_evidence_scopes WHERE order_id=:id)"
                ),
                {"id": order_id},
            ).scalar_one()
        )


def _events_for_order(order_id: int) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text("SELECT count(*) FROM public.employee_events WHERE order_id=:id"),
                {"id": order_id},
            ).scalar_one()
        )


def _create_test_employee(conn, *, unit_id: int, suffix: str) -> tuple[int, int]:
    position_values = {"name": f"Pytest leave position {suffix}"}
    if "category" in get_columns(conn, "positions"):
        position_values["category"] = "other"
    position_id = insert_returning_id(
        conn, table="positions", id_col="position_id", values=position_values
    )
    employee_id = insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values={
            "full_name": f"Pytest leave employee {suffix}",
            "org_unit_id": int(unit_id),
            "position_id": position_id,
            "employment_rate": 1.0,
            "is_active": True,
        },
    )
    return employee_id, position_id


def _event_count() -> int:
    with engine.connect() as conn:
        return int(conn.execute(text("SELECT count(*) FROM public.employee_events")).scalar_one())


@pytest.fixture
def leave_draft_context():
    """Own the full minimal org/user graph without relying on canonical deps_group seeds."""
    suffix = uuid4().hex[:8]
    group_id = unit_id = role_id = user_id = None
    try:
        with engine.begin() as conn:
            group_id = insert_returning_id(
                conn,
                table="deps_group",
                id_col="group_id",
                values={"group_name": f"Pytest leave group {suffix}"},
            )
            unit_id = insert_returning_id(
                conn,
                table="org_units",
                id_col="unit_id",
                values={
                    "name": f"Pytest leave unit {suffix}",
                    "code": f"pytest_leave_{suffix}",
                    "group_id": group_id,
                },
            )
            role_id = insert_returning_id(
                conn,
                table="roles",
                id_col="role_id",
                values={
                    "name": f"Pytest leave role {suffix}",
                    "code": f"pytest_leave_{suffix}",
                },
            )
            user_id = create_user(
                conn,
                full_name=f"Pytest leave user {suffix}",
                role_id=role_id,
                unit_id=unit_id,
            )
        yield {"group_id": group_id, "unit_id": unit_id, "role_id": role_id, "user_id": user_id}
    finally:
        with engine.begin() as conn:
            if user_id is not None:
                if table_exists(conn, "access_grants"):
                    conn.execute(
                        text(
                            "DELETE FROM public.access_grants "
                            "WHERE (target_type = 'USER' AND target_id = :user_id) "
                            "OR granted_by_user_id = :user_id"
                        ),
                        {"user_id": user_id},
                    )
                if table_exists(conn, "user_roles"):
                    conn.execute(
                        text("DELETE FROM public.user_roles WHERE user_id = :user_id"),
                        {"user_id": user_id},
                    )
                conn.execute(text("DELETE FROM public.users WHERE user_id = :user_id"), {"user_id": user_id})
            if role_id is not None:
                conn.execute(text("DELETE FROM public.roles WHERE role_id = :role_id"), {"role_id": role_id})
            if unit_id is not None:
                conn.execute(text("DELETE FROM public.org_units WHERE unit_id = :unit_id"), {"unit_id": unit_id})
            if group_id is not None:
                conn.execute(text("DELETE FROM public.deps_group WHERE group_id = :group_id"), {"group_id": group_id})


def _create_leave_draft(client, headers, *, suffix: str, employee_id: int, item_type_code: str, start: str, end: str, payload: dict, created_order_ids: list[int]):
    created = client.post(
        "/directory/personnel-orders",
        json={
            "order_number": f"PYTEST-LEAVE-{suffix}",
            "order_date": start,
            "order_type_code": "COMPOSITE",
            "source_mode": "PAPER",
            "comment": "LOCAL TEST: substituted local employee; no apply",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    order_id = created.json()["order"]["order_id"]
    created_order_ids.append(order_id)
    added = client.post(
        f"/directory/personnel-orders/{order_id}/items",
        json={
            "item_type_code": item_type_code,
            "employee_id": employee_id,
            "effective_date": start,
            "period_start": start,
            "period_end": end,
            "payload": payload,
        },
        headers=headers,
    )
    assert added.status_code == 200, added.text
    return order_id, added.json()["items"][0]["item_id"]


def test_leave_draft_create_read_update_delete_via_api(client, leave_draft_context, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(leave_draft_context["user_id"]))
    headers = auth_headers(leave_draft_context["user_id"])
    baseline_events = _event_count()
    suffix = uuid4().hex[:8]
    created_order_ids: list[int] = []
    created_employee_ids: list[int] = []
    created_position_ids: list[int] = []

    try:
        with engine.begin() as conn:
            annual_employee_id, annual_position_id = _create_test_employee(
                conn, unit_id=int(leave_draft_context["unit_id"]), suffix=f"annual-{suffix}"
            )
            unpaid_employee_id, unpaid_position_id = _create_test_employee(
                conn, unit_id=int(leave_draft_context["unit_id"]), suffix=f"unpaid-{suffix}"
            )
        created_employee_ids.extend((annual_employee_id, unpaid_employee_id))
        created_position_ids.extend((annual_position_id, unpaid_position_id))
        annual_payload = {
            "leave_start": "2026-07-20",
            "leave_end": "2026-08-08",
            "leave_days": 20,
            "work_period_start": "2025-07-20",
            "work_period_end": "2026-07-19",
            "source_order_number": "315-д",
            "source_order_date": "2026-07-02",
        }
        annual_order_id, annual_item_id = _create_leave_draft(
            client, headers, suffix=f"ANNUAL-{suffix}", employee_id=annual_employee_id,
            item_type_code="LEAVE.ANNUAL.GRANT", start="2026-07-20", end="2026-08-08", payload=annual_payload,
            created_order_ids=created_order_ids,
        )
        assert _scope_exists(annual_order_id)
        annual_read = client.get(f"/directory/personnel-orders/{annual_order_id}", headers=headers)
        assert annual_read.status_code == 200, annual_read.text
        assert annual_read.json()["items"][0]["item_type_code"] == "LEAVE.ANNUAL.GRANT"

        annual_payload["leave_end"] = "2026-08-07"
        annual_payload["leave_days"] = 19
        updated = client.patch(
            f"/directory/personnel-orders/{annual_order_id}/items/{annual_item_id}",
            json={"period_end": "2026-08-07", "payload": annual_payload}, headers=headers,
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["items"][0]["period_end"] == "2026-08-07"
        assert updated.json()["items"][0]["payload"]["leave_days"] == 19

        unpaid_payload = {
            "leave_start": "2026-04-09", "leave_end": "2026-04-11",
            "source_order_number": "125-д", "source_order_date": "2026-04-07",
        }
        unpaid_order_id, unpaid_item_id = _create_leave_draft(
            client, headers, suffix=f"UNPAID-{suffix}", employee_id=unpaid_employee_id,
            item_type_code="LEAVE.UNPAID.GRANT", start="2026-04-09", end="2026-04-11", payload=unpaid_payload,
            created_order_ids=created_order_ids,
        )
        unpaid_payload["leave_end"] = "2026-04-10"
        updated = client.patch(
            f"/directory/personnel-orders/{unpaid_order_id}/items/{unpaid_item_id}",
            json={"period_end": "2026-04-10", "payload": unpaid_payload}, headers=headers,
        )
        assert updated.status_code == 200, updated.text
        reread = client.get(f"/directory/personnel-orders/{unpaid_order_id}", headers=headers)
        assert reread.status_code == 200, reread.text
        assert reread.json()["items"][0]["period_end"] == "2026-04-10"
        assert reread.json()["items"][0]["payload"]["source_order_number"] == "125-д"
    finally:
        for order_id in reversed(created_order_ids):
            deleted = client.delete(f"/directory/personnel-orders/{order_id}", headers=headers)
            assert deleted.status_code == 204, deleted.text
            assert not _scope_exists(order_id)
            assert client.get(f"/directory/personnel-orders/{order_id}", headers=headers).status_code == 404
        if created_employee_ids or created_position_ids:
            with engine.begin() as conn:
                if created_employee_ids:
                    linked = conn.execute(
                        text("SELECT count(*) FROM public.personnel_order_items WHERE employee_id = ANY(:ids)"),
                        {"ids": created_employee_ids},
                    ).scalar_one()
                    assert int(linked) == 0
                    conn.execute(
                        text("DELETE FROM public.employees WHERE employee_id = ANY(:ids)"),
                        {"ids": created_employee_ids},
                    )
                if created_position_ids:
                    conn.execute(
                        text("DELETE FROM public.positions WHERE position_id = ANY(:ids)"),
                        {"ids": created_position_ids},
                    )
    assert _event_count() == baseline_events


@pytest.mark.parametrize("status", ["SIGNED", "REGISTERED", "APPROVED", "VOIDED"])
def test_non_draft_orders_are_not_editable_or_physically_deletable(status):
    with pytest.raises(PersonnelOrderConflictError):
        _ensure_order_editable({"order_id": 1, "status": status})