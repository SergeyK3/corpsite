"""Command policies — allowed/blocked mutation plans (UDE-012)."""
from __future__ import annotations

from app.document_engine.contracts.validation import ValidationIssue, ValidationResult, ValidationSeverity
from app.document_engine.editorial.editorial_models import OfficialDraftSnapshot
from app.document_engine.lifecycle.activation_service import ActivationService
from app.document_engine.lifecycle.facade import DocumentEngineLifecycleSnapshot
from app.document_engine.lifecycle.lifecycle_models import LifecycleGate, LifecycleViolation
from app.document_engine.lifecycle.registration_policy import RegistrationPolicy
from app.document_engine.read_models.lifecycle import LifecycleReadModel
from app.document_engine.value_objects.lifecycle import ArchiveState, DocumentLifecycleState, VoidKind
from app.document_engine.write.aggregate_models import DocumentAggregate
from app.document_engine.write.command_models import (
    AnnulDocumentCommand,
    ArchiveDocumentCommand,
    CancelDocumentCommand,
    CreateDocumentCommand,
    MarkReadyCommand,
    PromoteDraftCommand,
    RegisterDocumentCommand,
    RestoreDocumentCommand,
    ReturnToDraftCommand,
    SignDocumentCommand,
)
from app.document_engine.write.command_results import (
    CreateResult,
    LifecycleMutationPlan,
    PromotionResult,
    RegistrationResult,
)
from app.document_engine.write.domain_events import (
    DocumentAnnulled,
    DocumentArchived,
    DocumentCancelled,
    DocumentMarkedReady,
    DocumentRegistered,
    DocumentRestored,
    DocumentReturnedToDraft,
    DocumentSigned,
)
from app.document_engine.write.aggregate_factory import AggregateFactory


