# tests/personnel_orders/characterization/test_personnel_orders_characterization_hire.py
"""Characterization: Personnel Orders HIRE new-employee path (UDE-007)."""
from __future__ import annotations

import pytest

from tests.personnel_orders.characterization._helpers import (
    cleanup_order,
    create_draft_order,
    create_hire_item,
    unique_suffix,
)

pytestmark = pytest.mark.usefixtures("_require_po_characterization_schema")


def test_personnel_orders_characterization_hire_item_without_employee_id_allowed(
    client, privileged_headers
) -> None:
    order_id = create_draft_order(client, privileged_headers, suffix=unique_suffix())
    try:
        item_id = create_hire_item(
            client,
            privileged_headers,
            order_id,
            employee_id=None,
        )
        detail = client.get(
            f"/directory/personnel-orders/{order_id}",
            headers=privileged_headers,
        )
        assert detail.status_code == 200, detail.text
        item = next(row for row in detail.json()["items"] if row["item_id"] == item_id)
        assert item["employee_id"] is None
    finally:
        cleanup_order(order_id)


def test_personnel_orders_characterization_hire_register_requires_employee_id(
    client, privileged_headers
) -> None:
    order_id = create_draft_order(client, privileged_headers, suffix=unique_suffix())
    try:
        create_hire_item(
            client,
            privileged_headers,
            order_id,
            employee_id=None,
        )
        register = client.post(
            f"/directory/personnel-orders/{order_id}/register",
            json={"target_status": "REGISTERED"},
            headers=privileged_headers,
        )
        assert register.status_code == 422, register.text
        body = register.json()
        detail = body.get("detail", body)
        message = str(detail)
        assert "employee_id" in message
    finally:
        cleanup_order(order_id)


def test_personnel_orders_characterization_transfer_item_allows_missing_employee_id_on_create(
    client, privileged_headers
) -> None:
    """TRANSFER item create accepts null employee_id; registration enforces it later."""
    order_id = create_draft_order(client, privileged_headers, suffix=unique_suffix())
    try:
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/items",
            json={
                "item_type_code": "TRANSFER",
                "effective_date": "2026-07-12",
                "payload": {
                    "org_unit_name": "Synthetic Unit",
                    "position_name": "Synthetic Position",
                },
            },
            headers=privileged_headers,
        )
        assert resp.status_code == 200, resp.text
        item = resp.json()["items"][0]
        assert item["item_type_code"] == "TRANSFER"
        assert item["employee_id"] is None
    finally:
        cleanup_order(order_id)
