"""Education reconciliation decision executor — U2 apply (WP-009 / WP-008 rev.4)."""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Iterator, Mapping

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.personnel_intake.application.reconciliation.dto import ProposalRecordRef
from app.personnel_intake.application.reconciliation.engine import SECTION_APPLY_MODE_PER_RECORD
from app.personnel_intake.application.reconciliation.plugins.education import (
    EducationReconciliationPlugin,
    edu_identity_key,
)
from app.personnel_intake.application.reconciliation.plugins.education_apply import (
    build_education_ppr_command,
    find_live_target,
    run_education_apply_gate,
    validate_deterministic_executable_intent,
)
from app.personnel_intake.domain.reconciliation.actions import (
    APPLY_STATUS_APPLIED,
    APPLY_STATUS_BLOCKED,
    APPLY_STATUS_FAILED,
    APPLY_STATUS_PENDING,
    APPLY_STATUS_SKIPPED_MANUAL,
    DECISION_EVIDENCE_REQUIRED_FIELDS,
    DECISION_SOURCE_SYSTEM,
    REASON_APPLY_CONCURRENCY_PRECONDITION,
    REASON_APPLY_NO_MATCH_LOST,
    REASON_APPLY_STALE_ROW_VERSION,
    RECONCILE_ACTION_ADD,
    RECONCILE_ACTION_KEEP_EXISTING,
    RECONCILE_ACTION_MANUAL_REVIEW,
    RECONCILE_ACTION_SUPERSEDE,
    RECONCILE_ACTION_UPDATE_VERSION,
    SECTION_CODE_EDUCATION,
    TERMINAL_APPLY_STATUSES,
)
from app.personnel_intake.domain.reconciliation.digest import (
    DEFAULT_DIGEST_BUILDER_REGISTRY,
    DigestBuilderRegistry,
)
from app.personnel_intake.domain.reconciliation.errors import ReconciliationValidationError
from app.personnel_intake.domain.reconciliation.models import (
    ReconcileDecisionRecord,
    TerminalTransitionCommand,
)
from app.personnel_intake.infrastructure.reconciliation_repository import (
    SqlAlchemyReconciliationDecisionRepository,
)
from app.ppr.application.authorization import AllowAllAuthorizationPort
from app.ppr.application.command_models import (
    COMMAND_TYPE_ADD_EDUCATION,
    COMMAND_TYPE_UPDATE_EDUCATION,
    PprCommandEnvelope,
)
from app.ppr.application.section_service import PprSectionApplicationService
from app.ppr.application.uow_participation import bind_participating_uow
from app.ppr.domain.errors import (
    SectionDuplicateRecordError,
    SectionOptimisticConcurrencyConflictError,
)
from app.ppr.domain.section_models import SECTION_CODE_PPR_EDUCATION, EducationRecord
from app.ppr.infrastructure.section_repository import SqlAlchemySectionReadRepository

_SUPPORTED_ACTIONS = frozenset(
    {
        RECONCILE_ACTION_ADD,
        RECONCILE_ACTION_UPDATE_VERSION,
        RECONCILE_ACTION_KEEP_EXISTING,
        RECONCILE_ACTION_MANUAL_REVIEW,
        RECONCILE_ACTION_SUPERSEDE,
    }
)


@dataclass(frozen=True, slots=True)
class ApplyEducationDecisionCommand:
    decision_id: int
    section_payload: Mapping[str, Any]
    actor_id: int | str | None = None
    correlation_id: str | None = None
    digest_algorithm_version: str = "canon-json-v1"


@dataclass(frozen=True, slots=True)
class ApplyDecisionResult:
    decision: ReconcileDecisionRecord
    idempotent_replay: bool
    result_status: str
    ppr_command_id: str | None = None
    section_record_id: int | None = None
    redecide_required: bool = False


@contextmanager
def _u2_transaction(conn: Connection, *, caller_owns_transaction: bool) -> Iterator[None]:
    """Open U2: full txn when executor owns the connection, else savepoint."""
    if caller_owns_transaction:
        with conn.begin_nested():
            yield
    else:
        with conn.begin():
            yield


