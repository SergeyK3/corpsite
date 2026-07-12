"""Compatibility harness — legacy PO view vs adapter view (UDE-008)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.document_engine.adapters.personnel.lifecycle import PersonnelLifecycleAdapter
from app.document_engine.adapters.personnel.read_adapter import PersonnelReadAdapter
from app.document_engine.adapters.personnel.views import PersonnelReadBundle


@dataclass(frozen=True, slots=True)
class CompatibilityDifference:
    path: str
    legacy_value: Any
    adapter_value: Any
    note: str | None = None


@dataclass(frozen=True, slots=True)
class CompatibilityReport:
    order_id: int
    differences: tuple[CompatibilityDifference, ...]

    @property
    def is_compatible(self) -> bool:
        return not self.differences


def compare_legacy_detail_to_adapter(
    detail: Mapping[str, Any],
    bundle: PersonnelReadBundle,
) -> CompatibilityReport:
    order = detail.get("order") or {}
    order_id = int(order.get("order_id") or bundle.document.metadata.order_number or 0)
    differences: list[CompatibilityDifference] = []

    def add(path: str, legacy: Any, adapter: Any, note: str | None = None) -> None:
        if legacy != adapter:
            differences.append(
                CompatibilityDifference(
                    path=path,
                    legacy_value=legacy,
                    adapter_value=adapter,
                    note=note,
                )
            )

    add("order_id", int(order.get("order_id")), int(bundle.document.document_id.value.split(":")[-1]))
    add("status", order.get("status"), bundle.document.lifecycle_state.value)
    add("is_archived", bool(order.get("is_archived")), bundle.document.is_archived)
    add(
        "archive_state",
        "ARCHIVED" if order.get("is_archived") else "ACTIVE",
        bundle.document.archive_state.value,
    )
    add(
        "lifecycle_enum",
        order.get("status"),
        PersonnelLifecycleAdapter.lifecycle_state(order).value,
    )
    add("item_count", len(detail.get("items") or []), len(bundle.items))
    add(
        "localized_text_count",
        len(detail.get("localized_texts") or []),
        len(bundle.locale_snapshots),
    )
    add("print_count", len(detail.get("prints") or []), len(bundle.print_view.records if bundle.print_view else ()))

    for index, item in enumerate(detail.get("items") or []):
        if index >= len(bundle.items):
            break
        adapted = bundle.items[index]
        add(f"items[{index}].item_type_code", item.get("item_type_code"), adapted.backend_item_type_code)
        add(f"items[{index}].employee_id", item.get("employee_id"), (
            int(adapted.event_subject.reference) if adapted.event_subject else None
        ))

    return CompatibilityReport(order_id=order_id, differences=tuple(differences))


def build_compatibility_report(
    detail: Mapping[str, Any],
    *,
    supplement: Mapping[str, Any] | None = None,
    editorial: Mapping[str, Any] | None = None,
    audit_items: Sequence[Mapping[str, Any]] | None = None,
) -> CompatibilityReport:
    bundle = PersonnelReadAdapter.from_detail(
        detail,
        supplement=supplement,
        editorial=editorial,
        audit_items=list(audit_items) if audit_items is not None else None,
    )
    return compare_legacy_detail_to_adapter(detail, bundle)


def format_compatibility_report(report: CompatibilityReport) -> str:
    if report.is_compatible:
        return f"order {report.order_id}: compatible"
    lines = [f"order {report.order_id}: {len(report.differences)} difference(s)"]
    for diff in report.differences:
        note = f" ({diff.note})" if diff.note else ""
        lines.append(
            f"  - {diff.path}: legacy={diff.legacy_value!r} adapter={diff.adapter_value!r}{note}"
        )
    return "\n".join(lines)
