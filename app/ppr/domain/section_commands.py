"""PPR domain commands for section mutations (R4 — not REST/API)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class AddEducationRecord:
    person_id: int
    education_kind: str
    employee_context_id: int | None = None
    institution_type: str | None = None
    institution_name: str | None = None
    specialty: str | None = None
    qualification: str | None = None
    started_at: date | None = None
    completed_at: date | None = None
    diploma_number: str | None = None
    document_date: date | None = None
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class UpdateEducationRecord:
    person_id: int
    record_id: int
    expected_updated_at: datetime
    education_kind: str | None = None
    institution_type: str | None = None
    institution_name: str | None = None
    specialty: str | None = None
    qualification: str | None = None
    started_at: date | None = None
    completed_at: date | None = None
    diploma_number: str | None = None
    document_date: date | None = None
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class VoidEducationRecord:
    person_id: int
    record_id: int
    reason: str
    expected_updated_at: datetime


@dataclass(frozen=True, slots=True)
class SupersedeEducationRecord:
    person_id: int
    record_id: int
    expected_updated_at: datetime
    replacement: AddEducationRecord


@dataclass(frozen=True, slots=True)
class AddTrainingRecord:
    person_id: int
    training_kind: str
    employee_context_id: int | None = None
    title: str | None = None
    organization_name: str | None = None
    hours: Decimal | None = None
    started_at: date | None = None
    completed_at: date | None = None
    certificate_number: str | None = None
    document_date: date | None = None
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class UpdateTrainingRecord:
    person_id: int
    record_id: int
    expected_updated_at: datetime
    training_kind: str | None = None
    title: str | None = None
    organization_name: str | None = None
    hours: Decimal | None = None
    started_at: date | None = None
    completed_at: date | None = None
    certificate_number: str | None = None
    document_date: date | None = None
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class VoidTrainingRecord:
    person_id: int
    record_id: int
    reason: str
    expected_updated_at: datetime


@dataclass(frozen=True, slots=True)
class SupersedeTrainingRecord:
    person_id: int
    record_id: int
    expected_updated_at: datetime
    replacement: AddTrainingRecord


@dataclass(frozen=True, slots=True)
class AddRelativeRecord:
    person_id: int
    relationship_type: str
    full_name: str
    birth_date: date | None = None
    birth_place: str | None = None
    organization_name: str | None = None
    residence_address: str | None = None
    notes: str | None = None
    source_type: str | None = None
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class UpdateRelativeRecord:
    person_id: int
    record_id: int
    expected_updated_at: datetime
    relationship_type: str | None = None
    full_name: str | None = None
    birth_date: date | None = None
    birth_place: str | None = None
    organization_name: str | None = None
    residence_address: str | None = None
    notes: str | None = None
    source_type: str | None = None
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class VoidRelativeRecord:
    person_id: int
    record_id: int
    reason: str
    expected_updated_at: datetime


@dataclass(frozen=True, slots=True)
class SupersedeRelativeRecord:
    person_id: int
    record_id: int
    expected_updated_at: datetime
    replacement: AddRelativeRecord


@dataclass(frozen=True, slots=True)
class AddExternalEmploymentRecord:
    person_id: int
    record_kind: str
    employee_context_id: int | None = None
    employer_name: str | None = None
    department_name: str | None = None
    position_title: str | None = None
    employment_type: str | None = None
    started_at: date | None = None
    ended_at: date | None = None
    termination_reason: str | None = None
    document_reference: str | None = None
    source_system: str | None = None
    source_id: str | None = None
    provenance: Mapping[str, Any] | None = None
    notes: str | None = None
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class VoidExternalEmploymentRecord:
    person_id: int
    record_id: int
    reason: str
    expected_updated_at: datetime


@dataclass(frozen=True, slots=True)
class SupersedeExternalEmploymentRecord:
    person_id: int
    record_id: int
    expected_updated_at: datetime
    replacement: AddExternalEmploymentRecord


@dataclass(frozen=True, slots=True)
class CreateMilitaryServiceRecord:
    person_id: int
    record_kind: str
    employee_context_id: int | None = None
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
    source_type: str | None = None
    provenance: Mapping[str, Any] | None = None
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class VoidMilitaryServiceRecord:
    person_id: int
    record_id: int
    reason: str
    expected_updated_at: datetime


@dataclass(frozen=True, slots=True)
class SupersedeMilitaryServiceRecord:
    person_id: int
    record_id: int
    expected_updated_at: datetime
    replacement: CreateMilitaryServiceRecord
