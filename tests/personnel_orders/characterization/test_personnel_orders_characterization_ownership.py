# tests/personnel_orders/characterization/test_personnel_orders_characterization_ownership.py
"""Characterization: Personnel Orders ownership and cancel scope (UDE-007)."""
from __future__ import annotations

import pytest

from tests.personnel_orders.characterization._helpers import (
    cancel_payload,
    cleanup_order,
    create_draft_order,
    unique_suffix,
)

pytestmark = pytest.mark.usefixtures("_require_po_characterization_schema")


def test_personnel_orders_characterization_owner_can_cancel_own_draft(
    client, cancel_own_user, privileged_headers
) -> None:
    order_id = create_draft_order(
        client,
        privileged_headers,
        suffix=unique_suffix(),
        created_by=cancel_own_user["user_id"],
    )
    try:
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json=cancel_payload(reason_text="Owner cancel"),
            headers=cancel_own_user["headers"],
        )
        assert resp.status_code == 200, resp.text
    finally:
        cleanup_order(order_id)


def test_personnel_orders_characterization_non_owner_cancel_own_denied(
    client, cancel_own_user, privileged_headers
) -> None:
    order_id = create_draft_order(client, privileged_headers, suffix=unique_suffix())
    try:
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json=cancel_payload(reason_text="Foreign cancel"),
            headers=cancel_own_user["headers"],
        )
        assert resp.status_code == 403, resp.text
    finally:
        cleanup_order(order_id)


def test_personnel_orders_characterization_directory_privileged_does_not_imply_cancel(
    client, privileged_headers
) -> None:
    order_id = create_draft_order(client, privileged_headers, suffix=unique_suffix())
    try:
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json=cancel_payload(reason_text="Privileged without cancel grant"),
            headers=privileged_headers,
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["detail"]["code"] == "CANCEL_PERMISSION_DENIED"
    finally:
        cleanup_order(order_id)
