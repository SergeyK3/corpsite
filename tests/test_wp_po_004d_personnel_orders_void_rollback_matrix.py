# tests/test_wp_po_004d_personnel_orders_void_rollback_matrix.py
"""Rollback matrix: HIRE / TRANSFER / TERMINATION × pre_apply_state present / legacy."""
from __future__ import annotations

from datetime import date
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
            "full_name": f"WPPO4D-matrix {uuid4().hex[:8]}",
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
                SELECT org_unit_id, position_id, employment_rate, is_active, date_from, date_to
                FROM public.employees
                WHERE employee_id = :employee_id
                """
            ),
            {"employee_id": employee_id},
        ).mappings().one()
    )


def _create_registered_order(client, privileged_headers, *, order_type_code: str) -> int:
    create_resp = client.post(
        "/directory/personnel-orders",
        json={
            "order_number": f"WPPO4D-M-{uuid4().hex[:8]}",
            "order_date": "2026-07-07",
            "order_type_code": order_type_code,
            "source_mode": "PAPER",
        },
        headers=privileged_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    return int(create_resp.json()["order"]["order_id"])


def _add_item(
    client,
    privileged_headers,
    *,
    order_id: int,
    item_type_code: str,
    employee_id: int,
    payload: Dict[str, Any],
) -> int:
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
    return int(item_resp.json()["items"][-1]["item_id"])


def _register_and_apply(client, privileged_headers, order_id: int) -> Dict[str, Any]:
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
    return apply_resp.json()


def _strip_pre_apply_state(conn, event_id: int) -> None:
    conn.execute(
        text(
            """
            UPDATE public.employee_events
            SET metadata = metadata - 'pre_apply_state'
            WHERE event_id = :event_id
            """
        ),
        {"event_id": int(event_id)},
    )


def _void_order(client, privileged_headers, order_id: int) -> None:
    void_resp = client.post(
        f"/directory/personnel-orders/{order_id}/void",
        json={"void_reason": "Rollback matrix void"},
        headers=privileged_headers,
    )
    assert void_resp.status_code == 200, void_resp.text


def test_rollback_matrix_hire_with_snapshot(client, privileged_headers, seed):
    """HIRE + snapshot → rollback по pre_apply_state."""
    pos_ids: List[int] = []
    employee_id = 0
    with engine.begin() as conn:
        org_unit_id = int(seed["unit_id"])
        position_id = _create_position(conn, name=f"matrix-hire-snap-{uuid4().hex[:6]}")
        pos_ids.append(position_id)
        employee_id = _create_test_employee(conn, org_unit_id=org_unit_id, position_id=position_id)
        before = _employee_snapshot(conn, employee_id)

    order_id = _create_registered_order(client, privileged_headers, order_type_code="HIRE")
    try:
        _add_item(
            client,
            privileged_headers,
            order_id=order_id,
            item_type_code="HIRE",
            employee_id=employee_id,
            payload={
                "org_unit_id": int(before["org_unit_id"]),
                "position_id": int(before["position_id"]),
                "employment_rate": float(before["employment_rate"] or 1.0),
            },
        )
        apply_body = _register_and_apply(client, privileged_headers, order_id)
        pre_apply_state = (apply_body["events"][0].get("metadata") or {}).get("pre_apply_state") or {}
        assert pre_apply_state.get("had_prior_employment_events") is False

        _void_order(client, privileged_headers, order_id)

        with engine.begin() as conn:
            after = _employee_snapshot(conn, employee_id)
        assert bool(after["is_active"]) is False
        assert int(after["position_id"]) == int(before["position_id"])
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


def test_rollback_matrix_hire_legacy_without_snapshot(client, privileged_headers, seed):
    """HIRE + no snapshot → legacy fallback (deactivate when sole APPROVED event)."""
    pos_ids: List[int] = []
    employee_id = 0
    with engine.begin() as conn:
        org_unit_id = int(seed["unit_id"])
        position_id = _create_position(conn, name=f"matrix-hire-leg-{uuid4().hex[:6]}")
        pos_ids.append(position_id)
        employee_id = _create_test_employee(conn, org_unit_id=org_unit_id, position_id=position_id)
        before = _employee_snapshot(conn, employee_id)

    order_id = _create_registered_order(client, privileged_headers, order_type_code="HIRE")
    try:
        _add_item(
            client,
            privileged_headers,
            order_id=order_id,
            item_type_code="HIRE",
            employee_id=employee_id,
            payload={
                "org_unit_id": int(before["org_unit_id"]),
                "position_id": int(before["position_id"]),
                "employment_rate": float(before["employment_rate"] or 1.0),
            },
        )
        apply_body = _register_and_apply(client, privileged_headers, order_id)
        event_id = int(apply_body["events"][0]["event_id"])
        with engine.begin() as conn:
            _strip_pre_apply_state(conn, event_id)

        _void_order(client, privileged_headers, order_id)

        with engine.begin() as conn:
            after = _employee_snapshot(conn, employee_id)
        assert bool(after["is_active"]) is False
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


def test_rollback_matrix_transfer_with_snapshot(client, privileged_headers, seed):
    """TRANSFER + snapshot → rollback по pre_apply_state (игнорирует испорченные from_*)."""
    pos_ids: List[int] = []
    employee_id = 0
    with engine.begin() as conn:
        org_unit_id = int(seed["unit_id"])
        from_position_id = _create_position(conn, name=f"matrix-xfer-from-{uuid4().hex[:6]}")
        to_position_id = _create_position(conn, name=f"matrix-xfer-to-{uuid4().hex[:6]}")
        decoy_position_id = _create_position(conn, name=f"matrix-xfer-decoy-{uuid4().hex[:6]}")
        pos_ids.extend([from_position_id, to_position_id, decoy_position_id])
        employee_id = _create_test_employee(
            conn, org_unit_id=org_unit_id, position_id=from_position_id
        )
        before = _employee_snapshot(conn, employee_id)

    order_id = _create_registered_order(client, privileged_headers, order_type_code="TRANSFER")
    try:
        _add_item(
            client,
            privileged_headers,
            order_id=order_id,
            item_type_code="TRANSFER",
            employee_id=employee_id,
            payload={"to_position_id": to_position_id},
        )
        apply_body = _register_and_apply(client, privileged_headers, order_id)
        event_id = int(apply_body["events"][0]["event_id"])
        assert (apply_body["events"][0].get("metadata") or {}).get("pre_apply_state")

        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE public.employee_events
                    SET from_position_id = :decoy_position_id
                    WHERE event_id = :event_id
                    """
                ),
                {"event_id": event_id, "decoy_position_id": decoy_position_id},
            )

        _void_order(client, privileged_headers, order_id)

        with engine.begin() as conn:
            after = _employee_snapshot(conn, employee_id)
        assert int(after["position_id"]) == int(before["position_id"])
        assert int(after["org_unit_id"]) == int(before["org_unit_id"])
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


