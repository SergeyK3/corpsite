#!/usr/bin/env python3
"""Fail-closed account alignment for existing personnel identities.

The program is intentionally local tooling.  It never connects to production
by itself and defaults to a locked dry-run.  It does not use ``contacts`` as
an identity authority: a Person link is restored only from explicitly supplied
existing Person and Employee identifiers after uniqueness and exact-name checks.
"""
from __future__ import annotations

import argparse
import getpass
import json
import re
import sys
import unicodedata
from uuid import UUID
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from dotenv import load_dotenv
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

from app.auth import hash_password
from app.db.engine import engine
from app.services.active_employee_person_card_service import (
    active_employee_person_card_preflight,
    create_active_employee_person_card_tx,
)
from app.services.security_audit_service import write_security_event


LOGIN_RE = re.compile(r"[a-z0-9._-]{1,200}\Z")

# Planning inventory only.  The script never applies these rows implicitly;
# each future rename requires an explicitly approved --rename argument.
FUTURE_QM_RENAMES: tuple[tuple[str, str], ...] = (
    ("qm_head@corp.local", "masimov.ab"),
    ("qm_hosp@corp.local", "seytkazina.gt"),
    ("qm_amb@corp.local", "akiltaeva.bs"),
    ("qm_complaint_reg@corp.local", "abdina.ak"),
    ("qm_complaint_pat@corp.local", "musabekov.ka"),
    ("qm_intern_educat@corp.local", "saparbaeva.zs"),
)


@dataclass(frozen=True)
class RenameSpec:
    user_id: int
    employee_id: int
    login: str


@dataclass(frozen=True)
class CheckedRenameSpec:
    """Rename guarded by the complete expected current identity tuple."""

    user_id: int
    employee_id: int
    old_login: str
    login: str


@dataclass(frozen=True)
class LegacyRenameSpec:
    old_login: str
    login: str


@dataclass(frozen=True)
class PersonLinkSpec:
    employee_id: int
    person_id: int


@dataclass(frozen=True)
class PersonCreateSpec:
    employee_id: int
    request_id: str


@dataclass(frozen=True)
class RoleChangeSpec:
    user_id: int
    expected_role_code: str
    new_role_code: str


@dataclass(frozen=True)
class CheckedRoleChangeSpec:
    """Role change guarded by the complete expected current identity tuple."""

    user_id: int
    employee_id: int
    old_login: str
    expected_role_code: str
    new_role_code: str


@dataclass(frozen=True)
class CreateSpec:
    employee_id: int
    login: str
    role_code: str


def _norm_name(value: str | None) -> str:
    return " ".join(unicodedata.normalize("NFKC", value or "").split()).casefold()


def _norm_login(value: str | None) -> str:
    return "".join(str(value or "").split()).casefold()


def _positive(raw: str, field: str) -> int:
    if not raw.isdecimal() or int(raw) < 1:
        raise ValueError(f"{field} must be a positive integer")
    return int(raw)


def _login(raw: str) -> str:
    if not LOGIN_RE.fullmatch(raw):
        raise ValueError("login must use lowercase a-z, 0-9, dot, underscore, or hyphen")
    return raw


def _parts(raw: str, count: int, label: str) -> list[str]:
    values = str(raw or "").split(":")
    if len(values) != count or any(not value for value in values):
        raise ValueError(f"{label} has an invalid format")
    return values


def parse_rename(raw: str) -> RenameSpec:
    user_id, employee_id, login = _parts(raw, 3, "--rename USER_ID:EMPLOYEE_ID:LOGIN")
    return RenameSpec(_positive(user_id, "user_id"), _positive(employee_id, "employee_id"), _login(login))


def parse_checked_rename(raw: str) -> CheckedRenameSpec:
    user_id, employee_id, old_login, login = _parts(
        raw,
        4,
        "--checked-rename USER_ID:EMPLOYEE_ID:OLD_LOGIN:NEW_LOGIN",
    )
    if not re.fullmatch(r"[A-Za-z0-9._@+-]{1,200}", old_login):
        raise ValueError("old login has an unsafe format")
    return CheckedRenameSpec(
        _positive(user_id, "user_id"),
        _positive(employee_id, "employee_id"),
        old_login,
        _login(login),
    )


