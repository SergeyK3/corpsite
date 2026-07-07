# tests/test_wp_po_004a_personnel_orders_read_api.py
"""API tests for WP-PO-004A personnel orders read endpoints."""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers, table_exists
from tests.test_wp_po_003_personnel_orders_schema import (
    _insert_returning,
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


def _create_registered_hire_order(
    *,
    order_number: str,
    order_date: date,
    user_id: int,
    employee_id: int,
    with_event: bool = True,
) -> dict[str, int]:
    with engine.begin() as conn:
        order_id = _insert_returning(
            conn,
            """
            INSERT INTO public.personnel_orders (
                order_number,
                order_date,
                order_type_code,
                status,
                source_mode,
                signed_by_name,
                created_by
            )
            VALUES (
                :order_number,
                :order_date,
                'HIRE',
                'REGISTERED',
                'PAPER',
                'Director Test',
                :created_by
            )
            RETURNING order_id
            """,
            {
                "order_number": order_number,
                "order_date": order_date,
                "created_by": user_id,
            },
        )

        item_id = _insert_returning(
            conn,
            """
            INSERT INTO public.personnel_order_items (
                order_id,
                item_number,
                item_type_code,
                employee_id,
                effective_date,
                payload
            )
            VALUES (
                :order_id,
                1,
                'HIRE',
                :employee_id,
                :effective_date,
                '{"employment_rate": 1.0}'::jsonb
            )
            RETURNING item_id
            """,
            {
                "order_id": order_id,
                "employee_id": employee_id,
                "effective_date": order_date,
            },
        )

        _insert_returning(
            conn,
            """
            INSERT INTO public.personnel_order_localized_texts (
                order_id,
                locale,
                title,
                is_authoritative
            )
            VALUES (
                :order_id,
                'kk',
                'Жұмысқа қабылдау туралы',
                TRUE
            )
            RETURNING localized_text_id
            """,
            {"order_id": order_id},
        )

        event_id = 0
        if with_event:
            event_id = _insert_returning(
                conn,
                """
                INSERT INTO public.employee_events (
                    employee_id,
                    event_type,
                    effective_date,
                    order_id,
                    order_item_id,
                    created_by
                )
                VALUES (
                    :employee_id,
                    'HIRE',
                    :effective_date,
                    :order_id,
                    :order_item_id,
                    :created_by
                )
                RETURNING event_id
                """,
                {
                    "employee_id": employee_id,
                    "effective_date": order_date,
                    "order_id": order_id,
                    "order_item_id": item_id,
                    "created_by": user_id,
                },
            )

    return {
        "order_id": order_id,
        "item_id": item_id,
        "event_id": event_id,
    }


def _cleanup_order(order_id: int, event_id: int | None = None) -> None:
    with engine.begin() as conn:
        if event_id:
            conn.execute(
                text("DELETE FROM public.employee_events WHERE event_id = :event_id"),
                {"event_id": event_id},
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


def test_list_personnel_orders_privileged(client, privileged_headers):
    resp = client.get("/directory/personnel-orders", headers=privileged_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert "limit" in body
    assert "offset" in body
    assert isinstance(body["items"], list)


def test_list_personnel_orders_unprivileged_returns_403(client, seed):
    resp = client.get("/directory/personnel-orders", headers=auth_headers(seed["executor_user_id"]))
    assert resp.status_code == 403


def test_list_personnel_orders_invalid_status_returns_422(client, privileged_headers):
    resp = client.get(
        "/directory/personnel-orders",
        params={"status": "NOT_A_STATUS"},
        headers=privileged_headers,
    )
    assert resp.status_code == 422


def test_list_and_get_personnel_order_detail(client, privileged_headers):
    suffix = uuid4().hex[:8]
    order_number = f"WPPO4A-{suffix}"
    order_date = date(2026, 7, 1)

    with engine.begin() as conn:
        user_id = _pick_user_id(conn)
        employee_id = _pick_employee_id(conn)

    created = _create_registered_hire_order(
        order_number=order_number,
        order_date=order_date,
        user_id=user_id,
        employee_id=employee_id,
        with_event=True,
    )

    try:
        list_resp = client.get(
            "/directory/personnel-orders",
            params={
                "status": "REGISTERED",
                "order_type_code": "HIRE",
                "date_from": "2026-07-01",
                "date_to": "2026-07-31",
                "employee_id": employee_id,
                "q": order_number,
            },
            headers=privileged_headers,
        )
        assert list_resp.status_code == 200, list_resp.text
        list_body = list_resp.json()
        row = next((item for item in list_body["items"] if item["order_number"] == order_number), None)
        assert row is not None, list_body["items"]
        assert row["order_type_code"] == "HIRE"
        assert row["status"] == "REGISTERED"
        assert row["item_count"] == 1
        assert employee_id in row["employee_ids"]

        detail_resp = client.get(
            f"/directory/personnel-orders/{created['order_id']}",
            headers=privileged_headers,
        )
        assert detail_resp.status_code == 200, detail_resp.text
        detail = detail_resp.json()

        assert detail["order"]["order_number"] == order_number
        assert len(detail["items"]) == 1
        assert detail["items"][0]["item_id"] == created["item_id"]
        assert detail["items"][0]["employee_id"] == employee_id
        assert detail["items"][0]["item_type_code"] == "HIRE"
        assert len(detail["localized_texts"]) == 1
        assert detail["localized_texts"][0]["locale"] == "kk"
        assert len(detail["events"]) == 1
        assert detail["events"][0]["event_id"] == created["event_id"]
        assert detail["events"][0]["order_item_id"] == created["item_id"]
        assert detail["events"][0]["event_type"] == "HIRE"
    finally:
        _cleanup_order(created["order_id"], created["event_id"])


def test_list_personnel_orders_filter_by_org_unit(client, privileged_headers):
    suffix = uuid4().hex[:8]
    order_number = f"WPPO4A-ORG-{suffix}"
    order_date = date(2026, 6, 15)

    with engine.begin() as conn:
        user_id = _pick_user_id(conn)
        employee_id = _pick_employee_id(conn)
        org_unit_id = conn.execute(
            text("SELECT org_unit_id FROM public.employees WHERE employee_id = :employee_id"),
            {"employee_id": employee_id},
        ).scalar_one()

    created = _create_registered_hire_order(
        order_number=order_number,
        order_date=order_date,
        user_id=user_id,
        employee_id=employee_id,
        with_event=False,
    )

    try:
        resp = client.get(
            "/directory/personnel-orders",
            params={"org_unit_id": int(org_unit_id), "q": order_number},
            headers=privileged_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert any(item["order_number"] == order_number for item in body["items"])
    finally:
        _cleanup_order(created["order_id"])


def test_get_personnel_order_unknown_returns_404(client, privileged_headers):
    resp = client.get("/directory/personnel-orders/999999999", headers=privileged_headers)
    assert resp.status_code == 404
