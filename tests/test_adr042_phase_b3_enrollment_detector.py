# tests/test_adr042_phase_b3_enrollment_detector.py
"""Tests for ADR-042 Phase B3 enrollment detector service."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.enrollment_detector_service import (
    detect_enrollment_candidates,
    enqueue_enrollment_candidate,
    explain_candidate,
)
from tests.conftest import insert_returning_id, table_exists


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_b2() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "enrollment_queue"):
            pytest.skip("ADR-042 B2 enrollment_queue missing")


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_enqueue_idempotent(seed):
    _require_b2()
    suffix = uuid4().hex[:8]

    with engine.begin() as conn:
        person_id = insert_returning_id(
            conn,
            table="persons",
            id_col="person_id",
            values={
                "full_name": f"Detect Person {suffix}",
                "match_key": f"name:detect person {suffix}",
                "source": "manual",
                "person_status": "active",
            },
        )

    first = enqueue_enrollment_candidate(
        reason="MANUAL_REQUEST",
        person_id=person_id,
        dry_run=False,
    )
    second = enqueue_enrollment_candidate(
        reason="MANUAL_REQUEST",
        person_id=person_id,
        dry_run=False,
    )
    assert first["queue_id"] == second["queue_id"]
    assert second.get("idempotent_hit") is True

    explained = explain_candidate(queue_id=int(first["queue_id"]))
    assert explained["queue_status"] == "PENDING"
    assert "explanation" in explained

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.enrollment_history WHERE queue_id = :qid"),
            {"qid": int(first["queue_id"])},
        )
        conn.execute(
            text("DELETE FROM public.enrollment_queue WHERE queue_id = :qid"),
            {"qid": int(first["queue_id"])},
        )
        conn.execute(text("DELETE FROM public.persons WHERE person_id = :pid"), {"pid": person_id})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_detect_dry_run_does_not_create_employee(seed):
    _require_b2()

    before_employees = _count_employees()
    result = detect_enrollment_candidates(dry_run=True, limit=10)
    after_employees = _count_employees()

    assert result["dry_run"] is True
    assert before_employees == after_employees
    assert "candidates" in result


def _count_employees() -> int:
    with engine.connect() as conn:
        return int(conn.execute(text("SELECT COUNT(*) FROM public.employees")).scalar_one())
