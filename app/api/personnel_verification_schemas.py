"""HTTP DTOs for personnel verification employment API (WP-VER-005A)."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class EmploymentVerificationDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_prior_updated_at: datetime
    comment: str | None = None
    evidence_ref: str | None = None


class VerificationTaskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: int
    person_id: int
    control_point: str
    object_type: str
    object_id: int
    object_version_id: int
    policy_id: int
    policy_version: int
    status: str
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    prior_updated_at: datetime | None = None


class EmploymentPendingTaskListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[VerificationTaskResponse]
    count: int = Field(ge=0)


class DerivedVerificationStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str
    control_point: str
    object_type: str | None = None
    object_id: int | None = None
    object_version_id: int | None = None
    policy_id: int | None = None
    policy_version: int | None = None
    attestation_id: int | None = None
    decided_at: datetime | None = None


class VerificationAttestationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attestation_id: int
    task_id: int
    person_id: int
    control_point: str
    object_type: str
    object_id: int
    object_version_id: int
    policy_id: int
    policy_version: int
    decision: str
    verifier_user_id: int
    verifier_employee_id: int | None = None
    decided_at: datetime
    comment: str | None = None
    evidence_ref: str | None = None
    created_at: datetime


class EmploymentRevisionDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: VerificationTaskResponse
    attestation: VerificationAttestationResponse
    prior_employment_id: int
    revision_employment_id: int
    prior_lifecycle_status: str
    revision_lifecycle_status: str


class EmploymentRecordSnapshotResponse(BaseModel):
    """Human-facing employment fields for HR comparison (WP-VER-005B)."""

    model_config = ConfigDict(extra="forbid")

    employment_id: int
    record_kind: str
    employer_name: str | None = None
    department_name: str | None = None
    position_title: str | None = None
    employment_type: str | None = None
    started_at: date | None = None
    ended_at: date | None = None
    termination_reason: str | None = None
    document_reference: str | None = None
    notes: str | None = None
    lifecycle_status: str
    updated_at: datetime | None = None


class EmploymentTaskReviewResponse(BaseModel):
    """Task + prior/revision snapshots for HR queue detail (WP-VER-005B)."""

    model_config = ConfigDict(extra="forbid")

    task: VerificationTaskResponse
    person_id: int
    person_full_name: str
    prior: EmploymentRecordSnapshotResponse
    revision: EmploymentRecordSnapshotResponse
    verification_state: str
