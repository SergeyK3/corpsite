"""Strict, provenance-preserving parser for the control-list qualification category.

The source column carries free text.  This parser deliberately accepts only an
unambiguous category and complete date; it never promotes a year or a name into
a date/specialty.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import re

from app.services.hr_import_document_parser import split_raw_fragments

_CATEGORY_PATTERNS = (
    (re.compile(r"\bвысш\w*\b", re.IGNORECASE), "highest"),
    (re.compile(r"\bперв\w*\b", re.IGNORECASE), "first"),
    (re.compile(r"\bвтор\w*\b", re.IGNORECASE), "second"),
)
_EXPIRY_RE = re.compile(r"\bдо\s*(\d{2}\.\d{2}\.\d{4})\b", re.IGNORECASE)
_ISSUED_RE = re.compile(r"\b(?:от|присвоена?\s*(?:с|от)?)\s*(\d{2}\.\d{2}\.\d{4})\b", re.IGNORECASE)
_ORDINAL_RE = re.compile(r"^\s*\d+\s*[.)]\s*")


@dataclass(frozen=True)
class QualificationCategoryParse:
    specialty: str
    category: str
    assigned_at: str
    assigned_at_calculated: bool
    review_status: str
    review_reason: str | None
    fingerprint: str


def _subtract_five_years(value: date) -> date | None:
    try:
        return value.replace(year=value.year - 5)
    except ValueError:  # 29 February has no exact equivalent in a non-leap year.
        return None


def _specialty(fragment: str, category_match: re.Match[str]) -> str:
    # The control list's reliable specialty delimiter is a quoted value after
    # the category/date.  Never treat surrounding labels or a truncated token
    # as a specialty.
    tail = fragment[category_match.end():]
    quoted = re.search(r'["«]([^"»]+)["»]', tail)
    if quoted:
        return " ".join(quoted.group(1).split()).strip()
    # Unquoted values are not structurally delimited in this workbook.  A
    # conservative empty value is reviewable; a guessed remainder is not.
    return ""

def _legacy_specialty(fragment: str, category_match: re.Match[str]) -> str:
    value = _ORDINAL_RE.sub("", fragment)
    value = value[:category_match.start()] + " " + value[category_match.end():]
    value = _EXPIRY_RE.sub(" ", value)
    value = _ISSUED_RE.sub(" ", value)
    value = re.sub(r"\b(?:г\.?|год(?:а)?)\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\bквалификационн\w*\s+категор\w*\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"[,:;()]+", " ", value)
    return " ".join(value.split()).strip(".- ")


def parse_qualification_categories(raw: str) -> list[QualificationCategoryParse]:
    result: list[QualificationCategoryParse] = []
    for fragment in split_raw_fragments(str(raw or "")):
        matches = [(pattern.search(fragment), code) for pattern, code in _CATEGORY_PATTERNS]
        hits = [(match, code) for match, code in matches if match]
        if not hits:
            continue
        digest = hashlib.sha256(fragment.strip().encode("utf-8")).hexdigest()
        if len(hits) != 1:
            result.append(QualificationCategoryParse("", "", "", False, "REVIEW_REQUIRED", "CATEGORY_AMBIGUOUS_VALUE", digest))
            continue
        match, category = hits[0]
        specialty = _specialty(fragment, match)
        expiry = _EXPIRY_RE.search(fragment)
        issued = _ISSUED_RE.search(fragment)
        assigned_at = ""
        calculated = False
        reason: str | None = None
        if expiry:
            try:
                calculated_date = _subtract_five_years(date.fromisoformat(expiry.group(1)[6:10] + "-" + expiry.group(1)[3:5] + "-" + expiry.group(1)[:2]))
            except ValueError:
                calculated_date = None
            if calculated_date is None:
                reason = "CATEGORY_ASSIGNED_DATE_MISSING_OR_AMBIGUOUS"
            else:
                assigned_at, calculated = calculated_date.isoformat(), True
        elif issued:
            try:
                day, month, year = issued.group(1).split(".")
                assigned_at = date(int(year), int(month), int(day)).isoformat()
            except ValueError:
                reason = "CATEGORY_ASSIGNED_DATE_MISSING_OR_AMBIGUOUS"
        else:
            reason = "CATEGORY_ASSIGNED_DATE_MISSING_OR_AMBIGUOUS"
        if not specialty:
            reason = reason or "CATEGORY_MISSING_SPECIALTY"
        result.append(QualificationCategoryParse(
            specialty=specialty, category=category, assigned_at=assigned_at,
            assigned_at_calculated=calculated,
            review_status="AUTO_READY" if reason is None else "REVIEW_REQUIRED",
            review_reason=reason, fingerprint=digest,
        ))
    return result
