"""PostgreSQL integration contract for pojson015; every test rolls back its own transaction.

Run only after applying pojson015 to a disposable loopback corpsite_test database.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine as database_engine
from app.services import technical_personnel_order_cleanup_service as cleanup


class _SameConnectionEngine:
    """Lets the service use one outer transaction that the test always rolls back."""
    def __init__(self, conn): self.conn = conn
    @contextmanager
    def begin(self):
        nested = self.conn.begin_nested()
        try:
            yield self.conn
        except Exception:
            nested.rollback()
            raise
        else:
            nested.commit()
    @contextmanager
    def connect(self): yield self.conn


@pytest.fixture()
def cleanup_tx(monkeypatch):
    with database_engine.connect() as conn:
        transaction = conn.begin()
        try:
            if any(conn.execute(text(f"SELECT to_regclass('public.{table}')")).scalar_one() is None for table in ("technical_personnel_order_deletion_audit", "technical_personnel_order_provenance_audit")):
                pytest.skip("pojson015 has not been applied to corpsite_test")
            monkeypatch.setattr(cleanup, "engine", _SameConnectionEngine(conn))
            yield conn
        finally:
            transaction.rollback()


def _actor(conn) -> int:
    return int(conn.execute(text("SELECT user_id FROM public.users WHERE is_active=TRUE ORDER BY user_id LIMIT 1")).scalar_one())


def _order(conn, *, technical=True) -> int:
    actor = _actor(conn); suffix = uuid4().hex[:10]
    storage = {"technical_record": True, "record_quality": "TECHNICAL_RECORD", "import_source_id": f"pytest:{suffix}"} if technical else {}
    return int(conn.execute(text("""INSERT INTO public.personnel_orders
      (order_number,order_date,order_type_code,status,source_mode,storage_json,created_by)
      VALUES (:n,CURRENT_DATE,'HIRE','DRAFT','DIGITAL',CAST(:s AS jsonb),:a) RETURNING order_id"""),
      {"n": f"PYTEST-TECH-{suffix}", "s": json.dumps(storage), "a": actor}).scalar_one())


def test_preview_is_read_only_and_regular_order_is_not_eligible(cleanup_tx):
    order_id = _order(cleanup_tx, technical=False)
    before = cleanup_tx.execute(text("SELECT count(*) FROM public.personnel_orders WHERE order_id=:id"), {"id": order_id}).scalar_one()
    preview = cleanup.preview(order_id)
    assert preview["technical_confirmed"] is False and preview["can_delete"] is False
    assert cleanup_tx.execute(text("SELECT count(*) FROM public.personnel_orders WHERE order_id=:id"), {"id": order_id}).scalar_one() == before


def test_isolated_technical_order_deletes_only_its_allowlist_and_writes_audit(cleanup_tx):
    target, neighbour, actor = _order(cleanup_tx), _order(cleanup_tx), _actor(cleanup_tx)
    result = cleanup.execute(order_id=target, actor_user_id=actor, reason="pytest isolated technical cleanup", confirmation_phrase=f"DELETE TECHNICAL ORDER {target}")
    assert result["status"] == "COMPLETED"
    assert cleanup_tx.execute(text("SELECT count(*) FROM public.personnel_orders WHERE order_id=:id"), {"id": target}).scalar_one() == 0
    assert cleanup_tx.execute(text("SELECT count(*) FROM public.personnel_orders WHERE order_id=:id"), {"id": neighbour}).scalar_one() == 1
    assert cleanup_tx.execute(text("SELECT count(*) FROM public.technical_personnel_order_deletion_audit WHERE order_id=:id AND result_code='COMPLETED'"), {"id": target}).scalar_one() == 1


def test_legacy_confirmation_is_separate_from_delete_and_writes_provenance_audit(cleanup_tx):
    actor = _actor(cleanup_tx)
    order_id = int(cleanup_tx.execute(text("""INSERT INTO public.personnel_orders
      (order_number,order_date,order_type_code,status,source_mode,storage_json,created_by)
      VALUES (:n,CURRENT_DATE,'HIRE','DRAFT','DIGITAL','{}'::jsonb,:a) RETURNING order_id"""), {"n": f"PERSONNEL-IMPORT-2026-{uuid4().hex[:8]}", "a": actor}).scalar_one())
    assert cleanup.preview(order_id)["can_delete"] is False
    confirmed = cleanup.confirm_provenance(order_id=order_id, actor_user_id=actor, reason="pytest legacy provenance", confirmation_phrase=f"CONFIRM TECHNICAL ORDER {order_id}")
    assert confirmed["classification"] == cleanup.CONFIRMED_TECHNICAL
    assert cleanup.preview(order_id)["classification"] == cleanup.CONFIRMED_TECHNICAL
    assert cleanup_tx.execute(text("SELECT count(*) FROM public.technical_personnel_order_provenance_audit WHERE order_id=:id"), {"id": order_id}).scalar_one() == 1


def test_unknown_fk_and_employee_event_like_dependency_block_without_audit(cleanup_tx):
    order_id = _order(cleanup_tx); actor = _actor(cleanup_tx)
    cleanup_tx.execute(text("""CREATE TABLE public.pytest_technical_order_blocker (
      id BIGSERIAL PRIMARY KEY, order_id BIGINT NOT NULL REFERENCES public.personnel_orders(order_id))"""))
    cleanup_tx.execute(text("INSERT INTO public.pytest_technical_order_blocker(order_id) VALUES (:id)"), {"id": order_id})
    preview = cleanup.preview(order_id)
    assert preview["can_delete"] is False
    assert any(row["table"] == "pytest_technical_order_blocker" for row in preview["blocking_dependencies"])
    with pytest.raises(cleanup.TechnicalOrderCleanupError, match="Blocking"):
        cleanup.execute(order_id=order_id, actor_user_id=actor, reason="pytest blocker", confirmation_phrase=f"DELETE TECHNICAL ORDER {order_id}")
    assert cleanup_tx.execute(text("SELECT count(*) FROM public.personnel_orders WHERE order_id=:id"), {"id": order_id}).scalar_one() == 1
    assert cleanup_tx.execute(text("SELECT count(*) FROM public.technical_personnel_order_deletion_audit WHERE order_id=:id"), {"id": order_id}).scalar_one() == 0


def test_transaction_rolls_back_when_audit_insert_fails(cleanup_tx, monkeypatch):
    order_id, actor = _order(cleanup_tx), _actor(cleanup_tx)
    original = cleanup_tx.execute
    def fail_audit(statement, *args, **kwargs):
        if "technical_personnel_order_deletion_audit" in str(statement): raise RuntimeError("forced audit failure")
        return original(statement, *args, **kwargs)
    monkeypatch.setattr(cleanup_tx, "execute", fail_audit)
    with pytest.raises(RuntimeError, match="forced audit failure"):
        cleanup.execute(order_id=order_id, actor_user_id=actor, reason="pytest rollback", confirmation_phrase=f"DELETE TECHNICAL ORDER {order_id}")
    # The service transaction is the outer rollback-only transaction; restore execution to inspect it.
    monkeypatch.setattr(cleanup_tx, "execute", original)
    assert cleanup_tx.execute(text("SELECT count(*) FROM public.personnel_orders WHERE order_id=:id"), {"id": order_id}).scalar_one() == 1
