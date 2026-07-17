"""Read-only Person lookup adapter for import matching (WP-CL-005)."""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from app.control_list_import.domain.person_match_repository import PersonLookupRecord
from app.control_list_import.matching.keys import person_fio_comparison_key
from app.ppr.domain.identity_models import PersonIdentitySnapshot
from app.ppr.infrastructure.merge_resolver import resolve_merge_chain


def _mapping_to_record(row: RowMapping | dict[str, Any]) -> PersonLookupRecord:
    birth = row.get("birth_date")
    merged = row.get("merged_into_person_id")
    iin = row.get("iin")
    return PersonLookupRecord(
        person_id=int(row["person_id"]),
        person_status=str(row["person_status"]),
        merged_into_person_id=int(merged) if merged is not None else None,
        iin=str(iin) if iin is not None else None,
        full_name=str(row["full_name"]),
        birth_date=birth if isinstance(birth, date) else None,
        match_key=str(row["match_key"]),
    )


class SqlAlchemyPersonMatchReadRepository:
    """SQL adapter for PersonMatchReadPort — read-only, no apply/mutation."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def find_by_iin(self, iin: str) -> tuple[PersonLookupRecord, ...]:
        rows = self._conn.execute(
            text(
                """
                SELECT person_id, person_status, merged_into_person_id, iin, full_name, birth_date, match_key
                FROM public.persons
                WHERE iin = :iin
                  AND person_status IN ('active', 'inactive')
                ORDER BY person_id
                """
            ),
            {"iin": iin},
        ).mappings().all()
        return self._dedupe_resolved(tuple(_mapping_to_record(row) for row in rows))

    def find_by_fio_and_birth_date(
        self,
        *,
        normalized_fio_key: str,
        birth_date: date,
    ) -> tuple[PersonLookupRecord, ...]:
        rows = self._conn.execute(
            text(
                """
                SELECT person_id, person_status, merged_into_person_id, iin, full_name, birth_date, match_key
                FROM public.persons
                WHERE birth_date = :birth_date
                  AND person_status IN ('active', 'inactive')
                ORDER BY person_id
                """
            ),
            {"birth_date": birth_date},
        ).mappings().all()
        matched = [
            _mapping_to_record(row)
            for row in rows
            if person_fio_comparison_key(str(row["full_name"])) == normalized_fio_key
        ]
        return self._dedupe_resolved(tuple(matched))

    def find_by_normalized_fio(self, normalized_fio_key: str) -> tuple[PersonLookupRecord, ...]:
        rows = self._conn.execute(
            text(
                """
                SELECT person_id, person_status, merged_into_person_id, iin, full_name, birth_date, match_key
                FROM public.persons
                WHERE person_status IN ('active', 'inactive')
                ORDER BY person_id
                """
            ),
        ).mappings().all()
        matched = [
            _mapping_to_record(row)
            for row in rows
            if person_fio_comparison_key(str(row["full_name"])) == normalized_fio_key
        ]
        return self._dedupe_resolved(tuple(matched))

    def resolve_survivor(self, person_id: int) -> int:
        merge = resolve_merge_chain(person_id, self._load_identity_opt)
        return merge.resolved_person_id

    def load_person(self, person_id: int) -> PersonLookupRecord | None:
        return self._load_person_opt(person_id)

    def _load_identity_opt(self, person_id: int) -> PersonIdentitySnapshot | None:
        row = self._conn.execute(
            text(
                """
                SELECT person_id, person_status, merged_into_person_id, match_key, iin
                FROM public.persons
                WHERE person_id = :person_id
                """
            ),
            {"person_id": person_id},
        ).mappings().one_or_none()
        if row is None:
            return None
        merged = row.get("merged_into_person_id")
        iin = row.get("iin")
        return PersonIdentitySnapshot(
            person_id=int(row["person_id"]),
            person_status=str(row["person_status"]),
            merged_into_person_id=int(merged) if merged is not None else None,
            match_key=str(row["match_key"]),
            iin=str(iin) if iin is not None else None,
        )

    def _load_person_opt(self, person_id: int) -> Optional[PersonLookupRecord]:
        row = self._conn.execute(
            text(
                """
                SELECT person_id, person_status, merged_into_person_id, iin, full_name, birth_date, match_key
                FROM public.persons
                WHERE person_id = :person_id
                """
            ),
            {"person_id": person_id},
        ).mappings().one_or_none()
        if row is None:
            return None
        return _mapping_to_record(row)

    def _dedupe_resolved(self, records: tuple[PersonLookupRecord, ...]) -> tuple[PersonLookupRecord, ...]:
        deduped: dict[int, PersonLookupRecord] = {}
        for record in records:
            resolved_id = self.resolve_survivor(record.person_id)
            if resolved_id in deduped:
                continue
            if resolved_id == record.person_id:
                deduped[resolved_id] = record
                continue
            survivor = self._load_person_opt(resolved_id)
            deduped[resolved_id] = survivor or record
        return tuple(deduped.values())
