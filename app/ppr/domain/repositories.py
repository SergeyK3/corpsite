"""PPR repository contracts (WP-PR-010 §4.2)."""
from __future__ import annotations

from typing import Protocol

from app.ppr.domain.models import PprEnvelope


class PprRepository(Protocol):
    """Envelope repository — owns personnel_record_metadata only."""

    def exists_envelope(self, person_id: int) -> bool:
        """Return True when a materialized envelope row exists for person_id."""

    def load_envelope(self, person_id: int) -> PprEnvelope | None:
        """Load envelope or None when not materialized. Never auto-creates."""

    def insert_envelope(self, envelope: PprEnvelope) -> PprEnvelope:
        """Insert one envelope row. Rejects duplicate person_id."""

    def update_envelope(self, envelope: PprEnvelope, *, expected_version: int) -> PprEnvelope:
        """Optimistic update; increments version by 1 on success."""
