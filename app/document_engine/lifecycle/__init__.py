"""Shared activation and lifecycle runtime (UDE-011).

Read-only lifecycle orchestration — no write path, no persistence.
"""
from __future__ import annotations

from app.document_engine.lifecycle.activation_service import ActivationService
from app.document_engine.lifecycle.compatibility import (
    LifecycleCompatibilityDifference,
    LifecycleCompatibilityReport,
    build_lifecycle_compatibility_report,
    compare_snapshots_to_lifecycle,
    format_lifecycle_compatibility_report,
)
from app.document_engine.lifecycle.facade import (
    DocumentEngineLifecycleFacade,
    DocumentEngineLifecycleSnapshot,
)
from app.document_engine.lifecycle.lifecycle_models import (
    ActivationDecision,
    LifecycleDecision,
    LifecycleEvaluation,
    LifecycleGate,
    LifecycleTransition,
    LifecycleViolation,
    PromotionReadiness,
    RegistrationReadiness,
    SignedSnapshotDescriptor,
)
from app.document_engine.lifecycle.lifecycle_rules import LifecycleRules
from app.document_engine.lifecycle.lifecycle_service import LifecycleEvaluationService
from app.document_engine.lifecycle.promotion_policy import PromotionPolicy
from app.document_engine.lifecycle.readiness_policy import ReadinessPolicy
from app.document_engine.lifecycle.registration_policy import RegistrationPolicy

__all__ = [
    "ActivationDecision",
    "ActivationService",
    "DocumentEngineLifecycleFacade",
    "DocumentEngineLifecycleSnapshot",
    "LifecycleCompatibilityDifference",
    "LifecycleCompatibilityReport",
    "LifecycleDecision",
    "LifecycleEvaluation",
    "LifecycleEvaluationService",
    "LifecycleGate",
    "LifecycleRules",
    "LifecycleTransition",
    "LifecycleViolation",
    "PromotionPolicy",
    "PromotionReadiness",
    "ReadinessPolicy",
    "RegistrationPolicy",
    "RegistrationReadiness",
    "SignedSnapshotDescriptor",
    "build_lifecycle_compatibility_report",
    "compare_snapshots_to_lifecycle",
    "format_lifecycle_compatibility_report",
]
