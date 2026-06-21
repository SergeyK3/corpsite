"""ADR-044 R2.2 — User → Employee linkage preview (read-only, no writes)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

PHASE_R2 = "R2"

CLASSIFICATION_AUTO_LINK_SAFE = "AUTO_LINK_SAFE"
CLASSIFICATION_REVIEW_REQUIRED = "REVIEW_REQUIRED"
CLASSIFICATION_AMBIGUOUS = "AMBIGUOUS"
CLASSIFICATION_IMPOSSIBLE = "IMPOSSIBLE"
CLASSIFICATION_EXCLUDED = "EXCLUDED_SERVICE_ACCOUNT"

MATCH_STRATEGY_LOGIN_SUFFIX = "LOGIN_SUFFIX"
MATCH_STRATEGY_NORMALIZED_FIO = "NORMALIZED_FIO"

REASON_LOGIN_SUFFIX_MATCH = "LOGIN_SUFFIX_MATCH"
REASON_FIO_EXACT_MATCH = "FIO_EXACT_MATCH"
REASON_SERVICE_ACCOUNT = "SERVICE_ACCOUNT"
REASON_MULTIPLE_EMPLOYEE_MATCHES = "MULTIPLE_EMPLOYEE_MATCHES"
REASON_MULTIPLE_USER_MATCHES = "MULTIPLE_USER_MATCHES"
REASON_FIO_COLLISION = "FIO_COLLISION"
REASON_MISSING_EMPLOYEE = "MISSING_EMPLOYEE"
REASON_INACTIVE_EMPLOYEE = "INACTIVE_EMPLOYEE"
REASON_NO_MATCH = "NO_MATCH"

CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"

SYSTEM_ADMIN_ROLE_ID = 2
OPERATIONAL_EMPLOYEE_STATUSES = frozenset({"draft", "active", "suspended"})

LOGIN_SUFFIX_RE = re.compile(r"^(.+)_([0-9]+)$")
SERVICE_LOGIN_PREFIX_RE = re.compile(
    r"^(admin|system|service|cron|bot|api|internal|sysadmin)",
    re.IGNORECASE,
)
SERVICE_NAME_RE = re.compile(
    r"(системн|service account|\bbot\b|\bcron\b)",
    re.IGNORECASE,
)


def normalize_fio(name: Optional[str]) -> str:
    if not name:
        return ""
    return re.sub(r"\s+", " ", str(name).strip().lower())


def parse_login_suffix(login: Optional[str]) -> Optional[int]:
    if not login:
        return None
    match = LOGIN_SUFFIX_RE.match(str(login).strip())
    if not match:
        return None
    try:
        return int(match.group(2))
    except ValueError:
        return None


def is_service_account(user: dict[str, Any]) -> bool:
    if int(user.get("role_id") or 0) == SYSTEM_ADMIN_ROLE_ID:
        return True

    login = str(user.get("login") or "").lower()
    google_login = str(user.get("google_login") or "").lower()
    full_name = str(user.get("full_name") or "")

    if SERVICE_LOGIN_PREFIX_RE.match(login):
        return True
    if login.startswith("admin_") or login.endswith("_admin"):
        return True
    if SERVICE_LOGIN_PREFIX_RE.match(google_login):
        return True
    if google_login.startswith("admin_"):
        return True
    if SERVICE_NAME_RE.search(full_name):
        return True
    return False


@dataclass
class _EmployeeRow:
    employee_id: int
    full_name: str
    operational_status: str
    normalized_name: str


@dataclass
class _UserRow:
    user_id: int
    login: Optional[str]
    full_name: str
    role_id: int
    google_login: Optional[str]
    normalized_name: str


@dataclass
class _PreviewContext:
    employees_by_id: dict[int, _EmployeeRow]
    active_employees_by_id: dict[int, _EmployeeRow]
    users: list[_UserRow]
    fio_users_by_name: dict[str, list[int]] = field(default_factory=dict)
    fio_employees_by_name: dict[str, list[int]] = field(default_factory=dict)
    login_users_by_employee: dict[int, list[int]] = field(default_factory=dict)


def _load_active_users(conn: Connection) -> list[_UserRow]:
    rows = conn.execute(
        text(
            """
            SELECT user_id, login, full_name, role_id, google_login
            FROM public.users
            WHERE COALESCE(is_active, TRUE) = TRUE
              AND employee_id IS NULL
            ORDER BY user_id
            """
        )
    ).mappings().all()
    return [
        _UserRow(
            user_id=int(row["user_id"]),
            login=row.get("login"),
            full_name=str(row.get("full_name") or ""),
            role_id=int(row.get("role_id") or 0),
            google_login=row.get("google_login"),
            normalized_name=normalize_fio(row.get("full_name")),
        )
        for row in rows
    ]


def _load_employees_for_lookup(conn: Connection) -> dict[int, _EmployeeRow]:
    rows = conn.execute(
        text(
            """
            SELECT employee_id, full_name, operational_status
            FROM public.employees
            ORDER BY employee_id
            """
        )
    ).mappings().all()
    return {
        int(row["employee_id"]): _EmployeeRow(
            employee_id=int(row["employee_id"]),
            full_name=str(row.get("full_name") or ""),
            operational_status=str(row.get("operational_status") or ""),
            normalized_name=normalize_fio(row.get("full_name")),
        )
        for row in rows
    }


def _load_active_employees(conn: Connection) -> list[_EmployeeRow]:
    return [
        employee
        for employee in _load_employees_for_lookup(conn).values()
        if employee.operational_status in OPERATIONAL_EMPLOYEE_STATUSES
    ]


def _count_active_users(conn: Connection) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(*) AS cnt
                FROM public.users
                WHERE COALESCE(is_active, TRUE) = TRUE
                """
            )
        ).scalar_one()
    )