def parse_legacy_rename(raw: str) -> LegacyRenameSpec:
    old_login, login = _parts(raw, 2, "--rename-login OLD_LOGIN:NEW_LOGIN")
    if not re.fullmatch(r"[A-Za-z0-9._@+-]{1,200}", old_login):
        raise ValueError("old login has an unsafe format")
    return LegacyRenameSpec(old_login, _login(login))


def parse_person_link(raw: str) -> PersonLinkSpec:
    employee_id, person_id = _parts(raw, 2, "--link-person EMPLOYEE_ID:PERSON_ID")
    return PersonLinkSpec(_positive(employee_id, "employee_id"), _positive(person_id, "person_id"))


def parse_person_create(raw: str) -> PersonCreateSpec:
    employee_id, request_id = _parts(raw, 2, "--create-person EMPLOYEE_ID:REQUEST_UUID")
    try:
        parsed_request_id = str(UUID(request_id))
    except ValueError as exc:
        raise ValueError("create-person request ID must be a UUID") from exc
    return PersonCreateSpec(_positive(employee_id, "employee_id"), parsed_request_id)


def parse_role_change(raw: str) -> RoleChangeSpec:
    user_id, old_code, new_code = _parts(raw, 3, "--change-role USER_ID:EXPECTED_ROLE:NEW_ROLE")
    if not re.fullmatch(r"[A-Z0-9_]{1,100}", old_code) or not re.fullmatch(r"[A-Z0-9_]{1,100}", new_code):
        raise ValueError("role codes must be uppercase platform-role codes")
    return RoleChangeSpec(_positive(user_id, "user_id"), old_code, new_code)


def parse_checked_role_change(raw: str) -> CheckedRoleChangeSpec:
    user_id, employee_id, old_login, old_code, new_code = _parts(
        raw,
        5,
        "--checked-change-role USER_ID:EMPLOYEE_ID:CURRENT_LOGIN:OLD_ROLE:NEW_ROLE",
    )
    if not re.fullmatch(r"[A-Za-z0-9._@+-]{1,200}", old_login):
        raise ValueError("current login has an unsafe format")
    if not re.fullmatch(r"[A-Z0-9_]{1,100}", old_code) or not re.fullmatch(r"[A-Z0-9_]{1,100}", new_code):
        raise ValueError("role codes must be uppercase platform-role codes")
    return CheckedRoleChangeSpec(
        _positive(user_id, "user_id"),
        _positive(employee_id, "employee_id"),
        old_login,
        old_code,
        new_code,
    )


def parse_create(raw: str) -> CreateSpec:
    employee_id, login, role_code = _parts(raw, 3, "--create EMPLOYEE_ID:LOGIN:ROLE")
    if not re.fullmatch(r"[A-Z0-9_]{1,100}", role_code):
        raise ValueError("role code must be an uppercase platform-role code")
    return CreateSpec(_positive(employee_id, "employee_id"), _login(login), role_code)


