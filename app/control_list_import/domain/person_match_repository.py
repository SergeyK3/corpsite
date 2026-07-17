"""Read-only Person lookup port for import matching (WP-CL-005)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Protocol


@dataclass(frozen=True, slots=True)
class PersonLookupRecord:
    """Minimal Person slice for read-only matching."""

    person_id: int
    person_status: str
    merged_into_person_id: Optional[int]
    iin: Optional[str]
    full_name: str
    birth_date: Optional[date]
    match_key: str


class PersonMatchReadPort(Protocol):
    """Read-only access to canonical Person rows for import matching."""

    def find_by_iin(self, iin: str) -> tuple[PersonLookupRecord, ...]:
        """Find active/inactive persons with exact IIN."""

    def find_by_fio_and_birth_date(
        self,
        *,
        normalized_fio_key: str,
        birth_date: date,
    ) -> tuple[PersonLookupRecord, ...]:
        """Find active/inactive persons with normalized FIO and birth date."""

    def find_by_normalized_fio(self, normalized_fio_key: str) -> tuple[PersonLookupRecord, ...]:
        """Find active/inactive persons with normalized FIO only."""

    def resolve_survivor(self, person_id: int) -> int:
        """Follow merged Person chain to canonical survivor."""

    def load_person(self, person_id: int) -> PersonLookupRecord | None:
        """Load one Person row by id (any status) for merge redirect enrichment."""
