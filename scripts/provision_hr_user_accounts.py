#!/usr/bin/env python3
"""Safely provision platform users for an approved HR employee roster.

The script never creates or changes employee, placement, position, org-unit, or
access-grant data. Apply mode creates only missing ``public.users`` rows and is
fail-closed unless every roster row is READY or ALREADY_EXISTS.
"""
from __future__ import annotations

import argparse
import getpass
import sys
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Sequence

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.auth import hash_password  # noqa: E402
from app.db.engine import engine  # noqa: E402

HR_UNIT_CODE = "HR"
ORDINARY_HR_ROLE_CODE = "HR_reg"
ORDINARY_HR_ALLOWED_ROLE_GRANTS = frozenset({"ACCESS_OBSERVER"})
INCOMING_INFO_PERMISSION_PREFIX = "INCOMING_INFO_"
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 200

READY = "READY"
ALREADY_EXISTS = "ALREADY_EXISTS"
NOT_FOUND = "NOT_FOUND"
AMBIGUOUS = "AMBIGUOUS"
WRONG_UNIT = "WRONG_UNIT"
LOGIN_CONFLICT = "LOGIN_CONFLICT"
LINK_CONFLICT = "LINK_CONFLICT"
ALLOWED_APPLY_STATUSES = frozenset({READY, ALREADY_EXISTS})


@dataclass(frozen=True)
class AccountSpec:
    source_full_name: str
    login: str


APPROVED_ACCOUNTS: tuple[AccountSpec, ...] = (
    AccountSpec("Достояр Гулбану Есенбаевна", "dostoyar.ge"),
    AccountSpec("Абзалқызы Толғанай", "abzalkyzy.t"),
    AccountSpec(
        "Бекмагамбетова Гулден Нурлановна",
        "bekmagambetova.gn",
    ),
    AccountSpec("Умерзакова Махаббат Тылеулесовна", "umerzakova.mt"),
    AccountSpec("Хамитжанова Куралай Данабековна", "khamitzhanova.kd"),
    AccountSpec("Достоярова Навзгуль Салимовна", "dostoyarova.ns"),
    AccountSpec("Сырманова Айдана Ерболқызы", "syrmanova.ae"),
    AccountSpec("Капбасова Гулнура Муктаровна", "kapbasova.gm"),
    AccountSpec("Абежанова Марал Иманмагзамовна", "abezhanova.mi"),
    AccountSpec("Шаймарданова Алия Тулешовна", "shaimardanova.at"),
    AccountSpec(
        "Абдрахманова Гульмира Фариденовна",
        "abdrakhmanova.gf",
    ),
    AccountSpec("Өсерова Айсара Асанқызы", "oserova.aa"),
)


@dataclass(frozen=True)
class RoleRecord:
    role_id: int
    code: str
    name: str
    is_active: bool
    active_grant_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class OrgUnitRecord:
    unit_id: int
    code: str
    name: str
    is_active: bool


@dataclass(frozen=True)
class EmployeeRecord:
    employee_id: int
    full_name: str
    person_id: int | None
    is_active: bool
    operational_status: str | None
    org_unit_id: int | None
    org_unit_code: str | None
    org_unit_name: str | None
    position_id: int | None
    position_name: str | None
    date_from: date | None
    date_to: date | None


@dataclass(frozen=True)
class PlacementRecord:
    employee_id: int
    assignment_id: int
    org_unit_id: int | None
    org_unit_code: str | None
    org_unit_name: str | None
    position_id: int | None
    position_name: str | None
    start_date: date | None
    end_date: date | None
    active_flag: bool
    is_primary: bool
    lifecycle_status: str | None
    link_status: str | None


@dataclass(frozen=True)
class UserRecord:
    user_id: int
    employee_id: int | None
    full_name: str
    login: str | None
    role_id: int
    role_code: str | None
    is_active: bool


@dataclass(frozen=True)
class ProvisioningSnapshot:
    roles: tuple[RoleRecord, ...]
    org_units: tuple[OrgUnitRecord, ...]
    employees: tuple[EmployeeRecord, ...]
    placements: tuple[PlacementRecord, ...]
    users: tuple[UserRecord, ...]


