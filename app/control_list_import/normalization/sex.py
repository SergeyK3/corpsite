"""Sex normalization (WP-CL-004)."""
from __future__ import annotations

import re
from typing import Any

from app.control_list_import.domain.person_candidate import NormalizedSex
from app.control_list_import.normalization.strings import normalize_comparison_key, normalize_plain_string, to_raw_text

_MALE_TOKENS = frozenset({"м", "муж", "мужской", "male", "m"})
_FEMALE_TOKENS = frozenset({"ж", "жен", "женский", "female", "f"})
_TOKEN_CLEAN_RE = re.compile(r"[^a-zа-яё]")


def normalize_sex(value: Any) -> NormalizedSex:
    raw = to_raw_text(value)
    if not raw:
        return NormalizedSex(raw=None)

    text, _ = normalize_plain_string(value)
    key = normalize_comparison_key(text)
    if not key:
        return NormalizedSex(raw=raw or None)

    token = key.split()[0] if key.split() else key
    token = _TOKEN_CLEAN_RE.sub("", token)
    if token in _MALE_TOKENS:
        return NormalizedSex(raw=raw or None, code="M")
    if token in _FEMALE_TOKENS:
        return NormalizedSex(raw=raw or None, code="F")

    return NormalizedSex(raw=raw or None, code=None, issues=("sex_unrecognized_value",))
