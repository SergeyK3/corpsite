"""PPR command API schemas — employment biography mutations (WP-PR-016)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PprExternalEmploymentRecordWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_kind: str
    employee_context_id: int | None = Field(default=None, ge=1)
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
    provenance: dict[str, Any] | None = None
    notes: str | None = None
    metadata: dict[str, Any] | None = None


class PprExternalEmploymentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: str = Field(min_length=1)
    correlation_id: str | None = None
    record: PprExternalEmploymentRecordWrite


class PprExternalEmploymentVoidRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: str = Field(min_length=1)
    correlation_id: str | None = None
    reason: str = Field(min_length=1)
    expected_updated_at: datetime


class PprExternalEmploymentSupersedeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: str = Field(min_length=1)
    correlation_id: str | None = None
    expected_updated_at: datetime
    replacement: PprExternalEmploymentRecordWrite


class PprMilitaryServiceRecordWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_kind: str
    employee_context_id: int | None = Field(default=None, ge=1)
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
    provenance: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class PprMilitaryServiceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: str = Field(min_length=1)
    correlation_id: str | None = None
    record: PprMilitaryServiceRecordWrite


class PprMilitaryServiceVoidRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: str = Field(min_length=1)
    correlation_id: str | None = None
    reason: str = Field(min_length=1)
    expected_updated_at: datetime


class PprMilitaryServiceSupersedeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: str = Field(min_length=1)
    correlation_id: str | None = None
    expected_updated_at: datetime
    replacement: PprMilitaryServiceRecordWrite


class PprCommandMutationResponse(BaseModel):
    command_id: str
    command_type: str
    status: str
    resolved_person_id: int
    section_code: str
    section_record_id: int | None = None
    section_mutation_kind: str | None = None
    event_ids: list[int] = Field(default_factory=list)
    envelope_version: int | None = None
    correlation_id: str | None = None
