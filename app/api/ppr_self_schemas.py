"""Response contract for the employee-owned PPR read namespace."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.ppr_schemas import (
    PprAdditionalProfileResponse,
    PprGeneralResponse,
    PprMaterializationResponse,
    PprSectionResponse,
)


class PprSelfCardDataResponse(BaseModel):
    """Self-safe projection: no requested/resolved Person or Employee IDs."""

    materialization: PprMaterializationResponse
    general: PprGeneralResponse
    sections: dict[str, PprSectionResponse]
    additional: PprAdditionalProfileResponse


class PprSelfCardResponse(BaseModel):
    """A controlled self-card bootstrap state for the authenticated caller."""

    status: Literal[
        "READY",
        "NO_EMPLOYEE_LINK",
        "PERSON_NOT_LINKED",
        "IDENTITY_AMBIGUOUS",
    ]
    card: PprSelfCardDataResponse | None = None


class PprSelfOperationalAssignmentDataResponse(BaseModel):
    """Current operational employment data for the authenticated employee.

    This projection intentionally contains labels only: neither Person nor
    Employee identifiers are returned to the browser.  The IIN is unmasked
    because the authenticated employee is reading their own record.
    """

    department_group_name: str | None = None
    org_unit_name: str | None = None
    position_name: str | None = None
    operational_status: str | None = None
    employment_rate: float | None = None
    iin: str | None = None


class PprSelfOperationalAssignmentResponse(BaseModel):
    status: Literal[
        "READY",
        "NO_EMPLOYEE_LINK",
        "PERSON_NOT_LINKED",
        "IDENTITY_AMBIGUOUS",
    ]
    operational_assignment: PprSelfOperationalAssignmentDataResponse | None = None


class PprSelfOrderListItem(BaseModel):
    """Minimal, employee-safe order journal row (no personnel identifiers)."""

    order_id: int
    order_number: str | None = None
    order_date: date | None = None
    title: str
    item_text: str | None = None
    confirmation_status: Literal["CONFIRMED", "UNCONFIRMED"]


class PprSelfOrderListResponse(BaseModel):
    status: Literal["READY", "NO_EMPLOYEE_LINK", "PERSON_NOT_LINKED", "IDENTITY_AMBIGUOUS"]
    orders: list[PprSelfOrderListItem] = Field(default_factory=list)


class PprSelfOrderDetailResponse(PprSelfOrderListItem):
    """A safe personal view of one order: one caller-owned item only."""

    warning: str | None = None


class _StrictSelfCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command_id: str = Field(min_length=1)
    correlation_id: str | None = None
    comment: str | None = None


class SelfContactsCommand(_StrictSelfCommand):
    expected_version: int | None = Field(default=None, ge=0)
    mobile_phone: str | None = Field(default=None, max_length=64)
    email: str | None = None
    registration_address: str | None = Field(default=None, max_length=2000)
    residence_address: str | None = Field(default=None, max_length=2000)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        value = (value or "").strip() or None
        if value is not None and ("@" not in value or value.startswith("@") or value.endswith("@")):
            raise ValueError("Invalid email")
        return value


class SelfEducationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    education_kind: str
    institution_type: str | None = None
    institution_name: str | None = None
    specialty: str | None = None
    qualification: str | None = None
    started_at: date | None = None
    completed_at: date | None = None
    diploma_number: str | None = None
    document_date: date | None = None


class SelfEducationCreateCommand(_StrictSelfCommand):
    record: SelfEducationRecord


class SelfEducationSupersedeCommand(_StrictSelfCommand):
    expected_updated_at: datetime
    replacement: SelfEducationRecord


class SelfEducationVoidCommand(_StrictSelfCommand):
    expected_updated_at: datetime
    reason: str = Field(min_length=1)


class SelfForeignLanguage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: str = Field(min_length=1, max_length=200)
    proficiency: str = Field(min_length=1, max_length=100)

    @field_validator("language", "proficiency")
    @classmethod
    def required_text(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Value is required")
        return value


class SelfForeignLanguagesCommand(_StrictSelfCommand):
    expected_updated_at: datetime | None = None
    foreign_languages: list[SelfForeignLanguage]


class SelfExternalEmploymentRecord(BaseModel):
    """Employee-owned employment biography fields; HR provenance is excluded."""
    model_config = ConfigDict(extra="forbid")
    record_kind: str = Field(min_length=1)
    employer_name: str | None = Field(default=None, max_length=2000)
    department_name: str | None = Field(default=None, max_length=2000)
    position_title: str | None = Field(default=None, max_length=2000)
    employment_type: str | None = None
    started_at: date | None = None
    ended_at: date | None = None
    termination_reason: str | None = Field(default=None, max_length=2000)
    document_reference: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=4000)


class SelfExternalEmploymentCreateCommand(_StrictSelfCommand):
    record: SelfExternalEmploymentRecord


class SelfExternalEmploymentSupersedeCommand(_StrictSelfCommand):
    """Versioned replacement of one self-owned external-employment record."""
    expected_updated_at: datetime
    replacement: SelfExternalEmploymentRecord


class SelfExternalEmploymentVoidCommand(_StrictSelfCommand):
    expected_updated_at: datetime
    reason: str = Field(min_length=1)
