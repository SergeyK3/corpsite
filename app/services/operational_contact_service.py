"""Ensure operational ``public.contacts`` row for enrolled employee/user pairs (OPS-026.4)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

_TELEGRAM_DIGITS = re.compile(r"\D+")


@dataclass(frozen=True)
class EnsureOperationalContactResult:
    contact_id: Optional[int]
    created: bool
    existed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "contact_id": self.contact_id,
            "created": self.created,
            "existed": self.existed,
        }


def _table_exists(conn: Connection, table: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :table
            LIMIT 1
            """
        ),
        {"table": table},
    ).first()
    return row is not None


def _column_exists(conn: Connection, table: str, column: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table
              AND column_name = :column
            LIMIT 1
            """
        ),
        {"table": table, "column": column},
    ).first()
    return row is not None


def normalize_contact_full_name(value: Optional[str]) -> str:
    return (
        " ".join(str(value or "").split())
        .casefold()
        .replace("ё", "е")
    )


def parse_telegram_numeric_id(value: Any) -> Optional[int]:
    digits = _TELEGRAM_DIGITS.sub("", str(value or ""))
    if not digits:
        return None
    try:
        parsed = int(digits)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _load_employee_context(conn: Connection, employee_id: int) -> dict[str, Any]:
    person_col = ", e.person_id" if _column_exists(conn, "employees", "person_id") else ", NULL::bigint AS person_id"
    phone_col = ", e.phone" if _column_exists(conn, "employees", "phone") else ", NULL::text AS phone"
    row = conn.execute(
        text(
            f"""
            SELECT
                e.employee_id,
                e.full_name
                {person_col}
                {phone_col}
            FROM public.employees e
            WHERE e.employee_id = :employee_id
            LIMIT 1
            """
        ),
        {"employee_id": int(employee_id)},
    ).mappings().first()
    if row is None:
        raise ValueError(f"employee_id={employee_id} not found")
    return dict(row)


def _load_user_context(conn: Connection, employee_id: int) -> Optional[dict[str, Any]]:
    if not _table_exists(conn, "users"):
        return None
    phone_col = ", u.phone" if _column_exists(conn, "users", "phone") else ", NULL::text AS phone"
    row = conn.execute(
        text(
            f"""
            SELECT
                u.user_id,
                u.full_name,
                u.telegram_id,
                u.telegram_username
                {phone_col}
            FROM public.users u
            WHERE u.employee_id = :employee_id
            ORDER BY u.user_id
            LIMIT 1
            """
        ),
        {"employee_id": int(employee_id)},
    ).mappings().first()
    return dict(row) if row else None


def find_operational_contact_id(
    conn: Connection,
    *,
    person_id: Optional[int],
    telegram_numeric_id: Optional[int],
    full_name: str,
) -> Optional[int]:
    if not _table_exists(conn, "contacts"):
        return None

    if person_id is not None and int(person_id) > 0:
        row = conn.execute(
            text(
                """
                SELECT contact_id
                FROM public.contacts
                WHERE person_id = :person_id
                  AND COALESCE(is_deleted, false) = false
                ORDER BY contact_id
                LIMIT 1
                """
            ),
            {"person_id": int(person_id)},
        ).first()
        if row:
            return int(row[0])

    if telegram_numeric_id is not None and int(telegram_numeric_id) > 0:
        row = conn.execute(
            text(
                """
                SELECT contact_id
                FROM public.contacts
                WHERE telegram_numeric_id = :telegram_numeric_id
                  AND COALESCE(is_deleted, false) = false
                ORDER BY contact_id
                LIMIT 1
                """
            ),
            {"telegram_numeric_id": int(telegram_numeric_id)},
        ).first()
        if row:
            return int(row[0])

    normalized_name = normalize_contact_full_name(full_name)
    if not normalized_name:
        return None

    row = conn.execute(
        text(
            """
            SELECT contact_id
            FROM public.contacts
            WHERE COALESCE(is_deleted, false) = false
              AND lower(replace(trim(full_name), 'ё', 'е')) = :normalized_name
            ORDER BY contact_id
            LIMIT 1
            """
        ),
        {"normalized_name": normalized_name},
    ).first()
    return int(row[0]) if row else None


def _compose_contact_fields(
    *,
    employee: dict[str, Any],
    user: Optional[dict[str, Any]],
    full_name_override: Optional[str] = None,
) -> dict[str, Any]:
    full_name = " ".join(
        str(
            full_name_override
            or (user or {}).get("full_name")
            or employee.get("full_name")
            or ""
        ).split()
    )
    if not full_name:
        raise ValueError("full_name is required to create operational contact")

    phone = str((user or {}).get("phone") or employee.get("phone") or "").strip() or None
    telegram_username = str((user or {}).get("telegram_username") or "").strip() or None
    telegram_numeric_id = parse_telegram_numeric_id((user or {}).get("telegram_id"))

    person_id_raw = employee.get("person_id")
    person_id = int(person_id_raw) if person_id_raw not in (None, "") else None
    if person_id is not None and person_id <= 0:
        person_id = None

    return {
        "full_name": full_name,
        "phone": phone,
        "telegram_username": telegram_username,
        "telegram_numeric_id": telegram_numeric_id,
        "person_id": person_id,
    }


def ensure_operational_contact_for_employee(
    conn: Connection,
    *,
    employee_id: int,
    full_name: Optional[str] = None,
) -> EnsureOperationalContactResult:
    """Create or reuse operational contact for an enrolled employee (idempotent)."""
    if not _table_exists(conn, "contacts"):
        return EnsureOperationalContactResult(contact_id=None, created=False, existed=False)

    employee = _load_employee_context(conn, int(employee_id))
    user = _load_user_context(conn, int(employee_id))
    fields = _compose_contact_fields(employee=employee, user=user, full_name_override=full_name)

    existing_id = find_operational_contact_id(
        conn,
        person_id=fields["person_id"],
        telegram_numeric_id=fields["telegram_numeric_id"],
        full_name=fields["full_name"],
    )
    if existing_id is not None:
        conn.execute(
            text(
                """
                UPDATE public.contacts
                SET
                    phone = COALESCE(NULLIF(trim(phone), ''), :phone),
                    telegram_username = COALESCE(NULLIF(trim(telegram_username), ''), :telegram_username),
                    telegram_numeric_id = COALESCE(telegram_numeric_id, :telegram_numeric_id),
                    person_id = COALESCE(person_id, :person_id),
                    updated_at = NOW()
                WHERE contact_id = :contact_id
                """
            ),
            {
                "contact_id": int(existing_id),
                **fields,
            },
        )
        return EnsureOperationalContactResult(contact_id=existing_id, created=False, existed=True)

    inserted = conn.execute(
        text(
            """
            INSERT INTO public.contacts (
                person_id,
                full_name,
                phone,
                telegram_username,
                telegram_numeric_id
            )
            VALUES (
                :person_id,
                :full_name,
                :phone,
                :telegram_username,
                :telegram_numeric_id
            )
            RETURNING contact_id
            """
        ),
        fields,
    ).scalar_one()

    return EnsureOperationalContactResult(
        contact_id=int(inserted),
        created=True,
        existed=False,
    )
