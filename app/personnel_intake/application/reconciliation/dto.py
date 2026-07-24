"""Engine input/output DTOs (WP-PPR-CARD-COORDINATION-004)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from app.personnel_intake.domain.reconciliation.models import ReconcileDecisionRecord


@dataclass(frozen=True, slots=True)
class DecideSectionCommand:
    """U1 Decide input for one accepted collection section."""

    application_id: int
    person_id: int
    section_code: str
    section_payload: Mapping[str, Any]
    decision_source: str = "system"
    override_token: str | None = None
    correlation_id: str | None = None
    digest_algorithm_version: str = "canon-json-v1"
    policy_version_override: str | None = None


@dataclass(frozen=True, slots=True)
class ProposalRecordRef:
    """Plugin-built proposal reference (digest filled by engine)."""

    proposal_index: int
    proposal_fingerprint: str
    normalized_content: Mapping[str, Any]
    raw_payload: Mapping[str, Any]
    claimed_payload_digest: str | None = None
    payload_digest: str | None = None


@dataclass(frozen=True, slots=True)
class CanonicalRecordRef:
    """Plugin-loaded canonical reference (digest filled by engine)."""

    record_id: int
    lifecycle_status: str
    row_version: str
    record_fingerprint: str
    normalized_content: Mapping[str, Any]
    claimed_payload_digest: str | None = None
    payload_digest: str | None = None


@dataclass(frozen=True, slots=True)
class MatchOutcome:
    """Plugin match result (002 §4.2 / WP-004 §5.3)."""

    match_kind: str
    match_confidence: str
    matched_canonical_record_id: int | None = None
    candidate_canonical_record_ids: tuple[int, ...] = ()
    semantically_equal: bool | None = None
    detail: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DecideDecisionOutcome:
    """One persisted decision outcome from decide_section."""

    decision: ReconcileDecisionRecord
    idempotent_replay: bool
    proposal_index: int
    action: str
    reason_code: str


@dataclass(frozen=True, slots=True)
class DecideSectionSummary:
    """Action / apply_status counts for a decide_section call."""

    add: int
    update_version: int
    supersede: int
    keep_existing: int
    manual_review: int
    pending: int
    applied: int
    skipped_manual: int


@dataclass(frozen=True, slots=True)
class DecideSectionResult:
    """U1 Decide output for one section."""

    application_id: int
    person_id: int
    section_code: str
    section_apply_mode: str
    correlation_id: str | None
    digest_algorithm_version: str
    policy_version: str
    decision_ids: tuple[int, ...]
    decisions: tuple[DecideDecisionOutcome, ...]
    summary: DecideSectionSummary
    batch_idempotent_replay: bool
    result_status: str


__all__ = [
    "CanonicalRecordRef",
    "DecideDecisionOutcome",
    "DecideSectionCommand",
    "DecideSectionResult",
    "DecideSectionSummary",
    "MatchOutcome",
    "ProposalRecordRef",
]
