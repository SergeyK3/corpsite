"""Allowed report_period window for MRD creation (fork-period)."""
from __future__ import annotations

from datetime import date

from app.mrd.domain.errors import MrdPeriodWindowError


def anchor_report_period(reference: date) -> date:
    return date(reference.year, reference.month, 1)


def shift_report_period(period: date, delta_months: int) -> date:
    year = period.year
    month = period.month + delta_months
    while month > 12:
        month -= 12
        year += 1
    while month < 1:
        month += 12
        year -= 1
    return date(year, month, 1)


def reference_business_date(reference: date | None = None) -> date:
    return reference or date.today()


def get_creation_window_periods(reference: date | None = None) -> tuple[date, ...]:
    anchor = anchor_report_period(reference_business_date(reference))
    return (
        shift_report_period(anchor, -1),
        anchor,
        shift_report_period(anchor, 1),
    )


def is_period_in_creation_window(target_period: date, reference: date | None = None) -> bool:
    normalized = anchor_report_period(target_period)
    return normalized in get_creation_window_periods(reference)


def require_period_in_creation_window(target_period: date, reference: date | None = None) -> None:
    normalized = anchor_report_period(target_period)
    if is_period_in_creation_window(normalized, reference):
        return
    window = get_creation_window_periods(reference)
    labels = ", ".join(p.strftime("%m.%Y") for p in window)
    raise MrdPeriodWindowError(
        "Период создания эталона вне допустимого окна. "
        f"Доступны только предыдущий, текущий и следующий календарные месяцы: {labels}."
    )
