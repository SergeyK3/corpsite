"""Compatibility harness — adapter bundle vs read service snapshot (UDE-009)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.document_engine.adapters.personnel.views import PersonnelReadBundle
from app.document_engine.read_services.facade import DocumentEngineReadSnapshot


@dataclass(frozen=True, slots=True)
class ReadServiceCompatibilityDifference:
    path: str
    adapter_value: Any
    read_service_value: Any
    note: str | None = None


@dataclass(frozen=True, slots=True)
class ReadServiceCompatibilityReport:
    order_id: int
    differences: tuple[ReadServiceCompatibilityDifference, ...]

    @property
    def is_compatible(self) -> bool:
        return not self.differences


def compare_bundle_to_read_snapshot(
    bundle: PersonnelReadBundle,
    snapshot: DocumentEngineReadSnapshot,
) -> ReadServiceCompatibilityReport:
    order_id = int(bundle.document.document_id.value.split(":")[-1])
    differences: list[ReadServiceCompatibilityDifference] = []

    def add(path: str, adapter: Any, read_service: Any, note: str | None = None) -> None:
        if adapter != read_service:
            differences.append(
                ReadServiceCompatibilityDifference(
                    path=path,
                    adapter_value=adapter,
                    read_service_value=read_service,
                    note=note,
                )
            )

    doc = bundle.document
    read_doc = snapshot.document
    add("document_id", doc.document_id, read_doc.document_id)
    add("lifecycle_state", doc.lifecycle_state, read_doc.lifecycle_state)
    add("archive_state", doc.archive_state, read_doc.archive_state)
    add("void_kind", doc.void_kind, read_doc.void_kind)
    add("legacy_status", doc.legacy_status, read_doc.legacy_status)
    add("is_archived", doc.is_archived, read_doc.is_archived)

    lifecycle = snapshot.lifecycle
    add("lifecycle.document_id", doc.document_id, lifecycle.document_id)
    add("lifecycle.lifecycle_state", doc.lifecycle_state, lifecycle.lifecycle_state)
    add("lifecycle.archive_state", doc.archive_state, lifecycle.archive_state)
    add("lifecycle.void_kind", doc.void_kind, lifecycle.void_kind)

    add("item_count", len(bundle.items), len(snapshot.items))
    add("locale_block_count", len(bundle.locale_blocks), len(snapshot.locale.blocks))
    add(
        "locale_snapshot_count",
        len(bundle.locale_snapshots),
        len(snapshot.locale.snapshots),
    )
    add(
        "audit_event_count",
        len(bundle.audit_events),
        len(snapshot.audit.events) if snapshot.audit else 0,
    )
    print_records = len(bundle.print_view.records) if bundle.print_view else 0
    read_print_records = len(snapshot.print_view.records) if snapshot.print_view else 0
    add("print_record_count", print_records, read_print_records)

    for index, item in enumerate(bundle.items):
        if index >= len(snapshot.items):
            break
        read_item = snapshot.items[index]
        add(
            f"items[{index}].backend_item_type_code",
            item.backend_item_type_code,
            read_item.backend_item_type_code,
        )
        add(
            f"items[{index}].display_item_type_code",
            item.display_item_type_code,
            read_item.display_item_type_code,
        )
        add(
            f"items[{index}].event_subject",
            item.event_subject,
            read_item.event_subject,
        )

    for index, block in enumerate(bundle.locale_blocks):
        if index >= len(snapshot.locale.blocks):
            break
        read_block = snapshot.locale.blocks[index]
        add(f"locale.blocks[{index}].effective_text", block.effective_text, read_block.effective_text)
        add(f"locale.blocks[{index}].text_source_type", block.text_source_type, read_block.text_source_type)
        add(f"locale.blocks[{index}].staleness_state", block.staleness_state, read_block.staleness_state)

    return ReadServiceCompatibilityReport(order_id=order_id, differences=tuple(differences))


def format_read_service_compatibility_report(report: ReadServiceCompatibilityReport) -> str:
    if report.is_compatible:
        return f"order {report.order_id}: read service compatible with adapter"
    lines = [
        f"order {report.order_id}: {len(report.differences)} read service difference(s)"
    ]
    for diff in report.differences:
        note = f" ({diff.note})" if diff.note else ""
        lines.append(
            f"  - {diff.path}: adapter={diff.adapter_value!r} "
            f"read_service={diff.read_service_value!r}{note}"
        )
    return "\n".join(lines)
