# tests/test_wp_mrd_003_unit.py
"""Unit tests for WP-MRD-003 ACTIVE resolver and idempotency helpers."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from app.mrd.application.fork_idempotency import build_request_fingerprint
from app.mrd.domain.active_resolver import require_active_mrd
from app.mrd.domain.errors import ActiveMrdAmbiguousError, ActiveMrdMissingError
from app.mrd.infrastructure.repository import MonthlyReferenceRow


def _row(mrd_id: int, period: date, version: int = 1) -> MonthlyReferenceRow:
    return MonthlyReferenceRow(
        mrd_id=mrd_id,
        report_period=period,
        version=version,
        status="ACTIVE",
        row_version=1,
        entry_count=0,
    )


def test_require_active_mrd_returns_single_row() -> None:
    period = date(2026, 6, 1)
    repo = MagicMock()
    repo.list_active_mrd_candidates.return_value = [_row(10, period)]
    result = require_active_mrd(repo, period)
    assert result.mrd_id == 10


def test_require_active_mrd_missing_raises() -> None:
    repo = MagicMock()
    repo.list_active_mrd_candidates.return_value = []
    with pytest.raises(ActiveMrdMissingError):
        require_active_mrd(repo, date(2026, 6, 1))


def test_require_active_mrd_ambiguous_raises() -> None:
    period = date(2026, 6, 1)
    repo = MagicMock()
    repo.list_active_mrd_candidates.return_value = [_row(10, period), _row(11, period)]
    with pytest.raises(ActiveMrdAmbiguousError):
        require_active_mrd(repo, period)


def test_request_fingerprint_is_stable() -> None:
    payload = {"source_mrd_id": 1, "target_report_period": "2026-07-01"}
    assert build_request_fingerprint(payload) == build_request_fingerprint(payload)


def test_request_fingerprint_changes_with_payload() -> None:
    a = build_request_fingerprint({"source_mrd_id": 1})
    b = build_request_fingerprint({"source_mrd_id": 2})
    assert a != b
