"""ADR-042 Phase E1 — personnel visibility assignment CRUD."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.services.security_audit_service import write_security_event

TARGET_TYPES = frozenset({"USER", "POSITION", "DEPARTMENT"})
SCOPE_TYPES = frozenset({"ORGANIZATION", "DEPARTMENT", "DEPARTMENT_GROUP"})


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


def _row_to_dict(row: Any) -> Dict[str, Any]:
    out = dict(row)
    for key in ("assignment_id", "target_user_id", "target_position_id", "target_department_id",
                "scope_department_id", "scope_department_group_id", "created_by_user_id",
                "revoked_by_user_id"):
        if out.get(key) is not None:
            out[key] = int(out[key])
    return out


def _validate_target(*, target_type: str, target_user_id: Optional[int],
                     target_position_id: Optional[int], target_department_id: Optional[int],
                     conn: Connection) -> None:
    tt = (target_type or "").strip().upper()
    if tt not in TARGET_TYPES:
        raise ValueError(f"Invalid target_type: {target_type}")

    if tt == "USER":
        if target_user_id is None:
            raise ValueError("target_user_id is required for USER target")
        row = conn.execute(
            text("SELECT 1 FROM public.users WHERE user_id = :id LIMIT 1"),
            {"id": int(target_user_id)},
        ).first()
        if not row:
            raise ValueError(f"User not found: {target_user_id}")
    elif tt == "POSITION":
        if target_position_id is None:
            raise ValueError("target_position_id is required for POSITION target")
        row = conn.execute(
            text("SELECT 1 FROM public.positions WHERE position_id = :id LIMIT 1"),
            {"id": int(target_position_id)},
        ).first()
        if not row:
            raise ValueError(f"Position not found: {target_position_id}")
    elif tt == "DEPARTMENT":
        if target_department_id is None:
            raise ValueError("target_department_id is required for DEPARTMENT target")
        row = conn.execute(
            text("SELECT 1 FROM public.org_units WHERE unit_id = :id LIMIT 1"),
            {"id": int(target_department_id)},
        ).first()
        if not row:
            raise ValueError(f"Department not found: {target_department_id}")


def _validate_scope(*, scope_type: str, scope_department_id: Optional[int],
                    scope_department_group_id: Optional[int], conn: Connection) -> None:
    st = (scope_type or "").strip().upper()
    if st not in SCOPE_TYPES:
        raise ValueError(f"Invalid scope_type: {scope_type}")

    if st == "DEPARTMENT":
        if scope_department_id is None:
            raise ValueError("scope_department_id is required for DEPARTMENT scope")
        row = conn.execute(
            text("SELECT 1 FROM public.org_units WHERE unit_id = :id LIMIT 1"),
            {"id": int(scope_department_id)},
        ).first()
        if not row:
            raise ValueError(f"Scope department not found: {scope_department_id}")
    elif st == "DEPARTMENT_GROUP":
        if scope_department_group_id is None:
            raise ValueError("scope_department_group_id is required for DEPARTMENT_GROUP scope")
        row = conn.execute(
            text("SELECT 1 FROM public.deps_group WHERE group_id = :id LIMIT 1"),
            {"id": int(scope_department_group_id)},
        ).first()
        if not row:
            raise ValueError(f"Scope department group not found: {scope_department_group_id}")


def list_visibility_assignments(
    *,
    active_only: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    with engine.connect() as conn:
        if not _table_exists(conn, "personnel_visibility_assignments"):
            return {"items": [], "total": 0, "limit": limit, "offset": offset}

        where = "WHERE is_active = TRUE" if active_only else ""
        total = int(
            conn.execute(
                text(f"SELECT COUNT(*) FROM public.personnel_visibility_assignments {where}")
            ).scalar_one()
        )
        rows = conn.execute(
            text(
                f"""
                SELECT
                    assignment_id,
                    target_type,
                    target_user_id,
                    target_position_id,
                    target_department_id,
                    scope_type,
                    scope_department_id,
                    scope_department_group_id,
                    can_view_personnel,
                    can_view_tasks,
                    is_active,
                    created_at,
                    created_by_user_id,
                    revoked_at,
                    revoked_by_user_id,
                    revoke_reason
                FROM public.personnel_visibility_assignments
                {where}
                ORDER BY created_at DESC, assignment_id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {"limit": int(limit), "offset": int(offset)},
        ).mappings().all()

    return {
        "items": [_row_to_dict(r) for r in rows],
        "total": total,
        "limit": int(limit),
        "offset": int(offset),
    }


