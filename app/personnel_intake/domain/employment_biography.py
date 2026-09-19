"""Canonical, backwards-compatible intake employment-biography payloads."""
from __future__ import annotations

import json
from datetime import date
from typing import Any
from uuid import UUID, uuid5

_LEGACY_RECORD_NAMESPACE = UUID("3ba45a2d-b6b5-42f1-a0f0-46e033298e5f")
_VERIFICATION_STATUSES = {"unverified", "requires_review", "verified", "rejected"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _nullable_text(value: Any) -> str | None:
    return _text(value) or None


def _record_id(item: dict[str, Any], index: int) -> str:
    value = _text(item.get("record_id"))
    try:
        return str(UUID(value))
    except ValueError:
        # A deterministic id lets an old row be read repeatedly before its first save.
        fingerprint = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
        return str(uuid5(_LEGACY_RECORD_NAMESPACE, f"{index}:{fingerprint}"))


def _requires_surgical_review(position: str) -> bool:
    """A job title (and oncology training elsewhere in the payload) is not proof."""
    normalized = position.casefold().replace("-", " ")
    return "хирург" in normalized


def normalize_employment_biography_record(item: dict[str, Any], index: int) -> dict[str, Any]:
    """Read legacy fields, but always return the JSON-payload canonical shape."""
    organization_original = _text(item.get("organization_original") or item.get("organization"))
    position_original = _text(item.get("position_original") or item.get("position"))
    evidence = item.get("evidence_document_ids")
    evidence_document_ids = [str(value) for value in evidence if _text(value)] if isinstance(evidence, list) else []
    status = _text(item.get("verification_status")) or "unverified"
    if status not in _VERIFICATION_STATUSES:
        status = "unverified"
    # Generic evidence links are not a verified qualification document. Only an
    # explicit verifier decision may move a surgeon title past requires_review.
    if _requires_surgical_review(position_original) and status != "verified":
        status = "requires_review"
    return {
        "record_id": _record_id(item, index),
        "start_date": _nullable_text(item.get("start_date") if "start_date" in item else item.get("year_from")),
        "end_date": _nullable_text(item.get("end_date") if "end_date" in item else item.get("year_to")),
        "organization_original": organization_original,
        "organization_normalized": _nullable_text(item.get("organization_normalized")),
        "city": _nullable_text(item.get("city")),
        "position_original": position_original,
        "position_normalized": _nullable_text(item.get("position_normalized")),
        "reason_for_leaving": _nullable_text(item.get("reason_for_leaving")),
        "note": _nullable_text(item.get("note")),
        "verification_status": status,
        "evidence_document_ids": evidence_document_ids,
    }


def normalize_employment_biography_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Copy payload and canonicalize only employment rows; never substitute education."""
    result = dict(payload)
    raw = payload.get("employment_biography")
    result["employment_biography"] = [
        normalize_employment_biography_record(item, index)
        for index, item in enumerate(raw if isinstance(raw, list) else [])
        if isinstance(item, dict)
    ]
    return result


def employment_dates_are_ordered(record: dict[str, Any]) -> bool:
    start, end = record.get("start_date"), record.get("end_date")
    if not start or not end:
        return True
    try:
        return date.fromisoformat(start) <= date.fromisoformat(end)
    except ValueError:
        return True