@dataclass(frozen=True)
class EffectivePlacement:
    org_unit_id: int
    org_unit_code: str | None
    org_unit_name: str | None
    position_id: int
    position_name: str | None
    source: str


@dataclass(frozen=True)
class PlanRow:
    spec: AccountSpec
    status: str
    detail: str
    employee: EmployeeRecord | None
    placement: EffectivePlacement | None
    existing_user: UserRecord | None
    login_owner: UserRecord | None
    proposed_role: RoleRecord


class ProvisioningError(RuntimeError):
    """A fail-closed configuration, plan, or apply error."""


def normalize_identity(value: str | None) -> str:
    """Exact Unicode identity key with only compatibility/case/space normalization."""
    normalized = unicodedata.normalize("NFKC", value or "")
    return " ".join(normalized.split()).casefold()


def normalize_login(value: str | None) -> str:
    return " ".join((value or "").split()).casefold()


def _is_current(start: date | None, end: date | None, *, today: date) -> bool:
    return (start is None or start <= today) and (end is None or end >= today)


def _resolve_role(snapshot: ProvisioningSnapshot, role_code: str) -> RoleRecord:
    matches = [role for role in snapshot.roles if role.code == role_code and role.is_active]
    if len(matches) != 1:
        raise ProvisioningError(
            f"Expected exactly one active role code={role_code!r}; found {len(matches)}."
        )
    role = matches[0]
    if role.code == "HR_HEAD":
        raise ProvisioningError("Ordinary HR accounts must never use HR_HEAD.")
    effective_codes = frozenset(role.active_grant_codes)
    forbidden_codes = sorted(
        code
        for code in effective_codes
        if code.startswith(INCOMING_INFO_PERMISSION_PREFIX)
        or code not in ORDINARY_HR_ALLOWED_ROLE_GRANTS
    )
    if forbidden_codes:
        joined = ", ".join(forbidden_codes)
        raise ProvisioningError(
            f"Role {role.code!r} has non-baseline effective access grants "
            f"({joined}); refusing implicit rights."
        )
    return role


def _resolve_hr_unit(snapshot: ProvisioningSnapshot, unit_code: str) -> OrgUnitRecord:
    matches = [
        unit
        for unit in snapshot.org_units
        if normalize_login(unit.code) == normalize_login(unit_code) and unit.is_active
    ]
    if len(matches) != 1:
        raise ProvisioningError(
            f"Expected exactly one active org unit code={unit_code!r}; found {len(matches)}."
        )
    return matches[0]


def _effective_placement(
    employee: EmployeeRecord,
    placements: Sequence[PlacementRecord],
    *,
    today: date,
) -> tuple[EffectivePlacement | None, bool]:
    canonical = [
        row
        for row in placements
        if row.employee_id == employee.employee_id
        and row.active_flag
        and row.is_primary
        and normalize_login(row.lifecycle_status) == "active"
        and normalize_login(row.link_status) == "active"
        and _is_current(row.start_date, row.end_date, today=today)
    ]
    if len(canonical) > 1:
        return None, True
    if canonical:
        row = canonical[0]
        if row.org_unit_id is None or row.position_id is None:
            return None, False
        return (
            EffectivePlacement(
                org_unit_id=row.org_unit_id,
                org_unit_code=row.org_unit_code,
                org_unit_name=row.org_unit_name,
                position_id=row.position_id,
                position_name=row.position_name,
                source=f"person_assignment:{row.assignment_id}",
            ),
            False,
        )

    operational = normalize_login(employee.operational_status)
    snapshot_active = (
        employee.is_active
        and operational not in {"inactive", "terminated", "dismissed"}
        and _is_current(employee.date_from, employee.date_to, today=today)
        and employee.org_unit_id is not None
        and employee.position_id is not None
    )
    if not snapshot_active:
        return None, False
    return (
        EffectivePlacement(
            org_unit_id=int(employee.org_unit_id),
            org_unit_code=employee.org_unit_code,
            org_unit_name=employee.org_unit_name,
            position_id=int(employee.position_id),
            position_name=employee.position_name,
            source="employee_snapshot",
        ),
        False,
    )


