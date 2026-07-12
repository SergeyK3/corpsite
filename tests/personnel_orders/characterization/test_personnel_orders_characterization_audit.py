# tests/personnel_orders/characterization/test_personnel_orders_characterization_audit.py
"""Characterization: Personnel Orders lifecycle audit behavior (UDE-007)."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.personnel_orders.characterization._helpers import (
    cancel_payload,
    cleanup_order,
    create_draft_order,
    unique_suffix,
)

pytestmark = pytest.mark.usefixtures("_require_po_characterization_schema")


def _audit_count(order_id: int) -> int:
    with engine.begin() as conn:
        return int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.personnel_order_lifecycle_audit
                    WHERE order_id = :order_id
                    """
                ),
                {"order_id": order_id},
            ).scalar_one()
        )


def test_personnel_orders_characterization_cancel_appends_audit_event(
    client, cancel_own_user, privileged_headers
) -> None:
    order_id = create_draft_order(
        client,
        privileged_headers,
        suffix=unique_suffix(),
        created_by=cancel_own_user["user_id"],
    )
    try:
        before = _audit_count(order_id)
        cancel = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json=cancel_payload(reason_text="Synthetic audit characterization"),
            headers=cancel_own_user["headers"],
        )
        assert cancel.status_code == 200, cancel.text
        assert _audit_count(order_id) == before + 1

        audit = client.get(
            f"/directory/personnel-orders/{order_id}/lifecycle-audit",
            headers=privileged_headers,
        )
        assert audit.status_code == 200, audit.text
        items = audit.json()["items"]
        assert len(items) >= 1
        latest = items[0]
        assert latest["action"] == "CANCEL"
        assert latest["new_status"] == "VOIDED"
        assert latest["new_void_kind"] == "CANCEL"
    finally:
        cleanup_order(order_id)


def test_personnel_orders_characterization_audit_rows_are_not_rewritten_on_second_read(
    client, cancel_own_user, privileged_headers
) -> None:
    order_id = create_draft_order(
        client,
        privileged_headers,
        suffix=unique_suffix(),
        created_by=cancel_own_user["user_id"],
    )
    try:
        cancel = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json=cancel_payload(reason_text="Synthetic audit characterization"),
            headers=cancel_own_user["headers"],
        )
        assert cancel.status_code == 200, cancel.text

        first = client.get(
            f"/directory/personnel-orders/{order_id}/lifecycle-audit",
            headers=privileged_headers,
        )
        second = client.get(
            f"/directory/personnel-orders/{order_id}/lifecycle-audit",
            headers=privileged_headers,
        )
        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert first.json()["items"] == second.json()["items"]
        assert _audit_count(order_id) == len(first.json()["items"])
    finally:
        cleanup_order(order_id)


def test_personnel_orders_characterization_no_synthetic_activation_audit_on_draft_create(
    client, privileged_headers
) -> None:
    order_id = create_draft_order(client, privileged_headers, suffix=unique_suffix())
    try:
        assert _audit_count(order_id) == 0
        audit = client.get(
            f"/directory/personnel-orders/{order_id}/lifecycle-audit",
            headers=privileged_headers,
        )
        assert audit.status_code == 200, audit.text
        assert audit.json()["items"] == []
    finally:
        cleanup_order(order_id)
