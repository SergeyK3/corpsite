"""Repository contracts for MRD application layer."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any, Protocol

from app.mrd.domain.difference_models import (
    ConfirmDifferenceResult,
    CreateDifferenceCommand,
    DetectedDifferenceRecord,
    RejectDifferenceResult,
)


class MonthlyReferenceRecord(Protocol):
    mrd_id: int
    report_period: date
    version: int
    status: str
    row_version: int
    entry_count: int


class MrdEntryRecord(Protocol):
    entry_id: int
    mrd_id: int
    match_key: str
    entity_scope: str
    record_kind: str
    canonical_hash: str
    effective_payload: dict[str, Any]
    row_version: int


class MrdReadRepository(Protocol):
    def resolve_active_mrd(self, report_period: date) -> MonthlyReferenceRecord | None:
        ...

    def load_mrd(self, mrd_id: int) -> MonthlyReferenceRecord | None:
        ...

    def load_mrd_entries(self, mrd_id: int) -> list[MrdEntryRecord]:
        ...

    def load_entry_by_match_key(self, *, mrd_id: int, match_key: str) -> MrdEntryRecord | None:
        ...

    def count_differences_for_mrd(self, mrd_id: int) -> int:
        ...

    def count_confirmed_changes_for_mrd(self, mrd_id: int) -> int:
        ...

    def origin_is_active(self, origin_code: str) -> bool:
        ...


class DifferenceReadRepository(Protocol):
    def load_difference(self, difference_id: int) -> DetectedDifferenceRecord | None:
        ...

    def list_differences_for_mrd(self, mrd_id: int) -> list[DetectedDifferenceRecord]:
        ...


class DifferenceWriteRepository(Protocol):
    def insert_difference(self, command: CreateDifferenceCommand) -> DetectedDifferenceRecord:
        ...

    def mark_superseded(self, difference_id: int, *, expected_row_version: int) -> None:
        ...

    def mark_confirmed(
        self,
        difference_id: int,
        *,
        expected_row_version: int,
        confirmed_by: int,
        confirmed_at: datetime,
    ) -> None:
        ...

    def mark_rejected(
        self,
        difference_id: int,
        *,
        expected_row_version: int,
        rejected_by: int,
        rejected_at: datetime,
        basis: str | None,
    ) -> None:
        ...

    def touch_comparison_run(
        self,
        difference_id: int,
        *,
        comparison_run_id: int,
    ) -> None:
        ...


class ComparisonRunWriteRepository(Protocol):
    def insert_comparison_run(
        self,
        *,
        batch_id: int,
        mrd_id: int,
        report_period: date,
        started_by: int | None,
        stats: Mapping[str, int],
    ) -> int:
        ...

    def complete_comparison_run(self, comparison_run_id: int, *, stats: Mapping[str, int]) -> None:
        ...


class ConfirmedChangeWriteRepository(Protocol):
    def insert_confirmed_change(
        self,
        *,
        difference: DetectedDifferenceRecord,
        confirmed_by: int,
        confirmed_at: datetime,
        basis: str | None,
    ) -> int:
        ...


class MrdEntryWriteRepository(Protocol):
    def apply_attribute_change(
        self,
        *,
        mrd_id: int,
        match_key: str,
        entity_scope: str,
        record_kind: str,
        attribute: str,
        old_value: Any,
        new_value: Any,
        confirmed_change_id: int,
    ) -> int | None:
        ...
