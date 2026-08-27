"""Transaction-bound primitives used by the personnel CSV loader."""
from __future__ import annotations

from datetime import date
import inspect
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services import personnel_orders_command_service as orders
from tests.test_wp_po_003_personnel_orders_schema import _require_schema


@pytest.fixture(scope="module", autouse=True)
def _require_personnel_orders_schema():
    _require_schema()


def test_import_transaction_primitives_do_not_open_or_commit_transactions():
    for function in (
        orders.create_personnel_order_draft_tx,
        orders.create_personnel_order_item_tx,
        orders.register_personnel_order_tx,
    ):
        source = inspect.getsource(function)
        assert "engine.begin" not in source
        assert ".commit(" not in source


def test_transaction_draft_is_rolled_back_with_the_caller_row_transaction():
    order_number = f"TX-ROLLBACK-{uuid4().hex}"

    with pytest.raises(RuntimeError, match="force rollback"):
        with engine.begin() as conn:
            created_by = conn.execute(
                text("SELECT user_id FROM public.users WHERE is_active = TRUE ORDER BY user_id LIMIT 1")
            ).scalar_one()
            order_id = orders.create_personnel_order_draft_tx(
                conn,
                created_by=int(created_by),
                order_number=order_number,
                order_date=date(2026, 8, 27),
                order_type_code="HIRE",
                comment="pytest transaction rollback",
            )
            assert order_id > 0
            raise RuntimeError("force rollback")

    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM public.personnel_orders WHERE order_number = :number"),
            {"number": order_number},
        ).scalar_one()
    assert count == 0
