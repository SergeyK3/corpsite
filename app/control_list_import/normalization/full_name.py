"""Full name (FIO) normalization (WP-CL-004)."""
from __future__ import annotations

import re
from typing import Any

from app.control_list_import.domain.person_candidate import NormalizedFullName
from app.control_list_import.normalization.strings import normalize_comparison_key, normalize_plain_string, to_raw_text

_KAZAKH_UPPER = "ӘҒҚҢӨҰҮҺІ"
_FIO_RE = re.compile(
    rf"^[А-ЯЁ{_KAZAKH_UPPER}][а-яё{_KAZAKH_UPPER.lower()}a-z\-']+"
    rf"(?:\s+[А-ЯЁ{_KAZAKH_UPPER}][а-яё{_KAZAKH_UPPER.lower()}a-z\-']+){{1,3}}$"
)


def _title_token(token: str) -> str:
    if not token:
        return token
    parts = token.split("-")
    titled = []
    for part in parts:
        if not part:
            titled.append(part)
        elif len(part) == 1:
            titled.append(part.upper())
        else:
            titled.append(part[0].upper() + part[1:].lower())
    return "-".join(titled)


def normalize_full_name(value: Any) -> NormalizedFullName:
    raw = to_raw_text(value)
    if not raw:
        return NormalizedFullName(raw=None)

    display, issues_list = normalize_plain_string(value)
    issues: list[str] = list(issues_list)
    if not display:
        return NormalizedFullName(raw=raw or None, issues=tuple(issues))

    if any(ch.isdigit() for ch in display):
        issues.append("full_name_contains_digits")

    tokens = display.split()
    display = " ".join(_title_token(token) for token in tokens)
    normalized_key = normalize_comparison_key(display)

    if not _FIO_RE.match(display):
        issues.append("full_name_unrecognized_pattern")

    return NormalizedFullName(
        raw=raw or None,
        display=display,
        normalized_key=normalized_key,
        issues=tuple(dict.fromkeys(issues)),
    )
