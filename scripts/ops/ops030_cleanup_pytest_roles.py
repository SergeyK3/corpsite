#!/usr/bin/env python3
"""OPS-030 — audit and optionally delete unused pytest_* Platform Roles.

Usage (from repo root):

  ./venv/bin/python scripts/ops/ops030_cleanup_pytest_roles.py audit
  ./venv/bin/python scripts/ops/ops030_cleanup_pytest_roles.py cleanup --apply

Default mode is audit-only (no deletes). Roles referenced by users, regular_tasks, or tasks
are reported as blocked and never deleted automatically.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.config  # noqa: F401
from sqlalchemy import text

from app.db.engine import engine


def _table_exists(conn, table: str) -> bool:
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


def _count_users(conn, role_id: int) -> int:
    if not _table_exists(conn, "users"):
        return 0
    return int(
        conn.execute(
            text("SELECT COUNT(*) FROM public.users WHERE role_id = :rid"),
            {"rid": int(role_id)},
        ).scalar_one()
    )


def _count_regular_tasks_refs(conn, role_id: int) -> int:
    if not _table_exists(conn, "regular_tasks"):
        return 0
    cols = {
        r[0]
        for r in conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'regular_tasks'
                """
            )
        ).fetchall()
    }
    parts: list[str] = []
    for col in ("initiator_role_id", "target_role_id", "executor_role_id"):
        if col in cols:
            parts.append(f"{col} = :rid")
    if not parts:
        return 0
    where = " OR ".join(parts)
    return int(
        conn.execute(
            text(f"SELECT COUNT(*) FROM public.regular_tasks WHERE {where}"),
            {"rid": int(role_id)},
        ).scalar_one()
    )


def _count_tasks_refs(conn, role_id: int) -> int:
    if not _table_exists(conn, "tasks"):
        return 0
    cols = {
        r[0]
        for r in conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'tasks'
                """
            )
        ).fetchall()
    }
    if "executor_role_id" not in cols:
        return 0
    return int(
        conn.execute(
            text("SELECT COUNT(*) FROM public.tasks WHERE executor_role_id = :rid"),
            {"rid": int(role_id)},
        ).scalar_one()
    )


def audit_pytest_roles() -> dict[str, Any]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT role_id, code, name
                FROM public.roles
                WHERE lower(COALESCE(code, '')) LIKE 'pytest\\_%' ESCAPE '\\'
                   OR lower(COALESCE(name, '')) LIKE 'pytest\\_%' ESCAPE '\\'
                ORDER BY role_id
                """
            )
        ).mappings().all()

        items: list[dict[str, Any]] = []
        for row in rows:
            role_id = int(row["role_id"])
            users = _count_users(conn, role_id)
            rt_refs = _count_regular_tasks_refs(conn, role_id)
            task_refs = _count_tasks_refs(conn, role_id)
            blocked = users > 0 or rt_refs > 0 or task_refs > 0
            items.append(
                {
                    "role_id": role_id,
                    "code": row.get("code"),
                    "name": row.get("name"),
                    "users_count": users,
                    "regular_tasks_refs": rt_refs,
                    "tasks_refs": task_refs,
                    "deletable": not blocked,
                    "blocked_reason": (
                        None
                        if not blocked
                        else {
                            "users_count": users,
                            "regular_tasks_refs": rt_refs,
                            "tasks_refs": task_refs,
                        }
                    ),
                }
            )

    return {
        "total_pytest_roles": len(items),
        "deletable_count": sum(1 for i in items if i["deletable"]),
        "blocked_count": sum(1 for i in items if not i["deletable"]),
        "items": items,
    }


def cleanup_pytest_roles(*, apply: bool) -> dict[str, Any]:
    report = audit_pytest_roles()
    deleted: list[int] = []
    if apply:
        with engine.begin() as conn:
            for item in report["items"]:
                if not item["deletable"]:
                    continue
                conn.execute(
                    text("DELETE FROM public.roles WHERE role_id = :rid"),
                    {"rid": int(item["role_id"])},
                )
                deleted.append(int(item["role_id"]))
    report["deleted_role_ids"] = deleted
    report["apply"] = apply
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="OPS-030 pytest_* roles audit/cleanup")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("audit", help="Report pytest_* roles and usage (default safe mode)")
    cleanup_parser = sub.add_parser("cleanup", help="Delete unused pytest_* roles")
    cleanup_parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform deletes (default is dry-run report only)",
    )
    args = parser.parse_args()

    if args.command == "audit":
        payload = audit_pytest_roles()
    else:
        payload = cleanup_pytest_roles(apply=bool(args.apply))

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
