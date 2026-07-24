"""Domain invariant tests for WP-PPR-CARD-COORDINATION-003."""
from __future__ import annotations

import pytest

from app.personnel_intake.domain.reconciliation.actions import (
    APPLY_STATUS_APPLIED,
    APPLY_STATUS_BLOCKED,
    APPLY_STATUS_FAILED,
    APPLY_STATUS_PENDING,
    APPLY_STATUS_SKIPPED_MANUAL,
    RECONCILE_ACTION_ADD,
    RECONCILE_ACTION_KEEP_EXISTING,
    RECONCILE_ACTION_MANUAL_REVIEW,
    RECONCILE_ACTION_SUPERSEDE,
    RECONCILE_ACTION_UPDATE_VERSION,
    RECONCILE_ACTIONS,
    APPLY_STATUSES,
    EVIDENCE_SOURCE_INTAKE_RECONCILIATION,
)
from app.personnel_intake.domain.reconciliation.errors import ReconciliationValidationError
from app.personnel_intake.domain.reconciliation.invariants import (
    assert_failure_evidence_for_terminal,
    assert_valid_action,
    assert_valid_apply_status,
    assert_valid_batch_terminal_finalization,
    assert_valid_create,
    assert_valid_decision_evidence,
    assert_valid_transition,
    compute_intent_fingerprint,
)
from app.personnel_intake.domain.reconciliation.models import (
    BatchTerminalFinalizationCommand,
    BatchTerminalTransitionItem,
    CreatePendingDecisionCommand,
)


def _full_evidence(**overrides) -> dict:
    action = overrides.get("action", RECONCILE_ACTION_ADD)
    reason_code = overrides.get("reason_code", "MATCH_NONE_CONFIDENT")
    target_id = overrides.pop("target_canonical_record_id", None)

    if action == RECONCILE_ACTION_ADD:
        match_kind = "none"
        match_confidence = "high"
        semantically_equal = None
        matched = None
        candidates: list[int] = []
    elif action == RECONCILE_ACTION_KEEP_EXISTING:
        match_kind = "exact_one"
        match_confidence = "high"
        semantically_equal = True
        matched = target_id
        candidates = [target_id] if target_id is not None else []
    elif action == RECONCILE_ACTION_UPDATE_VERSION:
        match_kind = "exact_one"
        match_confidence = "high"
        semantically_equal = False
        matched = target_id
        candidates = [target_id] if target_id is not None else []
    elif action == RECONCILE_ACTION_SUPERSEDE:
        match_kind = "exact_one"
        match_confidence = "high"
        semantically_equal = False
        matched = target_id
        candidates = [target_id] if target_id is not None else []
    elif action == RECONCILE_ACTION_MANUAL_REVIEW:
        if reason_code == "MATCH_CONFIDENCE_LOW":
            match_kind = "none"
            match_confidence = "low"
            candidates = []
        elif reason_code == "MATCH_STALE_TARGET":
            match_kind = "stale_target"
            match_confidence = "high"
            candidates = []
        else:
            match_kind = "ambiguous"
            match_confidence = "high"
            candidates = [1, 2]
        semantically_equal = None
        matched = None
    else:
        match_kind = "none"
        match_confidence = "high"
        semantically_equal = None
        matched = None
        candidates = []

    base = {
        "source": EVIDENCE_SOURCE_INTAKE_RECONCILIATION,
        "application_id": 1,
        "section_code": "education",
        "proposal_index": 0,
        "proposal_fingerprint": "fp-edu",
        "proposal_payload_digest": "digest-a",
        "digest_algorithm_version": "canon-json-v1",
        "match_kind": match_kind,
        "match_confidence": match_confidence,
        "semantically_equal": semantically_equal,
        "matcher_rule_id": "EDU-FP-v1",
        "matcher_version": "1.0.0",
        "policy_version": "1.0.0",
        "candidate_canonical_record_ids": candidates,
        "matched_canonical_record_id": matched,
        "canonical_payload_digest_at_match": None,
        "expected_canonical_precondition": "none-match:set-v1",
        "action": action,
        "reason_code": reason_code,
        "decision_source": "system",
        "override_token": None,
        "before_snapshot_ref": None,
        "after_intent_digest": "after-digest-a",
        "correlation_id": None,
        "idempotency_key": "recon:1:education:0:add:digest-a",
    }
    base.update(overrides)
    return base


