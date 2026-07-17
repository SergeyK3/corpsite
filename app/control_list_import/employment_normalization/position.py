"""Position title normalization (WP-CL-006)."""
from __future__ import annotations

from typing import Any

from app.control_list_import.domain.person_candidate import NormalizedPlainText
from app.control_list_import.normalization.strings import normalize_plain_string, to_raw_text


def normalize_position_title(value: Any) -> NormalizedPlainText:
    raw = to_raw_text(value)
    if not raw:
        return NormalizedPlainText(raw=None)

    text, issues = normalize_plain_string(value)
    return NormalizedPlainText(raw=raw, text=text, issues=issues)
