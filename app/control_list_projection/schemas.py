"""Typed internal contract for the control-list read projection."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ControlListAssignmentViolation = Literal[
    "MISSING_PRIMARY_ASSIGNMENT",
    "MULTIPLE_PRIMARY_ASSIGNMENTS",
]


class ControlListEducationItem(BaseModel):
    record_id: int
    institution_name: str | None = None
    graduation_year: int | None = None
    specialty: str | None = None
    started_at: date | None = None
    completed_at: date | None = None


class ControlListTrainingItem(BaseModel):
    record_id: int
    title: str | None = None
    organization_name: str | None = None
    hours: Decimal | None = None
    started_at: date | None = None
    completed_at: date | None = None
    certificate_number: str | None = None


class ControlListAcademicDegreeItem(BaseModel):
    ordinal: int = Field(ge=0)
    degree: str | None = None
    degree_other: str | None = None
    field_of_science: str | None = None
    completed_at: str | None = None
    document_number: str | None = None
    label: str | None = None
    degree_type: str | None = None


class ControlListAwardItem(BaseModel):
    ordinal: int = Field(ge=0)
    category: str | None = None
    name: str | None = None
    issued_by: str | None = None
    awarded_at: str | None = None
    document_number: str | None = None


class ControlListPhoneItem(BaseModel):
    contact_id: int
    value: str


class ControlListProjectionRow(BaseModel):
    """One employee row; collections remain structured for later renderers."""

    number: int = Field(ge=1)
    org_group: str | None = None
    org_unit: str
    full_name: str
    birth_date: date | None = None
    iin: str | None = None
    position: str | None = None
    position_category: str | None = None
    employment_rate: Decimal | None = None
    assignment_start_date: date
    education: list[ControlListEducationItem] = Field(default_factory=list)
    training: list[ControlListTrainingItem] = Field(default_factory=list)
    academic_degrees: list[ControlListAcademicDegreeItem] = Field(default_factory=list)
    academic_degrees_none: bool = False
    awards: list[ControlListAwardItem] = Field(default_factory=list)
    awards_none: bool = False
    phones: list[ControlListPhoneItem] = Field(default_factory=list)
    employee_id: int
    missing_fields: list[str] = Field(default_factory=list)


class ControlListProjectionScope(BaseModel):
    organization_wide: bool
    org_unit_ids: list[int] | None = None


class ControlListProjectionFilters(BaseModel):
    """MVP exposes no user-selected filters or historical as-of parameter."""

    model_config = ConfigDict(extra="forbid")


class ControlListProjectionMetadata(BaseModel):
    schema_version: Literal["CONTROL_LIST_EXPORT_V1"]
    as_of_date: date
    generated_at: datetime
    timezone: str
    initiator_user_id: int
    scope: ControlListProjectionScope
    filters: ControlListProjectionFilters = Field(default_factory=ControlListProjectionFilters)


class ControlListProjectionResponse(BaseModel):
    metadata: ControlListProjectionMetadata
    total: int = Field(ge=0)
    items: list[ControlListProjectionRow] = Field(default_factory=list)


class ControlListAssignmentConflictItem(BaseModel):
    employee_id: int
    violation: ControlListAssignmentViolation


class ControlListAssignmentConflictDetail(BaseModel):
    code: Literal["CONTROL_LIST_ASSIGNMENT_CONFLICT"]
    message: str
    schema_version: Literal["CONTROL_LIST_EXPORT_V1"]
    as_of_date: date
    conflicts: list[ControlListAssignmentConflictItem] = Field(min_length=1)