def build_plan_from_snapshot(
    snapshot: ProvisioningSnapshot,
    specs: Sequence[AccountSpec] = APPROVED_ACCOUNTS,
    *,
    today: date | None = None,
    role_code: str = ORDINARY_HR_ROLE_CODE,
    hr_unit_code: str = HR_UNIT_CODE,
) -> list[PlanRow]:
    role = _resolve_role(snapshot, role_code)
    hr_unit = _resolve_hr_unit(snapshot, hr_unit_code)
    effective_today = today or date.today()

    employees_by_name: dict[str, list[EmployeeRecord]] = {}
    for employee in snapshot.employees:
        employees_by_name.setdefault(normalize_identity(employee.full_name), []).append(employee)

    users_by_login: dict[str, list[UserRecord]] = {}
    users_by_employee: dict[int, list[UserRecord]] = {}
    users_by_name: dict[str, list[UserRecord]] = {}
    for user in snapshot.users:
        users_by_login.setdefault(normalize_login(user.login), []).append(user)
        users_by_name.setdefault(normalize_identity(user.full_name), []).append(user)
        if user.employee_id is not None:
            users_by_employee.setdefault(user.employee_id, []).append(user)

    plan: list[PlanRow] = []
    for spec in specs:
        employee_matches = employees_by_name.get(normalize_identity(spec.source_full_name), [])
        if not employee_matches:
            plan.append(
                PlanRow(
                    spec, NOT_FOUND, "No exact employee match.", None, None, None, None, role
                )
            )
            continue
        if len(employee_matches) > 1:
            plan.append(
                PlanRow(
                    spec,
                    AMBIGUOUS,
                    f"Multiple exact employee matches: {len(employee_matches)}.",
                    None,
                    None,
                    None,
                    None,
                    role,
                )
            )
            continue

        employee = employee_matches[0]
        placement, placement_ambiguous = _effective_placement(
            employee, snapshot.placements, today=effective_today
        )
        linked_users = users_by_employee.get(employee.employee_id, [])
        login_owners = users_by_login.get(normalize_login(spec.login), [])
        login_owner = login_owners[0] if len(login_owners) == 1 else None
        existing_user = linked_users[0] if len(linked_users) == 1 else None

        if placement_ambiguous:
            status, detail = AMBIGUOUS, "Multiple current primary placements."
        elif placement is None:
            status, detail = WRONG_UNIT, "No unique active placement with unit and position."
        elif normalize_login(placement.org_unit_code) != normalize_login(hr_unit.code):
            status, detail = (
                WRONG_UNIT,
                (
                    f"Active placement is unit code={placement.org_unit_code!r}, "
                    f"expected {hr_unit.code!r}."
                ),
            )
        elif len(linked_users) > 1:
            status, detail = LINK_CONFLICT, "Multiple users are linked to this employee."
        elif existing_user is not None:
            if normalize_login(existing_user.login) != normalize_login(spec.login):
                status, detail = (
                    LINK_CONFLICT,
                    (
                        f"Employee is already linked to user_id={existing_user.user_id} "
                        "with another login."
                    ),
                )
            elif len(login_owners) != 1:
                status, detail = (
                    LOGIN_CONFLICT,
                    "Requested login does not have exactly one owner.",
                )
            elif login_owner is None or login_owner.user_id != existing_user.user_id:
                status, detail = (
                    LOGIN_CONFLICT,
                    "Requested login belongs to a different user.",
                )
            else:
                status, detail = ALREADY_EXISTS, "Employee already has the requested login."
        else:
            identity_users = [
                user
                for user in users_by_name.get(normalize_identity(employee.full_name), [])
                if user.employee_id != employee.employee_id
            ]
            if identity_users:
                conflict_ids = ",".join(str(user.user_id) for user in identity_users)
                status, detail = (
                    LINK_CONFLICT,
                    f"Same normalized FIO is used by unlinked/other user(s): {conflict_ids}.",
                )
            elif len(login_owners) > 1:
                status, detail = LOGIN_CONFLICT, "Requested login has multiple owners."
            elif login_owner is not None:
                status, detail = (
                    LOGIN_CONFLICT,
                    f"Requested login belongs to user_id={login_owner.user_id}.",
                )
            else:
                status, detail = READY, "Missing user can be created safely."

        plan.append(
            PlanRow(
                spec=spec,
                status=status,
                detail=detail,
                employee=employee,
                placement=placement,
                existing_user=existing_user,
                login_owner=login_owner,
                proposed_role=role,
            )
        )
    return plan


