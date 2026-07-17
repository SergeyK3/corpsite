"""Composite training cell splitting and conservative fragment parsing (WP-CL-009)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from app.control_list_import.domain.person_candidate import NormalizedPlainText
from app.control_list_import.domain.training_candidate import (
    NormalizedCompletionDate,
    NormalizedCompletionYear,
    NormalizedDurationHours,
)
from app.control_list_import.domain.vocabulary import SEMANTIC_FIELD_TRAINING_RECORDS
from app.control_list_import.normalization.strings import normalize_comparison_key, normalize_plain_string, to_raw_text

TRAINING_RECORD_SPLIT_RE = re.compile(r"[\n;|]+")
NUMBERED_SPLIT_RE = re.compile(r"(?<=\n)(?=\d+[\.)]\s)|(?<=[;|])\s*(?=\d+[\.)]\s)")
YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
DATE_DMY_RE = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](\d{2,4})\b")
HOURS_RE = re.compile(
    r"(?P<hours>\d+(?:[.,]\d+)?)\s*(?:ч(?:ас(?:ов|а)?)?\.?|ч\.?|акад\.?\s*час(?:ов|а)?)(?:\b|$)",
    re.IGNORECASE,
)
CERT_NUMBER_RE = re.compile(
    r"(?:сертификат\s*)?(?:№|номер)\s*([\w/-]+)",
    re.IGNORECASE,
)
PROVIDER_LABEL_RE = re.compile(
    r"(?:организатор|организация|провайдер|учеб(?:ный|\.)\s*центр|место\s*проведения)"
    r"\s*[:—–-]\s*(.+?)(?:[;\n|]|$)",
    re.IGNORECASE,
)
TITLE_LABEL_RE = re.compile(
    r"(?:курс|тема|наименование|название|программа)\s*[:—–-]\s*(.+?)(?:[;\n|]|$)",
    re.IGNORECASE,
)
TRAINING_KEYWORDS_RE = re.compile(
    r"\b(?:повышени(?:е|я)\s+квалиф|пк\b|сертификат|курс|обучени(?:е|я)|семинар|конференц|"
    r"мастер[-\s]?класс|нмо\b)\b",
    re.IGNORECASE,
)
TRAINING_TYPE_KEYWORDS: tuple[tuple[str, str], ...] = (
    (r"\bпк\b|повышени[ея]\s+квалиф", "QUAL_UPGRADE"),
    (r"семинар", "SEMINAR"),
    (r"конференц", "CONFERENCE"),
    (r"мастер[-\s]?класс", "WORKSHOP"),
    (r"\bнмо\b", "NMO"),
    (r"курс", "COURSE"),
)

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


def _is_technical_empty(value: str) -> bool:
    key = normalize_comparison_key(value)
    return key in _TECHNICAL_EMPTY_KEYS if key else False


def is_technical_empty_training_cell(value: Any) -> bool:
    raw = to_raw_text(value)
    if not raw:
        return True
    return _is_technical_empty(raw)


def split_training_fragments(raw: Any) -> list[str]:
    """Split composite training cell into record fragments.

    Delimiters: newline, ``;``, ``|``. Commas inside a record are preserved.
    """
    text_val = to_raw_text(raw)
    if not text_val or _is_technical_empty(text_val):
        return []

    parts = TRAINING_RECORD_SPLIT_RE.split(text_val)
    expanded: list[str] = []
    for part in parts:
        part = part.strip()
        if not part or _is_technical_empty(part):
            continue
        subparts = NUMBERED_SPLIT_RE.split(part)
        for sub in subparts:
            fragment = sub.strip()
            if fragment and not _is_technical_empty(fragment):
                expanded.append(fragment)

    if expanded:
        return expanded
    if _is_technical_empty(text_val):
        return []
    return [text_val]


@dataclass(frozen=True)
class ParsedTrainingRecord:
    raw_fragment: str
    fragment_index: int
    training_title: NormalizedPlainText
    provider_name: NormalizedPlainText
    completion_date: NormalizedCompletionDate
    completion_year: NormalizedCompletionYear
    certificate_number: NormalizedPlainText
    duration_hours: NormalizedDurationHours
    training_type: NormalizedPlainText
    field_issues: dict[str, tuple[str, ...]]


def _plain(raw: str | None, text: str | None = None, issues: tuple[str, ...] = ()) -> NormalizedPlainText:
    return NormalizedPlainText(raw=raw, text=text, issues=issues)


def _parse_text_for_extraction(fragment: str) -> str:
    text_val = fragment.strip()
    return re.sub(r"^\d+[\.)]\s*", "", text_val)


def _parse_dmy(text_val: str) -> NormalizedCompletionDate:
    match = DATE_DMY_RE.search(text_val)
    if not match:
        return NormalizedCompletionDate(raw=None)
    day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
    if year < 100:
        year += 2000 if year < 50 else 1900
    try:
        parsed = date(year, month, day)
    except ValueError:
        return NormalizedCompletionDate(
            raw=match.group(0),
            issues=("training_completion_date_invalid",),
        )
    return NormalizedCompletionDate(raw=match.group(0), value=parsed)


def _extract_completion_year(text_val: str, completion_date: NormalizedCompletionDate) -> NormalizedCompletionYear:
    if completion_date.is_valid and completion_date.value is not None:
        return NormalizedCompletionYear(raw=str(completion_date.value.year), value=completion_date.value.year)
    match = YEAR_RE.search(text_val)
    if not match:
        return NormalizedCompletionYear(raw=None)
    year = int(match.group(1))
    if year < 1950 or year > 2100:
        return NormalizedCompletionYear(raw=match.group(1), issues=("training_completion_year_out_of_range",))
    return NormalizedCompletionYear(raw=match.group(1), value=year)


def _extract_duration_hours(text_val: str) -> NormalizedDurationHours:
    match = HOURS_RE.search(text_val)
    if not match:
        return NormalizedDurationHours(raw=None)
    raw_hours = match.group("hours").replace(",", ".")
    try:
        value = Decimal(raw_hours)
    except (InvalidOperation, ValueError):
        return NormalizedDurationHours(raw=match.group(0), issues=("training_duration_hours_unrecognized",))
    if value <= 0:
        return NormalizedDurationHours(raw=match.group(0), issues=("training_duration_hours_out_of_range",))
    return NormalizedDurationHours(raw=match.group(0), value=value)


def _extract_certificate_number(text_val: str) -> NormalizedPlainText:
    match = CERT_NUMBER_RE.search(text_val)
    if not match:
        return _plain(None)
    number_raw = match.group(1).strip()
    text, issues = normalize_plain_string(number_raw)
    return _plain(number_raw, text, issues)


def _extract_provider_name(text_val: str) -> NormalizedPlainText:
    match = PROVIDER_LABEL_RE.search(text_val)
    if not match:
        return _plain(None)
    provider_raw = match.group(1).strip(" ,;.-«»\"")
    provider_raw = re.split(r",\s*(?=\d)", provider_raw, maxsplit=1)[0].strip(" ,;.-«»\"")
    text, issues = normalize_plain_string(provider_raw)
    return _plain(provider_raw or None, text, issues)


def _match_training_type(text_val: str) -> NormalizedPlainText:
    lowered = text_val.lower()
    for pattern, code in TRAINING_TYPE_KEYWORDS:
        if re.search(pattern, lowered):
            return _plain(code, code)
    return _plain(None)


def _strip_extracted_metadata(text_val: str) -> str:
    cleaned = text_val
    cleaned = PROVIDER_LABEL_RE.sub(" ", cleaned)
    cleaned = TITLE_LABEL_RE.sub(" ", cleaned)
    cleaned = HOURS_RE.sub(" ", cleaned)
    cleaned = CERT_NUMBER_RE.sub(" ", cleaned)
    cleaned = DATE_DMY_RE.sub(" ", cleaned)
    cleaned = YEAR_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;.-")
    return cleaned


def _extract_training_title(text_val: str, provider_name: NormalizedPlainText) -> NormalizedPlainText:
    label_match = TITLE_LABEL_RE.search(text_val)
    if label_match:
        title_raw = label_match.group(1).strip(" ,;.-«»\"")
        text, issues = normalize_plain_string(title_raw)
        if text:
            return _plain(title_raw, text, issues)

    if not TRAINING_KEYWORDS_RE.search(text_val):
        return _plain(None)

    cleaned = _strip_extracted_metadata(text_val)
    if provider_name.text and cleaned:
        cleaned = cleaned.replace(provider_name.text, " ", 1).strip(" ,;.-")
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;.-")

    if not cleaned or len(cleaned) < 3:
        return _plain(None)

    text, issues = normalize_plain_string(cleaned)
    return _plain(cleaned, text, issues)


def _collect_fragment_issues(
    *,
    training_title: NormalizedPlainText,
    provider_name: NormalizedPlainText,
    completion_date: NormalizedCompletionDate,
    completion_year: NormalizedCompletionYear,
    certificate_number: NormalizedPlainText,
    duration_hours: NormalizedDurationHours,
    training_type: NormalizedPlainText,
) -> dict[str, tuple[str, ...]]:
    field_issues: dict[str, tuple[str, ...]] = {}

    def append(field: str, issues: tuple[str, ...]) -> None:
        if issues:
            field_issues[field] = issues

    append(SEMANTIC_FIELD_TRAINING_RECORDS, training_title.issues)
    append(SEMANTIC_FIELD_TRAINING_RECORDS, provider_name.issues)
    append(SEMANTIC_FIELD_TRAINING_RECORDS, completion_date.issues)
    append(SEMANTIC_FIELD_TRAINING_RECORDS, completion_year.issues)
    append(SEMANTIC_FIELD_TRAINING_RECORDS, certificate_number.issues)
    append(SEMANTIC_FIELD_TRAINING_RECORDS, duration_hours.issues)
    append(SEMANTIC_FIELD_TRAINING_RECORDS, training_type.issues)

    has_signal = any(
        (
            training_title.text,
            provider_name.text,
            certificate_number.text,
            training_type.text,
            duration_hours.is_valid,
            completion_date.is_valid,
            completion_year.is_valid,
            completion_year.raw,
        )
    )
    if not has_signal:
        field_issues[SEMANTIC_FIELD_TRAINING_RECORDS] = field_issues.get(
            SEMANTIC_FIELD_TRAINING_RECORDS,
            (),
        ) + ("training_fragment_incomplete",)
    elif not training_title.text and not duration_hours.is_valid and not certificate_number.text:
        field_issues[SEMANTIC_FIELD_TRAINING_RECORDS] = field_issues.get(
            SEMANTIC_FIELD_TRAINING_RECORDS,
            (),
        ) + ("training_fragment_unparsed",)
    elif (
        completion_year.is_valid
        and not training_title.text
        and not duration_hours.is_valid
        and not certificate_number.text
        and not provider_name.text
    ):
        field_issues[SEMANTIC_FIELD_TRAINING_RECORDS] = field_issues.get(
            SEMANTIC_FIELD_TRAINING_RECORDS,
            (),
        ) + ("training_fragment_unparsed",)

    merged: dict[str, tuple[str, ...]] = {}
    for field, issues in field_issues.items():
        merged[field] = tuple(dict.fromkeys(issues))
    return merged


def parse_training_fragment(fragment: str, *, fragment_index: int) -> ParsedTrainingRecord:
    raw_fragment = fragment
    parse_text = _parse_text_for_extraction(fragment)
    provider_name = _extract_provider_name(parse_text)
    completion_date = _parse_dmy(parse_text)
    completion_year = _extract_completion_year(parse_text, completion_date)
    duration_hours = _extract_duration_hours(parse_text)
    certificate_number = _extract_certificate_number(parse_text)
    training_type = _match_training_type(parse_text)
    training_title = _extract_training_title(parse_text, provider_name)
    field_issues = _collect_fragment_issues(
        training_title=training_title,
        provider_name=provider_name,
        completion_date=completion_date,
        completion_year=completion_year,
        certificate_number=certificate_number,
        duration_hours=duration_hours,
        training_type=training_type,
    )
    return ParsedTrainingRecord(
        raw_fragment=raw_fragment,
        fragment_index=fragment_index,
        training_title=training_title,
        provider_name=provider_name,
        completion_date=completion_date,
        completion_year=completion_year,
        certificate_number=certificate_number,
        duration_hours=duration_hours,
        training_type=training_type,
        field_issues=field_issues,
    )