def _build_context(users: list[_UserRow], employees: list[_EmployeeRow]) -> _PreviewContext:
    employees_by_id = {employee.employee_id: employee for employee in employees}
    active_employees_by_id = {
        employee_id: employee
        for employee_id, employee in employees_by_id.items()
        if employee.operational_status in OPERATIONAL_EMPLOYEE_STATUSES
    }
    fio_users_by_name: dict[str, list[int]] = {}
    fio_employees_by_name: dict[str, list[int]] = {}
    login_users_by_employee: dict[int, list[int]] = {}

    for user in users:
        if user.normalized_name:
            fio_users_by_name.setdefault(user.normalized_name, []).append(user.user_id)

        parsed_id = parse_login_suffix(user.login)
        if parsed_id is None:
            continue
        employee = active_employees_by_id.get(parsed_id)
        if employee is None:
            continue
        login_users_by_employee.setdefault(parsed_id, []).append(user.user_id)

    for employee in active_employees_by_id.values():
        if employee.normalized_name:
            fio_employees_by_name.setdefault(employee.normalized_name, []).append(
                employee.employee_id
            )

    return _PreviewContext(
        employees_by_id=employees_by_id,
        active_employees_by_id=active_employees_by_id,
        users=users,
        fio_users_by_name=fio_users_by_name,
        fio_employees_by_name=fio_employees_by_name,
        login_users_by_employee=login_users_by_employee,
    )


def _fio_employee_ids(ctx: _PreviewContext, user: _UserRow) -> list[int]:
    if not user.normalized_name:
        return []
    return list(ctx.fio_employees_by_name.get(user.normalized_name, []))


def _is_fio_collision(ctx: _PreviewContext, user: _UserRow) -> bool:
    if not user.normalized_name:
        return False
    user_count = len(ctx.fio_users_by_name.get(user.normalized_name, []))
    employee_count = len(ctx.fio_employees_by_name.get(user.normalized_name, []))
    if user_count == 0 and employee_count == 0:
        return False
    return user_count > 1 or employee_count > 1


