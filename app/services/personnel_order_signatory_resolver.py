"""Resolve default personnel-order signatory from current organization director.

Resolution priority:
1. Platform Role ``DIRECTOR`` with ``users.employee_id`` FK (ADR-044 target state).
2. Temporary verified name bridge (ADR-044 gap): exactly one unlinked DIRECTOR user,
   exactly one verified active employee match, current director assignment.
3. HR fallback: active employee with current employment on canonical director position.

Name-only matching is never sufficient by itself; see ``_resolve_verified_name_bridge``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.security.platform_role_classification import LEADERSHIP_PLATFORM_ROLE_CODES

DIRECTOR_PLATFORM_ROLE_CODE = "DIRECTOR"
DIRECTOR_POSITION_NAME_FALLBACK = "директор"

SOURCE_PLATFORM_ROLE = "platform_role"
SOURCE_PLATFORM_ROLE_VERIFIED_NAME_BRIDGE = "platform_role_verified_name_bridge"
SOURCE_HR_DIRECTOR_ASSIGNMENT = "hr_director_assignment"

WARNING_AMBIGUOUS_DIRECTORS = (
    "Найдено несколько действующих директоров. Укажите подписанта вручную."
)
WARNING_AMBIGUOUS_EMPLOYEES = (
    "Найдено несколько сотрудников, подходящих под директора. "
    "Укажите подписанта вручную."
)
WARNING_NOT_FOUND = (
    "Действующий директор не найден. Заполните должность и ФИО подписанта вручную."
)
WARNING_NAME_BRIDGE_BLOCKED = (
    "Автоматическое определение подписанта недоступно "
    "(неоднозначная или непроверенная связь DIRECTOR). "
    "Заполните должность и ФИО подписанта вручную."
)

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
        return (
            self.employee_id is not None
            and bool((self.signed_by_name or "").strip())
            and bool((self.signed_by_position or "").strip())
            and not self.warning
        )


def _normalize_text(value: Any) -> Optional[str]:
    normalized = " ".join(str(value or "").split()).strip()
    return normalized or None


def _normalize_full_name(value: Any) -> Optional[str]:
    normalized = _normalize_text(value)
    return normalized.casefold() if normalized else None


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


def _table_exists(conn: Connection, table: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = :table
            LIMIT 1
            """
        ),
        {"table": table},
    ).first()
    return row is not None


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


def _director_position_predicate(position_alias: str = "p") -> str:
    """Canonical director position match: role name for DIRECTOR or legacy fallback token."""
    return f"""(
        LOWER(BTRIM({position_alias}.name)) = :director_fallback
        OR LOWER(BTRIM({position_alias}.name)) = LOWER(BTRIM(COALESCE(
            (
                SELECT r.name
                FROM public.roles r
                WHERE UPPER(BTRIM(r.code)) = :director_role_code
                ORDER BY r.role_id
                LIMIT 1
            ),
            :director_fallback
        )))
    )"""


def _employee_snapshot_current_predicate(employee_alias: str = "e") -> str:
    return f"""(
        COALESCE({employee_alias}.is_active, TRUE) = TRUE
        AND COALESCE({employee_alias}.date_from, CURRENT_DATE) <= CURRENT_DATE
        AND ({employee_alias}.date_to IS NULL OR {employee_alias}.date_to >= CURRENT_DATE)
    )"""


def _fetch_active_director_users(conn: Connection) -> List[Dict[str, Any]]:
    if not _table_has_column(conn, "users", "employee_id"):
        return []

    rows = conn.execute(
        text(
            """
            SELECT
                u.user_id,
                u.full_name,
                u.employee_id,
                COALESCE(NULLIF(BTRIM(r.name), ''), :director_fallback) AS role_name
            FROM public.users u
            JOIN public.roles r
              ON r.role_id = u.role_id
            WHERE UPPER(BTRIM(r.code)) = :director_role_code
              AND COALESCE(u.is_active, TRUE) = TRUE
            ORDER BY u.user_id
            """
        ),
        {
            "director_role_code": DIRECTOR_PLATFORM_ROLE_CODE,
            "director_fallback": DIRECTOR_POSITION_NAME_FALLBACK,
        },
    ).mappings().all()
    return [dict(row) for row in rows]


