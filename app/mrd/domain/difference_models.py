"""Commands and results for Detected Difference operations."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class CreateDifferenceCommand:
    report_period: date
    mrd_id: int
    logical_key: str
    entity_scope: str
    attribute: str
    business_type: str
    difference_origin_code: str
    origin_context: Mapping[str, Any]
    old_value: Any = None
    new_value: Any = None
    record_kind: str | None = None
    technical_diff_class: str | None = None
    supersedes_difference_id: int | None = None
    last_comparison_run_id: int | None = None


@dataclass(frozen=True, slots=True)
class ConfirmDifferenceCommand:
    difference_id: int
    confirmed_by: int
    expected_row_version: int
    basis: str | None = None


@dataclass(frozen=True, slots=True)
class RejectDifferenceCommand:
    difference_id: int
    rejected_by: int
    expected_row_version: int
    basis: str | None = None


@dataclass(frozen=True, slots=True)
class DetectedDifferenceRecord:
    difference_id: int
    report_period: date
    mrd_id: int
    logical_key: str
    entity_scope: str
    attribute: str
    business_type: str
    lifecycle_status: str
    difference_origin_code: str
    origin_context: dict[str, Any]
    old_value: Any
    new_value: Any
    technical_diff_class: str | None
    row_version: int
    record_kind: str | None = None
    supersedes_difference_id: int | None = None


@dataclass(frozen=True, slots=True)
class ConfirmDifferenceResult:
    confirmed_change_id: int
    difference_id: int
    mrd_id: int
    entry_id: int | None


@dataclass(frozen=True, slots=True)
class RejectDifferenceResult:
    difference_id: int
    lifecycle_status: str
    rejected_at: datetime


@dataclass(frozen=True, slots=True)
class ComparisonRunResult:
    comparison_run_id: int
    batch_id: int
    mrd_id: int
    report_period: date
    stats: dict[str, int] = field(default_factory=dict)
