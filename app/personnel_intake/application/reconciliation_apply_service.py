"""HR-facing apply entry for education reconciliation decisions (WP-009 API wiring)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from sqlalchemy.engine import Connection

from app.personnel_intake.application.reconciliation.executor import (
    ApplyDecisionResult,
    ApplyEducationDecisionCommand,
    EducationReconciliationDecisionExecutor,
)
from app.personnel_intake.domain.reconciliation.actions import SECTION_CODE_EDUCATION
from app.personnel_intake.domain.reconciliation.errors import (
    ReconciliationNotFoundError,
    ReconciliationValidationError,
)
from app.personnel_intake.infrastructure.reconciliation_repository import (
    SqlAlchemyReconciliationDecisionRepository,
)


@dataclass(frozen=True, slots=True)
class ApplyEducationReconciliationDecisionCommand:
    application_id: int
    decision_id: int
    section_payload: Mapping[str, Any]
    actor_id: str | None = None
    correlation_id: str | None = None
    digest_algorithm_version: str = "canon-json-v1"


def apply_education_reconciliation_decision(
    conn: Connection,
    command: ApplyEducationReconciliationDecisionCommand,
    *,
    executor: EducationReconciliationDecisionExecutor | None = None,
) -> ApplyDecisionResult:
    """Validate visibility/section, then delegate U2 apply to the education executor.

    Does not open/commit U2 itself — transaction ownership stays in the executor.
    A pre-apply visibility read may autobegin on a clean Connection; that is cleared
    before delegation so the executor still owns a full U2 begin when appropriate.
    """
    caller_owns_transaction = conn.in_transaction()
    repo = SqlAlchemyReconciliationDecisionRepository(conn)
    try:
        decision = repo.require_by_id(int(command.decision_id))
    except Exception:
        if not caller_owns_transaction and conn.in_transaction():
            conn.rollback()
        raise

    try:
        if int(decision.application_id) != int(command.application_id):
            # Same as missing: do not leak decisions across applications.
            raise ReconciliationNotFoundError(
                f"Reconciliation decision {command.decision_id} not found "
                f"for application_id={command.application_id}.",
                code="RECONCILIATION_NOT_FOUND",
            )
        if decision.section_code != SECTION_CODE_EDUCATION:
            raise ReconciliationValidationError(
                f"Decision {command.decision_id} section_code={decision.section_code!r} "
                "is not education.",
                code="INVALID_SECTION_FOR_EDUCATION_EXECUTOR",
            )
    finally:
        if not caller_owns_transaction and conn.in_transaction():
            conn.rollback()

    apply_executor = executor or EducationReconciliationDecisionExecutor()
    return apply_executor.apply_decision(
        conn,
        ApplyEducationDecisionCommand(
            decision_id=int(command.decision_id),
            section_payload=command.section_payload,
            actor_id=command.actor_id,
            correlation_id=command.correlation_id,
            digest_algorithm_version=command.digest_algorithm_version,
        ),
    )


__all__ = [
    "ApplyEducationReconciliationDecisionCommand",
    "apply_education_reconciliation_decision",
]
