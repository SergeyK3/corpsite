"""SQL repository for personnel verification foundation (WP-VER-002)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import Connection, text
from sqlalchemy.exc import IntegrityError

from app.db.models.personnel_verification import (
    ATTESTATION_DECISION_REJECTED,
    ATTESTATION_DECISION_VERIFIED,
    CONTROL_POINT_EMPLOYMENT_EPISODE,
    OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT,
    POLICY_STATUS_ACTIVE,
    POLICY_STATUS_DRAFT,
    POLICY_STATUS_INACTIVE,
    TASK_STATUS_CANCELLED,
    TASK_STATUS_PENDING,
)
from app.personnel_verification.domain.control_catalog import get_control_point_definition
from app.personnel_verification.domain.errors import (
    AttestationImmutableError,
    AttestationValidationError,
    ControlledRecordNotFoundError,
    PolicyNotFoundError,
    PolicyValidationError,
    TaskNotFoundError,
    TaskValidationError,
)
from app.personnel_verification.domain.invariants import (
    expected_task_status_for_decision,
    require_allowed_control_point,
    require_task_creation_supported,
    validate_attestation_decision,
    validate_attestation_matches_task,
    validate_decision_basis,
    validate_employment_episode_object_identity,
    validate_policy_active_for_tasks,
    validate_policy_dates,
    validate_publish_fields,
    validate_task_not_terminal,
)
from app.personnel_verification.domain.models import (
    VerificationAttestationSnapshot,
    VerificationPolicySnapshot,
    VerificationTaskSnapshot,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _map_policy(row: Any) -> VerificationPolicySnapshot:
    return VerificationPolicySnapshot(
        policy_id=int(row["policy_id"]),
        control_point=str(row["control_point"]),
        policy_version=int(row["policy_version"]),
        status=str(row["status"]),
        effective_from=row["effective_from"],
        effective_to=row["effective_to"],
        decision_basis=str(row["decision_basis"]),
        created_by_user_id=int(row["created_by_user_id"]),
        published_by_user_id=(
            int(row["published_by_user_id"]) if row["published_by_user_id"] is not None else None
        ),
        created_at=row["created_at"],
        published_at=row["published_at"],
        updated_at=row["updated_at"],
    )


def _map_task(row: Any) -> VerificationTaskSnapshot:
    return VerificationTaskSnapshot(
        task_id=int(row["task_id"]),
        person_id=int(row["person_id"]),
        control_point=str(row["control_point"]),
        object_type=str(row["object_type"]),
        object_id=int(row["object_id"]),
        object_version_id=int(row["object_version_id"]),
        policy_id=int(row["policy_id"]),
        policy_version=int(row["policy_version"]),
        status=str(row["status"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        closed_at=row["closed_at"],
    )


def _map_attestation(row: Any) -> VerificationAttestationSnapshot:
    return VerificationAttestationSnapshot(
        attestation_id=int(row["attestation_id"]),
        task_id=int(row["task_id"]),
        person_id=int(row["person_id"]),
        control_point=str(row["control_point"]),
        object_type=str(row["object_type"]),
        object_id=int(row["object_id"]),
        object_version_id=int(row["object_version_id"]),
        policy_id=int(row["policy_id"]),
        policy_version=int(row["policy_version"]),
        decision=str(row["decision"]),
        verifier_user_id=int(row["verifier_user_id"]),
        verifier_employee_id=(
            int(row["verifier_employee_id"]) if row["verifier_employee_id"] is not None else None
        ),
        decided_at=row["decided_at"],
        comment=row["comment"],
        evidence_ref=row["evidence_ref"],
        created_at=row["created_at"],
    )


_POLICY_SELECT = """
    policy_id, control_point, policy_version, status,
    effective_from, effective_to, decision_basis,
    created_by_user_id, published_by_user_id,
    created_at, published_at, updated_at
"""

_TASK_SELECT = """
    task_id, person_id, control_point, object_type, object_id, object_version_id,
    policy_id, policy_version, status, created_at, updated_at, closed_at