def create_visibility_assignment(
    *,
    target_type: str,
    target_user_id: Optional[int] = None,
    target_position_id: Optional[int] = None,
    target_department_id: Optional[int] = None,
    scope_type: str,
    scope_department_id: Optional[int] = None,
    scope_department_group_id: Optional[int] = None,
    can_view_personnel: bool = True,
    can_view_tasks: bool = False,
    created_by_user_id: int,
) -> Dict[str, Any]:
    tt = (target_type or "").strip().upper()
    st = (scope_type or "").strip().upper()

    with engine.begin() as conn:
        if not _table_exists(conn, "personnel_visibility_assignments"):
            raise RuntimeError("personnel_visibility_assignments table is not available")

        _validate_target(
            target_type=tt,
            target_user_id=target_user_id,
            target_position_id=target_position_id,
            target_department_id=target_department_id,
            conn=conn,
        )
        _validate_scope(
            scope_type=st,
            scope_department_id=scope_department_id,
            scope_department_group_id=scope_department_group_id,
            conn=conn,
        )

        row = conn.execute(
            text(
                """
                INSERT INTO public.personnel_visibility_assignments (
                    target_type,
                    target_user_id,
                    target_position_id,
                    target_department_id,
                    scope_type,
                    scope_department_id,
                    scope_department_group_id,
                    can_view_personnel,
                    can_view_tasks,
                    is_active,
                    created_by_user_id
                )
                VALUES (
                    :target_type,
                    :target_user_id,
                    :target_position_id,
                    :target_department_id,
                    :scope_type,
                    :scope_department_id,
                    :scope_department_group_id,
                    :can_view_personnel,
                    :can_view_tasks,
                    TRUE,
                    :created_by_user_id
                )
                RETURNING
                    assignment_id,
                    target_type,
                    target_user_id,
                    target_position_id,
                    target_department_id,
                    scope_type,
                    scope_department_id,
                    scope_department_group_id,
                    can_view_personnel,
                    can_view_tasks,
                    is_active,
                    created_at,
                    created_by_user_id,
                    revoked_at,
                    revoked_by_user_id,
                    revoke_reason
                """
            ),
            {
                "target_type": tt,
                "target_user_id": int(target_user_id) if target_user_id is not None else None,
                "target_position_id": int(target_position_id) if target_position_id is not None else None,
                "target_department_id": int(target_department_id) if target_department_id is not None else None,
                "scope_type": st,
                "scope_department_id": int(scope_department_id) if scope_department_id is not None else None,
                "scope_department_group_id": (
                    int(scope_department_group_id) if scope_department_group_id is not None else None
                ),
                "can_view_personnel": bool(can_view_personnel),
                "can_view_tasks": bool(can_view_tasks),
                "created_by_user_id": int(created_by_user_id),
            },
        ).mappings().first()

        result = _row_to_dict(row)
        write_security_event(
            event_type="VISIBILITY_GRANTED",
            actor_user_id=int(created_by_user_id),
            target_user_id=int(target_user_id) if target_user_id is not None else None,
            metadata={
                "assignment_id": result["assignment_id"],
                "target_type": tt,
                "target_user_id": target_user_id,
                "target_position_id": target_position_id,
                "target_department_id": target_department_id,
                "scope_type": st,
                "scope_department_id": scope_department_id,
                "scope_department_group_id": scope_department_group_id,
                "can_view_personnel": can_view_personnel,
                "can_view_tasks": can_view_tasks,
            },
            conn=conn,
        )
        return result


def revoke_visibility_assignment(
    *,
    assignment_id: int,
    revoked_by_user_id: int,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    with engine.begin() as conn:
        if not _table_exists(conn, "personnel_visibility_assignments"):
            raise RuntimeError("personnel_visibility_assignments table is not available")

        existing = conn.execute(
            text(
                """
                SELECT *
                FROM public.personnel_visibility_assignments
                WHERE assignment_id = :id
                LIMIT 1
                """
            ),
            {"id": int(assignment_id)},
        ).mappings().first()
        if not existing:
            raise ValueError(f"Assignment not found: {assignment_id}")
        if not existing["is_active"]:
            return _row_to_dict(existing)

        row = conn.execute(
            text(
                """
                UPDATE public.personnel_visibility_assignments
                SET
                    is_active = FALSE,
                    revoked_at = :revoked_at,
                    revoked_by_user_id = :revoked_by_user_id,
                    revoke_reason = :revoke_reason
                WHERE assignment_id = :id
                RETURNING
                    assignment_id,
                    target_type,
                    target_user_id,
                    target_position_id,
                    target_department_id,
                    scope_type,
                    scope_department_id,
                    scope_department_group_id,
                    can_view_personnel,
                    can_view_tasks,
                    is_active,
                    created_at,
                    created_by_user_id,
                    revoked_at,
                    revoked_by_user_id,
                    revoke_reason
                """
            ),
            {
                "id": int(assignment_id),
                "revoked_at": datetime.now(timezone.utc),
                "revoked_by_user_id": int(revoked_by_user_id),
                "revoke_reason": (reason or "").strip() or None,
            },
        ).mappings().first()

        result = _row_to_dict(row)
        write_security_event(
            event_type="VISIBILITY_REVOKED",
            actor_user_id=int(revoked_by_user_id),
            target_user_id=(
                int(result["target_user_id"]) if result.get("target_user_id") is not None else None
            ),
            metadata={
                "assignment_id": result["assignment_id"],
                "reason": reason,
            },
            conn=conn,
        )
        return result