def _cmd(**overrides) -> CreatePendingDecisionCommand:
    idempotency_key = overrides.pop("idempotency_key", "recon:1:education:0:add:digest-a")
    action = overrides.get("action", RECONCILE_ACTION_ADD)
    reason_code = overrides.get("reason_code", "MATCH_NONE_CONFIDENT")
    if "evidence" in overrides:
        evidence = overrides.pop("evidence")
    else:
        evidence = _full_evidence(
            action=action,
            reason_code=reason_code,
            idempotency_key=idempotency_key,
            target_canonical_record_id=overrides.get("target_canonical_record_id"),
        )
    base = dict(
        application_id=1,
        person_id=2,
        section_code="education",
        proposal_index=0,
        proposal_fingerprint="fp-edu",
        proposal_payload_digest="digest-a",
        action=action,
        reason_code=reason_code,
        evidence=evidence,
        expected_canonical_precondition="none-match:set-v1",
        matcher_rule_id="EDU-FP-v1",
        matcher_version="1.0.0",
        policy_version="1.0.0",
        digest_algorithm_version="canon-json-v1",
        idempotency_key=idempotency_key,
        decision_source="system",
        override_token=None,
        target_canonical_record_id=None,
        expected_row_version=None,
    )
    base.update(overrides)
    return CreatePendingDecisionCommand(**base)


@pytest.mark.parametrize("action", RECONCILE_ACTIONS)
def test_all_actions_are_valid(action: str) -> None:
    assert_valid_action(action)


@pytest.mark.parametrize("status", APPLY_STATUSES)
def test_all_apply_statuses_are_valid(status: str) -> None:
    assert_valid_apply_status(status)


@pytest.mark.parametrize("forbidden", ["blocked", "replayed", "failed", "pending"])
def test_forbidden_actions_rejected(forbidden: str) -> None:
    with pytest.raises(ReconciliationValidationError, match="Forbidden reconcile action"):
        assert_valid_action(forbidden)


def test_replayed_apply_status_rejected() -> None:
    with pytest.raises(ReconciliationValidationError, match="Forbidden persisted apply_status"):
        assert_valid_apply_status("replayed")


@pytest.mark.parametrize(
    ("action", "to_status"),
    [
        (RECONCILE_ACTION_ADD, APPLY_STATUS_APPLIED),
        (RECONCILE_ACTION_KEEP_EXISTING, APPLY_STATUS_APPLIED),
        (RECONCILE_ACTION_UPDATE_VERSION, APPLY_STATUS_APPLIED),
        (RECONCILE_ACTION_SUPERSEDE, APPLY_STATUS_APPLIED),
        (RECONCILE_ACTION_MANUAL_REVIEW, APPLY_STATUS_SKIPPED_MANUAL),
        (RECONCILE_ACTION_ADD, APPLY_STATUS_BLOCKED),
        (RECONCILE_ACTION_ADD, APPLY_STATUS_FAILED),
        (RECONCILE_ACTION_MANUAL_REVIEW, APPLY_STATUS_BLOCKED),
        (RECONCILE_ACTION_KEEP_EXISTING, APPLY_STATUS_FAILED),
    ],
)
def test_allowed_transitions(action: str, to_status: str) -> None:
    assert_valid_transition(
        action=action,
        from_status=APPLY_STATUS_PENDING,
        to_status=to_status,
    )


@pytest.mark.parametrize(
    ("action", "from_status", "to_status"),
    [
        (RECONCILE_ACTION_ADD, APPLY_STATUS_APPLIED, APPLY_STATUS_PENDING),
        (RECONCILE_ACTION_ADD, APPLY_STATUS_BLOCKED, APPLY_STATUS_APPLIED),
        (RECONCILE_ACTION_ADD, APPLY_STATUS_FAILED, APPLY_STATUS_PENDING),
        (RECONCILE_ACTION_ADD, APPLY_STATUS_SKIPPED_MANUAL, APPLY_STATUS_APPLIED),
        (RECONCILE_ACTION_ADD, APPLY_STATUS_PENDING, APPLY_STATUS_SKIPPED_MANUAL),
        (RECONCILE_ACTION_MANUAL_REVIEW, APPLY_STATUS_PENDING, APPLY_STATUS_APPLIED),
        (RECONCILE_ACTION_ADD, APPLY_STATUS_PENDING, "replayed"),
    ],
)
def test_forbidden_transitions(action: str, from_status: str, to_status: str) -> None:
    with pytest.raises(ReconciliationValidationError):
        assert_valid_transition(
            action=action,
            from_status=from_status,
            to_status=to_status,
        )


def test_create_add_ok() -> None:
    fp = assert_valid_create(_cmd())
    assert len(fp) == 64


def test_incomplete_evidence_rejected() -> None:
    with pytest.raises(ReconciliationValidationError, match="missing required fields"):
        assert_valid_create(_cmd(evidence={"source": EVIDENCE_SOURCE_INTAKE_RECONCILIATION}))


def test_evidence_command_mismatch_rejected() -> None:
    cmd = _cmd()
    bad_evidence = dict(cmd.evidence)
    bad_evidence["application_id"] = 999
    with pytest.raises(ReconciliationValidationError, match="evidence.application_id"):
        assert_valid_decision_evidence(bad_evidence, cmd)


def test_empty_batch_rejected() -> None:
    with pytest.raises(ReconciliationValidationError, match="at least one transition"):
        assert_valid_batch_terminal_finalization(BatchTerminalFinalizationCommand(transitions=()))


