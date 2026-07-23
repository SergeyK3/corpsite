"""Map intake draft payload fields to PPR section command payloads."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from app.db.models.personnel_migration import (
    EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
    MILITARY_RECORD_KIND_NOT_APPLICABLE,
    MILITARY_RECORD_KIND_REGISTRATION,
    RELATIONSHIP_TYPE_OTHER_CLOSE,
    TRAINING_KIND_COURSE,
)
from app.personnel_intake.domain.education_type import resolve_intake_education_kind

_RELATIONSHIP_MAP = {
    "отец": "father",
    "father": "father",
    "мать": "mother",
    "mother": "mother",
    "брат": "brother",
    "brother": "brother",
    "сестра": "sister",
    "sister": "sister",
    "сын": "son",
    "son": "son",
    "дочь": "daughter",
    "daughter": "daughter",
    "супруг": "spouse",
    "супруга": "spouse",
    "spouse": "spouse",
    "муж": "spouse",
    "жена": "spouse",
}


def build_full_name(personal: dict[str, Any]) -> str:
    parts = [
        str(personal.get("last_name") or "").strip(),
        str(personal.get("first_name") or "").strip(),
        str(personal.get("middle_name") or "").strip(),
    ]
    return " ".join(p for p in parts if p)


def parse_date_value(raw: Any) -> date | None:
    text = str(raw or "").strip()
    if not text:
        return None
    if len(text) >= 10 and text[4] == "-":
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None
    return None


def map_relationship_type(raw: Any) -> str:
    key = str(raw or "").strip().lower()
    return _RELATIONSHIP_MAP.get(key, RELATIONSHIP_TYPE_OTHER_CLOSE)


def intake_command_id(application_id: int, section: str, index: int | str = 0) -> str:
    return f"intake-transfer:{application_id}:{section}:{index}"


def map_education_records(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    for item in items:
        document_type = str(item.get("document_type") or "diploma").strip() or "diploma"
        mapped.append(
            {
                "education_kind": resolve_intake_education_kind(item.get("education_type")),
                "institution_name": str(item.get("institution") or "").strip() or None,
                "specialty": str(item.get("specialty") or "").strip() or None,
                "qualification": str(item.get("qualification") or "").strip() or None,
                "started_at": parse_date_value(item.get("year_from")),
                "completed_at": parse_date_value(item.get("year_to")),
                "diploma_number": str(item.get("diploma_number") or "").strip() or None,
                "metadata": {
                    "source": "personnel_intake",
                    "document_type": document_type,
                },
            }
        )
    return mapped


def map_training_records(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    for item in items:
        hours_raw = item.get("hours")
        hours: Decimal | None
        if hours_raw is None or str(hours_raw).strip() == "":
            hours = None
        else:
            hours = Decimal(str(hours_raw))
        year_to = item.get("year_to") or item.get("year")
        document_type = str(item.get("document_type") or "certificate").strip() or "certificate"
        mapped.append(
            {
                "training_kind": TRAINING_KIND_COURSE,
                "title": str(item.get("course_name") or "").strip() or None,
                "organization_name": str(item.get("institution") or "").strip() or None,
                "hours": hours,
                "started_at": parse_date_value(item.get("year_from")),
                "completed_at": parse_date_value(year_to),
                "certificate_number": str(item.get("document_number") or "").strip() or None,
                "metadata": {
                    "source": "personnel_intake",
                    "document_type": document_type,
                    "hours_is_manual": bool(item.get("hours_is_manual")),
                },
            }
        )
    return mapped


def map_relative_records(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    for item in items:
        mapped.append(
            {
                "relationship_type": map_relationship_type(item.get("relationship")),
                "full_name": str(item.get("full_name") or "").strip(),
                "birth_date": parse_date_value(item.get("birth_year")),
                "organization_name": str(item.get("work_place") or "").strip() or None,
                "metadata": {"source": "personnel_intake"},
            }
        )
    return mapped


def map_employment_records(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    for item in items:
        mapped.append(
            {
                "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
                "employer_name": str(item.get("organization") or "").strip() or None,
                "position_title": str(item.get("position") or "").strip() or None,
                "started_at": parse_date_value(item.get("year_from")),
                "ended_at": parse_date_value(item.get("year_to")),
                "termination_reason": str(item.get("reason_for_leaving") or "").strip() or None,
                "metadata": {"source": "personnel_intake"},
            }
        )
    return mapped


def map_military_record(block: dict[str, Any]) -> dict[str, Any]:
    status = str(block.get("status") or "").strip().lower()
    record_kind = (
        MILITARY_RECORD_KIND_NOT_APPLICABLE
        if status in {"не состоит", "not_applicable", "n/a", "нет"}
        else MILITARY_RECORD_KIND_REGISTRATION
    )
    return {
        "record_kind": record_kind,
        "registration_status": str(block.get("status") or "").strip() or None,
        "military_rank": str(block.get("rank") or "").strip() or None,
        "registration_category": str(block.get("category") or block.get("registration_category") or "").strip()
        or None,
        "personnel_composition": str(block.get("composition") or "").strip() or None,
        "military_specialty_code": str(block.get("specialty_code") or "").strip() or None,
        "fitness_category": str(block.get("fitness_category") or "").strip() or None,
        "commissariat_name": str(block.get("commissariat") or "").strip() or None,
        "metadata": {
            "source": "personnel_intake",
            "registration_group": str(block.get("registration_group") or "").strip() or None,
            "specialty_name": str(block.get("specialty_name") or "").strip() or None,
        },
    }


def map_foreign_language_records(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    for item in items:
        mapped.append(
            {
                "language": str(item.get("language") or "").strip() or None,
                "proficiency": str(item.get("proficiency") or "").strip() or None,
                "metadata": {"source": "personnel_intake"},
            }
        )
    return mapped


def map_award_records(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    for item in items:
        mapped.append(
            {
                "category": str(item.get("category") or "").strip() or None,
                "name": str(item.get("name") or "").strip() or None,
                "issued_by": str(item.get("issued_by") or "").strip() or None,
                "awarded_at": parse_date_value(item.get("awarded_at") or item.get("date")),
                "document_number": str(item.get("document_number") or "").strip() or None,
                "metadata": {"source": "personnel_intake"},
            }
        )
    return mapped


def map_academic_degree_records(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    for item in items:
        mapped.append(
            {
                "degree": str(item.get("degree") or "").strip() or None,
                "degree_other": str(item.get("degree_other") or "").strip() or None,
                "field_of_science": str(item.get("field_of_science") or item.get("degree_type") or "").strip()
                or None,
                "completed_at": parse_date_value(item.get("completed_at")),
                "document_number": str(item.get("document_number") or "").strip() or None,
                "label": str(item.get("label") or "").strip() or None,
                "degree_type": str(item.get("degree_type") or "").strip() or None,
                "metadata": {"source": "personnel_intake"},
            }
        )
    return mapped


def map_academic_title_records(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    for item in items:
        mapped.append(
            {
                "academic_title": str(item.get("academic_title") or "").strip() or None,
                "academic_title_other": str(item.get("academic_title_other") or "").strip() or None,
                "field_of_science": str(item.get("field_of_science") or item.get("degree_type") or "").strip()
                or None,
                "completed_at": parse_date_value(item.get("completed_at")),
                "document_number": str(item.get("document_number") or "").strip() or None,
                "label": str(item.get("label") or "").strip() or None,
                "degree_type": str(item.get("degree_type") or "").strip() or None,
                "metadata": {"source": "personnel_intake"},
            }
        )
    return mapped
