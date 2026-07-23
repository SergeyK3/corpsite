"""Section-scoped profile_override merge for HR import staging (Phase 2F.4)."""
from __future__ import annotations

import copy
import re
from typing import Any, Optional
from urllib.parse import urlparse

from app.personnel_intake.domain.date_validation import (
    is_incomplete_document_date,
    normalize_document_date_for_storage,
    validate_document_date_field,
)

_CATEGORY_CODE_TO_LABEL = {
    "highest": "Высшая",
    "first": "Первая",
    "second": "Вторая",
    "specialist_certificate": "Сертификат специалиста",
    "none": "Без категории",
    "other": "Другое",
}

_CATEGORY_LABEL_TO_CODE = {label.lower(): code for code, label in _CATEGORY_CODE_TO_LABEL.items()}
_CATEGORY_LABEL_TO_CODE.update(
    {
        "высшая": "highest",
        "первая": "first",
        "вторая": "second",
        "сертификат специалиста": "specialist_certificate",
        "без категории": "none",
        "другое": "other",
    }
)

_YEAR_RE = re.compile(r"^\d{4}$")
_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4})$", re.IGNORECASE)
_YEAR_ONLY_DATE_RE = re.compile(r"^01\.01\.\d{4}$")
_SECTION_KEYS = frozenset({"education", "training", "categories", "certificates", "degree", "awards", "notes"})


def category_display_label(value: str) -> str:
    text_val = (value or "").strip()
    if not text_val:
        return ""
    lowered = text_val.lower()
    if lowered in _CATEGORY_CODE_TO_LABEL:
        return _CATEGORY_CODE_TO_LABEL[lowered]
    if lowered in _CATEGORY_LABEL_TO_CODE:
        return _CATEGORY_CODE_TO_LABEL[_CATEGORY_LABEL_TO_CODE[lowered]]
    return text_val


_FULL_PROFILE_KEYS = frozenset(
    {
        "basic",
        "education_records",
        "training_records",
        "category_records",
        "certificate_records",
        "award_records",
        "degrees",
        "notes_raw",
        "status",
        "review_status",
        "portfolio",
    }
)


def is_section_override(override: Any) -> bool:
    if not isinstance(override, dict) or not override:
        return False
    keys = set(override.keys())
    if keys & _FULL_PROFILE_KEYS:
        return False
    return bool(keys & _SECTION_KEYS)


def is_year_only_date(value: str) -> bool:
    return is_incomplete_document_date(value)


def _normalize_date_value(value: Any) -> str:
    return normalize_document_date_for_storage(value)


def _validate_year(value: Any, *, field: str, errors: list[str]) -> None:
    text_val = str(value or "").strip()
    if text_val:
        _validate_date(text_val, field=field, errors=errors)


def _validate_date(value: Any, *, field: str, errors: list[str]) -> None:
    text_val = str(value or "").strip()
    if not text_val:
        return
    if text_val.lower() == "постоянно":
        return
    if _DATE_RE.match(text_val) or is_year_only_date(text_val):
        return
    errors.append(f"{field}: дата должна быть YYYY-MM-DD, DD.MM.YYYY или «постоянно»")


def _validate_hours(value: Any, *, field: str, errors: list[str]) -> None:
    if value is None or value == "":
        return
    try:
        float(value)
    except (TypeError, ValueError):
        errors.append(f"{field}: часы должны быть числом или пусто")


def _validate_url(value: Any, *, field: str, errors: list[str]) -> None:
    text_val = str(value or "").strip()
    if not text_val:
        return
    parsed = urlparse(text_val)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        errors.append(f"{field}: ссылка должна быть URL или пусто")