class CommandPolicy:
    """Evaluates write commands via lifecycle runtime — no persistence."""

    @staticmethod
    def _lifecycle_from_aggregate(aggregate: DocumentAggregate) -> LifecycleReadModel:
        return LifecycleReadModel(
            document_id=aggregate.document_id,
            lifecycle_state=aggregate.lifecycle_state,
            archive_state=aggregate.archive_state,
            void_kind=aggregate.void_kind,
            legacy_status=aggregate.lifecycle_state.value,
            is_archived=aggregate.is_archived,
        )

    @staticmethod
    def _plan(
        *,
        command_name: str,
        aggregate: DocumentAggregate,
        gate: LifecycleGate,
        target_state: DocumentLifecycleState | None,
        allowed: bool,
        blockers: tuple[LifecycleViolation, ...],
        events: tuple = (),
        void_kind: VoidKind | None = None,
        to_archive: ArchiveState | None = None,
    ) -> LifecycleMutationPlan:
        issues = tuple(
            ValidationIssue(
                code=b.code,
                severity=ValidationSeverity.ERROR,
                message=b.message,
                field_path=b.field_path,
            )
            for b in blockers
        )
        return LifecycleMutationPlan(
            command_name=command_name,
            is_allowed=allowed,
            from_lifecycle_state=aggregate.lifecycle_state,
            to_lifecycle_state=target_state,
            from_archive_state=aggregate.archive_state,
            to_archive_state=to_archive,
            void_kind=void_kind if void_kind is not None else aggregate.void_kind,
            blockers=blockers,
            events=events,
            validation=ValidationResult.from_issues(issues),
        )

    @staticmethod
    def _find_transition(
        lifecycle_snapshot: DocumentEngineLifecycleSnapshot,
        gate: LifecycleGate,
    ) -> tuple[bool, str | None]:
        decision = lifecycle_snapshot.lifecycle_decision
        if decision is None:
            return False, "No lifecycle decision available"
        for transition in decision.allowed_transitions:
            if transition.gate == gate:
                return transition.allowed, transition.reason
        return False, f"Gate {gate.value} not applicable"

    @staticmethod
    def evaluate_create(
        draft: OfficialDraftSnapshot,
        command: CreateDocumentCommand,
        lifecycle_snapshot: DocumentEngineLifecycleSnapshot,
    ) -> CreateResult:
        activation = ActivationService.evaluate(draft)
        if not activation.is_allowed:
            plan = CommandPolicy._plan(
                command_name="CreateDocumentCommand",
                aggregate=AggregateFactory.from_official_draft(draft),
                gate=LifecycleGate.ACTIVATION,
                target_state=DocumentLifecycleState.DRAFT,
                allowed=False,
                blockers=activation.blockers,
            )
            return CreateResult(
                is_allowed=False,
                mutation_plan=plan,
                validation=activation.validation,
            )

        aggregate = AggregateFactory.from_official_draft(draft)
        events = AggregateFactory.activation_events(aggregate)
        plan = LifecycleMutationPlan(
            command_name="CreateDocumentCommand",
            is_allowed=True,
            from_lifecycle_state=DocumentLifecycleState.DRAFT,
            to_lifecycle_state=DocumentLifecycleState.DRAFT,
            from_archive_state=ArchiveState.ACTIVE,
            to_archive_state=ArchiveState.ACTIVE,
            void_kind=None,
            blockers=(),
            events=events,
            validation=activation.validation,
        )
        return CreateResult(
            is_allowed=True,
            aggregate=aggregate,
            mutation_plan=plan,
            events=events,
            validation=activation.validation,
        )

    @staticmethod
    def evaluate_promote(
        draft: OfficialDraftSnapshot,
        command: PromoteDraftCommand,
        lifecycle_snapshot: DocumentEngineLifecycleSnapshot,
    ) -> PromotionResult:
        create = CommandPolicy.evaluate_create(
            draft,
            CreateDocumentCommand(workspace_reference=command.workspace_reference),
            lifecycle_snapshot,
        )
        return PromotionResult(
            is_allowed=create.is_allowed,
            aggregate=create.aggregate,
            mutation_plan=create.mutation_plan,
            events=create.events,
            validation=create.validation,
        )

    @staticmethod
    def evaluate_mark_ready(
        aggregate: DocumentAggregate,
        command: MarkReadyCommand,
        lifecycle_snapshot: DocumentEngineLifecycleSnapshot,
    ) -> LifecycleMutationPlan:
        allowed, reason = CommandPolicy._find_transition(lifecycle_snapshot, LifecycleGate.MARK_READY)
        blockers: list[LifecycleViolation] = []
        if not allowed and reason:
            blockers.append(
                LifecycleViolation(code="W_MARK_READY", message=reason, gate=LifecycleGate.MARK_READY)
            )
        events = ()
        if allowed:
            events = (
                DocumentMarkedReady(
                    document_id=aggregate.document_id,
                    from_state=aggregate.lifecycle_state,
                    to_state=DocumentLifecycleState.READY_FOR_SIGNATURE,
                ),
            )
        return CommandPolicy._plan(
            command_name="MarkReadyCommand",
            aggregate=aggregate,
            gate=LifecycleGate.MARK_READY,
            target_state=DocumentLifecycleState.READY_FOR_SIGNATURE,
            allowed=allowed,
            blockers=tuple(blockers),
            events=events,
        )

    @staticmethod
    def evaluate_return_to_draft(
        aggregate: DocumentAggregate,
        command: ReturnToDraftCommand,
        lifecycle_snapshot: DocumentEngineLifecycleSnapshot,
    ) -> LifecycleMutationPlan:
        allowed, reason = CommandPolicy._find_transition(
            lifecycle_snapshot, LifecycleGate.RETURN_TO_DRAFT
        )
        blockers: list[LifecycleViolation] = []
        if not allowed and reason:
            blockers.append(
                LifecycleViolation(
                    code="W_RETURN_DRAFT",
                    message=reason,
                    gate=LifecycleGate.RETURN_TO_DRAFT,
                )
            )
        events = ()
        if allowed:
            events = (
                DocumentReturnedToDraft(
                    document_id=aggregate.document_id,
                    from_state=aggregate.lifecycle_state,
                    to_state=DocumentLifecycleState.DRAFT,
                ),
            )
        return CommandPolicy._plan(
            command_name="ReturnToDraftCommand",
            aggregate=aggregate,
            gate=LifecycleGate.RETURN_TO_DRAFT,
            target_state=DocumentLifecycleState.DRAFT,
            allowed=allowed,
            blockers=tuple(blockers),
            events=events,
        )

    @staticmethod
    def evaluate_sign(
        aggregate: DocumentAggregate,
        command: SignDocumentCommand,
        lifecycle_snapshot: DocumentEngineLifecycleSnapshot,
    ) -> LifecycleMutationPlan:
        allowed, reason = CommandPolicy._find_transition(lifecycle_snapshot, LifecycleGate.SIGN)
        blockers: list[LifecycleViolation] = []
        if not allowed and reason:
            blockers.append(
                LifecycleViolation(code="W_SIGN", message=reason, gate=LifecycleGate.SIGN)
            )
        events = ()
        if allowed:
            events = (
                DocumentSigned(
                    document_id=aggregate.document_id,
                    from_state=aggregate.lifecycle_state,
                    to_state=DocumentLifecycleState.SIGNED,
                ),
            )
        return CommandPolicy._plan(
            command_name="SignDocumentCommand",
            aggregate=aggregate,
            gate=LifecycleGate.SIGN,
            target_state=DocumentLifecycleState.SIGNED,
            allowed=allowed,
            blockers=tuple(blockers),
            events=events,
        )

    @staticmethod
    def evaluate_register(
        aggregate: DocumentAggregate,
        command: RegisterDocumentCommand,
        lifecycle_snapshot: DocumentEngineLifecycleSnapshot,
    ) -> RegistrationResult:
        lifecycle = CommandPolicy._lifecycle_from_aggregate(aggregate)
        readiness = RegistrationPolicy.evaluate(lifecycle)
        allowed, reason = CommandPolicy._find_transition(lifecycle_snapshot, LifecycleGate.REGISTER)
        blockers = list(readiness.blockers)
        if not allowed and reason:
            blockers.append(
                LifecycleViolation(code="W_REGISTER", message=reason, gate=LifecycleGate.REGISTER)
            )
        events = ()
        if allowed and readiness.is_ready:
            events = (
                DocumentRegistered(
                    document_id=aggregate.document_id,
                    from_state=aggregate.lifecycle_state,
                    to_state=DocumentLifecycleState.REGISTERED,
                    registration_number=command.registration_number,
                ),
            )
        is_allowed = allowed and readiness.is_ready
        plan = CommandPolicy._plan(
            command_name="RegisterDocumentCommand",
            aggregate=aggregate,
            gate=LifecycleGate.REGISTER,
            target_state=DocumentLifecycleState.REGISTERED,
            allowed=is_allowed,
            blockers=tuple(blockers),
            events=events,
        )
        return RegistrationResult(
            is_allowed=is_allowed,
            mutation_plan=plan,
            registration_number=command.registration_number,
            events=events,
            validation=plan.validation,
        )

    @staticmethod
    def evaluate_cancel(
        aggregate: DocumentAggregate,
        command: CancelDocumentCommand,
        lifecycle_snapshot: DocumentEngineLifecycleSnapshot,
    ) -> LifecycleMutationPlan:
        allowed, reason = CommandPolicy._find_transition(lifecycle_snapshot, LifecycleGate.CANCEL)
        blockers: list[LifecycleViolation] = []
        if not allowed and reason:
            blockers.append(
                LifecycleViolation(code="W_CANCEL", message=reason, gate=LifecycleGate.CANCEL)
            )
        events = ()
        if allowed:
            events = (
                DocumentCancelled(
                    document_id=aggregate.document_id,
                    void_kind=VoidKind.CANCEL,
                    reason_code=command.reason_code,
                    reason_text=command.reason_text,
                ),
            )
        return CommandPolicy._plan(
            command_name="CancelDocumentCommand",
            aggregate=aggregate,
            gate=LifecycleGate.CANCEL,
            target_state=DocumentLifecycleState.VOIDED,
            allowed=allowed,
            blockers=tuple(blockers),
            events=events,
            void_kind=VoidKind.CANCEL,
        )

    @staticmethod
    def evaluate_annul(
        aggregate: DocumentAggregate,
        command: AnnulDocumentCommand,
        lifecycle_snapshot: DocumentEngineLifecycleSnapshot,
    ) -> LifecycleMutationPlan:
        allowed, reason = CommandPolicy._find_transition(lifecycle_snapshot, LifecycleGate.ANNUL)
        blockers: list[LifecycleViolation] = []
        if not allowed and reason:
            blockers.append(
                LifecycleViolation(code="W_ANNUL", message=reason, gate=LifecycleGate.ANNUL)
            )
        events = ()
        if allowed:
            events = (
                DocumentAnnulled(
                    document_id=aggregate.document_id,
                    void_kind=VoidKind.ANNUL,
                    reason_code=command.reason_code,
                    reason_text=command.reason_text,
                ),
            )
        return CommandPolicy._plan(
            command_name="AnnulDocumentCommand",
            aggregate=aggregate,
            gate=LifecycleGate.ANNUL,
            target_state=DocumentLifecycleState.VOIDED,
            allowed=allowed,
            blockers=tuple(blockers),
            events=events,
            void_kind=VoidKind.ANNUL,
        )

    @staticmethod
    def evaluate_archive(
        aggregate: DocumentAggregate,
        command: ArchiveDocumentCommand,
        lifecycle_snapshot: DocumentEngineLifecycleSnapshot,
    ) -> LifecycleMutationPlan:
        allowed, reason = CommandPolicy._find_transition(lifecycle_snapshot, LifecycleGate.ARCHIVE)
        if aggregate.archive_state == ArchiveState.ARCHIVED:
            allowed = False
            reason = "Already archived"
        blockers: list[LifecycleViolation] = []
        if not allowed and reason:
            blockers.append(
                LifecycleViolation(code="W_ARCHIVE", message=reason, gate=LifecycleGate.ARCHIVE)
            )
        events = ()
        if allowed:
            events = (
                DocumentArchived(
                    document_id=aggregate.document_id,
                    from_archive_state=aggregate.archive_state,
                    to_archive_state=ArchiveState.ARCHIVED,
                ),
            )
        return CommandPolicy._plan(
            command_name="ArchiveDocumentCommand",
            aggregate=aggregate,
            gate=LifecycleGate.ARCHIVE,
            target_state=None,
            allowed=allowed,
            blockers=tuple(blockers),
            events=events,
            to_archive=ArchiveState.ARCHIVED,
        )

    @staticmethod
    def evaluate_restore(
        aggregate: DocumentAggregate,
        command: RestoreDocumentCommand,
        lifecycle_snapshot: DocumentEngineLifecycleSnapshot,
    ) -> LifecycleMutationPlan:
        allowed = aggregate.archive_state == ArchiveState.ARCHIVED
        reason = None if allowed else "Not archived"
        blockers: list[LifecycleViolation] = []
        if not allowed and reason:
            blockers.append(
                LifecycleViolation(code="W_RESTORE", message=reason, gate=LifecycleGate.ARCHIVE)
            )
        events = ()
        if allowed:
            events = (
                DocumentRestored(
                    document_id=aggregate.document_id,
                    from_archive_state=aggregate.archive_state,
                    to_archive_state=ArchiveState.ACTIVE,
                ),
            )
        return CommandPolicy._plan(
            command_name="RestoreDocumentCommand",
            aggregate=aggregate,
            gate=LifecycleGate.ARCHIVE,
            target_state=None,
            allowed=allowed,
            blockers=tuple(blockers),
            events=events,
            to_archive=ArchiveState.ACTIVE,
        )
