# tests/personnel_orders/characterization/test_personnel_orders_characterization_hire.py
"""Characterization: Personnel Orders HIRE identity contract (UDE-007, hire-from-person)."""
from __future__ import annotations

import pytest

from app.db.engine import engine
from tests.personnel_orders.characterization._helpers import (
    build_hire_item_payload,
    cleanup_order,
    create_draft_order,
    create_hire_candidate_person,
    create_hire_item,
    post_order_item,
    unique_suffix,
)
from tests.test_wp_po_003_personnel_orders_schema import _pick_employee_id

pytestmark = pytest.mark.usefixtures("_require_po_characterization_schema")


def test_personnel_orders_characterization_hire_without_identity_rejected_on_create(
    client, privileged_headers
) -> None:
    order_id = create_draft_order(client, privileged_headers, suffix=unique_suffix())
    try:
        resp = post_order_item(
            client,
            privileged_headers,
            order_id,
            item_type_code="HIRE",
            payload={"employment_rate": 1.0},
        )
        assert resp.status_code == 422, resp.text
        assert "employee_id or payload.person_id" in str(resp.json().get("detail", resp.text))
    finally:
        cleanup_order(order_id)


def test_personnel_orders_characterization_hire_with_person_id_allowed_without_employee_id(
    client, privileged_headers
) -> None:
    order_id = create_draft_order(client, privileged_headers, suffix=unique_suffix())
    try:
        with engine.begin() as conn:
            person_id = create_hire_candidate_person(conn, suffix=unique_suffix())
        item_id = create_hire_item(
            client,
            privileged_headers,
            order_id,
            person_id=person_id,
            auto_person_for_hire=False,
        )
        detail = client.get(
            f"/directory/personnel-orders/{order_id}",
            headers=privileged_headers,
        )
        assert detail.status_code == 200, detail.text
        item = next(row for row in detail.json()["items"] if row["item_id"] == item_id)
        assert item["employee_id"] is None
        assert int(item["payload"]["person_id"]) == person_id
    finally:
        cleanup_order(order_id)


def test_personnel_orders_characterization_hire_with_person_id_allows_register(
    client, privileged_headers
) -> None:
    order_id = create_draft_order(client, privileged_headers, suffix=unique_suffix())
    try:
        with engine.begin() as conn:
            person_id = create_hire_candidate_person(conn, suffix=unique_suffix())
        create_resp = post_order_item(
            client,
            privileged_headers,
            order_id,
            item_type_code="HIRE",
            payload=build_hire_item_payload(person_id=person_id),
        )
        assert create_resp.status_code == 200, create_resp.text
        register = client.post(
            f"/directory/personnel-orders/{order_id}/register",
            json={"target_status": "REGISTERED"},
            headers=privileged_headers,
        )
        assert register.status_code == 200, register.text
        assert register.json()["order"]["status"] == "REGISTERED"
    finally:
        cleanup_order(order_id)


def test_personnel_orders_characterization_hire_with_employee_id_allowed(
    client, privileged_headers
) -> None:
    order_id = create_draft_order(client, privileged_headers, suffix=unique_suffix())
    try:
        with engine.begin() as conn:
            employee_id = _pick_employee_id(conn)
        item_id = create_hire_item(
            client,
            privileged_headers,
            order_id,
            employee_id=employee_id,
            auto_person_for_hire=False,
        )
        detail = client.get(
            f"/directory/personnel-orders/{order_id}",
            headers=privileged_headers,
        )
        assert detail.status_code == 200, detail.text
        item = next(row for row in detail.json()["items"] if row["item_id"] == item_id)
        assert int(item["employee_id"]) == employee_id
    finally:
        cleanup_order(order_id)


def test_personnel_orders_characterization_transfer_item_requires_employee_id_on_create(
    client, privileged_headers
) -> None:
    """Non-HIRE item types require employee_id at create time."""
    order_id = create_draft_order(client, privileged_headers, suffix=unique_suffix())
    try:
        resp = post_order_item(
            client,
            privileged_headers,
            order_id,
            item_type_code="TRANSFER",
            payload={
                "org_unit_name": "Synthetic Unit",
                "position_name": "Synthetic Position",
            },
        )
        assert resp.status_code == 422, resp.text
        assert "requires employee_id" in str(resp.json().get("detail", resp.text))
    finally:
        cleanup_order(order_id)
