"""Lifecycle read service (UDE-009)."""
from __future__ import annotations

from typing import Any, Mapping

from app.document_engine.adapters.personnel.lifecycle import PersonnelLifecycleAdapter
from app.document_engine.adapters.personnel.views import PersonnelDocumentReadView, PersonnelReadBundle
from app.document_engine.read_models.lifecycle import LifecycleReadModel
from app.document_engine.adapters.personnel._mapping import document_id_from_order


class LifecycleReadService:
    """Maps Personnel lifecycle adapter output → shared lifecycle read model."""

    @staticmethod
    def from_header(
        header: Mapping[str, Any],
        *,
        supplement: Mapping[str, Any] | None = None,
    ) -> LifecycleReadModel:
        order_id = int(header["order_id"])
        is_archived = bool(header.get("is_archived"))
        return LifecycleReadModel(
            document_id=document_id_from_order(order_id),
            lifecycle_state=PersonnelLifecycleAdapter.lifecycle_state(header),
            archive_state=PersonnelLifecycleAdapter.archive_state(header),
            void_kind=PersonnelLifecycleAdapter.void_kind(header, supplement=supplement),
            legacy_status=str(header.get("status") or ""),
            is_archived=is_archived,
        )

    @staticmethod
    def from_adapter_view(view: PersonnelDocumentReadView) -> LifecycleReadModel:
        return LifecycleReadModel(
            document_id=view.document_id,
            lifecycle_state=view.lifecycle_state,
            archive_state=view.archive_state,
            void_kind=view.void_kind,
            legacy_status=view.legacy_status,
            is_archived=view.is_archived,
        )

    @staticmethod
    def from_bundle(bundle: PersonnelReadBundle) -> LifecycleReadModel:
        return LifecycleReadService.from_adapter_view(bundle.document)
