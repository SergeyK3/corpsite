#!/usr/bin/env python3
"""Atomically provision neutral local EMPLOYEE accounts from explicit inputs."""
from __future__ import annotations

import argparse
import getpass
import json
import re
import sys
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
from app.services.security_audit_service import write_security_event


ROLE_CODE = "EMPLOYEE"
_LOGIN_RE = re.compile(r"[a-z0-9._-]{1,200}\Z")


@dataclass(frozen=True)
class AccountSpec:
    employee_id: int
    login: str


def _norm_login(value: str) -> str:
    return "".join(value.split()).casefold()


def parse_account_spec(raw: str) -> AccountSpec:
    """Parse one safe ``employee_id:login`` parameter without guessing data."""
    employee_raw, separator, login = str(raw or "").partition(":")
    if not separator or not employee_raw.isdecimal() or int(employee_raw) < 1:
        raise ValueError("account must be employee_id:login with a positive numeric employee_id")
    if not _LOGIN_RE.fullmatch(login):
        raise ValueError("login must use only lowercase a-z, 0-9, dot, underscore, or hyphen")
    return AccountSpec(employee_id=int(employee_raw), login=login)


def parse_account_specs(raw_specs: Sequence[str]) -> tuple[AccountSpec, ...]:
    specs = tuple(parse_account_spec(raw) for raw in raw_specs)
    if not specs:
        raise ValueError("at least one --account employee_id:login is required")
    employee_ids = [spec.employee_id for spec in specs]
    logins = [_norm_login(spec.login) for spec in specs]
    if len(employee_ids) != len(set(employee_ids)):
        raise ValueError("each employee_id may appear only once")
    if len(logins) != len(set(logins)):
        raise ValueError("each login may appear only once, ignoring case and whitespace")
    return specs


def _audit(conn: Any, *, user_id: int, employee_id: int, login: str) -> int:
    return int(
        conn.execute(
            text(
                """
                INSERT INTO public.audit_log (
                    actor_user_id, entity, entity_id, action, before_data, after_data
                ) VALUES (
                    NULL, 'users', :user_id, 'USER_CREATED_APPROVED',
                    CAST(:before_data AS jsonb), CAST(:after_data AS jsonb)
                )
                RETURNING audit_id
                """
            ),
            {
                "user_id": int(user_id),
                "before_data": "{}",
                "after_data": json.dumps(
                    {
                        "employee_id": int(employee_id),
                        "login": login,
                        "role_code": ROLE_CODE,
                        "source": "explicit_local_employee_provisioning",
                    }
                ),
            },
        ).scalar_one()
    )


def _has_any_effective_allow_grant(conn: Any, *, employee: dict[str, Any], role_id: int) -> bool:
    """Fail closed: a neutral EMPLOYEE account must start with implicit NONE."""
    return conn.execute(
        text(
            """
            WITH subjects(target_type, target_id) AS (
                VALUES
                    ('ROLE'::text, CAST(:role_id AS bigint)),
                    ('EMPLOYEE'::text, CAST(:employee_id AS bigint)),
                    ('PERSON'::text, CAST(:person_id AS bigint)),
                    ('ORG_UNIT'::text, CAST(:org_unit_id AS bigint))
                UNION ALL
                SELECT 'ASSIGNMENT', pa.assignment_id
                FROM public.person_assignments pa
                WHERE pa.person_id = :person_id
                  AND pa.active_flag = TRUE
                  AND pa.lifecycle_status = 'active'
                UNION ALL
                SELECT 'POSITION', pa.position_id
                FROM public.person_assignments pa
                WHERE pa.person_id = :person_id
                  AND pa.active_flag = TRUE
                  AND pa.lifecycle_status = 'active'
                  AND pa.position_id IS NOT NULL
            )
            SELECT 1
            FROM public.access_grants g
            JOIN public.access_roles ar ON ar.access_role_id = g.access_role_id
            JOIN subjects s ON s.target_type = g.target_type AND s.target_id = g.target_id
            WHERE g.active_flag = TRUE
              AND g.revoked_at IS NULL
              AND g.starts_at <= statement_timestamp()
              AND (g.ends_at IS NULL OR g.ends_at > statement_timestamp())
              AND ar.is_active = TRUE
              AND ar.access_level <> 'NONE'
            LIMIT 1
            """
        ),
        {
            "role_id": int(role_id),
            "employee_id": int(employee["employee_id"]),
            "person_id": int(employee["person_id"]),
            "org_unit_id": int(employee["org_unit_id"]),
        },
    ).first() is not None


