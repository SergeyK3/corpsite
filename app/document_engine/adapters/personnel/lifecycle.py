"""Personnel lifecycle read adapter (UDE-008)."""
from __future__ import annotations

from typing import Any, Mapping

from app.document_engine.adapters.personnel._mapping import (
    parse_archive_state,
    parse_lifecycle_state,
    parse_void_kind,
)
from app.document_engine.adapters.personnel._supplement import void_kind_for_header
from app.document_engine.value_objects.lifecycle import (
    ArchiveState,
    DocumentLifecycleState,
    VoidKind,
)


class PersonnelLifecycleAdapter:
    """Maps PO lifecycle fields → shared lifecycle contracts."""

    @staticmethod
    def lifecycle_state(header: Mapping[str, Any]) -> DocumentLifecycleState:
        return parse_lifecycle_state(header.get("status"))

    @staticmethod
    def archive_state(header: Mapping[str, Any]) -> ArchiveState:
        return parse_archive_state(is_archived=bool(header.get("is_archived")))

    @staticmethod
    def void_kind(
        header: Mapping[str, Any],
        *,
        supplement: Mapping[str, Any] | None = None,
    ) -> VoidKind | None:
        raw = void_kind_for_header(dict(header), dict(supplement or {}))
        return parse_void_kind(raw)
