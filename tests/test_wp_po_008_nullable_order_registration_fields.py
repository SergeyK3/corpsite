# tests/test_wp_po_008_nullable_order_registration_fields.py
"""WP-PO-008 — Draft may omit order_number/order_date; Register requires them."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers
from tests.test_wp_po_003_personnel_orders_schema import (
    _pick_employee_id,
    _require_schema,
)

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


def test_create_draft_without_registration_fields(client, privileged_headers):
    create_resp = client.post(
        "/directory/personnel-orders",
        json={
            "order_type_code": "HIRE",
            "source_mode": "PAPER",
            "comment": "Draft before paper journal entry",
        },
        headers=privileged_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    body = create_resp.json()
    order = body["order"]
    order_id = order["order_id"]

    try:
        assert order["status"] == "DRAFT"
        assert order["order_number"] is None
        assert order["order_date"] is None
        assert order["order_type_code"] == "HIRE"
        assert order["comment"] == "Draft before paper journal entry"

        with engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT order_number, order_date, status
                    FROM public.personnel_orders
                    WHERE order_id = :order_id
                    """
                ),
                {"order_id": order_id},
            ).mappings().one()
        assert row["order_number"] is None
        assert row["order_date"] is None
        assert row["status"] == "DRAFT"
    finally:
        _cleanup_order(order_id)


def test_register_without_registration_fields_rejected(client, privileged_headers):
    with engine.begin() as conn:
        employee_id = _pick_employee_id(conn)

    create_resp = client.post(
        "/directory/personnel-orders",
        json={"order_type_code": "TRANSFER", "source_mode": "PAPER"},
        headers=privileged_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    order_id = create_resp.json()["order"]["order_id"]

    try:
        item_resp = client.post(
            f"/directory/personnel-orders/{order_id}/items",
            json={
                "item_type_code": "TRANSFER",
                "employee_id": employee_id,
                "effective_date": "2026-07-10",
                "payload": {"to_position_id": 1},
            },
            headers=privileged_headers,
        )
        assert item_resp.status_code == 200, item_resp.text

        register_resp = client.post(
            f"/directory/personnel-orders/{order_id}/register",
            json={"target_status": "REGISTERED"},
            headers=privileged_headers,
        )
        assert register_resp.status_code == 422, register_resp.text
        detail = str(register_resp.json().get("detail") or "")
        assert "order_number" in detail.lower() or "registration" in detail.lower()

        assert create_resp.json()["order"]["status"] == "DRAFT"
        detail_resp = client.get(
            f"/directory/personnel-orders/{order_id}",
            headers=privileged_headers,
        )
        assert detail_resp.status_code == 200
        assert detail_resp.json()["order"]["status"] == "DRAFT"
    finally:
        _cleanup_order(order_id)


def test_patch_registration_fields_then_register(client, privileged_headers):
    suffix = uuid4().hex[:8]
    order_number = f"WPPO8-{suffix}"

    with engine.begin() as conn:
        employee_id = _pick_employee_id(conn)

    create_resp = client.post(
        "/directory/personnel-orders",
        json={"order_type_code": "TERMINATION", "source_mode": "PAPER"},
        headers=privileged_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    order_id = create_resp.json()["order"]["order_id"]

    try:
        item_resp = client.post(
            f"/directory/personnel-orders/{order_id}/items",
            json={
                "item_type_code": "TERMINATION",
                "employee_id": employee_id,
                "effective_date": "2026-07-10",
                "payload": {"termination_reason": "agreement"},
            },
            headers=privileged_headers,
        )
        assert item_resp.status_code == 200, item_resp.text

        patch_resp = client.patch(
            f"/directory/personnel-orders/{order_id}",
            json={
                "order_number": order_number,
                "order_date": "2026-07-10",
            },
            headers=privileged_headers,
        )
        assert patch_resp.status_code == 200, patch_resp.text
        assert patch_resp.json()["order"]["order_number"] == order_number
        assert patch_resp.json()["order"]["order_date"] == "2026-07-10"

        register_resp = client.post(
            f"/directory/personnel-orders/{order_id}/register",
            json={"target_status": "REGISTERED"},
            headers=privileged_headers,
        )
        assert register_resp.status_code == 200, register_resp.text
        assert register_resp.json()["order"]["status"] == "REGISTERED"
        assert register_resp.json()["order"]["order_number"] == order_number
    finally:
        _cleanup_order(order_id)


def test_multiple_drafts_without_number_allowed(client, privileged_headers):
    order_ids: list[int] = []
    try:
        for _ in range(2):
            resp = client.post(
                "/directory/personnel-orders",
                json={"order_type_code": "HIRE", "source_mode": "PAPER"},
                headers=privileged_headers,
            )
            assert resp.status_code == 201, resp.text
            order_ids.append(resp.json()["order"]["order_id"])
            assert resp.json()["order"]["order_number"] is None
        assert order_ids[0] != order_ids[1]
    finally:
        for order_id in order_ids:
            _cleanup_order(order_id)
