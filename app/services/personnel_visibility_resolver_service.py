"""ADR-042 Phase E1 — effective personnel visibility resolver."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.org_scope.resolver import resolve_subtree_unit_ids
from app.security.directory_scope import is_privileged as _is_privileged
from app.services.access_resolver_service import resolve_effective_access

ACCESS_LEVELS_WITH_IMPLICIT_VISIBILITY = frozenset({"MANAGER", "ADMIN"})


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


def _fetch_user_context(conn: Connection, user_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT
                u.user_id,
                u.role_id,
                u.unit_id,
                u.employee_id,
                e.person_id
            FROM public.users u
            LEFT JOIN public.employees e ON e.employee_id = u.employee_id
            WHERE u.user_id = :user_id
            LIMIT 1
            """
        ),
        {"user_id": int(user_id)},
    ).mappings().first()
    return dict(row) if row else None


def _collect_user_position_ids(conn: Connection, *, user_id: int, person_id: Optional[int]) -> Set[int]:
    ids: Set[int] = set()
    if person_id is not None:
        rows = conn.execute(
            text(
                """
                SELECT DISTINCT pa.position_id
                FROM public.person_assignments pa
                WHERE pa.person_id = :person_id
                  AND pa.active_flag = TRUE
                  AND pa.lifecycle_status = 'active'
                  AND pa.position_id IS NOT NULL
                """
            ),
            {"person_id": int(person_id)},
        ).mappings().all()
        for r in rows:
            if r["position_id"] is not None:
                ids.add(int(r["position_id"]))
    return ids


