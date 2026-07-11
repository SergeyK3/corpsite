"""Stable fingerprint helpers for editorial source payloads (WP-PO-EDIT-002)."""
from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(obj: Any, *, exclude_none: bool = True) -> str:
    """Serialize ``obj`` with sorted keys for stable hashing.

    When ``exclude_none`` is True (default), ``None`` values are omitted from
    dicts so optional missing fields do not change the fingerprint.
    """

    def _normalize(value: Any) -> Any:
        if isinstance(value, dict):
            items = []
            for key in sorted(value.keys(), key=lambda k: str(k)):
                normalized = _normalize(value[key])
                if exclude_none and normalized is None:
                    continue
                items.append((str(key), normalized))
            return dict(items)
        if isinstance(value, (list, tuple)):
            return [_normalize(item) for item in value]
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, float):
            return value
        if value is None:
            return None
        return value

    return json.dumps(
        _normalize(obj),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    )


def compute_fingerprint(payload: dict[str, Any]) -> str:
    """SHA-256 hex digest of the canonical JSON form of ``payload``.

    Callers should include ``generator_key`` and ``generator_version`` in the
    payload so generator upgrades invalidate stored fingerprints.
    """
    if not isinstance(payload, dict):
        raise TypeError("fingerprint payload must be a dict")
    encoded = canonical_json(payload).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