def _classify_user(ctx: _PreviewContext, user: _UserRow) -> dict[str, Any]:
    reason_codes: list[str] = []
    blockers: list[str] = []

    if is_service_account(
        {
            "role_id": user.role_id,
            "login": user.login,
            "google_login": user.google_login,
            "full_name": user.full_name,
        }
    ):
        return _candidate(
            user=user,
            classification=CLASSIFICATION_EXCLUDED,
            reason_codes=[REASON_SERVICE_ACCOUNT],
            blockers=blockers,
            requires_manual_confirmation=False,
        )

    parsed_login_employee_id = parse_login_suffix(user.login)
    login_target_id: Optional[int] = None
    login_suffix_present = parsed_login_employee_id is not None

    if login_suffix_present:
        login_employee = ctx.employees_by_id.get(parsed_login_employee_id)
        if login_employee is None:
            blockers.append(REASON_MISSING_EMPLOYEE)
        elif login_employee.operational_status not in OPERATIONAL_EMPLOYEE_STATUSES:
            blockers.append(REASON_INACTIVE_EMPLOYEE)
        else:
            login_target_id = parsed_login_employee_id

    fio_employee_ids = _fio_employee_ids(ctx, user)
    fio_collision = _is_fio_collision(ctx, user)

    employee_targets: set[int] = set()
    if login_target_id is not None:
        employee_targets.add(login_target_id)
    employee_targets.update(fio_employee_ids)

    if len(employee_targets) > 1:
        reason_codes.append(REASON_MULTIPLE_EMPLOYEE_MATCHES)
        if fio_collision:
            reason_codes.append(REASON_FIO_COLLISION)
        return _candidate(
            user=user,
            classification=CLASSIFICATION_AMBIGUOUS,
            proposed_employee_id=sorted(employee_targets)[0],
            employee_name=_employee_name(ctx, sorted(employee_targets)[0]),
            reason_codes=reason_codes,
            blockers=blockers,
            requires_manual_confirmation=True,
        )

    if login_target_id is not None and len(ctx.login_users_by_employee.get(login_target_id, [])) > 1:
        reason_codes.append(REASON_MULTIPLE_USER_MATCHES)
        return _candidate(
            user=user,
            classification=CLASSIFICATION_AMBIGUOUS,
            proposed_employee_id=login_target_id,
            employee_name=_employee_name(ctx, login_target_id),
            match_strategy=MATCH_STRATEGY_LOGIN_SUFFIX,
            reason_codes=reason_codes,
            blockers=blockers,
            requires_manual_confirmation=True,
        )

    if fio_collision and fio_employee_ids:
        reason_codes.append(REASON_FIO_COLLISION)
        proposed = fio_employee_ids[0] if len(fio_employee_ids) == 1 else None
        return _candidate(
            user=user,
            classification=CLASSIFICATION_AMBIGUOUS,
            proposed_employee_id=proposed,
            employee_name=_employee_name(ctx, proposed) if proposed else None,
            match_strategy=MATCH_STRATEGY_NORMALIZED_FIO if fio_employee_ids else None,
            reason_codes=reason_codes,
            blockers=blockers,
            requires_manual_confirmation=True,
        )

    if login_suffix_present and REASON_MISSING_EMPLOYEE in blockers:
        reason_codes.append(REASON_MISSING_EMPLOYEE)
        return _candidate(
            user=user,
            classification=CLASSIFICATION_IMPOSSIBLE,
            reason_codes=reason_codes,
            blockers=blockers,
            requires_manual_confirmation=False,
        )

    if login_suffix_present and REASON_INACTIVE_EMPLOYEE in blockers:
        reason_codes.append(REASON_INACTIVE_EMPLOYEE)
        return _candidate(
            user=user,
            classification=CLASSIFICATION_IMPOSSIBLE,
            proposed_employee_id=parsed_login_employee_id,
            employee_name=_employee_name(ctx, parsed_login_employee_id),
            match_strategy=MATCH_STRATEGY_LOGIN_SUFFIX,
            reason_codes=reason_codes,
            blockers=blockers,
            requires_manual_confirmation=False,
        )

    if login_target_id is not None:
        reason_codes.append(REASON_LOGIN_SUFFIX_MATCH)
        if len(fio_employee_ids) == 1 and fio_employee_ids[0] == login_target_id:
            reason_codes.append(REASON_FIO_EXACT_MATCH)
        return _candidate(
            user=user,
            classification=CLASSIFICATION_REVIEW_REQUIRED,
            proposed_employee_id=login_target_id,
            employee_name=_employee_name(ctx, login_target_id),
            match_strategy=MATCH_STRATEGY_LOGIN_SUFFIX,
            reason_codes=reason_codes,
            blockers=blockers,
            requires_manual_confirmation=True,
        )

    if len(fio_employee_ids) == 1 and not fio_collision:
        reason_codes.append(REASON_FIO_EXACT_MATCH)
        employee_id = fio_employee_ids[0]
        return _candidate(
            user=user,
            classification=CLASSIFICATION_REVIEW_REQUIRED,
            proposed_employee_id=employee_id,
            employee_name=_employee_name(ctx, employee_id),
            match_strategy=MATCH_STRATEGY_NORMALIZED_FIO,
            reason_codes=reason_codes,
            blockers=blockers,
            requires_manual_confirmation=True,
        )

    reason_codes.append(REASON_NO_MATCH)
    return _candidate(
        user=user,
        classification=CLASSIFICATION_IMPOSSIBLE,
        reason_codes=reason_codes,
        blockers=blockers,
        requires_manual_confirmation=False,
    )


