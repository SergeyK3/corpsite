from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.personnel_order_acknowledgement_service import (
    PersonnelOrderAcknowledgementError,
    clear,
    list_current,
    record,
)
from tests.conftest import auth_headers


def test_acknowledgement_events_are_append_only_per_order_employee_and_do_not_create_hr_events() -> None:
    """One subject with two items still has one current acknowledgement stream."""
    order_id = None
    with engine.begin() as conn:
        user_id = conn.execute(text("SELECT user_id FROM users ORDER BY user_id LIMIT 1")).scalar_one()
        employee_id = conn.execute(text("SELECT employee_id FROM employees ORDER BY employee_id LIMIT 1")).scalar_one()
        order_id = conn.execute(text("""
            INSERT INTO personnel_orders(order_number,order_date,order_type_code,order_class,status,source_mode,created_by)
            VALUES (:number,:day,'COMPOSITE','PERSONNEL','DRAFT','PAPER',:user_id) RETURNING order_id
        """), {"number": f"ACK-{uuid4().hex}", "day": date.today() - timedelta(days=2), "user_id": user_id}).scalar_one()
        for number in (1, 2):
            conn.execute(text("""
              INSERT INTO personnel_order_items(order_id,item_number,item_type_code,employee_id,item_status,payload)
              VALUES (:order_id,:number,'HIRE',:employee_id,'ACTIVE','{}'::jsonb)
            """), {"order_id": order_id, "number": number, "employee_id": employee_id})
        before_events = conn.execute(text("SELECT count(*) FROM employee_events WHERE order_id=:id"), {"id": order_id}).scalar_one()
    try:
        day = date.today() - timedelta(days=1)
        first = record(order_id, employee_id, day, user_id)
        assert first["item"]["event_type"] == "RECORDED"
        same = record(order_id, employee_id, day, user_id)
        assert same["idempotent"] is True
        corrected = record(order_id, employee_id, date.today(), user_id)
        assert corrected["item"]["event_type"] == "CORRECTED"
        cleared = clear(order_id, employee_id, user_id)
        assert cleared["item"]["event_type"] == "CLEARED"
        assert list_current(order_id)["items"][0]["acknowledged_on"] is None
        with pytest.raises(PersonnelOrderAcknowledgementError, match="NOT_IN_ACTIVE_ORDER"):
            record(order_id, employee_id + 999999, day, user_id)
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM employee_events WHERE order_id=:id"), {"id": order_id}).scalar_one() == before_events
            assert conn.execute(text("SELECT count(*) FROM personnel_order_acknowledgement_events WHERE order_id=:id"), {"id": order_id}).scalar_one() == 3
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM personnel_order_acknowledgement_events WHERE order_id=:id"), {"id": order_id})
            conn.execute(text("DELETE FROM personnel_order_items WHERE order_id=:id"), {"id": order_id})
            conn.execute(text("DELETE FROM personnel_orders WHERE order_id=:id"), {"id": order_id})


def test_non_privileged_employee_cannot_mutate_acknowledgements(client, seed) -> None:
    response = client.post(
        "/directory/personnel-orders/1/acknowledgements",
        json={"employee_id": 1, "acknowledged_on": date.today().isoformat()},
        headers=auth_headers(seed["initiator_user_id"]),
    )
    assert response.status_code == 403
