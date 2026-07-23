"""Calculate total employment tenure from intake employment biography records."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Mapping

from app.personnel_intake.domain.date_validation import (
    _parse_to_iso,
    is_valid_intake_full_date_iso,
)

DAYS_PER_YEAR = 365.25

MISSING_START_WARNING = "Не указана дата начала — запись не включена в общий стаж"
END_BEFORE_START_WARNING = "Дата окончания раньше даты начала — запись не включена в общий стаж"


@dataclass(frozen=True)
class EmploymentTenureYmd:
    years: int
    months: int
    days: int


@dataclass(frozen=True)
class EmploymentTenureRecordResult:
    record_id: str
    index: int
    label: str
    days: int | None
    included: bool
    is_open_ended: bool
    overlaps_other: bool
    warning: str | None


@dataclass(frozen=True)
class EmploymentTenureCalculation:
    calculation_date: date
    records: tuple[EmploymentTenureRecordResult, ...]
    arithmetic_sum_days: int
    overlap_excluded_days: int
    total_days: int
    total_ymd: EmploymentTenureYmd

    @property
    def decimal_years(self) -> float:
        return round(self.total_days / DAYS_PER_YEAR, 2)


def parse_employment_period_date(value: Any) -> date | None:
    iso = _parse_to_iso(value)
    if not iso or not is_valid_intake_full_date_iso(iso):
        return None
    return date.fromisoformat(iso)


def calendar_days_between(start: date, end: date) -> int:
    return (end - start).days


def decompose_calendar_days(total_days: int) -> EmploymentTenureYmd:
    if total_days <= 0:
        return EmploymentTenureYmd(0, 0, 0)
    start = date(2000, 1, 1)
    end = start + timedelta(days=total_days)
    years = end.year - start.year
    months = end.month - start.month
    days = end.day - start.day
    if days < 0:
        months -= 1
        prev_month = end.month - 1 or 12
        prev_year = end.year if end.month > 1 else end.year - 1
        days += calendar.monthrange(prev_year, prev_month)[1]
    if months < 0:
        years -= 1
        months += 12
    return EmploymentTenureYmd(years=years, months=months, days=days)


def intervals_strictly_overlap(left: tuple[date, date], right: tuple[date, date]) -> bool:
    return left[0] < right[1] and right[0] < left[1]


def merge_employment_intervals(intervals: list[tuple[date, date]]) -> list[tuple[date, date]]:
    if not intervals:
        return []
    sorted_intervals = sorted(intervals)
    merged: list[list[date]] = [[sorted_intervals[0][0], sorted_intervals[0][1]]]
    for start, end in sorted_intervals[1:]:
        if start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def _coerce_record_dict(record: Any) -> dict[str, Any] | None:
    if isinstance(record, Mapping):
        return dict(record)
    model_dump = getattr(record, "model_dump", None)
    if callable(model_dump):
        return model_dump()
    dict_method = getattr(record, "dict", None)
    if callable(dict_method):
        return dict_method()
    return None


def _record_label(record: Mapping[str, Any], index: int) -> str:
    organization = str(record.get("organization") or "").strip()
    if organization:
        return organization
    position = str(record.get("position") or "").strip()
    if position:
        return position
    return f"Запись {index + 1}"


def _record_id(record: Mapping[str, Any], index: int) -> str:
    explicit = str(record.get("record_id") or "").strip()
    if explicit:
        return explicit
    return f"legacy-{index}"


def calculate_employment_tenure(
    records: list[Any],
    *,
    calculation_date: date | None = None,
) -> EmploymentTenureCalculation:
    calc_date = calculation_date or date.today()
    parsed_records: list[dict[str, Any]] = []
    result_rows: list[EmploymentTenureRecordResult] = []

    for index, raw_record in enumerate(records):
        record = _coerce_record_dict(raw_record)
        if record is None:
            result_rows.append(
                EmploymentTenureRecordResult(
                    record_id=f"legacy-{index}",
                    index=index,
                    label=f"Запись {index + 1}",
                    days=None,
                    included=False,
                    is_open_ended=False,
                    overlaps_other=False,
                    warning=MISSING_START_WARNING,
                )
            )
            continue

        record_id = _record_id(record, index)
        label = _record_label(record, index)
        start = parse_employment_period_date(record.get("year_from"))
        end_raw = record.get("year_to")
        end_text = str(end_raw or "").strip()
        end = parse_employment_period_date(end_text) if end_text else calc_date
        is_open_ended = not end_text

        if start is None:
            result_rows.append(
                EmploymentTenureRecordResult(
                    record_id=record_id,
                    index=index,
                    label=label,
                    days=None,
                    included=False,
                    is_open_ended=is_open_ended,
                    overlaps_other=False,
                    warning=MISSING_START_WARNING,
                )
            )
            continue

        if end < start:
            result_rows.append(
                EmploymentTenureRecordResult(
                    record_id=record_id,
                    index=index,
                    label=label,
                    days=None,
                    included=False,
                    is_open_ended=is_open_ended,
                    overlaps_other=False,
                    warning=END_BEFORE_START_WARNING,
                )
            )
            continue

        days = calendar_days_between(start, end)
        parsed_records.append(
            {
                "record_id": record_id,
                "index": index,
                "label": label,
                "start": start,
                "end": end,
                "days": days,
                "is_open_ended": is_open_ended,
            }
        )
        result_rows.append(
            EmploymentTenureRecordResult(
                record_id=record_id,
                index=index,
                label=label,
                days=days,
                included=True,
                is_open_ended=is_open_ended,
                overlaps_other=False,
                warning=None,
            )
        )

    intervals = [(item["start"], item["end"]) for item in parsed_records]
    merged = merge_employment_intervals(intervals)
    arithmetic_sum = sum(item["days"] for item in parsed_records)
    merged_total = sum(calendar_days_between(start, end) for start, end in merged)
    overlap_excluded = arithmetic_sum - merged_total

    overlap_flags: dict[str, bool] = {item["record_id"]: False for item in parsed_records}
    for left_index, left in enumerate(parsed_records):
        left_interval = (left["start"], left["end"])
        for right in parsed_records[left_index + 1 :]:
            right_interval = (right["start"], right["end"])
            if intervals_strictly_overlap(left_interval, right_interval):
                overlap_flags[left["record_id"]] = True
                overlap_flags[right["record_id"]] = True

    finalized_rows = tuple(
        EmploymentTenureRecordResult(
            record_id=row.record_id,
            index=row.index,
            label=row.label,
            days=row.days,
            included=row.included,
            is_open_ended=row.is_open_ended,
            overlaps_other=overlap_flags.get(row.record_id, False),
            warning=row.warning,
        )
        for row in result_rows
    )

    return EmploymentTenureCalculation(
        calculation_date=calc_date,
        records=finalized_rows,
        arithmetic_sum_days=arithmetic_sum,
        overlap_excluded_days=overlap_excluded,
        total_days=merged_total,
        total_ymd=decompose_calendar_days(merged_total),
    )
