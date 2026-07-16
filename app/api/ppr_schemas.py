"""PPR composite read API schemas (R7 — separate from R6 domain DTOs)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PprIdentityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    requested_person_id: int | None = None
    requested_employee_id: int | None = None
    resolved_person_id: int
    merge_redirected: bool
    merge_chain: list[int] = Field(default_factory=list)
    employee_context_id: int | None = None
    person_status: str
    match_key: str
    iin: str | None = None


class PprMaterializationResponse(BaseModel):
    materialized: bool
    lifecycle_state: str
    hr_relationship_context: str | None = None
    envelope_version: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PprIntendedEmploymentResponse(BaseModel):
    org_group_id: int | None = None
    org_unit_id: int | None = None
    position_id: int | None = None
    employment_rate: float | None = None
    org_group_name: str | None = None
    org_unit_name: str | None = None
    position_name: str | None = None


class PprIntendedEmploymentUpdateRequest(BaseModel):
    org_group_id: int | None = Field(default=None, ge=1)
    org_unit_id: int | None = Field(default=None, ge=1)
    position_id: int | None = Field(default=None, ge=1)
    employment_rate: float | None = Field(default=None, gt=0, le=2)


class PprHireDefaultsResponse(BaseModel):
    person_id: int
    org_group_id: int | None = None
    org_unit_id: int | None = None
    position_id: int | None = None
    employment_rate: float | None = None
    org_group_name: str | None = None
    org_unit_name: str | None = None
    position_name: str | None = None


class PprGeneralResponse(BaseModel):
    full_name: str
    last_name: str | None = None
    first_name: str | None = None
    middle_name: str | None = None
    birth_date: date | None = None
    iin: str | None = None
    created_at: datetime
    updated_at: datetime


class PprEducationRecordResponse(BaseModel):
    record_id: int | None = None
    education_kind: str
    institution_type: str | None = None
    institution_name: str | None = None
    specialty: str | None = None
    qualification: str | None = None
    started_at: date | None = None
    completed_at: date | None = None
    diploma_number: str | None = None
    document_date: date | None = None
    verification_status: str
    lifecycle_status: str


class PprTrainingRecordResponse(BaseModel):
    record_id: int | None = None
    training_kind: str
    title: str | None = None
    organization_name: str | None = None
    hours: Decimal | None = None
    started_at: date | None = None
    completed_at: date | None = None
    certificate_number: str | None = None
    document_date: date | None = None
    verification_status: str
    lifecycle_status: str


class PprSectionResponse(BaseModel):
    section_code: str
    active: list[PprEducationRecordResponse | PprTrainingRecordResponse] = Field(default_factory=list)
    superseded: list[PprEducationRecordResponse | PprTrainingRecordResponse] = Field(default_factory=list)
    voided: list[PprEducationRecordResponse | PprTrainingRecordResponse] = Field(default_factory=list)


class PprEventSummaryItemResponse(BaseModel):
    event_id: int
    event_type: str
    category: str
    record_table_name: str
    record_id: int
    occurred_at: datetime
    section_code: str | None = None
    domain_code: str | None = None


class PprEventSummaryResponse(BaseModel):
    recent: list[PprEventSummaryItemResponse] = Field(default_factory=list)
    returned_count: int
    limit: int


class PprReadMetadataResponse(BaseModel):
    read_mode: str
    source: str
    generated_at: datetime
    warnings: list[str] = Field(default_factory=list)
    transitional: bool = False
    merge_redirected: bool = False
    source_person_id: int
    requested_input_kind: str | None = None
    requested_input_id: int | None = None


class PprCompositeReadResponse(BaseModel):
    identity: PprIdentityResponse
    materialization: PprMaterializationResponse
    general: PprGeneralResponse
    sections: dict[str, PprSectionResponse]
    events: PprEventSummaryResponse | None = None
    intended_employment: PprIntendedEmploymentResponse | None = None
    metadata: PprReadMetadataResponse


class PprCompositeSummaryResponse(BaseModel):
    identity: PprIdentityResponse
    materialization: PprMaterializationResponse
    full_name: str
    education_active_count: int
    training_active_count: int
    recent_event_count: int
    metadata: PprReadMetadataResponse
