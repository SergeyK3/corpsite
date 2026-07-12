"""Operational Orders domain helpers."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from app.document_engine import PartyReference, PartyReferenceType, TextSourceType


def normalize_party_reference(
    *,
    reference_type: str,
    reference: str,
    display_name: str | None = None,
) -> PartyReference:
    return PartyReference(
        reference_type=PartyReferenceType(str(reference_type).strip().upper()),
        reference=str(reference).strip(),
        display_name=(str(display_name).strip() or None) if display_name else None,
    )


def party_to_row(party: PartyReference) -> dict[str, str | None]:
    return {
        "reference_type": party.reference_type.value,
        "reference": party.reference,
        "display_name": party.display_name,
    }


def normalize_text_source(source_type: str) -> str:
    normalized = str(source_type or "").strip().upper()
    allowed = {member.value for member in TextSourceType}
    if normalized not in allowed:
        raise ValueError(f"Invalid source_type: {source_type}")
    return normalized


def content_fingerprint(text: str) -> str:
    payload = str(text or "").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def json_safe(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return json.loads(json.dumps(dict(value), default=str))
