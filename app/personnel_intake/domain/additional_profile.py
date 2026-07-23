"""Canonical additional profile payload shared by intake and PPR read."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

INTAKE_ACADEMIC_DEGREE_OTHER = "Другое"
INTAKE_ACADEMIC_TITLE_OTHER = "Другое"
INTAKE_AWARD_OTHER = "Другая"

KNOWN_DEGREES = {
    "Кандидат наук",
    "Доктор наук",
    "PhD",
    "Доктор по профилю",
}
KNOWN_TITLES = {
    "Доцент",
    "Профессор",
    "Ассоциированный профессор",
}
KNOWN_AWARD_CATEGORIES = {
    "Государственная",
    "Ведомственная",
    "Почётная грамота",
    "Благодарность",
    "Нагрудный знак",
    "Медаль",
    INTAKE_AWARD_OTHER,
}
LEGACY_AWARD_CATEGORY_ALIASES = {
    "Государственная награда": "Государственная",
    "Ведомственная награда": "Ведомственная",
    "Юбилейная медаль": "Медаль",
    "Другое": INTAKE_AWARD_OTHER,
}


def empty_additional_profile() -> dict[str, Any]:
    return {
        "foreign_languages": [],
        "foreign_languages_none": False,
        "awards": [],
        "awards_none": False,
        "academic_degrees": [],
        "academic_degrees_none": False,
        "academic_titles": [],
        "academic_titles_none": False,
    }


def _normalize_bool(value: Any) -> bool:
    return bool(value)


def _normalize_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def normalize_foreign_language_entry(item: dict[str, Any]) -> dict[str, str]:
    return {
        "language": str(item.get("language") or "").strip(),
        "proficiency": str(item.get("proficiency") or "").strip(),
    }


def _resolve_award_category(value: str) -> str:
    trimmed = str(value or "").strip()
    if not trimmed:
        return ""
    if trimmed in KNOWN_AWARD_CATEGORIES:
        return trimmed
    return LEGACY_AWARD_CATEGORY_ALIASES.get(trimmed, "")


def normalize_award_entry(item: dict[str, Any]) -> dict[str, str]:
    category = _resolve_award_category(str(item.get("category") or "").strip())
    name = str(item.get("name") or "").strip()
    legacy_title = str(item.get("title") or "").strip()

    if not category and not name and legacy_title:
        resolved_category = _resolve_award_category(legacy_title)
        if resolved_category:
            category = resolved_category
        else:
            name = legacy_title

    return {
        "category": category,
        "name": name,
        "issued_by": str(item.get("issued_by") or "").strip(),
        "awarded_at": str(item.get("awarded_at") or item.get("date") or "").strip(),
        "document_number": str(item.get("document_number") or "").strip(),
    }


def _migrate_legacy_combined_academic_fields(item: dict[str, Any]) -> dict[str, Any]:
    label = str(item.get("label") or "").strip()
    degree_type = str(item.get("degree_type") or "").strip()
    degree = str(item.get("degree") or "").strip()
    degree_other = str(item.get("degree_other") or "").strip()
    field_of_science = str(item.get("field_of_science") or "").strip()
    academic_title = str(item.get("academic_title") or "").strip()
    academic_title_other = str(item.get("academic_title_other") or "").strip()

    if not degree and not degree_other and label:
        if label in KNOWN_DEGREES:
            degree = label
        elif label in KNOWN_TITLES:
            academic_title = label
        else:
            degree = INTAKE_ACADEMIC_DEGREE_OTHER
            degree_other = label

    if not academic_title and not academic_title_other and label:
        for title in KNOWN_TITLES:
            if title in label:
                academic_title = title
                break

    if not field_of_science and degree_type:
        field_of_science = degree_type

    return {
        "degree": degree,
        "degree_other": degree_other,
        "field_of_science": field_of_science,
        "academic_title": academic_title,
        "academic_title_other": academic_title_other,
        "completed_at": str(item.get("completed_at") or "").strip(),
        "document_number": str(item.get("document_number") or "").strip(),
        "label": label,
        "degree_type": degree_type,
    }


def normalize_academic_degree_entry(item: dict[str, Any]) -> dict[str, Any]:
    migrated = _migrate_legacy_combined_academic_fields(item)
    normalized: dict[str, Any] = {
        "degree": migrated["degree"],
        "degree_other": migrated["degree_other"],
        "field_of_science": migrated["field_of_science"],
        "completed_at": migrated["completed_at"],
        "document_number": migrated["document_number"],
    }
    if migrated["label"]:
        normalized["label"] = migrated["label"]
    if migrated["degree_type"]:
        normalized["degree_type"] = migrated["degree_type"]
    return normalized


def normalize_academic_title_entry(item: dict[str, Any]) -> dict[str, Any]:
    migrated = _migrate_legacy_combined_academic_fields(item)
    normalized: dict[str, Any] = {
        "academic_title": migrated["academic_title"],
        "academic_title_other": migrated["academic_title_other"],
        "field_of_science": migrated["field_of_science"],
        "completed_at": migrated["completed_at"],
        "document_number": migrated["document_number"],
    }
    if migrated["label"]:
        normalized["label"] = migrated["label"]
    if migrated["degree_type"]:
        normalized["degree_type"] = migrated["degree_type"]
    return normalized


def _split_legacy_combined_academic_entry(item: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    migrated = _migrate_legacy_combined_academic_fields(item)
    has_degree = bool(migrated["degree"] or migrated["degree_other"])
    has_title = bool(migrated["academic_title"] or migrated["academic_title_other"])

    degree_entries: list[dict[str, Any]] = []
    title_entries: list[dict[str, Any]] = []

    if has_degree:
        degree_entries.append(normalize_academic_degree_entry(migrated))
    if has_title:
        title_entries.append(normalize_academic_title_entry(migrated))

    return degree_entries, title_entries


def normalize_additional_profile(raw: dict[str, Any] | None) -> dict[str, Any]:
    source = dict(raw) if isinstance(raw, dict) else {}
    template = empty_additional_profile()
    legacy_split_titles: list[dict[str, Any]] = []
    academic_degrees: list[dict[str, Any]] = []
    for item in _normalize_list(source.get("academic_degrees")):
        split_degrees, split_titles = _split_legacy_combined_academic_entry(item)
        academic_degrees.extend(split_degrees)
        legacy_split_titles.extend(split_titles)
    academic_titles = [normalize_academic_title_entry(item) for item in legacy_split_titles]
    academic_titles.extend(
        normalize_academic_title_entry(item) for item in _normalize_list(source.get("academic_titles"))
    )
    return {
        "foreign_languages": [
            normalize_foreign_language_entry(item) for item in _normalize_list(source.get("foreign_languages"))
        ],
        "foreign_languages_none": _normalize_bool(source.get("foreign_languages_none")),
        "awards": [normalize_award_entry(item) for item in _normalize_list(source.get("awards"))],
        "awards_none": _normalize_bool(source.get("awards_none")),
        "academic_degrees": academic_degrees,
        "academic_degrees_none": _normalize_bool(source.get("academic_degrees_none")),
        "academic_titles": academic_titles,
        "academic_titles_none": _normalize_bool(source.get("academic_titles_none")),
        **{
            key: template[key]
            for key in template
            if key
            not in {
                "foreign_languages",
                "foreign_languages_none",
                "awards",
                "awards_none",
                "academic_degrees",
                "academic_degrees_none",
                "academic_titles",
                "academic_titles_none",
            }
        },
    }


def additional_profile_has_content(profile: dict[str, Any]) -> bool:
    normalized = normalize_additional_profile(profile)
    if (
        normalized.get("foreign_languages_none")
        or normalized.get("awards_none")
        or normalized.get("academic_degrees_none")
        or normalized.get("academic_titles_none")
    ):
        return True
    return bool(
        normalized.get("foreign_languages")
        or normalized.get("awards")
        or normalized.get("academic_degrees")
        or normalized.get("academic_titles")
    )


def merge_additional_profiles(*profiles: dict[str, Any] | None) -> dict[str, Any]:
    result = empty_additional_profile()
    for profile in profiles:
        if not profile:
            continue
        normalized = normalize_additional_profile(profile)
        if not additional_profile_has_content(normalized):
            continue
        return deepcopy(normalized)
    return result
