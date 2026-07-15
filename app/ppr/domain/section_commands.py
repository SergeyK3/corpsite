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


@dataclass(frozen=True, slots=True)
class SupersedeEducationRecord:
    person_id: int
    record_id: int
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


@dataclass(frozen=True, slots=True)
class SupersedeTrainingRecord:
    person_id: int
    record_id: int
    replacement: AddTrainingRecord
