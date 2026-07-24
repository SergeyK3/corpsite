"""Derived verification state resolution (not a writable SSoT)."""
from __future__ import annotations

from app.personnel_verification.domain.invariants import resolve_derived_verification_state
from app.personnel_verification.domain.models import DerivedVerificationState
from app.personnel_verification.infrastructure.repository import PersonnelVerificationRepository


class VerificationStateService:
    """Reads policy/task/attestation and returns derived state only."""

    def __init__(self, repo: PersonnelVerificationRepository) -> None:
        self._repo = repo

    def resolve_for_version(
        self,
        *,
        control_point: str,
        object_type: str,
        object_version_id: int,
        policy_id: int | None = None,
    ) -> DerivedVerificationState:
        active_policy = self._repo.get_active_policy(control_point)
        policy_for_pending = (
            self._repo.get_policy(policy_id) if policy_id is not None else active_policy
        )
        pending_task = None
        if policy_for_pending is not None:
            pending_task = self._repo.get_pending_task_for_version(
                object_type=object_type,
                object_version_id=object_version_id,
                policy_id=policy_for_pending.policy_id,
            )
        latest_attestation = self._repo.get_latest_attestation_for_version(
            object_type=object_type,
            object_version_id=object_version_id,
        )
        return resolve_derived_verification_state(
            control_point=control_point,
            active_policy=active_policy,
            pending_task=pending_task,
            latest_attestation=latest_attestation,
        )
