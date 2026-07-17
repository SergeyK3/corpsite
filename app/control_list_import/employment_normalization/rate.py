"""Employment rate normalization (WP-CL-006)."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from app.control_list_import.domain.employment_candidate import NormalizedRate
from app.control_list_import.normalization.strings import to_raw_text

_RATE_RE = re.compile(r"^\d+(?:[.,]\d+)?$")


def normalize_employment_rate(value: Any) -> NormalizedRate:
    if value is None:
        return NormalizedRate(raw=None)

    if isinstance(value, (int, float, Decimal)):
        raw = str(value)
    else:
        raw = to_raw_text(value)

    if not raw:
        return NormalizedRate(raw=None)

    normalized_text = raw.replace(" ", "").replace(",", ".")
    if not _RATE_RE.match(normalized_text):
        return NormalizedRate(raw=raw, issues=("employment_rate_unrecognized_format",))

    try:
        parsed = Decimal(normalized_text)
    except InvalidOperation:
        return NormalizedRate(raw=raw, issues=("employment_rate_unrecognized_format",))

    if parsed <= 0 or parsed > 2:
        return NormalizedRate(raw=raw, issues=("employment_rate_out_of_range",))

    return NormalizedRate(raw=raw, value=parsed)
