"""Domain-shaped PPR section records (R4 — person-owned section SoT)."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Union

from app.db.models.personnel_migration import (
    EXTERNAL_EMPLOYMENT_SOURCE_MANUAL,
    LIFECYCLE_STATUS_ACTIVE,
    SECTION_SOURCE_TYPE_ENTERED,
    VERIFICATION_STATUS_PENDING,
)

SECTION_CODE_PPR_EDUCATION = "PPR-EDUCATION"
SECTION_CODE_PPR_TRAINING = "PPR-TRAINING"
SECTION_CODE_PPR_FAMILY = "PPR-FAMILY"
SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY = "PPR-EMPLOYMENT-BIOGRAPHY"
SECTION_CODE_PPR_MILITARY = "PPR-MILITARY"

SUPPORTED_SECTION_CODES: frozenset[str] = frozenset(
    {
        SECTION_CODE_PPR_EDUCATION,
        SECTION_CODE_PPR_TRAINING,
        SECTION_CODE_PPR_FAMILY,
        SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY,
        SECTION_CODE_PPR_MILITARY,
    }
)

# Optimistic concurrency for section updates (WP-PR-010 OQ-4).
# Schema has no record_version yet; updated_at is the temporary compare-and-swap token.
SECTION_OPTIMISTIC_TOKEN_FIELD = "updated_at"
SECTION_OPTIMISTIC_TOKEN_DOC = "updated_at (temporary until record_version column exists)"

MUTATION_KIND_INSERT = "insert"
MUTATION_KIND_UPDATE = "update"
MUTATION_KIND_VOID = "void"
MUTATION_KIND_SUPERSEDE = "supersede"


@dataclass(frozen=True, slots=True)
class EducationRecord:
    """Domain record for person_education (not ORM)."""

    person_id: int
    education_kind: str
    record_id: int | None = None
    employee_context_id: int | None = None
    institution_type: str | None = None
    institution_name: str | None = None
    specialty: str | None = None
    qualification: str | None = None
    started_at: date | None = None
    completed_at: date | None = None
    diploma_number: str | None = None
    document_date: date | None = None
    verification_status: str = VERIFICATION_STATUS_PENDING
    lifecycle_status: str = LIFECYCLE_STATUS_ACTIVE
    created_at: datetime | None = None
    updated_at: datetime | None = None  # temporary optimistic token until record_version exists
    metadata: Mapping[str, Any] | None = None

    @property
    def section_code(self) -> str:
        return SECTION_CODE_PPR_EDUCATION


@dataclass(frozen=True, slots=True)
class TrainingRecord:
    """Domain record for person_training (not ORM)."""

    person_id: int
    training_kind: str
    record_id: int | None = None
    employee_context_id: int | None = None
    title: str | None = None
    organization_name: str | None = None
    hours: Decimal | None = None
    started_at: date | None = None
    completed_at: date | None = None
    certificate_number: str | None = None
    document_date: date | None = None
    verification_status: str = VERIFICATION_STATUS_PENDING
    lifecycle_status: str = LIFECYCLE_STATUS_ACTIVE
    created_at: datetime | None = None
    updated_at: datetime | None = None  # temporary optimistic token until record_version exists
    metadata: Mapping[str, Any] | None = None

    @property
    def section_code(self) -> str:
        return SECTION_CODE_PPR_TRAINING


@dataclass(frozen=True, slots=True)
class RelativeRecord:
    """Domain record for person_relatives (not ORM)."""

    person_id: int
    relationship_type: str
    full_name: str
    record_id: int | None = None
    birth_date: date | None = None
    birth_place: str | None = None
    organization_name: str | None = None
    residence_address: str | None = None
    notes: str | None = None
    verification_status: str = VERIFICATION_STATUS_PENDING
    lifecycle_status: str = LIFECYCLE_STATUS_ACTIVE
    source_type: str = SECTION_SOURCE_TYPE_ENTERED
    created_at: datetime | None = None
    updated_at: datetime | None = None  # temporary optimistic token until record_version exists
    metadata: Mapping[str, Any] | None = None

    @property
    def section_code(self) -> str:
        return SECTION_CODE_PPR_FAMILY


@dataclass(frozen=True, slots=True)
class ExternalEmploymentRecord:
    """Domain record for person_external_employment (not ORM)."""

    person_id: int
    record_kind: str
    record_id: int | None = None
    employer_name: str | None = None
    department_name: str | None = None
    position_title: str | None = None
    employment_type: str | None = None
    started_at: date | None = None
    ended_at: date | None = None
    termination_reason: str | None = None
    document_reference: str | None = None
    source_system: str = EXTERNAL_EMPLOYMENT_SOURCE_MANUAL
    source_id: str | None = None
    provenance: Mapping[str, Any] | None = None
    verification_status: str = VERIFICATION_STATUS_PENDING
    lifecycle_status: str = LIFECYCLE_STATUS_ACTIVE
    notes: str | None = None
    employee_context_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None  # temporary optimistic token until record_version exists
    metadata: Mapping[str, Any] | None = None

    @property
    def section_code(self) -> str:
        return SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY


@dataclass(frozen=True, slots=True)
class MilitaryServiceRecord:
    """Domain record for person_military_service (not ORM)."""

    person_id: int
    record_kind: str
    record_id: int | None = None
    obligation_status: str | None = None
    registration_category: str | None = None
    military_rank: str | None = None
    military_specialty_code: str | None = None
    personnel_composition: str | None = None
    fitness_category: str | None = None
    registration_status: str | None = None
    commissariat_name: str | None = None
    registered_at: date | None = None
    deregistered_at: date | None = None
    military_id_book_series: str | None = None
    military_id_book_number: str | None = None
    registration_certificate_series: str | None = None
    registration_certificate_number: str | None = None
    notes: str | None = None
    verification_status: str = VERIFICATION_STATUS_PENDING
    lifecycle_status: str = LIFECYCLE_STATUS_ACTIVE
    source_type: str = SECTION_SOURCE_TYPE_ENTERED
    provenance: Mapping[str, Any] | None = None
    employee_context_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None  # temporary optimistic token until record_version exists
    metadata: Mapping[str, Any] | None = None

    @property
    def section_code(self) -> str:
        return SECTION_CODE_PPR_MILITARY


SectionRecord = Union[EducationRecord, TrainingRecord, RelativeRecord, ExternalEmploymentRecord, MilitaryServiceRecord]


@dataclass(frozen=True, slots=True)
class SectionMutationResult:
    """Outcome of a domain section handler — primary record plus optional supersede prior."""

    record: SectionRecord
    mutation_kind: str
    prior_record: SectionRecord | None = None
