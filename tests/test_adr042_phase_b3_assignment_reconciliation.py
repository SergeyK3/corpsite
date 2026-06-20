# tests/test_adr042_phase_b3_assignment_reconciliation.py
"""Tests for ADR-042 Phase B3 assignment reconciliation service."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.assignment_reconciliation_service import (
    compare_employee_snapshot_to_primary_assignment,
    list_assignment_drift,
    reconcile_all,
    reconcile_employee_primary_assignment,
)
from tests.conftest import table_exists


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_b2() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "person_assignments"):
            pytest.skip("ADR-042 B2 person_assignments missing")


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_assignment_drift_returns_rows():
    _require_b2()
    drift = list_assignment_drift(limit=10)
    assert "total" in drift
    assert "items" in drift
    assert drift["total"] >= 0


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_reconciliation_dry_run_does_not_mutate():
    _require_b2()
    drift = list_assignment_drift(limit=1)
    if drift["total"] == 0:
        pytest.skip("No drift rows in database")

    employee_id = int(drift["items"][0]["employee_id"])
    before = compare_employee_snapshot_to_primary_assignment(employee_id)

    result = reconcile_employee_primary_assignment(employee_id, dry_run=True)
    assert result["dry_run"] is True
    assert result.get("applied") is False
    assert "would_update" in result

    after = compare_employee_snapshot_to_primary_assignment(employee_id)
    assert after["diff"] == before["diff"]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_reconcile_all_dry_run():
    _require_b2()
    result = reconcile_all(dry_run=True, limit=5)
    assert result["dry_run"] is True
    assert result["applied_count"] == 0
    assert result["processed"] <= 5
