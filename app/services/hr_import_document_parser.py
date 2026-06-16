"""Parse roster document fields into document candidate fragments (Phase 2C/2D)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Optional

HOURS_RE = re.compile(
    r"(?P<hours>\d+(?:[.,]\d+)?)\s*(?:ч(?:ас(?:ов|а)?)?\.?|ч\.?)(?:\b|$)",
    re.IGNORECASE,
)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
DATE_DMY_RE = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](\d{2,4})\b")
VALID_UNTIL_RE = re.compile(
    r"(?:до|действ\.?\s*до|срок\s*до)\s*(\d{1,2}[./]\d{1,2}[./]\d{2,4})",
    re.IGNORECASE,
)
CERT_NUMBER_RE = re.compile(r"(?:№|номер)\s*([\d/-]+)", re.IGNORECASE)
NUMBERED_SPLIT_RE = re.compile(r"(?<=\n)(?=\d+[\.)]\s)|(?<=[;])\s*(?=\d+[\.)]\s)")

TRAINING_TYPE_KEYWORDS: tuple[tuple[str, str], ...] = (
    (r"\bпк\b|повышени[ея]\s+квалиф", "QUAL_UPGRADE"),
    (r"семинар", "SEMINAR_CERT"),
    (r"конференц", "CONFERENCE_CERT"),
    (r"мастер[-\s]?класс", "WORKSHOP_CERT"),
    (r"\bнмо\b", "NMO"),
    (r"курс", "COURSE"),
)

CERT_CATEGORY_KEYWORDS: tuple[tuple[str, str], ...] = (
    (r"высш", "highest"),
    (r"перва", "first"),
    (r"втор", "second"),
    (r"сертификат", "certificate"),
)

EDUCATION_INSTITUTION_RE = re.compile(
    r"\b(?:вуз|институт|университет|академи[яи]|колледж)\b",
    re.IGNORECASE,
)
EDUCATION_KEYWORDS_RE = re.compile(
    r"\b(?:диплом|окончил[а]?|образовани[ея])\b",
    re.IGNORECASE,
)
SPECIALTY_INLINE_RE = re.compile(
    r"(?:специальност[ьи]\s*(?:по\s*диплому)?[:\s]+)(.+?)(?:[;\n]|$)",
    re.IGNORECASE,
)
TRAINING_KEYWORDS_RE = re.compile(
    r"\b(?:повышени(?:е|я)\s+квалиф|сертификат|курс|обучени(?:е|я)|пк)\b",
    re.IGNORECASE,
)
ACAD_HOURS_RE = re.compile(r"акад\.?\s*час", re.IGNORECASE)

EDUCATION_UNIVERSITY_YEAR_RE = re.compile(
    r"^(.+?)[,\s;]+((?:19|20)\d{2})\b",
    re.IGNORECASE,
)

SOURCE_FIELD_EDUCATION_TRAINING = "education_training_raw"
SOURCE_FIELD_EDUCATION = "education_raw"
SOURCE_FIELD_CERTIFICATION = "certification_raw"


@dataclass
class ParsedDocumentFragment:
    document_kind: str
    fragment_index: int
    raw_text: str
    title: Optional[str] = None
    proposed_document_type: Optional[str] = None
    parsed_hours: Optional[Decimal] = None
    parsed_issued_at: Optional[date] = None
    parsed_valid_until: Optional[date] = None
    organization: Optional[str] = None
    specialty: Optional[str] = None
    category: Optional[str] = None
    certificate_number: Optional[str] = None
    confidence_score: Decimal = field(default_factory=lambda: Decimal("0.3000"))
    parse_method: str = "regex_v1"
    source_field: Optional[str] = None


def _parse_dmy(value: str) -> Optional[date]:
    match = DATE_DMY_RE.search(value)
    if not match:
        return None
    day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
    if year < 100:
        year += 2000 if year < 50 else 1900
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_year_as_date(text_val: str) -> Optional[date]:
    match = YEAR_RE.search(text_val)
    if not match:
        return None
    return date(int(match.group(0)), 1, 1)


def _extract_hours(text_val: str) -> Optional[Decimal]:
    match = HOURS_RE.search(text_val)
    if not match:
        return None
    raw = match.group("hours").replace(",", ".")
    try:
        return Decimal(raw)
    except Exception:
        return None


def _match_keyword(text_val: str, patterns: tuple[tuple[str, str], ...]) -> Optional[str]:
    lowered = text_val.lower()
    for pattern, code in patterns:
        if re.search(pattern, lowered):
            return code
    return None


def _clean_title(text_val: str) -> str:
    cleaned = HOURS_RE.sub(" ", text_val)
    cleaned = VALID_UNTIL_RE.sub(" ", cleaned)
    cleaned = DATE_DMY_RE.sub(" ", cleaned)
    cleaned = YEAR_RE.sub(" ", cleaned)
    cleaned = CERT_NUMBER_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;.-")
    return cleaned or text_val.strip()


def split_raw_fragments(raw: str) -> list[str]:
    text_val = (raw or "").strip()
    if not text_val:
        return []
    parts = re.split(r"[\n;]+", text_val)
    expanded: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        subparts = NUMBERED_SPLIT_RE.split(part)
        for sub in subparts:
            sub = re.sub(r"^\d+[\.)]\s*", "", sub.strip())
            if sub:
                expanded.append(sub)
    return expanded or [text_val]


def _looks_like_education(text_val: str) -> bool:
    if EDUCATION_UNIVERSITY_YEAR_RE.match(text_val):
        return True
    lowered = text_val.lower()
    has_institution = bool(EDUCATION_INSTITUTION_RE.search(text_val))
    has_year = bool(YEAR_RE.search(text_val))
    has_edu_kw = bool(EDUCATION_KEYWORDS_RE.search(text_val))
    has_specialty = "специальност" in lowered
    if has_institution:
        return True
    if has_edu_kw and has_year:
        return True
    if has_specialty and has_year:
        return True
    if has_institution and has_year:
        return True
    return False


def _looks_like_training(text_val: str) -> bool:
    if _extract_hours(text_val) is not None:
        return True
    if ACAD_HOURS_RE.search(text_val):
        return True
    if TRAINING_KEYWORDS_RE.search(text_val):
        return True
    return False


def _extract_specialty(text_val: str) -> Optional[str]:
    match = SPECIALTY_INLINE_RE.search(text_val)
    if match:
        value = match.group(1).strip(" ,;.-")
        return value or None
    return None


def parse_education_graduation_fragment(
    fragment: str,
    *,
    fragment_index: int,
    source_field: str = SOURCE_FIELD_EDUCATION_TRAINING,
    diploma_specialty: str = "",
) -> ParsedDocumentFragment:
    text_val = fragment.strip()
    organization: Optional[str] = None
    issued_at = _parse_year_as_date(text_val)
    match = EDUCATION_UNIVERSITY_YEAR_RE.match(text_val)
    if match:
        organization = match.group(1).strip(" ,;.-")
        issued_at = date(int(match.group(2)), 1, 1)
    elif EDUCATION_INSTITUTION_RE.search(text_val):
        organization = YEAR_RE.sub("", text_val).strip(" ,;.-") or None
        organization = re.sub(
            r"\b(?:специальност[ьи].*)$",
            "",
            organization or "",
            flags=re.IGNORECASE,
        ).strip(" ,;.-") or organization

    specialty = diploma_specialty.strip() or _extract_specialty(text_val) or None
    title = organization or _clean_title(text_val) or specialty or "Окончание учебного заведения"

    confidence = Decimal("0.4000")
    if organization:
        confidence += Decimal("0.2000")
    if issued_at:
        confidence += Decimal("0.2000")
    if specialty:
        confidence += Decimal("0.1500")
    confidence = min(confidence, Decimal("1.0000"))

    return ParsedDocumentFragment(
        document_kind="education",
        fragment_index=fragment_index,
        raw_text=text_val,
        title=title,
        proposed_document_type="EDUCATION_GRADUATION",
        organization=organization,
        parsed_issued_at=issued_at,
        specialty=specialty,
        category="EDUCATION",
        confidence_score=confidence,
        source_field=source_field,
    )


def parse_training_hours_fragment(
    fragment: str,
    *,
    fragment_index: int,
    source_field: str = SOURCE_FIELD_EDUCATION_TRAINING,
) -> ParsedDocumentFragment:
    text_val = fragment.strip()
    issued_at = _parse_dmy(text_val) or _parse_year_as_date(text_val)
    valid_until_match = VALID_UNTIL_RE.search(text_val)
    valid_until = _parse_dmy(valid_until_match.group(1)) if valid_until_match else None
    hours = _extract_hours(text_val)
    title = _clean_title(text_val)

    confidence = Decimal("0.3500")
    if issued_at:
        confidence += Decimal("0.2000")
    if hours is not None:
        confidence += Decimal("0.2000")
    if valid_until:
        confidence += Decimal("0.1000")
    if TRAINING_KEYWORDS_RE.search(text_val):
        confidence += Decimal("0.1000")
    if len(title) >= 5:
        confidence += Decimal("0.0500")
    confidence = min(confidence, Decimal("1.0000"))

    return ParsedDocumentFragment(
        document_kind="training",
        fragment_index=fragment_index,
        raw_text=text_val,
        title=title,
        proposed_document_type="TRAINING_HOURS",
        parsed_hours=hours,
        parsed_issued_at=issued_at,
        parsed_valid_until=valid_until,
        category="TRAINING",
        confidence_score=confidence,
        source_field=source_field,
    )


def parse_education_training_fragment(
    fragment: str,
    *,
    fragment_index: int,
    source_field: str = SOURCE_FIELD_EDUCATION_TRAINING,
) -> list[ParsedDocumentFragment]:
    text_val = fragment.strip()
    if not text_val:
        return []

    results: list[ParsedDocumentFragment] = []
    is_education = _looks_like_education(text_val)
    is_training = _looks_like_training(text_val)

    if is_education:
        results.append(
            parse_education_graduation_fragment(
                text_val,
                fragment_index=fragment_index,
                source_field=source_field,
            )
        )
    if is_training:
        results.append(
            parse_training_hours_fragment(
                text_val,
                fragment_index=fragment_index,
                source_field=source_field,
            )
        )
    return results


def parse_education_training_raw(raw: str) -> list[ParsedDocumentFragment]:
    """Split column M mixed education/training text into document candidates."""
    fragments: list[ParsedDocumentFragment] = []
    for idx, piece in enumerate(split_raw_fragments(raw)):
        fragments.extend(
            parse_education_training_fragment(
                piece,
                fragment_index=idx,
                source_field=SOURCE_FIELD_EDUCATION_TRAINING,
            )
        )
    return fragments


def parse_training_fragment(fragment: str, *, fragment_index: int) -> ParsedDocumentFragment:
    text_val = fragment.strip()
    issued_at = _parse_dmy(text_val) or _parse_year_as_date(text_val)
    valid_until_match = VALID_UNTIL_RE.search(text_val)
    valid_until = _parse_dmy(valid_until_match.group(1)) if valid_until_match else None
    hours = _extract_hours(text_val)
    doc_type = _match_keyword(text_val, TRAINING_TYPE_KEYWORDS) or "QUAL_UPGRADE"
    title = _clean_title(text_val)

    confidence = Decimal("0.3000")
    if issued_at:
        confidence += Decimal("0.2000")
    if hours is not None:
        confidence += Decimal("0.2000")
    if doc_type != "QUAL_UPGRADE" or "пк" in text_val.lower() or "курс" in text_val.lower():
        confidence += Decimal("0.1500")
    if len(title) >= 5:
        confidence += Decimal("0.1000")
    confidence = min(confidence, Decimal("1.0000"))

    return ParsedDocumentFragment(
        document_kind="training",
        fragment_index=fragment_index,
        raw_text=text_val,
        title=title,
        proposed_document_type=doc_type,
        parsed_hours=hours,
        parsed_issued_at=issued_at,
        parsed_valid_until=valid_until,
        confidence_score=confidence,
        source_field="training_raw",
    )


def parse_certification_fragment(fragment: str, *, fragment_index: int) -> ParsedDocumentFragment:
    text_val = fragment.strip()
    category = _match_keyword(text_val, CERT_CATEGORY_KEYWORDS)
    cert_number_match = CERT_NUMBER_RE.search(text_val)
    cert_number = cert_number_match.group(1).strip() if cert_number_match else None
    valid_until_match = VALID_UNTIL_RE.search(text_val)
    valid_until = _parse_dmy(valid_until_match.group(1)) if valid_until_match else _parse_dmy(text_val)
    issued_at = _parse_year_as_date(text_val)
    doc_type = "SPECIALIST_CERT" if category == "certificate" else "QUALIFICATION_CATEGORY"
    title = _clean_title(text_val) or (category or "certification")

    confidence = Decimal("0.3500")
    if category:
        confidence += Decimal("0.3000")
    if cert_number:
        confidence += Decimal("0.1500")
    if valid_until:
        confidence += Decimal("0.1000")
    confidence = min(confidence, Decimal("1.0000"))

    return ParsedDocumentFragment(
        document_kind="certification",
        fragment_index=fragment_index,
        raw_text=text_val,
        title=title,
        proposed_document_type=doc_type,
        parsed_issued_at=issued_at,
        parsed_valid_until=valid_until,
        category=category,
        certificate_number=cert_number,
        confidence_score=confidence,
        source_field=SOURCE_FIELD_CERTIFICATION,
    )


def parse_training_raw(raw: str) -> list[ParsedDocumentFragment]:
    return [
        parse_training_fragment(fragment, fragment_index=idx)
        for idx, fragment in enumerate(split_raw_fragments(raw))
    ]


def parse_certification_raw(raw: str) -> list[ParsedDocumentFragment]:
    return [
        parse_certification_fragment(fragment, fragment_index=idx)
        for idx, fragment in enumerate(split_raw_fragments(raw))
    ]


def parse_education_raw(
    education_raw: str,
    diploma_specialty_raw: str = "",
) -> list[ParsedDocumentFragment]:
    edu = (education_raw or "").strip()
    diploma = (diploma_specialty_raw or "").strip()
    if not edu and not diploma:
        return []

    raw_parts: list[str] = []
    if edu:
        raw_parts.append(edu)
    if diploma:
        raw_parts.append(f"Специальность по диплому: {diploma}")
    raw_text = "\n".join(raw_parts)

    fragment = parse_education_graduation_fragment(
        edu or raw_text,
        fragment_index=0,
        source_field=SOURCE_FIELD_EDUCATION,
        diploma_specialty=diploma,
    )
    if not edu and diploma:
        fragment.raw_text = raw_text
        fragment.specialty = diploma
        fragment.title = diploma
    return [fragment]


def fragment_to_dict(fragment: ParsedDocumentFragment) -> dict[str, Any]:
    return {
        "document_kind": fragment.document_kind,
        "fragment_index": fragment.fragment_index,
        "raw_text": fragment.raw_text,
        "title": fragment.title,
        "proposed_document_type": fragment.proposed_document_type,
        "parsed_hours": fragment.parsed_hours,
        "parsed_issued_at": fragment.parsed_issued_at,
        "parsed_valid_until": fragment.parsed_valid_until,
        "organization": fragment.organization,
        "specialty": fragment.specialty,
        "category": fragment.category,
        "certificate_number": fragment.certificate_number,
        "confidence_score": fragment.confidence_score,
        "parse_method": fragment.parse_method,
        "source_field": fragment.source_field,
    }
