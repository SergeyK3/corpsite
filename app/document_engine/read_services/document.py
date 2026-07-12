"""Document read service (UDE-009)."""
from __future__ import annotations

from typing import Any, Mapping

from app.document_engine.adapters.personnel.read_adapter import PersonnelReadAdapter
from app.document_engine.adapters.personnel.views import PersonnelDocumentReadView, PersonnelReadBundle
from app.document_engine.read_models.document import DocumentMetadataReadModel, DocumentReadModel


class DocumentReadService:
    """Maps Personnel read adapter output → shared document read model."""

    @staticmethod
    def from_adapter_view(view: PersonnelDocumentReadView) -> DocumentReadModel:
        metadata = DocumentMetadataReadModel(
            order_number=view.metadata.order_number,
            order_date=view.metadata.order_date,
            order_type_code=view.metadata.order_type_code,
            source_mode=view.metadata.source_mode,
            legal_basis_article=view.metadata.legal_basis_article,
            basis_summary=view.metadata.basis_summary,
            comment=view.metadata.comment,
            created_by=view.metadata.created_by,
            created_at=view.metadata.created_at,
            updated_at=view.metadata.updated_at,
            archived_at=view.metadata.archived_at,
            archive_reason_code=view.metadata.archive_reason_code,
            archive_reason_text=view.metadata.archive_reason_text,
        )
        return DocumentReadModel(
            document_id=view.document_id,
            document_kind=view.document_kind,
            specialization=view.specialization,
            lifecycle_state=view.lifecycle_state,
            archive_state=view.archive_state,
            void_kind=view.void_kind,
            metadata=metadata,
            legacy_status=view.legacy_status,
            is_archived=view.is_archived,
        )

    @staticmethod
    def from_bundle(bundle: PersonnelReadBundle) -> DocumentReadModel:
        return DocumentReadService.from_adapter_view(bundle.document)

    @staticmethod
    def from_detail(
        detail: Mapping[str, Any],
        *,
        supplement: Mapping[str, Any] | None = None,
        editorial: Mapping[str, Any] | None = None,
        audit_items: list[Mapping[str, Any]] | None = None,
    ) -> DocumentReadModel:
        bundle = PersonnelReadAdapter.from_detail(
            detail,
            supplement=supplement,
            editorial=editorial,
            audit_items=audit_items,
        )
        return DocumentReadService.from_bundle(bundle)
