"""Fail-closed invariants for reconciliation decisions."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from app.personnel_intake.domain.reconciliation.actions import (
    ALLOWED_APPLY_TRANSITIONS,
    APPLY_STATUS_APPLIED,
    APPLY_STATUS_BLOCKED,
    APPLY_STATUS_FAILED,
    APPLY_STATUS_PENDING,
    APPLY_STATUS_SKIPPED_MANUAL,
    APPLY_STATUSES,
    DECISION_EVIDENCE_REQUIRED_FIELDS,
    DECISION_SOURCE_HR,
    DECISION_SOURCE_SYSTEM,
    DECISION_SOURCES,
    EVIDENCE_SOURCE_INTAKE_RECONCILIATION,
    FORBIDDEN_ACTIONS,
    FORBIDDEN_APPLY_STATUSES,
    MATCH_CONFIDENCE_HIGH,
    MATCH_CONFIDENCE_LOW,
    MATCH_CONFIDENCES,
    MATCH_KIND_AMBIGUOUS,
    MATCH_KIND_EXACT_ONE,
    MATCH_KIND_NONE,
    MATCH_KIND_STALE_TARGET,
    MATCH_KINDS,
    REASON_CODES,
    REASON_HR_Q3_NO_AUTO_MERGE,
    REASON_MATCH_AMBIGUOUS,
    REASON_MATCH_CONFIDENCE_LOW,
    REASON_MATCH_EXACT_KEEP,
    REASON_MATCH_EXACT_SUPERSEDE,
    REASON_MATCH_EXACT_UPDATE,
    REASON_MATCH_NONE_CONFIDENT,
    REASON_MATCH_STALE_TARGET,
    RECONCILE_ACTION_ADD,
    RECONCILE_ACTION_KEEP_EXISTING,
    RECONCILE_ACTION_MANUAL_REVIEW,
    RECONCILE_ACTION_SUPERSEDE,
    RECONCILE_ACTION_UPDATE_VERSION,
    RECONCILE_ACTIONS,
    SECTION_CODES,
    TERMINAL_APPLY_STATUSES,
)
from app.personnel_intake.domain.reconciliation.errors import ReconciliationValidationError
from app.personnel_intake.domain.reconciliation.models import (
    BatchTerminalFinalizationCommand,
    BatchTerminalTransitionItem,
    CreatePendingDecisionCommand,
)


def is_terminal_apply_status(status: str) -> bool:
    return status in TERMINAL_APPLY_STATUSES


def assert_valid_action(action: str) -> None:
    if action in FORBIDDEN_ACTIONS:
        raise ReconciliationValidationError(
            f"Forbidden reconcile action {action!r} (not a ReconcileAction).",
            code="FORBIDDEN_RECONCILE_ACTION",
        )
    if action not in RECONCILE_ACTIONS:
        raise ReconciliationValidationError(
            f"Unknown reconcile action {action!r}.",
            code="UNKNOWN_RECONCILE_ACTION",
        )


def assert_valid_apply_status(status: str) -> None:
    if status in FORBIDDEN_APPLY_STATUSES:
        raise ReconciliationValidationError(
            f"Forbidden persisted apply_status {status!r}.",
            code="FORBIDDEN_APPLY_STATUS",
        )
    if status not in APPLY_STATUSES:
        raise ReconciliationValidationError(
            f"Unknown apply_status {status!r}.",
            code="UNKNOWN_APPLY_STATUS",
        )


def assert_valid_transition(*, action: str, from_status: str, to_status: str) -> None:
    assert_valid_action(action)
    assert_valid_apply_status(from_status)
    assert_valid_apply_status(to_status)

    allowed = ALLOWED_APPLY_TRANSITIONS.get(from_status, frozenset())
    if to_status not in allowed:
        raise ReconciliationValidationError(
            f"Illegal apply_status transition {from_status!r} → {to_status!r}.",
            code="ILLEGAL_APPLY_TRANSITION",
        )

    if to_status == APPLY_STATUS_SKIPPED_MANUAL and action != RECONCILE_ACTION_MANUAL_REVIEW:
        raise ReconciliationValidationError(
            "skipped_manual is only valid for action=manual_review.",
            code="INVALID_SKIPPED_MANUAL_ACTION",
        )

    if to_status == APPLY_STATUS_APPLIED and action == RECONCILE_ACTION_MANUAL_REVIEW:
        raise ReconciliationValidationError(
            "manual_review cannot transition to applied; use skipped_manual.",
            code="INVALID_APPLIED_FOR_MANUAL_REVIEW",
        )


def assert_valid_reason_code(reason_code: str) -> None:
    if reason_code not in REASON_CODES:
        raise ReconciliationValidationError(
            f"Unknown reason_code {reason_code!r}.",
            code="UNKNOWN_REASON_CODE",
        )


def assert_valid_terminal_reason_code(reason_code: str | None) -> None:
    if reason_code is not None:
        assert_valid_reason_code(reason_code)


def assert_valid_decision_evidence(
    evidence: Mapping[str, Any],
    command: CreatePendingDecisionCommand,
) -> None:
    if not isinstance(evidence, dict):
        raise ReconciliationValidationError(
            "evidence must be a JSON object.",
            code="INVALID_EVIDENCE",
        )
    missing = [field for field in DECISION_EVIDENCE_REQUIRED_FIELDS if field not in evidence]
    if missing:
        raise ReconciliationValidationError(
            f"evidence missing required fields: {', '.join(missing)}.",
            code="INCOMPLETE_EVIDENCE",
        )

    source = evidence.get("source")
    if source != EVIDENCE_SOURCE_INTAKE_RECONCILIATION:
        raise ReconciliationValidationError(
            f"evidence.source must be {EVIDENCE_SOURCE_INTAKE_RECONCILIATION!r}.",
            code="INVALID_EVIDENCE_SOURCE",
        )

    if not isinstance(evidence.get("candidate_canonical_record_ids"), list):
        raise ReconciliationValidationError(
            "evidence.candidate_canonical_record_ids must be a list.",
            code="INVALID_EVIDENCE_CANDIDATES",
        )

    semantically_equal = evidence.get("semantically_equal")
    if semantically_equal is not None and not isinstance(semantically_equal, bool):
        raise ReconciliationValidationError(
            "evidence.semantically_equal must be bool or null.",
            code="INVALID_EVIDENCE_SEMANTICALLY_EQUAL",
        )

    after_intent_digest = evidence.get("after_intent_digest")
    if not isinstance(after_intent_digest, str) or not after_intent_digest.strip():
        raise ReconciliationValidationError(
            "evidence.after_intent_digest is required and must be non-empty.",
            code="INVALID_EVIDENCE_AFTER_INTENT_DIGEST",
        )

    _require_nonempty(str(evidence.get("idempotency_key") or ""), field="evidence.idempotency_key")

    cross_checks: tuple[tuple[str, Any, Any], ...] = (
        ("application_id", evidence.get("application_id"), command.application_id),
        ("section_code", evidence.get("section_code"), command.section_code),
        ("proposal_index", evidence.get("proposal_index"), command.proposal_index),
        ("proposal_fingerprint", evidence.get("proposal_fingerprint"), command.proposal_fingerprint),
        ("proposal_payload_digest", evidence.get("proposal_payload_digest"), command.proposal_payload_digest),
        ("digest_algorithm_version", evidence.get("digest_algorithm_version"), command.digest_algorithm_version),
        ("matcher_rule_id", evidence.get("matcher_rule_id"), command.matcher_rule_id),
        ("matcher_version", evidence.get("matcher_version"), command.matcher_version),
        ("policy_version", evidence.get("policy_version"), command.policy_version),
        ("expected_canonical_precondition", evidence.get("expected_canonical_precondition"), command.expected_canonical_precondition),
        ("action", evidence.get("action"), command.action),
        ("reason_code", evidence.get("reason_code"), command.reason_code),
        ("decision_source", evidence.get("decision_source"), command.decision_source),
        ("override_token", evidence.get("override_token"), command.override_token),
        ("idempotency_key", evidence.get("idempotency_key"), command.idempotency_key),
    )
    for field, evidence_value, command_value in cross_checks:
        if evidence_value != command_value:
            raise ReconciliationValidationError(
                f"evidence.{field} must match command ({evidence_value!r} != {command_value!r}).",
                code="EVIDENCE_COMMAND_MISMATCH",
            )

    assert_action_evidence_consistency(command)


def _require_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReconciliationValidationError(
            f"{field} must be int.",
            code="INVALID_EVIDENCE_INTEGER",
        )
    return int(value)


def assert_action_evidence_consistency(command: CreatePendingDecisionCommand) -> None:
    """Cross-check action/reason_code vs evidence match fields (002 rev.3 §5.2, §6.2)."""
    evidence = command.evidence
    match_kind = evidence.get("match_kind")
    match_confidence = evidence.get("match_confidence")

    _require_nonempty(str(match_kind or ""), field="evidence.match_kind")
    _require_nonempty(str(match_confidence or ""), field="evidence.match_confidence")

    if match_kind not in MATCH_KINDS:
        raise ReconciliationValidationError(
            f"Unknown evidence.match_kind {match_kind!r}.",
            code="INVALID_EVIDENCE_MATCH_KIND",
        )
    if match_confidence not in MATCH_CONFIDENCES:
        raise ReconciliationValidationError(
            f"Unknown evidence.match_confidence {match_confidence!r}.",
            code="INVALID_EVIDENCE_MATCH_CONFIDENCE",
        )

    candidates = evidence.get("candidate_canonical_record_ids")
    for index, candidate_id in enumerate(candidates):
        _require_int(candidate_id, field=f"evidence.candidate_canonical_record_ids[{index}]")

    matched = evidence.get("matched_canonical_record_id")
    if matched is not None:
        matched = _require_int(matched, field="evidence.matched_canonical_record_id")

    uncertain_match = (
        match_kind in {MATCH_KIND_AMBIGUOUS, MATCH_KIND_STALE_TARGET}
        or match_confidence == MATCH_CONFIDENCE_LOW
    )
    if uncertain_match and command.action != RECONCILE_ACTION_MANUAL_REVIEW:
        raise ReconciliationValidationError(
            f"action={command.action!r} is invalid for "
            f"match_kind={match_kind!r}, match_confidence={match_confidence!r}; "
            "must be manual_review.",
            code="INVALID_ACTION_FOR_MATCH_OUTCOME",
        )

    if command.action == RECONCILE_ACTION_ADD:
        if command.reason_code != REASON_MATCH_NONE_CONFIDENT:
            raise ReconciliationValidationError(
                "action=add requires reason_code=MATCH_NONE_CONFIDENT.",
                code="INVALID_ADD_REASON",
            )
        if match_kind != MATCH_KIND_NONE or match_confidence != MATCH_CONFIDENCE_HIGH:
            raise ReconciliationValidationError(
                "action=add requires match_kind=none and match_confidence=high.",
                code="INVALID_ADD_MATCH_OUTCOME",
            )
        if matched is not None:
            raise ReconciliationValidationError(
                "action=add must not set evidence.matched_canonical_record_id.",
                code="FORBIDDEN_MATCHED_FOR_ADD",
            )
        return

    if command.action == RECONCILE_ACTION_KEEP_EXISTING:
        if command.reason_code != REASON_MATCH_EXACT_KEEP:
            raise ReconciliationValidationError(
                "action=keep_existing requires reason_code=MATCH_EXACT_KEEP.",
                code="INVALID_KEEP_REASON",
            )
        if match_kind != MATCH_KIND_EXACT_ONE or match_confidence != MATCH_CONFIDENCE_HIGH:
            raise ReconciliationValidationError(
                "action=keep_existing requires match_kind=exact_one and match_confidence=high.",
                code="INVALID_KEEP_MATCH_OUTCOME",
            )
        if evidence.get("semantically_equal") is not True:
            raise ReconciliationValidationError(
                "action=keep_existing requires evidence.semantically_equal=true.",
                code="INVALID_KEEP_SEMANTICALLY_EQUAL",
            )
        if matched != command.target_canonical_record_id:
            raise ReconciliationValidationError(
                "evidence.matched_canonical_record_id must equal target_canonical_record_id "
                f"for keep_existing ({matched!r} != {command.target_canonical_record_id!r}).",
                code="MATCHED_TARGET_MISMATCH",
            )
        return

    if command.action == RECONCILE_ACTION_UPDATE_VERSION:
        if command.reason_code != REASON_MATCH_EXACT_UPDATE:
            raise ReconciliationValidationError(
                "action=update_version requires reason_code=MATCH_EXACT_UPDATE.",
                code="INVALID_UPDATE_REASON",
            )
        if match_kind != MATCH_KIND_EXACT_ONE or match_confidence != MATCH_CONFIDENCE_HIGH:
            raise ReconciliationValidationError(
                "action=update_version requires match_kind=exact_one and match_confidence=high.",
                code="INVALID_UPDATE_MATCH_OUTCOME",
            )
        if matched != command.target_canonical_record_id:
            raise ReconciliationValidationError(
                "evidence.matched_canonical_record_id must equal target_canonical_record_id "
                f"for update_version ({matched!r} != {command.target_canonical_record_id!r}).",
                code="MATCHED_TARGET_MISMATCH",
            )
        return

    if command.action == RECONCILE_ACTION_SUPERSEDE:
        if command.reason_code != REASON_MATCH_EXACT_SUPERSEDE:
            raise ReconciliationValidationError(
                "action=supersede requires reason_code=MATCH_EXACT_SUPERSEDE.",
                code="INVALID_SUPERSEDE_REASON",
            )
        if match_kind != MATCH_KIND_EXACT_ONE or match_confidence != MATCH_CONFIDENCE_HIGH:
            raise ReconciliationValidationError(
                "action=supersede requires match_kind=exact_one and match_confidence=high.",
                code="INVALID_SUPERSEDE_MATCH_OUTCOME",
            )
        if matched != command.target_canonical_record_id:
            raise ReconciliationValidationError(
                "evidence.matched_canonical_record_id must equal target_canonical_record_id "
                f"for supersede ({matched!r} != {command.target_canonical_record_id!r}).",
                code="MATCHED_TARGET_MISMATCH",
            )
        return

    if command.action == RECONCILE_ACTION_MANUAL_REVIEW:
        allowed_reasons = {
            REASON_MATCH_AMBIGUOUS,
            REASON_MATCH_CONFIDENCE_LOW,
            REASON_MATCH_STALE_TARGET,
            REASON_HR_Q3_NO_AUTO_MERGE,
        }
        if command.reason_code not in allowed_reasons:
            raise ReconciliationValidationError(
                f"action=manual_review requires reason_code in {sorted(allowed_reasons)!r}.",
                code="INVALID_MANUAL_REVIEW_REASON",
            )


def _require_nonempty(value: str, *, field: str) -> str:
    text = (value or "").strip()
    if not text:
        raise ReconciliationValidationError(
            f"{field} is required and must be non-empty.",
            code="REQUIRED_FIELD",
        )
    return text


def compute_intent_fingerprint(
    *,
    application_id: int,
    person_id: int,
    section_code: str,
    proposal_index: int,
    proposal_fingerprint: str,
    proposal_payload_digest: str,
    action: str,
    reason_code: str,
    evidence: Mapping[str, Any],
    target_canonical_record_id: int | None,
    expected_row_version: str | None,
    expected_canonical_precondition: str,
    decision_source: str,
    override_token: str | None,
    matcher_rule_id: str,
    matcher_version: str,
    policy_version: str,
    digest_algorithm_version: str,
    idempotency_key: str,
) -> str:
    """Stable hash of execution-intent fields for conflict detection."""
    payload = {
        "application_id": int(application_id),
        "person_id": int(person_id),
        "section_code": section_code,
        "proposal_index": int(proposal_index),
        "proposal_fingerprint": proposal_fingerprint,
        "proposal_payload_digest": proposal_payload_digest,
        "action": action,
        "reason_code": reason_code,
        "evidence": evidence,
        "target_canonical_record_id": target_canonical_record_id,
        "expected_row_version": expected_row_version,
        "expected_canonical_precondition": expected_canonical_precondition,
        "decision_source": decision_source,
        "override_token": override_token,
        "matcher_rule_id": matcher_rule_id,
        "matcher_version": matcher_version,
        "policy_version": policy_version,
        "digest_algorithm_version": digest_algorithm_version,
        "idempotency_key": idempotency_key,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def assert_valid_create(command: CreatePendingDecisionCommand) -> str:
    """Validate create command; return intent_fingerprint."""
    assert_valid_action(command.action)

    if command.section_code not in SECTION_CODES:
        raise ReconciliationValidationError(
            f"Unsupported section_code {command.section_code!r}.",
            code="UNKNOWN_SECTION_CODE",
        )
    if command.decision_source not in DECISION_SOURCES:
        raise ReconciliationValidationError(
            f"Unknown decision_source {command.decision_source!r}.",
            code="UNKNOWN_DECISION_SOURCE",
        )
    assert_valid_reason_code(command.reason_code)
    if int(command.proposal_index) < 0:
        raise ReconciliationValidationError(
            "proposal_index must be >= 0.",
            code="INVALID_PROPOSAL_INDEX",
        )

    _require_nonempty(command.proposal_fingerprint, field="proposal_fingerprint")
    _require_nonempty(command.proposal_payload_digest, field="proposal_payload_digest")
    _require_nonempty(command.expected_canonical_precondition, field="expected_canonical_precondition")
    _require_nonempty(command.matcher_rule_id, field="matcher_rule_id")
    _require_nonempty(command.matcher_version, field="matcher_version")
    _require_nonempty(command.policy_version, field="policy_version")
    _require_nonempty(command.digest_algorithm_version, field="digest_algorithm_version")
    _require_nonempty(command.idempotency_key, field="idempotency_key")

    assert_valid_decision_evidence(command.evidence, command)

    # assert_valid_decision_evidence already invokes assert_action_evidence_consistency.

    if command.decision_source == DECISION_SOURCE_SYSTEM and command.override_token is not None:
        raise ReconciliationValidationError(
            "system decisions must not supply override_token.",
            code="INVALID_OVERRIDE_TOKEN",
        )
    if command.decision_source == DECISION_SOURCE_HR:
        token = (command.override_token or "").strip()
        if not token:
            raise ReconciliationValidationError(
                "hr decisions require non-empty override_token.",
                code="REQUIRED_OVERRIDE_TOKEN",
            )

    if command.action in {
        RECONCILE_ACTION_KEEP_EXISTING,
        RECONCILE_ACTION_UPDATE_VERSION,
        RECONCILE_ACTION_SUPERSEDE,
    }:
        if command.target_canonical_record_id is None:
            raise ReconciliationValidationError(
                f"action={command.action!r} requires target_canonical_record_id.",
                code="REQUIRED_TARGET",
            )
    if command.action in {RECONCILE_ACTION_UPDATE_VERSION, RECONCILE_ACTION_SUPERSEDE}:
        if not (command.expected_row_version or "").strip():
            raise ReconciliationValidationError(
                f"action={command.action!r} requires expected_row_version.",
                code="REQUIRED_EXPECTED_ROW_VERSION",
            )
    if command.action == RECONCILE_ACTION_ADD and command.target_canonical_record_id is not None:
        raise ReconciliationValidationError(
            "action=add must not set target_canonical_record_id.",
            code="FORBIDDEN_TARGET_FOR_ADD",
        )

    fingerprint = compute_intent_fingerprint(
        application_id=command.application_id,
        person_id=command.person_id,
        section_code=command.section_code,
        proposal_index=command.proposal_index,
        proposal_fingerprint=command.proposal_fingerprint,
        proposal_payload_digest=command.proposal_payload_digest,
        action=command.action,
        reason_code=command.reason_code,
        evidence=command.evidence,
        target_canonical_record_id=command.target_canonical_record_id,
        expected_row_version=command.expected_row_version,
        expected_canonical_precondition=command.expected_canonical_precondition,
        decision_source=command.decision_source,
        override_token=command.override_token,
        matcher_rule_id=command.matcher_rule_id,
        matcher_version=command.matcher_version,
        policy_version=command.policy_version,
        digest_algorithm_version=command.digest_algorithm_version,
        idempotency_key=command.idempotency_key,
    )
    if command.intent_fingerprint is not None and command.intent_fingerprint != fingerprint:
        raise ReconciliationValidationError(
            "intent_fingerprint does not match command fields.",
            code="INTENT_FINGERPRINT_MISMATCH",
        )
    return fingerprint


def assert_valid_batch_terminal_finalization(
    command: BatchTerminalFinalizationCommand,
) -> tuple[BatchTerminalTransitionItem, ...]:
    if not command.transitions:
        raise ReconciliationValidationError(
            "Batch terminal finalization requires at least one transition.",
            code="EMPTY_BATCH",
        )
    decision_ids = [int(item.decision_id) for item in command.transitions]
    if len(decision_ids) != len(set(decision_ids)):
        raise ReconciliationValidationError(
            "Batch terminal finalization requires unique decision_id values.",
            code="BATCH_DUPLICATE_DECISION_ID",
        )
    return command.transitions


def assert_failure_evidence_for_terminal(
    *,
    to_status: str,
    failure_evidence: Mapping[str, Any] | None,
) -> None:
    if to_status in {APPLY_STATUS_BLOCKED, APPLY_STATUS_FAILED}:
        if failure_evidence is None or not isinstance(failure_evidence, dict):
            raise ReconciliationValidationError(
                f"{to_status} requires failure_evidence object.",
                code="REQUIRED_FAILURE_EVIDENCE",
            )
        if not failure_evidence:
            raise ReconciliationValidationError(
                f"{to_status} requires non-empty failure_evidence object.",
                code="EMPTY_FAILURE_EVIDENCE",
            )
    elif failure_evidence is not None:
        raise ReconciliationValidationError(
            f"failure_evidence is only allowed for blocked/failed (got {to_status!r}).",
            code="UNEXPECTED_FAILURE_EVIDENCE",
        )


__all__ = [
    "APPLY_STATUS_APPLIED",
    "APPLY_STATUS_BLOCKED",
    "APPLY_STATUS_FAILED",
    "APPLY_STATUS_PENDING",
    "APPLY_STATUS_SKIPPED_MANUAL",
    "assert_failure_evidence_for_terminal",
    "assert_valid_action",
    "assert_valid_apply_status",
    "assert_action_evidence_consistency",
    "assert_valid_batch_terminal_finalization",
    "assert_valid_create",
    "assert_valid_decision_evidence",
    "assert_valid_reason_code",
    "assert_valid_terminal_reason_code",
    "assert_valid_transition",
    "compute_intent_fingerprint",
    "is_terminal_apply_status",
]
