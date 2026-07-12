"""Print runtime read models (UDE-009)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

from app.document_engine.value_objects.lifecycle import ArchiveState, DocumentLifecycleState
from app.document_engine.value_objects.localization import LocaleCode


@dataclass(frozen=True, slots=True)
class PrintRecordReadModel:
    print_id: int
    order_id: int
    locale: LocaleCode
    format: str
    file_path: str | None
    file_url: str | None
    is_signed_copy: bool
    render_version: int
    generated_at: str | None


@dataclass(frozen=True, slots=True)
class PrintReadModel:
    order_id: int
    lifecycle_state: DocumentLifecycleState
    archive_state: ArchiveState
    status_mark: str
    printable: bool
    records: Tuple[PrintRecordReadModel, ...] = field(default_factory=tuple)
