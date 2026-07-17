"""Phone normalization (WP-CL-004)."""
from __future__ import annotations

import re
from typing import Any

from app.control_list_import.domain.person_candidate import NormalizedPhone
from app.control_list_import.normalization.strings import to_raw_text


def normalize_phone(value: Any) -> NormalizedPhone:
    raw = to_raw_text(value)
    if not raw and value is None:
        return NormalizedPhone(raw=None)

    issues: list[str] = []

    if isinstance(value, bool):
        return NormalizedPhone(raw=raw or None, issues=("phone_invalid_length",))

    if isinstance(value, (int, float)):
        issues.append("phone_stored_as_number")
        digits = re.sub(r"\D", "", str(int(value)))
    else:
        digits = re.sub(r"\D", "", raw)

    if not digits:
        return NormalizedPhone(raw=raw or None, issues=tuple(issues))

    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]

    if len(digits) not in (10, 11, 12):
        issues.append("phone_invalid_length")
        return NormalizedPhone(raw=raw or None, digits=None, issues=tuple(dict.fromkeys(issues)))

    return NormalizedPhone(
        raw=raw or None,
        digits=digits,
        issues=tuple(dict.fromkeys(issues)),
    )
