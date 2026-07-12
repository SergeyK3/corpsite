# tests/personnel_orders/characterization/test_personnel_orders_characterization_item_registry.py
"""Characterization: Personnel Orders item type registry and dispatch (UDE-007)."""
from __future__ import annotations

import pytest

from app.db.engine import engine
from app.db.models.personnel_orders import MVP_ITEM_TYPE_CODES
from app.services.personnel_orders_command_service import PersonnelOrderValidationError
from tests.personnel_orders.characterization._helpers import (
    cleanup_order,
    create_draft_order,
    create_hire_item,
    unique_suffix,
)
from tests.test_wp_po_003_personnel_orders_schema import _pick_employee_id

pytestmark = pytest.mark.usefixtures("_require_po_characterization_schema")


@pytest.mark.parametrize(
    "item_type",
    [
        "HIRE",
        "TRANSFER",
        "TERMINATION",
        "CONCURRENT_DUTY_START",
        "CONCURRENT_DUTY_END",
    ],
)
def test_personnel_orders_characterization_item_type_registration(
    client, privileged_headers, item_type: str
) -> None:
    assert item_type in MVP_ITEM_TYPE_CODES
    order_id = create_draft_order(client, privileged_headers, suffix=unique_suffix())
    try:
        employee_id = None
        if item_type != "HIRE":
            with engine.begin() as conn:
                employee_id = _pick_employee_id(conn)
        item_id = create_hire_item(
            client,
            privileged_headers,
            order_id,
            employee_id=employee_id,
            item_type=item_type,
        )
        detail = client.get(
            f"/directory/personnel-orders/{order_id}",
            headers=privileged_headers,
        )
        assert detail.status_code == 200, detail.text
        items = detail.json()["items"]
        assert any(item["item_id"] == item_id and item["item_type_code"] == item_type for item in items)
    finally:
        cleanup_order(order_id)


def test_personnel_orders_characterization_unknown_item_type_rejected(
    client, privileged_headers
) -> None:
    order_id = create_draft_order(client, privileged_headers, suffix=unique_suffix())
    try:
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/items",
            json={
                "item_type_code": "BONUS",
                "effective_date": "2026-07-12",
                "payload": {},
            },
            headers=privileged_headers,
        )
        assert resp.status_code == 422, resp.text
        message = str(resp.json().get("detail", resp.json().get("message", "")))
        assert "Invalid item_type_code" in message
    finally:
        cleanup_order(order_id)


def test_personnel_orders_characterization_rate_change_is_not_backend_item_type(
    client, privileged_headers
) -> None:
    """RATE_CHANGE is a UI alias; backend rejects it as item_type_code."""
    order_id = create_draft_order(client, privileged_headers, suffix=unique_suffix())
    try:
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/items",
            json={
                "item_type_code": "RATE_CHANGE",
                "effective_date": "2026-07-12",
                "payload": {"to_rate": 0.5},
            },
            headers=privileged_headers,
        )
        assert resp.status_code == 422, resp.text
    finally:
        cleanup_order(order_id)


def test_personnel_orders_characterization_command_service_normalizes_item_types() -> None:
    from app.services.personnel_orders_command_service import _normalize_item_type

    assert _normalize_item_type("hire") == "HIRE"
    with pytest.raises(PersonnelOrderValidationError, match="Invalid item_type_code"):
        _normalize_item_type("BONUS")