def _clear_autobegin_if_unowned(conn: Connection, *, caller_owns_transaction: bool) -> None:
    """Drop SQLAlchemy autobegin left by a read when the caller had no active txn."""
    if not caller_owns_transaction and conn.in_transaction():
        conn.rollback()


def _stable_int64_hash(*parts: object) -> int:
    material = "|".join(str(part) for part in parts).encode("utf-8")
    digest = hashlib.sha256(material).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


def _acquire_education_identity_lock(
    conn: Connection, *, person_id: int, identity_key: tuple[str, str]
) -> None:
    lock_key = _stable_int64_hash(
        "recon-edu-identity", person_id, identity_key[0], identity_key[1]
    )
    conn.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": int(lock_key)})


def _terminal_result(
    decision: ReconcileDecisionRecord,
    *,
    idempotent_replay: bool = False,
    redecide_required: bool = False,
    ppr_command_id: str | None = None,
    section_record_id: int | None = None,
) -> ApplyDecisionResult:
    status = decision.apply_status
    if idempotent_replay:
        result_status = "idempotent_replay"
    elif status == APPLY_STATUS_APPLIED:
        result_status = "applied"
    elif status == APPLY_STATUS_SKIPPED_MANUAL:
        result_status = "skipped_manual"
    elif status == APPLY_STATUS_BLOCKED:
        result_status = "blocked_new_decide_required"
        redecide_required = True
    elif status == APPLY_STATUS_FAILED:
        result_status = "failed_new_decide_required"
        redecide_required = True
    else:
        result_status = "retryable_pending"
    return ApplyDecisionResult(
        decision=decision,
        idempotent_replay=idempotent_replay,
        result_status=result_status,
        ppr_command_id=ppr_command_id,
        section_record_id=section_record_id,
        redecide_required=redecide_required,
    )


def _validate_education_eligibility(decision: ReconcileDecisionRecord) -> None:
    if decision.section_code != SECTION_CODE_EDUCATION:
        raise ReconciliationValidationError(
            f"Education executor cannot apply section_code={decision.section_code!r}.",
            code="INVALID_SECTION_FOR_EDUCATION_EXECUTOR",
        )
    evidence_mode = decision.evidence.get("section_apply_mode")
    plugin_mode = EducationReconciliationPlugin.section_apply_mode
    if evidence_mode is not None and evidence_mode != SECTION_APPLY_MODE_PER_RECORD:
        raise ReconciliationValidationError(
            f"section_apply_mode must be per_record, got {evidence_mode!r}.",
            code="INVALID_SECTION_APPLY_MODE",
        )
    if plugin_mode != SECTION_APPLY_MODE_PER_RECORD:
        raise ReconciliationValidationError(
            f"education plugin section_apply_mode must be per_record, got {plugin_mode!r}.",
            code="INVALID_SECTION_APPLY_MODE",
        )
    if decision.decision_source != DECISION_SOURCE_SYSTEM:
        raise ReconciliationValidationError(
            f"Unsupported decision_source={decision.decision_source!r}.",
            code="UNSUPPORTED_DECISION_SOURCE",
        )
    if decision.action not in _SUPPORTED_ACTIONS:
        raise ReconciliationValidationError(
            f"Unsupported education apply action={decision.action!r}.",
            code="INVALID_EDUCATION_APPLY_ACTION",
        )
    for field in DECISION_EVIDENCE_REQUIRED_FIELDS:
        if field not in decision.evidence:
            raise ReconciliationValidationError(
                f"Decision evidence missing required field {field!r}.",
                code="INVALID_DECISION_EVIDENCE",
            )