def test_rollback_matrix_transfer_legacy_without_snapshot(client, privileged_headers, seed):
    """TRANSFER + no snapshot → старая логика from_*."""
    pos_ids: List[int] = []
    employee_id = 0
    with engine.begin() as conn:
        org_unit_id = int(seed["unit_id"])
        from_position_id = _create_position(conn, name=f"matrix-xfer-lfrom-{uuid4().hex[:6]}")
        to_position_id = _create_position(conn, name=f"matrix-xfer-lto-{uuid4().hex[:6]}")
        pos_ids.extend([from_position_id, to_position_id])
        employee_id = _create_test_employee(
            conn, org_unit_id=org_unit_id, position_id=from_position_id
        )
        before = _employee_snapshot(conn, employee_id)

    order_id = _create_registered_order(client, privileged_headers, order_type_code="TRANSFER")
    try:
        _add_item(
            client,
            privileged_headers,
            order_id=order_id,
            item_type_code="TRANSFER",
            employee_id=employee_id,
            payload={"to_position_id": to_position_id},
        )
        apply_body = _register_and_apply(client, privileged_headers, order_id)
        event_id = int(apply_body["events"][0]["event_id"])
        with engine.begin() as conn:
            _strip_pre_apply_state(conn, event_id)

        _void_order(client, privileged_headers, order_id)

        with engine.begin() as conn:
            after = _employee_snapshot(conn, employee_id)
        assert int(after["position_id"]) == int(before["position_id"])
        assert int(after["org_unit_id"]) == int(before["org_unit_id"])
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


def test_rollback_matrix_termination_with_snapshot(client, privileged_headers, seed):
    """TERMINATION + snapshot → rollback по pre_apply_state."""
    pos_ids: List[int] = []
    employee_id = 0
    with engine.begin() as conn:
        org_unit_id = int(seed["unit_id"])
        position_id = _create_position(conn, name=f"matrix-term-snap-{uuid4().hex[:6]}")
        pos_ids.append(position_id)
        employee_id = _create_test_employee(conn, org_unit_id=org_unit_id, position_id=position_id)
        before = _employee_snapshot(conn, employee_id)

    order_id = _create_registered_order(client, privileged_headers, order_type_code="TERMINATION")
    try:
        _add_item(
            client,
            privileged_headers,
            order_id=order_id,
            item_type_code="TERMINATION",
            employee_id=employee_id,
            payload={"termination_reason": "agreement"},
        )
        apply_body = _register_and_apply(client, privileged_headers, order_id)
        assert (apply_body["events"][0].get("metadata") or {}).get("pre_apply_state")

        with engine.begin() as conn:
            terminated = _employee_snapshot(conn, employee_id)
        assert bool(terminated["is_active"]) is False
        assert terminated["date_to"] is not None

        _void_order(client, privileged_headers, order_id)

        with engine.begin() as conn:
            after = _employee_snapshot(conn, employee_id)
        assert bool(after["is_active"]) == bool(before["is_active"])
        assert after["date_to"] == before["date_to"]
        assert int(after["position_id"]) == int(before["position_id"])
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


def test_rollback_matrix_termination_legacy_without_snapshot(client, privileged_headers, seed):
    """TERMINATION + no snapshot → старая логика (is_active=TRUE, date_to=NULL)."""
    pos_ids: List[int] = []
    employee_id = 0
    with engine.begin() as conn:
        org_unit_id = int(seed["unit_id"])
        position_id = _create_position(conn, name=f"matrix-term-leg-{uuid4().hex[:6]}")
        pos_ids.append(position_id)
        employee_id = _create_test_employee(conn, org_unit_id=org_unit_id, position_id=position_id)

    order_id = _create_registered_order(client, privileged_headers, order_type_code="TERMINATION")
    try:
        _add_item(
            client,
            privileged_headers,
            order_id=order_id,
            item_type_code="TERMINATION",
            employee_id=employee_id,
            payload={"termination_reason": "agreement"},
        )
        apply_body = _register_and_apply(client, privileged_headers, order_id)
        event_id = int(apply_body["events"][0]["event_id"])
        with engine.begin() as conn:
            _strip_pre_apply_state(conn, event_id)

        _void_order(client, privileged_headers, order_id)

        with engine.begin() as conn:
            after = _employee_snapshot(conn, employee_id)
        assert bool(after["is_active"]) is True
        assert after["date_to"] is None
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
