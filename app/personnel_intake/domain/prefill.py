"""Build initial intake draft payload from personnel application registration data."""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.personnel_intake.domain.models import empty_intake_draft_payload


def split_russian_full_name(full_name: str) -> tuple[str, str, str]:
    parts = [part for part in str(full_name or "").split() if part]
    if not parts:
        return "", "", ""
    if len(parts) == 1:
        return parts[0], "", ""
    if len(parts) == 2:
        return parts[0], parts[1], ""
    return parts[0], parts[1], " ".join(parts[2:])


def resolve_person_name_parts(
    *,
    last_name: str,
    first_name: str,
    middle_name: str,
    full_name: str,
) -> tuple[str, str, str]:
    """Prefer structured name parts; split full_name only when all structured parts are empty."""
    last = str(last_name or "").strip()
    first = str(first_name or "").strip()
    middle = str(middle_name or "").strip()
    if last or first or middle:
        return last, first, middle
    return split_russian_full_name(str(full_name or "").strip())


def _format_birth_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    text_value = str(value).strip()
    if len(text_value) >= 10 and text_value[4] == "-":
        return text_value[:10]
    return text_value


def build_initial_intake_draft_payload(conn: Connection, application_id: int) -> dict[str, Any]:
    """Prefill a new intake draft from the linked person and application contacts."""
    payload = empty_intake_draft_payload()
    row = conn.execute(
        text(
            """
            SELECT
                pa.contact_mobile_phone,
                pa.contact_email,
                p.full_name,
                p.last_name,
                p.first_name,
                p.middle_name,
                p.birth_date
            FROM public.personnel_applications pa
            JOIN public.persons p ON p.person_id = pa.person_id
            WHERE pa.application_id = :application_id
            LIMIT 1
            """
        ),
        {"application_id": int(application_id)},
    ).mappings().first()
    if row is None:
        return payload

    last_name, first_name, middle_name = resolve_person_name_parts(
        last_name=str(row.get("last_name") or ""),
        first_name=str(row.get("first_name") or ""),
        middle_name=str(row.get("middle_name") or ""),
        full_name=str(row.get("full_name") or ""),
    )

    payload["personal"]["last_name"] = last_name
    payload["personal"]["first_name"] = first_name
    payload["personal"]["middle_name"] = middle_name
    payload["personal"]["birth_date"] = _format_birth_date(row.get("birth_date"))
    payload["contacts"]["mobile_phone"] = str(row.get("contact_mobile_phone") or "").strip()
    payload["contacts"]["email"] = str(row.get("contact_email") or "").strip()
    return payload