"""

_ATTESTATION_SELECT = """
    attestation_id, task_id, person_id, control_point, object_type, object_id,
    object_version_id, policy_id, policy_version, decision,
    verifier_user_id, verifier_employee_id, decided_at, comment, evidence_ref, created_at
"""


class PersonnelVerificationRepository:
    """Repository for policies, tasks and immutable attestations.

    Does not update PPR ``verification_status`` — that column is not SSoT.
    Does not call supersede when creating a pending task/revision reference.
    """

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    # ------------------------------------------------------------------ policy
    def next_policy_version(self, control_point: str) -> int:
        require_allowed_control_point(control_point)
        row = self._conn.execute(
            text(
                """
                SELECT COALESCE(MAX(policy_version), 0) + 1 AS next_version
                FROM public.verification_policies
                WHERE control_point = :control_point
                """
            ),
            {"control_point": control_point},
        ).mappings().one()
        return int(row["next_version"])

    def create_policy_draft(
        self,
        *,
        control_point: str,
        effective_from: date,
        decision_basis: str,
        created_by_user_id: int,
        effective_to: date | None = None,
        policy_version: int | None = None,
    ) -> VerificationPolicySnapshot:
        require_allowed_control_point(control_point)
        validate_policy_dates(effective_from, effective_to)
        validate_decision_basis(decision_basis)
        validate_publish_fields(
            status=POLICY_STATUS_DRAFT,
            published_by_user_id=None,
            published_at_present=False,
        )
        version = policy_version if policy_version is not None else self.next_policy_version(
            control_point
        )
        if version <= 0:
            raise PolicyValidationError("policy_version must be positive")
        nested = self._conn.begin_nested()
        try:
            row = self._conn.execute(
                text(
                    f"""
                    INSERT INTO public.verification_policies (
                        control_point, policy_version, status,
                        effective_from, effective_to, decision_basis,
                        created_by_user_id
                    )
                    VALUES (
                        :control_point, :policy_version, :status,
                        :effective_from, :effective_to, :decision_basis,
                        :created_by_user_id
                    )
                    RETURNING {_POLICY_SELECT}
                    """
                ),
                {
                    "control_point": control_point,
                    "policy_version": version,
                    "status": POLICY_STATUS_DRAFT,
                    "effective_from": effective_from,
                    "effective_to": effective_to,
                    "decision_basis": decision_basis.strip(),
                    "created_by_user_id": created_by_user_id,
                },
            ).mappings().one()
            nested.commit()
        except IntegrityError as exc:
            nested.rollback()
            raise PolicyValidationError(
                f"Unable to create draft policy for {control_point!r}: {exc.orig}"
            ) from exc
        return _map_policy(row)

    def publish_policy(
        self,
        *,
        policy_id: int,
        published_by_user_id: int,
        published_at: datetime | None = None,
    ) -> VerificationPolicySnapshot:
        policy = self.get_policy(policy_id)
        if policy.status != POLICY_STATUS_DRAFT:
            raise PolicyValidationError(
                f"Only draft policies can be published; got {policy.status!r}"
            )
        validate_decision_basis(policy.decision_basis)
        stamp = published_at or _utc_now()
        validate_publish_fields(
            status=POLICY_STATUS_ACTIVE,
            published_by_user_id=published_by_user_id,
            published_at_present=True,
        )
        # Deactivate previous active policy for the same control point.
        self._conn.execute(
            text(
                """
                UPDATE public.verification_policies
                SET status = :inactive,
                    updated_at = :updated_at
                WHERE control_point = :control_point
                  AND status = :active
                """
            ),
            {
                "inactive": POLICY_STATUS_INACTIVE,
                "updated_at": stamp,
                "control_point": policy.control_point,
                "active": POLICY_STATUS_ACTIVE,
            },
        )
        row = self._conn.execute(
            text(
                f"""
                UPDATE public.verification_policies
                SET status = :status,
                    published_by_user_id = :published_by_user_id,
                    published_at = :published_at,
                    updated_at = :updated_at
                WHERE policy_id = :policy_id
                  AND status = :draft
                RETURNING {_POLICY_SELECT}
                """
            ),
            {
                "status": POLICY_STATUS_ACTIVE,
                "published_by_user_id": published_by_user_id,
                "published_at": stamp,
                "updated_at": stamp,
                "policy_id": policy_id,
                "draft": POLICY_STATUS_DRAFT,
            },
        ).mappings().first()
        if row is None:
            raise PolicyNotFoundError(f"Draft policy {policy_id} not found for publish")
        return _map_policy(row)

    def get_policy(self, policy_id: int) -> VerificationPolicySnapshot:
        row = self._conn.execute(
            text(
                f"""
                SELECT {_POLICY_SELECT}
                FROM public.verification_policies
                WHERE policy_id = :policy_id
                """
            ),
            {"policy_id": policy_id},
        ).mappings().first()
        if row is None:
            raise PolicyNotFoundError(f"Policy {policy_id} not found")
        return _map_policy(row)

    def get_active_policy(self, control_point: str) -> VerificationPolicySnapshot | None:
        require_allowed_control_point(control_point)
        row = self._conn.execute(
            text(
                f"""
                SELECT {_POLICY_SELECT}
                FROM public.verification_policies
                WHERE control_point = :control_point
                  AND status = :status
                """
            ),
            {"control_point": control_point, "status": POLICY_STATUS_ACTIVE},
        ).mappings().first()
        return _map_policy(row) if row is not None else None

    # -------------------------------------------------------------------- tasks
    def _assert_employment_episode_target(
        self,
        *,
        person_id: int,
        object_id: int,
        object_version_id: int,
    ) -> None:
        """Validate task→PPR binding for WP-VER-002 foundation identity.

        Until WP-VER-003 introduces physical lineage:
        - ``object_version_id`` = ``person_external_employment.employment_id``
        - ``object_id`` = ``object_version_id``
        - target row must be ``lifecycle_status='active'``
        """
        validate_employment_episode_object_identity(
            object_id=object_id,
            object_version_id=object_version_id,
        )
        version = self._conn.execute(
            text(
                """
                SELECT employment_id, person_id, lifecycle_status
                FROM public.person_external_employment
                WHERE employment_id = :employment_id
                """
            ),
            {"employment_id": object_version_id},
        ).mappings().first()
        if version is None:
            raise ControlledRecordNotFoundError(
                f"person_external_employment.employment_id={object_version_id} not found"
            )
        if int(version["person_id"]) != person_id:
            raise ControlledRecordNotFoundError(
                f"employment_id={object_version_id} does not belong to person_id={person_id}"
            )
        if str(version["lifecycle_status"]) != "active":
            raise TaskValidationError(
                "employment_episode tasks require lifecycle_status='active'; "
                f"got {version['lifecycle_status']!r} for employment_id={object_version_id}"
            )

    def create_pending_task(
        self,
        *,
        person_id: int,
        control_point: str,
        object_id: int,
        object_version_id: int,
        policy_id: int,
        object_type: str | None = None,
    ) -> VerificationTaskSnapshot:
        """Create a pending task for a revision without superseding any verified row."""
        require_task_creation_supported(control_point)
        policy = self.get_policy(policy_id)
        validate_policy_active_for_tasks(policy)
        if policy.control_point != control_point:
            raise TaskValidationError(
                f"Policy control_point {policy.control_point!r} != {control_point!r}"
            )

        definition = get_control_point_definition(control_point)
        resolved_object_type = object_type or definition.object_type
        if not resolved_object_type:
            raise TaskValidationError(
                f"object_type is required for control point {control_point!r}"
            )
        if (
            control_point == CONTROL_POINT_EMPLOYMENT_EPISODE
            and resolved_object_type != OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT
        ):
            raise TaskValidationError(
                "employment_episode tasks must use object_type="
                f"{OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT!r}"
            )
        if control_point == CONTROL_POINT_EMPLOYMENT_EPISODE:
            self._assert_employment_episode_target(
                person_id=person_id,
                object_id=object_id,
                object_version_id=object_version_id,
            )

        nested = self._conn.begin_nested()
        try:
            row = self._conn.execute(
                text(
                    f"""
                    INSERT INTO public.verification_tasks (
                        person_id, control_point, object_type, object_id, object_version_id,
                        policy_id, policy_version, status
                    )
                    VALUES (
                        :person_id, :control_point, :object_type, :object_id, :object_version_id,
                        :policy_id, :policy_version, :status
                    )
                    RETURNING {_TASK_SELECT}
                    """
                ),
                {
                    "person_id": person_id,
                    "control_point": control_point,
                    "object_type": resolved_object_type,
                    "object_id": object_id,
                    "object_version_id": object_version_id,
                    "policy_id": policy_id,
                    "policy_version": policy.policy_version,
                    "status": TASK_STATUS_PENDING,
                },
            ).mappings().one()
            nested.commit()
        except IntegrityError as exc:
            nested.rollback()
            raise TaskValidationError(
                "Unable to create pending task "
                "(unique pending task per object_type+object_version_id+policy "
                f"may already exist): {exc.orig}"
            ) from exc
        return _map_task(row)

    def get_task(self, task_id: int) -> VerificationTaskSnapshot:
        row = self._conn.execute(
            text(
                f"""
                SELECT {_TASK_SELECT}
                FROM public.verification_tasks
                WHERE task_id = :task_id
                """
            ),
            {"task_id": task_id},
        ).mappings().first()
        if row is None:
            raise TaskNotFoundError(f"Task {task_id} not found")
        return _map_task(row)

    def get_pending_task_for_version(
        self,
        *,
        object_type: str,
        object_version_id: int,
        policy_id: int,
    ) -> VerificationTaskSnapshot | None:
        row = self._conn.execute(
            text(
                f"""
                SELECT {_TASK_SELECT}
                FROM public.verification_tasks
                WHERE object_type = :object_type
                  AND object_version_id = :object_version_id
                  AND policy_id = :policy_id
                  AND status = :status
                """
            ),
            {
                "object_type": object_type,
                "object_version_id": object_version_id,
                "policy_id": policy_id,
                "status": TASK_STATUS_PENDING,
            },
        ).mappings().first()
        return _map_task(row) if row is not None else None

    def cancel_task(self, task_id: int, *, closed_at: datetime | None = None) -> VerificationTaskSnapshot:
        task = self.get_task(task_id)
        validate_task_not_terminal(task.status)
        stamp = closed_at or _utc_now()
        row = self._conn.execute(
            text(
                f"""
                UPDATE public.verification_tasks
                SET status = :status,
                    closed_at = :closed_at,
                    updated_at = :updated_at
                WHERE task_id = :task_id
                  AND status = :pending
                RETURNING {_TASK_SELECT}
                """
            ),
            {
                "status": TASK_STATUS_CANCELLED,
                "closed_at": stamp,
                "updated_at": stamp,
                "task_id": task_id,
                "pending": TASK_STATUS_PENDING,
            },
        ).mappings().first()
        if row is None:
            raise TaskValidationError(f"Task {task_id} is not pending and cannot be cancelled")
        return _map_task(row)

    # ------------------------------------------------------------- attestations
    def create_attestation(
        self,
        *,
        task_id: int,
        decision: str,
        verifier_user_id: int,
        verifier_employee_id: int | None = None,
        decided_at: datetime | None = None,
        comment: str | None = None,
        evidence_ref: str | None = None,
    ) -> VerificationAttestationSnapshot:
        """Append-only attestation; closes the task. No update/delete API exists."""
        validate_attestation_decision(decision)
        task = self.get_task(task_id)
        policy = self.get_policy(task.policy_id)
        stamp = decided_at or _utc_now()
        validate_attestation_matches_task(
            task=task,
            policy=policy,
            person_id=task.person_id,
            control_point=task.control_point,
            object_type=task.object_type,
            object_id=task.object_id,
            object_version_id=task.object_version_id,
            policy_id=task.policy_id,
            policy_version=task.policy_version,
        )
        next_status = expected_task_status_for_decision(decision)
        nested = self._conn.begin_nested()
        try:
            row = self._conn.execute(
                text(
                    f"""
                    INSERT INTO public.verification_attestations (
                        task_id, person_id, control_point, object_type, object_id,
                        object_version_id, policy_id, policy_version, decision,
                        verifier_user_id, verifier_employee_id, decided_at,
                        comment, evidence_ref
                    )
                    VALUES (
                        :task_id, :person_id, :control_point, :object_type, :object_id,
                        :object_version_id, :policy_id, :policy_version, :decision,
                        :verifier_user_id, :verifier_employee_id, :decided_at,
                        :comment, :evidence_ref
                    )
                    RETURNING {_ATTESTATION_SELECT}
                    """
                ),
                {
                    "task_id": task.task_id,
                    "person_id": task.person_id,
                    "control_point": task.control_point,
                    "object_type": task.object_type,
                    "object_id": task.object_id,
                    "object_version_id": task.object_version_id,
                    "policy_id": task.policy_id,
                    "policy_version": task.policy_version,
                    "decision": decision,
                    "verifier_user_id": verifier_user_id,
                    "verifier_employee_id": verifier_employee_id,
                    "decided_at": stamp,
                    "comment": comment,
                    "evidence_ref": evidence_ref,
                },
            ).mappings().one()
            nested.commit()
        except IntegrityError as exc:
            nested.rollback()
            raise AttestationValidationError(
                f"Unable to create attestation for task {task_id}: {exc.orig}"
            ) from exc

        closed = self._conn.execute(
            text(
                f"""
                UPDATE public.verification_tasks
                SET status = :status,
                    closed_at = :closed_at,
                    updated_at = :updated_at
                WHERE task_id = :task_id
                  AND status = :pending
                RETURNING {_TASK_SELECT}
                """
            ),
            {
                "status": next_status,
                "closed_at": stamp,
                "updated_at": stamp,
                "task_id": task_id,
                "pending": TASK_STATUS_PENDING,
            },
        ).mappings().first()
        if closed is None:
            raise TaskValidationError(
                f"Task {task_id} could not be closed after attestation"
            )
        return _map_attestation(row)

    def get_attestation(self, attestation_id: int) -> VerificationAttestationSnapshot:
        row = self._conn.execute(
            text(
                f"""
                SELECT {_ATTESTATION_SELECT}
                FROM public.verification_attestations
                WHERE attestation_id = :attestation_id
                """
            ),
            {"attestation_id": attestation_id},
        ).mappings().first()
        if row is None:
            raise AttestationValidationError(f"Attestation {attestation_id} not found")
        return _map_attestation(row)

    def get_attestation_for_task(self, task_id: int) -> VerificationAttestationSnapshot | None:
        row = self._conn.execute(
            text(
                f"""
                SELECT {_ATTESTATION_SELECT}
                FROM public.verification_attestations
                WHERE task_id = :task_id
                """
            ),
            {"task_id": task_id},
        ).mappings().first()
        return _map_attestation(row) if row is not None else None

    def get_latest_attestation_for_version(
        self,
        *,
        object_type: str,
        object_version_id: int,
    ) -> VerificationAttestationSnapshot | None:
        row = self._conn.execute(
            text(
                f"""
                SELECT {_ATTESTATION_SELECT}
                FROM public.verification_attestations
                WHERE object_type = :object_type
                  AND object_version_id = :object_version_id
                ORDER BY decided_at DESC, attestation_id DESC
                LIMIT 1
                """
            ),
            {
                "object_type": object_type,
                "object_version_id": object_version_id,
            },
        ).mappings().first()
        return _map_attestation(row) if row is not None else None

    def update_attestation(self, *_args: Any, **_kwargs: Any) -> None:
        raise AttestationImmutableError(
            "verification_attestations cannot be updated via repository API"
        )

    def delete_attestation(self, *_args: Any, **_kwargs: Any) -> None:
        raise AttestationImmutableError(
            "verification_attestations cannot be deleted via repository API"
        )


# Keep decision constants importable for callers/tests.
__all__ = [
    "PersonnelVerificationRepository",
    "ATTESTATION_DECISION_VERIFIED",
    "ATTESTATION_DECISION_REJECTED",
]
