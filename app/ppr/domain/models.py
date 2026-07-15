"""PPR envelope domain types and lifecycle constants (WP-PR-004)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# Materialized PPR lifecycle states (stored on envelope).
PPR_LIFECYCLE_CREATED = "CREATED"
PPR_LIFECYCLE_COLLECTING = "COLLECTING"
PPR_LIFECYCLE_READY = "READY"
PPR_LIFECYCLE_ACTIVE = "ACTIVE"
PPR_LIFECYCLE_ARCHIVED = "ARCHIVED"
PPR_LIFECYCLE_MERGED = "MERGED"

PPR_LIFECYCLE_STATES = (
    PPR_LIFECYCLE_CREATED,
    PPR_LIFECYCLE_COLLECTING,
    PPR_LIFECYCLE_READY,
    PPR_LIFECYCLE_ACTIVE,
    PPR_LIFECYCLE_ARCHIVED,
    PPR_LIFECYCLE_MERGED,
)

# Pre-lifecycle logical state — not stored on envelope row.
PPR_LIFECYCLE_NOT_MATERIALIZED = "NOT_MATERIALIZED"

# HR relationship context labels (informational; WP-PR-004 §3.3).
HR_RELATIONSHIP_CANDIDATE = "CANDIDATE"
HR_RELATIONSHIP_EMPLOYED = "EMPLOYED"
HR_RELATIONSHIP_FORMER_EMPLOYEE = "FORMER_EMPLOYEE"
HR_RELATIONSHIP_UNKNOWN = "UNKNOWN"

HR_RELATIONSHIP_CONTEXTS = (
    HR_RELATIONSHIP_CANDIDATE,
    HR_RELATIONSHIP_EMPLOYED,
    HR_RELATIONSHIP_FORMER_EMPLOYEE,
    HR_RELATIONSHIP_UNKNOWN,
)

# Safe defaults for new envelope rows (MaterializePPR will use these in R5).
PPR_ENVELOPE_INITIAL_LIFECYCLE_STATE = PPR_LIFECYCLE_CREATED
PPR_ENVELOPE_INITIAL_HR_RELATIONSHIP_CONTEXT = HR_RELATIONSHIP_UNKNOWN
PPR_ENVELOPE_INITIAL_VERSION = 1


@dataclass(frozen=True, slots=True)
class PprEnvelope:
    """Domain-shaped aggregate envelope snapshot (not raw ORM row)."""

    person_id: int
    lifecycle_state: str
    hr_relationship_context: str
    version: int
    created_at: datetime
    updated_at: datetime

    def with_updates(
        self,
        *,
        lifecycle_state: str | None = None,
        hr_relationship_context: str | None = None,
        version: int | None = None,
        updated_at: datetime | None = None,
    ) -> PprEnvelope:
        return PprEnvelope(
            person_id=self.person_id,
            lifecycle_state=lifecycle_state if lifecycle_state is not None else self.lifecycle_state,
            hr_relationship_context=(
                hr_relationship_context
                if hr_relationship_context is not None
                else self.hr_relationship_context
            ),
            version=version if version is not None else self.version,
            created_at=self.created_at,
            updated_at=updated_at if updated_at is not None else self.updated_at,
        )
