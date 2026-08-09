"""Narrow migration/writer tests for ADR-065 preflight dependencies."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

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


def test_scope_generation_cas_and_rollback() -> None:
    with engine.connect() as conn:
        order_id = conn.execute(
            text("SELECT order_id FROM public.personnel_orders ORDER BY order_id LIMIT 1")
        ).scalar_one_or_none()
    if order_id is None:
        pytest.skip("no personnel order available")
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


def test_scope_writer_lock_serializes_concurrent_generation() -> None:
    with engine.connect() as probe:
        order_id = probe.execute(text("SELECT order_id FROM public.personnel_orders ORDER BY order_id LIMIT 1")).scalar_one_or_none()
    if order_id is None:
        pytest.skip("no personnel order available")
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
        future = assignment_boundary_activation_tx(
            conn,
            target_effective_date=current + timedelta(days=1),
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