def _assert_required_schema(conn: Connection) -> None:
    required: dict[str, set[str]] = {
        "users": {
            "user_id",
            "full_name",
            "google_login",
            "role_id",
            "unit_id",
            "is_active",
            "login",
            "password_hash",
            "employee_id",
            "must_change_password",
        },
        "employees": {
            "employee_id",
            "full_name",
            "org_unit_id",
            "position_id",
            "is_active",
        },
        "roles": {"role_id", "code", "name"},
        "org_units": {"unit_id", "code", "name", "is_active"},
        "positions": {"position_id", "name"},
    }
    rows = conn.execute(
        text(
            """
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = ANY(:tables)
            """
        ),
        {"tables": list(required)},
    ).all()
    actual: dict[str, set[str]] = {}
    for table_name, column_name in rows:
        actual.setdefault(str(table_name), set()).add(str(column_name))
    missing = {
        table: sorted(columns - actual.get(table, set()))
        for table, columns in required.items()
        if columns - actual.get(table, set())
    }
    if missing:
        raise ProvisioningError(f"Required schema is missing: {missing}")


def load_snapshot(conn: Connection) -> ProvisioningSnapshot:
    _assert_required_schema(conn)
    roles_have_is_active = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'roles'
              AND column_name = 'is_active'
            LIMIT 1
            """
        )
    ).first() is not None
    role_active_sql = "is_active" if roles_have_is_active else "TRUE"
    role_rows = conn.execute(
        text(
            f"""
            SELECT role_id, code, name, {role_active_sql} AS is_active
            FROM public.roles
            WHERE code = :role_code
            ORDER BY role_id
            """
        ),
        {"role_code": ORDINARY_HR_ROLE_CODE},
    ).mappings().all()
    roles: list[RoleRecord] = []
    for row in role_rows:
        grant_codes = conn.execute(
            text(
                """
                SELECT ar.code
                FROM public.access_grants g
                JOIN public.access_roles ar ON ar.access_role_id = g.access_role_id
                WHERE g.target_type = 'ROLE'
                  AND g.target_id = :role_id
                  AND g.active_flag = TRUE
                  AND g.revoked_at IS NULL
                  AND g.starts_at <= statement_timestamp()
                  AND (g.ends_at IS NULL OR g.ends_at > statement_timestamp())
                  AND ar.is_active = TRUE
                ORDER BY ar.code
                """
            ),
            {"role_id": int(row["role_id"])},
        ).scalars().all()
        roles.append(
            RoleRecord(
                role_id=int(row["role_id"]),
                code=str(row["code"]),
                name=str(row["name"]),
                is_active=bool(row["is_active"]),
                active_grant_codes=tuple(str(code) for code in grant_codes),
            )
        )

    units = tuple(
        OrgUnitRecord(
            unit_id=int(row["unit_id"]),
            code=str(row["code"] or ""),
            name=str(row["name"]),
            is_active=bool(row["is_active"]),
        )
        for row in conn.execute(
            text(
                """
                SELECT unit_id, code, name, is_active
                FROM public.org_units
                WHERE lower(trim(code)) = lower(:unit_code)
                ORDER BY unit_id
                """
            ),
            {"unit_code": HR_UNIT_CODE},
        ).mappings()
    )

    employees = tuple(
        EmployeeRecord(
            employee_id=int(row["employee_id"]),
            full_name=str(row["full_name"]),
            person_id=int(row["person_id"]) if row["person_id"] is not None else None,
            is_active=bool(row["is_active"]),
            operational_status=(
                str(row["operational_status"]) if row["operational_status"] is not None else None
            ),
            org_unit_id=int(row["org_unit_id"]) if row["org_unit_id"] is not None else None,
            org_unit_code=str(row["org_unit_code"]) if row["org_unit_code"] is not None else None,
            org_unit_name=str(row["org_unit_name"]) if row["org_unit_name"] is not None else None,
            position_id=int(row["position_id"]) if row["position_id"] is not None else None,
            position_name=str(row["position_name"]) if row["position_name"] is not None else None,
            date_from=row["date_from"],
            date_to=row["date_to"],
        )
        for row in conn.execute(
            text(
                """
                SELECT e.employee_id, e.full_name, e.person_id, e.is_active,
                       e.operational_status, e.org_unit_id, ou.code AS org_unit_code,
                       ou.name AS org_unit_name, e.position_id, p.name AS position_name,
                       e.date_from, e.date_to
                FROM public.employees e
                LEFT JOIN public.org_units ou ON ou.unit_id = e.org_unit_id
                LEFT JOIN public.positions p ON p.position_id = e.position_id
                ORDER BY e.employee_id
                """
            )
        ).mappings()
    )

    placements = tuple(
        PlacementRecord(
            employee_id=int(row["employee_id"]),
            assignment_id=int(row["assignment_id"]),
            org_unit_id=int(row["org_unit_id"]) if row["org_unit_id"] is not None else None,
            org_unit_code=str(row["org_unit_code"]) if row["org_unit_code"] is not None else None,
            org_unit_name=str(row["org_unit_name"]) if row["org_unit_name"] is not None else None,
            position_id=int(row["position_id"]) if row["position_id"] is not None else None,
            position_name=str(row["position_name"]) if row["position_name"] is not None else None,
            start_date=row["start_date"],
            end_date=row["end_date"],
            active_flag=bool(row["active_flag"]),
            is_primary=bool(row["is_primary"]),
            lifecycle_status=(
                str(row["lifecycle_status"]) if row["lifecycle_status"] is not None else None
            ),
            link_status=str(row["link_status"]) if row["link_status"] is not None else None,
        )
        for row in conn.execute(
            text(
                """
                SELECT eal.employee_id, pa.assignment_id, pa.org_unit_id,
                       ou.code AS org_unit_code, ou.name AS org_unit_name,
                       pa.position_id, p.name AS position_name,
                       pa.start_date, pa.end_date, pa.active_flag, pa.is_primary,
                       pa.lifecycle_status, eal.link_status
                FROM public.employee_assignment_links eal
                JOIN public.person_assignments pa ON pa.assignment_id = eal.assignment_id
                LEFT JOIN public.org_units ou ON ou.unit_id = pa.org_unit_id
                LEFT JOIN public.positions p ON p.position_id = pa.position_id
                ORDER BY eal.employee_id, pa.assignment_id
                """
            )
        ).mappings()
    )

    users = tuple(
        UserRecord(
            user_id=int(row["user_id"]),
            employee_id=int(row["employee_id"]) if row["employee_id"] is not None else None,
            full_name=str(row["full_name"]),
            login=str(row["login"]) if row["login"] is not None else None,
            role_id=int(row["role_id"]),
            role_code=str(row["role_code"]) if row["role_code"] is not None else None,
            is_active=bool(row["is_active"]),
        )
        for row in conn.execute(
            text(
                """
                SELECT u.user_id, u.employee_id, u.full_name, u.login, u.role_id,
                       r.code AS role_code, u.is_active
                FROM public.users u
                LEFT JOIN public.roles r ON r.role_id = u.role_id
                ORDER BY u.user_id
                """
            )
        ).mappings()
    )
    return ProvisioningSnapshot(tuple(roles), units, employees, placements, users)


def build_plan(conn: Connection) -> list[PlanRow]:
    return build_plan_from_snapshot(load_snapshot(conn))


def render_plan(plan: Sequence[PlanRow], *, output: Callable[[str], None] = print) -> None:
    output("HR user provisioning plan")
    output("=" * 80)
    for index, row in enumerate(plan, start=1):
        employee = row.employee
        placement = row.placement
        existing = row.existing_user
        login_owner = row.login_owner
        output(f"[{index:02d}] {row.spec.source_full_name}")
        output(f"  planned_login: {row.spec.login}")
        output(f"  employee_found: {'yes' if employee else 'no'}")
        output(f"  employee_id: {employee.employee_id if employee else '-'}")
        output(f"  actual_full_name: {employee.full_name if employee else '-'}")
        output(f"  active_unit: {placement.org_unit_name if placement else '-'}")
        output(f"  active_unit_code: {placement.org_unit_code if placement else '-'}")
        output(f"  position: {placement.position_name if placement else '-'}")
        output(f"  placement_source: {placement.source if placement else '-'}")
        output(f"  existing_user_id: {existing.user_id if existing else '-'}")
        output(f"  existing_login: {existing.login if existing else '-'}")
        output(f"  login_taken: {'yes' if login_owner else 'no'}")
        output(f"  login_owner_user_id: {login_owner.user_id if login_owner else '-'}")
        output(f"  proposed_role: {row.proposed_role.code} ({row.proposed_role.name})")
        output(f"  result: {row.status}")
        output(f"  detail: {row.detail}")
    counts: dict[str, int] = {}
    for row in plan:
        counts[row.status] = counts.get(row.status, 0) + 1
    output("-" * 80)
    output("summary: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    output(
        "password_change_risk: self-service first-login password change is not implemented; "
        "new users keep must_change_password=false."
    )


def plan_is_apply_safe(plan: Sequence[PlanRow]) -> bool:
    return len(plan) == len(APPROVED_ACCOUNTS) and all(
        row.status in ALLOWED_APPLY_STATUSES for row in plan
    )


def _plan_signature(plan: Sequence[PlanRow]) -> tuple[PlanRow, ...]:
    return tuple(plan)


def _lock_users_for_apply(conn: Connection) -> None:
    # ACCESS EXCLUSIVE intentionally blocks stale user-creation pre-checks in other
    # sessions until this short provisioning transaction commits or rolls back.
    conn.execute(text("LOCK TABLE public.users IN ACCESS EXCLUSIVE MODE"))


def provision_ready_rows(
    conn: Connection,
    plan: Sequence[PlanRow],
    password: str,
    *,
    hash_fn: Callable[[str], str] = hash_password,
    lock_users: bool = True,
) -> list[int]:
    if not plan_is_apply_safe(plan):
        raise ProvisioningError("Apply requires all 12 rows to be READY or ALREADY_EXISTS.")
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise ProvisioningError(
            f"Temporary password length must be {MIN_PASSWORD_LENGTH}..{MAX_PASSWORD_LENGTH}."
        )

    if lock_users:
        _lock_users_for_apply(conn)
    ready_rows = [row for row in plan if row.status == READY]
    login_keys = [normalize_login(row.spec.login) for row in ready_rows]
    employee_ids = [
        row.employee.employee_id for row in ready_rows if row.employee is not None
    ]
    if len(login_keys) != len(set(login_keys)):
        raise ProvisioningError("READY plan contains duplicate logins.")
    if len(employee_ids) != len(set(employee_ids)):
        raise ProvisioningError("READY plan contains duplicate employee links.")
    for row in ready_rows:
        if row.employee is None:
            raise ProvisioningError("READY row lost employee context.")
        conflict = conn.execute(
            text(
                """
                SELECT user_id, login, employee_id
                FROM public.users
                WHERE lower(login) = lower(:login)
                   OR employee_id = :employee_id
                ORDER BY user_id
                LIMIT 1
                """
            ),
            {"login": row.spec.login, "employee_id": row.employee.employee_id},
        ).mappings().first()
        if conflict:
            raise ProvisioningError(
                "User/login state changed after planning; transaction rolled back."
            )

    created_ids: list[int] = []
    for row in plan:
        if row.status != READY:
            continue
        if row.employee is None or row.placement is None:
            raise ProvisioningError("READY row lost employee or placement context.")
        password_hash = hash_fn(password)
        created = conn.execute(
            text(
                """
                INSERT INTO public.users (
                    full_name,
                    google_login,
                    role_id,
                    unit_id,
                    is_active,
                    login,
                    password_hash,
                    employee_id,
                    must_change_password
                )
                VALUES (
                    :full_name,
                    :google_login,
                    :role_id,
                    :unit_id,
                    TRUE,
                    :login,
                    :password_hash,
                    :employee_id,
                    FALSE
                )
                RETURNING user_id
                """
            ),
            {
                "full_name": row.employee.full_name,
                "google_login": row.spec.login,
                "role_id": row.proposed_role.role_id,
                "unit_id": row.placement.org_unit_id,
                "login": row.spec.login,
                "password_hash": password_hash,
                "employee_id": row.employee.employee_id,
            },
        ).scalar_one()
        created_ids.append(int(created))
    return created_ids


def _read_password() -> str:
    password = getpass.getpass("Shared temporary password: ")
    confirmation = getpass.getpass("Repeat temporary password: ")
    if password != confirmation:
        raise ProvisioningError("Password confirmation does not match.")
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise ProvisioningError(
            f"Temporary password length must be {MIN_PASSWORD_LENGTH}..{MAX_PASSWORD_LENGTH}."
        )
    return password


def _assert_safe_apply_runtime() -> None:
    if Path.cwd().resolve() != PROJECT_ROOT:
        raise ProvisioningError(f"Apply must run from application root: {PROJECT_ROOT}")
    if sys.prefix == sys.base_prefix:
        raise ProvisioningError("Apply requires an active virtual environment (.venv).")


def run_dry_run(db_engine: Engine = engine) -> int:
    with db_engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        plan = build_plan(conn)
        render_plan(plan)
        conn.rollback()
    return 0 if plan_is_apply_safe(plan) else 2


def run_apply(db_engine: Engine = engine) -> int:
    _assert_safe_apply_runtime()
    with db_engine.connect() as diagnostic_conn:
        diagnostic_conn.execute(text("SET TRANSACTION READ ONLY"))
        initial_plan = build_plan(diagnostic_conn)
        diagnostic_conn.rollback()

    if not plan_is_apply_safe(initial_plan):
        render_plan(initial_plan)
        raise ProvisioningError(
            "Apply blocked: every roster row must be READY or ALREADY_EXISTS."
        )
    ready_count = sum(row.status == READY for row in initial_plan)
    if ready_count == 0:
        render_plan(initial_plan)
        print("No accounts to create; all requested accounts already exist.")
        return 0

    password = _read_password()
    render_plan(initial_plan)
    phrase = f"APPLY {ready_count} HR USER ACCOUNTS"
    entered = input(f"Type exactly '{phrase}' to continue: ").strip()
    if entered != phrase:
        password = ""
        raise ProvisioningError("Explicit confirmation did not match; no changes applied.")

    try:
        with db_engine.connect().execution_options(isolation_level="SERIALIZABLE") as conn:
            transaction = conn.begin()
            try:
                # This must be the first SQL statement in the final transaction so
                # PostgreSQL establishes its SERIALIZABLE snapshot only after the lock.
                _lock_users_for_apply(conn)
                final_plan = build_plan(conn)
                if not plan_is_apply_safe(final_plan):
                    raise ProvisioningError(
                        "Apply blocked: final plan is not entirely READY/ALREADY_EXISTS."
                    )
                if _plan_signature(final_plan) != _plan_signature(initial_plan):
                    raise ProvisioningError(
                        "Provisioning plan changed before apply; retry dry-run."
                    )
                created_ids = provision_ready_rows(
                    conn,
                    final_plan,
                    password,
                    lock_users=False,
                )
                transaction.commit()
            except Exception:
                if transaction.is_active:
                    transaction.rollback()
                raise
    finally:
        password = ""  # drop the plaintext reference before output or propagation
    print(f"Created {len(created_ids)} user account(s).")
    return 0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Idempotently diagnose or create users for the approved 12-person HR roster. "
            "Apply reads the shared password only with getpass."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Diagnose only; never write data.")
    mode.add_argument("--apply", action="store_true", help="Create only READY users atomically.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return run_apply() if args.apply else run_dry_run()
    except ProvisioningError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR: provisioning failed safely ({type(exc).__name__}).", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
