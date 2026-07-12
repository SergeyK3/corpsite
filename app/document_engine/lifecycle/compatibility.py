"""Compatibility harness — read/editorial vs lifecycle evaluation (UDE-011)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.document_engine.editorial.facade import DocumentEngineEditorialSnapshot
from app.document_engine.lifecycle.facade import DocumentEngineLifecycleSnapshot
from app.document_engine.read_services.facade import DocumentEngineReadSnapshot


@dataclass(frozen=True, slots=True)
class LifecycleCompatibilityDifference:
    path: str
    upstream_value: Any
    lifecycle_value: Any
    note: str | None = None


@dataclass(frozen=True, slots=True)
class LifecycleCompatibilityReport:
    workspace_reference: str
    differences: tuple[LifecycleCompatibilityDifference, ...]

    @property
    def is_compatible(self) -> bool:
        return not self.differences


def compare_snapshots_to_lifecycle(
    read_snapshot: DocumentEngineReadSnapshot,
    editorial_snapshot: DocumentEngineEditorialSnapshot,
    lifecycle_snapshot: DocumentEngineLifecycleSnapshot,
) -> LifecycleCompatibilityReport:
    workspace_ref = read_snapshot.document.document_id.value
    differences: list[LifecycleCompatibilityDifference] = []

    def add(path: str, upstream: Any, lifecycle: Any, note: str | None = None) -> None:
        if upstream != lifecycle:
            differences.append(
                LifecycleCompatibilityDifference(
                    path=path,
                    upstream_value=upstream,
                    lifecycle_value=lifecycle,
                    note=note,
                )
            )

    read_doc = read_snapshot.document
    edit_doc = editorial_snapshot.editorial
    add("document_kind", read_doc.document_kind, edit_doc.document_kind)
    add("lifecycle_state", read_doc.lifecycle_state, edit_doc.lifecycle_state)
    add("legacy_status", read_doc.legacy_status, edit_doc.legacy_status)

    evaluation = lifecycle_snapshot.evaluation
    if evaluation is not None:
        add(
            "evaluation.lifecycle_state",
            read_doc.lifecycle_state,
            evaluation.lifecycle.lifecycle_state,
        )
        add(
            "evaluation.archive_state",
            read_doc.archive_state,
            evaluation.lifecycle.archive_state,
        )
        add(
            "evaluation.void_kind",
            read_doc.void_kind,
            evaluation.lifecycle.void_kind,
        )
        add(
            "decision.current_state",
            read_doc.lifecycle_state,
            evaluation.decision.current_state,
        )

    if editorial_snapshot.official_draft is not None and lifecycle_snapshot.promotion_readiness is not None:
        add(
            "official_draft.item_count",
            editorial_snapshot.official_draft.item_count,
            len(read_snapshot.items),
        )

    return LifecycleCompatibilityReport(
        workspace_reference=workspace_ref,
        differences=tuple(differences),
    )


def build_lifecycle_compatibility_report(
    read_snapshot: DocumentEngineReadSnapshot,
) -> LifecycleCompatibilityReport:
    from app.document_engine.editorial.facade import DocumentEngineEditorialFacade
    from app.document_engine.lifecycle.facade import DocumentEngineLifecycleFacade

    editorial_snapshot = DocumentEngineEditorialFacade.from_read_snapshot(read_snapshot)
    lifecycle_snapshot = DocumentEngineLifecycleFacade.from_read_snapshot(read_snapshot)
    return compare_snapshots_to_lifecycle(
        read_snapshot,
        editorial_snapshot,
        lifecycle_snapshot,
    )


def format_lifecycle_compatibility_report(report: LifecycleCompatibilityReport) -> str:
    if report.is_compatible:
        return f"{report.workspace_reference}: lifecycle compatible with upstream snapshots"
    lines = [
        f"{report.workspace_reference}: {len(report.differences)} lifecycle difference(s)"
    ]
    for diff in report.differences:
        note = f" ({diff.note})" if diff.note else ""
        lines.append(
            f"  - {diff.path}: upstream={diff.upstream_value!r} "
            f"lifecycle={diff.lifecycle_value!r}{note}"
        )
    return "\n".join(lines)
