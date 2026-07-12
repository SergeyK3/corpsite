"""Document engine write facade — single public entry point (UDE-012)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Tuple

from app.document_engine.editorial.facade import DocumentEngineEditorialFacade
from app.document_engine.lifecycle.facade import DocumentEngineLifecycleFacade
from app.document_engine.read_services.facade import DocumentEngineReadFacade
from app.document_engine.write.aggregate_factory import AggregateFactory
from app.document_engine.write.aggregate_models import DocumentAggregate
from app.document_engine.write.command_models import (
    CreateDocumentCommand,
    PromoteDraftCommand,
)
from app.document_engine.write.command_results import CreateResult, WriteEvaluation
from app.document_engine.write.domain_events import DomainEvent
from app.document_engine.write.write_orchestrator import WriteCommand, WriteOrchestrator


@dataclass(frozen=True, slots=True)
class DocumentEngineWriteContext:
    """Bundled upstream snapshots for write planning."""

    read_snapshot: Any
    editorial_snapshot: Any
    lifecycle_snapshot: Any
    aggregate: DocumentAggregate | None = None


@dataclass(frozen=True, slots=True)
class DocumentEngineWriteSnapshot:
    context: DocumentEngineWriteContext
    last_evaluation: WriteEvaluation | None = None
    planned_events: Tuple[DomainEvent, ...] = field(default_factory=tuple)


class DocumentEngineWriteFacade:
    """Entry point for future Operational Orders write orchestration."""

    @staticmethod
    def build_context_from_detail(
        detail: Mapping[str, Any],
        *,
        supplement: Mapping[str, Any] | None = None,
        editorial: Mapping[str, Any] | None = None,
        audit_items: list[Mapping[str, Any]] | None = None,
        create_aggregate: bool = True,
    ) -> DocumentEngineWriteContext:
        read_snapshot = DocumentEngineReadFacade.from_detail(
            detail,
            supplement=supplement,
            editorial=editorial,
            audit_items=audit_items,
        )
        editorial_snapshot = DocumentEngineEditorialFacade.from_read_snapshot(read_snapshot)
        lifecycle_snapshot = DocumentEngineLifecycleFacade.from_editorial_snapshot(
            editorial_snapshot,
            read_snapshot,
        )
        aggregate = None
        if create_aggregate and editorial_snapshot.official_draft is not None:
            if lifecycle_snapshot.activation and lifecycle_snapshot.activation.is_allowed:
                aggregate = AggregateFactory.from_official_draft(
                    editorial_snapshot.official_draft
                )
        return DocumentEngineWriteContext(
            read_snapshot=read_snapshot,
            editorial_snapshot=editorial_snapshot,
            lifecycle_snapshot=lifecycle_snapshot,
            aggregate=aggregate,
        )

    @staticmethod
    def plan_command(
        command: WriteCommand,
        context: DocumentEngineWriteContext,
    ) -> WriteEvaluation:
        draft = None
        if context.editorial_snapshot.official_draft is not None:
            draft = context.editorial_snapshot.official_draft
        return WriteOrchestrator.plan(
            command,
            aggregate=context.aggregate,
            draft=draft,
            lifecycle_snapshot=context.lifecycle_snapshot,
        )

    @staticmethod
    def create_from_draft(context: DocumentEngineWriteContext) -> CreateResult:
        draft = context.editorial_snapshot.official_draft
        if draft is None:
            raise ValueError("No official draft in context")
        command = CreateDocumentCommand(workspace_reference=draft.workspace_reference)
        evaluation = DocumentEngineWriteFacade.plan_command(command, context)
        return CreateResult(
            is_allowed=evaluation.is_allowed,
            aggregate=evaluation.aggregate,
            mutation_plan=evaluation.mutation_plan,
            events=evaluation.events,
            validation=evaluation.validation,
        )

    @staticmethod
    def promote_from_draft(context: DocumentEngineWriteContext) -> WriteEvaluation:
        draft = context.editorial_snapshot.official_draft
        if draft is None:
            raise ValueError("No official draft in context")
        return DocumentEngineWriteFacade.plan_command(
            PromoteDraftCommand(workspace_reference=draft.workspace_reference),
            context,
        )
