"""Runtime aggregate factory (UDE-012)."""
from __future__ import annotations

from app.document_engine.editorial.editorial_models import OfficialDraftSnapshot
from app.document_engine.lifecycle.activation_service import ActivationService
from app.document_engine.value_objects.identity import DocumentId
from app.document_engine.value_objects.lifecycle import ArchiveState, DocumentLifecycleState
from app.document_engine.write.aggregate_models import AggregateMetadata, DocumentAggregate
from app.document_engine.write.domain_events import DocumentActivated, DocumentPromoted


class AggregateFactory:
    """Creates runtime DocumentAggregate from OfficialDraftSnapshot — no persistence."""

    @staticmethod
    def document_id_from_workspace(workspace_reference: str) -> DocumentId:
        normalized = str(workspace_reference or "").strip().replace(":", "-")
        return DocumentId(f"doc:{normalized}")

    @staticmethod
    def from_official_draft(draft: OfficialDraftSnapshot) -> DocumentAggregate:
        activation = ActivationService.evaluate(draft)
        document_id = AggregateFactory.document_id_from_workspace(draft.workspace_reference)
        metadata = AggregateMetadata(
            order_type_code=draft.order_type_code,
            order_number=str(draft.draft_metadata.get("order_number") or "") or None,
            order_date=str(draft.draft_metadata.get("order_date") or "") or None,
            source_mode=str(draft.draft_metadata.get("source_mode") or "") or None,
            legal_basis_article=str(draft.draft_metadata.get("legal_basis_article") or "") or None,
            basis_summary=str(draft.draft_metadata.get("basis_summary") or "") or None,
            workspace_reference=draft.workspace_reference,
            extra=dict(draft.draft_metadata),
        )
        return DocumentAggregate(
            document_id=document_id,
            document_kind=draft.document_kind,
            specialization=draft.specialization,
            lifecycle_state=DocumentLifecycleState.DRAFT,
            archive_state=ArchiveState.ACTIVE,
            void_kind=None,
            metadata=metadata,
            locale_blocks=draft.locale_blocks,
            official_draft=draft,
            item_count=draft.item_count,
            validation_state=activation.validation,
        )

    @staticmethod
    def activation_events(aggregate: DocumentAggregate) -> tuple[DocumentActivated, DocumentPromoted]:
        workspace = aggregate.metadata.workspace_reference or aggregate.document_id.value
        return (
            DocumentActivated(
                document_id=aggregate.document_id,
                workspace_reference=workspace,
                lifecycle_state=DocumentLifecycleState.DRAFT,
            ),
            DocumentPromoted(
                document_id=aggregate.document_id,
                workspace_reference=workspace,
            ),
        )
