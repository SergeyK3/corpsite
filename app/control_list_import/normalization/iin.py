"""IIN normalization (WP-CL-004)."""
from __future__ import annotations

import re
from typing import Any

from app.control_list_import.domain.person_candidate import NormalizedIin
from app.control_list_import.normalization.strings import to_raw_text


def normalize_iin(value: Any) -> NormalizedIin:
    raw = to_raw_text(value)
    if not raw and value is None:
        return NormalizedIin(raw=None)

    issues: list[str] = []
    digits = ""

    if isinstance(value, bool):
        issues.append("iin_contains_non_digits")
    elif isinstance(value, int):
        digits = str(abs(value))
        issues.append("iin_stored_as_number")
    elif isinstance(value, float):
        issues.append("iin_stored_as_number")
        if value > 1e11:
            issues.append("iin_possible_precision_loss")
        digits = re.sub(r"\D", "", f"{value:.0f}")
    else:
        text = raw
        if text and re.search(r"\.0+\s*$", text.replace(" ", "")):
            issues.append("iin_stored_as_number")
        if text and not re.sub(r"[\s.\-]", "", text).isdigit() and re.search(r"[A-Za-zА-Яа-я]", text):
            issues.append("iin_contains_non_digits")
        digits = re.sub(r"\D", "", text)

    if not digits:
        return NormalizedIin(raw=raw or None, issues=tuple(dict.fromkeys(issues)))

    if len(digits) == 11:
        digits = f"0{digits}"

    if len(digits) != 12:
        issues.append("iin_not_12_digits")
        return NormalizedIin(raw=raw or None, digits=None, issues=tuple(dict.fromkeys(issues)))

    return NormalizedIin(
        raw=raw or None,
        digits=digits,
        issues=tuple(dict.fromkeys(issues)),
    )