def _employee_name(ctx: _PreviewContext, employee_id: Optional[int]) -> Optional[str]:
    if employee_id is None:
        return None
    employee = ctx.employees_by_id.get(int(employee_id))
    return employee.full_name if employee else None


def _candidate(
    *,
    user: _UserRow,
    classification: str,
    proposed_employee_id: Optional[int] = None,
    employee_name: Optional[str] = None,
    match_strategy: Optional[str] = None,
    reason_codes: list[str],
    blockers: list[str],
    requires_manual_confirmation: bool,
) -> dict[str, Any]:
    confidence: Optional[str] = None
    if classification == CLASSIFICATION_REVIEW_REQUIRED:
        confidence = CONFIDENCE_MEDIUM
    elif classification == CLASSIFICATION_IMPOSSIBLE:
        confidence = CONFIDENCE_LOW

    return {
        "user_id": user.user_id,
        "login": user.login,
        "proposed_employee_id": proposed_employee_id,
        "employee_name": employee_name,
        "match_strategy": match_strategy,
        "classification": classification,
        "confidence": confidence,
        "reason_codes": reason_codes,
        "blockers": blockers,
        "requires_manual_confirmation": requires_manual_confirmation,
    }


def _build_summary(candidates: list[dict[str, Any]], total_users: int) -> dict[str, int]:
    counts = {
        "total_users": total_users,
        "auto_link_safe": 0,
        "review_required": 0,
        "ambiguous": 0,
        "impossible": 0,
        "excluded": 0,
    }
    key_by_classification = {
        CLASSIFICATION_AUTO_LINK_SAFE: "auto_link_safe",
        CLASSIFICATION_REVIEW_REQUIRED: "review_required",
        CLASSIFICATION_AMBIGUOUS: "ambiguous",
        CLASSIFICATION_IMPOSSIBLE: "impossible",
        CLASSIFICATION_EXCLUDED: "excluded",
    }
    for candidate in candidates:
        bucket = key_by_classification.get(candidate["classification"])
        if bucket:
            counts[bucket] += 1
    return counts


def run_user_linkage_preview(conn: Connection) -> dict[str, Any]:
    """Read-only User → Employee linkage preview. Never writes."""
    users = _load_active_users(conn)
    employees = list(_load_employees_for_lookup(conn).values())
    total_users = _count_active_users(conn)
    ctx = _build_context(users, employees)
    candidates = [_classify_user(ctx, user) for user in users]

    return {
        "phase": PHASE_R2,
        "dry_run": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": _build_summary(candidates, total_users),
        "candidates": candidates,
    }
