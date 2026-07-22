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
YEAR_RE = re.compile(
    r"\b((?:19|20)\d{2})(?:\s*г\.)?(?=[\s,;.)]|$)",
    re.IGNORECASE,
)
DATE_DMY_RE = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](\d{2,4})\b")
VALID_UNTIL_RE = re.compile(
    r"(?:до|действ\.?\s*до|срок\s*до)\s*(\d{1,2}[./]\d{1,2}[./]\d{2,4})",
    re.IGNORECASE,
)
CERT_NUMBER_RE = re.compile(r"(?:№|номер)\s*([\d/-]+)", re.IGNORECASE)
NUMBERED_SPLIT_RE = re.compile(
    r"(?<=\n)(?=\d+[\.)]\s)"
    r"|(?<=[;|])\s*(?=\d+[\.)]\s)"
    r"|(?<=\S)\s+(?=\d+[\.)]\s)"
)
EDUCATION_ADMISSION_RE = re.compile(
    r"поступ(?:ил(?:а)?|ление)?\s*[:\-]?\s*"
    r"(\d{1,2}[./]\d{1,2}[./]\d{2,4}|(?:19|20)\d{2}(?:\s*г\.)?)",
    re.IGNORECASE,
)
EDUCATION_GRADUATION_RE = re.compile(
    r"оконч(?:ил(?:а)?|ание)?\s*[:\-]?\s*"
    r"(\d{1,2}[./]\d{1,2}[./]\d{2,4}|(?:19|20)\d{2}(?:\s*г\.)?)",
    re.IGNORECASE,
)
EDUCATION_YEAR_RANGE_RE = re.compile(
    r"(?:с|от)\s*((?:19|20)\d{2})(?:\s*г\.)?\s*[-–—]\s*(?:по\s*)?((?:19|20)\d{2})(?:\s*г\.)?",
    re.IGNORECASE,
)

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
    r"(?:специальност[ьи]\s*(?:по\s*диплому)?[:\s«]+)(.+?)(?:[;\n]|$|(?=\s*квалификац|\s*факультет|\s*форма\s+обучения))",
    re.IGNORECASE,
)
QUALIFICATION_INLINE_RE = re.compile(
    r"квалификац(?:ия|ии)\s*[:\s«]+(.+?)(?:[;\n]|$|(?=\s*специальност|\s*факультет|\s*форма\s+обучения))",
    re.IGNORECASE,
)
FACULTY_INLINE_RE = re.compile(
    r"факультет\s*[:\s«]+(.+?)(?:[;\n]|$|(?=\s*специальност|\s*квалификац|\s*форма\s+обучения))",
    re.IGNORECASE,
)
STUDY_FORM_INLINE_RE = re.compile(
    r"форма\s+обучения\s*[:\s«]+(.+?)(?:[;\n]|$|(?=\s*специальност|\s*квалификац|\s*факультет))",
    re.IGNORECASE,
)
SHARED_ATTR_START_RE = re.compile(
    r"(?:,\s+(?=специальност|квалификац|факультет|форма\s+обучения))"
    r"|(?:\.\s+(?=специальност|квалификац|факультет|форма\s+обучения))"
    r"|(?:\s{2,}(?=специальност|квалификац|факультет|форма\s+обучения))"
    r"|(?<=[^\d]\S)\s+(?=специальност|квалификац|факультет|форма\s+обучения)\b",
    re.IGNORECASE,
)
EDUCATION_SHARED_CONTEXT_REMARK = (
    "Требуется уточнить принадлежность данных к учебному заведению"
)
TRAINING_KEYWORDS_RE = re.compile(
    r"\b(?:повышени(?:е|я)\s+квалиф|сертификат|курс|обучени(?:е|я)|пк)\b",
    re.IGNORECASE,
)
ACAD_HOURS_RE = re.compile(r"акад\.?\s*час", re.IGNORECASE)

