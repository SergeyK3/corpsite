"""Write command results and mutation plans (UDE-012)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

from app.document_engine.contracts.validation import ValidationResult
from app.document_engine.lifecycle.lifecycle_models import LifecycleViolation
from app.document_engine.value_objects.identity import DocumentId
from app.document_engine.value_objects.lifecycle import ArchiveState, DocumentLifecycleState, VoidKind
from app.document_engine.write.aggregate_models import DocumentAggregate
from app.document_engine.write.domain_events import DomainEvent


@dataclass(frozen=True, slots=True)
class LifecycleMutationPlan:
    """Planned in-memory lifecycle mutation — no side effects."""

    command_name: str
    is_allowed: bool
    from_lifecycle_state: DocumentLifecycleState
    to_lifecycle_state: DocumentLifecycleState | None = None
    from_archive_state: ArchiveState = ArchiveState.ACTIVE
    to_archive_state: ArchiveState | None = None
    void_kind: VoidKind | None = None
    blockers: Tuple[LifecycleViolation, ...] = field(default_factory=tuple)
    events: Tuple[DomainEvent, ...] = field(default_factory=tuple)
    validation: ValidationResult = field(default_factory=ValidationResult)


@dataclass(frozen=True, slots=True)
class CreateResult:
    """Result of create/activate planning — aggregate in memory only."""

    is_allowed: bool
    aggregate: DocumentAggregate | None = None
    mutation_plan: LifecycleMutationPlan | None = None
    events: Tuple[DomainEvent, ...] = field(default_factory=tuple)
    validation: ValidationResult = field(default_factory=ValidationResult)


@dataclass(frozen=True, slots=True)
class PromotionResult:
    """Result of promotion planning."""

    is_allowed: bool
    aggregate: DocumentAggregate | None = None
    mutation_plan: LifecycleMutationPlan | None = None
    events: Tuple[DomainEvent, ...] = field(default_factory=tuple)
    validation: ValidationResult = field(default_factory=ValidationResult)


@dataclass(frozen=True, slots=True)
class RegistrationResult:
    """Result of registration planning — no number persisted."""

    is_allowed: bool
    mutation_plan: LifecycleMutationPlan | None = None
    registration_number: str | None = None
    events: Tuple[DomainEvent, ...] = field(default_factory=tuple)
    validation: ValidationResult = field(default_factory=ValidationResult)


@dataclass(frozen=True, slots=True)
class WriteEvaluation:
    """Unified write orchestration outcome."""

    is_allowed: bool
    command_name: str
    mutation_plan: LifecycleMutationPlan | None = None
    aggregate: DocumentAggregate | None = None
    events: Tuple[DomainEvent, ...] = field(default_factory=tuple)
    validation: ValidationResult = field(default_factory=ValidationResult)