def _load_matching_assignments(
    conn: Connection,
    *,
    user_id: int,
    unit_id: Optional[int],
    position_ids: Set[int],
) -> List[Dict[str, Any]]:
    if not _table_exists(conn, "personnel_visibility_assignments"):
        return []

    clauses = ["(target_type = 'USER' AND target_user_id = :user_id)"]
    params: Dict[str, Any] = {"user_id": int(user_id)}

    if unit_id is not None:
        clauses.append("(target_type = 'DEPARTMENT' AND target_department_id = :unit_id)")
        params["unit_id"] = int(unit_id)

    if position_ids:
        clauses.append("(target_type = 'POSITION' AND target_position_id = ANY(:position_ids))")
        params["position_ids"] = sorted(position_ids)

    where_targets = " OR ".join(clauses)
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
                can_view_tasks
            FROM public.personnel_visibility_assignments
            WHERE is_active = TRUE
              AND ({where_targets})
            ORDER BY assignment_id
            """
        ),
        params,
    ).mappings().all()
    return [dict(r) for r in rows]


def _resolve_scope_unit_ids(
    conn: Connection,
    assignments: List[Dict[str, Any]],
    *,
    include_inactive: bool = False,
) -> Optional[Set[int]]:
    """Return None for organization-wide; empty set if no units; otherwise merged unit ids."""
    if not assignments:
        return set()

    organization_wide = any((a.get("scope_type") or "").upper() == "ORGANIZATION" for a in assignments)
    if organization_wide:
        return None

    merged: Set[int] = set()
    for a in assignments:
        st = (a.get("scope_type") or "").upper()
        if st == "DEPARTMENT" and a.get("scope_department_id") is not None:
            dept_id = int(a["scope_department_id"])
            merged.update(resolve_subtree_unit_ids(conn, root_unit_id=dept_id, include_inactive=include_inactive))
        elif st == "DEPARTMENT_GROUP" and a.get("scope_department_group_id") is not None:
            gid = int(a["scope_department_group_id"])
            rows = conn.execute(
                text(
                    """
                    SELECT unit_id
                    FROM public.org_units
                    WHERE group_id = :gid
                    """
                ),
                {"gid": gid},
            ).mappings().all()
            for r in rows:
                merged.add(int(r["unit_id"]))

    return merged


def _empty_visibility() -> Dict[str, Any]:
    return {
        "has_visibility": False,
        "show_org_sidebar": False,
        "organization_wide": False,
        "scope_unit_ids": [],
        "can_view_personnel": False,
        "can_view_tasks": False,
        "source": "none",
        "matched_assignment_ids": [],
        "implicit_from_access_level": False,
    }


def resolve_effective_personnel_visibility(
    user_id: int,
    *,
    user_ctx: Optional[Dict[str, Any]] = None,
    include_inactive: bool = False,
) -> Dict[str, Any]:
    """Resolve merged visibility scope for a user (read-only; no action grants)."""
    with engine.connect() as conn:
        ctx = _fetch_user_context(conn, int(user_id))
        if not ctx:
            raise ValueError(f"User not found: {user_id}")

        effective_ctx = dict(user_ctx or {})
        effective_ctx.setdefault("user_id", int(user_id))
        if effective_ctx.get("role_id") is None and ctx.get("role_id") is not None:
            effective_ctx["role_id"] = int(ctx["role_id"])
        if effective_ctx.get("unit_id") is None and ctx.get("unit_id") is not None:
            effective_ctx["unit_id"] = int(ctx["unit_id"])

        privileged = _is_privileged(effective_ctx)
        if privileged:
            return {
                "has_visibility": True,
                "show_org_sidebar": True,
                "organization_wide": True,
                "scope_unit_ids": None,
                "can_view_personnel": True,
                "can_view_tasks": True,
                "source": "privileged",
                "matched_assignment_ids": [],
                "implicit_from_access_level": False,
            }

        unit_id = int(ctx["unit_id"]) if ctx.get("unit_id") is not None else None
        person_id = int(ctx["person_id"]) if ctx.get("person_id") is not None else None
        position_ids = _collect_user_position_ids(conn, user_id=int(user_id), person_id=person_id)

        assignments = _load_matching_assignments(
            conn,
            user_id=int(user_id),
            unit_id=unit_id,
            position_ids=position_ids,
        )

        if assignments:
            scope_ids = _resolve_scope_unit_ids(conn, assignments, include_inactive=include_inactive)
            can_view_personnel = any(bool(a.get("can_view_personnel", True)) for a in assignments)
            can_view_tasks = any(bool(a.get("can_view_tasks")) for a in assignments)
            org_wide = scope_ids is None
            return {
                "has_visibility": can_view_personnel,
                "show_org_sidebar": can_view_personnel,
                "organization_wide": org_wide,
                "scope_unit_ids": None if org_wide else sorted(scope_ids or []),
                "can_view_personnel": can_view_personnel,
                "can_view_tasks": can_view_tasks,
                "source": "assignment",
                "matched_assignment_ids": [int(a["assignment_id"]) for a in assignments],
                "implicit_from_access_level": False,
            }

        try:
            access = resolve_effective_access(int(user_id))
            access_level = str(access.get("access_level") or "NONE").upper()
        except Exception:
            access_level = "NONE"

        if access_level in ACCESS_LEVELS_WITH_IMPLICIT_VISIBILITY:
            return {
                "has_visibility": True,
                "show_org_sidebar": True,
                "organization_wide": access_level == "ADMIN",
                "scope_unit_ids": None if access_level == "ADMIN" else [],
                "can_view_personnel": True,
                "can_view_tasks": access_level == "ADMIN",
                "source": "access_level",
                "matched_assignment_ids": [],
                "implicit_from_access_level": True,
                "access_level": access_level,
            }

        return _empty_visibility()


def enrich_user_with_personnel_visibility(user: Dict[str, Any]) -> Dict[str, Any]:
    """Add personnel visibility fields to user context (/auth/me)."""
    out = dict(user)
    uid = int(out.get("user_id") or 0)
    if uid <= 0:
        return out

    try:
        vis = resolve_effective_personnel_visibility(uid, user_ctx=out)
    except ValueError:
        vis = _empty_visibility()

    out["has_personnel_visibility"] = bool(vis.get("has_visibility"))
    out["show_org_sidebar"] = bool(vis.get("show_org_sidebar"))
    out["personnel_visibility"] = {
        "organization_wide": bool(vis.get("organization_wide")),
        "scope_unit_ids": vis.get("scope_unit_ids"),
        "can_view_personnel": bool(vis.get("can_view_personnel")),
        "can_view_tasks": bool(vis.get("can_view_tasks")),
        "source": vis.get("source"),
        "matched_assignment_ids": vis.get("matched_assignment_ids") or [],
        "implicit_from_access_level": bool(vis.get("implicit_from_access_level")),
    }
    return out
