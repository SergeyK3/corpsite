# tests/document_engine/lifecycle/test_lifecycle_services.py
"""Unit tests for shared activation and lifecycle runtime (UDE-011)."""
from __future__ import annotations

import pytest

from app.document_engine.editorial.facade import DocumentEngineEditorialFacade
from app.document_engine.lifecycle.activation_service import ActivationService
from app.document_engine.lifecycle.facade import DocumentEngineLifecycleFacade
from app.document_engine.lifecycle.lifecycle_models import LifecycleGate
from app.document_engine.lifecycle.lifecycle_rules import LifecycleRules
from app.document_engine.lifecycle.lifecycle_service import LifecycleEvaluationService
from app.document_engine.lifecycle.promotion_policy import PromotionPolicy
from app.document_engine.lifecycle.readiness_policy import ReadinessPolicy
from app.document_engine.lifecycle.registration_policy import RegistrationPolicy
from app.document_engine.read_models.lifecycle import LifecycleReadModel
from app.document_engine.read_services.facade import DocumentEngineReadFacade
from app.document_engine.value_objects.identity import DocumentId
from app.document_engine.value_objects.lifecycle import ArchiveState, DocumentLifecycleState, VoidKind
from tests.document_engine.adapters._fixtures import (
    synthetic_audit_row,
    synthetic_detail,
    synthetic_editorial_state,
)


@pytest.fixture
def read_snapshot():
    detail = synthetic_detail()
    return DocumentEngineReadFacade.from_detail(
        detail,
        supplement={"void_kind": None},
        editorial=synthetic_editorial_state(),
        audit_items=[synthetic_audit_row()],
    )


@pytest.fixture
def editorial_snapshot(read_snapshot):
    return DocumentEngineEditorialFacade.from_read_snapshot(read_snapshot)


@pytest.fixture
def lifecycle_model(read_snapshot):
    doc = read_snapshot.document
    return LifecycleReadModel(
        document_id=doc.document_id,
        lifecycle_state=doc.lifecycle_state,
        archive_state=doc.archive_state,
        void_kind=doc.void_kind,
        legacy_status=doc.legacy_status,
        is_archived=doc.is_archived,
    )


def test_lifecycle_rules_draft_transitions() -> None:
    assert LifecycleRules.structurally_allowed(
        DocumentLifecycleState.DRAFT,
        DocumentLifecycleState.READY_FOR_SIGNATURE,
    )
    assert LifecycleRules.structurally_allowed(
        DocumentLifecycleState.DRAFT,
        DocumentLifecycleState.VOIDED,
    )
    assert not LifecycleRules.structurally_allowed(
        DocumentLifecycleState.DRAFT,
        DocumentLifecycleState.REGISTERED,
    )


def test_lifecycle_rules_voided_terminal() -> None:
    assert LifecycleRules.possible_transitions(DocumentLifecycleState.VOIDED) == ()


def test_lifecycle_rules_published_present() -> None:
    assert DocumentLifecycleState.PUBLISHED.value == "PUBLISHED"


def test_lifecycle_rules_registered_to_published() -> None:
    assert LifecycleRules.structurally_allowed(
        DocumentLifecycleState.REGISTERED,
        DocumentLifecycleState.PUBLISHED,
    )
    gate = LifecycleRules.gate_for_transition(
        DocumentLifecycleState.REGISTERED,
        DocumentLifecycleState.PUBLISHED,
    )
    assert gate == LifecycleGate.PUBLISH


def test_lifecycle_rules_forbidden_backward_transitions() -> None:
    assert not LifecycleRules.structurally_allowed(
        DocumentLifecycleState.PUBLISHED,
        DocumentLifecycleState.REGISTERED,
    )
    assert not LifecycleRules.structurally_allowed(
        DocumentLifecycleState.PUBLISHED,
        DocumentLifecycleState.SIGNED,
    )
    assert not LifecycleRules.structurally_allowed(
        DocumentLifecycleState.REGISTERED,
        DocumentLifecycleState.SIGNED,
    )
    assert not LifecycleRules.structurally_allowed(
        DocumentLifecycleState.SIGNED,
        DocumentLifecycleState.READY_FOR_SIGNATURE,
    )


def test_readiness_policy_passes_synthetic_draft(editorial_snapshot) -> None:
    draft = editorial_snapshot.official_draft
    assert draft is not None
    violations, validation = ReadinessPolicy.evaluate_official_draft(draft)
    assert violations == []
    assert validation.is_valid is True


def test_promotion_policy_ready_for_draft(editorial_snapshot) -> None:
    draft = editorial_snapshot.official_draft
    assert draft is not None
    readiness = PromotionPolicy.evaluate(draft)
    assert readiness.is_ready is True
    assert readiness.blockers == ()


