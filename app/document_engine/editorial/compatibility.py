"""Compatibility harness — read model vs editorial model (UDE-010)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.document_engine.editorial.editorial_models import EditorialBlock
from app.document_engine.editorial.localization_service import LocalizationService
from app.document_engine.read_models.locale import LocaleBlockReadModel, LocaleReadModel
from app.document_engine.read_services.facade import DocumentEngineReadSnapshot
from app.document_engine.editorial.facade import DocumentEngineEditorialSnapshot


@dataclass(frozen=True, slots=True)
class EditorialCompatibilityDifference:
    path: str
    read_model_value: Any
    editorial_value: Any
    note: str | None = None


@dataclass(frozen=True, slots=True)
class EditorialCompatibilityReport:
    workspace_reference: str
    differences: tuple[EditorialCompatibilityDifference, ...]

    @property
    def is_compatible(self) -> bool:
        return not self.differences


def compare_locale_block_to_editorial(
    read_block: LocaleBlockReadModel,
    editorial_block: EditorialBlock,
) -> list[EditorialCompatibilityDifference]:
    differences: list[EditorialCompatibilityDifference] = []

    def add(path: str, read_value: Any, editorial_value: Any) -> None:
        if read_value != editorial_value:
            differences.append(
                EditorialCompatibilityDifference(
                    path=path,
                    read_model_value=read_value,
                    editorial_value=editorial_value,
                )
            )

    add("block_id", read_block.block_id, editorial_block.block_id)
    add("scope", read_block.scope, editorial_block.scope)
    add("order_item_id", read_block.order_item_id, editorial_block.order_item_id)
    add("locale", read_block.locale, editorial_block.locale)
    add("block_type", read_block.block_type, editorial_block.block_type)
    add("generated_text", read_block.generated_text, editorial_block.generated_text)
    add("override_text", read_block.override_text, editorial_block.override.override_text)
    add("effective_text", read_block.effective_text, editorial_block.effective_text)
    add("text_source_type", read_block.text_source_type, editorial_block.text_source_type)
    add("staleness_state", read_block.staleness_state, editorial_block.staleness_state)
    add("review_status→review_state", read_block.review_status, editorial_block.review_state.value)
    add("source_fingerprint", read_block.source_fingerprint, editorial_block.fingerprint.source_fingerprint)
    add("generator_key", read_block.generator_key, editorial_block.fingerprint.generator_key)
    add("generator_version", read_block.generator_version, editorial_block.fingerprint.generator_version)
    return differences


def compare_read_snapshot_to_editorial(
    read_snapshot: DocumentEngineReadSnapshot,
    editorial_snapshot: DocumentEngineEditorialSnapshot,
) -> EditorialCompatibilityReport:
    workspace_ref = read_snapshot.document.document_id.value
    differences: list[EditorialCompatibilityDifference] = []

    editorial_block_map = {
        block.block_id: block
        for locale in editorial_snapshot.editorial.locales
        for block in locale.blocks
    }
    add_count = len(read_snapshot.locale.blocks)
    if add_count != len(editorial_block_map):
        differences.append(
            EditorialCompatibilityDifference(
                path="block_count",
                read_model_value=add_count,
                editorial_value=len(editorial_block_map),
            )
        )

    for read_block in read_snapshot.locale.blocks:
        editorial_block = editorial_block_map.get(read_block.block_id)
        if editorial_block is None:
            differences.append(
                EditorialCompatibilityDifference(
                    path=f"blocks[{read_block.block_id}]",
                    read_model_value=read_block.block_id,
                    editorial_value=None,
                    note="missing editorial block",
                )
            )
            continue
        differences.extend(
            compare_locale_block_to_editorial(read_block, editorial_block)
        )

    read_doc = read_snapshot.document
    edit_doc = editorial_snapshot.editorial
    if read_doc.document_kind != edit_doc.document_kind:
        differences.append(
            EditorialCompatibilityDifference(
                path="document_kind",
                read_model_value=read_doc.document_kind,
                editorial_value=edit_doc.document_kind,
            )
        )
    if read_doc.lifecycle_state != edit_doc.lifecycle_state:
        differences.append(
            EditorialCompatibilityDifference(
                path="lifecycle_state",
                read_model_value=read_doc.lifecycle_state,
                editorial_value=edit_doc.lifecycle_state,
            )
        )

    official = editorial_snapshot.official_draft
    if official is not None:
        if official.item_count != len(read_snapshot.items):
            differences.append(
                EditorialCompatibilityDifference(
                    path="official_draft.item_count",
                    read_model_value=len(read_snapshot.items),
                    editorial_value=official.item_count,
                )
            )
        from dataclasses import fields

        if any(field.name == "document_id" for field in fields(official)):
            differences.append(
                EditorialCompatibilityDifference(
                    path="official_draft.document_id",
                    read_model_value=None,
                    editorial_value="present",
                    note="OfficialDraftSnapshot must not expose DocumentId",
                )
            )

    return EditorialCompatibilityReport(
        workspace_reference=workspace_ref,
        differences=tuple(differences),
    )


def build_editorial_compatibility_report(
    read_snapshot: DocumentEngineReadSnapshot,
) -> EditorialCompatibilityReport:
    from app.document_engine.editorial.facade import DocumentEngineEditorialFacade

    editorial_snapshot = DocumentEngineEditorialFacade.from_read_snapshot(read_snapshot)
    return compare_read_snapshot_to_editorial(read_snapshot, editorial_snapshot)


def format_editorial_compatibility_report(report: EditorialCompatibilityReport) -> str:
    if report.is_compatible:
        return f"{report.workspace_reference}: editorial compatible with read model"
    lines = [
        f"{report.workspace_reference}: {len(report.differences)} editorial difference(s)"
    ]
    for diff in report.differences:
        note = f" ({diff.note})" if diff.note else ""
        lines.append(
            f"  - {diff.path}: read={diff.read_model_value!r} "
            f"editorial={diff.editorial_value!r}{note}"
        )
    return "\n".join(lines)
