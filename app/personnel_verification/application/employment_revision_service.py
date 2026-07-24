"""WP-VER-003 employment_episode pending revision create / confirm / reject."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import Connection, text
from sqlalchemy.exc import IntegrityError

from app.db.models.personnel_migration import (
    EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
    EXTERNAL_EMPLOYMENT_SOURCE_MANUAL,
    LIFECYCLE_STATUS_ACTIVE,
    LIFECYCLE_STATUS_SUPERSEDED,
    LIFECYCLE_STATUS_VOIDED,
    VERIFICATION_STATUS_PENDING,
)
from app.db.models.personnel_verification import (
    ATTESTATION_DECISION_REJECTED,
    ATTESTATION_DECISION_VERIFIED,
    CONTROL_POINT_EMPLOYMENT_EPISODE,
    OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_PENDING,
    TASK_STATUS_REJECTED,
)
from app.personnel_verification.domain.errors import (
    ControlledRecordNotFoundError,
    RevisionConflictError,
    TaskNotFoundError,
    TaskValidationError,
)
from app.personnel_verification.domain.invariants import expected_task_status_for_decision
from app.personnel_verification.domain.models import (
    VerificationAttestationSnapshot,
    VerificationTaskSnapshot,
)
from app.personnel_verification.infrastructure.repository import (
    PersonnelVerificationRepository,
    _ATTESTATION_SELECT,
    _TASK_SELECT,
    _map_attestation,
    _map_task,
)
from app.ppr.domain.section_models import ExternalEmploymentRecord
from app.ppr.infrastructure.section_repository import SqlAlchemySectionMutationRepository


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class PendingRevisionResult:
    prior_employment_id: int
    revision_employment_id: int
    task: VerificationTaskSnapshot


@dataclass(frozen=True, slots=True)
class RevisionDecisionResult:
    task: VerificationTaskSnapshot
    attestation: VerificationAttestationSnapshot
    prior_employment_id: int
    revision_employment_id: int
    prior_lifecycle_status: str
    revision_lifecycle_status: str


class EmploymentRevisionService:
    """Employment-specific dual-version create/confirm/reject (WP-VER-003).

    Confirm/reject run as a single outer DB transaction on the provided connection.
    Callers must begin/commit/rollback the connection transaction.
    """

    def __init__(self, conn: Connection) -> None:
        self._conn = conn
        self._repo = PersonnelVerificationRepository(conn)
        self._mutations = SqlAlchemySectionMutationRepository(conn)

    def create_pending_revision(
        self,
        *,
        person_id: int,
        prior_employment_id: int,
        policy_id: int,
        employer_name: str | None = None,
        department_name: str | None = None,
        position_title: str | None = None,
        employment_type: str | None = None,
        started_at: date | None = None,
        ended_at: date | None = None,
        termination_reason: str | None = None,
        document_reference: str | None = None,
        notes: str | None = None,
        source_system: str = EXTERNAL_EMPLOYMENT_SOURCE_MANUAL,
        source_id: str | None = None,
        provenance: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        employee_context_id: int | None = None,
        copy_material_fields_from_prior: bool = True,
    ) -> PendingRevisionResult:
        """Insert active pending revision without superseding prior; create pending task."""
        prior = self._load_employment(prior_employment_id)
        if prior is None or int(prior["person_id"]) != person_id:
            raise ControlledRecordNotFoundError(
                f"prior employment_id={prior_employment_id} not found for person_id={person_id}"
            )
        if str(prior["lifecycle_status"]) != LIFECYCLE_STATUS_ACTIVE:
            raise TaskValidationError(
                f"prior employment_id={prior_employment_id} must be active "
                f"(got {prior['lifecycle_status']!r})"
            )
        if not self._is_effective_active_employment(prior):
            raise TaskValidationError(
                f"prior employment_id={prior_employment_id} is not the effective active record"
            )
        if self._has_active_unconfirmed_revision(prior_employment_id):
            raise RevisionConflictError(
                f"active unconfirmed revision already exists for prior employment_id="
                f"{prior_employment_id}"
            )

        if copy_material_fields_from_prior:
            employer_name = employer_name if employer_name is not None else prior["employer_name"]
            department_name = (
                department_name if department_name is not None else prior["department_name"]
            )
            position_title = (
                position_title if position_title is not None else prior["position_title"]
            )
            employment_type = (
                employment_type if employment_type is not None else prior["employment_type"]
            )
            started_at = started_at if started_at is not None else prior["started_at"]
            ended_at = ended_at if ended_at is not None else prior["ended_at"]
            termination_reason = (
                termination_reason
                if termination_reason is not None
                else prior["termination_reason"]
            )
            document_reference = (
                document_reference
                if document_reference is not None
                else prior["document_reference"]
            )
            notes = notes if notes is not None else prior["notes"]

        revision = self._mutations.insert_record(
            ExternalEmploymentRecord(
                person_id=person_id,
                record_kind=str(prior["record_kind"] or EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE),
                employer_name=employer_name,
                department_name=department_name,
                position_title=position_title,
                employment_type=employment_type,
                started_at=started_at,
                ended_at=ended_at,
                termination_reason=termination_reason,
                document_reference=document_reference,
                source_system=source_system,
                source_id=source_id,
                provenance=provenance or {},
                verification_status=VERIFICATION_STATUS_PENDING,
                lifecycle_status=LIFECYCLE_STATUS_ACTIVE,
                supersedes_employment_id=prior_employment_id,
                notes=notes,
                employee_context_id=employee_context_id,
                metadata=metadata or {},
            )
        )
        assert revision.record_id is not None

        # Prior must remain active (do not call supersede_pair).
        still_active = self._load_employment(prior_employment_id)
        if still_active is None or str(still_active["lifecycle_status"]) != LIFECYCLE_STATUS_ACTIVE:
            raise RevisionConflictError(
                f"prior employment_id={prior_employment_id} left active state unexpectedly"
            )

        task = self._repo.create_pending_task(
            person_id=person_id,
            control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
            object_id=prior_employment_id,
            object_version_id=int(revision.record_id),
            policy_id=policy_id,
            object_type=OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT,
        )
        return PendingRevisionResult(
            prior_employment_id=prior_employment_id,
            revision_employment_id=int(revision.record_id),
            task=task,
        )

    def confirm_pending_revision(
        self,
        *,
        task_id: int,
        verifier_user_id: int,
        expected_prior_updated_at: datetime,
        verifier_employee_id: int | None = None,
        decided_at: datetime | None = None,
        comment: str | None = None,
        evidence_ref: str | None = None,
    ) -> RevisionDecisionResult:
        """Atomically attest verified, supersede prior, complete task."""
        return self._decide_pending_revision(
            task_id=task_id,
            decision=ATTESTATION_DECISION_VERIFIED,
            verifier_user_id=verifier_user_id,
            expected_prior_updated_at=expected_prior_updated_at,
            verifier_employee_id=verifier_employee_id,
            decided_at=decided_at,
            comment=comment,
            evidence_ref=evidence_ref,
        )

    def reject_pending_revision(
        self,
        *,
        task_id: int,
        verifier_user_id: int,
        expected_prior_updated_at: datetime,
        verifier_employee_id: int | None = None,
        decided_at: datetime | None = None,
        comment: str | None = None,
        evidence_ref: str | None = None,
    ) -> RevisionDecisionResult:
        """Atomically attest rejected, void pending revision, leave prior active."""
        return self._decide_pending_revision(
            task_id=task_id,
            decision=ATTESTATION_DECISION_REJECTED,
            verifier_user_id=verifier_user_id,
            expected_prior_updated_at=expected_prior_updated_at,
            verifier_employee_id=verifier_employee_id,
            decided_at=decided_at,
            comment=comment,
            evidence_ref=evidence_ref,
        )

    def _decide_pending_revision(
        self,
        *,
        task_id: int,
        decision: str,
        verifier_user_id: int,
        expected_prior_updated_at: datetime,
        verifier_employee_id: int | None,
        decided_at: datetime | None,
        comment: str | None,
        evidence_ref: str | None,
    ) -> RevisionDecisionResult:
        stamp = decided_at or _utc_now()
        task_row = self._conn.execute(
            text(
                f"""
                SELECT {_TASK_SELECT}
                FROM public.verification_tasks
                WHERE task_id = :task_id
                FOR UPDATE
                """
            ),
            {"task_id": task_id},
        ).mappings().first()
        if task_row is None:
            raise TaskNotFoundError(f"Task {task_id} not found")
        task = _map_task(task_row)
        if task.status != TASK_STATUS_PENDING:
            raise RevisionConflictError(
                f"Task {task_id} is not pending (status={task.status!r})"
            )
        if task.control_point != CONTROL_POINT_EMPLOYMENT_EPISODE:
            raise TaskValidationError(
                f"Task {task_id} control_point must be employment_episode"
            )

        revision = self._load_employment(task.object_version_id)
        if revision is None:
            raise ControlledRecordNotFoundError(
                f"revision employment_id={task.object_version_id} not found"
            )
        prior_id = revision["supersedes_employment_id"]
        if prior_id is None:
            raise TaskValidationError(
                f"employment_id={task.object_version_id} is not a pending revision"
            )
        prior_id = int(prior_id)
        if prior_id != task.object_id:
            raise TaskValidationError(
                f"task.object_id={task.object_id} != revision.supersedes_employment_id={prior_id}"
            )
        if int(revision["person_id"]) != task.person_id:
            raise TaskValidationError("revision person_id does not match task")
        if str(revision["lifecycle_status"]) != LIFECYCLE_STATUS_ACTIVE:
            raise RevisionConflictError(
                f"revision employment_id={task.object_version_id} is not active"
            )

        prior = self._load_employment_for_update(prior_id)
        if prior is None or int(prior["person_id"]) != task.person_id:
            raise ControlledRecordNotFoundError(
                f"prior employment_id={prior_id} not found for task person"
            )
        if str(prior["lifecycle_status"]) != LIFECYCLE_STATUS_ACTIVE:
            raise RevisionConflictError(
                f"prior employment_id={prior_id} is not active "
                f"(got {prior['lifecycle_status']!r})"
            )
        if prior["updated_at"] != expected_prior_updated_at:
            raise RevisionConflictError(
                f"CAS conflict on prior employment_id={prior_id}: stale updated_at"
            )

        policy = self._repo.get_policy(task.policy_id)
        next_status = expected_task_status_for_decision(decision)
        # Keep WP-VER-002 task status mapping (verified→completed, rejected→rejected).
        if decision == ATTESTATION_DECISION_VERIFIED and next_status != TASK_STATUS_COMPLETED:
            raise TaskValidationError("verified decision must complete the task")
        if decision == ATTESTATION_DECISION_REJECTED and next_status != TASK_STATUS_REJECTED:
            raise TaskValidationError("rejected decision must reject the task")

        try:
            attestation_row = self._conn.execute(
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
                    "policy_version": policy.policy_version,
                    "decision": decision,
                    "verifier_user_id": verifier_user_id,
                    "verifier_employee_id": verifier_employee_id,
                    "decided_at": stamp,
                    "comment": comment,
                    "evidence_ref": evidence_ref,
                },
            ).mappings().one()
        except IntegrityError as exc:
            raise RevisionConflictError(
                f"Unable to create attestation for task {task_id}: {exc.orig}"
            ) from exc

        if decision == ATTESTATION_DECISION_VERIFIED:
            prior_result = self._conn.execute(
                text(
                    """
                    UPDATE public.person_external_employment
                    SET lifecycle_status = :superseded,
                        updated_at = :stamp
                    WHERE employment_id = :employment_id
                      AND person_id = :person_id
                      AND lifecycle_status = :active
                      AND updated_at = :expected_updated_at
                    """
                ),
                {
                    "superseded": LIFECYCLE_STATUS_SUPERSEDED,
                    "stamp": stamp,
                    "employment_id": prior_id,
                    "person_id": task.person_id,
                    "active": LIFECYCLE_STATUS_ACTIVE,
                    "expected_updated_at": expected_prior_updated_at,
                },
            )
            if prior_result.rowcount != 1:
                raise RevisionConflictError(
                    f"CAS conflict superseding prior employment_id={prior_id}"
                )
            revision_lifecycle = LIFECYCLE_STATUS_ACTIVE
            prior_lifecycle = LIFECYCLE_STATUS_SUPERSEDED
        else:
            void_result = self._conn.execute(
                text(
                    """
                    UPDATE public.person_external_employment
                    SET lifecycle_status = :voided,
                        updated_at = :stamp
                    WHERE employment_id = :employment_id
                      AND person_id = :person_id
                      AND lifecycle_status = :active
                    """
                ),
                {
                    "voided": LIFECYCLE_STATUS_VOIDED,
                    "stamp": stamp,
                    "employment_id": task.object_version_id,
                    "person_id": task.person_id,
                    "active": LIFECYCLE_STATUS_ACTIVE,
                },
            )
            if void_result.rowcount != 1:
                raise RevisionConflictError(
                    f"Unable to void revision employment_id={task.object_version_id}"
                )
            # Re-check prior still active under CAS token (detect concurrent supersede).
            prior_check = self._conn.execute(
                text(
                    """
                    SELECT employment_id
                    FROM public.person_external_employment
                    WHERE employment_id = :employment_id
                      AND lifecycle_status = :active
                      AND updated_at = :expected_updated_at
                    """
                ),
                {
                    "employment_id": prior_id,
                    "active": LIFECYCLE_STATUS_ACTIVE,
                    "expected_updated_at": expected_prior_updated_at,
                },
            ).first()
            if prior_check is None:
                raise RevisionConflictError(
                    f"CAS conflict on prior employment_id={prior_id} during reject"
                )
            revision_lifecycle = LIFECYCLE_STATUS_VOIDED
            prior_lifecycle = LIFECYCLE_STATUS_ACTIVE

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
            raise RevisionConflictError(f"Task {task_id} could not be closed after decision")

        # Do not write person_external_employment.verification_status (not SSoT).
        return RevisionDecisionResult(
            task=_map_task(closed),
            attestation=_map_attestation(attestation_row),
            prior_employment_id=prior_id,
            revision_employment_id=task.object_version_id,
            prior_lifecycle_status=prior_lifecycle,
            revision_lifecycle_status=revision_lifecycle,
        )

    def _load_employment(self, employment_id: int):
        return self._conn.execute(
            text(
                """
                SELECT employment_id, person_id, record_kind, employer_name, department_name,
                       position_title, employment_type, started_at, ended_at,
                       termination_reason, document_reference, notes,
                       lifecycle_status, supersedes_employment_id, updated_at,
                       verification_status
                FROM public.person_external_employment
                WHERE employment_id = :employment_id
                """
            ),
            {"employment_id": employment_id},
        ).mappings().first()

    def _load_employment_for_update(self, employment_id: int):
        return self._conn.execute(
            text(
                """
                SELECT employment_id, person_id, lifecycle_status, supersedes_employment_id,
                       updated_at
                FROM public.person_external_employment
                WHERE employment_id = :employment_id
                FOR UPDATE
                """
            ),
            {"employment_id": employment_id},
        ).mappings().first()

    def _is_effective_active_employment(self, row) -> bool:
        if str(row["lifecycle_status"]) != LIFECYCLE_STATUS_ACTIVE:
            return False
        supersedes = row["supersedes_employment_id"]
        if supersedes is None:
            return True
        attested = self._conn.execute(
            text(
                """
                SELECT 1
                FROM public.verification_tasks vt
                JOIN public.verification_attestations va ON va.task_id = vt.task_id
                WHERE vt.object_type = :object_type
                  AND vt.object_version_id = :employment_id
                  AND va.decision = :verified
                LIMIT 1
                """
            ),
            {
                "object_type": OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT,
                "employment_id": int(row["employment_id"]),
                "verified": ATTESTATION_DECISION_VERIFIED,
            },
        ).first()
        return attested is not None

    def _has_active_unconfirmed_revision(self, prior_employment_id: int) -> bool:
        row = self._conn.execute(
            text(
                """
                SELECT pee.employment_id
                FROM public.person_external_employment pee
                WHERE pee.supersedes_employment_id = :prior_id
                  AND pee.lifecycle_status = :active
                  AND NOT EXISTS (
                    SELECT 1
                    FROM public.verification_tasks vt
                    JOIN public.verification_attestations va ON va.task_id = vt.task_id
                    WHERE vt.object_type = :object_type
                      AND vt.object_version_id = pee.employment_id
                      AND va.decision = :verified
                  )
                LIMIT 1
                """
            ),
            {
                "prior_id": prior_employment_id,
                "active": LIFECYCLE_STATUS_ACTIVE,
                "object_type": OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT,
                "verified": ATTESTATION_DECISION_VERIFIED,
            },
        ).first()
        return row is not None
