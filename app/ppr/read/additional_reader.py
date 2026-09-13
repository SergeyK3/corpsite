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


def load_person_status_facts(conn: Connection, *, person_id: int) -> list[dict[str, Any]]:
    """Current PPR status facts, with the original note available only to the card."""
    exists = conn.execute(text("SELECT to_regclass('public.person_status_facts') IS NOT NULL")).scalar_one()
    if not exists:
        return []
    rows = conn.execute(
        text(
            """
            SELECT f.status_fact_id, f.fact_kind, f.effective_date, f.disability_group,
                   f.icd10_code, f.pension_kind, f.review_status, f.review_reason,
                   f.version, f.created_at, r.normalized_payload->>'note_raw' AS source_note_hint
            FROM public.person_status_facts f
            LEFT JOIN public.hr_import_rows r ON r.row_id=f.source_row_id
            WHERE f.person_id=:person_id
              AND NOT f.is_deleted
              AND NOT EXISTS (
                SELECT 1 FROM public.person_status_facts newer
                WHERE newer.supersedes_fact_id=f.status_fact_id
              )
            ORDER BY f.fact_kind, f.version DESC, f.status_fact_id DESC
            """
        ),
        {"person_id": int(person_id)},
    ).mappings().all()
    return [dict(row) for row in rows]


def load_person_status_note_hint(conn: Connection, *, person_id: int, employee_id: int | None = None) -> str | None:
    """Original imported note for the permitted PPR-card hint, never for audit/reporting."""
    exists = conn.execute(text("SELECT to_regclass('public.person_status_facts') IS NOT NULL")).scalar_one()
    if not exists:
        return None
    historical = conn.execute(
        text(
            """
            SELECT r.normalized_payload->>'note_raw'
            FROM public.person_status_facts f
            JOIN public.hr_import_rows r ON r.row_id=f.source_row_id
            WHERE f.person_id=:person_id
              AND COALESCE(r.normalized_payload->>'note_raw', '') <> ''
            ORDER BY f.created_at DESC, f.status_fact_id DESC
            LIMIT 1
            """
        ),
        {"person_id": int(person_id)},
    ).scalar_one_or_none()
    if historical:
        return str(historical)
    if employee_id is None:
        # A PPR card opened by person_id has no employee context in the
        # identity resolver.  Use only an unambiguous canonical relation —
        # never a name-based import match — to retain the import-card path.
        employee_ids = conn.execute(
            text(
                """
                SELECT employee_id FROM public.employees
                WHERE person_id=:person_id AND COALESCE(is_active, true) IS TRUE
                ORDER BY employee_id
                LIMIT 2
                """
            ),
            {"person_id": int(person_id)},
        ).scalars().all()
        if len(employee_ids) != 1:
            return None
        employee_id = int(employee_ids[0])
    # The card uses the same deterministic selection as import-card.  The raw
    # note is returned only through this permitted PPR-card read path.
    from app.services.hr_import_additional_status_service import FACT_PENSION, parse_control_list_note
    from app.services.hr_import_employee_card_service import EmployeeImportCardNotFoundError, get_employee_import_card

    try:
        card = get_employee_import_card(conn, int(employee_id))
    except EmployeeImportCardNotFoundError:
        return None
    note = conn.execute(
        text("SELECT normalized_payload->>'note_raw' FROM public.hr_import_rows WHERE row_id=:row_id"),
        {"row_id": int(card["row_id"])},
    ).scalar_one_or_none()
    parsed = parse_control_list_note(note)
    return str(note) if any(item.fact_kind == FACT_PENSION for item in parsed.facts) else None


def load_person_additional_profile(
    conn: Connection,
    *,
    person_id: int,
    employee_id: int | None = None,
) -> dict[str, Any]:
    metadata_profile = _load_metadata_additional_profile(conn, person_id)
    intake_profile = _load_intake_additional_profile(conn, person_id)
    import_profile = _load_import_additional_profile(conn, employee_id) if employee_id else None
    merged = merge_additional_profiles(metadata_profile, intake_profile, import_profile) or empty_additional_profile()
    version = conn.execute(text("SELECT updated_at FROM public.personnel_record_metadata WHERE person_id=:person_id"), {"person_id": int(person_id)}).scalar_one_or_none()
    merged["qualification_categories_version"] = str(version or "")
    return merged


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
