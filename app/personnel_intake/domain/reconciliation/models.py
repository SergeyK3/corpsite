"""Domain models for reconciliation decisions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class CreatePendingDecisionCommand:
    """Create a pending reconciliation decision (no PPR mutation)."""

    application_id: int
    person_id: int
    section_code: str
    proposal_index: int
    proposal_fingerprint: str
    proposal_payload_digest: str
    action: str
    reason_code: str
    evidence: dict[str, Any]
    expected_canonical_precondition: str
    matcher_rule_id: str
    matcher_version: str
    policy_version: str
    digest_algorithm_version: str
    idempotency_key: str
    decision_source: str = "system"
    override_token: str | None = None
    target_canonical_record_id: int | None = None
    expected_row_version: str | None = None
    intent_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class TerminalTransitionCommand:
    """Atomic pending → terminal apply_status transition."""

    decision_id: int
    expected_row_version: int
    to_status: str
    failure_evidence: dict[str, Any] | None = None
    reason_code: str | None = None


@dataclass(frozen=True, slots=True)
class BatchTerminalTransitionItem:
    """One decision within an atomic batch terminal finalization."""

    decision_id: int
    expected_row_version: int
    to_status: str
    failure_evidence: dict[str, Any] | None = None
    reason_code: str | None = None


@dataclass(frozen=True, slots=True)
class BatchTerminalFinalizationCommand:
    """Atomic terminal finalization for an explicit non-empty decision batch."""

    transitions: tuple[BatchTerminalTransitionItem, ...]


@dataclass(frozen=True, slots=True)
class BatchTerminalFinalizationResult:
    """All decisions in the batch after successful terminal finalization."""

    decisions: tuple[ReconcileDecisionRecord, ...]


@dataclass(frozen=True, slots=True)
class ReconcileDecisionRecord:
    """Persisted reconciliation decision snapshot."""

    decision_id: int
    application_id: int
    person_id: int
    section_code: str
    proposal_index: int
    proposal_fingerprint: str
    proposal_payload_digest: str
    action: str
    reason_code: str
    evidence: dict[str, Any]
    target_canonical_record_id: int | None
    expected_row_version: str | None
    expected_canonical_precondition: str
    decision_source: str
    override_token: str | None
    matcher_rule_id: str
    matcher_version: str
    policy_version: str
    digest_algorithm_version: str
    idempotency_key: str
    intent_fingerprint: str
    apply_status: str
    failure_evidence: dict[str, Any] | None
    row_version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CreatePendingDecisionResult:
    decision: ReconcileDecisionRecord
    idempotent_replay: bool