def test_duplicate_batch_ids_rejected() -> None:
    item = BatchTerminalTransitionItem(
        decision_id=1,
        expected_row_version=1,
        to_status=APPLY_STATUS_APPLIED,
    )
    with pytest.raises(ReconciliationValidationError, match="unique decision_id"):
        assert_valid_batch_terminal_finalization(
            BatchTerminalFinalizationCommand(transitions=(item, item))
        )


def test_empty_failure_evidence_rejected() -> None:
    with pytest.raises(ReconciliationValidationError, match="non-empty failure_evidence"):
        assert_failure_evidence_for_terminal(
            to_status=APPLY_STATUS_BLOCKED,
            failure_evidence={},
        )


def test_create_keep_requires_target() -> None:
    with pytest.raises(ReconciliationValidationError, match="target_canonical_record_id"):
        assert_valid_create(
            _cmd(
                action=RECONCILE_ACTION_KEEP_EXISTING,
                reason_code="MATCH_EXACT_KEEP",
                target_canonical_record_id=None,
            )
        )


def test_create_update_requires_expected_row_version() -> None:
    with pytest.raises(ReconciliationValidationError, match="expected_row_version"):
        assert_valid_create(
            _cmd(
                action=RECONCILE_ACTION_UPDATE_VERSION,
                reason_code="MATCH_EXACT_UPDATE",
                target_canonical_record_id=10,
                expected_row_version=None,
            )
        )


def test_ambiguous_add_rejected() -> None:
    with pytest.raises(ReconciliationValidationError, match="manual_review"):
        assert_valid_create(
            _cmd(
                evidence=_full_evidence(
                    action=RECONCILE_ACTION_ADD,
                    reason_code="MATCH_NONE_CONFIDENT",
                    match_kind="ambiguous",
                    match_confidence="high",
                    candidate_canonical_record_ids=[1, 2],
                ),
            )
        )


def test_low_confidence_add_rejected() -> None:
    with pytest.raises(ReconciliationValidationError, match="manual_review"):
        assert_valid_create(
            _cmd(
                evidence=_full_evidence(
                    action=RECONCILE_ACTION_ADD,
                    reason_code="MATCH_NONE_CONFIDENT",
                    match_kind="none",
                    match_confidence="low",
                ),
            )
        )


def test_matched_target_mismatch_rejected() -> None:
    with pytest.raises(ReconciliationValidationError, match="matched_canonical_record_id"):
        assert_valid_create(
            _cmd(
                action=RECONCILE_ACTION_KEEP_EXISTING,
                reason_code="MATCH_EXACT_KEEP",
                target_canonical_record_id=10,
                evidence=_full_evidence(
                    action=RECONCILE_ACTION_KEEP_EXISTING,
                    reason_code="MATCH_EXACT_KEEP",
                    target_canonical_record_id=10,
                    matched_canonical_record_id=99,
                ),
            )
        )


def test_hr_requires_override_token() -> None:
    with pytest.raises(ReconciliationValidationError, match="override_token"):
        assert_valid_create(
            _cmd(
                decision_source="hr",
                override_token=None,
                evidence=_full_evidence(decision_source="hr", override_token=None),
            )
        )


def test_intent_fingerprint_stable_and_sensitive() -> None:
    evidence = _full_evidence()
    a = compute_intent_fingerprint(
        application_id=1,
        person_id=2,
        section_code="education",
        proposal_index=0,
        proposal_fingerprint="fp",
        proposal_payload_digest="d1",
        action="add",
        reason_code="MATCH_NONE_CONFIDENT",
        evidence=evidence,
        target_canonical_record_id=None,
        expected_row_version=None,
        expected_canonical_precondition="none",
        decision_source="system",
        override_token=None,
        matcher_rule_id="r",
        matcher_version="1",
        policy_version="1",
        digest_algorithm_version="canon-json-v1",
        idempotency_key="k",
    )
    b = compute_intent_fingerprint(
        application_id=1,
        person_id=2,
        section_code="education",
        proposal_index=0,
        proposal_fingerprint="fp",
        proposal_payload_digest="d1",
        action="add",
        reason_code="MATCH_NONE_CONFIDENT",
        evidence=evidence,
        target_canonical_record_id=None,
        expected_row_version=None,
        expected_canonical_precondition="none",
        decision_source="system",
        override_token=None,
        matcher_rule_id="r",
        matcher_version="1",
        policy_version="1",
        digest_algorithm_version="canon-json-v1",
        idempotency_key="k",
    )
    c = compute_intent_fingerprint(
        application_id=1,
        person_id=2,
        section_code="education",
        proposal_index=0,
        proposal_fingerprint="fp",
        proposal_payload_digest="d2",
        action="add",
        reason_code="MATCH_NONE_CONFIDENT",
        evidence=evidence,
        target_canonical_record_id=None,
        expected_row_version=None,
        expected_canonical_precondition="none",
        decision_source="system",
        override_token=None,
        matcher_rule_id="r",
        matcher_version="1",
        policy_version="1",
        digest_algorithm_version="canon-json-v1",
        idempotency_key="k",
    )
    assert a == b
    assert a != c
