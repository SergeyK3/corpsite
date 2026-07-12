# tests/document_engine/write/test_write_services.py
"""Unit tests for shared write runtime (UDE-012)."""
from __future__ import annotations

import pytest

from app.document_engine.value_objects.identity import DocumentId, DocumentKind, DocumentSpecialization
from app.document_engine.value_objects.lifecycle import ArchiveState, DocumentLifecycleState, VoidKind
from app.document_engine.write.aggregate_factory import AggregateFactory
from app.document_engine.write.aggregate_models import AggregateMetadata, DocumentAggregate
from app.document_engine.write.command_models import (
    CancelDocumentCommand,
    CreateDocumentCommand,
    MarkReadyCommand,
    PromoteDraftCommand,
    RegisterDocumentCommand,
    SignDocumentCommand,
)
from app.document_engine.write.command_policies import CommandPolicy
from app.document_engine.write.domain_events import DocumentActivated, DocumentCancelled, DocumentMarkedReady
from app.document_engine.write.facade import DocumentEngineWriteFacade
from app.document_engine.write.write_orchestrator import WriteOrchestrator
from tests.document_engine.adapters._fixtures import (
    synthetic_audit_row,
    synthetic_detail,
    synthetic_editorial_state,
)


@pytest.fixture
def write_context():
    detail = synthetic_detail()
    return DocumentEngineWriteFacade.build_context_from_detail(
        detail,
        supplement={"void_kind": None},
        editorial=synthetic_editorial_state(),
        audit_items=[synthetic_audit_row()],
    )


def test_aggregate_factory_assigns_document_id(write_context) -> None:
    draft = write_context.editorial_snapshot.official_draft
    assert draft is not None
    aggregate = AggregateFactory.from_official_draft(draft)
    assert aggregate.document_id.value == "doc:po-1001"
    assert aggregate.lifecycle_state == DocumentLifecycleState.DRAFT
    assert aggregate.archive_state == ArchiveState.ACTIVE
    assert aggregate.document_kind == DocumentKind.PERSONNEL_ORDER
    assert len(aggregate.locale_blocks) == 3


def test_aggregate_factory_activation_events(write_context) -> None:
    draft = write_context.editorial_snapshot.official_draft
    assert draft is not None
    aggregate = AggregateFactory.from_official_draft(draft)
    activated, promoted = AggregateFactory.activation_events(aggregate)
    assert isinstance(activated, DocumentActivated)
    assert activated.lifecycle_state == DocumentLifecycleState.DRAFT
    assert promoted.workspace_reference == draft.workspace_reference


def test_create_command_allowed(write_context) -> None:
    draft = write_context.editorial_snapshot.official_draft
    assert draft is not None
    result = DocumentEngineWriteFacade.create_from_draft(write_context)
    assert result.is_allowed is True
    assert result.aggregate is not None
    assert len(result.events) == 2


def test_promote_command_allowed(write_context) -> None:
    evaluation = DocumentEngineWriteFacade.promote_from_draft(write_context)
    assert evaluation.is_allowed is True
    assert evaluation.aggregate is not None
    assert evaluation.mutation_plan is not None
    assert evaluation.mutation_plan.command_name == "CreateDocumentCommand"


def test_mark_ready_command_from_draft(write_context) -> None:
    aggregate = write_context.aggregate
    assert aggregate is not None
    plan = CommandPolicy.evaluate_mark_ready(
        aggregate,
        MarkReadyCommand(actor_user_id=1),
        write_context.lifecycle_snapshot,
    )
    assert plan.is_allowed is True
    assert plan.to_lifecycle_state == DocumentLifecycleState.READY_FOR_SIGNATURE
    assert len(plan.events) == 1
    assert isinstance(plan.events[0], DocumentMarkedReady)


def test_cancel_command_from_draft(write_context) -> None:
    aggregate = write_context.aggregate
    assert aggregate is not None
    plan = CommandPolicy.evaluate_cancel(
        aggregate,
        CancelDocumentCommand(reason_code="mistake"),
        write_context.lifecycle_snapshot,
    )
    assert plan.is_allowed is True
    assert plan.to_lifecycle_state == DocumentLifecycleState.VOIDED
    assert plan.void_kind == VoidKind.CANCEL
    assert isinstance(plan.events[0], DocumentCancelled)


def test_register_blocked_from_draft(write_context) -> None:
    aggregate = write_context.aggregate
    assert aggregate is not None
    result = CommandPolicy.evaluate_register(
        aggregate,
        RegisterDocumentCommand(registration_number="REG-001"),
        write_context.lifecycle_snapshot,
    )
    assert result.is_allowed is False


def test_register_allowed_from_signed() -> None:
    aggregate = DocumentAggregate(
        document_id=DocumentId("doc:po-1001"),
        document_kind=DocumentKind.PERSONNEL_ORDER,
        specialization=DocumentSpecialization.PERSONNEL,
        lifecycle_state=DocumentLifecycleState.SIGNED,
        archive_state=ArchiveState.ACTIVE,
        void_kind=None,
        metadata=AggregateMetadata(order_type_code="HIRE", workspace_reference="po:1001"),
    )
    from app.document_engine.lifecycle.facade import DocumentEngineLifecycleFacade
    from app.document_engine.read_services.facade import DocumentEngineReadFacade

    detail = synthetic_detail()
    detail["order"]["status"] = "SIGNED"
    read_snapshot = DocumentEngineReadFacade.from_detail(
        detail,
        editorial=synthetic_editorial_state(),
    )
    lifecycle_snapshot = DocumentEngineLifecycleFacade.from_read_snapshot(read_snapshot)
    result = CommandPolicy.evaluate_register(
        aggregate,
        RegisterDocumentCommand(registration_number="REG-001"),
        lifecycle_snapshot,
    )
    assert result.is_allowed is True
    assert result.mutation_plan is not None
    assert result.mutation_plan.to_lifecycle_state == DocumentLifecycleState.REGISTERED


def test_write_orchestrator_apply_plan_in_memory(write_context) -> None:
    aggregate = write_context.aggregate
    assert aggregate is not None
    evaluation = WriteOrchestrator.plan(
        MarkReadyCommand(),
        aggregate=aggregate,
        lifecycle_snapshot=write_context.lifecycle_snapshot,
    )
    assert evaluation.mutation_plan is not None
    updated = WriteOrchestrator.apply_plan_in_memory(aggregate, evaluation.mutation_plan)
    assert updated.lifecycle_state == DocumentLifecycleState.READY_FOR_SIGNATURE
    assert aggregate.lifecycle_state == DocumentLifecycleState.DRAFT


def test_write_facade_plan_command(write_context) -> None:
    draft = write_context.editorial_snapshot.official_draft
    assert draft is not None
    evaluation = DocumentEngineWriteFacade.plan_command(
        CreateDocumentCommand(workspace_reference=draft.workspace_reference),
        write_context,
    )
    assert evaluation.is_allowed is True
    assert evaluation.command_name == "CreateDocumentCommand"


def test_write_models_are_immutable(write_context) -> None:
    aggregate = write_context.aggregate
    assert aggregate is not None
    with pytest.raises(AttributeError):
        aggregate.lifecycle_state = DocumentLifecycleState.VOIDED  # type: ignore[misc]


def test_write_evaluation_repeatable(write_context) -> None:
    first = DocumentEngineWriteFacade.promote_from_draft(write_context)
    second = DocumentEngineWriteFacade.promote_from_draft(write_context)
    assert first.is_allowed == second.is_allowed
    assert first.aggregate is not None and second.aggregate is not None
    assert first.aggregate.document_id == second.aggregate.document_id
