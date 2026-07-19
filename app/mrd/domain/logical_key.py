"""Logical key helpers for Detected Difference identity (ADR-058)."""
from __future__ import annotations

from datetime import date


def build_logical_key(
    *,
    report_period: date,
    mrd_id: int,
    entity_scope: str,
    attribute: str,
    record_kind: str | None = None,
) -> str:
    period_token = report_period.isoformat()
    kind_token = (record_kind or "").strip()
    return f"{period_token}|{mrd_id}|{entity_scope.strip()}|{attribute.strip()}|{kind_token}"


def candidate_signature(*, new_value: object | None, old_value: object | None = None) -> str:
    """Stable compare fingerprint for reconcile same-candidate detection."""
    import json

    payload = {"old": old_value, "new": new_value}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
