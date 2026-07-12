"""Personnel document read adapter (UDE-008)."""
from __future__ import annotations

from typing import Any, Mapping

from app.document_engine.adapters.personnel._mapping import (
    document_id_from_order,
    merge_supplement,
    optional_str,
    parse_archive_state,
    parse_lifecycle_state,
    parse_void_kind,
    personnel_document_kind,
    personnel_specialization,
)
from app.document_engine.adapters.personnel._supplement import void_kind_for_header
from app.document_engine.adapters.personnel.views import (
    PersonnelDocumentMetadataView,
    PersonnelDocumentReadView,
)


class PersonnelDocumentAdapter:
    """Maps PO order header dict → shared document read view."""

    @staticmethod
    def from_header(
        header: Mapping[str, Any],
        *,
        supplement: Mapping[str, Any] | None = None,
    ) -> PersonnelDocumentReadView:
        merged = merge_supplement(header, supplement)
        order_id = int(merged["order_id"])
        is_archived = bool(merged.get("is_archived"))
        lifecycle = parse_lifecycle_state(merged.get("status"))
        archive = parse_archive_state(is_archived=is_archived)
        void_kind = parse_void_kind(void_kind_for_header(dict(merged), dict(supplement or {})))

        metadata = PersonnelDocumentMetadataView(
            order_number=optional_str(merged.get("order_number")),
            order_date=optional_str(merged.get("order_date")),
            order_type_code=str(merged.get("order_type_code") or ""),
            source_mode=str(merged.get("source_mode") or ""),
            legal_basis_article=optional_str(merged.get("legal_basis_article")),
            basis_summary=optional_str(merged.get("basis_summary")),
            comment=optional_str(merged.get("comment")),
            created_by=int(merged["created_by"]) if merged.get("created_by") is not None else None,
            created_at=optional_str(merged.get("created_at")),
            updated_at=optional_str(merged.get("updated_at")),
            archived_at=optional_str(
                merged.get("archive_summary_at") or merged.get("archived_at")
            ),
            archive_reason_code=optional_str(merged.get("archive_reason_code")),
            archive_reason_text=optional_str(
                merged.get("archive_summary_reason") or merged.get("archive_reason_text")
            ),
        )

        return PersonnelDocumentReadView(
            document_id=document_id_from_order(order_id),
            document_kind=personnel_document_kind(),
            specialization=personnel_specialization(merged.get("order_class")),
            lifecycle_state=lifecycle,
            archive_state=archive,
            void_kind=void_kind,
            metadata=metadata,
            legacy_status=str(merged.get("status") or ""),
            is_archived=is_archived,
        )
