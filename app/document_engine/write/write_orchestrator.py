"""Write orchestrator — command planning without side effects (UDE-012)."""
from __future__ import annotations

from typing import Any, Union

from app.document_engine.editorial.editorial_models import OfficialDraftSnapshot
from app.document_engine.lifecycle.facade import DocumentEngineLifecycleSnapshot
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
from app.document_engine.write.command_policies import CommandPolicy
from app.document_engine.write.command_results import (
    CreateResult,
    LifecycleMutationPlan,
    PromotionResult,
    RegistrationResult,
    WriteEvaluation,
)

WriteCommand = Union[
    CreateDocumentCommand,
    PromoteDraftCommand,
    MarkReadyCommand,
    ReturnToDraftCommand,
    SignDocumentCommand,
    RegisterDocumentCommand,
    CancelDocumentCommand,
    AnnulDocumentCommand,
    ArchiveDocumentCommand,
    RestoreDocumentCommand,
]


class WriteOrchestrator:
    """Plans write commands via lifecycle runtime — no DB, no ORM, no side effects."""

    @staticmethod
    def command_name(command: WriteCommand) -> str:
        return type(command).__name__

    @staticmethod
    def plan(
        command: WriteCommand,
        *,
        aggregate: DocumentAggregate | None = None,
        draft: OfficialDraftSnapshot | None = None,
        lifecycle_snapshot: DocumentEngineLifecycleSnapshot,
    ) -> WriteEvaluation:
        if isinstance(command, CreateDocumentCommand):
            if draft is None:
                raise ValueError("CreateDocumentCommand requires draft")
            result = CommandPolicy.evaluate_create(draft, command, lifecycle_snapshot)
            return WriteEvaluation(
                is_allowed=result.is_allowed,
                command_name="CreateDocumentCommand",
                mutation_plan=result.mutation_plan,
                aggregate=result.aggregate,
                events=result.events,
                validation=result.validation,
            )

        if isinstance(command, PromoteDraftCommand):
            if draft is None:
                raise ValueError("PromoteDraftCommand requires draft")
            result = CommandPolicy.evaluate_promote(draft, command, lifecycle_snapshot)
            return WriteEvaluation(
                is_allowed=result.is_allowed,
                command_name="PromoteDraftCommand",
                mutation_plan=result.mutation_plan,
                aggregate=result.aggregate,
                events=result.events,
                validation=result.validation,
            )

        if aggregate is None:
            raise ValueError(f"{WriteOrchestrator.command_name(command)} requires aggregate")

        if isinstance(command, MarkReadyCommand):
            plan = CommandPolicy.evaluate_mark_ready(aggregate, command, lifecycle_snapshot)
        elif isinstance(command, ReturnToDraftCommand):
            plan = CommandPolicy.evaluate_return_to_draft(aggregate, command, lifecycle_snapshot)
        elif isinstance(command, SignDocumentCommand):
            plan = CommandPolicy.evaluate_sign(aggregate, command, lifecycle_snapshot)
        elif isinstance(command, RegisterDocumentCommand):
            reg = CommandPolicy.evaluate_register(aggregate, command, lifecycle_snapshot)
            return WriteEvaluation(
                is_allowed=reg.is_allowed,
                command_name="RegisterDocumentCommand",
                mutation_plan=reg.mutation_plan,
                aggregate=aggregate,
                events=reg.events,
                validation=reg.validation,
            )
        elif isinstance(command, CancelDocumentCommand):
            plan = CommandPolicy.evaluate_cancel(aggregate, command, lifecycle_snapshot)
        elif isinstance(command, AnnulDocumentCommand):
            plan = CommandPolicy.evaluate_annul(aggregate, command, lifecycle_snapshot)
        elif isinstance(command, ArchiveDocumentCommand):
            plan = CommandPolicy.evaluate_archive(aggregate, command, lifecycle_snapshot)
        elif isinstance(command, RestoreDocumentCommand):
            plan = CommandPolicy.evaluate_restore(aggregate, command, lifecycle_snapshot)
        else:
            raise TypeError(f"Unsupported command: {type(command)}")

        return WriteEvaluation(
            is_allowed=plan.is_allowed,
            command_name=plan.command_name,
            mutation_plan=plan,
            aggregate=aggregate,
            events=plan.events,
            validation=plan.validation,
        )

    @staticmethod
    def apply_plan_in_memory(
        aggregate: DocumentAggregate,
        plan: LifecycleMutationPlan,
    ) -> DocumentAggregate:
        """Returns new aggregate reflecting plan — in-memory only, no persistence."""
        return DocumentAggregate(
            document_id=aggregate.document_id,
            document_kind=aggregate.document_kind,
            specialization=aggregate.specialization,
            lifecycle_state=plan.to_lifecycle_state or aggregate.lifecycle_state,
            archive_state=plan.to_archive_state or aggregate.archive_state,
            void_kind=plan.void_kind,
            metadata=aggregate.metadata,
            locale_blocks=aggregate.locale_blocks,
            official_draft=aggregate.official_draft,
            item_count=aggregate.item_count,
            validation_state=plan.validation,
        )
