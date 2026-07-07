# tests/test_wp_po_004b_personnel_orders_draft_register_api.py
"""API tests for WP-PO-004B personnel orders draft/register write endpoints."""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers
from tests.test_wp_po_003_personnel_orders_schema import (
    _pick_employee_id,
    _pick_user_id,
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


def _count_events_for_order(order_id: int) -> int:
    with engine.begin() as conn:
        return int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.employee_events
                    WHERE order_id = :order_id
                    """
                ),
                {"order_id": order_id},
            ).scalar_one()
        )


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


def test_create_draft_add_item_text_and_register_without_events(client, privileged_headers):
    suffix = uuid4().hex[:8]
    order_number = f"WPPO4B-{suffix}"

    with engine.begin() as conn:
        employee_id = _pick_employee_id(conn)

    create_resp = client.post(
        "/directory/personnel-orders",
        json={
            "order_number": order_number,
            "order_date": "2026-07-07",
            "order_type_code": "HIRE",
            "source_mode": "PAPER",
            "signed_by_name": "Director Test",
        },
        headers=privileged_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    order_id = created["order"]["order_id"]
    assert created["order"]["status"] == "DRAFT"
    assert created["items"] == []

    try:
        item_resp = client.post(
            f"/directory/personnel-orders/{order_id}/items",
            json={
                "item_type_code": "HIRE",
                "employee_id": employee_id,
                "effective_date": "2026-07-07",
                "payload": {"employment_rate": 1.0},
            },
            headers=privileged_headers,
        )
        assert item_resp.status_code == 200, item_resp.text
        assert len(item_resp.json()["items"]) == 1

        text_resp = client.put(
            f"/directory/personnel-orders/{order_id}/localized-texts/kk",
            json={
                "title": "Жұмысқа қабылдау туралы",
                "body_text": "БҰЙЫРАМЫН: ...",
                "is_authoritative": True,
            },
            headers=privileged_headers,
        )
        assert text_resp.status_code == 200, text_resp.text
        assert len(text_resp.json()["localized_texts"]) == 1

        register_resp = client.post(
            f"/directory/personnel-orders/{order_id}/register",
            json={"target_status": "REGISTERED"},
            headers=privileged_headers,
        )
        assert register_resp.status_code == 200, register_resp.text
        registered = register_resp.json()
        assert registered["order"]["status"] == "REGISTERED"
        assert _count_events_for_order(order_id) == 0
        assert registered["events"] == []

        patch_resp = client.patch(
            f"/directory/personnel-orders/{order_id}",
            json={"comment": "should fail"},
            headers=privileged_headers,
        )
        assert patch_resp.status_code == 409

        item_patch_resp = client.post(
            f"/directory/personnel-orders/{order_id}/items",
            json={
                "item_type_code": "HIRE",
                "employee_id": employee_id,
                "effective_date": "2026-07-08",
            },
            headers=privileged_headers,
        )
        assert item_patch_resp.status_code == 409
    finally:
        _cleanup_order(order_id)


def test_register_to_signed_from_ready_for_signature(client, privileged_headers):
    suffix = uuid4().hex[:8]
    order_number = f"WPPO4B-SIGNED-{suffix}"

    with engine.begin() as conn:
        employee_id = _pick_employee_id(conn)

    create_resp = client.post(
        "/directory/personnel-orders",
        json={
            "order_number": order_number,
            "order_date": "2026-07-07",
            "order_type_code": "TRANSFER",
            "source_mode": "DIGITAL",
        },
        headers=privileged_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    order_id = create_resp.json()["order"]["order_id"]

    try:
        client.post(
            f"/directory/personnel-orders/{order_id}/items",
            json={
                "item_type_code": "TRANSFER",
                "employee_id": employee_id,
                "effective_date": "2026-07-07",
                "payload": {"to_position_id": 1},
            },
            headers=privileged_headers,
        )

        ready_resp = client.post(
            f"/directory/personnel-orders/{order_id}/ready-for-signature",
            headers=privileged_headers,
        )
        assert ready_resp.status_code == 200, ready_resp.text
        assert ready_resp.json()["order"]["status"] == "READY_FOR_SIGNATURE"

        signed_resp = client.post(
            f"/directory/personnel-orders/{order_id}/register",
            json={"target_status": "SIGNED"},
            headers=privileged_headers,
        )
        assert signed_resp.status_code == 200, signed_resp.text
        assert signed_resp.json()["order"]["status"] == "SIGNED"
        assert _count_events_for_order(order_id) == 0
    finally:
        _cleanup_order(order_id)


def test_register_without_items_returns_422(client, privileged_headers):
    suffix = uuid4().hex[:8]
    create_resp = client.post(
        "/directory/personnel-orders",
        json={
            "order_number": f"WPPO4B-NOITEM-{suffix}",
            "order_date": "2026-07-07",
            "order_type_code": "HIRE",
        },
        headers=privileged_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    order_id = create_resp.json()["order"]["order_id"]

    try:
        register_resp = client.post(
            f"/directory/personnel-orders/{order_id}/register",
            json={"target_status": "REGISTERED"},
            headers=privileged_headers,
        )
        assert register_resp.status_code == 422
    finally:
        _cleanup_order(order_id)


def test_write_endpoints_require_personnel_admin(client, seed):
    suffix = uuid4().hex[:8]
    headers = auth_headers(seed["executor_user_id"])
    resp = client.post(
        "/directory/personnel-orders",
        json={
            "order_number": f"WPPO4B-FORBID-{suffix}",
            "order_date": "2026-07-07",
            "order_type_code": "HIRE",
        },
        headers=headers,
    )
    assert resp.status_code == 403


def test_update_item_payload(client, privileged_headers):
    suffix = uuid4().hex[:8]
    order_number = f"WPPO4B-ITEM-{suffix}"

    with engine.begin() as conn:
        employee_id = _pick_employee_id(conn)

    create_resp = client.post(
        "/directory/personnel-orders",
        json={
            "order_number": order_number,
            "order_date": "2026-07-07",
            "order_type_code": "CONCURRENT_DUTY_START",
        },
        headers=privileged_headers,
    )
    order_id = create_resp.json()["order"]["order_id"]

    try:
        item_resp = client.post(
            f"/directory/personnel-orders/{order_id}/items",
            json={
                "item_type_code": "CONCURRENT_DUTY_START",
                "employee_id": employee_id,
                "effective_date": "2026-07-07",
                "payload": {"concurrent_rate": 0.5},
            },
            headers=privileged_headers,
        )
        item_id = item_resp.json()["items"][0]["item_id"]

        patch_resp = client.patch(
            f"/directory/personnel-orders/{order_id}/items/{item_id}",
            json={"payload": {"concurrent_rate": 0.25, "total_rate": 1.25}},
            headers=privileged_headers,
        )
        assert patch_resp.status_code == 200, patch_resp.text
        updated_item = patch_resp.json()["items"][0]
        assert updated_item["payload"]["concurrent_rate"] == 0.25
        assert updated_item["payload"]["total_rate"] == 1.25
    finally:
        _cleanup_order(order_id)
