"""Read canonical additional profile for PPR composite query."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.personnel_intake.domain.additional_profile import (
    empty_additional_profile,
    merge_additional_profiles,
    normalize_additional_profile,
)


def _json_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _load_metadata_additional_profile(conn: Connection, person_id: int) -> dict[str, Any] | None:
    row = (
        conn.execute(
            text(
                """
                SELECT additional_profile
                FROM public.personnel_record_metadata
                WHERE person_id = :person_id
                """
            ),
            {"person_id": int(person_id)},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    profile = _json_dict(row.get("additional_profile"))
    if not profile:
        return None
    normalized = normalize_additional_profile(profile)
    return normalized


def _load_intake_additional_profile(conn: Connection, person_id: int) -> dict[str, Any] | None:
    row = (
        conn.execute(
            text(
                """
                SELECT d.payload->'additional' AS additional
                FROM public.personnel_intake_drafts d
                JOIN public.personnel_applications a ON a.application_id = d.application_id
                WHERE a.person_id = :person_id
                ORDER BY d.updated_at DESC
                LIMIT 1
                """
            ),
            {"person_id": int(person_id)},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    profile = _json_dict(row.get("additional"))
    if not profile:
        return None
    return normalize_additional_profile(profile)


def _load_import_additional_profile(conn: Connection, employee_id: int) -> dict[str, Any] | None:
    try:
        from app.services.hr_import_employee_card_service import get_employee_import_card
    except ImportError:
        return None

    try:
        card = get_employee_import_card(conn, int(employee_id))
    except Exception:
        return None

    profile = card.get("profile") if isinstance(card, dict) else None
    if not isinstance(profile, dict):
        return None

    awards = []
    for item in profile.get("award_records") or []:
        if not isinstance(item, dict):
            continue
        awards.append(
            {
                "title": str(item.get("title") or "").strip(),
                "issued_by": "",
                "awarded_at": str(item.get("date") or "").strip(),
                "document_number": "",
            }
        )

    degrees_block = profile.get("degrees") if isinstance(profile.get("degrees"), dict) else {}
    degree_records = degrees_block.get("records") if isinstance(degrees_block, dict) else []
    academic_degrees = []
    for item in degree_records or []:
        if not isinstance(item, dict):
            continue
        academic_degrees.append(
            {
                "label": str(item.get("label") or "").strip(),
                "degree_type": str(item.get("degree_type") or "").strip(),
                "completed_at": str(item.get("completed_at") or "").strip(),
                "document_number": str(item.get("document_number") or "").strip(),
            }
        )

    if not awards and not academic_degrees:
        return None

    return normalize_additional_profile(
        {
            "foreign_languages": [],
            "foreign_languages_none": False,
            "awards": awards,
            "awards_none": False,
            "academic_degrees": academic_degrees,
            "academic_degrees_none": False,
        }
    )


def load_person_additional_profile(
    conn: Connection,
    *,
    person_id: int,
    employee_id: int | None = None,
) -> dict[str, Any]:
    metadata_profile = _load_metadata_additional_profile(conn, person_id)
    intake_profile = _load_intake_additional_profile(conn, person_id)
    import_profile = _load_import_additional_profile(conn, employee_id) if employee_id else None
    merged = merge_additional_profiles(metadata_profile, intake_profile, import_profile)
    return merged or empty_additional_profile()


def save_person_additional_profile(conn: Connection, *, person_id: int, profile: dict[str, Any]) -> None:
    normalized = normalize_additional_profile(profile)
    conn.execute(
        text(
            """
            INSERT INTO public.personnel_record_metadata (person_id, additional_profile)
            VALUES (:person_id, CAST(:additional_profile AS jsonb))
            ON CONFLICT (person_id) DO UPDATE
            SET additional_profile = EXCLUDED.additional_profile,
                updated_at = now()
            """
        ),
        {
            "person_id": int(person_id),
            "additional_profile": json.dumps(normalized, ensure_ascii=False),
        },
    )
