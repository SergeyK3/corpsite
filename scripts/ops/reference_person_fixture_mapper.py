"""Map tests/fixtures/ppr_reference_person.json to Personnel Intake draft payload."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from app.personnel_intake.domain.models import empty_intake_draft_payload

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "ppr_reference_person.json"

FIXTURE_PERSON_KEY = "telegram_ref_person_001"
REFERENCE_IIN = "880315350789"
IDEMPOTENCY_KEY = f"fixture:{FIXTURE_PERSON_KEY}"

_INTAKE_SUPPORTED_FIXTURE_SECTIONS = frozenset(
    {
        "PPR-GENERAL",
        "PPR-CONTACTS",
        "PPR-EDUCATION",
        "PPR-TRAINING",
        "PPR-FAMILY",
        "PPR-EMPLOYMENT-BIOGRAPHY",
        "PPR-MILITARY",
    }
)

_SEX_TO_GENDER = {
    "male": "Мужской",
    "female": "Женский",
    "m": "Мужской",
    "f": "Женский",
}

_RELATIONSHIP_LABELS = {
    "spouse": "супруга",
    "father": "отец",
    "mother": "мать",
    "son": "сын",
    "daughter": "дочь",
    "brother": "брат",
    "sister": "сестра",
}


def load_reference_fixture(path: Path | None = None) -> dict[str, Any]:
    fixture_path = path or DEFAULT_FIXTURE_PATH
    with fixture_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def fixture_field_value(section: dict[str, Any], field_name: str) -> Any:
    fields = section.get("fields") or {}
    entry = fields.get(field_name) or {}
    return entry.get("value")


def fixture_record_field(record: dict[str, Any], field_name: str) -> Any:
    fields = record.get("fields") or {}
    entry = fields.get(field_name) or {}
    return entry.get("value")


def split_russian_full_name(full_name: str) -> tuple[str, str, str]:
    parts = [part for part in str(full_name or "").split() if part]
    if not parts:
        return "", "", ""
    if len(parts) == 1:
        return parts[0], "", ""
    if len(parts) == 2:
        return parts[0], parts[1], ""
    return parts[0], parts[1], " ".join(parts[2:])


def _year_from_date(raw: Any) -> str:
    text = str(raw or "").strip()
    if len(text) >= 4 and text[4] == "-":
        return text[:4]
    if text.isdigit() and len(text) == 4:
        return text
    return ""


def _find_contact_record(sections: dict[str, Any], record_key: str) -> dict[str, Any] | None:
    contacts = sections.get("PPR-CONTACTS") or {}
    for record in contacts.get("records") or []:
        if record.get("record_key") == record_key:
            return record
    return None


def _find_address(sections: dict[str, Any], address_kind: str) -> str:
    addresses = sections.get("PPR-ADDRESSES") or {}
    for record in addresses.get("records") or []:
        if record.get("address_kind") == address_kind:
            value = fixture_record_field(record, "structured_address")
            if value:
                return str(value)
    return ""


def fixture_skipped_sections(fixture: dict[str, Any]) -> list[str]:
    sections = fixture.get("sections") or {}
    skipped = [
        code
        for code in sections
        if code not in _INTAKE_SUPPORTED_FIXTURE_SECTIONS
    ]
    spec_gaps = fixture.get("spec_gaps") or {}
    for item in spec_gaps.get("sections_without_normative_field_schema") or []:
        label = str(item).split(" ", 1)[0]
        if label.startswith("PPR-") and label not in skipped:
            skipped.append(label)
    return sorted(set(skipped))


def fixture_to_intake_draft(fixture: dict[str, Any]) -> dict[str, Any]:
    sections = fixture.get("sections") or {}
    general = sections.get("PPR-GENERAL") or {}
    full_name = str(fixture_field_value(general, "full_name") or "").strip()
    last_name, first_name, middle_name = split_russian_full_name(full_name)
    sex_raw = str(fixture_field_value(general, "sex") or "").strip().lower()

    payload = empty_intake_draft_payload()
    payload["personal"] = {
        "last_name": last_name,
        "first_name": first_name,
        "middle_name": middle_name,
        "birth_date": str(fixture_field_value(general, "birth_date") or ""),
        "birth_place": str(fixture_field_value(general, "birth_place") or ""),
        "gender": _SEX_TO_GENDER.get(sex_raw, str(fixture_field_value(general, "sex") or "")),
        "citizenship": str(fixture_field_value(general, "citizenship") or ""),
        "nationality": str(fixture_field_value(general, "nationality") or ""),
    }

    phone_record = _find_contact_record(sections, "contacts.mobile_primary")
    email_record = _find_contact_record(sections, "contacts.email_personal")
    payload["contacts"] = {
        "mobile_phone": str(fixture_record_field(phone_record or {}, "phone_raw") or ""),
        "email": str(fixture_record_field(email_record or {}, "email") or ""),
        "registration_address": _find_address(sections, "registration"),
        "residence_address": _find_address(sections, "residence"),
    }

    education_items: list[dict[str, str]] = []
    for record in (sections.get("PPR-EDUCATION") or {}).get("records") or []:
        institution = str(fixture_record_field(record, "institution_name") or "").strip()
        education_type = str(fixture_record_field(record, "education_kind") or "basic").strip().lower()
        education_items.append(
            {
                "education_type": education_type,
                "institution": institution,
                "year_from": _year_from_date(fixture_record_field(record, "started_at")),
                "year_to": _year_from_date(fixture_record_field(record, "completed_at")),
                "specialty": str(fixture_record_field(record, "specialty") or ""),
                "qualification": str(fixture_record_field(record, "qualification") or ""),
                "diploma_number": str(fixture_record_field(record, "diploma_number") or ""),
            }
        )
    payload["education"] = education_items

    training_items: list[dict[str, str]] = []
    for record in (sections.get("PPR-TRAINING") or {}).get("records") or []:
        training_items.append(
            {
                "course_name": str(fixture_record_field(record, "title") or ""),
                "institution": str(fixture_record_field(record, "organization_name") or ""),
                "year": _year_from_date(fixture_record_field(record, "completed_at")),
                "hours": str(fixture_record_field(record, "hours") or ""),
            }
        )
    payload["training"] = training_items

    relatives_items: list[dict[str, str]] = []
    for record in (sections.get("PPR-FAMILY") or {}).get("records") or []:
        relationship = str(fixture_record_field(record, "relationship_type") or "")
        relatives_items.append(
            {
                "relationship": _RELATIONSHIP_LABELS.get(relationship, relationship),
                "full_name": str(fixture_record_field(record, "full_name") or ""),
                "birth_year": _year_from_date(fixture_record_field(record, "birth_date")),
                "work_place": str(fixture_record_field(record, "organization_name") or ""),
            }
        )
    payload["relatives"] = relatives_items

    employment_items: list[dict[str, str]] = []
    for record in (sections.get("PPR-EMPLOYMENT-BIOGRAPHY") or {}).get("records") or []:
        employment_items.append(
            {
                "organization": str(fixture_record_field(record, "employer_name") or ""),
                "position": str(fixture_record_field(record, "position_title") or ""),
                "year_from": _year_from_date(fixture_record_field(record, "started_at")),
                "year_to": _year_from_date(fixture_record_field(record, "ended_at")),
                "reason_for_leaving": str(fixture_record_field(record, "termination_reason") or ""),
            }
        )
    payload["employment_biography"] = employment_items

    military_section = sections.get("PPR-MILITARY") or {}
    military_record = military_section.get("active_record") or {}
    payload["military"] = {
        "status": str(fixture_record_field(military_record, "registration_status") or ""),
        "rank": str(fixture_record_field(military_record, "military_rank") or ""),
        "category": str(fixture_record_field(military_record, "registration_category") or ""),
        "composition": str(fixture_record_field(military_record, "personnel_composition") or ""),
        "specialty_code": str(fixture_record_field(military_record, "military_specialty_code") or ""),
        "fitness_category": str(fixture_record_field(military_record, "fitness_category") or ""),
        "commissariat": str(fixture_record_field(military_record, "commissariat_name") or ""),
        "registration_group": "",
        "registration_category": str(fixture_record_field(military_record, "registration_category") or ""),
    }
    payload["current_step"] = "personal"
    return payload


def fixture_identity(fixture: dict[str, Any]) -> dict[str, str]:
    envelope = fixture.get("AGGREGATE-ENVELOPE") or {}
    general = (fixture.get("sections") or {}).get("PPR-GENERAL") or {}
    fixture_key = str(fixture_field_value(envelope, "fixture_person_key") or FIXTURE_PERSON_KEY)
    full_name = str(fixture_field_value(general, "full_name") or "").strip()
    iin = str(fixture_field_value(general, "iin") or REFERENCE_IIN)
    birth_raw = fixture_field_value(general, "birth_date")
    birth_date: date | None
    if birth_raw:
        birth_date = date.fromisoformat(str(birth_raw)[:10])
    else:
        birth_date = None
    return {
        "fixture_person_key": fixture_key,
        "full_name": full_name,
        "iin": iin,
        "birth_date": birth_date.isoformat() if birth_date else "",
        "idempotency_key": IDEMPOTENCY_KEY,
    }
