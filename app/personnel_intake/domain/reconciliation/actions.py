"""Reconcile action / apply status constants (WP-PPR-CARD-COORDINATION-002 rev.3)."""
from __future__ import annotations

RECONCILE_ACTION_ADD = "add"
RECONCILE_ACTION_KEEP_EXISTING = "keep_existing"
RECONCILE_ACTION_UPDATE_VERSION = "update_version"
RECONCILE_ACTION_SUPERSEDE = "supersede"
RECONCILE_ACTION_MANUAL_REVIEW = "manual_review"

RECONCILE_ACTIONS: tuple[str, ...] = (
    RECONCILE_ACTION_ADD,
    RECONCILE_ACTION_KEEP_EXISTING,
    RECONCILE_ACTION_UPDATE_VERSION,
    RECONCILE_ACTION_SUPERSEDE,
    RECONCILE_ACTION_MANUAL_REVIEW,
)

# Forbidden as ReconcileAction (ApplyStatus only).
FORBIDDEN_ACTIONS: frozenset[str] = frozenset({"blocked", "replayed", "failed", "pending", "applied"})

APPLY_STATUS_PENDING = "pending"
APPLY_STATUS_APPLIED = "applied"
APPLY_STATUS_SKIPPED_MANUAL = "skipped_manual"
APPLY_STATUS_BLOCKED = "blocked"
APPLY_STATUS_FAILED = "failed"

APPLY_STATUSES: tuple[str, ...] = (
    APPLY_STATUS_PENDING,
    APPLY_STATUS_APPLIED,
    APPLY_STATUS_SKIPPED_MANUAL,
    APPLY_STATUS_BLOCKED,
    APPLY_STATUS_FAILED,
)

# Forbidden as persisted ApplyStatus.
FORBIDDEN_APPLY_STATUSES: frozenset[str] = frozenset({"replayed"})

TERMINAL_APPLY_STATUSES: frozenset[str] = frozenset(
    {
        APPLY_STATUS_APPLIED,
        APPLY_STATUS_SKIPPED_MANUAL,
        APPLY_STATUS_BLOCKED,
        APPLY_STATUS_FAILED,
    }
)

DECISION_SOURCE_SYSTEM = "system"
DECISION_SOURCE_HR = "hr"
DECISION_SOURCES: tuple[str, ...] = (
    DECISION_SOURCE_SYSTEM,
    DECISION_SOURCE_HR,
)

SECTION_CODE_EDUCATION = "education"
SECTION_CODE_TRAINING = "training"
SECTION_CODE_EMPLOYMENT_BIOGRAPHY = "employment_biography"
SECTION_CODE_MILITARY = "military"

SECTION_CODES: tuple[str, ...] = (
    SECTION_CODE_EDUCATION,
    SECTION_CODE_TRAINING,
    SECTION_CODE_EMPLOYMENT_BIOGRAPHY,
    SECTION_CODE_MILITARY,
)

MATCH_KIND_NONE = "none"
MATCH_KIND_EXACT_ONE = "exact_one"
MATCH_KIND_AMBIGUOUS = "ambiguous"
MATCH_KIND_STALE_TARGET = "stale_target"

MATCH_KINDS: tuple[str, ...] = (
    MATCH_KIND_NONE,
    MATCH_KIND_EXACT_ONE,
    MATCH_KIND_AMBIGUOUS,
    MATCH_KIND_STALE_TARGET,
)

MATCH_CONFIDENCE_HIGH = "high"
MATCH_CONFIDENCE_LOW = "low"

MATCH_CONFIDENCES: tuple[str, ...] = (
    MATCH_CONFIDENCE_HIGH,
    MATCH_CONFIDENCE_LOW,
)

REASON_MATCH_NONE_CONFIDENT = "MATCH_NONE_CONFIDENT"
REASON_MATCH_EXACT_KEEP = "MATCH_EXACT_KEEP"
REASON_MATCH_EXACT_UPDATE = "MATCH_EXACT_UPDATE"
REASON_MATCH_EXACT_SUPERSEDE = "MATCH_EXACT_SUPERSEDE"
REASON_MATCH_AMBIGUOUS = "MATCH_AMBIGUOUS"
REASON_MATCH_CONFIDENCE_LOW = "MATCH_CONFIDENCE_LOW"
REASON_MATCH_STALE_TARGET = "MATCH_STALE_TARGET"
REASON_MATCH_FORBIDDEN_BLIND_APPEND = "MATCH_FORBIDDEN_BLIND_APPEND"
REASON_HR_Q3_NO_AUTO_MERGE = "HR_Q3_NO_AUTO_MERGE"
REASON_SECTION_ATOMICITY_HOLD = "SECTION_ATOMICITY_HOLD"
REASON_APPLY_STALE_ROW_VERSION = "APPLY_STALE_ROW_VERSION"
REASON_APPLY_NO_MATCH_LOST = "APPLY_NO_MATCH_LOST"
REASON_APPLY_CONCURRENCY_PRECONDITION = "APPLY_CONCURRENCY_PRECONDITION"
REASON_IDEMPOTENT_REPLAY = "IDEMPOTENT_REPLAY"

EVIDENCE_SOURCE_INTAKE_RECONCILIATION = "intake_reconciliation"

# Contract WP-PPR-CARD-COORDINATION-002 rev.3 §6.1 — all keys required (values may be null).
DECISION_EVIDENCE_REQUIRED_FIELDS: tuple[str, ...] = (
    "source",
    "application_id",
    "section_code",
    "proposal_index",
    "proposal_fingerprint",
    "proposal_payload_digest",
    "digest_algorithm_version",
    "match_kind",
    "match_confidence",
    "semantically_equal",
    "matcher_rule_id",
    "matcher_version",
    "policy_version",
    "candidate_canonical_record_ids",
    "matched_canonical_record_id",
    "canonical_payload_digest_at_match",
    "expected_canonical_precondition",
    "action",
    "reason_code",
    "decision_source",
    "override_token",
    "before_snapshot_ref",
    "after_intent_digest",
    "correlation_id",
    "idempotency_key",
)

REASON_CODES: tuple[str, ...] = (
    REASON_MATCH_NONE_CONFIDENT,
    REASON_MATCH_EXACT_KEEP,
    REASON_MATCH_EXACT_UPDATE,
    REASON_MATCH_EXACT_SUPERSEDE,
    REASON_MATCH_AMBIGUOUS,
    REASON_MATCH_CONFIDENCE_LOW,
    REASON_MATCH_STALE_TARGET,
    REASON_MATCH_FORBIDDEN_BLIND_APPEND,
    REASON_HR_Q3_NO_AUTO_MERGE,
    REASON_SECTION_ATOMICITY_HOLD,
    REASON_APPLY_STALE_ROW_VERSION,
    REASON_APPLY_NO_MATCH_LOST,
    REASON_APPLY_CONCURRENCY_PRECONDITION,
    REASON_IDEMPOTENT_REPLAY,
)

# pending → terminal only (002 §4.4.1).
ALLOWED_APPLY_TRANSITIONS: dict[str, frozenset[str]] = {
    APPLY_STATUS_PENDING: frozenset(
        {
            APPLY_STATUS_APPLIED,
            APPLY_STATUS_SKIPPED_MANUAL,
            APPLY_STATUS_BLOCKED,
            APPLY_STATUS_FAILED,
        }
    ),
}
