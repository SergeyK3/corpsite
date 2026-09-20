"""Event-only organisational visibility for the personnel event journal."""
from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.org_scope.resolver import resolve_subtree_unit_ids

SCOPE_TYPES = frozenset({"ORGANIZATION", "DEPARTMENT", "DEPARTMENT_GROUP"})


def _table_exists(conn: Connection) -> bool:
    return conn.execute(text("""
        SELECT 1 FROM information_schema.tables
        WHERE table_schema='public' AND table_name='personnel_event_visibility_assignments'
    """)).first() is not None


def _validate_scope(
    conn: Connection,
    *,
    scope_type: str,
    scope_department_id: Optional[int],
    scope_department_group_id: Optional[int],
) -> None:
    if scope_type not in SCOPE_TYPES:
        raise ValueError(f"Invalid event visibility scope_type: {scope_type}")
    if scope_type == "ORGANIZATION":
        if scope_department_id is not None or scope_department_group_id is not None:
            raise ValueError("ORGANIZATION event scope cannot have a department or group")
        return
    if scope_type == "DEPARTMENT":
        if scope_department_id is None:
            raise ValueError("scope_department_id is required for DEPARTMENT event scope")
        exists = conn.execute(text("SELECT 1 FROM public.org_units WHERE unit_id=:id"), {"id": int(scope_department_id)}).first()
        if not exists:
            raise ValueError(f"Scope department not found: {scope_department_id}")
        return
    if scope_department_group_id is None:
        raise ValueError("scope_department_group_id is required for DEPARTMENT_GROUP event scope")
    exists = conn.execute(text("SELECT 1 FROM public.deps_group WHERE group_id=:id"), {"id": int(scope_department_group_id)}).first()
    if not exists:
        raise ValueError(f"Scope department group not found: {scope_department_group_id}")


def create_event_visibility_assignment(
    *,
    target_user_id: int,
    scope_type: str,
    scope_department_id: Optional[int] = None,
    scope_department_group_id: Optional[int] = None,
    created_by_user_id: int,
) -> Dict[str, Any]:
    """Create a direct USER journal scope; it has no PPR/personnel side effect."""
    st = (scope_type or "").strip().upper()
    with engine.begin() as conn:
        if not _table_exists(conn):
            raise RuntimeError("personnel_event_visibility_assignments table is not available")
        if not conn.execute(text("SELECT 1 FROM public.users WHERE user_id=:id"), {"id": int(target_user_id)}).first():
            raise ValueError(f"User not found: {target_user_id}")
        _validate_scope(
            conn,
            scope_type=st,
            scope_department_id=scope_department_id,
            scope_department_group_id=scope_department_group_id,
        )
        row = conn.execute(text("""
            INSERT INTO public.personnel_event_visibility_assignments(
              target_user_id, scope_type, scope_department_id, scope_department_group_id, created_by_user_id
            ) VALUES (:user_id, :scope_type, :department_id, :group_id, :actor_id)
            RETURNING assignment_id, target_user_id, scope_type, scope_department_id,
                      scope_department_group_id, is_active, created_at
        """), {
            "user_id": int(target_user_id), "scope_type": st,
            "department_id": int(scope_department_id) if scope_department_id is not None else None,
            "group_id": int(scope_department_group_id) if scope_department_group_id is not None else None,
            "actor_id": int(created_by_user_id),
        }).mappings().one()
    return dict(row)


def resolve_event_visibility_scope(user_id: int, *, include_inactive: bool = False) -> Dict[str, Any]:
    """Return ``None`` unit ids for organization-wide, otherwise the merged event scope."""
    with engine.connect() as conn:
        if not _table_exists(conn):
            return {"has_event_visibility": False, "scope_unit_ids": [], "assignment_ids": []}
        rows = conn.execute(text("""
            SELECT assignment_id, scope_type, scope_department_id, scope_department_group_id
            FROM public.personnel_event_visibility_assignments
            WHERE target_user_id=:user_id AND is_active=TRUE
            ORDER BY assignment_id
        """), {"user_id": int(user_id)}).mappings().all()
        if not rows:
            return {"has_event_visibility": False, "scope_unit_ids": [], "assignment_ids": []}
        assignment_ids = [int(row["assignment_id"]) for row in rows]
        if any(str(row["scope_type"]).upper() == "ORGANIZATION" for row in rows):
            return {"has_event_visibility": True, "scope_unit_ids": None, "assignment_ids": assignment_ids}
        unit_ids: set[int] = set()
        for row in rows:
            scope_type = str(row["scope_type"]).upper()
            if scope_type == "DEPARTMENT" and row["scope_department_id"] is not None:
                unit_ids.update(resolve_subtree_unit_ids(conn, root_unit_id=int(row["scope_department_id"]), include_inactive=include_inactive))
            elif scope_type == "DEPARTMENT_GROUP" and row["scope_department_group_id"] is not None:
                group_rows = conn.execute(text("""
                    SELECT unit_id FROM public.org_units
                    WHERE group_id=:group_id AND (:include_inactive OR COALESCE(is_active, TRUE)=TRUE)
                """), {"group_id": int(row["scope_department_group_id"]), "include_inactive": bool(include_inactive)}).scalars().all()
                unit_ids.update(int(value) for value in group_rows)
    return {"has_event_visibility": bool(unit_ids), "scope_unit_ids": sorted(unit_ids), "assignment_ids": assignment_ids}
