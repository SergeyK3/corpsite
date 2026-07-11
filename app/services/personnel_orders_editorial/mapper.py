"""Editorial payload / serialization helpers (WP-PO-EDIT-002)."""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Dict, Mapping, Optional


def effective_text(override_text: Optional[str], generated_text: Optional[str]) -> str:
    return (override_text or "").strip() or (generated_text or "").strip()


def iso_datetime(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def iso_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def payload_dict(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return dict(parsed) if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def pick_payload_value(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return payload[key]
    return None


def build_item_ctx(item: Mapping[str, Any], employee_name: Optional[str]) -> Dict[str, Any]:
    payload = payload_dict(item.get("payload"))
    return {
        "item_type_code": item.get("item_type_code"),
        "employee_name": employee_name,
        "effective_date": iso_date(item.get("effective_date")),
        "org_unit_name": pick_payload_value(
            payload, "org_unit_name", "orgUnitName", "from_org_unit_name"
        ),
        "position_name": pick_payload_value(
            payload, "position_name", "positionName", "from_position_name"
        ),
        "to_org_unit_name": pick_payload_value(
            payload, "to_org_unit_name", "toOrgUnitName"
        ),
        "to_position_name": pick_payload_value(
            payload, "to_position_name", "toPositionName"
        ),
        "rate": pick_payload_value(payload, "employment_rate", "rate", "from_rate"),
        "to_rate": pick_payload_value(payload, "to_rate", "toRate", "employment_rate"),
        "concurrent_rate": pick_payload_value(
            payload, "concurrent_rate", "concurrentRate"
        ),
        "remaining_rate": pick_payload_value(
            payload, "remaining_rate", "remainingRate"
        ),
        "total_rate": pick_payload_value(payload, "total_rate", "totalRate"),
        "termination_reason": pick_payload_value(
            payload, "termination_reason", "terminationReason", "reason"
        ),
    }


def serialize_block(
    row: Mapping[str, Any],
    *,
    scope: str,
    editable: bool,
) -> Dict[str, Any]:
    override = row.get("override_text")
    generated = row.get("generated_text")
    out: Dict[str, Any] = {
        "block_id": int(row["block_id"]),
        "scope": scope,
        "order_item_id": int(row["order_item_id"]) if row.get("order_item_id") is not None else None,
        "locale": row["locale"],
        "block_type": row["block_type"],
        "generated_text": generated,
        "override_text": override,
        "effective_text": effective_text(override, generated),
        "generator_key": row.get("generator_key"),
        "generator_version": row.get("generator_version"),
        "source_fingerprint": row.get("source_fingerprint"),
        "review_status": row["review_status"],
        "basis_required": bool(row["basis_required"]) if row.get("basis_required") is not None else None,
        "editable": editable,
        "revision": int(row.get("revision") or 1),
        "generated_at": iso_datetime(row.get("generated_at")),
        "edited_at": iso_datetime(row.get("edited_at")),
        "edited_by_user_id": (
            int(row["edited_by_user_id"]) if row.get("edited_by_user_id") is not None else None
        ),
    }
    return out
