"""Fake section plugins for WP-005 reconciliation engine tests."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from sqlalchemy.engine import Connection

from app.personnel_intake.application.reconciliation.dto import (
    CanonicalRecordRef,
    MatchOutcome,
    ProposalRecordRef,
)


MatchFn = Callable[
    [ProposalRecordRef, tuple[CanonicalRecordRef, ...]],
    MatchOutcome,
]


@dataclass
class FakeSectionPlugin:
    """Configurable decide-phase plugin (no real section logic)."""

    section_code: str = "education"
    section_apply_mode: str = "per_record"
    policy_version: str = "1.0.0"
    matcher_rule_id: str = "FAKE-RULE-v1"
    matcher_version: str = "1.0.0"
    proposals: list[ProposalRecordRef] = field(default_factory=list)
    canonicals: list[CanonicalRecordRef] = field(default_factory=list)
    match_by_index: dict[int, MatchOutcome] = field(default_factory=dict)
    default_match: MatchOutcome | None = None
    exact_action: str = "update_version"
    match_hook: MatchFn | None = None
    fail_on_match_index: int | None = None
    raise_on_match: Exception | None = None

    def build_proposal_refs(
        self,
        section_payload: Mapping[str, object],
        digest_algorithm_version: str,
    ) -> tuple[ProposalRecordRef, ...]:
        del section_payload, digest_algorithm_version
        return tuple(self.proposals)

    def load_canonical_refs(
        self,
        conn: Connection,
        person_id: int,
        digest_algorithm_version: str,
    ) -> tuple[CanonicalRecordRef, ...]:
        del conn, person_id, digest_algorithm_version
        return tuple(self.canonicals)

    def match(
        self,
        proposal: ProposalRecordRef,
        canonicals: tuple[CanonicalRecordRef, ...],
    ) -> MatchOutcome:
        if self.raise_on_match is not None:
            raise self.raise_on_match
        if (
            self.fail_on_match_index is not None
            and int(proposal.proposal_index) == int(self.fail_on_match_index)
        ):
            raise RuntimeError(f"injected failure at proposal_index={proposal.proposal_index}")
        if self.match_hook is not None:
            return self.match_hook(proposal, canonicals)
        if proposal.proposal_index in self.match_by_index:
            return self.match_by_index[proposal.proposal_index]
        if self.default_match is not None:
            return self.default_match
        return MatchOutcome(match_kind="none", match_confidence="high")

    def choose_exact_action(
        self,
        match: MatchOutcome,
        proposal: ProposalRecordRef,
        target: CanonicalRecordRef,
    ) -> str:
        del match, proposal, target
        return self.exact_action


def proposal(
    index: int,
    *,
    content: dict[str, Any] | None = None,
    fingerprint: str | None = None,
    claimed_payload_digest: str | None = None,
    raw: dict[str, Any] | None = None,
) -> ProposalRecordRef:
    body = content if content is not None else {"title": f"item-{index}"}
    return ProposalRecordRef(
        proposal_index=index,
        proposal_fingerprint=fingerprint or f"fp-{index}",
        normalized_content=body,
        raw_payload=raw if raw is not None else dict(body),
        claimed_payload_digest=claimed_payload_digest,
    )


def canonical(
    record_id: int,
    *,
    content: dict[str, Any] | None = None,
    row_version: str = "1",
    fingerprint: str | None = None,
    claimed_payload_digest: str | None = None,
    lifecycle_status: str = "active",
) -> CanonicalRecordRef:
    body = content if content is not None else {"title": f"canon-{record_id}"}
    return CanonicalRecordRef(
        record_id=record_id,
        lifecycle_status=lifecycle_status,
        row_version=row_version,
        record_fingerprint=fingerprint or f"cfp-{record_id}",
        normalized_content=body,
        claimed_payload_digest=claimed_payload_digest,
    )
