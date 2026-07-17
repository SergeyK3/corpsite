"""Date normalization (WP-CL-004)."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Optional

from app.control_list_import.domain.person_candidate import NormalizedBirthDate
from app.control_list_import.normalization.strings import to_raw_text

_DATE_TEXT_RE = re.compile(
    r"^(\d{1,2})[./\-](\d{1,2})[./\-](\d{2,4})$|^(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})$"
)


def _excel_serial_to_date(serial: float) -> Optional[date]:
    if serial <= 0:
        return None
    try:
        base = datetime(1899, 12, 30)
        return (base + timedelta(days=serial)).date()
    except (OverflowError, ValueError):
        return None


def _parse_text_date(text: str) -> tuple[Optional[date], tuple[str, ...]]:
    match = _DATE_TEXT_RE.match(text.strip())
    if not match:
        return None, ("birth_date_unrecognized_format",)

    if match.group(1):
        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
    else:
        year, month, day = int(match.group(4)), int(match.group(5)), int(match.group(6))

    if year < 100:
        year += 1900 if year >= 30 else 2000

    try:
        return date(year, month, day), ()
    except ValueError:
        return None, ("birth_date_invalid_calendar",)


def normalize_birth_date(value: Any) -> NormalizedBirthDate:
    if value is None:
        return NormalizedBirthDate(raw=None)

    if isinstance(value, datetime):
        return NormalizedBirthDate(raw=value.isoformat(), value=value.date())
    if isinstance(value, date):
        return NormalizedBirthDate(raw=value.isoformat(), value=value)

    raw = to_raw_text(value)
    if not raw:
        return NormalizedBirthDate(raw=None)

    issues: list[str] = []

    if isinstance(value, (int, float)):
        parsed = _excel_serial_to_date(float(value))
        if parsed is None:
            issues.append("birth_date_invalid_excel_serial")
            return NormalizedBirthDate(raw=raw, issues=tuple(issues))
        return NormalizedBirthDate(raw=raw, value=parsed)

    if re.fullmatch(r"\d+(?:\.\d+)?", raw.replace(" ", "")):
        parsed = _excel_serial_to_date(float(raw.replace(",", ".")))
        if parsed is not None:
            return NormalizedBirthDate(raw=raw, value=parsed)

    parsed, parse_issues = _parse_text_date(raw)
    issues.extend(parse_issues)
    if parsed is None and "birth_date_unrecognized_format" in parse_issues:
        issues.append("date_stored_as_text")

    return NormalizedBirthDate(
        raw=raw,
        value=parsed,
        issues=tuple(dict.fromkeys(issues)),
    )
