"""Narrow migration/writer tests for ADR-065 preflight dependencies."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db.engine import engine
from app.services.hr_person_assignment_sync_service import assignment_boundary_activation_tx
from app.services.personnel_order_evidence_scope_service import (
    PersonnelOrderEvidenceScopeError,
    advance_personnel_order_evidence_scopes_tx,
    lock_personnel_order_evidence_scopes_tx,
)


@pytest.fixture
def evidence_scope_order() -> int:
    """Self-contained ADR-065 order/scope fixture; never relies on seed rows."""
    with engine.begin() as conn:
        user_id = conn.execute(text("SELECT user_id FROM public.users WHERE is_active IS TRUE ORDER BY user_id LIMIT 1")).scalar_one()
        order_id = int(conn.execute(text("""
            INSERT INTO public.personnel_orders(order_number, order_date, order_type_code, status, source_mode, created_by)
            VALUES (:number, :date, 'HIRE', 'DRAFT', 'PAPER', :user_id)
            RETURNING order_id
        """), {"number": f"ADR065-PREFLIGHT-{uuid4().hex[:12]}", "date": date(2026, 7, 10), "user_id": user_id}).scalar_one())
        conn.execute(text("INSERT INTO public.personnel_order_evidence_scopes(order_id) VALUES (:id)"), {"id": order_id})
    try:
        yield order_id
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM public.personnel_order_evidence_scopes WHERE order_id=:id"), {"id": order_id})
            conn.execute(text("DELETE FROM public.personnel_orders WHERE order_id=:id"), {"id": order_id})


def test_revision_chain_is_linear() -> None:
    source = Path(
        "alembic/versions/l9m0n1o2p3q4_adr065_preflight_schema_dependencies.py"
    ).read_text(encoding="utf-8")
    assert 'revision = "l9m0n1o2p3q4"' in source
    assert 'down_revision = "j7k8l9m0n1o2"' in source


def test_migrated_schema_and_deterministic_backfill() -> None:
    with engine.connect() as conn:
        columns = {
            row["column_name"]: (row["data_type"], row["is_nullable"])
            for row in conn.execute(
                text(
                    "SELECT column_name,data_type,is_nullable FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name='person_assignment_activation_watermark'"
                )
            ).mappings()
        }
        assert columns == {
            "singleton": ("boolean", "NO"),
            "effective_date": ("date", "NO"),
            "processed_at": ("timestamp with time zone", "NO"),
            "generation": ("bigint", "NO"),
            "updated_at": ("timestamp with time zone", "NO"),
        }
        assert conn.execute(
            text("SELECT count(*) FROM public.person_assignment_activation_watermark")
        ).scalar_one() == 1
        missing = conn.execute(
            text(
                "SELECT count(*) FROM public.personnel_orders po LEFT JOIN "
                "public.personnel_order_evidence_scopes s ON s.order_id=po.order_id "
                "WHERE s.order_id IS NULL"
            )
        ).scalar_one()
        assert missing == 0


def test_scope_generation_cas_and_rollback(evidence_scope_order: int) -> None:
    order_id = evidence_scope_order
    with engine.connect() as conn:
        tx = conn.begin()
        before = conn.execute(
            text("SELECT generation FROM public.personnel_order_evidence_scopes WHERE order_id=:id"),
            {"id": order_id},
        ).scalar_one()
        tokens = lock_personnel_order_evidence_scopes_tx(conn, order_ids=[order_id])
        advanced = advance_personnel_order_evidence_scopes_tx(conn, tokens=tokens)
        assert advanced[0].generation == before + 1
        with pytest.raises(PersonnelOrderEvidenceScopeError):
            advance_personnel_order_evidence_scopes_tx(conn, tokens=tokens)
        tx.rollback()
    with engine.connect() as conn:
        after = conn.execute(
            text("SELECT generation FROM public.personnel_order_evidence_scopes WHERE order_id=:id"),
            {"id": order_id},
        ).scalar_one()
        assert after == before


def test_scope_writer_lock_serializes_concurrent_generation(evidence_scope_order: int) -> None:
    order_id = evidence_scope_order
    with engine.connect() as first, engine.connect() as second:
        first_tx = first.begin()
        second_tx = second.begin()
        lock_personnel_order_evidence_scopes_tx(first, order_ids=[order_id])
        second.execute(text("SET LOCAL lock_timeout='200ms'"))
        with pytest.raises(DBAPIError):
            lock_personnel_order_evidence_scopes_tx(second, order_ids=[order_id])
        second_tx.rollback()
        first_tx.rollback()


def test_c2_watermark_advance_duplicate_future_and_rollback() -> None:
    with engine.connect() as conn:
        tx = conn.begin()
        row = conn.execute(
            text(
                "SELECT effective_date,generation FROM public.person_assignment_activation_watermark "
                "WHERE singleton IS TRUE FOR UPDATE"
            )
        ).mappings().one()
        current = row["effective_date"]
        generation = int(row["generation"])
        duplicate = assignment_boundary_activation_tx(
            conn,
            target_effective_date=current,
            expected_effective_date=current,
            expected_generation=generation,
        )
        assert duplicate.code == "BOUNDARY_RUN_DUPLICATE"
        business_date = conn.execute(
            text("SELECT ((transaction_timestamp() AT TIME ZONE 'UTC') + INTERVAL '5 hours')::date")
        ).scalar_one()
        future = assignment_boundary_activation_tx(
            conn,
            target_effective_date=business_date + timedelta(days=1),
            expected_effective_date=current,
            expected_generation=generation,
        )
        assert future.code == "BOUNDARY_RUN_FUTURE_DATE"
        conn.execute(
            text(
                "UPDATE public.person_assignment_activation_watermark SET effective_date=:old "
                "WHERE singleton IS TRUE"
            ),
            {"old": current - timedelta(days=1)},
        )
        advanced = assignment_boundary_activation_tx(
            conn,
            target_effective_date=current,
            expected_effective_date=current - timedelta(days=1),
            expected_generation=generation,
        )
        assert advanced.code == "BOUNDARY_RUN_ADVANCED"
        assert advanced.generation == generation + 1
        tx.rollback()
    with engine.connect() as conn:
        persisted = conn.execute(
            text(
                "SELECT effective_date,generation FROM public.person_assignment_activation_watermark "
                "WHERE singleton IS TRUE"
            )
        ).mappings().one()
        assert persisted["effective_date"] == current
        assert int(persisted["generation"]) == generation
