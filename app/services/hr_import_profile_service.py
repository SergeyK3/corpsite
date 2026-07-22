"""Employee import profile card — ADR-039 education portfolio foundation (Phase 2F.2)."""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Optional

from app.services.hr_import_document_parser import (
    parse_certification_raw,
    parse_education_raw,
    parse_education_training_raw,
    split_raw_fragments,
)

EDUCATION_TYPE_BASIC = "basic"
EDUCATION_TYPE_INTERNSHIP = "internship"
EDUCATION_TYPE_RESIDENCY = "residency"
EDUCATION_TYPE_MASTERS = "masters"
EDUCATION_TYPE_PHD = "phd"

_EDUCATION_TYPE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (EDUCATION_TYPE_INTERNSHIP, re.compile(r"\bинтернатур", re.IGNORECASE)),
    (EDUCATION_TYPE_RESIDENCY, re.compile(r"\b(?:ординатур|резидентур)", re.IGNORECASE)),
    (EDUCATION_TYPE_MASTERS, re.compile(r"\bмагистр", re.IGNORECASE)),
    (EDUCATION_TYPE_PHD, re.compile(r"\b(?:ph\.?\s*d|доктор\s+наук|к\.?\s*м\.?\s*н\.?)\b", re.IGNORECASE)),
)

_RATE_RE = re.compile(
    r"(?:ставк[аи]\s*[:=]?\s*)?(?P<rate>0[.,]5|1[.,]0?|1[.,]5|2[.,]0?)\b",
    re.IGNORECASE,
)


