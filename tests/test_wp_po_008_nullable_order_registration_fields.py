"""New personnel-order saves require registration number and date.

The database columns remain nullable because legacy Paper First drafts must
remain readable; this test module covers the stricter creation path instead.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers, get_columns
from tests.test_wp_po_003_personnel_orders_schema import _delete_personnel_order_audit_rows, _require_schema


@pytest.fixture(scope="module", autouse=True)
def _require_structured_storage_schema():
    _require_schema()
    with engine.begin() as conn:
        if "storage_json" not in get_columns(conn, "personnel_orders"):
            pytest.skip("Structured personnel-order storage migration is not applied.")


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


def _cleanup_order(order_id: int) -> None:
    with engine.begin() as conn:
        _delete_personnel_order_audit_rows(conn, order_id)
        for table in (
            "personnel_order_evidence_scopes",
            "employee_events",
            "personnel_order_localized_texts",
            "personnel_order_items",
        ):
            conn.execute(
                text(f"DELETE FROM public.{table} WHERE order_id = :order_id"),
                {"order_id": order_id},
            )
        conn.execute(
            text("DELETE FROM public.personnel_orders WHERE order_id = :order_id"),
            {"order_id": order_id},
        )


def test_order_with_number_and_date_is_saved_and_read(client, privileged_headers):
    order_number = f"1379-ж-{uuid4().hex[:8]}"
    storage_json = {"schema_version": "0.1", "basis_documents": []}
    response = client.post(
        "/directory/personnel-orders",
        json={
            "order_number": order_number,
            "order_date": "2026-08-01",
            "order_type_code": "HIRE",
            "source_mode": "PAPER",
            "storage_json": storage_json,
        },
        headers=privileged_headers,
    )
    assert response.status_code == 201, response.text
    order_id = response.json()["order"]["order_id"]
    try:
        detail = client.get(f"/directory/personnel-orders/{order_id}", headers=privileged_headers)
        assert detail.status_code == 200, detail.text
        order = detail.json()["order"]
        assert order["order_number"] == order_number
        assert order["order_date"] == "2026-08-01"
        assert order["storage_json"] == storage_json
    finally:
        _cleanup_order(order_id)


def test_order_without_number_is_not_saved(client, privileged_headers):
    response = client.post(
        "/directory/personnel-orders",
        json={"order_date": "2026-08-01", "order_type_code": "HIRE", "source_mode": "PAPER"},
        headers=privileged_headers,
    )
    assert response.status_code == 422, response.text
    assert "order_number" in str(response.json().get("detail") or "").lower()


def test_order_without_date_is_not_saved(client, privileged_headers):
    response = client.post(
        "/directory/personnel-orders",
        json={"order_number": f"1379-ж-{uuid4().hex[:8]}", "order_type_code": "HIRE", "source_mode": "PAPER"},
        headers=privileged_headers,
    )
    assert response.status_code == 422, response.text
    assert "order_date" in str(response.json().get("detail") or "").lower()
