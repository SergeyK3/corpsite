"""Focused contract tests for Stage 0 safe snapshot mechanics."""
from __future__ import annotations

from app.api.ppr_stage0_cohort_schemas import Stage0BlockerOut, Stage0ParticipantOut
from app.services.ppr_stage0_cohort_service import (
    ALLOWED_BATCH_STATUSES,
    BLOCKED_SOURCE_DELETION_OR_REBINDING,
    ELIGIBLE,
    _hash,
    _safe_candidate_key,
)


def test_stage0_fingerprint_is_deterministic_and_order_sensitive() -> None:
    assert _hash({"b": 2, "a": 1}) == _hash({"a": 1, "b": 2})
    assert _hash([{"employee_id": 1}, {"employee_id": 2}]) != _hash(
        [{"employee_id": 2}, {"employee_id": 1}]
    )


def test_stage0_safe_candidate_key_is_technical_only() -> None:
    key = _safe_candidate_key(41, 99)
    assert len(key) == 64
    assert key != _safe_candidate_key(41, 100)
    assert key == _safe_candidate_key(41, 99)


def test_stage0_batch_policy_and_categories_are_fail_closed() -> None:
    assert ALLOWED_BATCH_STATUSES == {"APPLY_PENDING", "APPLIED", "PARTIALLY_APPLIED"}
    assert ELIGIBLE == "ELIGIBLE"
    assert BLOCKED_SOURCE_DELETION_OR_REBINDING.startswith("BLOCKED_")


def test_safe_api_contracts_do_not_expose_iin_or_name_fields() -> None:
    fields = set(Stage0ParticipantOut.model_fields) | set(Stage0BlockerOut.model_fields)
    assert not fields.intersection({"iin", "full_iin", "full_name", "first_name", "last_name", "raw_payload"})
