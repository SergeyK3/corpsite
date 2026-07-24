"""SQLAlchemy repository for reconciliation decisions (no engine / no PPR mutations)."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import null as sa_null
from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection, RowMapping

from app.db.models.personnel_intake import PersonnelIntakeReconciliationDecision
from app.personnel_intake.domain.reconciliation.actions import APPLY_STATUS_PENDING
from app.personnel_intake.domain.reconciliation.errors import (
    ReconciliationConflictError,
    ReconciliationConcurrencyError,
    ReconciliationNotFoundError,
    ReconciliationValidationError,
)
from app.personnel_intake.domain.reconciliation.invariants import (
    assert_failure_evidence_for_terminal,
    assert_valid_batch_terminal_finalization,
    assert_valid_create,
    assert_valid_terminal_reason_code,
    assert_valid_transition,
    is_terminal_apply_status,
)
from app.personnel_intake.domain.reconciliation.models import (
    BatchTerminalFinalizationCommand,
    BatchTerminalFinalizationResult,
    BatchTerminalTransitionItem,
    CreatePendingDecisionCommand,
    CreatePendingDecisionResult,
    ReconcileDecisionRecord,
    TerminalTransitionCommand,
)

_COLUMNS = (
    PersonnelIntakeReconciliationDecision.decision_id,
    PersonnelIntakeReconciliationDecision.application_id,
    PersonnelIntakeReconciliationDecision.person_id,
    PersonnelIntakeReconciliationDecision.section_code,
    PersonnelIntakeReconciliationDecision.proposal_index,
    PersonnelIntakeReconciliationDecision.proposal_fingerprint,
    PersonnelIntakeReconciliationDecision.proposal_payload_digest,
    PersonnelIntakeReconciliationDecision.action,
    PersonnelIntakeReconciliationDecision.reason_code,
    PersonnelIntakeReconciliationDecision.evidence,
    PersonnelIntakeReconciliationDecision.target_canonical_record_id,
    PersonnelIntakeReconciliationDecision.expected_row_version,
    PersonnelIntakeReconciliationDecision.expected_canonical_precondition,
    PersonnelIntakeReconciliationDecision.decision_source,
    PersonnelIntakeReconciliationDecision.override_token,
    PersonnelIntakeReconciliationDecision.matcher_rule_id,
    PersonnelIntakeReconciliationDecision.matcher_version,
    PersonnelIntakeReconciliationDecision.policy_version,
    PersonnelIntakeReconciliationDecision.digest_algorithm_version,
    PersonnelIntakeReconciliationDecision.idempotency_key,
    PersonnelIntakeReconciliationDecision.intent_fingerprint,
    PersonnelIntakeReconciliationDecision.apply_status,
    PersonnelIntakeReconciliationDecision.failure_evidence,
    PersonnelIntakeReconciliationDecision.row_version,
    PersonnelIntakeReconciliationDecision.created_at,
    PersonnelIntakeReconciliationDecision.updated_at,
)


def _as_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return dict(value)
    raise TypeError(f"Expected JSON object, got {type(value)!r}")


def _from_row(row: RowMapping | dict[str, Any]) -> ReconcileDecisionRecord:
    return ReconcileDecisionRecord(
        decision_id=int(row["decision_id"]),
        application_id=int(row["application_id"]),
        person_id=int(row["person_id"]),
        section_code=str(row["section_code"]),
        proposal_index=int(row["proposal_index"]),
        proposal_fingerprint=str(row["proposal_fingerprint"]),
        proposal_payload_digest=str(row["proposal_payload_digest"]),
        action=str(row["action"]),
        reason_code=str(row["reason_code"]),
        evidence=_as_dict(row["evidence"]) or {},
        target_canonical_record_id=(
            int(row["target_canonical_record_id"])
            if row.get("target_canonical_record_id") is not None
            else None
        ),
        expected_row_version=(
            str(row["expected_row_version"]) if row.get("expected_row_version") is not None else None
        ),
        expected_canonical_precondition=str(row["expected_canonical_precondition"]),
        decision_source=str(row["decision_source"]),
        override_token=(
            str(row["override_token"]) if row.get("override_token") is not None else None
        ),
        matcher_rule_id=str(row["matcher_rule_id"]),
        matcher_version=str(row["matcher_version"]),
        policy_version=str(row["policy_version"]),
        digest_algorithm_version=str(row["digest_algorithm_version"]),
        idempotency_key=str(row["idempotency_key"]),
        intent_fingerprint=str(row["intent_fingerprint"]),
        apply_status=str(row["apply_status"]),
        failure_evidence=_as_dict(row.get("failure_evidence")),
        row_version=int(row["row_version"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class SqlAlchemyReconciliationDecisionRepository:
    """Durable reconciliation decision store. No matcher/engine/PPR writes."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def get_by_id(self, decision_id: int) -> ReconcileDecisionRecord | None:
        row = self._conn.execute(
            select(*_COLUMNS).where(
                PersonnelIntakeReconciliationDecision.decision_id == int(decision_id)
            )
        ).mappings().first()
        return _from_row(row) if row is not None else None

    def require_by_id(self, decision_id: int) -> ReconcileDecisionRecord:
        record = self.get_by_id(decision_id)
        if record is None:
            raise ReconciliationNotFoundError(
                f"Reconciliation decision {decision_id} not found."
            )
        return record

    def lock_for_update(self, decision_id: int) -> ReconcileDecisionRecord:
        """Load decision row under SELECT … FOR UPDATE (caller owns the transaction)."""
        row = self._conn.execute(
            select(*_COLUMNS)
            .where(PersonnelIntakeReconciliationDecision.decision_id == int(decision_id))
            .with_for_update()
        ).mappings().first()
        if row is None:
            raise ReconciliationNotFoundError(
                f"Reconciliation decision {decision_id} not found."
            )
        return _from_row(row)

    def get_by_idempotency_key(self, idempotency_key: str) -> ReconcileDecisionRecord | None:
        row = self._conn.execute(
            select(*_COLUMNS).where(
                PersonnelIntakeReconciliationDecision.idempotency_key == str(idempotency_key)
            )
        ).mappings().first()
        return _from_row(row) if row is not None else None

    def list_for_application(
        self,
        application_id: int,
        *,
        section_code: str | None = None,
    ) -> tuple[ReconcileDecisionRecord, ...]:
        """List durable decisions for an application (optional section filter)."""
        stmt = (
            select(*_COLUMNS)
            .where(
                PersonnelIntakeReconciliationDecision.application_id == int(application_id)
            )
            .order_by(
                PersonnelIntakeReconciliationDecision.section_code,
                PersonnelIntakeReconciliationDecision.proposal_index,
                PersonnelIntakeReconciliationDecision.decision_id,
            )
        )
        if section_code is not None:
            stmt = stmt.where(
                PersonnelIntakeReconciliationDecision.section_code == str(section_code)
            )
        rows = self._conn.execute(stmt).mappings().all()
        return tuple(_from_row(row) for row in rows)

    def _assert_application_belongs_to_person(
        self, *, application_id: int, person_id: int
    ) -> None:
        row = self._conn.execute(
            text(
                """
                SELECT person_id
                FROM public.personnel_applications
                WHERE application_id = :application_id
                """
            ),
            {"application_id": int(application_id)},
        ).scalar_one_or_none()
        if row is None:
            raise ReconciliationValidationError(
                f"Application {application_id} not found.",
                code="APPLICATION_NOT_FOUND",
            )
        if int(row) != int(person_id):
            raise ReconciliationValidationError(
                f"Application {application_id} does not belong to person_id={person_id}.",
                code="APPLICATION_PERSON_MISMATCH",
            )

    def create_pending(self, command: CreatePendingDecisionCommand) -> CreatePendingDecisionResult:
        intent_fingerprint = assert_valid_create(command)
        self._assert_application_belongs_to_person(
            application_id=command.application_id,
            person_id=command.person_id,
        )
        now = datetime.now(UTC)

        existing = self.get_by_idempotency_key(command.idempotency_key)
        if existing is not None:
            if existing.intent_fingerprint != intent_fingerprint:
                raise ReconciliationConflictError(
                    "Idempotency key already used with a different intent payload.",
                )
            return CreatePendingDecisionResult(decision=existing, idempotent_replay=True)

        values = {
            "application_id": int(command.application_id),
            "person_id": int(command.person_id),
            "section_code": command.section_code,
            "proposal_index": int(command.proposal_index),
            "proposal_fingerprint": command.proposal_fingerprint,
            "proposal_payload_digest": command.proposal_payload_digest,
            "action": command.action,
            "reason_code": command.reason_code,
            "evidence": dict(command.evidence),
            "target_canonical_record_id": command.target_canonical_record_id,
            "expected_row_version": command.expected_row_version,
            "expected_canonical_precondition": command.expected_canonical_precondition,
            "decision_source": command.decision_source,
            "override_token": command.override_token,
            "matcher_rule_id": command.matcher_rule_id,
            "matcher_version": command.matcher_version,
            "policy_version": command.policy_version,
            "digest_algorithm_version": command.digest_algorithm_version,
            "idempotency_key": command.idempotency_key,
            "intent_fingerprint": intent_fingerprint,
            "apply_status": APPLY_STATUS_PENDING,
            "row_version": 1,
            "created_at": now,
            "updated_at": now,
        }

        row = self._conn.execute(
            pg_insert(PersonnelIntakeReconciliationDecision)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
            .returning(*_COLUMNS)
        ).mappings().first()

        if row is None:
            existing = self.get_by_idempotency_key(command.idempotency_key)
            if existing is None:
                raise ReconciliationConflictError(
                    "Idempotency insert conflicted but existing decision was not found.",
                    code="RECONCILIATION_IDEMPOTENCY_RACE",
                )
            if existing.intent_fingerprint != intent_fingerprint:
                raise ReconciliationConflictError(
                    "Idempotency key already used with a different intent payload.",
                )
            return CreatePendingDecisionResult(decision=existing, idempotent_replay=True)

        return CreatePendingDecisionResult(decision=_from_row(row), idempotent_replay=False)

    def _validate_pending_terminal_transition(
        self,
        current: ReconcileDecisionRecord,
        item: BatchTerminalTransitionItem | TerminalTransitionCommand,
    ) -> None:
        assert_valid_terminal_reason_code(item.reason_code)
        assert_valid_transition(
            action=current.action,
            from_status=current.apply_status,
            to_status=item.to_status,
        )
        assert_failure_evidence_for_terminal(
            to_status=item.to_status,
            failure_evidence=item.failure_evidence,
        )
        if current.apply_status != APPLY_STATUS_PENDING:
            raise ReconciliationConcurrencyError(
                f"Decision {current.decision_id} is not pending "
                f"(apply_status={current.apply_status!r})."
            )
        if int(current.row_version) != int(item.expected_row_version):
            raise ReconciliationConcurrencyError(
                f"Stale row_version for decision {current.decision_id}: "
                f"expected {item.expected_row_version}, actual {current.row_version}."
            )

    def _terminal_update_values(
        self,
        *,
        current: ReconcileDecisionRecord,
        item: BatchTerminalTransitionItem | TerminalTransitionCommand,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        values: dict[str, Any] = {
            "apply_status": item.to_status,
            "row_version": int(current.row_version) + 1,
            "updated_at": now,
        }
        if item.failure_evidence is not None:
            values["failure_evidence"] = dict(item.failure_evidence)
        else:
            values["failure_evidence"] = sa_null()
        if item.reason_code is not None:
            values["reason_code"] = item.reason_code
        return values

    def _apply_terminal_transition(
        self,
        current: ReconcileDecisionRecord,
        item: BatchTerminalTransitionItem | TerminalTransitionCommand,
    ) -> ReconcileDecisionRecord:
        row = self._conn.execute(
            update(PersonnelIntakeReconciliationDecision)
            .where(
                PersonnelIntakeReconciliationDecision.decision_id == int(item.decision_id),
                PersonnelIntakeReconciliationDecision.row_version
                == int(item.expected_row_version),
                PersonnelIntakeReconciliationDecision.apply_status == APPLY_STATUS_PENDING,
            )
            .values(**self._terminal_update_values(current=current, item=item))
            .returning(*_COLUMNS)
        ).mappings().first()

        if row is None:
            latest = self.require_by_id(item.decision_id)
            if latest.apply_status != APPLY_STATUS_PENDING:
                raise ReconciliationConcurrencyError(
                    f"Decision {item.decision_id} is no longer pending "
                    f"(apply_status={latest.apply_status!r})."
                )
            raise ReconciliationConcurrencyError(
                f"Stale row_version for decision {item.decision_id}."
            )

        record = _from_row(row)
        if not is_terminal_apply_status(record.apply_status):
            raise ReconciliationConcurrencyError(
                f"Terminal transition left decision {item.decision_id} non-terminal "
                f"(apply_status={record.apply_status!r})."
            )
        return record

    def transition_to_terminal(
        self, command: TerminalTransitionCommand
    ) -> ReconcileDecisionRecord:
        current = self.require_by_id(command.decision_id)
        self._validate_pending_terminal_transition(current, command)
        return self._apply_terminal_transition(current, command)

    def finalize_batch_terminal(
        self, command: BatchTerminalFinalizationCommand
    ) -> BatchTerminalFinalizationResult:
        items = assert_valid_batch_terminal_finalization(command)
        decision_ids = [int(item.decision_id) for item in items]

        rows = self._conn.execute(
            select(*_COLUMNS).where(
                PersonnelIntakeReconciliationDecision.decision_id.in_(decision_ids)
            )
        ).mappings().all()
        loaded = {int(row["decision_id"]): _from_row(row) for row in rows}

        missing = [decision_id for decision_id in decision_ids if decision_id not in loaded]
        if missing:
            raise ReconciliationNotFoundError(
                f"Reconciliation decisions not found: {missing}."
            )

        for item in items:
            current = loaded[int(item.decision_id)]
            self._validate_pending_terminal_transition(current, item)

        with self._conn.begin_nested():
            updated: list[ReconcileDecisionRecord] = []
            for item in items:
                current = loaded[int(item.decision_id)]
                record = self._apply_terminal_transition(current, item)
                updated.append(record)

            if any(record.apply_status == APPLY_STATUS_PENDING for record in updated):
                raise ReconciliationConcurrencyError(
                    "Batch terminal finalization left pending decisions."
                )

            return BatchTerminalFinalizationResult(decisions=tuple(updated))
