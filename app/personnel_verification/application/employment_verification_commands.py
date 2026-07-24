"""WP-VER-005A employment verification command/query orchestration.

Owns one DB transaction per mutating call. EmploymentRevisionService must not commit.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.db.engine import engine as default_engine
from app.db.models.personnel_verification import (
    CONTROL_POINT_EMPLOYMENT_EPISODE,
    OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT,
    TASK_STATUS_PENDING,
)
from app.personnel_verification.application.employment_revision_service import (
    EmploymentRevisionService,
    RevisionDecisionResult,
)
from app.personnel_verification.application.verification_state_service import (
    VerificationStateService,
)
from app.personnel_verification.domain.errors import (
    ControlledRecordNotFoundError,
    RevisionConflictError,
    TaskValidationError,
)
from app.personnel_verification.domain.models import (
    DerivedVerificationState,
    VerificationTaskSnapshot,
)
from app.personnel_verification.infrastructure.repository import PersonnelVerificationRepository

_PRIOR_UPDATED_AT_SQL = text(
    """
    SELECT updated_at
    FROM public.person_external_employment
    WHERE employment_id = :employment_id
    """
)

_EMPLOYMENT_REVISION_SQL = text(
    """
    SELECT employment_id, person_id, lifecycle_status, supersedes_employment_id
    FROM public.person_external_employment
    WHERE employment_id = :employment_id
    """
)


@dataclass(frozen=True, slots=True)
class EmploymentPendingTaskView:
    task: VerificationTaskSnapshot
    prior_updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class EmploymentRecordSnapshot:
    employment_id: int
    record_kind: str
    employer_name: str | None
    department_name: str | None
    position_title: str | None
    employment_type: str | None
    started_at: Any
    ended_at: Any
    termination_reason: str | None
    document_reference: str | None
    notes: str | None
    lifecycle_status: str
    updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class EmploymentTaskReview:
    task: VerificationTaskSnapshot
    person_id: int
    person_full_name: str
    prior: EmploymentRecordSnapshot
    revision: EmploymentRecordSnapshot
    verification_state: str


_PERSON_NAME_SQL = text(
    """
    SELECT full_name
    FROM public.persons
    WHERE person_id = :person_id
    """
)

_EMPLOYMENT_SNAPSHOT_SQL = text(
    """
    SELECT employment_id, person_id, record_kind, employer_name, department_name,
           position_title, employment_type, started_at, ended_at,
           termination_reason, document_reference, notes,
           lifecycle_status, supersedes_employment_id, updated_at
    FROM public.person_external_employment
    WHERE employment_id = :employment_id
    """
)


def _map_employment_snapshot(row: Any) -> EmploymentRecordSnapshot:
    return EmploymentRecordSnapshot(
        employment_id=int(row["employment_id"]),
        record_kind=str(row["record_kind"]),
        employer_name=row["employer_name"],
        department_name=row["department_name"],
        position_title=row["position_title"],
        employment_type=row["employment_type"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        termination_reason=row["termination_reason"],
        document_reference=row["document_reference"],
        notes=row["notes"],
        lifecycle_status=str(row["lifecycle_status"]),
        updated_at=row["updated_at"],
    )


class EmploymentVerificationCommandService:
    """HTTP-facing employment revision confirm/reject/list/state."""

    def __init__(self, *, db_engine: Engine | None = None) -> None:
        self._engine = db_engine or default_engine

    def list_pending_tasks(
        self,
        *,
        person_id: int | None = None,
        limit: int = 100,
    ) -> list[EmploymentPendingTaskView]:
        with self._engine.connect() as conn:
            repo = PersonnelVerificationRepository(conn)
            tasks = repo.list_pending_employment_tasks(person_id=person_id, limit=limit)
            return [
                EmploymentPendingTaskView(
                    task=task,
                    prior_updated_at=self._prior_updated_at(conn, task.object_id),
                )
                for task in tasks
            ]

    def get_revision_state(self, *, revision_employment_id: int) -> DerivedVerificationState:
        with self._engine.connect() as conn:
            repo = PersonnelVerificationRepository(conn)
            self._require_employment_revision(conn, revision_employment_id)
            return VerificationStateService(repo).resolve_for_version(
                control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
                object_type=OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT,
                object_version_id=revision_employment_id,
            )

    def get_revision_person_id(self, *, revision_employment_id: int) -> int:
        with self._engine.connect() as conn:
            row = self._require_employment_revision(conn, revision_employment_id)
            return int(row["person_id"])

    def confirm_pending_revision(
        self,
        *,
        task_id: int,
        verifier_user_id: int,
        expected_prior_updated_at: datetime,
        verifier_employee_id: int | None = None,
        comment: str | None = None,
        evidence_ref: str | None = None,
    ) -> RevisionDecisionResult:
        with self._engine.connect() as conn:
            tx = conn.begin()
            try:
                result = EmploymentRevisionService(conn).confirm_pending_revision(
                    task_id=task_id,
                    verifier_user_id=verifier_user_id,
                    expected_prior_updated_at=expected_prior_updated_at,
                    verifier_employee_id=verifier_employee_id,
                    comment=comment,
                    evidence_ref=evidence_ref,
                )
                tx.commit()
                return result
            except Exception:
                tx.rollback()
                raise

    def reject_pending_revision(
        self,
        *,
        task_id: int,
        verifier_user_id: int,
        expected_prior_updated_at: datetime,
        verifier_employee_id: int | None = None,
        comment: str | None = None,
        evidence_ref: str | None = None,
    ) -> RevisionDecisionResult:
        with self._engine.connect() as conn:
            tx = conn.begin()
            try:
                result = EmploymentRevisionService(conn).reject_pending_revision(
                    task_id=task_id,
                    verifier_user_id=verifier_user_id,
                    expected_prior_updated_at=expected_prior_updated_at,
                    verifier_employee_id=verifier_employee_id,
                    comment=comment,
                    evidence_ref=evidence_ref,
                )
                tx.commit()
                return result
            except Exception:
                tx.rollback()
                raise

    def get_task(self, *, task_id: int) -> VerificationTaskSnapshot:
        with self._engine.connect() as conn:
            task = PersonnelVerificationRepository(conn).get_task(task_id)
            if task.control_point != CONTROL_POINT_EMPLOYMENT_EPISODE:
                raise TaskValidationError(
                    f"Task {task_id} is not an employment_episode verification task"
                )
            return task

    def get_task_review(self, *, task_id: int) -> EmploymentTaskReview:
        """Load HR-facing prior/revision snapshots for a pending employment task only."""
        with self._engine.connect() as conn:
            repo = PersonnelVerificationRepository(conn)
            task = repo.get_task(task_id)
            if task.control_point != CONTROL_POINT_EMPLOYMENT_EPISODE:
                raise TaskValidationError(
                    f"Task {task_id} is not an employment_episode verification task"
                )
            if task.object_type != OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT:
                raise TaskValidationError(
                    f"Task {task_id} object_type must be person_external_employment"
                )
            if task.status != TASK_STATUS_PENDING:
                raise RevisionConflictError(
                    f"Task {task_id} is not pending (status={task.status!r})"
                )

            prior_row = conn.execute(
                _EMPLOYMENT_SNAPSHOT_SQL, {"employment_id": task.object_id}
            ).mappings().first()
            revision_row = conn.execute(
                _EMPLOYMENT_SNAPSHOT_SQL, {"employment_id": task.object_version_id}
            ).mappings().first()
            if prior_row is None:
                raise ControlledRecordNotFoundError(
                    f"prior employment_id={task.object_id} not found"
                )
            if revision_row is None:
                raise ControlledRecordNotFoundError(
                    f"revision employment_id={task.object_version_id} not found"
                )
            if int(prior_row["person_id"]) != task.person_id:
                raise TaskValidationError("prior person_id does not match task")
            if int(revision_row["person_id"]) != task.person_id:
                raise TaskValidationError("revision person_id does not match task")
            supersedes = revision_row["supersedes_employment_id"]
            if supersedes is None or int(supersedes) != task.object_id:
                raise TaskValidationError(
                    "revision is not linked to task prior employment_id"
                )

            full_name = conn.execute(
                _PERSON_NAME_SQL, {"person_id": task.person_id}
            ).scalar_one_or_none()
            if full_name is None or not str(full_name).strip():
                raise ControlledRecordNotFoundError(
                    f"person_id={task.person_id} not found"
                )

            state = VerificationStateService(repo).resolve_for_version(
                control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
                object_type=OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT,
                object_version_id=task.object_version_id,
                policy_id=task.policy_id,
            )
            return EmploymentTaskReview(
                task=task,
                person_id=task.person_id,
                person_full_name=str(full_name).strip(),
                prior=_map_employment_snapshot(prior_row),
                revision=_map_employment_snapshot(revision_row),
                verification_state=state.state,
            )

    @staticmethod
    def _prior_updated_at(conn: Connection, prior_employment_id: int) -> datetime | None:
        return conn.execute(
            _PRIOR_UPDATED_AT_SQL,
            {"employment_id": prior_employment_id},
        ).scalar_one_or_none()

    @staticmethod
    def _require_employment_revision(
        conn: Connection, revision_employment_id: int
    ) -> dict[str, Any]:
        row = conn.execute(
            _EMPLOYMENT_REVISION_SQL,
            {"employment_id": revision_employment_id},
        ).mappings().first()
        if row is None:
            raise ControlledRecordNotFoundError(
                f"employment revision employment_id={revision_employment_id} not found"
            )
        if row["supersedes_employment_id"] is None:
            raise TaskValidationError(
                f"employment_id={revision_employment_id} is not a pending/confirmed revision"
            )
        return dict(row)
