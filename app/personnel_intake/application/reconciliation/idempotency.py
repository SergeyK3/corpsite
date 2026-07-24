"""Idempotency key builder — recon:v1:<sha256> (WP-004 §3.3.3 / §8.2)."""
from __future__ import annotations

from app.personnel_intake.domain.reconciliation.digest import DigestBuilder

IDEMPOTENCY_KEY_PREFIX = "recon:v1:"


def build_idempotency_key(
    *,
    digest_builder: DigestBuilder,
    application_id: int,
    section_code: str,
    proposal_index: int,
    action: str,
    digest_algorithm_version: str,
    proposal_payload_digest: str,
    target_canonical_record_id: int | None,
    expected_canonical_precondition: str,
    decision_source: str,
    override_token: str | None,
    matcher_rule_id: str,
    matcher_version: str,
    policy_version: str,
) -> str:
    """Build durable idempotency key from fixed 14-element intent_material."""
    intent_material = [
        "recon",
        int(application_id),
        str(section_code),
        int(proposal_index),
        str(action),
        str(digest_algorithm_version),
        str(proposal_payload_digest),
        target_canonical_record_id,
        str(expected_canonical_precondition),
        str(decision_source),
        override_token,
        str(matcher_rule_id),
        str(matcher_version),
        str(policy_version),
    ]
    return IDEMPOTENCY_KEY_PREFIX + digest_builder.payload_digest(intent_material)


__all__ = ["IDEMPOTENCY_KEY_PREFIX", "build_idempotency_key"]
