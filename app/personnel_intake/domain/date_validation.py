"""Validate intake draft date fields for full-day precision."""
from __future__ import annotations

import re
from datetime import date
from typing import Any

ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
YEAR_ONLY_RE = re.compile(r"^\d{4}$")
PARTIAL_YEAR_RE = re.compile(r"^\d{1,3}$")
RU_DATE_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")

INTAKE_INCOMPLETE_DATE_MESSAGE = "Укажите полную дату в формате ДД.ММ.ГГГГ"


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _is_year_only_iso(text: str) -> bool:
    match = ISO_DATE_RE.match(text)
    if not match:
        return False
    return match.group(2) == "01" and match.group(3) == "01"


def _parse_to_iso(value: Any) -> str | None:
    text = _normalize_text(value)
    if not text:
        return None
    if ISO_DATE_RE.match(text):
        return text[:10]
    ru_match = RU_DATE_RE.match(text)
    if ru_match:
        day, month, year = ru_match.groups()
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    return None


def is_valid_intake_full_date_iso(value: Any) -> bool:
    iso = _parse_to_iso(value)
    if not iso:
        return False
    try:
        date.fromisoformat(iso)
    except ValueError:
        return False
    return True


def is_incomplete_intake_period_date(value: Any) -> bool:
    text = _normalize_text(value)
    if not text:
        return False
    if PARTIAL_YEAR_RE.match(text) or YEAR_ONLY_RE.match(text):
        return True
    if ISO_DATE_RE.match(text):
        return _is_year_only_iso(text)
    ru_match = RU_DATE_RE.match(text)
    if ru_match and ru_match.group(1) == "01" and ru_match.group(2) == "01":
        return True
    return not is_valid_intake_full_date_iso(text)


def is_incomplete_intake_birth_date(value: Any) -> bool:
    text = _normalize_text(value)
    if not text:
        return False
    if PARTIAL_YEAR_RE.match(text) or YEAR_ONLY_RE.match(text):
        return True
    return not is_valid_intake_full_date_iso(text)


def is_incomplete_document_date(value: Any) -> bool:
    return is_incomplete_intake_period_date(value)


def normalize_document_date_for_storage(value: Any) -> str:
    text = _normalize_text(value)
    if not text:
        return ""
    if text.lower() == "постоянно":
        return text
    if is_incomplete_document_date(text):
        return text
    iso = _parse_to_iso(text)
    if iso and is_valid_intake_full_date_iso(iso):
        return iso
    return text


def validate_document_date_field(value: Any, *, field: str, errors: list[str]) -> None:
    text = _normalize_text(value)
    if not text:
        return
    if text.lower() == "постоянно":
        return
    if is_incomplete_document_date(text):
        errors.append(f"{field}: {INTAKE_INCOMPLETE_DATE_MESSAGE}")
        return
    if not is_valid_intake_full_date_iso(text):
        errors.append(f"{field}: {INTAKE_INCOMPLETE_DATE_MESSAGE}")


def collect_intake_date_validation_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    personal = payload.get("personal") or {}
    if is_incomplete_intake_birth_date(personal.get("birth_date")):
        errors.append("personal.birth_date")

    education = payload.get("education") or []
    if isinstance(education, list):
        for index, item in enumerate(education):
            if not isinstance(item, dict):
                continue
            if is_incomplete_intake_period_date(item.get("year_from")):
                errors.append(f"education[{index}].year_from")
            if is_incomplete_intake_period_date(item.get("year_to")):
                errors.append(f"education[{index}].year_to")

    training = payload.get("training") or []
    if isinstance(training, list):
        for index, item in enumerate(training):
            if not isinstance(item, dict):
                continue
            if is_incomplete_intake_period_date(item.get("year")):
                errors.append(f"training[{index}].year")

    relatives = payload.get("relatives") or []
    if isinstance(relatives, list):
        for index, item in enumerate(relatives):
            if not isinstance(item, dict):
                continue
            if is_incomplete_intake_period_date(item.get("birth_year")):
                errors.append(f"relatives[{index}].birth_year")

    employment = payload.get("employment_biography") or []
    if isinstance(employment, list):
        for index, item in enumerate(employment):
            if not isinstance(item, dict):
                continue
            if is_incomplete_intake_period_date(item.get("year_from")):
                errors.append(f"employment_biography[{index}].year_from")
            if is_incomplete_intake_period_date(item.get("year_to")):
                errors.append(f"employment_biography[{index}].year_to")

    return errors