def _rebuild_and_verify_proposal(
    *,
    plugin: EducationReconciliationPlugin,
    section_payload: Mapping[str, Any],
    decision: ReconcileDecisionRecord,
    digest_algorithm_version: str,
    digest_registry: DigestBuilderRegistry,
) -> ProposalRecordRef:
    try:
        digest_builder = digest_registry.resolve(digest_algorithm_version)
    except ReconciliationValidationError as exc:
        raise ReconciliationValidationError(
            str(exc),
            code="UNSUPPORTED_DIGEST_ALGORITHM",
        ) from exc

    if digest_algorithm_version != decision.digest_algorithm_version:
        raise ReconciliationValidationError(
            "Apply digest_algorithm_version does not match decision.",
            code="UNSUPPORTED_DIGEST_ALGORITHM",
        )

    proposals = plugin.build_proposal_refs(section_payload, digest_algorithm_version)
    by_index = {int(ref.proposal_index): ref for ref in proposals}
    proposal = by_index.get(int(decision.proposal_index))
    if proposal is None:
        raise ReconciliationValidationError(
            f"section_payload missing proposal_index={decision.proposal_index}.",
            code="PROPOSAL_DIGEST_MISMATCH",
        )

    digest = digest_builder.verify_or_compute(
        proposal.normalized_content,
        proposal.claimed_payload_digest,
    )
    enriched = replace(proposal, payload_digest=digest)
    if (
        enriched.payload_digest != decision.proposal_payload_digest
        or enriched.proposal_fingerprint != decision.proposal_fingerprint
        or int(enriched.proposal_index) != int(decision.proposal_index)
    ):
        raise ReconciliationValidationError(
            "Re-supplied education proposal does not match decision digests.",
            code="PROPOSAL_DIGEST_MISMATCH",
        )
    return enriched


def _enrich_canonicals(plugin_canonicals, digest_builder):
    enriched = []
    for ref in plugin_canonicals:
        digest = digest_builder.verify_or_compute(
            ref.normalized_content,
            ref.claimed_payload_digest,
        )
        enriched.append(replace(ref, payload_digest=digest))
    return tuple(enriched)


def _live_education_metadata(conn: Connection, person_id: int, record_id: int) -> dict[str, Any]:
    loaded = SqlAlchemySectionReadRepository(conn).load_record(
        person_id, SECTION_CODE_PPR_EDUCATION, record_id
    )
    if isinstance(loaded, EducationRecord) and loaded.metadata:
        return dict(loaded.metadata)
    return {}


def _build_failure_evidence_from_ppr(
    *,
    decision: ReconcileDecisionRecord,
    reason_code: str,
    exception: Exception,
) -> dict[str, Any]:
    return {
        "source": "intake_reconciliation_apply",
        "at": datetime.now(UTC).isoformat(),
        "gate": decision.action,
        "reason_code": reason_code,
        "detail": {
            "exception_type": type(exception).__name__,
            "message": str(exception),
        },
        "decision_id": int(decision.decision_id),
        "idempotency_key": decision.idempotency_key,
    }


