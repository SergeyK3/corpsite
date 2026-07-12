"""Shared activation and lifecycle runtime models (UDE-011).

Immutable runtime models — not ORM, not API DTOs, not persistence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Tuple

from app.document_engine.contracts.validation import ValidationResult
from app.document_engine.read_models.lifecycle import LifecycleReadModel
from app.document_engine.value_objects.lifecycle import (
    ArchiveState,
    DocumentLifecycleState,
    VoidKind,
)


class LifecycleGate(str, Enum):
    """Lifecycle evaluation gate — computation only, no commands."""

    ACTIVATION = "ACTIVATION"
    PROMOTION = "PROMOTION"
    MARK_READY = "MARK_READY"
    SIGN = "SIGN"
    REGISTER = "REGISTER"
    CANCEL = "CANCEL"
    ANNUL = "ANNUL"
    ARCHIVE = "ARCHIVE"
    RETURN_TO_DRAFT = "RETURN_TO_DRAFT"


@dataclass(frozen=True, slots=True)
class LifecycleViolation:
    """Blocking or informational lifecycle finding."""

    code: str
    message: str
    gate: LifecycleGate | None = None
    field_path: str | None = None


@dataclass(frozen=True, slots=True)
class LifecycleTransition:
    """Allowed or blocked lifecycle transition evaluation."""

    from_state: DocumentLifecycleState
    to_state: DocumentLifecycleState
    gate: LifecycleGate
    allowed: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class PromotionReadiness:
    """Whether OfficialDraftSnapshot may be promoted — no Document created."""

    is_ready: bool
    blockers: Tuple[LifecycleViolation, ...] = field(default_factory=tuple)
    validation: ValidationResult = field(default_factory=ValidationResult)


@dataclass(frozen=True, slots=True)
class RegistrationReadiness:
    """Whether document may be registered — no number assigned."""

    is_ready: bool
    blockers: Tuple[LifecycleViolation, ...] = field(default_factory=tuple)
    validation: ValidationResult = field(default_factory=ValidationResult)


@dataclass(frozen=True, slots=True)
class ActivationDecision:
    """Activation eligibility — no DocumentId, no persistence."""

    is_allowed: bool
    blockers: Tuple[LifecycleViolation, ...] = field(default_factory=tuple)
    validation: ValidationResult = field(default_factory=ValidationResult)


@dataclass(frozen=True, slots=True)
class LifecycleDecision:
    """Computed lifecycle decision for current state."""

    current_state: DocumentLifecycleState
    archive_state: ArchiveState
    void_kind: VoidKind | None
    allowed_transitions: Tuple[LifecycleTransition, ...] = field(default_factory=tuple)
    blockers: Tuple[LifecycleViolation, ...] = field(default_factory=tuple)
    validation: ValidationResult = field(default_factory=ValidationResult)


@dataclass(frozen=True, slots=True)
class SignedSnapshotDescriptor:
    """Signed snapshot eligibility descriptor — no actual snapshot bytes."""

    is_eligible: bool
    lifecycle_state: DocumentLifecycleState
    blockers: Tuple[LifecycleViolation, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class LifecycleEvaluation:
    """Full lifecycle evaluation from editorial + lifecycle read models."""

    lifecycle: LifecycleReadModel
    decision: LifecycleDecision
    signed_snapshot: SignedSnapshotDescriptor | None = None
    promotion_readiness: PromotionReadiness | None = None
    registration_readiness: RegistrationReadiness | None = None
    validation: ValidationResult = field(default_factory=ValidationResult)
