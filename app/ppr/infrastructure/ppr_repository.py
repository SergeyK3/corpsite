"""SQLAlchemy adapter for PprRepository (personnel_record_metadata)."""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection, RowMapping

from app.db.models.personnel_record_metadata import PersonnelRecordMetadata
from app.ppr.domain.errors import (
    PprEnvelopeAlreadyExistsError,
    PprEnvelopeNotFoundError,
    PprOptimisticConcurrencyConflictError,
)
from app.ppr.domain.models import PprEnvelope

_ENVELOPE_COLUMNS = (
    PersonnelRecordMetadata.person_id,
    PersonnelRecordMetadata.ppr_lifecycle_state,
    PersonnelRecordMetadata.hr_relationship_context,
    PersonnelRecordMetadata.version,
    PersonnelRecordMetadata.created_at,
    PersonnelRecordMetadata.updated_at,
)


def _mapping_to_envelope(row: RowMapping | dict[str, Any]) -> PprEnvelope:
    return PprEnvelope(
        person_id=int(row["person_id"]),
        lifecycle_state=str(row["ppr_lifecycle_state"]),
        hr_relationship_context=str(row["hr_relationship_context"]),
        version=int(row["version"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class SqlAlchemyPprRepository:
    """Envelope persistence adapter — does not commit; caller owns transaction."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def exists_envelope(self, person_id: int) -> bool:
        stmt = (
            select(PersonnelRecordMetadata.person_id)
            .where(PersonnelRecordMetadata.person_id == person_id)
            .limit(1)
        )
        return self._conn.execute(stmt).first() is not None

    def load_envelope(self, person_id: int) -> PprEnvelope | None:
        stmt = select(*_ENVELOPE_COLUMNS).where(PersonnelRecordMetadata.person_id == person_id)
        row = self._conn.execute(stmt).mappings().one_or_none()
        if row is None:
            return None
        return _mapping_to_envelope(row)

    def _require_loaded(self, person_id: int) -> PprEnvelope:
        loaded = self.load_envelope(person_id)
        if loaded is None:
            raise PprEnvelopeNotFoundError(f"PPR envelope not found for person_id={person_id}")
        return loaded

    def insert_envelope(self, envelope: PprEnvelope) -> PprEnvelope:
        stmt = (
            pg_insert(PersonnelRecordMetadata)
            .values(
                person_id=envelope.person_id,
                ppr_lifecycle_state=envelope.lifecycle_state,
                hr_relationship_context=envelope.hr_relationship_context,
                version=envelope.version,
            )
            .on_conflict_do_nothing(index_elements=["person_id"])
            .returning(*_ENVELOPE_COLUMNS)
        )
        row = self._conn.execute(stmt).mappings().one_or_none()
        if row is None:
            raise PprEnvelopeAlreadyExistsError(
                f"PPR envelope already exists for person_id={envelope.person_id}"
            )
        return _mapping_to_envelope(row)

    def update_envelope(self, envelope: PprEnvelope, *, expected_version: int) -> PprEnvelope:
        stmt = (
            update(PersonnelRecordMetadata)
            .where(
                PersonnelRecordMetadata.person_id == envelope.person_id,
                PersonnelRecordMetadata.version == expected_version,
            )
            .values(
                ppr_lifecycle_state=envelope.lifecycle_state,
                hr_relationship_context=envelope.hr_relationship_context,
                version=expected_version + 1,
                updated_at=func.now(),
            )
        )
        result = self._conn.execute(stmt)
        if result.rowcount == 1:
            return self._require_loaded(envelope.person_id)

        if not self.exists_envelope(envelope.person_id):
            raise PprEnvelopeNotFoundError(
                f"PPR envelope not found for person_id={envelope.person_id}"
            )
        raise PprOptimisticConcurrencyConflictError(
            f"Stale version for person_id={envelope.person_id}: expected={expected_version}"
        )
