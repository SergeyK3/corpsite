"""Field-specific conservative normalizers for WP-CL-010."""
from __future__ import annotations

from typing import Any

from app.control_list_import.domain.other_ppr_candidate import NormalizedScalarValue
from app.control_list_import.other_ppr_normalization.common import (
    is_technical_empty_value,
    normalize_alias_scalar,
    normalize_plain_scalar,
    preserve_raw_value,
)
from app.control_list_import.normalization.strings import normalize_comparison_key, normalize_plain_string

_CITIZENSHIP_ALIASES: dict[str, tuple[str, str]] = {
    "казахстан": ("Казахстан", "KZ"),
    "казахстанская": ("Казахстан", "KZ"),
    "рк": ("Казахстан", "KZ"),
    "kz": ("Казахстан", "KZ"),
    "россия": ("Россия", "RU"),
    "российская": ("Россия", "RU"),
    "рф": ("Россия", "RU"),
    "ru": ("Россия", "RU"),
}

_MARITAL_ALIASES: dict[str, tuple[str, str]] = {
    "женат": ("Женат", "married"),
    "замужем": ("Замужем", "married"),
    "состоит в браке": ("Состоит в браке", "married"),
    "холост": ("Холост", "single"),
    "не замужем": ("Не замужем", "single"),
    "не женат": ("Не женат", "single"),
    "разведен": ("Разведен(а)", "divorced"),
    "разведена": ("Разведен(а)", "divorced"),
    "вдовец": ("Вдовец", "widowed"),
    "вдова": ("Вдова", "widowed"),
    "не применимо": ("Не применимо", "not_applicable"),
}

_MILITARY_ALIASES: dict[str, tuple[str, str]] = {
    "не подлежит": ("Не подлежит воинскому учёту", "not_applicable"),
    "не подлежит воинскому учету": ("Не подлежит воинскому учёту", "not_applicable"),
    "не подлежит воинскому учёту": ("Не подлежит воинскому учёту", "not_applicable"),
    "не состоит": ("Не состоит на воинском учёте", "not_applicable"),
    "состоит на учете": ("Состоит на воинском учёте", "registered"),
    "состоит на учёте": ("Состоит на воинском учёте", "registered"),
    "военный билет": ("Состоит на воинском учёте", "registered"),
    "запас": ("Состоит на воинском учёте", "registered"),
}

_DISABILITY_ALIASES: dict[str, tuple[str, str]] = {
    "нет": ("Нет", "no"),
    "не имеет": ("Нет", "no"),
    "отсутствует": ("Нет", "no"),
    "да": ("Да", "yes"),
    "имеется": ("Да", "yes"),
    "инвалид": ("Да", "yes"),
    "не применимо": ("Не применимо", "not_applicable"),
    "н/п": ("Не применимо", "not_applicable"),
}


def normalize_citizenship(value: Any) -> NormalizedScalarValue:
    return normalize_alias_scalar(
        value,
        aliases=_CITIZENSHIP_ALIASES,
        ambiguous_issue="other_ppr_citizenship_ambiguous",
        unmapped_issue="other_ppr_citizenship_unmapped",
    )


def normalize_marital_status(value: Any) -> NormalizedScalarValue:
    return normalize_alias_scalar(
        value,
        aliases=_MARITAL_ALIASES,
        ambiguous_issue="other_ppr_marital_status_ambiguous",
        unmapped_issue="other_ppr_marital_status_unmapped",
        code_on_exact_match_only=True,
    )


def normalize_military_summary(value: Any) -> NormalizedScalarValue:
    raw = preserve_raw_value(value)
    if is_technical_empty_value(raw):
        return NormalizedScalarValue(raw=raw or None, issues=("other_ppr_technical_empty",))

    key = normalize_comparison_key(raw)
    if not key:
        return NormalizedScalarValue(raw=raw or None, issues=("other_ppr_military_summary_empty",))

    for alias_key, (text, code) in _MILITARY_ALIASES.items():
        if alias_key == key:
            return NormalizedScalarValue(raw=raw, text=text, code=code)

    for alias_key, (text, code) in _MILITARY_ALIASES.items():
        if alias_key in key:
            return NormalizedScalarValue(raw=raw, text=text, issues=("other_ppr_military_summary_ambiguous",))

    text, issues = normalize_plain_string(raw)
    if text:
        return NormalizedScalarValue(
            raw=raw,
            text=text,
            issues=("other_ppr_military_summary_unparsed",),
        )
    return NormalizedScalarValue(raw=raw or None, issues=issues or ("other_ppr_military_summary_empty",))


def normalize_disability_summary(value: Any) -> NormalizedScalarValue:
    raw = preserve_raw_value(value)
    key = normalize_comparison_key(raw)
    if key and key in _DISABILITY_ALIASES:
        text, code = _DISABILITY_ALIASES[key]
        return NormalizedScalarValue(raw=raw, text=text, code=code)

    if is_technical_empty_value(raw):
        return NormalizedScalarValue(raw=raw or None, issues=("other_ppr_technical_empty",))

    if not key:
        return NormalizedScalarValue(raw=raw or None, issues=("other_ppr_empty_after_normalization",))

    for alias_key, (text, code) in _DISABILITY_ALIASES.items():
        if alias_key in key or key in alias_key:
            return NormalizedScalarValue(raw=raw, text=text, issues=("other_ppr_disability_summary_ambiguous",))

    text, issues = normalize_plain_string(raw)
    if text:
        return NormalizedScalarValue(raw=raw, text=text, issues=("other_ppr_disability_summary_unmapped",))
    return NormalizedScalarValue(raw=raw or None, issues=issues or ("other_ppr_disability_summary_unmapped",))


def normalize_nationality_raw(value: Any) -> NormalizedScalarValue:
    return normalize_plain_scalar(value)


def normalize_awards(value: Any) -> NormalizedScalarValue:
    return normalize_plain_scalar(value)


def normalize_notes(value: Any) -> NormalizedScalarValue:
    return normalize_plain_scalar(value)


def normalize_qualification_category(value: Any) -> NormalizedScalarValue:
    return normalize_plain_scalar(value)


def normalize_qualification_degree(value: Any) -> NormalizedScalarValue:
    return normalize_plain_scalar(value)


def normalize_unsupported_field(value: Any) -> NormalizedScalarValue:
    raw = preserve_raw_value(value)
    if is_technical_empty_value(raw):
        return NormalizedScalarValue(raw=raw or None, issues=("other_ppr_technical_empty",))
    text, _ = normalize_plain_string(raw)
    return NormalizedScalarValue(
        raw=raw,
        text=text,
        issues=("other_ppr_unsupported_semantic_field",),
    )
