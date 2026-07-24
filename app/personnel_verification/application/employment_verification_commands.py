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
