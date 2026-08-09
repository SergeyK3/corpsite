"""Pydantic schemas for person-centric LK registry and repair preflight APIs."""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.personnel_lk.application.registry_query_service import PersonnelLkRegistryRow


_CONFIRMATION_AT_RE = re.compile(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$')
_CONFIRMATION_REFERENCE_RE = r'^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$'
_CANONICAL_DECIMAL_RE = re.compile(r'^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$')


def _normalize_confirmed_name(value: str) -> str:
    normalized = unicodedata.normalize('NFC', value)
    normalized = ' '.join(normalized.split())
    return unicodedata.normalize('NFC', normalized.casefold())


class ControlListRepairImportSelectionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: int = Field(ge=1)
    row_id: int = Field(ge=1)
    normalized_record_ids: list[int] = Field(min_length=1)

    @field_validator("normalized_record_ids")
    @classmethod
    def validate_normalized_record_ids(cls, value: list[int]) -> list[int]:
        if any(item < 1 for item in value):
            raise ValueError("normalized_record_ids must contain positive integers")
        if len(set(value)) != len(value):
            raise ValueError("normalized_record_ids must not contain duplicates")
        return value


class ControlListRepairOrgUnitConfirmationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    org_unit_id: int | None = Field(default=None, ge=1)
    org_unit_normalized_stable_code: str | None = Field(
        default=None, min_length=1, max_length=128
    )
    operator_confirmed_normalized_org_name: str | None = Field(
        default=None, min_length=1, max_length=512
    )

    @field_validator('org_unit_normalized_stable_code')
    @classmethod
    def validate_stable_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.isascii() or value != value.strip():
            raise ValueError('org unit stable code must be exact trimmed ASCII')
        return value

    @field_validator('operator_confirmed_normalized_org_name')
    @classmethod
    def validate_normalized_org_name(cls, value: str | None) -> str | None:
        if value is not None and value != _normalize_confirmed_name(value):
            raise ValueError('org unit name must use the normative normalized form')
        return value


class ControlListRepairPositionConfirmationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position_id: int | None = Field(default=None, ge=1)
    operator_confirmed_normalized_position_name: str | None = Field(
        default=None, min_length=1, max_length=512
    )

    @field_validator('operator_confirmed_normalized_position_name')
    @classmethod
    def validate_normalized_position_name(cls, value: str | None) -> str | None:
        if value is not None and value != _normalize_confirmed_name(value):
            raise ValueError('position name must use the normative normalized form')
        return value


class ControlListRepairPersonnelOrderEvidenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_type: Literal["PERSONNEL_ORDER"]
    personnel_order_id: int | None = Field(default=None, ge=1)
    evidence_record_id: int | None = Field(default=None, ge=1)
    evidence_profile_id: str | None = Field(
        default=None, pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$"
    )
    evidence_profile_version: int | None = Field(default=None, ge=1)
    evidence_key_id: str | None = Field(
        default=None, pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$"
    )
    evidence_fingerprint: str | None = Field(default=None, pattern="^[0-9a-f]{64}$")
    admissibility_confirmed: bool | None = None


class ControlListRepairExternalReferenceEvidenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_type: Literal["EXTERNAL_REFERENCE"]
    personnel_order_id: None = None
    evidence_record_id: None = None
    evidence_profile_id: None = None
    evidence_profile_version: None = None
    evidence_key_id: None = None
    evidence_fingerprint: str | None = Field(default=None, pattern="^[0-9a-f]{64}$")
    admissibility_confirmed: bool | None = None


ControlListRepairEvidenceIn = Annotated[
    ControlListRepairPersonnelOrderEvidenceIn
    | ControlListRepairExternalReferenceEvidenceIn,
    Field(discriminator="evidence_type"),
]


class ControlListRepairVerifierConfirmationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verifier_user_id: int | None = Field(default=None, ge=1)
    confirmation_at: str | None = None
    confirmation_reference: str | None = Field(
        default=None,
        pattern=_CONFIRMATION_REFERENCE_RE,
    )

    @field_validator('confirmation_at')
    @classmethod
    def validate_confirmation_at(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if _CONFIRMATION_AT_RE.fullmatch(value) is None:
            raise ValueError('confirmation_at must be UTC seconds with a literal Z')
        try:
            datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')
        except ValueError as exc:
            raise ValueError('confirmation_at must be a valid UTC timestamp') from exc
        return value


class ControlListRepairAssignmentIntentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    org_unit: ControlListRepairOrgUnitConfirmationIn | None = None
    position: ControlListRepairPositionConfirmationIn | None = None
    rate: str | None = None
    employment_type: Literal[
        "primary", "part_time", "internal_combo", "external", "locum"
    ] | None = None
    is_primary: bool | None = None
    start_date: date | None = None
    evidence: ControlListRepairEvidenceIn | None = None
    reason_code: Literal[
        "ACTIVE_ENROLLMENT_CONFIRMED",
        "CONSISTENT_STATE_VERIFIED",
        "EXISTING_CARD_PERSON_LINK_GAP_CONFIRMED",
        "EXISTING_CARD_PERSON_AND_ASSIGNMENT_GAP_CONFIRMED",
        "MISSING_PRIMARY_ASSIGNMENT_CONFIRMED",
        "ERRONEOUS_ASSIGNMENT_RECORD_CONFIRMED",
        "REAL_LIFECYCLE_EPISODE_COMPLETION_CONFIRMED",
        "CURRENT_ASSIGNMENT_CHANGE_CONFIRMED",
        "FUTURE_ASSIGNMENT_PRESERVATION_CONFIRMED",
        "FUTURE_ASSIGNMENT_CHANGE_CONFIRMED",
    ] | None = None
    verifier_confirmation: ControlListRepairVerifierConfirmationIn | None = None

    @field_validator('rate', mode='before')
    @classmethod
    def validate_rate(cls, value):
        if value is None:
            return None
        if not isinstance(value, str) or _CANONICAL_DECIMAL_RE.fullmatch(value) is None:
            raise ValueError('rate must be a canonical non-exponent decimal string')
        if '.' in value:
            fraction = value.partition('.')[2]
            if len(fraction) > 2 or value.endswith('0'):
                raise ValueError('rate must have scale at most 2 without trailing zero')
        decimal_value = Decimal(value)
        if decimal_value <= 0 or decimal_value > Decimal('1.5'):
            raise ValueError('rate must be greater than 0 and at most 1.5')
        if len(decimal_value.as_tuple().digits) > 4:
            raise ValueError('rate must fit NUMERIC(4,2)')
        return value


class ControlListRepairPreflightIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    iin: str
    import_selection: ControlListRepairImportSelectionIn | None = None
    assignment_intent: ControlListRepairAssignmentIntentIn | None = None

    @field_validator("iin")
    @classmethod
    def validate_iin(cls, value: str) -> str:
        if len(value) != 12 or any(char < "0" or char > "9" for char in value):
            raise ValueError("iin must be exactly 12 ASCII digits")
        return value


class SafeIinOut(BaseModel):
    present: bool
    last4: str | None = None


class ControlListRepairEmployeeOut(BaseModel):
    employee_id: int
    person_id: int | None
    operational_status: str | None
    iin: SafeIinOut


class ControlListRepairPersonOut(BaseModel):
    person_id: int
    person_status: str
    compatible: bool
    incompatibility_reason: str | None
    iin: SafeIinOut


class ControlListRepairAssignmentOut(BaseModel):
    assignment_id: int
    person_id: int
    lifecycle_status: str
    active_flag: bool
    is_primary: bool


class ControlListRepairImportRecordOut(BaseModel):
    batch_id: int
    row_id: int
    normalized_record_ids: list[int]


class ControlListRepairBlockerOut(BaseModel):
    code: str
    detail: str


class ControlListRepairPreflightOut(BaseModel):
    request_iin: SafeIinOut
    import_records: list[ControlListRepairImportRecordOut]
    selected_import: ControlListRepairImportRecordOut | None
    employees: list[ControlListRepairEmployeeOut]
    person_candidates: list[ControlListRepairPersonOut]
    primary_assignments: list[ControlListRepairAssignmentOut]
    classification: Literal["P0_CREATE", "P1_ADOPT"] | None
    mode: Literal["LINK_AND_OPEN_MISSING_ASSIGNMENT"] | None
    proposed_outcome: Literal["EMPLOYEE_PERSON_AND_ASSIGNMENT_REPAIRED"] | None
    blockers: list[ControlListRepairBlockerOut]
    missing_assignment_inputs: list[str]
    invalid_assignment_inputs: list[str]
    preflight_complete: bool
    apply_available: Literal[False] = False
    observed_at: datetime


class PersonnelLkRegistryItemOut(BaseModel):
    person_id: int
    record_kind: Literal["employee", "applicant"]
    id: int | None = Field(
        default=None,
        description="Employee id when record_kind=employee; null for applicants.",
    )
    employee_id: int | None = None
    active_application_id: int | None = None
    fio: str | None = None
    iin: str | None = None
    rate: Decimal | float | None = None
    status: str
    application_status: str | None = None


class PersonnelLkRegistryListOut(BaseModel):
    items: list[PersonnelLkRegistryItemOut]
    total: int
    limit: int
    offset: int


def registry_row_to_out(row: PersonnelLkRegistryRow) -> PersonnelLkRegistryItemOut:
    return PersonnelLkRegistryItemOut(
        person_id=row.person_id,
        record_kind=row.record_kind,  # type: ignore[arg-type]
        id=row.employee_id,
        employee_id=row.employee_id,
        active_application_id=row.active_application_id,
        fio=row.fio,
        iin=row.iin,
        rate=row.rate,
        status=row.status,
        application_status=row.application_status,
    )
