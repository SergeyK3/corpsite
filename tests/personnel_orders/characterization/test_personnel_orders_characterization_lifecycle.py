# tests/personnel_orders/characterization/test_personnel_orders_characterization_lifecycle.py
"""Characterization: Personnel Orders lifecycle status behavior (UDE-007)."""
from __future__ import annotations

import pytest

from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_orders import ORDER_STATUSES
from app.document_engine.value_objects.lifecycle import DocumentLifecycleState, VoidKind
from app.services.personnel_order_lifecycle_audit_service import resolve_void_kind
from tests.personnel_orders.characterization._helpers import (
    cancel_payload,
    cleanup_order,
    create_draft_order,
    set_order_status,
    unique_suffix,
)

pytestmark = pytest.mark.usefixtures("_require_po_characterization_schema")


def _fetch_void_kind(order_id: int) -> str:
    with engine.begin() as conn:
        return str(
            conn.execute(
                text(
                    """
                    SELECT void_kind
                    FROM public.personnel_orders
                    WHERE order_id = :order_id
                    """
                ),
                {"order_id": order_id},
            ).scalar_one()
        )


def test_personnel_orders_characterization_lifecycle_statuses_match_shared_contract() -> None:
    """PO ORDER_STATUSES is the MVP authority; shared enum is a superset (includes PUBLISHED)."""
    po_statuses = set(ORDER_STATUSES)
    shared_statuses = {state.value for state in DocumentLifecycleState}
    assert po_statuses.issubset(shared_statuses)
    assert "PUBLISHED" in shared_statuses
    assert "PUBLISHED" not in po_statuses


@pytest.mark.parametrize("status", list(ORDER_STATUSES))
def test_personnel_orders_characterization_detail_exposes_status(
    client, privileged_headers, status: str
) -> None:
    order_id = create_draft_order(client, privileged_headers, suffix=unique_suffix())
    try:
        set_order_status(order_id, status)
        detail = client.get(
            f"/directory/personnel-orders/{order_id}",
            headers=privileged_headers,
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["order"]["status"] == status
    finally:
        cleanup_order(order_id)


@pytest.mark.parametrize(
    ("previous_status", "expected_void_kind"),
    [
        ("DRAFT", VoidKind.CANCEL),
        ("READY_FOR_SIGNATURE", VoidKind.CANCEL),
        ("SIGNED", VoidKind.ANNUL),
        ("REGISTERED", VoidKind.ANNUL),
    ],
)
def test_personnel_orders_characterization_resolve_void_kind_matrix(
    previous_status: str,
    expected_void_kind: VoidKind,
) -> None:
    assert resolve_void_kind(previous_status) == expected_void_kind.value


def test_personnel_orders_characterization_cancel_draft_via_api(
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
            json=cancel_payload(),
            headers=cancel_own_user["headers"],
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["order"]["status"] == "VOIDED"
        assert _fetch_void_kind(order_id) == "CANCEL"
    finally:
        cleanup_order(order_id)


def test_personnel_orders_characterization_cancel_ready_via_api(
    client, cancel_own_user, privileged_headers
) -> None:
    order_id = create_draft_order(
        client,
        privileged_headers,
        suffix=unique_suffix(),
        created_by=cancel_own_user["user_id"],
    )
    try:
        set_order_status(order_id, "READY_FOR_SIGNATURE")
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json=cancel_payload(),
            headers=cancel_own_user["headers"],
        )
        assert resp.status_code == 200, resp.text
        assert _fetch_void_kind(order_id) == "CANCEL"
    finally:
        cleanup_order(order_id)


def test_personnel_orders_characterization_cancel_registered_rejected(
    client, cancel_own_user, privileged_headers
) -> None:
    order_id = create_draft_order(
        client,
        privileged_headers,
        suffix=unique_suffix(),
        created_by=cancel_own_user["user_id"],
    )
    try:
        set_order_status(order_id, "REGISTERED")
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json=cancel_payload(),
            headers=cancel_own_user["headers"],
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["detail"]["code"] == "ORDER_NOT_CANCELLABLE"
    finally:
        cleanup_order(order_id)
