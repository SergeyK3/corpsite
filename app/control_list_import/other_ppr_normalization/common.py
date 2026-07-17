"""Shared helpers for other PPR field normalization (WP-CL-010)."""
from __future__ import annotations

from typing import Any

from app.control_list_import.domain.other_ppr_candidate import NormalizedScalarValue
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


def preserve_raw_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.replace("\r\n", "\n").replace("\r", "\n")
    return str(value)


def is_technical_empty_value(value: Any) -> bool:
    raw = to_raw_text(value)
    if not raw:
        return True
    key = normalize_comparison_key(raw)
    return key in _TECHNICAL_EMPTY_KEYS if key else False


def normalize_plain_scalar(value: Any) -> NormalizedScalarValue:
    raw = preserve_raw_value(value)
    if is_technical_empty_value(raw):
        return NormalizedScalarValue(raw=raw or None, issues=("other_ppr_technical_empty",))

    text, issues = normalize_plain_string(raw)
    if not text:
        return NormalizedScalarValue(raw=raw or None, issues=issues or ("other_ppr_empty_after_normalization",))
    return NormalizedScalarValue(raw=raw, text=text, issues=issues)


def normalize_alias_scalar(
    value: Any,
    *,
    aliases: dict[str, tuple[str, str]],
    ambiguous_issue: str,
    unmapped_issue: str | None = None,
    code_on_exact_match_only: bool = False,
) -> NormalizedScalarValue:
    raw = preserve_raw_value(value)
    if is_technical_empty_value(raw):
        return NormalizedScalarValue(raw=raw or None, issues=("other_ppr_technical_empty",))

    key = normalize_comparison_key(raw)
    if not key:
        return NormalizedScalarValue(raw=raw or None, issues=("other_ppr_empty_after_normalization",))

    if key in aliases:
        text, code = aliases[key]
        return NormalizedScalarValue(raw=raw, text=text, code=code)

    for alias_key, (text, code) in aliases.items():
        if alias_key in key or key in alias_key:
            if code_on_exact_match_only:
                return NormalizedScalarValue(raw=raw, text=text, issues=(ambiguous_issue,))
            return NormalizedScalarValue(raw=raw, text=text, code=code, issues=(ambiguous_issue,))

    text, issues = normalize_plain_string(raw)
    if text and unmapped_issue:
        return NormalizedScalarValue(raw=raw, text=text, issues=(unmapped_issue,))
    if text:
        return NormalizedScalarValue(raw=raw, text=text, issues=issues)
    return NormalizedScalarValue(raw=raw or None, issues=issues or (unmapped_issue or ambiguous_issue,))
