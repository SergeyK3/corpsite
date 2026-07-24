"""Reconciliation Decision Engine application layer (WP-004 / WP-005)."""
from __future__ import annotations

from app.personnel_intake.application.reconciliation.dto import (
    CanonicalRecordRef,
    DecideDecisionOutcome,
    DecideSectionCommand,
    DecideSectionResult,
    DecideSectionSummary,
    MatchOutcome,
    ProposalRecordRef,
)
from app.personnel_intake.application.reconciliation.engine import (
    SECTION_APPLY_MODE_ALL_OR_NOTHING,
    SECTION_APPLY_MODE_PER_RECORD,
    ReconciliationDecisionEngine,
)
from app.personnel_intake.application.reconciliation.idempotency import build_idempotency_key
from app.personnel_intake.application.reconciliation.normalizer import (
    NormalizeMatchResult,
    normalize_match_outcome,
)
from app.personnel_intake.application.reconciliation.plugin import SectionReconciliationPlugin
from app.personnel_intake.application.reconciliation.plugins import (
    EducationReconciliationPlugin,
    register_default_section_plugins,
    register_education_plugin,
)
from app.personnel_intake.application.reconciliation.registry import SectionReconciliationRegistry

__all__ = [
    "CanonicalRecordRef",
    "DecideDecisionOutcome",
    "DecideSectionCommand",
    "DecideSectionResult",
    "DecideSectionSummary",
    "EducationReconciliationPlugin",
    "MatchOutcome",
    "NormalizeMatchResult",
    "ProposalRecordRef",
    "ReconciliationDecisionEngine",
    "SECTION_APPLY_MODE_ALL_OR_NOTHING",
    "SECTION_APPLY_MODE_PER_RECORD",
    "SectionReconciliationPlugin",
    "SectionReconciliationRegistry",
    "build_idempotency_key",
    "normalize_match_outcome",
    "register_default_section_plugins",
    "register_education_plugin",
]
