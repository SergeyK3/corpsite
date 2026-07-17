"""Address line normalization (WP-CL-007)."""
from __future__ import annotations

from typing import Any

from app.control_list_import.domain.person_candidate import NormalizedPlainText
from app.control_list_import.normalization.strings import normalize_comparison_key, normalize_plain_string, to_raw_text

_TECHNICAL_EMPTY_KEYS = frozenset(
    {
        "-",
        "—",
        "–",
        "нет",
        "не указан",
        "не указано",
        "отсутствует",
        "н/д",
        "н.д.",
        "n/a",
        "na",
        "none",
        "null",
    }
)


def _is_technical_empty(value: str) -> bool:
    key = normalize_comparison_key(value)
    return key in _TECHNICAL_EMPTY_KEYS if key else False


def normalize_contact_address(value: Any) -> NormalizedPlainText:
    raw = to_raw_text(value)
    if not raw:
        return NormalizedPlainText(raw=None)

    if _is_technical_empty(raw):
        return NormalizedPlainText(raw=raw, issues=("contact_address_technical_empty",))

    text, issues = normalize_plain_string(value)
    if not text:
        return NormalizedPlainText(raw=raw or None)

    return NormalizedPlainText(raw=raw, text=text, issues=issues)
