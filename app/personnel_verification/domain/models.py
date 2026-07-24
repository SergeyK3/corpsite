"""Frozen snapshots for personnel verification foundation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class VerificationPolicySnapshot:
    policy_id: int
    control_point: str
    policy_version: int
    status: str
    effective_from: date
    effective_to: date | None
    decision_basis: str
    created_by_user_id: int
    published_by_user_id: int | None
    created_at: datetime
    published_at: datetime | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class VerificationTaskSnapshot:
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
    closed_at: datetime | None


@dataclass(frozen=True, slots=True)
class VerificationAttestationSnapshot:
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
    verifier_employee_id: int | None
    decided_at: datetime
    comment: str | None
    evidence_ref: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DerivedVerificationState:
    """Computed verification state — not a writable SSoT column."""

    state: str
    control_point: str
    object_type: str | None
    object_id: int | None
    object_version_id: int | None
    policy_id: int | None
    policy_version: int | None
    attestation_id: int | None
    decided_at: datetime | None
