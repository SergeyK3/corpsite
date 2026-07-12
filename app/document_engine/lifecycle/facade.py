"""Document engine lifecycle facade — single public entry point (UDE-011)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.document_engine.editorial.facade import (
    DocumentEngineEditorialFacade,
    DocumentEngineEditorialSnapshot,
)
from app.document_engine.lifecycle.activation_service import ActivationService
from app.document_engine.lifecycle.lifecycle_models import (
    ActivationDecision,
    LifecycleDecision,
    LifecycleEvaluation,
    PromotionReadiness,
    RegistrationReadiness,
)
from app.document_engine.lifecycle.lifecycle_service import LifecycleEvaluationService
from app.document_engine.lifecycle.promotion_policy import PromotionPolicy
from app.document_engine.lifecycle.registration_policy import RegistrationPolicy
from app.document_engine.read_models.lifecycle import LifecycleReadModel
from app.document_engine.read_services.facade import (
    DocumentEngineReadFacade,
    DocumentEngineReadSnapshot,
)


@dataclass(frozen=True, slots=True)
class DocumentEngineLifecycleSnapshot:
    activation: ActivationDecision | None = None
    evaluation: LifecycleEvaluation | None = None
    promotion_readiness: PromotionReadiness | None = None
    registration_readiness: RegistrationReadiness | None = None
    lifecycle_decision: LifecycleDecision | None = None


class DocumentEngineLifecycleFacade:
    """Aggregates activation and lifecycle evaluation behind a single entry point."""

    @staticmethod
    def _lifecycle_from_read_snapshot(read_snapshot: DocumentEngineReadSnapshot) -> LifecycleReadModel:
        document = read_snapshot.document
        return LifecycleReadModel(
            document_id=document.document_id,
            lifecycle_state=document.lifecycle_state,
            archive_state=document.archive_state,
            void_kind=document.void_kind,
            legacy_status=document.legacy_status,
            is_archived=document.is_archived,
        )

    @staticmethod
    def from_editorial_snapshot(
        editorial_snapshot: DocumentEngineEditorialSnapshot,
        read_snapshot: DocumentEngineReadSnapshot,
    ) -> DocumentEngineLifecycleSnapshot:
        draft = editorial_snapshot.official_draft
        lifecycle_model = DocumentEngineLifecycleFacade._lifecycle_from_read_snapshot(read_snapshot)

        evaluation = LifecycleEvaluationService.evaluate(
            editorial_snapshot.editorial,
            lifecycle_model,
            draft=draft,
        )
        activation = ActivationService.evaluate(draft) if draft is not None else None
        promotion = PromotionPolicy.evaluate(draft) if draft is not None else None
        registration = RegistrationPolicy.evaluate(lifecycle_model)

        return DocumentEngineLifecycleSnapshot(
            activation=activation,
            evaluation=evaluation,
            promotion_readiness=promotion,
            registration_readiness=registration,
            lifecycle_decision=evaluation.decision,
        )

    @staticmethod
    def from_read_snapshot(read_snapshot: DocumentEngineReadSnapshot) -> DocumentEngineLifecycleSnapshot:
        editorial_snapshot = DocumentEngineEditorialFacade.from_read_snapshot(read_snapshot)
        return DocumentEngineLifecycleFacade.from_editorial_snapshot(
            editorial_snapshot,
            read_snapshot,
        )

    @staticmethod
    def from_detail(
        detail: Mapping[str, Any],
        *,
        supplement: Mapping[str, Any] | None = None,
        editorial: Mapping[str, Any] | None = None,
        audit_items: list[Mapping[str, Any]] | None = None,
    ) -> DocumentEngineLifecycleSnapshot:
        read_snapshot = DocumentEngineReadFacade.from_detail(
            detail,
            supplement=supplement,
            editorial=editorial,
            audit_items=audit_items,
        )
        return DocumentEngineLifecycleFacade.from_read_snapshot(read_snapshot)
