"""Unit tests for MRD creation window rules."""
from __future__ import annotations

from datetime import date

import pytest

from app.mrd.domain.errors import MrdPeriodWindowError
from app.mrd.domain.period_window import (
    get_creation_window_periods,
    is_period_in_creation_window,
    require_period_in_creation_window,
    shift_report_period,
)


def test_creation_window_three_months() -> None:
    ref = date(2026, 7, 19)
    window = get_creation_window_periods(ref)
    assert window == (date(2026, 6, 1), date(2026, 7, 1), date(2026, 8, 1))


def test_in_window_accepts_month_input() -> None:
    ref = date(2026, 7, 19)
    assert is_period_in_creation_window(date(2026, 7, 15), ref) is True
    assert is_period_in_creation_window(date(2026, 10, 1), ref) is False


def test_require_period_raises_with_message() -> None:
    ref = date(2026, 7, 19)
    with pytest.raises(MrdPeriodWindowError, match="допустимого окна"):
        require_period_in_creation_window(date(2026, 12, 1), ref)


def test_shift_report_period() -> None:
    assert shift_report_period(date(2026, 1, 1), -1) == date(2025, 12, 1)
    assert shift_report_period(date(2026, 12, 1), 1) == date(2027, 1, 1)


def test_require_period_rejects_september_2026_from_july_reference() -> None:
    ref = date(2026, 7, 19)
    with pytest.raises(MrdPeriodWindowError, match="допустимого окна"):
        require_period_in_creation_window(date(2026, 9, 1), ref)