def validate_profile_override(override: dict[str, Any]) -> None:
    errors: list[str] = []
    training = override.get("training")
    if training is not None:
        if not isinstance(training, list):
            errors.append("training: must be a list")
        else:
            for idx, row in enumerate(training, start=1):
                if not isinstance(row, dict):
                    errors.append(f"training[{idx}]: must be an object")
                    continue
                validate_document_date_field(
                    row.get("date") or row.get("year") or row.get("completed_at"),
                    field=f"training[{idx}].date",
                    errors=errors,
                )
                _validate_hours(row.get("hours"), field=f"training[{idx}].hours", errors=errors)

    categories = override.get("categories")
    if categories is not None:
        if not isinstance(categories, list):
            errors.append("categories: must be a list")
        else:
            for idx, row in enumerate(categories, start=1):
                if not isinstance(row, dict):
                    errors.append(f"categories[{idx}]: must be an object")
                    continue
                validate_document_date_field(
                    row.get("date") or row.get("issued_at"),
                    field=f"categories[{idx}].date",
                    errors=errors,
                )

    certificates = override.get("certificates")
    if certificates is not None:
        if not isinstance(certificates, list):
            errors.append("certificates: must be a list")
        else:
            for idx, row in enumerate(certificates, start=1):
                if not isinstance(row, dict):
                    errors.append(f"certificates[{idx}]: must be an object")
                    continue
                validate_document_date_field(
                    row.get("date") or row.get("issued_at"),
                    field=f"certificates[{idx}].date",
                    errors=errors,
                )
                validate_document_date_field(
                    row.get("valid_until"),
                    field=f"certificates[{idx}].valid_until",
                    errors=errors,
                )
                _validate_hours(row.get("hours"), field=f"certificates[{idx}].hours", errors=errors)
                _validate_url(row.get("link"), field=f"certificates[{idx}].link", errors=errors)

    awards = override.get("awards")
    if awards is not None:
        if not isinstance(awards, list):
            errors.append("awards: must be a list")
        else:
            for idx, row in enumerate(awards, start=1):
                if not isinstance(row, dict):
                    errors.append(f"awards[{idx}]: must be an object")
                    continue
                validate_document_date_field(row.get("date"), field=f"awards[{idx}].date", errors=errors)

    degree = override.get("degree")
    if isinstance(degree, list):
        for idx, row in enumerate(degree, start=1):
            if not isinstance(row, dict):
                errors.append(f"degree[{idx}]: must be an object")
                continue
            validate_document_date_field(
                row.get("date") or row.get("completed_at"),
                field=f"degree[{idx}].date",
                errors=errors,
            )

    education = override.get("education")
    if education is not None:
        if not isinstance(education, list):
            errors.append("education: must be a list")
        else:
            for idx, row in enumerate(education, start=1):
                if not isinstance(row, dict):
                    errors.append(f"education[{idx}]: must be an object")
                    continue
                validate_document_date_field(
                    row.get("date") or row.get("completed_at"),
                    field=f"education[{idx}].date",
                    errors=errors,
                )

    if errors:
        raise ValueError("; ".join(errors))


