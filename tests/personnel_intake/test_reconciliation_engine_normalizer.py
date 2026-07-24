"""Unit tests for DecisionNormalizer, idempotency key, and add precondition."""
from __future__ import annotations

from dataclasses import replace

import pytest

from app.personnel_intake.application.reconciliation.dto import MatchOutcome
from app.personnel_intake.application.reconciliation.idempotency import (
    IDEMPOTENCY_KEY_PREFIX,
    build_idempotency_key,
)
from app.personnel_intake.application.reconciliation.normalizer import normalize_match_outcome
from app.personnel_intake.application.reconciliation.precondition import build_add_precondition
from app.personnel_intake.domain.reconciliation.actions import (
    REASON_MATCH_AMBIGUOUS,
    REASON_MATCH_CONFIDENCE_LOW,
    REASON_MATCH_EXACT_KEEP,
    REASON_MATCH_NONE_CONFIDENT,
    REASON_MATCH_STALE_TARGET,
    RECONCILE_ACTION_ADD,
    RECONCILE_ACTION_KEEP_EXISTING,
    RECONCILE_ACTION_MANUAL_REVIEW,
)
from app.personnel_intake.domain.reconciliation.digest import CanonJsonV1DigestBuilder
from app.personnel_intake.domain.reconciliation.errors import ReconciliationValidationError
from tests.personnel_intake.recon_engine_fakes import canonical


def test_normalizer_matrix() -> None:
    cases = [
        (
            MatchOutcome(match_kind="none", match_confidence="low"),
            RECONCILE_ACTION_MANUAL_REVIEW,
            REASON_MATCH_CONFIDENCE_LOW,
            False,
        ),
        (
            MatchOutcome(
                match_kind="ambiguous",
                match_confidence="high",
                candidate_canonical_record_ids=(1, 2),
            ),
            RECONCILE_ACTION_MANUAL_REVIEW,
            REASON_MATCH_AMBIGUOUS,
            False,
        ),
        (
            MatchOutcome(match_kind="stale_target", match_confidence="high"),
            RECONCILE_ACTION_MANUAL_REVIEW,
            REASON_MATCH_STALE_TARGET,
            False,
        ),
        (
            MatchOutcome(match_kind="none", match_confidence="high"),
            RECONCILE_ACTION_ADD,
            REASON_MATCH_NONE_CONFIDENT,
            False,
        ),
        (
            MatchOutcome(
                match_kind="exact_one",
                match_confidence="high",
                matched_canonical_record_id=1,
                semantically_equal=True,
            ),
            RECONCILE_ACTION_KEEP_EXISTING,
            REASON_MATCH_EXACT_KEEP,
            False,
        ),
    ]
    for match, action, reason, needs in cases:
        result = normalize_match_outcome(match, section_code="education")
        assert result.action == action
        assert result.reason_code == reason
        assert result.needs_choose_exact_action is needs

    exact_update = normalize_match_outcome(
        MatchOutcome(
            match_kind="exact_one",
            match_confidence="high",
            matched_canonical_record_id=1,
            semantically_equal=False,
        ),
        section_code="education",
    )
    assert exact_update.needs_choose_exact_action is True
    assert exact_update.action is None


def test_normalizer_exact_one_high_requires_semantically_equal_bool() -> None:
    with pytest.raises(ReconciliationValidationError) as exc:
        normalize_match_outcome(
            MatchOutcome(
                match_kind="exact_one",
                match_confidence="high",
                matched_canonical_record_id=1,
                semantically_equal=None,
            ),
            section_code="education",
        )
    assert exc.value.code == "INVALID_MATCH_OUTCOME"


def test_add_precondition_ignores_inactive_canonicals() -> None:
    builder = CanonJsonV1DigestBuilder()
    active_a = replace(
        canonical(1, content={"a": 1}, lifecycle_status="active"),
        payload_digest=builder.payload_digest({"a": 1}),
    )
    active_b = replace(
        canonical(2, content={"b": 2}, lifecycle_status="active"),
        payload_digest=builder.payload_digest({"b": 2}),
    )
    superseded = replace(
        canonical(3, content={"c": 3}, lifecycle_status="superseded"),
        payload_digest=builder.payload_digest({"c": 3}),
    )
    voided = replace(
        canonical(4, content={"d": 4}, lifecycle_status="voided"),
        payload_digest=builder.payload_digest({"d": 4}),
    )

    active_only = build_add_precondition(
        digest_builder=builder,
        canonicals=(active_a, active_b),
    )
    with_inactive = build_add_precondition(
        digest_builder=builder,
        canonicals=(active_a, superseded, active_b, voided),
    )
    assert active_only == with_inactive

    changed_active = build_add_precondition(
        digest_builder=builder,
        canonicals=(active_a,),
    )
    assert changed_active != active_only


def test_idempotency_key_prefix_and_stability() -> None:
    builder = CanonJsonV1DigestBuilder()
    kwargs = dict(
        digest_builder=builder,
        application_id=10,
        section_code="education",
        proposal_index=0,
        action="add",
        digest_algorithm_version="canon-json-v1",
        proposal_payload_digest="a" * 64,
        target_canonical_record_id=None,
        expected_canonical_precondition="none-match:x",
        decision_source="system",
        override_token=None,
        matcher_rule_id="R1",
        matcher_version="1.0.0",
        policy_version="1.0.0",
    )
    key1 = build_idempotency_key(**kwargs)
    key2 = build_idempotency_key(**kwargs)
    assert key1 == key2
    assert key1.startswith(IDEMPOTENCY_KEY_PREFIX)
    assert len(key1) == len(IDEMPOTENCY_KEY_PREFIX) + 64