def _preflight(conn: Any, specs: Sequence[AccountSpec]) -> tuple[int, list[tuple[dict[str, Any], str]]]:
    role = conn.execute(
        text(
            """
            SELECT role_id FROM public.roles
            WHERE code = :code AND is_active = TRUE
            FOR UPDATE
            """
        ),
        {"code": ROLE_CODE},
    ).mappings().one_or_none()
    if role is None:
        raise RuntimeError("Active EMPLOYEE Platform Role is missing.")
    role_id = int(role["role_id"])

    employees: list[tuple[dict[str, Any], str]] = []
    for spec in specs:
        employee = conn.execute(
            text(
                """
                SELECT employee_id, full_name, person_id, org_unit_id, is_active, operational_status
                FROM public.employees
                WHERE employee_id = :employee_id
                FOR UPDATE
                """
            ),
            {"employee_id": spec.employee_id},
        ).mappings().one_or_none()
        if employee is None:
            raise RuntimeError(f"Employee {spec.employee_id} is missing.")
        employee = dict(employee)
        if (
            not employee["is_active"]
            or str(employee["operational_status"] or "").casefold() != "active"
            or employee["person_id"] is None
            or employee["org_unit_id"] is None
        ):
            raise RuntimeError(f"Employee {spec.employee_id} is not eligible for account creation.")
        if conn.execute(
            text("SELECT 1 FROM public.users WHERE employee_id = :employee_id FOR UPDATE"),
            {"employee_id": spec.employee_id},
        ).first():
            raise RuntimeError(f"Employee {spec.employee_id} already has a User.")
        if conn.execute(
            text(
                """
                SELECT 1 FROM public.users
                WHERE regexp_replace(lower(coalesce(login, '')), '\\s+', '', 'g') = :login
                FOR UPDATE
                """
            ),
            {"login": _norm_login(spec.login)},
        ).first():
            raise RuntimeError(f"Login conflict for {spec.login!r}.")
        if _has_any_effective_allow_grant(conn, employee=employee, role_id=role_id):
            raise RuntimeError(
                f"Employee {spec.employee_id} would receive an access grant; refusing non-neutral provisioning."
            )
        employees.append((employee, spec.login))
    return role_id, employees


def provision(*, specs: Sequence[AccountSpec], password: str | None, dry_run: bool) -> dict[str, Any]:
    """Preflight and, unless dry-run, create all requested accounts atomically."""
    if not dry_run and (password is None or not 8 <= len(password) <= 200):
        raise ValueError("Password length must be 8..200 characters.")

    with engine.begin() as conn:
        role_id, employees = _preflight(conn, specs)
        if dry_run:
            return {
                "status": "dry_run_ok",
                "role_code": ROLE_CODE,
                "accounts": [
                    {"employee_id": int(employee["employee_id"]), "login": login}
                    for employee, login in employees
                ],
            }

        created: list[dict[str, Any]] = []
        for employee, login in employees:
            user_id = int(
                conn.execute(
                    text(
                        """
                        INSERT INTO public.users (
                            full_name, google_login, role_id, unit_id, is_active,
                            login, password_hash, employee_id
                        ) VALUES (
                            :full_name, :login, :role_id, :unit_id, TRUE,
                            :login, :password_hash, :employee_id
                        ) RETURNING user_id
                        """
                    ),
                    {
                        "full_name": str(employee["full_name"]),
                        "login": login,
                        "role_id": role_id,
                        "unit_id": int(employee["org_unit_id"]),
                        "password_hash": hash_password(password or ""),
                        "employee_id": int(employee["employee_id"]),
                    },
                ).scalar_one()
            )
            audit_id = _audit(conn, user_id=user_id, employee_id=int(employee["employee_id"]), login=login)
            security_audit_id = write_security_event(
                event_type="USER_EMPLOYEE_LINKED",
                target_user_id=user_id,
                target_employee_id=int(employee["employee_id"]),
                metadata={"link_source": "explicit_local_employee_provisioning"},
                conn=conn,
            )
            if security_audit_id is None:
                raise RuntimeError("Security audit log is unavailable.")
            created.append(
                {
                    "employee_id": int(employee["employee_id"]),
                    "user_id": user_id,
                    "login": login,
                    "audit_id": audit_id,
                    "security_audit_id": int(security_audit_id),
                }
            )
    return {"status": "committed", "role_code": ROLE_CODE, "accounts": created}


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Provision neutral EMPLOYEE accounts in one transaction.")
    parser.add_argument(
        "--account",
        action="append",
        required=True,
        metavar="EMPLOYEE_ID:LOGIN",
        help="repeatable explicit account target; role is always EMPLOYEE",
    )
    parser.add_argument("--dry-run", action="store_true", help="preflight only; never asks for a password or writes")
    args = parser.parse_args(argv)
    try:
        specs = parse_account_specs(args.account)
    except ValueError as exc:
        parser.error(str(exc))

    password: str | None = None
    if not args.dry_run:
        # Exactly one interactive request; no command-line or file password input exists.
        password = getpass.getpass("Temporary password for all requested EMPLOYEE accounts: ")
    print(json.dumps(provision(specs=specs, password=password, dry_run=bool(args.dry_run)), ensure_ascii=False))


if __name__ == "__main__":
    main()
