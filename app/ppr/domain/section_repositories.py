"""Section read/mutation repository contracts (WP-PR-010 §4.5, R4.1 split)."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.ppr.domain.section_models import SectionRecord


class SectionReadRepository(Protocol):
    """Read-only section access — safe via UnitOfWork.sections."""

    def load_active_records(self, person_id: int, section_code: str) -> tuple[SectionRecord, ...]:
        """All active rows for person + section_code."""
        ...

    def load_record(
        self,
        person_id: int,
        section_code: str,
        record_id: int,
    ) -> SectionRecord | None:
        """Single section row or None."""
        ...


class SectionMutationRepository(Protocol):
    """Append/update section rows — use via SectionMutationContext in domain handlers."""

    def insert_record(self, record: SectionRecord) -> SectionRecord:
        """Insert new section row; returns persisted record with generated id/timestamps."""
        ...

    def update_record(
        self,
        record: SectionRecord,
        *,
        expected_updated_at: datetime,
    ) -> SectionRecord:
        """Update active row; expected_updated_at is the temporary optimistic token (see section_models)."""
        ...

    def void_record(
        self,
        person_id: int,
        section_code: str,
        record_id: int,
    ) -> SectionRecord:
        """Soft-void active row (lifecycle_status=voided)."""
        ...

    def supersede_pair(
        self,
        person_id: int,
        section_code: str,
        old_record_id: int,
        new_record: SectionRecord,
    ) -> tuple[SectionRecord, SectionRecord]:
        """Mark old row superseded and insert replacement atomically in caller transaction."""
        ...
