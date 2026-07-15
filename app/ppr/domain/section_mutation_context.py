"""Handler-scoped section mutation access (R4.1 — not exposed on read repository)."""
from __future__ import annotations

from datetime import datetime

from app.ppr.domain.section_models import SectionRecord
from app.ppr.domain.section_repositories import SectionMutationRepository


class SectionMutationContext:
    """Write scope for domain handlers.

    Obtain via ``UnitOfWork.section_mutations()`` only — ``UnitOfWork.sections`` is read-only.
    Does not commit; caller/UoW owns the transaction.
    """

    __slots__ = ("_mutations",)

    def __init__(self, mutations: SectionMutationRepository) -> None:
        self._mutations = mutations

    def insert_record(self, record: SectionRecord) -> SectionRecord:
        return self._mutations.insert_record(record)

    def update_record(
        self,
        record: SectionRecord,
        *,
        expected_updated_at: datetime,
    ) -> SectionRecord:
        return self._mutations.update_record(record, expected_updated_at=expected_updated_at)

    def void_record(
        self,
        person_id: int,
        section_code: str,
        record_id: int,
    ) -> SectionRecord:
        return self._mutations.void_record(person_id, section_code, record_id)

    def supersede_pair(
        self,
        person_id: int,
        section_code: str,
        old_record_id: int,
        new_record: SectionRecord,
    ) -> tuple[SectionRecord, SectionRecord]:
        return self._mutations.supersede_pair(
            person_id,
            section_code,
            old_record_id,
            new_record,
        )
