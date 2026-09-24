from __future__ import annotations

import json
from datetime import date
from uuid import uuid4

from sqlalchemy import text

from app.db.engine import engine
from app.services.personnel_orders_query_service import list_personnel_orders
from tests.test_wp_po_003_personnel_orders_schema import _pick_employee_id, _pick_user_id, _require_schema


def test_list_personnel_orders_prefers_source_names_for_every_personnel_item():
    _require_schema()
    order_number = f"TEST-SOURCE-NAMES-{uuid4().hex[:10]}"
    order_id: int | None = None

    try:
        with engine.begin() as conn:
            employee_id = _pick_employee_id(conn)
            user_id = _pick_user_id(conn)
            order_id = int(conn.execute(text("""
                INSERT INTO public.personnel_orders (
                    order_number, order_date, order_type_code, status, source_mode, created_by
                ) VALUES (
                    :order_number, :order_date, 'HIRE', 'DRAFT', 'PAPER', :created_by
                ) RETURNING order_id
            """), {
                "order_number": order_number,
                "order_date": date(2026, 9, 24),
                "created_by": user_id,
            }).scalar_one())
            conn.execute(text("""
                INSERT INTO public.personnel_order_items (
                    order_id, item_number, item_type_code, employee_id, effective_date, payload
                ) VALUES
                    (:order_id, 1, 'HIRE', :employee_id, :effective_date, CAST(:first_payload AS jsonb)),
                    (:order_id, 2, 'HIRE', NULL, :effective_date, CAST(:second_payload AS jsonb))
            """), {
                "order_id": order_id,
                "employee_id": employee_id,
                "effective_date": date(2026, 9, 24),
                "first_payload": json.dumps({"source_employee_name": "Оразбеков"}),
                "second_payload": json.dumps({"source_employee_name": "Икрамбек"}),
            })

        result = list_personnel_orders(q=order_number, limit=10)
        row = next(item for item in result["items"] if item["order_id"] == order_id)

        assert row["employee_names"] == ["Оразбеков", "Икрамбек"]
    finally:
        if order_id is not None:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM public.personnel_order_items WHERE order_id = :order_id"), {"order_id": order_id})
                conn.execute(text("DELETE FROM public.personnel_orders WHERE order_id = :order_id"), {"order_id": order_id})
