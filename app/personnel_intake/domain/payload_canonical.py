"""Version 2 canonicalisation for the applicant-owned intake JSON payload.

This module deliberately drops applicant-supplied review/normalisation fields.  Those
fields belong to the HR verification contour, not to the public form.
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any
from uuid import UUID, uuid5

_NS = UUID("b7ddbf1e-90f4-4ced-a976-6115dd1f2b8b")
_RELATIONSHIPS = {"отец", "мать", "брат", "сестра", "сын", "дочь", "жена", "муж", "супруг", "супруга", "другое"}


def _text(value: Any) -> str | None:
    value = str(value or "").strip()
    return value or None


def _uuid(item: dict[str, Any], index: int, section: str) -> str:
    try:
        return str(UUID(str(item.get("record_id") or "")))
    except ValueError:
        return str(uuid5(_NS, f"{section}:{index}:{json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)}"))


def _date(item: dict[str, Any], canonical: str, legacy: str | None = None) -> str | None:
    return _text(item.get(canonical) if canonical in item else item.get(legacy))


def _original(item: dict[str, Any], canonical: str, legacy: str) -> str | None:
    return _text(item.get(canonical) if canonical in item else item.get(legacy))


def _records(value: Any) -> list[dict[str, Any]]:
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


def _education(item: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "record_id": _uuid(item, index, "education"), "start_date": _date(item, "start_date", "year_from"),
        "end_date": _date(item, "end_date", "year_to"),
        "institution_original": _original(item, "institution_original", "institution"),
        "institution_normalized": None, "city": _text(item.get("city")),
        "country_code": _text(item.get("country_code")) or "KZ",
        "education_type": _text(item.get("education_type")) or "basic",
        "document_type": _text(item.get("document_type")) or "diploma",
        "document_number": _text(item.get("document_number") or item.get("diploma_number")),
        "document_date": _text(item.get("document_date")),
        "specialty_original": _original(item, "specialty_original", "specialty"), "specialty_normalized": None,
        "qualification_original": _original(item, "qualification_original", "qualification"), "qualification_normalized": None,
        "evidence_document_ids": [],
    }


def _training(item: dict[str, Any], index: int) -> dict[str, Any]:
    raw_hours = item.get("hours")
    try: hours = float(raw_hours) if raw_hours not in (None, "") else None
    except (TypeError, ValueError): hours = None
    if hours is not None and hours.is_integer(): hours = int(hours)
    return {
        "record_id": _uuid(item, index, "training"), "start_date": _date(item, "start_date", "year_from"),
        "end_date": _date(item, "end_date", "year_to") or _text(item.get("year")),
        "training_type": _text(item.get("training_type")) or "other",
        "course_name_original": _original(item, "course_name_original", "course_name"), "course_name_normalized": None,
        "specialty_original": _original(item, "specialty_original", "specialty"), "specialty_normalized": None,
        "institution_original": _original(item, "institution_original", "institution"), "institution_normalized": None,
        "document_type": _text(item.get("document_type")) or "certificate",
        "document_number": _text(item.get("document_number")), "document_date": _text(item.get("document_date")),
        "hours": hours, "hours_is_manual": bool(item.get("hours_is_manual")),
        "study_leave_type": _text(item.get("study_leave_type")) or "unknown",
        "employment_continued": item.get("employment_continued") if isinstance(item.get("employment_continued"), bool) else None,
        "evidence_document_ids": [],
    }


def _relative(item: dict[str, Any], index: int) -> dict[str, Any]:
    relationship = _text(item.get("relationship")) or "другое"
    other = _text(item.get("relationship_other"))
    if relationship.lower() not in _RELATIONSHIPS:
        other, relationship = relationship, "другое"
    return {"record_id": _uuid(item, index, "relatives"), "relationship": relationship,
            "relationship_other": other if relationship.lower() == "другое" else None,
            "full_name": _text(item.get("full_name")), "birth_date": _date(item, "birth_date", "birth_year"),
            "workplace": _text(item.get("workplace") if "workplace" in item else item.get("work_place"))}


def _additional_item(item: dict[str, Any], index: int, section: str) -> dict[str, Any]:
    result = {key: value for key, value in item.items() if key not in {"verification_status", "normalized", "decision_id"}}
    result["record_id"] = _uuid(item, index, section)
    for key, value in list(result.items()):
        if key != "record_id" and isinstance(value, str): result[key] = _text(value)
    return result


def _phone(value: Any) -> str | None:
    text = _text(value)
    if not text: return None
    digits = re.sub(r"\D", "", text)
    if len(digits) == 11 and digits[0] in "78": return "+7" + digits[1:]
    return text


def _employment_source(item: dict[str, Any]) -> dict[str, Any]:
    """Whitelist applicant-owned fields; never trust review or HR normalisation input."""
    return {
        "record_id": item.get("record_id"), "start_date": item.get("start_date", item.get("year_from")),
        "end_date": item.get("end_date", item.get("year_to")),
        "organization_original": item.get("organization_original", item.get("organization")),
        "city": item.get("city"), "position_original": item.get("position_original", item.get("position")),
        "reason_for_leaving": item.get("reason_for_leaving"), "note": item.get("note"),
    }


def normalize_intake_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert legacy applicant input to v2 and refuse public control of system fields."""
    source = deepcopy(payload if isinstance(payload, dict) else {})
    personal = source.get("personal") if isinstance(source.get("personal"), dict) else {}
    contacts = source.get("contacts") if isinstance(source.get("contacts"), dict) else {}
    additional = source.get("additional") if isinstance(source.get("additional"), dict) else {}
    result: dict[str, Any] = {
        "schema_version": 2,
        "personal": {key: _text(personal.get(key)) for key in ("last_name", "first_name", "middle_name", "birth_date", "birth_place")},
        "contacts": {"email": _text(contacts.get("email")), "mobile_phone": _phone(contacts.get("mobile_phone")), "residence_address": _text(contacts.get("residence_address")), "registration_address": _text(contacts.get("registration_address"))},
        "education": [_education(x, i) for i, x in enumerate(_records(source.get("education")))],
        "training": [_training(x, i) for i, x in enumerate(_records(source.get("training")))],
        "relatives": [_relative(x, i) for i, x in enumerate(_records(source.get("relatives")))],
        "employment_biography": [_employment_source(x) for x in _records(source.get("employment_biography"))],
        "current_step": _text(source.get("current_step")) or "personal",
    }
    result["personal"].update({"gender": _text(personal.get("gender")), "citizenship": _text(personal.get("citizenship")), "nationality": _text(personal.get("nationality")), "photo_file_id": _text(personal.get("photo_file_id"))})
    # personnel_number and IIN are HR/application-owned and are intentionally absent.
    for name in ("foreign_languages", "awards", "academic_degrees", "academic_titles"):
        entries = [_additional_item(x, i, name) for i, x in enumerate(_records(additional.get(name)))]
        none = bool(additional.get(f"{name}_none"))
        # Legacy drafts sometimes contain both values.  Preserve the evidence
        # and repair the flag on read; never make a flag delete user data.
        result.setdefault("additional", {})[name] = entries
        result["additional"][f"{name}_none"] = none and not entries
    military = source.get("military") if isinstance(source.get("military"), dict) else {}
    result["military"] = {"status": _text(military.get("status")) or "not_provided", **{key: _text(military.get(key)) for key in ("rank", "category", "composition", "commissariat", "specialty_code", "specialty_name", "fitness_category", "registration_group", "registration_category")}}
    return result


def additional_none_conflicts(payload: dict[str, Any]) -> list[str]:
    """Return contradictory sections in a newly submitted applicant payload."""
    additional = payload.get("additional") if isinstance(payload.get("additional"), dict) else {}
    return [name for name in ("foreign_languages", "awards", "academic_degrees", "academic_titles")
            if bool(additional.get(f"{name}_none")) and _records(additional.get(name))]
