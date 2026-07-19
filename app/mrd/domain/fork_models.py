"""Fork / ACTIVE management commands and results (WP-MRD-003)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class ForkVersionCommand:
    command_id: str
    source_mrd_id: int
    performed_by: int
    expected_active_row_version: int | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class ForkPeriodCommand:
    command_id: str
    source_mrd_id: int
    target_report_period: date
    performed_by: int
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class ForkVersionResult:
    command_id: str
    source_mrd_id: int
    target_mrd_id: int
    target_report_period: date
    target_version: int
    closed_mrd_id: int | None
    copied_entry_count: int
    version_event_ids: tuple[int, ...]
    idempotent_replay: bool = False


@dataclass(frozen=True, slots=True)
class ForkPeriodResult:
    command_id: str
    source_mrd_id: int
    target_mrd_id: int
    target_report_period: date
    target_version: int
    copied_entry_count: int
    version_event_ids: tuple[int, ...]
    idempotent_replay: bool = False


@dataclass(frozen=True, slots=True)
class VersionEventRecord:
    event_id: int
    event_type: str
    report_period: date
    mrd_id: int
    source_mrd_id: int | None