def _hours_value(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _training_to_override(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for record in records:
        raw_date = record.get("completed_at") or record.get("date") or record.get("year")
        items.append(
            {
                "title": str(record.get("title") or ""),
                "organization": str(record.get("organization") or ""),
                "date": _normalize_date_value(raw_date),
                "hours": _hours_value(record.get("hours")),
            }
        )
    return items


def _categories_to_override(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for record in records:
        items.append(
            {
                "category": category_display_label(str(record.get("category") or "")),
                "date": normalize_document_date_for_storage(record.get("issued_at") or record.get("date") or ""),
                "specialty": str(record.get("specialty") or ""),
            }
        )
    return items


def _certificates_to_override(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for record in records:
        items.append(
            {
                "kind": str(record.get("kind") or ""),
                "topic": str(record.get("topic") or record.get("specialty") or ""),
                "date": normalize_document_date_for_storage(record.get("issued_at") or record.get("date") or ""),
                "valid_until": normalize_document_date_for_storage(record.get("valid_until") or ""),
                "hours": _hours_value(record.get("hours")),
                "link": str(record.get("link") or ""),
            }
        )
    return items


def _awards_to_override(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for record in records:
        items.append(
            {
                "title": str(record.get("title") or ""),
                "date": _normalize_date_value(record.get("date") or ""),
            }
        )
    return items


def _education_to_override(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for record in records:
        items.append(
            {
                "institution": str(record.get("institution") or ""),
                "specialty": str(record.get("specialty") or ""),
                "date": _normalize_date_value(record.get("completed_at") or record.get("date") or ""),
                "record_type": str(record.get("record_type") or "basic"),
            }
        )
    return items


def _group_education_records(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {
        "basic": [],
        "internship": [],
        "residency": [],
        "masters": [],
        "phd": [],
    }
    for record in records:
        record_type = str(record.get("record_type") or "basic")
        if record_type not in grouped:
            record_type = "basic"
        grouped[record_type].append(record)
    return grouped


def extract_editable_sections_override(profile: dict[str, Any]) -> dict[str, Any]:
    """Build section override payload from displayed/edited profile."""
    degrees = profile.get("degrees") or {}
    return {
        "education": _education_to_override(profile.get("education_records") or []),
        "training": _training_to_override(profile.get("training_records") or []),
        "categories": _categories_to_override(profile.get("category_records") or []),
        "certificates": _certificates_to_override(profile.get("certificate_records") or []),
        "degree": _degrees_to_override(degrees),
        "awards": _awards_to_override(profile.get("award_records") or []),
        "notes": str(profile.get("notes_raw") or ""),
    }


def _education_from_override(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in items:
        records.append(
            {
                "record_type": str(item.get("record_type") or "basic"),
                "institution": str(item.get("institution") or ""),
                "specialty": str(item.get("specialty") or ""),
                "completed_at": _normalize_date_value(item.get("date") or item.get("completed_at") or ""),
                "source_field": "profile_override",
                "source_text": "",
                "confidence": 1.0,
                "parse_method": "manual_override",
                "document_id": None,
            }
        )
    return records


def _training_from_override(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in items:
        records.append(
            {
                "title": str(item.get("title") or ""),
                "organization": str(item.get("organization") or ""),
                "hours": _hours_value(item.get("hours")),
                "started_at": "",
                "completed_at": _normalize_date_value(item.get("date") or item.get("year") or item.get("completed_at") or ""),
                "source_field": "profile_override",
                "source_text": "",
                "confidence": 1.0,
                "parse_method": "manual_override",
                "document_id": None,
            }
        )
    return records


def _categories_from_override(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in items:
        records.append(
            {
                "category": category_display_label(str(item.get("category") or "")),
                "specialty": str(item.get("specialty") or ""),
                "issued_at": normalize_document_date_for_storage(item.get("date") or item.get("issued_at") or ""),
                "source_field": "profile_override",
                "source_text": "",
                "confidence": 1.0,
                "parse_method": "manual_override",
                "document_id": None,
            }
        )
    return records


def _certificates_from_override(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in items:
        records.append(
            {
                "kind": str(item.get("kind") or ""),
                "topic": str(item.get("topic") or ""),
                "specialty": str(item.get("topic") or ""),
                "issued_at": normalize_document_date_for_storage(item.get("date") or item.get("issued_at") or ""),
                "valid_until": normalize_document_date_for_storage(item.get("valid_until") or ""),
                "hours": _hours_value(item.get("hours")),
                "link": str(item.get("link") or ""),
                "certificate_number": "",
                "source_field": "profile_override",
                "source_text": "",
                "confidence": 1.0,
                "parse_method": "manual_override",
                "document_id": None,
            }
        )
    return records


def _awards_from_override(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in items:
        records.append(
            {
                "title": str(item.get("title") or ""),
                "date": _normalize_date_value(item.get("date") or ""),
                "source_field": "profile_override",
                "source_text": "",
                "confidence": 1.0,
                "parse_method": "manual_override",
                "document_id": None,
            }
        )
    return records


def _infer_degree_type(label: str) -> str:
    lowered = (label or "").lower()
    if re.search(r"кандидат\s+мед", lowered):
        return "candidate_medical_sciences"
    if re.search(r"доктор\s+мед", lowered):
        return "doctor_medical_sciences"
    return "other"


def _degrees_to_override(degrees: dict[str, Any]) -> list[dict[str, Any]]:
    records = degrees.get("records") or []
    items: list[dict[str, Any]] = []
    if records:
        for record in records:
            label = str(record.get("label") or record.get("source_text") or "")
            items.append(
                {
                    "label": label,
                    "date": _normalize_date_value(record.get("completed_at") or record.get("date") or ""),
                }
            )
        return items
    raw_text = str(degrees.get("raw_text") or "").strip()
    if raw_text:
        return [{"label": raw_text, "date": ""}]
    return []


def _degree_from_override_text(raw_text: str, base_degrees: Optional[dict[str, Any]]) -> dict[str, Any]:
    text_val = str(raw_text or "")
    lowered = text_val.lower()
    candidate = bool(re.search(r"кандидат\s+мед", lowered))
    doctor = bool(re.search(r"доктор\s+мед", lowered))
    records: list[dict[str, Any]] = []
    if candidate:
        records.append(
            {
                "degree_type": "candidate_medical_sciences",
                "label": "Кандидат медицинских наук",
                "completed_at": "",
                "source_field": "profile_override",
                "source_text": text_val,
                "confidence": 1.0,
                "parse_method": "manual_override",
                "document_id": None,
            }
        )
    if doctor:
        records.append(
            {
                "degree_type": "doctor_medical_sciences",
                "label": "Доктор медицинских наук",
                "completed_at": "",
                "source_field": "profile_override",
                "source_text": text_val,
                "confidence": 1.0,
                "parse_method": "manual_override",
                "document_id": None,
            }
        )
    return {
        "candidate_medical_sciences": candidate,
        "doctor_medical_sciences": doctor,
        "raw_text": text_val,
        "records": records or list((base_degrees or {}).get("records") or []),
    }


def _degrees_from_override_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    labels: list[str] = []
    for item in items:
        label = str(item.get("label") or item.get("degree") or "").strip()
        if not label:
            continue
        labels.append(label)
        records.append(
            {
                "degree_type": _infer_degree_type(label),
                "label": label,
                "completed_at": _normalize_date_value(item.get("date") or item.get("completed_at") or ""),
                "source_field": "profile_override",
                "source_text": label,
                "confidence": 1.0,
                "parse_method": "manual_override",
                "document_id": None,
            }
        )
    raw_text = "; ".join(labels)
    return {
        "candidate_medical_sciences": any(r["degree_type"] == "candidate_medical_sciences" for r in records),
        "doctor_medical_sciences": any(r["degree_type"] == "doctor_medical_sciences" for r in records),
        "raw_text": raw_text,
        "records": records,
    }


def _degree_from_override(value: Any, base_degrees: Optional[dict[str, Any]]) -> dict[str, Any]:
    if isinstance(value, list):
        return _degrees_from_override_items(value)
    return _degree_from_override_text(str(value or ""), base_degrees)


def _recompute_portfolio_totals(profile: dict[str, Any]) -> None:
    degrees = profile.get("degrees") or {}
    profile["portfolio_totals"] = {
        "education": len(profile.get("education_records") or []),
        "training": len(profile.get("training_records") or []),
        "categories": len(profile.get("category_records") or []),
        "certificates": len(profile.get("certificate_records") or []),
        "awards": len(profile.get("award_records") or []),
        "degrees": len(degrees.get("records") or []),
    }


def apply_profile_override(base_profile: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Replace editable sections from section-scoped override."""
    profile = copy.deepcopy(base_profile)
    if "education" in override:
        education_records = _education_from_override(override.get("education") or [])
        profile["education_records"] = education_records
        profile["education"] = _group_education_records(education_records)
    if "training" in override:
        profile["training_records"] = _training_from_override(override.get("training") or [])
    if "categories" in override:
        profile["category_records"] = _categories_from_override(override.get("categories") or [])
    if "certificates" in override:
        profile["certificate_records"] = _certificates_from_override(override.get("certificates") or [])
    if "degree" in override:
        profile["degrees"] = _degree_from_override(override.get("degree"), profile.get("degrees"))
    if "awards" in override:
        profile["award_records"] = _awards_from_override(override.get("awards") or [])
    if "notes" in override:
        profile["notes_raw"] = str(override.get("notes") or "")
    _recompute_portfolio_totals(profile)
    return profile


def prepare_profile_override_for_storage(profile_input: dict[str, Any]) -> dict[str, Any]:
    """Accept full profile or section override from API and normalize for JSONB storage."""
    if is_section_override(profile_input):
        override = copy.deepcopy(profile_input)
    else:
        override = extract_editable_sections_override(profile_input)
    if isinstance(override.get("education"), list):
        for row in override["education"]:
            if isinstance(row, dict):
                row["date"] = _normalize_date_value(row.get("date") or row.get("completed_at"))
                row.pop("completed_at", None)
    if isinstance(override.get("training"), list):
        for row in override["training"]:
            if isinstance(row, dict):
                row["date"] = _normalize_date_value(row.get("date") or row.get("year"))
                row.pop("year", None)
    if isinstance(override.get("categories"), list):
        for row in override["categories"]:
            if isinstance(row, dict):
                row["date"] = normalize_document_date_for_storage(row.get("date"))
    if isinstance(override.get("certificates"), list):
        for row in override["certificates"]:
            if isinstance(row, dict):
                row["date"] = normalize_document_date_for_storage(row.get("date"))
                row["valid_until"] = normalize_document_date_for_storage(row.get("valid_until"))
    if isinstance(override.get("awards"), list):
        for row in override["awards"]:
            if isinstance(row, dict):
                row["date"] = _normalize_date_value(row.get("date"))
    if isinstance(override.get("degree"), list):
        for row in override["degree"]:
            if isinstance(row, dict):
                row["label"] = str(row.get("label") or row.get("degree") or "")
                row.pop("degree", None)
                row["date"] = _normalize_date_value(row.get("date") or row.get("completed_at"))
                row.pop("completed_at", None)
    validate_profile_override(override)
    return override