def _unique(values: Sequence[int], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must not contain duplicates")


def _audit(conn: Any, *, user_id: int | None, employee_id: int | None, action: str, after: dict[str, Any]) -> None:
    conn.execute(
        text(
            """
            INSERT INTO public.audit_log (actor_user_id, entity, entity_id, action, before_data, after_data)
            VALUES (NULL, :entity, :entity_id, :action, CAST('{}' AS jsonb), CAST(:after_data AS jsonb))
            """
        ),
        {
            "entity": "users" if user_id is not None else "employees",
            "entity_id": int(user_id if user_id is not None else employee_id or 0),
            "action": action,
            "after_data": json.dumps(after, ensure_ascii=False),
        },
    )


def _locked_one(conn: Any, sql: str, params: dict[str, Any], missing: str) -> dict[str, Any]:
    row = conn.execute(text(sql), params).mappings().one_or_none()
    if row is None:
        raise RuntimeError(missing)
    return dict(row)


def _preflight(
    conn: Any,
    *,
    renames: Sequence[RenameSpec],
    checked_renames: Sequence[CheckedRenameSpec],
    legacy_renames: Sequence[LegacyRenameSpec],
    links: Sequence[PersonLinkSpec],
    person_creates: Sequence[PersonCreateSpec],
    role_changes: Sequence[RoleChangeSpec],
    checked_role_changes: Sequence[CheckedRoleChangeSpec],
    creates: Sequence[CreateSpec],
    actor_user_id: int | None,
) -> dict[str, Any]:
    _unique([item.user_id for item in (*renames, *checked_renames)], "rename user IDs")
    _unique([item.user_id for item in (*role_changes, *checked_role_changes)], "role-change user IDs")
    _unique([item.employee_id for item in links], "Person-link employee IDs")
    _unique([item.employee_id for item in person_creates], "Person-create employee IDs")
    _unique([item.employee_id for item in creates], "create employee IDs")
    if {item.employee_id for item in links} & {item.employee_id for item in person_creates}:
        raise RuntimeError("an Employee cannot use both existing-Person link and governance Person creation")
    if person_creates and actor_user_id is None:
        raise RuntimeError("--actor-user-id is required for governance Person creation")
    if actor_user_id is not None and actor_user_id < 1:
        raise RuntimeError("actor_user_id must be positive")
    _unique([_norm_login(item.old_login) for item in legacy_renames], "legacy login sources")
    all_logins = [_norm_login(item.login) for item in (*renames, *checked_renames, *legacy_renames, *creates)]
    if len(all_logins) != len(set(all_logins)):
        raise RuntimeError("target logins are not unique ignoring case and whitespace")
    employee_ids = {item.employee_id for item in renames} | {item.employee_id for item in checked_renames} | {item.employee_id for item in checked_role_changes} | {item.employee_id for item in links} | {item.employee_id for item in person_creates} | {item.employee_id for item in creates}
    person_ids = {item.person_id for item in links}
    user_ids = {item.user_id for item in renames} | {item.user_id for item in checked_renames} | {item.user_id for item in role_changes} | {item.user_id for item in checked_role_changes}
    resolved_legacy: list[dict[str, Any]] = []
    for item in legacy_renames:
        rows = conn.execute(
            text("""SELECT u.user_id, u.employee_id, u.login, u.role_id, u.is_active, r.code AS role_code
                    FROM public.users u JOIN public.roles r ON r.role_id=u.role_id
                    WHERE regexp_replace(lower(coalesce(u.login,'')), '\\s+', '', 'g')=:login
                    FOR UPDATE OF u"""),
            {"login": _norm_login(item.old_login)},
        ).mappings().all()
        if len(rows) != 1:
            raise RuntimeError(f"Legacy login {item.old_login!r} must resolve to exactly one existing User.")
        resolved_legacy.append({"spec": item, "user": dict(rows[0])})
        user_ids.add(int(rows[0]["user_id"]))
        if rows[0]["employee_id"] is not None:
            employee_ids.add(int(rows[0]["employee_id"]))

    employees = {
        employee_id: _locked_one(
            conn,
            """SELECT employee_id, person_id, full_name, org_unit_id, is_active, operational_status
               FROM public.employees WHERE employee_id=:employee_id FOR UPDATE""",
            {"employee_id": employee_id},
            f"Employee {employee_id} is missing.",
        )
        for employee_id in sorted(employee_ids)
    }
    persons = {
        person_id: _locked_one(
            conn,
            "SELECT person_id, full_name, person_status FROM public.persons WHERE person_id=:person_id FOR UPDATE",
            {"person_id": person_id},
            f"Person {person_id} is missing.",
        )
        for person_id in sorted(person_ids)
    }
    users = {
        user_id: _locked_one(
            conn,
            """SELECT u.user_id, u.employee_id, u.login, u.role_id, u.is_active, r.code AS role_code
               FROM public.users u JOIN public.roles r ON r.role_id=u.role_id
               WHERE u.user_id=:user_id FOR UPDATE OF u""",
            {"user_id": user_id},
            f"User {user_id} is missing.",
        )
        for user_id in sorted(user_ids)
    }
    if person_creates:
        _locked_one(
            conn,
            "SELECT user_id FROM public.users WHERE user_id=:user_id FOR UPDATE",
            {"user_id": int(actor_user_id or 0)},
            f"Actor User {actor_user_id} is missing.",
        )

    for item in links:
        employee, person = employees[item.employee_id], persons[item.person_id]
        if employee["person_id"] not in (None, item.person_id):
            raise RuntimeError(f"Employee {item.employee_id} already points to another Person.")
        if str(person["person_status"]).casefold() != "active":
            raise RuntimeError(f"Person {item.person_id} is not active.")
        if _norm_name(employee["full_name"]) != _norm_name(person["full_name"]):
            raise RuntimeError(f"Employee {item.employee_id} and Person {item.person_id} do not have an exact normalized name match.")
        other = conn.execute(
            text("SELECT employee_id FROM public.employees WHERE person_id=:person_id AND employee_id<>:employee_id FOR UPDATE"),
            {"person_id": item.person_id, "employee_id": item.employee_id},
        ).scalars().all()
        if other:
            raise RuntimeError(f"Person {item.person_id} is already linked to another Employee.")

    governance_preconditions: dict[int, str] = {}
    for item in person_creates:
        employee = employees[item.employee_id]
        if employee["person_id"] is not None:
            raise RuntimeError(f"Employee {item.employee_id} already has a Person link.")
        name_candidates = conn.execute(
            text("""SELECT person_id FROM public.persons
                    WHERE lower(regexp_replace(coalesce(full_name,''), '\\s+', ' ', 'g')) = :full_name
                    FOR UPDATE"""),
            {"full_name": _norm_name(employee["full_name"])},
        ).scalars().all()
        if name_candidates:
            raise RuntimeError(f"Person candidates already exist for Employee {item.employee_id}; governance creation is refused.")
        governance = active_employee_person_card_preflight(conn, employee_id=item.employee_id)
        if not governance.get("ready") or not governance.get("expected_precondition"):
            blocker_codes = ", ".join(str(row.get("code")) for row in governance.get("blockers", []))
            raise RuntimeError(f"Employee {item.employee_id} is not ready for governance Person creation: {blocker_codes or 'unknown'}.")
        governance_preconditions[item.employee_id] = str(governance["expected_precondition"])

    created_person_employee_ids = {item.employee_id for item in person_creates}
    for item in creates:
        employee = employees[item.employee_id]
        if employee["person_id"] is None and item.employee_id not in created_person_employee_ids:
            raise RuntimeError(f"Create for Employee {item.employee_id} requires the approved Person link first.")
        if not bool(employee["is_active"]) or str(employee["operational_status"] or "").casefold() != "active":
            raise RuntimeError(f"Employee {item.employee_id} is not active.")
        if employee["org_unit_id"] is None:
            raise RuntimeError(f"Employee {item.employee_id} is not eligible for account creation.")
        linked = conn.execute(text("SELECT user_id FROM public.users WHERE employee_id=:employee_id FOR UPDATE"), {"employee_id": item.employee_id}).scalars().all()
        if linked:
            raise RuntimeError(f"Employee {item.employee_id} already has a User.")

    for item in renames:
        user = users[item.user_id]
        if user["employee_id"] != item.employee_id:
            raise RuntimeError(f"User {item.user_id} is not uniquely linked to Employee {item.employee_id}.")
        linked = conn.execute(text("SELECT user_id FROM public.users WHERE employee_id=:employee_id FOR UPDATE"), {"employee_id": item.employee_id}).scalars().all()
        if linked != [item.user_id]:
            raise RuntimeError(f"Employee {item.employee_id} has an unexpected User linkage.")

    for item in checked_renames:
        user = users[item.user_id]
        if user["employee_id"] != item.employee_id:
            raise RuntimeError(f"Checked rename: User {item.user_id} is not uniquely linked to Employee {item.employee_id}.")
        if user["login"] != item.old_login:
            raise RuntimeError(f"Checked rename: User {item.user_id} does not have the expected current login.")
        linked = conn.execute(text("SELECT user_id FROM public.users WHERE employee_id=:employee_id FOR UPDATE"), {"employee_id": item.employee_id}).scalars().all()
        if linked != [item.user_id]:
            raise RuntimeError(f"Employee {item.employee_id} has an unexpected User linkage.")

    for item in role_changes:
        if users[item.user_id]["role_code"] != item.expected_role_code:
            raise RuntimeError(f"User {item.user_id} no longer has expected role {item.expected_role_code}.")

    for item in checked_role_changes:
        user = users[item.user_id]
        if user["employee_id"] != item.employee_id:
            raise RuntimeError(f"Checked role change: User {item.user_id} is not directly linked to Employee {item.employee_id}.")
        if user["login"] != item.old_login:
            raise RuntimeError(f"Checked role change: User {item.user_id} does not have the expected current login.")
        if user["role_code"] != item.expected_role_code:
            raise RuntimeError(f"Checked role change: User {item.user_id} no longer has expected role {item.expected_role_code}.")
        linked = conn.execute(text("SELECT user_id FROM public.users WHERE employee_id=:employee_id FOR UPDATE"), {"employee_id": item.employee_id}).scalars().all()
        if linked != [item.user_id]:
            raise RuntimeError(f"Employee {item.employee_id} has an unexpected User linkage.")

    role_codes = {item.role_code for item in creates} | {item.new_role_code for item in (*role_changes, *checked_role_changes)}
    roles: dict[str, int] = {}
    for code in sorted(role_codes):
        role = _locked_one(conn, "SELECT role_id FROM public.roles WHERE code=:code FOR UPDATE", {"code": code}, f"Role {code} is missing.")
        roles[code] = int(role["role_id"])

    for login in all_logins:
        owners = conn.execute(
            text("""SELECT user_id FROM public.users
                    WHERE regexp_replace(lower(coalesce(login,'')), '\\s+', '', 'g')=:login
                    FOR UPDATE"""),
            {"login": login},
        ).scalars().all()
        permitted = {item.user_id for item in (*renames, *checked_renames) if _norm_login(item.login) == login}
        permitted |= {int(row["user"]["user_id"]) for row in resolved_legacy if _norm_login(row["spec"].login) == login}
        if set(owners) - permitted:
            raise RuntimeError(f"Login conflict for {login!r}.")

    return {"employees": employees, "users": users, "roles": roles, "governance_preconditions": governance_preconditions, "resolved_legacy": resolved_legacy}


def align(
    *,
    renames: Sequence[RenameSpec] = (),
    checked_renames: Sequence[CheckedRenameSpec] = (),
    legacy_renames: Sequence[LegacyRenameSpec] = (),
    links: Sequence[PersonLinkSpec] = (),
    person_creates: Sequence[PersonCreateSpec] = (),
    role_changes: Sequence[RoleChangeSpec] = (),
    checked_role_changes: Sequence[CheckedRoleChangeSpec] = (),
    creates: Sequence[CreateSpec] = (),
    actor_user_id: int | None = None,
    execute: bool = False,
    password: str | None = None,
) -> dict[str, Any]:
    """Run one locked preflight; apply all approved operations atomically only with ``execute``."""
    if not any((renames, checked_renames, legacy_renames, links, person_creates, role_changes, checked_role_changes, creates)):
        raise ValueError("at least one alignment action is required")
    if execute and creates and (password is None or not 8 <= len(password) <= 200):
        raise ValueError("Password length must be 8..200 characters.")

    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            state = _preflight(conn, renames=renames, checked_renames=checked_renames, legacy_renames=legacy_renames, links=links, person_creates=person_creates, role_changes=role_changes, checked_role_changes=checked_role_changes, creates=creates, actor_user_id=actor_user_id)
            if not execute:
                result = {
                    "status": "dry_run_ok",
                    "renames": [{"user_id": item.user_id, "employee_id": item.employee_id, "login": item.login} for item in renames],
                    "checked_renames": [{"user_id": item.user_id, "employee_id": item.employee_id, "old_login": item.old_login, "login": item.login} for item in checked_renames],
                    "legacy_renames": [{"old_login": item.old_login, "login": item.login} for item in legacy_renames],
                    "person_links": [{"employee_id": item.employee_id, "person_id": item.person_id} for item in links],
                    "person_creates": [{"employee_id": item.employee_id, "request_id": item.request_id} for item in person_creates],
                    "role_changes": [{"user_id": item.user_id, "from": item.expected_role_code, "to": item.new_role_code} for item in role_changes],
                    "checked_role_changes": [{"user_id": item.user_id, "employee_id": item.employee_id, "old_login": item.old_login, "from": item.expected_role_code, "to": item.new_role_code} for item in checked_role_changes],
                    "creates": [{"employee_id": item.employee_id, "login": item.login, "role": item.role_code} for item in creates],
                }
                transaction.rollback()
                return result

            for item in person_creates:
                result = create_active_employee_person_card_tx(
                    conn,
                    employee_id=item.employee_id,
                    expected_precondition=state["governance_preconditions"][item.employee_id],
                    request_id=item.request_id,
                    actor_user_id=int(actor_user_id or 0),
                    hr_confirmed=True,
                )
                state["employees"][item.employee_id]["person_id"] = int(result["person_id"])
                _audit(conn, user_id=None, employee_id=item.employee_id, action="EMPLOYEE_PERSON_CREATED_GOVERNANCE", after={"person_id": int(result["person_id"]), "source": "approved_account_alignment"})
                if write_security_event(event_type="ACCESS_CHANGED", target_employee_id=item.employee_id, metadata={"action": "employee_person_created_governance", "source": "approved_account_alignment"}, conn=conn) is None:
                    raise RuntimeError("Security audit log is unavailable.")

            for item in links:
                conn.execute(text("UPDATE public.employees SET person_id=:person_id WHERE employee_id=:employee_id"), {"employee_id": item.employee_id, "person_id": item.person_id})
                _audit(conn, user_id=None, employee_id=item.employee_id, action="EMPLOYEE_PERSON_LINK_RESTORED", after={"person_id": item.person_id, "source": "approved_account_alignment"})
                if write_security_event(event_type="ACCESS_CHANGED", target_employee_id=item.employee_id, metadata={"action": "employee_person_link_restored", "person_id": item.person_id, "source": "approved_account_alignment"}, conn=conn) is None:
                    raise RuntimeError("Security audit log is unavailable.")

            for item in renames:
                conn.execute(text("UPDATE public.users SET login=:login WHERE user_id=:user_id"), {"user_id": item.user_id, "login": item.login})
                _audit(conn, user_id=item.user_id, employee_id=item.employee_id, action="USER_LOGIN_RENAMED", after={"login": item.login, "source": "approved_account_alignment"})
                if write_security_event(event_type="ACCESS_CHANGED", target_user_id=item.user_id, target_employee_id=item.employee_id, metadata={"action": "user_login_renamed", "login": item.login, "source": "approved_account_alignment"}, conn=conn) is None:
                    raise RuntimeError("Security audit log is unavailable.")

            for item in checked_renames:
                conn.execute(text("UPDATE public.users SET login=:login WHERE user_id=:user_id"), {"user_id": item.user_id, "login": item.login})
                _audit(conn, user_id=item.user_id, employee_id=item.employee_id, action="USER_LOGIN_RENAMED", after={"login": item.login, "source": "approved_account_alignment"})
                if write_security_event(event_type="ACCESS_CHANGED", target_user_id=item.user_id, target_employee_id=item.employee_id, metadata={"action": "user_login_renamed", "login": item.login, "source": "approved_account_alignment"}, conn=conn) is None:
                    raise RuntimeError("Security audit log is unavailable.")

            for row in state["resolved_legacy"]:
                item, user = row["spec"], row["user"]
                user_id = int(user["user_id"])
                employee_id = int(user["employee_id"]) if user["employee_id"] is not None else None
                conn.execute(text("UPDATE public.users SET login=:login WHERE user_id=:user_id"), {"user_id": user_id, "login": item.login})
                _audit(conn, user_id=user_id, employee_id=employee_id, action="USER_LOGIN_RENAMED", after={"login": item.login, "source": "approved_account_alignment"})
                if write_security_event(event_type="ACCESS_CHANGED", target_user_id=user_id, target_employee_id=employee_id, metadata={"action": "user_login_renamed", "login": item.login, "source": "approved_account_alignment"}, conn=conn) is None:
                    raise RuntimeError("Security audit log is unavailable.")

            for item in role_changes:
                user = state["users"][item.user_id]
                conn.execute(text("UPDATE public.users SET role_id=:role_id WHERE user_id=:user_id"), {"role_id": state["roles"][item.new_role_code], "user_id": item.user_id})
                _audit(conn, user_id=item.user_id, employee_id=int(user["employee_id"]), action="USER_ROLE_ALIGNED", after={"from": item.expected_role_code, "to": item.new_role_code, "source": "approved_account_alignment"})
                if write_security_event(event_type="ACCESS_CHANGED", target_user_id=item.user_id, target_employee_id=int(user["employee_id"]), metadata={"from_role": item.expected_role_code, "to_role": item.new_role_code, "source": "approved_account_alignment"}, conn=conn) is None:
                    raise RuntimeError("Security audit log is unavailable.")

            for item in checked_role_changes:
                conn.execute(text("UPDATE public.users SET role_id=:role_id WHERE user_id=:user_id"), {"role_id": state["roles"][item.new_role_code], "user_id": item.user_id})
                _audit(conn, user_id=item.user_id, employee_id=item.employee_id, action="USER_ROLE_ALIGNED", after={"from": item.expected_role_code, "to": item.new_role_code, "source": "approved_account_alignment"})
                if write_security_event(event_type="ACCESS_CHANGED", target_user_id=item.user_id, target_employee_id=item.employee_id, metadata={"from_role": item.expected_role_code, "to_role": item.new_role_code, "source": "approved_account_alignment"}, conn=conn) is None:
                    raise RuntimeError("Security audit log is unavailable.")

            for item in creates:
                employee = state["employees"][item.employee_id]
                user_id = int(conn.execute(text("""INSERT INTO public.users (full_name, role_id, unit_id, is_active, login, password_hash, employee_id)
                    VALUES (:full_name,:role_id,:unit_id,TRUE,:login,:password_hash,:employee_id) RETURNING user_id"""), {"full_name": employee["full_name"], "role_id": state["roles"][item.role_code], "unit_id": employee["org_unit_id"], "login": item.login, "password_hash": hash_password(password or ""), "employee_id": item.employee_id}).scalar_one())
                _audit(conn, user_id=user_id, employee_id=item.employee_id, action="USER_CREATED_APPROVED", after={"login": item.login, "role": item.role_code, "source": "approved_account_alignment"})
                if write_security_event(event_type="USER_EMPLOYEE_LINKED", target_user_id=user_id, target_employee_id=item.employee_id, metadata={"role": item.role_code, "source": "approved_account_alignment"}, conn=conn) is None:
                    raise RuntimeError("Security audit log is unavailable.")

            transaction.commit()
            return {"status": "committed"}
        except Exception:
            if transaction.is_active:
                transaction.rollback()
            raise


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Locked, atomic personnel account alignment; dry-run by default.")
    parser.add_argument("--rename", action="append", default=[], metavar="USER_ID:EMPLOYEE_ID:LOGIN")
    parser.add_argument("--checked-rename", action="append", default=[], metavar="USER_ID:EMPLOYEE_ID:OLD_LOGIN:NEW_LOGIN")
    parser.add_argument("--rename-login", action="append", default=[], metavar="OLD_LOGIN:NEW_LOGIN")
    parser.add_argument("--link-person", action="append", default=[], metavar="EMPLOYEE_ID:PERSON_ID")
    parser.add_argument("--create-person", action="append", default=[], metavar="EMPLOYEE_ID:REQUEST_UUID")
    parser.add_argument("--actor-user-id", type=int, metavar="USER_ID", help="required for governance Person creation")
    parser.add_argument("--change-role", action="append", default=[], metavar="USER_ID:EXPECTED_ROLE:NEW_ROLE")
    parser.add_argument("--checked-change-role", action="append", default=[], metavar="USER_ID:EMPLOYEE_ID:CURRENT_LOGIN:OLD_ROLE:NEW_ROLE")
    parser.add_argument("--create", action="append", default=[], metavar="EMPLOYEE_ID:LOGIN:ROLE")
    execution_mode = parser.add_mutually_exclusive_group()
    execution_mode.add_argument("--dry-run", action="store_true", help="locked preflight only (default); never writes")
    execution_mode.add_argument("--execute", action="store_true", help="commit after locked preflight")
    args = parser.parse_args(argv)
    try:
        renames = tuple(parse_rename(value) for value in args.rename)
        checked_renames = tuple(parse_checked_rename(value) for value in args.checked_rename)
        legacy_renames = tuple(parse_legacy_rename(value) for value in args.rename_login)
        links = tuple(parse_person_link(value) for value in args.link_person)
        person_creates = tuple(parse_person_create(value) for value in args.create_person)
        role_changes = tuple(parse_role_change(value) for value in args.change_role)
        checked_role_changes = tuple(parse_checked_role_change(value) for value in args.checked_change_role)
        creates = tuple(parse_create(value) for value in args.create)
        password = getpass.getpass("Temporary password for newly created accounts: ") if args.execute and creates else None
        print(json.dumps(align(renames=renames, checked_renames=checked_renames, legacy_renames=legacy_renames, links=links, person_creates=person_creates, role_changes=role_changes, checked_role_changes=checked_role_changes, creates=creates, actor_user_id=args.actor_user_id, execute=bool(args.execute), password=password), ensure_ascii=False))
    except (RuntimeError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