def _format_date(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        d = value
        if d.month == 1 and d.day == 1 and d.year >= 1900:
            return str(d.year)
        return d.isoformat()
    return str(value)


def _confidence(value: Decimal | float | None) -> float:
    if value is None:
        return 0.0
    return round(float(value), 4)


def _infer_education_type(text: str) -> str:
    for edu_type, pattern in _EDUCATION_TYPE_PATTERNS:
        if pattern.search(text):
            return edu_type
    return EDUCATION_TYPE_BASIC


def _normalize_sex(value: str) -> str:
    text_val = (value or "").strip().lower()
    if text_val in ("м", "m", "male", "муж", "мужской"):
        return "M"
    if text_val in ("ж", "f", "female", "жен", "женский"):
        return "F"
    return text_val or ""


def _extract_employment_rate(position_raw: str) -> Optional[float]:
    match = _RATE_RE.search(position_raw or "")
    if not match:
        return None
    try:
        return float(match.group("rate").replace(",", "."))
    except ValueError:
        return None


def _parse_awards(raw: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for piece in split_raw_fragments(raw):
        text_val = piece.strip()
        if not text_val:
            continue
        year_match = re.search(r"\b(19|20)\d{2}\b", text_val)
        award_date = year_match.group(0) if year_match else ""
        title = re.sub(r"\b(19|20)\d{2}\b", "", text_val).strip(" ,;.-")
        items.append(
            {
                "title": title or text_val,
                "date": award_date,
                "source_field": "awards_raw",
                "source_text": text_val,
                "confidence": 0.5 if award_date else 0.35,
                "parse_method": "regex_v1",
                "document_id": None,
            }
        )
    return items


def _parse_degrees(raw: str) -> dict[str, Any]:
    lowered = (raw or "").lower()
    candidate = bool(re.search(r"кандидат\s+мед", lowered))
    doctor = bool(re.search(r"доктор\s+мед", lowered))
    records: list[dict[str, Any]] = []
    if candidate:
        records.append(
            {
                "degree_type": "candidate_medical_sciences",
                "label": "Кандидат медицинских наук",
                "completed_at": "",
                "source_field": "degree_raw",
                "source_text": raw or "",
                "confidence": 0.85,
                "parse_method": "regex_v1",
                "document_id": None,
            }
        )
    if doctor:
        records.append(
            {
                "degree_type": "doctor_medical_sciences",
                "label": "Доктор медицинских наук",
                "completed_at": "",
                "source_field": "degree_raw",
                "source_text": raw or "",
                "confidence": 0.85,
                "parse_method": "regex_v1",
                "document_id": None,
            }
        )
    return {
        "candidate_medical_sciences": candidate,
        "doctor_medical_sciences": doctor,
        "raw_text": raw or "",
        "records": records,
    }


def build_import_profile(payload: dict[str, Any]) -> dict[str, Any]:
    """Build structured employee import profile from staging normalized_payload."""
    education_raw = str(payload.get("education_raw", "") or "")
    diploma_specialty = str(payload.get("diploma_specialty_raw", "") or "")
    qualification_raw = str(payload.get("qualification_raw", "") or "")
    training_source = str(
        payload.get("education_training_raw", "") or payload.get("training_raw", "") or ""
    )
    certification_raw = str(payload.get("certification_raw", "") or "")
    degree_raw = str(payload.get("degree_raw", "") or "")
    awards_raw = str(payload.get("awards_raw", "") or "")
    position_raw = str(payload.get("position_raw", "") or "")

    education_by_type: dict[str, list[dict[str, Any]]] = {
        EDUCATION_TYPE_BASIC: [],
        EDUCATION_TYPE_INTERNSHIP: [],
        EDUCATION_TYPE_RESIDENCY: [],
        EDUCATION_TYPE_MASTERS: [],
        EDUCATION_TYPE_PHD: [],
    }
    education_records: list[dict[str, Any]] = []

    for frag in parse_education_raw(education_raw, diploma_specialty):
        edu_type = _infer_education_type(frag.raw_text)
        record = {
            "record_type": edu_type,
            "institution": frag.organization or frag.title or "",
            "specialty": frag.specialty or "",
            "qualification": frag.qualification or "",
            "faculty": frag.faculty or "",
            "study_form": frag.study_form or "",
            "started_at": _format_date(frag.parsed_start_at),
            "completed_at": _format_date(frag.parsed_end_at or frag.parsed_issued_at),
            "source_field": frag.source_field or "education_raw",
            "source_text": frag.raw_text,
            "confidence": _confidence(frag.confidence_score),
            "parse_method": frag.parse_method,
            "document_id": None,
        }
        education_by_type[edu_type].append(record)
        education_records.append(record)

    for frag in parse_education_training_raw(training_source):
        if frag.document_kind != "training" and _infer_education_type(frag.raw_text) != EDUCATION_TYPE_BASIC:
            edu_type = _infer_education_type(frag.raw_text)
            if edu_type != EDUCATION_TYPE_BASIC:
                record = {
                    "record_type": edu_type,
                    "institution": frag.organization or frag.title or "",
                    "specialty": frag.specialty or "",
                    "completed_at": _format_date(frag.parsed_issued_at),
                    "source_field": frag.source_field or "education_training_raw",
                    "source_text": frag.raw_text,
                    "confidence": _confidence(frag.confidence_score),
                    "parse_method": frag.parse_method,
                    "document_id": None,
                }
                education_by_type[edu_type].append(record)
                education_records.append(record)

    training_records: list[dict[str, Any]] = []
    for frag in parse_education_training_raw(training_source):
        if frag.document_kind == "training":
            training_records.append(
                {
                    "title": frag.title or frag.raw_text,
                    "organization": frag.organization or "",
                    "hours": float(frag.parsed_hours) if frag.parsed_hours is not None else None,
                    "started_at": "",
                    "completed_at": _format_date(frag.parsed_issued_at),
                    "source_field": frag.source_field or "education_training_raw",
                    "source_text": frag.raw_text,
                    "confidence": _confidence(frag.confidence_score),
                    "parse_method": frag.parse_method,
                    "document_id": None,
                }
            )

    category_records: list[dict[str, Any]] = []
    certificate_records: list[dict[str, Any]] = []
    for frag in parse_certification_raw(certification_raw):
        issued = _format_date(frag.parsed_issued_at or frag.parsed_valid_until)
        valid_until = _format_date(frag.parsed_valid_until)
        if frag.proposed_document_type == "QUALIFICATION_CATEGORY":
            category_records.append(
                {
                    "category": frag.category or frag.title or "",
                    "specialty": frag.specialty or "",
                    "issued_at": issued,
                    "source_field": frag.source_field or "certification_raw",
                    "source_text": frag.raw_text,
                    "confidence": _confidence(frag.confidence_score),
                    "parse_method": frag.parse_method,
                    "document_id": None,
                }
            )
        else:
            certificate_records.append(
                {
                    "kind": frag.category or frag.proposed_document_type or "Сертификат",
                    "topic": frag.title or frag.raw_text,
                    "specialty": frag.specialty or frag.title or "",
                    "issued_at": issued,
                    "valid_until": valid_until,
                    "hours": float(frag.parsed_hours) if frag.parsed_hours is not None else None,
                    "link": "",
                    "certificate_number": frag.certificate_number or "",
                    "source_field": frag.source_field or "certification_raw",
                    "source_text": frag.raw_text,
                    "confidence": _confidence(frag.confidence_score),
                    "parse_method": frag.parse_method,
                    "document_id": None,
                }
            )

    if qualification_raw.strip() and not category_records:
        category_records.append(
            {
                "category": qualification_raw.strip(),
                "specialty": diploma_specialty.strip(),
                "issued_at": "",
                "source_field": "qualification_raw",
                "source_text": qualification_raw.strip(),
                "confidence": 0.4,
                "parse_method": "regex_v1",
                "document_id": None,
            }
        )

    degrees = _parse_degrees(degree_raw)
    award_records = _parse_awards(awards_raw)

    return {
        "basic": {
            "full_name": str(payload.get("full_name", "") or ""),
            "iin": str(payload.get("iin", "") or ""),
            "birth_date": str(payload.get("birth_date", "") or ""),
            "sex": _normalize_sex(str(payload.get("sex", "") or "")),
            "position_raw": position_raw,
            "department_source": str(payload.get("department", "") or ""),
            "experience_raw": str(payload.get("experience_raw", "") or ""),
            "employment_rate": _extract_employment_rate(position_raw),
            "qualification_raw": qualification_raw.strip(),
            "nationality": str(payload.get("nationality", "") or ""),
            "phone_raw": str(payload.get("phone_raw", "") or ""),
        },
        "education": education_by_type,
        "education_records": education_records,
        "training_records": training_records,
        "category_records": category_records,
        "certificate_records": certificate_records,
        "award_records": award_records,
        "degrees": degrees,
        "portfolio_totals": {
            "education": len(education_records),
            "training": len(training_records),
            "categories": len(category_records),
            "certificates": len(certificate_records),
            "awards": len(award_records),
            "degrees": len(degrees["records"]),
        },
    }
