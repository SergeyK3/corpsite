"""Shared PO → UDE mapping helpers (read-only)."""
from __future__ import annotations

from typing import Any, Mapping, Optional

from app.document_engine.value_objects.identity import (
    DocumentId,
    DocumentKind,
    DocumentSpecialization,
)
from app.document_engine.value_objects.lifecycle import (
    ArchiveState,
    DocumentLifecycleState,
    VoidKind,
)
from app.document_engine.value_objects.localization import LocaleCode, StalenessState
from app.document_engine.value_objects.provenance import TextSourceType

PO_REVIEW_STATUS_TO_STALENESS = {
    "CURRENT": StalenessState.CURRENT,
    "STALE": StalenessState.STALE_FINGERPRINT_MISMATCH,
    "REVIEW_REQUIRED": StalenessState.REVIEW_REQUIRED,
    "GENERATION_FAILED": StalenessState.REVIEW_REQUIRED,
}


def document_id_from_order(order_id: int | str) -> DocumentId:
    return DocumentId(f"po:{int(order_id)}")


def parse_lifecycle_state(status: str | None) -> DocumentLifecycleState:
    normalized = str(status or "").strip().upper()
    return DocumentLifecycleState(normalized)


def parse_archive_state(*, is_archived: bool) -> ArchiveState:
    return ArchiveState.ARCHIVED if is_archived else ArchiveState.ACTIVE


def parse_void_kind(value: str | None) -> VoidKind | None:
    if value is None:
        return None
    normalized = str(value).strip().upper()
    if not normalized:
        return None
    return VoidKind(normalized)


def parse_locale_code(locale: str | None) -> LocaleCode:
    normalized = str(locale or "").strip().lower()
    return LocaleCode(normalized)


def parse_staleness_state(review_status: str | None) -> StalenessState:
    normalized = str(review_status or "CURRENT").strip().upper()
    return PO_REVIEW_STATUS_TO_STALENESS.get(normalized, StalenessState.CURRENT)


def parse_text_source_type(
    *,
    override_text: str | None,
    generated_text: str | None,
    is_authoritative_legacy: bool | None = None,
) -> TextSourceType:
    if str(override_text or "").strip():
        return TextSourceType.OVERRIDE
    if str(generated_text or "").strip():
        return TextSourceType.GENERATED
    if is_authoritative_legacy is True:
        return TextSourceType.SUBMITTED
    return TextSourceType.GENERATED


def personnel_document_kind() -> DocumentKind:
    return DocumentKind.PERSONNEL_ORDER


def personnel_specialization(order_class: str | None = None) -> DocumentSpecialization:
    normalized = str(order_class or "PERSONNEL").strip().upper()
    if normalized == "OPERATIONAL":
        return DocumentSpecialization.OPERATIONAL
    return DocumentSpecialization.PERSONNEL


def optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def payload_dict(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def infer_display_item_type(item_type_code: str, payload: Mapping[str, Any]) -> str:
    """UI alias: TRANSFER with rate-only payload reads as RATE_CHANGE."""
    normalized = str(item_type_code or "").strip().upper()
    if normalized != "TRANSFER":
        return normalized
    body = payload_dict(payload)
    has_to_rate = body.get("to_rate") is not None or body.get("toRate") is not None
    has_placement_change = any(
        body.get(key) is not None
        for key in (
            "to_org_unit_name",
            "toOrgUnitName",
            "to_position_name",
            "toPositionName",
            "org_unit_name",
            "position_name",
        )
    )
    if has_to_rate and not has_placement_change:
        return "RATE_CHANGE"
    return normalized


def merge_supplement(
    header: Mapping[str, Any],
    supplement: Mapping[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(header)
    if supplement:
        merged.update(supplement)
    return merged
