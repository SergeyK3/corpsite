#!/usr/bin/env python3
"""ADR-042 E1 — idempotent QM pilot personnel visibility bootstrap (local).

Creates one active DEPARTMENT assignment for the QM org unit so QM users get
org sidebar / personnel directory without manual Admin UI setup.

Safe to re-run: skips insert when an equivalent active assignment exists.

Prerequisites:
  - Alembic applied (personnel_visibility_assignments table exists)
  - QM org unit present (default: unit_id=72 local expanded tree)
  - At least one sysadmin user (role_id=2) for created_by_user_id

Apply:
  ./venv/bin/python scripts/pilot/qm_personnel_visibility_bootstrap.py --yes

Optional SQL equivalent:
  docker exec -i corpsite-pg psql -U postgres -d corpsite \\
    < scripts/pilot/qm_personnel_visibility_bootstrap.sql

Not for production VPS apply (production may already have assignments).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import app.config  # noqa: F401
from app.db.engine import engine
from app.services.personnel_visibility_service import create_visibility_assignment

# Local expanded org tree: «Отдел менеджмента и качества» (QM).
# VPS pilot anchor remains unit_id=44; override via QM_PILOT_VISIBILITY_UNIT_ID if needed.
QM_PILOT_VISIBILITY_UNIT_ID = 72

TARGET_TYPE = "DEPARTMENT"
SCOPE_TYPE = "DEPARTMENT"
CAN_VIEW_PERSONNEL = True
CAN_VIEW_TASKS = True


def _table_exists(conn: Connection, table: str) -> bool:
    return (
        conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = :table
                LIMIT 1
                """
            ),
            {"table": table},
        ).first()
        is not None
    )


def find_active_qm_pilot_visibility_assignment(
    conn: Connection,
    *,
    unit_id: int = QM_PILOT_VISIBILITY_UNIT_ID,
) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT
                assignment_id,
                target_type,
                target_department_id,
                scope_type,
                scope_department_id,
                can_view_personnel,
                can_view_tasks,
                is_active
            FROM public.personnel_visibility_assignments
            WHERE is_active = TRUE
              AND target_type = :target_type
              AND target_department_id = :unit_id
              AND scope_type = :scope_type
              AND scope_department_id = :unit_id
              AND can_view_personnel = :can_view_personnel
              AND can_view_tasks = :can_view_tasks
            ORDER BY assignment_id
            LIMIT 1
            """
        ),
        {
            "target_type": TARGET_TYPE,
            "scope_type": SCOPE_TYPE,
            "unit_id": int(unit_id),
            "can_view_personnel": CAN_VIEW_PERSONNEL,
            "can_view_tasks": CAN_VIEW_TASKS,
        },
    ).mappings().first()
    return dict(row) if row else None


def count_active_qm_pilot_visibility_assignments(
    conn: Connection,
    *,
    unit_id: int = QM_PILOT_VISIBILITY_UNIT_ID,
) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.personnel_visibility_assignments
                WHERE is_active = TRUE
                  AND target_type = :target_type
                  AND target_department_id = :unit_id
                  AND scope_type = :scope_type
                  AND scope_department_id = :unit_id
                  AND can_view_personnel = :can_view_personnel
                  AND can_view_tasks = :can_view_tasks
                """
            ),
            {
                "target_type": TARGET_TYPE,
                "scope_type": SCOPE_TYPE,
                "unit_id": int(unit_id),
                "can_view_personnel": CAN_VIEW_PERSONNEL,
                "can_view_tasks": CAN_VIEW_TASKS,
            },
        ).scalar_one()
    )


def resolve_bootstrap_actor_user_id(conn: Connection) -> int:
    row = conn.execute(
        text(
            """
            SELECT user_id
            FROM public.users
            WHERE is_active = TRUE
              AND (
                lower(login) = 'admin'
                OR role_id = 2
              )
            ORDER BY CASE WHEN lower(login) = 'admin' THEN 0 ELSE 1 END, user_id
            LIMIT 1
            """
        )
    ).mappings().first()
    if not row:
        raise RuntimeError("No active sysadmin user found for visibility bootstrap")
    return int(row["user_id"])


def ensure_qm_pilot_personnel_visibility(
    *,
    unit_id: int = QM_PILOT_VISIBILITY_UNIT_ID,
    created_by_user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Ensure QM pilot visibility assignment exists. Returns created flag + assignment row."""
    with engine.connect() as conn:
        if not _table_exists(conn, "personnel_visibility_assignments"):
            raise RuntimeError(
                "personnel_visibility_assignments table is missing; run Alembic migrations first"
            )

        unit_row = conn.execute(
            text("SELECT 1 FROM public.org_units WHERE unit_id = :id LIMIT 1"),
            {"id": int(unit_id)},
        ).first()
        if not unit_row:
            return {
                "created": False,
                "skipped": True,
                "reason": f"org unit {unit_id} not found",
                "assignment_id": None,
            }

        existing = find_active_qm_pilot_visibility_assignment(conn, unit_id=unit_id)
        if existing:
            return {
                "created": False,
                "skipped": False,
                "reason": "active assignment already exists",
                "assignment_id": int(existing["assignment_id"]),
            }

        actor_id = (
            int(created_by_user_id)
            if created_by_user_id is not None
            else resolve_bootstrap_actor_user_id(conn)
        )

    created = create_visibility_assignment(
        target_type=TARGET_TYPE,
        target_department_id=int(unit_id),
        scope_type=SCOPE_TYPE,
        scope_department_id=int(unit_id),
        can_view_personnel=CAN_VIEW_PERSONNEL,
        can_view_tasks=CAN_VIEW_TASKS,
        created_by_user_id=actor_id,
    )
    return {
        "created": True,
        "skipped": False,
        "reason": "inserted",
        "assignment_id": int(created["assignment_id"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Idempotent ADR-042 E1 QM pilot personnel visibility bootstrap",
    )
    parser.add_argument(
        "--unit-id",
        type=int,
        default=QM_PILOT_VISIBILITY_UNIT_ID,
        help=f"QM org unit id (default: {QM_PILOT_VISIBILITY_UNIT_ID})",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Apply without interactive confirmation",
    )
    args = parser.parse_args()

    if not args.yes:
        answer = input(
            f"Ensure QM personnel visibility assignment for unit_id={args.unit_id}? [y/N] "
        ).strip().lower()
        if answer not in {"y", "yes"}:
            print("Aborted.")
            return 0

    result = ensure_qm_pilot_personnel_visibility(unit_id=int(args.unit_id))
    print(result)
    if result.get("skipped") and result.get("reason", "").startswith("org unit"):
        return 0
    if result.get("assignment_id") is None:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
