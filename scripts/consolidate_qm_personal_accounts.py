#!/usr/bin/env python3
"""Atomically consolidate the approved local QM legacy accounts.

Without ``--execute`` this performs the same locked preflight only.  The
script never reads or prints password hashes, Google identifiers, tokens, or
contacts.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.engine import engine
from app.services.security_audit_service import write_security_event


TARGETS = {
    1246: (13, "EMPLOYEE", "QM_AMB"),
    1247: (15, "EMPLOYEE", "QM_COMPLAINT_PAT"),
}
LEGACY = {5: "QM_AMB", 3: "QM_COMPLAINT_PAT"}
USER_IDS = [3, 5, 1246, 1247]
AUDIT_TABLES = {
    "audit_log",
    "security_audit_log",
    "task_audit_log",
    "employee_onboarding_task_audit",
    "employee_termination_record_audit",
    "incoming_document_audit",
    "operational_order_draft_audit",
    "operational_order_lifecycle_audit",
    "personnel_application_lifecycle_audit",
    "personnel_application_resolution_audit",
    "personnel_order_lifecycle_audit",
    "hr_sync_audit_log",
    "hr_import_identity_review_events",
    "ppr_section_manual_correction_events",
}


def _non_audit_dependencies(conn: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    inspector = inspect(conn)
    for table in inspector.get_table_names(schema="public"):
        if table in AUDIT_TABLES or "audit" in table:
            continue
        for foreign_key in inspector.get_foreign_keys(table, schema="public"):
            columns = foreign_key.get("constrained_columns") or []
            if foreign_key.get("referred_table") != "users" or len(columns) != 1:
                continue
            column = columns[0]
            rows = conn.execute(
                text(
                    f"SELECT {column} AS user_id, COUNT(*) AS row_count "
                    f"FROM public.{table} WHERE {column} = ANY(:user_ids) "
                    f"GROUP BY {column}"
                ),
                {"user_ids": USER_IDS},
            ).mappings().all()
            if rows:
                found.append({"table": table, "column": column})
    return found


def _preflight(conn: Any) -> tuple[dict[str, dict[str, Any]], dict[int, dict[str, Any]], list[dict[str, Any]]]:
    role_rows = conn.execute(
        text(
            """
            SELECT role_id, code, is_active
            FROM public.roles
            WHERE code IN ('EMPLOYEE', 'QM_AMB', 'QM_COMPLAINT_PAT')
            FOR UPDATE
            """
        )
    ).mappings().all()
    roles = {str(row["code"]): dict(row) for row in role_rows}
    if set(roles) != {"EMPLOYEE", "QM_AMB", "QM_COMPLAINT_PAT"} or not all(
        bool(row["is_active"]) for row in roles.values()
    ):
        raise RuntimeError("Required active roles are missing.")

    rows = conn.execute(
        text(
            """
            SELECT u.user_id, u.login, u.employee_id, u.role_id, u.is_active,
                   u.password_hash, u.google_login, u.token_version, r.code AS role_code
            FROM public.users u
            JOIN public.roles r ON r.role_id = u.role_id
            WHERE u.user_id = ANY(:user_ids)
            ORDER BY u.user_id
            FOR UPDATE
            """
        ),
        {"user_ids": USER_IDS},
    ).mappings().all()
    if len(rows) != 4:
        raise RuntimeError("One or more consolidation users are missing.")
    users = {int(row["user_id"]): dict(row) for row in rows}

    for user_id, (employee_id, old_role, _) in TARGETS.items():
        row = users[user_id]
        if row["employee_id"] != employee_id or row["role_code"] != old_role or not row["is_active"]:
            raise RuntimeError(f"User {user_id} no longer matches the approved target state.")
        linked_users = conn.execute(
            text("SELECT user_id FROM public.users WHERE employee_id = :employee_id FOR UPDATE"),
            {"employee_id": employee_id},
        ).scalars().all()
        if linked_users != [user_id]:
            raise RuntimeError(f"Employee {employee_id} is not uniquely linked to User {user_id}.")

    for user_id, role_code in LEGACY.items():
        row = users[user_id]
        if row["employee_id"] is not None or row["role_code"] != role_code or not row["is_active"]:
            raise RuntimeError(f"Legacy User {user_id} no longer matches the approved target state.")

    occupant_rows = conn.execute(
        text(
            """
            SELECT r.code, u.user_id
            FROM public.roles r
            JOIN public.users u ON u.role_id = r.role_id AND u.is_active = TRUE
            WHERE r.code IN ('QM_AMB', 'QM_COMPLAINT_PAT')
            ORDER BY r.code, u.user_id
            FOR UPDATE OF u
            """
        )
    ).mappings().all()
    occupants: dict[str, list[int]] = {}
    for row in occupant_rows:
        occupants.setdefault(str(row["code"]), []).append(int(row["user_id"]))
    if occupants != {
        "QM_AMB": [5],
        "QM_COMPLAINT_PAT": [3],
    }:
        raise RuntimeError("Unexpected active User occupies a target QM role.")

    direct_grants = [
        dict(row)
        for row in conn.execute(
            text(
                """
                SELECT grant_id, target_type, target_id
                FROM public.access_grants
                WHERE target_type = 'USER' AND target_id = ANY(:user_ids)
                ORDER BY grant_id
                FOR UPDATE
                """
            ),
            {"user_ids": USER_IDS},
        ).mappings().all()
    ]
    if _non_audit_dependencies(conn):
        raise RuntimeError("New non-audit User dependencies appeared; refusing consolidation.")
    return roles, users, direct_grants


def consolidate(*, execute: bool) -> dict[str, Any]:
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            roles, before, grants_before = _preflight(conn)
            if not execute:
                transaction.rollback()
                return {"status": "dry_run_ok", "active_legacy_users": [3, 5]}

            for user_id, (employee_id, old_role, new_role) in TARGETS.items():
                conn.execute(
                    text("UPDATE public.users SET role_id = :role_id WHERE user_id = :user_id"),
                    {"role_id": int(roles[new_role]["role_id"]), "user_id": user_id},
                )
                conn.execute(
                    text(
                        """
                        INSERT INTO public.audit_log (actor_user_id, entity, entity_id, action, before_data, after_data)
                        VALUES (NULL, 'users', :user_id, 'QM_ROLE_CONSOLIDATED',
                                CAST(:before_data AS jsonb), CAST(:after_data AS jsonb))
                        """
                    ),
                    {
                        "user_id": user_id,
                        "before_data": json.dumps({"role_code": old_role}),
                        "after_data": json.dumps(
                            {"role_code": new_role, "reason": "qm_personal_account_consolidation"}
                        ),
                    },
                )
                write_security_event(
                    event_type="ACCESS_CHANGED",
                    target_user_id=user_id,
                    target_employee_id=employee_id,
                    metadata={
                        "action": "qm_personal_account_consolidation",
                        "from_role_code": old_role,
                        "to_role_code": new_role,
                    },
                    conn=conn,
                )

            for user_id, role_code in LEGACY.items():
                conn.execute(
                    text(
                        """
                        UPDATE public.users
                        SET is_active = FALSE, token_version = token_version + 1
                        WHERE user_id = :user_id
                        """
                    ),
                    {"user_id": user_id},
                )
                conn.execute(
                    text(
                        """
                        INSERT INTO public.audit_log (actor_user_id, entity, entity_id, action, before_data, after_data)
                        VALUES (NULL, 'users', :user_id, 'QM_LEGACY_ACCOUNT_RETIRED',
                                CAST(:before_data AS jsonb), CAST(:after_data AS jsonb))
                        """
                    ),
                    {
                        "user_id": user_id,
                        "before_data": json.dumps({"role_code": role_code, "is_active": True}),
                        "after_data": json.dumps(
                            {
                                "role_code": role_code,
                                "is_active": False,
                                "reason": "qm_personal_account_consolidation",
                            }
                        ),
                    },
                )
                write_security_event(
                    event_type="USER_BLOCKED",
                    target_user_id=user_id,
                    metadata={
                        "action": "qm_legacy_account_retired",
                        "role_code": role_code,
                        "reason": "qm_personal_account_consolidation",
                    },
                    conn=conn,
                )

            after_rows = conn.execute(
                text(
                    """
                    SELECT u.user_id, u.login, u.employee_id, u.is_active,
                           u.password_hash, u.google_login, u.token_version, r.code AS role_code
                    FROM public.users u JOIN public.roles r ON r.role_id = u.role_id
                    WHERE u.user_id = ANY(:user_ids)
                    """
                ),
                {"user_ids": USER_IDS},
            ).mappings().all()
            after = {int(row["user_id"]): dict(row) for row in after_rows}
            for user_id in USER_IDS:
                for protected_column in ("login", "password_hash", "employee_id", "google_login"):
                    if after[user_id][protected_column] != before[user_id][protected_column]:
                        raise RuntimeError(f"Protected data changed for User {user_id}.")
            for user_id, (_, _, new_role) in TARGETS.items():
                if after[user_id]["role_code"] != new_role or not after[user_id]["is_active"]:
                    raise RuntimeError(f"Target User {user_id} postcondition failed.")
            for user_id in LEGACY:
                if after[user_id]["is_active"] or after[user_id]["token_version"] != before[user_id]["token_version"] + 1:
                    raise RuntimeError(f"Legacy User {user_id} postcondition failed.")

            grants_after = [
                dict(row)
                for row in conn.execute(
                    text(
                        """
                        SELECT grant_id, target_type, target_id FROM public.access_grants
                        WHERE target_type = 'USER' AND target_id = ANY(:user_ids)
                        ORDER BY grant_id
                        """
                    ),
                    {"user_ids": USER_IDS},
                ).mappings().all()
            ]
            if grants_after != grants_before:
                raise RuntimeError("Direct User grants changed unexpectedly.")
            if _non_audit_dependencies(conn):
                raise RuntimeError("New non-audit User dependencies appeared before commit.")

            final_rows = conn.execute(
                text(
                    """
                    SELECT r.code, array_agg(u.user_id ORDER BY u.user_id) AS user_ids
                    FROM public.roles r JOIN public.users u ON u.role_id = r.role_id AND u.is_active = TRUE
                    WHERE r.code IN ('QM_AMB', 'QM_COMPLAINT_PAT')
                    GROUP BY r.code ORDER BY r.code
                    """
                )
            ).mappings().all()
            active_role_users = {str(row["code"]): list(row["user_ids"]) for row in final_rows}
            if active_role_users != {"QM_AMB": [1246], "QM_COMPLAINT_PAT": [1247]}:
                raise RuntimeError("Final active QM role uniqueness check failed.")
            transaction.commit()
            return {
                "status": "committed",
                "active_qm_role_users": active_role_users,
                "retired_legacy_user_ids": [3, 5],
                "generic_audit_events": 4,
                "security_audit_events": 4,
            }
        except Exception:
            transaction.rollback()
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Commit the approved local consolidation.")
    args = parser.parse_args()
    print(json.dumps(consolidate(execute=bool(args.execute)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
