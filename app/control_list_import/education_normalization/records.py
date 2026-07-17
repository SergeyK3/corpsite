"""Composite education cell splitting and fragment parsing (WP-CL-008)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.control_list_import.domain.education_candidate import NormalizedGraduationYear
from app.control_list_import.domain.person_candidate import NormalizedPlainText
from app.control_list_import.domain.vocabulary import SEMANTIC_FIELD_EDUCATION_RECORDS
from app.control_list_import.normalization.strings import normalize_comparison_key, normalize_plain_string, to_raw_text

EDUCATION_RECORD_SPLIT_RE = re.compile(r"[\n;|]+")
NUMBERED_SPLIT_RE = re.compile(r"(?<=\n)(?=\d+[\.)]\s)|(?<=[;|])\s*(?=\d+[\.)]\s)")
YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
EDUCATION_UNIVERSITY_YEAR_RE = re.compile(
    r"^(.+?)[,\s;]+((?:19|20)\d{2})\b",
    re.IGNORECASE,
)
EDUCATION_INSTITUTION_RE = re.compile(
    r"\b(?:вуз|институт|университет|академи[яи]|колледж|ун-?т)\b",
    re.IGNORECASE,
)
SPECIALTY_INLINE_RE = re.compile(
    r"(?:специальност[ьи]\s*(?:по\s*диплому)?[:\s]+)(.+?)(?:[;\n|]|$)",
    re.IGNORECASE,
)
DOCUMENT_NUMBER_RE = re.compile(
    r"(?:№|номер|диплом\s*№?)\s*([\w/-]+)",
    re.IGNORECASE,
)
QUALIFICATION_RE = re.compile(
    r"\b(бакалавр(?:\s+наук)?|магистр(?:\s+наук)?|специалист|"
    r"среднее\s+специальное|среднее\s+профессиональное|высшее\s+образование)\b",
    re.IGNORECASE,
)
EDUCATION_LEVEL_RE = re.compile(
    r"\b(высшее|среднее|послевузовское|базовое)\b",
    re.IGNORECASE,
)
INSTITUTION_ABBREVIATION_RE = re.compile(r"[A-ZА-ЯЁ]{2,}")

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


def is_technical_empty_education_cell(value: Any) -> bool:
    raw = to_raw_text(value)
    if not raw:
        return True
    return _is_technical_empty(raw)


def split_education_fragments(raw: Any) -> list[str]:
    """Split composite education cell into record fragments.

    Delimiters: newline, ``;``, ``|``. Commas inside a record are preserved.
    """
    text_val = to_raw_text(raw)
    if not text_val or _is_technical_empty(text_val):
        return []

    parts = EDUCATION_RECORD_SPLIT_RE.split(text_val)
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
class ParsedEducationRecord:
    raw_fragment: str
    fragment_index: int
    institution_name: NormalizedPlainText
    qualification: NormalizedPlainText
    specialty: NormalizedPlainText
    graduation_year: NormalizedGraduationYear
    education_level: NormalizedPlainText
    document_number: NormalizedPlainText
    field_issues: dict[str, tuple[str, ...]]


def _plain(raw: str | None, text: str | None = None, issues: tuple[str, ...] = ()) -> NormalizedPlainText:
    return NormalizedPlainText(raw=raw, text=text, issues=issues)


def _extract_graduation_year(text_val: str) -> NormalizedGraduationYear:
    match = YEAR_RE.search(text_val)
    if not match:
        return NormalizedGraduationYear(raw=None)
    year = int(match.group(1))
    if year < 1950 or year > 2100:
        return NormalizedGraduationYear(raw=match.group(1), issues=("education_graduation_year_out_of_range",))
    return NormalizedGraduationYear(raw=match.group(1), value=year)


def _institution_candidate_is_confident(institution_raw: str) -> bool:
    if not institution_raw.strip():
        return False
    if EDUCATION_INSTITUTION_RE.search(institution_raw):
        return True
    return bool(INSTITUTION_ABBREVIATION_RE.search(institution_raw))


def _leading_segment_before_specialty(text_val: str) -> str:
    before_specialty = re.split(r"\bспециальност[ьи]\b", text_val, maxsplit=1, flags=re.IGNORECASE)[0]
    return before_specialty.strip(" ,;")


def _extract_institution(text_val: str) -> NormalizedPlainText:
    leading_text = _leading_segment_before_specialty(text_val)
    match = EDUCATION_UNIVERSITY_YEAR_RE.match(leading_text)
    if match:
        institution_raw = match.group(1).strip(" ,;.-")
        if _institution_candidate_is_confident(institution_raw):
            text, issues = normalize_plain_string(institution_raw)
            return _plain(institution_raw or None, text, issues)
        return _plain(None)

    if "," in leading_text:
        institution_raw = leading_text.split(",", 1)[0].strip(" ,;.-")
        if institution_raw and _institution_candidate_is_confident(institution_raw):
            text, issues = normalize_plain_string(institution_raw)
            return _plain(institution_raw or None, text, issues)
        return _plain(None)

    if leading_text and _institution_candidate_is_confident(leading_text):
        text, issues = normalize_plain_string(leading_text.strip(" ,;.-"))
        return _plain(leading_text.strip(" ,;.-") or None, text, issues)

    if EDUCATION_INSTITUTION_RE.search(text_val):
        without_year = YEAR_RE.sub("", text_val).strip(" ,;.-")
        without_year = re.sub(
            r"\b(?:специальност[ьи].*)$",
            "",
            without_year,
            flags=re.IGNORECASE,
        ).strip(" ,;.-")
        text, issues = normalize_plain_string(without_year)
        return _plain(without_year or None, text, issues)

    return _plain(None)


def _parse_text_for_extraction(fragment: str) -> str:
    text_val = fragment.strip()
    return re.sub(r"^\d+[\.)]\s*", "", text_val)


def _extract_specialty(text_val: str) -> NormalizedPlainText:
    match = SPECIALTY_INLINE_RE.search(text_val)
    if match:
        specialty_raw = match.group(1).strip(" ,;.-")
        text, issues = normalize_plain_string(specialty_raw)
        return _plain(specialty_raw or None, text, issues)
    return _plain(None)


def _extract_qualification(text_val: str) -> NormalizedPlainText:
    match = QUALIFICATION_RE.search(text_val)
    if not match:
        return _plain(None)
    qualification_raw = match.group(1).strip()
    text, issues = normalize_plain_string(qualification_raw)
    return _plain(qualification_raw, text, issues)


def _extract_education_level(text_val: str) -> NormalizedPlainText:
    match = EDUCATION_LEVEL_RE.search(text_val)
    if not match:
        return _plain(None)
    level_raw = match.group(1).strip()
    text, issues = normalize_plain_string(level_raw)
    return _plain(level_raw, text, issues)


def _extract_document_number(text_val: str) -> NormalizedPlainText:
    match = DOCUMENT_NUMBER_RE.search(text_val)
    if not match:
        return _plain(None)
    number_raw = match.group(1).strip()
    text, issues = normalize_plain_string(number_raw)
    return _plain(number_raw, text, issues)


def _collect_fragment_issues(
    *,
    institution_name: NormalizedPlainText,
    specialty: NormalizedPlainText,
    graduation_year: NormalizedGraduationYear,
    qualification: NormalizedPlainText,
    education_level: NormalizedPlainText,
    document_number: NormalizedPlainText,
) -> dict[str, tuple[str, ...]]:
    field_issues: dict[str, tuple[str, ...]] = {}

    def append(field: str, issues: tuple[str, ...]) -> None:
        if issues:
            field_issues[field] = issues

    append(SEMANTIC_FIELD_EDUCATION_RECORDS, institution_name.issues)
    append(SEMANTIC_FIELD_EDUCATION_RECORDS, specialty.issues)
    append(SEMANTIC_FIELD_EDUCATION_RECORDS, qualification.issues)
    append(SEMANTIC_FIELD_EDUCATION_RECORDS, education_level.issues)
    append(SEMANTIC_FIELD_EDUCATION_RECORDS, document_number.issues)
    append(SEMANTIC_FIELD_EDUCATION_RECORDS, graduation_year.issues)

    has_signal = any(
        (
            institution_name.text,
            specialty.text,
            qualification.text,
            education_level.text,
            document_number.text,
            graduation_year.is_valid,
            graduation_year.raw,
        )
    )
    if not has_signal:
        field_issues[SEMANTIC_FIELD_EDUCATION_RECORDS] = field_issues.get(
            SEMANTIC_FIELD_EDUCATION_RECORDS,
            (),
        ) + ("education_fragment_incomplete",)
    elif not institution_name.text and not specialty.text and (
        graduation_year.is_valid or (graduation_year.raw or "").strip()
    ):
        field_issues[SEMANTIC_FIELD_EDUCATION_RECORDS] = field_issues.get(
            SEMANTIC_FIELD_EDUCATION_RECORDS,
            (),
        ) + ("education_fragment_unparsed",)
    elif not institution_name.text and not graduation_year.is_valid and not specialty.text:
        field_issues[SEMANTIC_FIELD_EDUCATION_RECORDS] = field_issues.get(
            SEMANTIC_FIELD_EDUCATION_RECORDS,
            (),
        ) + ("education_fragment_unparsed",)

    merged: dict[str, tuple[str, ...]] = {}
    for field, issues in field_issues.items():
        merged[field] = tuple(dict.fromkeys(issues))
    return merged


def parse_education_fragment(fragment: str, *, fragment_index: int) -> ParsedEducationRecord:
    raw_fragment = fragment
    parse_text = _parse_text_for_extraction(fragment)
    graduation_year = _extract_graduation_year(parse_text)
    institution_name = _extract_institution(parse_text)
    specialty = _extract_specialty(parse_text)
    qualification = _extract_qualification(parse_text)
    education_level = _extract_education_level(parse_text)
    document_number = _extract_document_number(parse_text)
    field_issues = _collect_fragment_issues(
        institution_name=institution_name,
        specialty=specialty,
        graduation_year=graduation_year,
        qualification=qualification,
        education_level=education_level,
        document_number=document_number,
    )
    return ParsedEducationRecord(
        raw_fragment=raw_fragment,
        fragment_index=fragment_index,
        institution_name=institution_name,
        qualification=qualification,
        specialty=specialty,
        graduation_year=graduation_year,
        education_level=education_level,
        document_number=document_number,
        field_issues=field_issues,
    )