EDUCATION_UNIVERSITY_YEAR_RE = re.compile(
    r"^(.+?)[,\s;]+((?:19|20)\d{2})(?:\s*г\.)?(?=[\s,;.)]|$)",
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
    parsed_start_at: Optional[date] = None
    parsed_end_at: Optional[date] = None
    parsed_valid_until: Optional[date] = None
    organization: Optional[str] = None
    specialty: Optional[str] = None
    qualification: Optional[str] = None
    faculty: Optional[str] = None
    study_form: Optional[str] = None
    category: Optional[str] = None
    certificate_number: Optional[str] = None
    shared_context_ambiguous: bool = False
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


def _parse_year_token(value: str) -> Optional[date]:
    match = YEAR_RE.search(value)
    if not match:
        return None
    return date(int(match.group(1)), 1, 1)


def _parse_year_as_date(text_val: str) -> Optional[date]:
    return _parse_year_token(text_val)


def _extract_education_dates(text_val: str) -> tuple[Optional[date], Optional[date]]:
    """Extract admission/completion dates when explicitly present in fragment text."""
    start_at: Optional[date] = None
    end_at: Optional[date] = None

    range_match = EDUCATION_YEAR_RANGE_RE.search(text_val)
    if range_match:
        start_at = date(int(range_match.group(1)), 1, 1)
        end_at = date(int(range_match.group(2)), 1, 1)
        return start_at, end_at

    admission_match = EDUCATION_ADMISSION_RE.search(text_val)
    if admission_match:
        start_at = _parse_dmy(admission_match.group(1)) or _parse_year_token(admission_match.group(1))

    graduation_match = EDUCATION_GRADUATION_RE.search(text_val)
    if graduation_match:
        end_at = _parse_dmy(graduation_match.group(1)) or _parse_year_token(graduation_match.group(1))

    if start_at is None and end_at is None:
        end_at = _parse_year_as_date(text_val)

    return start_at, end_at


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
    parts = re.split(r"[\n;|]+", text_val)
    expanded: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        subparts = NUMBERED_SPLIT_RE.split(part)
        for sub in subparts:
            sub = sub.strip()
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


@dataclass(frozen=True)
class EducationSharedContext:
    specialty: Optional[str] = None
    qualification: Optional[str] = None
    faculty: Optional[str] = None
    study_form: Optional[str] = None
    ambiguous: bool = False

    def has_values(self) -> bool:
        return any((self.specialty, self.qualification, self.faculty, self.study_form))


def _clean_attr_value(value: str) -> Optional[str]:
    cleaned = value.strip(" ,;.-«»\"'")
    return cleaned or None


def _extract_qualification(text_val: str) -> Optional[str]:
    match = QUALIFICATION_INLINE_RE.search(text_val)
    if match:
        return _clean_attr_value(match.group(1))
    return None


def _extract_faculty(text_val: str) -> Optional[str]:
    match = FACULTY_INLINE_RE.search(text_val)
    if match:
        return _clean_attr_value(match.group(1))
    return None


def _extract_study_form(text_val: str) -> Optional[str]:
    match = STUDY_FORM_INLINE_RE.search(text_val)
    if match:
        return _clean_attr_value(match.group(1))
    return None


def _extract_specialty(text_val: str) -> Optional[str]:
    match = SPECIALTY_INLINE_RE.search(text_val)
    if match:
        return _clean_attr_value(match.group(1))
    return None


def _extract_education_shared_context(text_val: str) -> EducationSharedContext:
    text = (text_val or "").strip()
    if not text:
        return EducationSharedContext()
    return EducationSharedContext(
        specialty=_extract_specialty(text),
        qualification=_extract_qualification(text),
        faculty=_extract_faculty(text),
        study_form=_extract_study_form(text),
    )


def _merge_shared_context(*contexts: EducationSharedContext) -> EducationSharedContext:
    specialty = qualification = faculty = study_form = None
    ambiguous = False
    for ctx in contexts:
        if ctx.specialty and not specialty:
            specialty = ctx.specialty
        if ctx.qualification and not qualification:
            qualification = ctx.qualification
        if ctx.faculty and not faculty:
            faculty = ctx.faculty
        if ctx.study_form and not study_form:
            study_form = ctx.study_form
        ambiguous = ambiguous or ctx.ambiguous
    return EducationSharedContext(
        specialty=specialty,
        qualification=qualification,
        faculty=faculty,
        study_form=study_form,
        ambiguous=ambiguous,
    )


def _split_institution_entry(fragment: str) -> tuple[str, str]:
    text = fragment.strip()
    if not text:
        return "", ""
    match = SHARED_ATTR_START_RE.search(text)
    if not match:
        return text, ""
    institution_part = text[: match.start()].strip(" ,;.")
    shared_tail = text[match.start() :].strip(" ,;.")
    return institution_part, shared_tail


def _looks_like_institution_entry(fragment: str) -> bool:
    institution_part, _ = _split_institution_entry(fragment)
    body = re.sub(r"^\d+[\.)]\s*", "", institution_part.strip())
    if not body:
        return False
    if EDUCATION_UNIVERSITY_YEAR_RE.match(body):
        return True
    if EDUCATION_INSTITUTION_RE.search(body):
        return True
    if YEAR_RE.search(body) and len(body.split()) >= 2:
        return True
    return bool(re.match(r"^\d+[\.)]\s+\S", fragment.strip()))


def split_education_institution_pieces(raw: str) -> tuple[list[str], str]:
    """Split composite education text into institution entries and shared tail text."""
    pieces = split_raw_fragments(raw)
    if not pieces:
        return [], ""

    institution_entries: list[str] = []
    shared_tail_parts: list[str] = []

    for piece in pieces:
        if _looks_like_institution_entry(piece):
            institution_part, inline_tail = _split_institution_entry(piece)
            if institution_part:
                institution_entries.append(institution_part)
            if inline_tail:
                shared_tail_parts.append(inline_tail)
        else:
            shared_tail_parts.append(piece)

    return institution_entries, " ".join(shared_tail_parts).strip()


def _apply_shared_context_to_fragment(
    fragment: ParsedDocumentFragment,
    shared: EducationSharedContext,
) -> ParsedDocumentFragment:
    if not shared.has_values():
        return fragment

    applied_from_shared = False
    specialty = fragment.specialty
    qualification = fragment.qualification
    faculty = fragment.faculty
    study_form = fragment.study_form

    if not specialty and shared.specialty:
        specialty = shared.specialty
        applied_from_shared = True
    if not qualification and shared.qualification:
        qualification = shared.qualification
        applied_from_shared = True
    if not faculty and shared.faculty:
        faculty = shared.faculty
        applied_from_shared = True
    if not study_form and shared.study_form:
        study_form = shared.study_form
        applied_from_shared = True

    ambiguous = fragment.shared_context_ambiguous or (shared.ambiguous and applied_from_shared)
    parse_method = fragment.parse_method
    if ambiguous and "shared_context_ambiguous" not in parse_method:
        parse_method = f"{parse_method}|shared_context_ambiguous"

    return ParsedDocumentFragment(
        document_kind=fragment.document_kind,
        fragment_index=fragment.fragment_index,
        raw_text=fragment.raw_text,
        title=fragment.title,
        proposed_document_type=fragment.proposed_document_type,
        parsed_hours=fragment.parsed_hours,
        parsed_issued_at=fragment.parsed_issued_at,
        parsed_start_at=fragment.parsed_start_at,
        parsed_end_at=fragment.parsed_end_at,
        parsed_valid_until=fragment.parsed_valid_until,
        organization=fragment.organization,
        specialty=specialty,
        qualification=qualification,
        faculty=faculty,
        study_form=study_form,
        category=fragment.category,
        certificate_number=fragment.certificate_number,
        confidence_score=fragment.confidence_score,
        parse_method=parse_method,
        source_field=fragment.source_field,
        shared_context_ambiguous=ambiguous,
    )


def _apply_education_shared_context(
    fragments: list[ParsedDocumentFragment],
    *,
    shared: EducationSharedContext,
) -> list[ParsedDocumentFragment]:
    if len(fragments) < 2 or not shared.has_values():
        return fragments
    propagated = EducationSharedContext(
        specialty=shared.specialty,
        qualification=shared.qualification,
        faculty=shared.faculty,
        study_form=shared.study_form,
        ambiguous=shared.ambiguous,
    )
    return [_apply_shared_context_to_fragment(fragment, propagated) for fragment in fragments]


def parse_education_graduation_fragment(
    fragment: str,
    *,
    fragment_index: int,
    source_field: str = SOURCE_FIELD_EDUCATION_TRAINING,
    diploma_specialty: str = "",
) -> ParsedDocumentFragment:
    text_val = re.sub(r"^\d+[\.)]\s*", "", fragment.strip())
    organization: Optional[str] = None
    start_at, end_at = _extract_education_dates(text_val)
    issued_at = end_at
    match = EDUCATION_UNIVERSITY_YEAR_RE.match(text_val)
    if match:
        organization = match.group(1).strip(" ,;.-")
        if end_at is None:
            end_at = date(int(match.group(2)), 1, 1)
            issued_at = end_at
    elif EDUCATION_INSTITUTION_RE.search(text_val):
        organization = YEAR_RE.sub("", text_val).strip(" ,;.-") or None
        organization = re.sub(
            r"\b(?:специальност[ьи].*)$",
            "",
            organization or "",
            flags=re.IGNORECASE,
        ).strip(" ,;.-") or organization

    specialty = _extract_specialty(text_val) or (diploma_specialty.strip() or None)
    qualification = _extract_qualification(text_val)
    faculty = _extract_faculty(text_val)
    study_form = _extract_study_form(text_val)
    title = organization or _clean_title(text_val) or specialty or "Окончание учебного заведения"

    confidence = Decimal("0.4000")
    if organization:
        confidence += Decimal("0.2000")
    if issued_at:
        confidence += Decimal("0.2000")
    if start_at:
        confidence += Decimal("0.1000")
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
        parsed_start_at=start_at,
        parsed_end_at=end_at or issued_at,
        specialty=specialty,
        qualification=qualification,
        faculty=faculty,
        study_form=study_form,
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

    if not edu:
        raw_text = f"Специальность по диплому: {diploma}"
        fragment = parse_education_graduation_fragment(
            raw_text,
            fragment_index=0,
            source_field=SOURCE_FIELD_EDUCATION,
            diploma_specialty=diploma,
        )
        fragment.raw_text = raw_text
        fragment.specialty = diploma
        fragment.title = diploma
        return [fragment]

    institution_pieces, shared_tail = split_education_institution_pieces(edu)
    if not institution_pieces:
        institution_pieces = split_raw_fragments(edu)

    shared = _merge_shared_context(
        _extract_education_shared_context(shared_tail),
        EducationSharedContext(
            specialty=diploma or None,
            ambiguous=bool(diploma and len(institution_pieces) > 1),
        ),
    )
    if shared.has_values() and len(institution_pieces) > 1 and not shared.ambiguous:
        shared = EducationSharedContext(
            specialty=shared.specialty,
            qualification=shared.qualification,
            faculty=shared.faculty,
            study_form=shared.study_form,
            ambiguous=True,
        )

    fragments: list[ParsedDocumentFragment] = []
    single_institution = len(institution_pieces) == 1
    for idx, piece in enumerate(institution_pieces):
        fragments.append(
            parse_education_graduation_fragment(
                piece,
                fragment_index=idx,
                source_field=SOURCE_FIELD_EDUCATION,
                diploma_specialty=diploma if single_institution else "",
            )
        )

    if len(fragments) > 1:
        fragments = _apply_education_shared_context(fragments, shared=shared)

    return fragments


def fragment_to_dict(fragment: ParsedDocumentFragment) -> dict[str, Any]:
    return {
        "document_kind": fragment.document_kind,
        "fragment_index": fragment.fragment_index,
        "raw_text": fragment.raw_text,
        "title": fragment.title,
        "proposed_document_type": fragment.proposed_document_type,
        "parsed_hours": fragment.parsed_hours,
        "parsed_issued_at": fragment.parsed_issued_at,
        "parsed_start_at": fragment.parsed_start_at,
        "parsed_end_at": fragment.parsed_end_at,
        "parsed_valid_until": fragment.parsed_valid_until,
        "organization": fragment.organization,
        "specialty": fragment.specialty,
        "category": fragment.category,
        "certificate_number": fragment.certificate_number,
        "confidence_score": fragment.confidence_score,
        "parse_method": fragment.parse_method,
        "source_field": fragment.source_field,
    }