def test_activation_service_allowed_for_synthetic(editorial_snapshot) -> None:
    draft = editorial_snapshot.official_draft
    assert draft is not None
    decision = ActivationService.evaluate(draft)
    assert decision.is_allowed is True
    assert decision.blockers == ()
    assert decision.validation.is_valid is True


def test_registration_policy_requires_signed(lifecycle_model) -> None:
    readiness = RegistrationPolicy.evaluate(lifecycle_model)
    assert readiness.is_ready is False
    assert any(b.code == "L_REGISTER_STATE" for b in readiness.blockers)


def test_registration_policy_allows_signed() -> None:
    lifecycle = LifecycleReadModel(
        document_id=DocumentId("po:1001"),
        lifecycle_state=DocumentLifecycleState.SIGNED,
        archive_state=ArchiveState.ACTIVE,
        void_kind=None,
        legacy_status="SIGNED",
        is_archived=False,
    )
    readiness = RegistrationPolicy.evaluate(lifecycle)
    assert readiness.is_ready is True


def test_lifecycle_evaluation_preserves_state(
    editorial_snapshot,
    lifecycle_model,
) -> None:
    draft = editorial_snapshot.official_draft
    evaluation = LifecycleEvaluationService.evaluate(
        editorial_snapshot.editorial,
        lifecycle_model,
        draft=draft,
    )
    assert evaluation.lifecycle.lifecycle_state == DocumentLifecycleState.DRAFT
    assert evaluation.decision.current_state == DocumentLifecycleState.DRAFT
    assert evaluation.promotion_readiness is not None
    assert evaluation.promotion_readiness.is_ready is True


def test_lifecycle_evaluation_draft_allowed_transitions(
    editorial_snapshot,
    lifecycle_model,
) -> None:
    draft = editorial_snapshot.official_draft
    evaluation = LifecycleEvaluationService.evaluate(
        editorial_snapshot.editorial,
        lifecycle_model,
        draft=draft,
    )
    allowed_targets = {
        t.to_state for t in evaluation.decision.allowed_transitions if t.allowed
    }
    assert DocumentLifecycleState.READY_FOR_SIGNATURE in allowed_targets
    assert DocumentLifecycleState.VOIDED in allowed_targets


def test_lifecycle_evaluation_signed_snapshot_descriptor(lifecycle_model) -> None:
    descriptor = LifecycleEvaluationService.signed_snapshot_descriptor(lifecycle_model)
    assert descriptor.is_eligible is False
    assert lifecycle_model.lifecycle_state == DocumentLifecycleState.DRAFT


def test_lifecycle_facade_aggregates_all(read_snapshot) -> None:
    snapshot = DocumentEngineLifecycleFacade.from_read_snapshot(read_snapshot)
    assert snapshot.activation is not None
    assert snapshot.activation.is_allowed is True
    assert snapshot.evaluation is not None
    assert snapshot.promotion_readiness is not None
    assert snapshot.registration_readiness is not None
    assert snapshot.lifecycle_decision is not None
    assert snapshot.lifecycle_decision.current_state == DocumentLifecycleState.DRAFT


def test_lifecycle_facade_from_detail() -> None:
    detail = synthetic_detail()
    snapshot = DocumentEngineLifecycleFacade.from_detail(
        detail,
        editorial=synthetic_editorial_state(),
    )
    assert snapshot.evaluation is not None
    assert snapshot.evaluation.lifecycle.legacy_status == "DRAFT"


def test_lifecycle_models_are_immutable(read_snapshot) -> None:
    snapshot = DocumentEngineLifecycleFacade.from_read_snapshot(read_snapshot)
    with pytest.raises(AttributeError):
        snapshot.activation.is_allowed = False  # type: ignore[misc]


def test_lifecycle_evaluation_repeatable(read_snapshot) -> None:
    first = DocumentEngineLifecycleFacade.from_read_snapshot(read_snapshot)
    second = DocumentEngineLifecycleFacade.from_read_snapshot(read_snapshot)
    assert first.evaluation is not None and second.evaluation is not None
    assert (
        first.evaluation.decision.current_state
        == second.evaluation.decision.current_state
    )
    assert (
        first.activation.is_allowed
        == second.activation.is_allowed
    )


def test_cancel_gate_from_draft(editorial_snapshot, lifecycle_model) -> None:
    evaluation = LifecycleEvaluationService.evaluate_decision(
        editorial_snapshot.editorial,
        lifecycle_model,
    )
    cancel = next(
        t for t in evaluation.allowed_transitions
        if t.gate == LifecycleGate.CANCEL
    )
    assert cancel.allowed is True
