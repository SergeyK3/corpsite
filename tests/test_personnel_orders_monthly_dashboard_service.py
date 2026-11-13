from contextlib import nullcontext
from datetime import date
import os
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.services.personnel_orders_monthly_dashboard_service import build_personnel_orders_monthly_dashboard


class _TransactionEngine:
    def __init__(self, connection):
        self.connection = connection

    def connect(self):
        return nullcontext(self.connection)


def test_transfer_filter_counts_an_ordinary_order_and_a_two_item_composite_once():
    url = make_url(os.environ["TEST_DATABASE_URL"])
    assert url.host in {"127.0.0.1", "localhost", "::1"}
    assert (url.database or "").endswith("_test")
    engine = create_engine(url)

    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            bound_engine = _TransactionEngine(connection)
            today = date(2030, 1, 16)
            before_all = build_personnel_orders_monthly_dashboard(bound_engine, today=today)
            before_transfer = build_personnel_orders_monthly_dashboard(bound_engine, today=today, order_type="TRANSFER")
            creator_id = connection.execute(text("SELECT MIN(user_id) FROM public.users")).scalar_one()
            assert creator_id is not None

            base_id = 8_000_000_000 + uuid4().int % 1_000_000_000
            orders = [
                (base_id, "TRANSFER", date(2030, 1, 10)),
                (base_id + 1, "COMPOSITE", date(2030, 1, 11)),
                (base_id + 2, "HIRE", date(2030, 1, 12)),
                (base_id + 3, "COMPOSITE", date(2030, 1, 13)),
                (base_id + 4, "TRANSFER", date(2030, 1, 20)),
                (base_id + 5, "TRANSFER", None),
            ]
            for order_id, order_type, order_date in orders:
                connection.execute(text("""
                    INSERT INTO public.personnel_orders
                      (order_id, order_number, order_date, order_type_code, status, source_mode, created_by)
                    OVERRIDING SYSTEM VALUE
                    VALUES (:order_id, :number, :order_date, :order_type, 'SIGNED', 'MANUAL', :creator_id)
                """), {
                    "order_id": order_id,
                    "number": f"dashboard-test-{order_id}",
                    "order_date": order_date,
                    "order_type": order_type,
                    "creator_id": creator_id,
                })

            for index, (order_id, status) in enumerate([
                (base_id + 1, "ACTIVE"), (base_id + 1, "ACTIVE"),
                (base_id + 3, "VOIDED"), (base_id + 3, "VOIDED"),
            ]):
                connection.execute(text("""
                    INSERT INTO public.personnel_order_items
                      (item_id, order_id, item_number, item_type_code, item_status, void_reason)
                    OVERRIDING SYSTEM VALUE
                    VALUES (:item_id, :order_id, :item_number, 'TRANSFER', :status, :void_reason)
                """), {
                    "item_id": base_id * 10 + index,
                    "order_id": order_id,
                    "item_number": index % 2 + 1,
                    "status": status,
                    "void_reason": "test fixture" if status == "VOIDED" else None,
                })

            after_all = build_personnel_orders_monthly_dashboard(bound_engine, today=today)
            after_transfer = build_personnel_orders_monthly_dashboard(bound_engine, today=today, order_type="TRANSFER")
            assert after_all["months"][0]["count"] == before_all["months"][0]["count"] + 4
            assert after_transfer["months"][0]["count"] == before_transfer["months"][0]["count"] + 2
            assert after_transfer["order_type"] == "TRANSFER"
            assert len(after_transfer["months"]) == 1
        finally:
            transaction.rollback()
    engine.dispose()
