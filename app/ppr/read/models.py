"""Immutable composite read DTOs for PPR query layer (R6)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.ppr.domain.event_models import PprEventRecord
from app.ppr.domain.identity_models import IdentityResolution, PersonIdentitySnapshot
from app.ppr.domain.models import PPR_LIFECYCLE_NOT_MATERIALIZED
from app.ppr.domain.person_models import PersonGeneralReadSnapshot
from app.ppr.domain.section_models import SectionRecord


@dataclass(frozen=True, slots=True)
class PprEnvelopeReadSlice:
    """Envelope projection — logical NOT_MATERIALIZED when aggregate absent."""

    materialized: bool
    lifecycle_state: str
    hr_relationship_context: str | None
    version: int | None
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def not_materialized(cls) -> PprEnvelopeReadSlice:
        return cls(
            materialized=False,
            lifecycle_state=PPR_LIFECYCLE_NOT_MATERIALIZED,
            hr_relationship_context=None,
            version=None,
            created_at=None,
            updated_at=None,
        )


@dataclass(frozen=True, slots=True)
class PprSectionAggregation:
    """Section records grouped by lifecycle bucket."""

    section_code: str
    active: tuple[SectionRecord, ...]
    superseded: tuple[SectionRecord, ...] = ()
    voided: tuple[SectionRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class PprEventSummaryEntry:
    """Lightweight event row for composite read (not full payload)."""

    event_id: int
    event_type: str
    category: str
    record_table_name: str
    record_id: int
    occurred_at: datetime
    section_code: str | None = None
    domain_code: str | None = None

    @classmethod
    def from_record(cls, record: PprEventRecord) -> PprEventSummaryEntry:
        return cls(
            event_id=record.event_id,
            event_type=record.event_type,
            category=record.category,
            record_table_name=record.record_table_name,
            record_id=record.record_id,
            occurred_at=record.occurred_at,
            section_code=record.section_code,
            domain_code=record.domain_code,
        )


@dataclass(frozen=True, slots=True)
class PprEventSummary:
    """Recent events summary — not full history."""

    recent: tuple[PprEventSummaryEntry, ...]
    returned_count: int
    limit: int


@dataclass(frozen=True, slots=True)
class PprIntendedEmploymentReadSlice:
    org_group_id: int | None
    org_unit_id: int | None
    position_id: int | None
    employment_rate: float | None
    org_group_name: str | None = None
    org_unit_name: str | None = None
    position_name: str | None = None


@dataclass(frozen=True, slots=True)
class PprCompositeReadMetadata:
    """Assembly metadata attached to every composite read."""

    evaluated_at: datetime
    source_person_id: int
    merge_redirected: bool
    requested_input_kind: str | None = None
    requested_input_id: int | None = None


@dataclass(frozen=True, slots=True)
class PprCompositeReadModel:
    """Unified PPR read model — immutable, no ORM, no lazy loading."""

    person_id: int
    employee_id: int | None
    materialized: bool
    lifecycle_state: str
    hr_relationship_context: str | None
    envelope_version: int | None
    envelope_created_at: datetime | None
    envelope_updated_at: datetime | None
    identity: PersonIdentitySnapshot
    identity_resolution: IdentityResolution
    general: PersonGeneralReadSnapshot
    education: PprSectionAggregation
    training: PprSectionAggregation
    family: PprSectionAggregation
    events: PprEventSummary | None
    intended_employment: PprIntendedEmploymentReadSlice | None
    metadata: PprCompositeReadMetadata


@dataclass(frozen=True, slots=True)
class PprCompositeSummary:
    """Lightweight summary projection for registry-style reads."""

    person_id: int
    employee_id: int | None
    materialized: bool
    lifecycle_state: str
    hr_relationship_context: str | None
    identity: PersonIdentitySnapshot
    identity_resolution: IdentityResolution
    full_name: str
    education_active_count: int
    training_active_count: int
    family_active_count: int
    recent_event_count: int
    metadata: PprCompositeReadMetadata
