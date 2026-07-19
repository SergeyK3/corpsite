# tests/test_wp_mrd_004_unit.py
"""Unit tests for WP-MRD-004 API adapters."""
from __future__ import annotations

from datetime import date
from app.directory.mrd_command_api import _to_summary
from app.directory.mrd_errors import map_mrd_error
from app.mrd.domain.errors import MrdCommandConflictError, MrdNotFoundError, MrdPeriodExistsError
from app.mrd.infrastructure.repository import MrdVersionDetailRow


def test_to_summary_marks_active_for_period() -> None:
    row = MrdVersionDetailRow(
        mrd_id=10,
        report_period=date(2026, 6, 1),
        version=2,
        status="ACTIVE",
        row_version=1,
        entry_count=5,
        forked_from_reference_id=9,
    )
    summary = _to_summary(row, active_by_period={"2026-06-01": 10})
    assert summary["is_active_for_period"] is True


def test_map_mrd_error_status_codes() -> None:
    assert map_mrd_error(MrdNotFoundError("missing")).status_code == 404
    assert map_mrd_error(MrdPeriodExistsError("dup")).status_code == 409
    assert map_mrd_error(MrdCommandConflictError("conflict")).status_code == 409
    assert map_mrd_error(RuntimeError("x")) is None