def _map_employee_candidate(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    employee_id = row.get("employee_id")
    if employee_id is None:
        return None
    full_name = _normalize_text(row.get("full_name"))
    position_name = _normalize_text(row.get("position_name"))
    if not full_name and not position_name:
        return None
    return {
        "employee_id": int(employee_id),
        "full_name": full_name or "",
        "position_name": position_name or "",
    }


def _candidate_from_resolution(
    candidate: Dict[str, Any],
    *,
    source: str,
) -> PersonnelOrderSignatoryResolution:
    return PersonnelOrderSignatoryResolution(
        employee_id=int(candidate["employee_id"]),
        signed_by_name=format_signatory_fio_short(str(candidate.get("full_name") or "")),
        signed_by_position=_normalize_text(candidate.get("position_name")),
        source=source,
    )


def _finalize_unique_candidates(
    candidates: Sequence[Dict[str, Any]],
    *,
    source: str,
    ambiguous_warning: str,
    empty_warning: str,
) -> PersonnelOrderSignatoryResolution:
    unique: Dict[int, Dict[str, Any]] = {}
    for candidate in candidates:
        unique[int(candidate["employee_id"])] = candidate
    deduped = list(unique.values())
    if not deduped:
        return PersonnelOrderSignatoryResolution(warning=empty_warning, source=source)
    if len(deduped) > 1:
        return PersonnelOrderSignatoryResolution(warning=ambiguous_warning, source=source)
    return _candidate_from_resolution(deduped[0], source=source)


def _fetch_linked_platform_role_candidates(conn: Connection) -> List[Dict[str, Any]]:
    rows = conn.execute(
        text(
            f"""
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
            WHERE UPPER(BTRIM(r.code)) = :director_role_code
              AND u.employee_id IS NOT NULL
              AND COALESCE(u.is_active, TRUE) = TRUE
              AND {_employee_snapshot_current_predicate("e")}
            ORDER BY e.employee_id
            """
        ),
        {
            "director_role_code": DIRECTOR_PLATFORM_ROLE_CODE,
        },
    ).mappings().all()
    mapped = [_map_employee_candidate(dict(row)) for row in rows]
    return [item for item in mapped if item is not None]


def _employee_has_current_director_assignment(conn: Connection, employee_id: int) -> bool:
    params = {
        "employee_id": int(employee_id),
        "director_role_code": DIRECTOR_PLATFORM_ROLE_CODE,
        "director_fallback": DIRECTOR_POSITION_NAME_FALLBACK,
    }
    director_predicate = _director_position_predicate("p")

    if _table_exists(conn, "person_assignments") and _table_has_column(conn, "employees", "person_id"):
        row = conn.execute(
            text(
                f"""
                SELECT 1
                FROM public.employees e
                JOIN public.person_assignments pa
                  ON pa.person_id = e.person_id
                JOIN public.positions p
                  ON p.position_id = pa.position_id
                WHERE e.employee_id = :employee_id
                  AND {_employee_snapshot_current_predicate("e")}
                  AND pa.lifecycle_status = 'active'
                  AND pa.active_flag = TRUE
                  AND pa.start_date <= CURRENT_DATE
                  AND (pa.end_date IS NULL OR pa.end_date >= CURRENT_DATE)
                  AND {director_predicate}
                LIMIT 1
                """
            ),
            params,
        ).first()
        if row is not None:
            return True

    row = conn.execute(
        text(
            f"""
            SELECT 1
            FROM public.employees e
            JOIN public.positions p
              ON p.position_id = e.position_id
            WHERE e.employee_id = :employee_id
              AND {_employee_snapshot_current_predicate("e")}
              AND {director_predicate}
            LIMIT 1
            """
        ),
        params,
    ).first()
    return row is not None


def _fetch_employees_by_exact_full_name(conn: Connection, full_name: str) -> List[Dict[str, Any]]:
    normalized = _normalize_full_name(full_name)
    if not normalized:
        return []

    rows = conn.execute(
        text(
            """
            SELECT
                e.employee_id,
                e.full_name,
                p.name AS position_name
            FROM public.employees e
            LEFT JOIN public.positions p
              ON p.position_id = e.position_id
            WHERE LOWER(regexp_replace(BTRIM(e.full_name), '\\s+', ' ', 'g')) = :normalized_full_name
            ORDER BY e.employee_id
            """
        ),
        {"normalized_full_name": normalized},
    ).mappings().all()
    mapped = [_map_employee_candidate(dict(row)) for row in rows]
    return [item for item in mapped if item is not None]


def _resolve_verified_name_bridge(conn: Connection) -> PersonnelOrderSignatoryResolution:
    """Temporary ADR-044 compatibility path with strict verification gates."""
    director_users = _fetch_active_director_users(conn)
    if len(director_users) != 1:
        if len(director_users) > 1:
            return PersonnelOrderSignatoryResolution(
                warning=WARNING_NAME_BRIDGE_BLOCKED,
                source=SOURCE_PLATFORM_ROLE_VERIFIED_NAME_BRIDGE,
            )
        return PersonnelOrderSignatoryResolution(source=SOURCE_PLATFORM_ROLE_VERIFIED_NAME_BRIDGE)

    director_user = director_users[0]
    if director_user.get("employee_id") is not None:
        return PersonnelOrderSignatoryResolution(source=SOURCE_PLATFORM_ROLE_VERIFIED_NAME_BRIDGE)

    user_full_name = _normalize_text(director_user.get("full_name"))
    if not user_full_name:
        return PersonnelOrderSignatoryResolution(
            warning=WARNING_NAME_BRIDGE_BLOCKED,
            source=SOURCE_PLATFORM_ROLE_VERIFIED_NAME_BRIDGE,
        )

    name_matches = _fetch_employees_by_exact_full_name(conn, user_full_name)
    active_matches = [
        candidate
        for candidate in name_matches
        if _employee_has_current_director_assignment(conn, int(candidate["employee_id"]))
    ]

    if len(active_matches) != 1:
        warning = WARNING_AMBIGUOUS_EMPLOYEES if len(active_matches) > 1 else WARNING_NAME_BRIDGE_BLOCKED
        return PersonnelOrderSignatoryResolution(
            warning=warning,
            source=SOURCE_PLATFORM_ROLE_VERIFIED_NAME_BRIDGE,
        )

    candidate = active_matches[0]
    if not _normalize_text(candidate.get("position_name")):
        candidate = {
            **candidate,
            "position_name": _normalize_text(director_user.get("role_name"))
            or DIRECTOR_POSITION_NAME_FALLBACK.title(),
        }
    return _candidate_from_resolution(
        candidate,
        source=SOURCE_PLATFORM_ROLE_VERIFIED_NAME_BRIDGE,
    )


def _resolve_by_platform_role(conn: Connection) -> PersonnelOrderSignatoryResolution:
    if DIRECTOR_PLATFORM_ROLE_CODE not in LEADERSHIP_PLATFORM_ROLE_CODES:
        return PersonnelOrderSignatoryResolution(source=SOURCE_PLATFORM_ROLE)

    linked = _fetch_linked_platform_role_candidates(conn)
    linked_resolution = _finalize_unique_candidates(
        linked,
        source=SOURCE_PLATFORM_ROLE,
        ambiguous_warning=WARNING_AMBIGUOUS_DIRECTORS,
        empty_warning="",
    )
    if linked_resolution.resolved or linked_resolution.warning:
        return linked_resolution

    return _resolve_verified_name_bridge(conn)


def _fetch_hr_director_assignment_candidates(conn: Connection) -> List[Dict[str, Any]]:
    params = {
        "director_role_code": DIRECTOR_PLATFORM_ROLE_CODE,
        "director_fallback": DIRECTOR_POSITION_NAME_FALLBACK,
    }
    director_predicate = _director_position_predicate("p")

    if _table_exists(conn, "person_assignments") and _table_has_column(conn, "employees", "person_id"):
        rows = conn.execute(
            text(
                f"""
                SELECT DISTINCT
                    e.employee_id,
                    e.full_name,
                    p.name AS position_name
                FROM public.employees e
                JOIN public.person_assignments pa
                  ON pa.person_id = e.person_id
                JOIN public.positions p
                  ON p.position_id = pa.position_id
                WHERE {_employee_snapshot_current_predicate("e")}
                  AND pa.lifecycle_status = 'active'
                  AND pa.active_flag = TRUE
                  AND pa.start_date <= CURRENT_DATE
                  AND (pa.end_date IS NULL OR pa.end_date >= CURRENT_DATE)
                  AND {director_predicate}
                ORDER BY e.employee_id
                """
            ),
            params,
        ).mappings().all()
        mapped = [_map_employee_candidate(dict(row)) for row in rows]
        candidates = [item for item in mapped if item is not None]
        if candidates:
            return candidates

    rows = conn.execute(
        text(
            f"""
            SELECT
                e.employee_id,
                e.full_name,
                p.name AS position_name
            FROM public.employees e
            JOIN public.positions p
              ON p.position_id = e.position_id
            WHERE {_employee_snapshot_current_predicate("e")}
              AND {director_predicate}
            ORDER BY e.employee_id
            """
        ),
        params,
    ).mappings().all()
    mapped = [_map_employee_candidate(dict(row)) for row in rows]
    return [item for item in mapped if item is not None]


def _resolve_by_hr_director_assignment(conn: Connection) -> PersonnelOrderSignatoryResolution:
    return _finalize_unique_candidates(
        _fetch_hr_director_assignment_candidates(conn),
        source=SOURCE_HR_DIRECTOR_ASSIGNMENT,
        ambiguous_warning=WARNING_AMBIGUOUS_EMPLOYEES,
        empty_warning=WARNING_NOT_FOUND,
    )


def resolve_default_personnel_order_signatory(
    conn: Connection,
) -> PersonnelOrderSignatoryResolution:
    """Resolve a single default signatory candidate for a new personnel order."""
    platform_resolution = _resolve_by_platform_role(conn)
    if platform_resolution.resolved:
        return platform_resolution
    if platform_resolution.warning:
        return platform_resolution

    return _resolve_by_hr_director_assignment(conn)


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
