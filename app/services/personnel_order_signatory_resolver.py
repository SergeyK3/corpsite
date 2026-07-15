"""Resolve default personnel-order signatory from current organization director.

Priority:
1. Platform Role code ``DIRECTOR`` (users → roles → employees → positions).
2. Temporary fallback: active employee on position whose name matches ``Директор``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.security.platform_role_classification import LEADERSHIP_PLATFORM_ROLE_CODES

DIRECTOR_PLATFORM_ROLE_CODE = "DIRECTOR"
DIRECTOR_POSITION_NAME_FALLBACK = "директор"

_SURNAME_LIKE_RE = re.compile(
    r"(?:"
    r"ов|ова|ев|ева|ин|ина|"
    r"утаев|утаева|бек|қызы|ұлы|"
    r"ский|ская|енко|аза"
    r")$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PersonnelOrderSignatoryResolution:
    employee_id: Optional[int] = None
    signed_by_name: Optional[str] = None
    signed_by_position: Optional[str] = None
    warning: Optional[str] = None
    source: Optional[str] = None

    @property
    def resolved(self) -> bool:
        return self.employee_id is not None and bool(
            (self.signed_by_name or "").strip() or (self.signed_by_position or "").strip()
        )


def _normalize_text(value: Any) -> Optional[str]:
    normalized = " ".join(str(value or "").split()).strip()
    return normalized or None


def _title_token(token: str) -> str:
    if not token:
        return ""
    return "-".join(
        f"{piece[:1].upper()}{piece[1:]}" if piece else ""
        for piece in token.split("-")
    )


def _looks_like_surname(token: str) -> bool:
    normalized = str(token or "").strip()
    if not normalized:
        return False
    return bool(_SURNAME_LIKE_RE.search(normalized))


def _split_surname_and_given(parts: List[str]) -> tuple[str, str]:
    if len(parts) == 1:
        return parts[0], ""

    if len(parts) == 2:
        first, second = parts[0], parts[1]
        if _looks_like_surname(first) and not _looks_like_surname(second):
            return first, second
        if _looks_like_surname(second) and not _looks_like_surname(first):
            return second, first
        return first, second

    return parts[0], parts[1]


def format_signatory_fio_short(full_name: str) -> str:
    """Format employee full name as ``И. Фамилия`` (surname-first HR convention)."""
    parts = [part for part in str(full_name or "").strip().split() if part]
    if not parts:
        return ""

    surname, given_name = _split_surname_and_given(parts)
    if not given_name:
        return _title_token(surname)

    initial = given_name[0].upper()
    return f"{initial}. {_title_token(surname)}"


def _map_candidate_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for row in rows:
        employee_id = row.get("employee_id")
        if employee_id is None:
            continue
        full_name = _normalize_text(row.get("full_name"))
        position_name = _normalize_text(row.get("position_name"))
        if not full_name and not position_name:
            continue
        candidates.append(
            {
                "employee_id": int(employee_id),
                "full_name": full_name or "",
                "position_name": position_name or "",
            }
        )
    return candidates


def _finalize_resolution(
    candidates: List[Dict[str, Any]],
    *,
    source: str,
    ambiguous_warning: str,
    empty_warning: str,
) -> PersonnelOrderSignatoryResolution:
    if not candidates:
        return PersonnelOrderSignatoryResolution(warning=empty_warning, source=source)
    if len(candidates) > 1:
        return PersonnelOrderSignatoryResolution(
            warning=ambiguous_warning,
            source=source,
        )

    candidate = candidates[0]
    return PersonnelOrderSignatoryResolution(
        employee_id=int(candidate["employee_id"]),
        signed_by_name=format_signatory_fio_short(str(candidate.get("full_name") or "")),
        signed_by_position=_normalize_text(candidate.get("position_name")),
        source=source,
    )


def _table_has_column(conn: Connection, table: str, column: str) -> bool:
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


def _resolve_by_platform_role(conn: Connection) -> PersonnelOrderSignatoryResolution:
    if not _table_has_column(conn, "users", "employee_id"):
        return PersonnelOrderSignatoryResolution(source="platform_role")

    if DIRECTOR_PLATFORM_ROLE_CODE not in LEADERSHIP_PLATFORM_ROLE_CODES:
        return PersonnelOrderSignatoryResolution(source="platform_role")

    rows = conn.execute(
        text(
            """
            SELECT
                e.employee_id,
                e.full_name,
                COALESCE(NULLIF(BTRIM(p.name), ''), NULLIF(BTRIM(r.name), '')) AS position_name
            FROM public.users u
            JOIN public.roles r
              ON r.role_id = u.role_id
            JOIN public.employees e
              ON e.employee_id = u.employee_id
            LEFT JOIN public.positions p
              ON p.position_id = e.position_id
            WHERE UPPER(BTRIM(r.code)) = :role_code
              AND COALESCE(u.is_active, TRUE) = TRUE
              AND COALESCE(e.is_active, TRUE) = TRUE
            ORDER BY e.employee_id
            """
        ),
        {"role_code": DIRECTOR_PLATFORM_ROLE_CODE},
    ).mappings().all()

    candidates = _map_candidate_rows([dict(row) for row in rows])
    if len(candidates) > 1:
        return PersonnelOrderSignatoryResolution(
            warning="Найдено несколько действующих директоров. Укажите подписанта вручную.",
            source="platform_role",
        )
    if len(candidates) == 1:
        candidate = candidates[0]
        return PersonnelOrderSignatoryResolution(
            employee_id=int(candidate["employee_id"]),
            signed_by_name=format_signatory_fio_short(str(candidate.get("full_name") or "")),
            signed_by_position=_normalize_text(candidate.get("position_name")),
            source="platform_role",
        )
    return PersonnelOrderSignatoryResolution(source="platform_role")


def _resolve_by_director_position_name(conn: Connection) -> PersonnelOrderSignatoryResolution:
    rows = conn.execute(
        text(
            """
            SELECT
                e.employee_id,
                e.full_name,
                p.name AS position_name
            FROM public.employees e
            JOIN public.positions p
              ON p.position_id = e.position_id
            WHERE COALESCE(e.is_active, TRUE) = TRUE
              AND LOWER(BTRIM(p.name)) = :position_name
            ORDER BY e.employee_id
            """
        ),
        {"position_name": DIRECTOR_POSITION_NAME_FALLBACK},
    ).mappings().all()

    return _finalize_resolution(
        _map_candidate_rows([dict(row) for row in rows]),
        source="position_name_fallback",
        ambiguous_warning=(
            "Найдено несколько сотрудников на должности «Директор». "
            "Укажите подписанта вручную."
        ),
        empty_warning=(
            "Действующий директор не найден. Заполните должность и ФИО подписанта вручную."
        ),
    )


def resolve_default_personnel_order_signatory(
    conn: Connection,
) -> PersonnelOrderSignatoryResolution:
    """Resolve a single default signatory candidate for a new personnel order."""
    platform_resolution = _resolve_by_platform_role(conn)
    if platform_resolution.resolved or platform_resolution.warning:
        return platform_resolution
    return _resolve_by_director_position_name(conn)


def signatory_fields_provided(
    *,
    signed_by_employee_id: Optional[int] = None,
    signed_by_name: Optional[str] = None,
    signed_by_position: Optional[str] = None,
) -> bool:
    if signed_by_employee_id is not None:
        return True
    if _normalize_text(signed_by_name):
        return True
    if _normalize_text(signed_by_position):
        return True
    return False


def signatory_fields_all_empty(
    *,
    signed_by_employee_id: Optional[int] = None,
    signed_by_name: Optional[str] = None,
    signed_by_position: Optional[str] = None,
) -> bool:
    return not signatory_fields_provided(
        signed_by_employee_id=signed_by_employee_id,
        signed_by_name=signed_by_name,
        signed_by_position=signed_by_position,
    )


def apply_default_signatory_if_needed(
    *,
    signed_by_employee_id: Optional[int] = None,
    signed_by_name: Optional[str] = None,
    signed_by_position: Optional[str] = None,
    conn: Connection,
) -> tuple[Optional[int], Optional[str], Optional[str], Optional[str]]:
    """Return signatory fields, auto-filling only when all inputs are empty."""
    if signatory_fields_provided(
        signed_by_employee_id=signed_by_employee_id,
        signed_by_name=signed_by_name,
        signed_by_position=signed_by_position,
    ):
        return signed_by_employee_id, signed_by_name, signed_by_position, None

    resolution = resolve_default_personnel_order_signatory(conn)
    if not resolution.resolved:
        return signed_by_employee_id, signed_by_name, signed_by_position, resolution.warning

    return (
        resolution.employee_id,
        resolution.signed_by_name,
        resolution.signed_by_position,
        None,
    )