class EducationReconciliationDecisionExecutor:
    """Apply one pending education reconciliation decision (U2 per_record)."""

    section_code = SECTION_CODE_EDUCATION
    section_apply_mode = SECTION_APPLY_MODE_PER_RECORD

    def __init__(
        self,
        *,
        plugin: EducationReconciliationPlugin | None = None,
        digest_registry: DigestBuilderRegistry | None = None,
        section_service: PprSectionApplicationService | None = None,
    ) -> None:
        self._plugin = plugin or EducationReconciliationPlugin()
        self._digest_registry = digest_registry or DEFAULT_DIGEST_BUILDER_REGISTRY
        self._section_service = section_service or PprSectionApplicationService(
            authorization=AllowAllAuthorizationPort()
        )

    def apply_decision(
        self,
        conn: Connection,
        command: ApplyEducationDecisionCommand,
    ) -> ApplyDecisionResult:
        # Capture ownership BEFORE any SQL (autobegin would otherwise mask a clean Connection).
        caller_owns_transaction = conn.in_transaction()
        repo = SqlAlchemyReconciliationDecisionRepository(conn)
        try:
            peek = repo.require_by_id(command.decision_id)
        except Exception:
            _clear_autobegin_if_unowned(conn, caller_owns_transaction=caller_owns_transaction)
            raise

        if peek.apply_status in {APPLY_STATUS_APPLIED, APPLY_STATUS_SKIPPED_MANUAL}:
            _clear_autobegin_if_unowned(conn, caller_owns_transaction=caller_owns_transaction)
            return _terminal_result(peek, idempotent_replay=True)
        if peek.apply_status in {APPLY_STATUS_BLOCKED, APPLY_STATUS_FAILED}:
            _clear_autobegin_if_unowned(conn, caller_owns_transaction=caller_owns_transaction)
            return _terminal_result(peek, redecide_required=True)

        # Pending path: drop peek autobegin so executor can open a real U2 begin().
        _clear_autobegin_if_unowned(conn, caller_owns_transaction=caller_owns_transaction)

        with _u2_transaction(conn, caller_owns_transaction=caller_owns_transaction):
            current = repo.lock_for_update(command.decision_id)

            if current.apply_status in {APPLY_STATUS_APPLIED, APPLY_STATUS_SKIPPED_MANUAL}:
                # Nested txn will release; return terminal replay without mutation.
                return _terminal_result(current, idempotent_replay=True)
            if current.apply_status in {APPLY_STATUS_BLOCKED, APPLY_STATUS_FAILED}:
                return _terminal_result(current, redecide_required=True)
            if current.apply_status != APPLY_STATUS_PENDING:
                raise ReconciliationValidationError(
                    f"Unexpected apply_status under lock: {current.apply_status!r}.",
                    code="INVALID_DECISION_EVIDENCE",
                )

            _validate_education_eligibility(current)

            deterministic = validate_deterministic_executable_intent(current)
            if deterministic is not None:
                # Keep decide-time reason_code; deterministic code lives in failure_evidence
                # (WP-003 terminal reason_code catalog does not include SYSTEM_* codes).
                failed = repo.transition_to_terminal(
                    TerminalTransitionCommand(
                        decision_id=int(current.decision_id),
                        expected_row_version=int(current.row_version),
                        to_status=APPLY_STATUS_FAILED,
                        failure_evidence=dict(deterministic.evidence or {}),
                    )
                )
                return _terminal_result(failed, redecide_required=True)

            proposal = _rebuild_and_verify_proposal(
                plugin=self._plugin,
                section_payload=command.section_payload,
                decision=current,
                digest_algorithm_version=command.digest_algorithm_version,
                digest_registry=self._digest_registry,
            )

            if current.action == RECONCILE_ACTION_MANUAL_REVIEW:
                skipped = repo.transition_to_terminal(
                    TerminalTransitionCommand(
                        decision_id=int(current.decision_id),
                        expected_row_version=int(current.row_version),
                        to_status=APPLY_STATUS_SKIPPED_MANUAL,
                    )
                )
                return _terminal_result(skipped)

            if current.action == RECONCILE_ACTION_ADD:
                _acquire_education_identity_lock(
                    conn,
                    person_id=int(current.person_id),
                    identity_key=edu_identity_key(proposal.normalized_content),
                )

            digest_builder = self._digest_registry.resolve(command.digest_algorithm_version)
            live_raw = self._plugin.load_canonical_refs(
                conn,
                int(current.person_id),
                command.digest_algorithm_version,
            )
            live = _enrich_canonicals(live_raw, digest_builder)
            gate = run_education_apply_gate(
                current,
                proposal,
                live,
                digest_builder=digest_builder,
            )
            if gate.outcome == "block":
                blocked = repo.transition_to_terminal(
                    TerminalTransitionCommand(
                        decision_id=int(current.decision_id),
                        expected_row_version=int(current.row_version),
                        to_status=APPLY_STATUS_BLOCKED,
                        failure_evidence=dict(gate.evidence or {}),
                        reason_code=gate.reason_code,
                    )
                )
                return _terminal_result(blocked, redecide_required=True)

            if current.action == RECONCILE_ACTION_KEEP_EXISTING:
                applied = repo.transition_to_terminal(
                    TerminalTransitionCommand(
                        decision_id=int(current.decision_id),
                        expected_row_version=int(current.row_version),
                        to_status=APPLY_STATUS_APPLIED,
                    )
                )
                return _terminal_result(applied)

            live_target = find_live_target(current, live)
            command_spec = build_education_ppr_command(current, proposal, live_target)
            if command_spec is None:
                raise ReconciliationValidationError(
                    f"No PPR command mapping for action={current.action!r}.",
                    code="INVALID_EDUCATION_APPLY_ACTION",
                )

            if command_spec.command_type == COMMAND_TYPE_UPDATE_EDUCATION and live_target is not None:
                live_meta = _live_education_metadata(
                    conn, int(current.person_id), int(live_target.record_id)
                )
                merged = dict(live_meta)
                merged.update(command_spec.payload.get("metadata") or {})
                command_spec.payload["metadata"] = merged

            actor_id = (
                str(command.actor_id)
                if command.actor_id is not None
                else "personnel_intake_reconciliation"
            )
            correlation_id = command.correlation_id or current.evidence.get("correlation_id")
            ppr_command_id = f"recon-apply:{current.idempotency_key}"
            envelope = PprCommandEnvelope(
                command_id=ppr_command_id,
                command_type=command_spec.command_type,
                actor_id=actor_id,
                requested_at=datetime.now(UTC),
                payload=command_spec.payload,
                person_id=int(current.person_id),
                correlation_id=str(correlation_id) if correlation_id is not None else None,
            )

            uow = bind_participating_uow(conn)
            try:
                with conn.begin_nested():
                    if command_spec.command_type == COMMAND_TYPE_ADD_EDUCATION:
                        ppr_result = self._section_service.add_education_participating(
                            uow, envelope
                        )
                    elif command_spec.command_type == COMMAND_TYPE_UPDATE_EDUCATION:
                        ppr_result = self._section_service.update_education_participating(
                            uow, envelope
                        )
                    else:
                        raise ReconciliationValidationError(
                            f"Unexpected PPR command type {command_spec.command_type!r}.",
                            code="INVALID_EDUCATION_APPLY_ACTION",
                        )
            except SectionOptimisticConcurrencyConflictError as exc:
                blocked = repo.transition_to_terminal(
                    TerminalTransitionCommand(
                        decision_id=int(current.decision_id),
                        expected_row_version=int(current.row_version),
                        to_status=APPLY_STATUS_BLOCKED,
                        failure_evidence=_build_failure_evidence_from_ppr(
                            decision=current,
                            reason_code=REASON_APPLY_STALE_ROW_VERSION,
                            exception=exc,
                        ),
                        reason_code=REASON_APPLY_STALE_ROW_VERSION,
                    )
                )
                return _terminal_result(blocked, redecide_required=True)
            except SectionDuplicateRecordError as exc:
                reason = (
                    REASON_APPLY_NO_MATCH_LOST
                    if current.action == RECONCILE_ACTION_ADD
                    else REASON_APPLY_CONCURRENCY_PRECONDITION
                )
                blocked = repo.transition_to_terminal(
                    TerminalTransitionCommand(
                        decision_id=int(current.decision_id),
                        expected_row_version=int(current.row_version),
                        to_status=APPLY_STATUS_BLOCKED,
                        failure_evidence=_build_failure_evidence_from_ppr(
                            decision=current,
                            reason_code=reason,
                            exception=exc,
                        ),
                        reason_code=reason,
                    )
                )
                return _terminal_result(blocked, redecide_required=True)

            applied = repo.transition_to_terminal(
                TerminalTransitionCommand(
                    decision_id=int(current.decision_id),
                    expected_row_version=int(current.row_version),
                    to_status=APPLY_STATUS_APPLIED,
                )
            )
            if applied.apply_status not in TERMINAL_APPLY_STATUSES:
                raise RuntimeError(
                    f"Terminal transition left non-terminal status={applied.apply_status!r}"
                )
            return _terminal_result(
                applied,
                ppr_command_id=ppr_command_id,
                section_record_id=ppr_result.section_record_id,
            )


__all__ = [
    "ApplyDecisionResult",
    "ApplyEducationDecisionCommand",
    "EducationReconciliationDecisionExecutor",
]
