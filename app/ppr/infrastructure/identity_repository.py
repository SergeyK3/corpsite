"""SQLAlchemy adapter for IdentityRepository."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from app.ppr.domain.errors import (
    PprEmployeeNotFoundError,
    PprEmployeePersonLinkMissingError,
    PprPersonNotFoundError,
)
from app.ppr.domain.identity_models import (
    INPUT_KIND_EMPLOYEE_ID,
    INPUT_KIND_PERSON_ID,
    RESULT_DIRECT,
    RESULT_MERGE_REDIRECTED,
    IdentityResolution,
    PersonIdentitySnapshot,
)
from app.ppr.infrastructure.merge_resolver import resolve_merge_chain

_IDENTITY_COLUMNS = (
    "person_id",
    "person_status",
    "merged_into_person_id",
    "match_key",
    "iin",
)


def _mapping_to_identity(row: RowMapping | dict[str, Any]) -> PersonIdentitySnapshot:
    merged = row.get("merged_into_person_id")
    return PersonIdentitySnapshot(
        person_id=int(row["person_id"]),
        person_status=str(row["person_status"]),
        merged_into_person_id=int(merged) if merged is not None else None,
        match_key=str(row["match_key"]),
        iin=str(row["iin"]) if row.get("iin") is not None else None,
    )


class SqlAlchemyIdentityRepository:
    """Read-only identity resolution — does not commit; caller owns transaction."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def _load_identity_opt(self, person_id: int) -> PersonIdentitySnapshot | None:
        stmt = text(
            """
            SELECT person_id, person_status, merged_into_person_id, match_key, iin
            FROM public.persons
            WHERE person_id = :person_id
            """
        )
        row = self._conn.execute(stmt, {"person_id": person_id}).mappings().one_or_none()
        if row is None:
            return None
        return _mapping_to_identity(row)

    def load_identity(self, person_id: int) -> PersonIdentitySnapshot:
        snapshot = self._load_identity_opt(person_id)
        if snapshot is None:
            raise PprPersonNotFoundError(f"Person not found: person_id={person_id}")
        return snapshot

    def resolve_survivor(self, person_id: int) -> int:
        merge = resolve_merge_chain(person_id, self._load_identity_opt)
        return merge.resolved_person_id

    def resolve_person_id(self, person_id: int) -> IdentityResolution:
        merge = resolve_merge_chain(person_id, self._load_identity_opt)
        return IdentityResolution(
            input_kind=INPUT_KIND_PERSON_ID,
            input_id=person_id,
            employee_id=None,
            source_person_id=merge.source_person_id,
            resolved_person_id=merge.resolved_person_id,
            merge_redirected=merge.merge_redirected,
            merge_chain=merge.merge_chain,
            result_code=RESULT_MERGE_REDIRECTED if merge.merge_redirected else RESULT_DIRECT,
        )

    def resolve_employee_id(self, employee_id: int) -> IdentityResolution:
        row = self._conn.execute(
            text(
                """
                SELECT employee_id, person_id
                FROM public.employees
                WHERE employee_id = :employee_id
                """
            ),
            {"employee_id": employee_id},
        ).mappings().one_or_none()
        if row is None:
            raise PprEmployeeNotFoundError(f"Employee not found: employee_id={employee_id}")
        person_id = row.get("person_id")
        if person_id is None:
            raise PprEmployeePersonLinkMissingError(
                f"Employee {employee_id} has no linked person_id; authoritative PPR path blocked."
            )

        person_resolution = self.resolve_person_id(int(person_id))
        return IdentityResolution(
            input_kind=INPUT_KIND_EMPLOYEE_ID,
            input_id=employee_id,
            employee_id=employee_id,
            source_person_id=person_resolution.source_person_id,
            resolved_person_id=person_resolution.resolved_person_id,
            merge_redirected=person_resolution.merge_redirected,
            merge_chain=person_resolution.merge_chain,
            result_code=person_resolution.result_code,
        )
