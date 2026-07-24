"""Section reconciliation plugin protocol (decide subset — WP-004 §4.2)."""
from __future__ import annotations

from typing import Mapping, Protocol, runtime_checkable

from sqlalchemy.engine import Connection

from app.personnel_intake.application.reconciliation.dto import (
    CanonicalRecordRef,
    MatchOutcome,
    ProposalRecordRef,
)


@runtime_checkable
class SectionReconciliationPlugin(Protocol):
    """Decide-phase section plugin; no PPR mutations."""

    section_code: str
    section_apply_mode: str
    policy_version: str
    matcher_rule_id: str
    matcher_version: str

    def build_proposal_refs(
        self,
        section_payload: Mapping[str, object],
        digest_algorithm_version: str,
    ) -> tuple[ProposalRecordRef, ...]:
        """Build proposal refs; leave payload_digest null."""

    def load_canonical_refs(
        self,
        conn: Connection,
        person_id: int,
        digest_algorithm_version: str,
    ) -> tuple[CanonicalRecordRef, ...]:
        """Load canonical refs; leave payload_digest null."""

    def match(
        self,
        proposal: ProposalRecordRef,
        canonicals: tuple[CanonicalRecordRef, ...],
    ) -> MatchOutcome:
        """Match one proposal against decide-time canonical snapshot."""

    def choose_exact_action(
        self,
        match: MatchOutcome,
        proposal: ProposalRecordRef,
        target: CanonicalRecordRef,
    ) -> str:
        """Return update_version or supersede for non-equal exact_one."""


__all__ = ["SectionReconciliationPlugin"]
