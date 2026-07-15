"""Domain-shaped PPR section records (R4 — person-owned section SoT)."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Union

from app.db.models.personnel_migration import (
    LIFECYCLE_STATUS_ACTIVE,
    VERIFICATION_STATUS_PENDING,
)

SECTION_CODE_PPR_EDUCATION = "PPR-EDUCATION"
SECTION_CODE_PPR_TRAINING = "PPR-TRAINING"

SUPPORTED_SECTION_CODES: frozenset[str] = frozenset(
    {SECTION_CODE_PPR_EDUCATION, SECTION_CODE_PPR_TRAINING}
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


SectionRecord = Union[EducationRecord, TrainingRecord]


@dataclass(frozen=True, slots=True)
class SectionMutationResult:
    """Outcome of a domain section handler — primary record plus optional supersede prior."""

    record: SectionRecord
    mutation_kind: str
    prior_record: SectionRecord | None = None
