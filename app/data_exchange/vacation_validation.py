"""Non-destructive validation for periods found in vacation-event evidence."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

_DATE = re.compile(r"\b(\d{2}[.]\d{2}[.]\d{4}|\d{4}-\d{2}-\d{2})\b")
_DAYS = re.compile(r"\b(\d{1,3})\s*(?:календарн\w*\s*)?дн\w*\b", re.I)


@dataclass(frozen=True)
class PeriodIssue:
    code: str
    raw_fragment: str
    proposed_value: str | None = None


def _date(value: str) -> date | None:
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try: return date.fromisoformat(value) if fmt == "%Y-%m-%d" else __import__("datetime").datetime.strptime(value, fmt).date()
        except ValueError: pass
    return None


def validate_period(raw: str) -> list[PeriodIssue]:
    text = " ".join(str(raw or "").split())
    dates = _DATE.findall(text); parsed = [_date(value) for value in dates]
    issues: list[PeriodIssue] = []
    if not dates: return [PeriodIssue("PERIOD_MISSING_OR_AMBIGUOUS", text)]
    if any(value is None for value in parsed): issues.append(PeriodIssue("PERIOD_DATE_INVALID", text))
    valid = [value for value in parsed if value]
    if len(valid) == 1: issues.append(PeriodIssue("PERIOD_INCOMPLETE", text))
    if len(valid) > 2: issues.append(PeriodIssue("MULTIPLE_PERIODS_REVIEW_REQUIRED", text))
    if len(valid) >= 2 and valid[1] < valid[0]: issues.append(PeriodIssue("PERIOD_END_BEFORE_START", text))
    duration = _DAYS.search(text)
    if len(valid) >= 2 and duration and valid[1] >= valid[0]:
        actual = (valid[1] - valid[0]).days + 1
        if actual != int(duration.group(1)): issues.append(PeriodIssue("PERIOD_DURATION_CONFLICT", text, f"{actual} days"))
    return issues
