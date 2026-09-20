# FILE: app/directory/rbac.py
from __future__ import annotations

from typing import Any, Dict, Optional, List

from fastapi import HTTPException
from sqlalchemy import text

from app.db.engine import engine
from app.security.directory_scope import (
    rbac_mode as _rbac_mode,
    is_privileged as _is_privileged,
    require_dept_scope as _require_dept_scope,
)
from app.security.personnel_admin_guard import evaluate_personnel_admin_access
from app.security.admin_permissions import PERSONNEL_EVENTS_READ, has_admin_permission
from app.services.org_units_service import OrgUnitsService, OrgUnit

org_units = OrgUnitsService(engine)


def require_privileged_or_403(user_ctx: Dict[str, Any]) -> None:
    if not _is_privileged(user_ctx):
        raise HTTPException(status_code=403, detail="Forbidden.")


def _require_privileged_or_personnel_admin(user_ctx: Dict[str, Any], *, detail: str) -> None:
    if _is_privileged(user_ctx):
        return
    if evaluate_personnel_admin_access(user_ctx):
        return
    raise HTTPException(status_code=403, detail=detail)


def require_personnel_admin_or_403(user_ctx: Dict[str, Any]) -> None:
    """Org-wide personnel journal and HR process reads (ADR-045)."""
    _require_privileged_or_personnel_admin(
        user_ctx,
        detail="Personnel admin access required.",
    )


def require_personnel_events_read_or_403(user_ctx: Dict[str, Any]) -> None:
    """Allow the narrow journal reader without broad HR-process authority."""
    if _is_privileged(user_ctx) or evaluate_personnel_admin_access(user_ctx):
        return
    try:
        user_id = int(user_ctx["user_id"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=403, detail="Personnel events read access required.")
    if has_admin_permission(user_id, PERSONNEL_EVENTS_READ):
        return
    raise HTTPException(status_code=403, detail="Personnel events read access required.")


def resolve_personnel_events_scope_or_403(user_ctx: Dict[str, Any]) -> Optional[List[int]]:
    """Resolve journal scope without promoting an observer into PPR visibility."""
    if _is_privileged(user_ctx) or evaluate_personnel_admin_access(user_ctx):
        scope = compute_scope(int(user_ctx["user_id"]), user_ctx)
        require_personnel_visibility_or_403(user_ctx, scope)
        return scope["scope_unit_ids"]
    require_personnel_events_read_or_403(user_ctx)
    from app.services.personnel_event_visibility_service import resolve_event_visibility_scope
    scope = resolve_event_visibility_scope(int(user_ctx["user_id"]))
    if not scope.get("has_event_visibility"):
        raise HTTPException(status_code=403, detail="Personnel event visibility is not granted.")
    return scope["scope_unit_ids"]


def require_hr_import_admin_or_403(user_ctx: Dict[str, Any]) -> None:
    """HR import write actions: sysadmin/privileged operator or personnel admin (ADR-045)."""
    _require_privileged_or_personnel_admin(
        user_ctx,
        detail="HR import admin access required.",
    )


def _apply_dept_rbac_scope(
    uid: int,
    user_ctx: Dict[str, Any],
    *,
    include_inactive: bool,
) -> Dict[str, Any]:
    scope_unit_id: Optional[int] = None
    scope_unit_ids: Optional[List[int]] = None
    mode = _rbac_mode()

    if mode == "dept":
        scope_unit_id = _require_dept_scope(user_ctx)
        try:
            s = org_units.compute_user_scope_unit_ids(uid, include_inactive=include_inactive)
        except PermissionError as pe:
            raise HTTPException(status_code=403, detail=str(pe))
        if s is not None:
            scope_unit_ids = sorted(list(s))

    if mode == "groups":
        try:
            s = org_units.compute_user_scope_unit_ids(uid, include_inactive=include_inactive)
        except PermissionError as pe:
            raise HTTPException(status_code=403, detail=str(pe))
        if s is not None:
            scope_unit_ids = sorted(list(s))
        scope_unit_id = None

    return {
        "scope_unit_id": scope_unit_id,
        "scope_unit_ids": scope_unit_ids,
    }


def compute_scope(
    uid: int,
    user_ctx: Dict[str, Any],
    include_inactive: bool = False,
) -> Dict[str, Any]:
    from app.services.personnel_visibility_resolver_service import (
        resolve_effective_personnel_visibility,
    )

    privileged = _is_privileged(user_ctx)

    if privileged:
        return {
            "privileged": True,
            "scope_unit_id": None,
            "scope_unit_ids": None,
            "has_personnel_visibility": True,
            "can_view_tasks_readonly": True,
        }

    visibility = resolve_effective_personnel_visibility(
        int(uid),
        user_ctx=user_ctx,
        include_inactive=include_inactive,
    )

    if visibility.get("has_visibility"):
        if visibility.get("organization_wide"):
            return {
                "privileged": False,
                "scope_unit_id": None,
                "scope_unit_ids": None,
                "has_personnel_visibility": True,
                "can_view_tasks_readonly": bool(visibility.get("can_view_tasks")),
            }

        raw_scope_ids = visibility.get("scope_unit_ids")
        if visibility.get("implicit_from_access_level") and raw_scope_ids == []:
            dept_scope = _apply_dept_rbac_scope(uid, user_ctx, include_inactive=include_inactive)
            return {
                "privileged": False,
                "has_personnel_visibility": True,
                "can_view_tasks_readonly": bool(visibility.get("can_view_tasks")),
                **dept_scope,
            }

        scope_unit_ids: Optional[List[int]]
        if raw_scope_ids is None:
            scope_unit_ids = []
        else:
            scope_unit_ids = sorted(int(x) for x in raw_scope_ids)

        scope_unit_id = scope_unit_ids[0] if len(scope_unit_ids) == 1 else None
        return {
            "privileged": False,
            "scope_unit_id": scope_unit_id,
            "scope_unit_ids": scope_unit_ids,
            "has_personnel_visibility": True,
            "can_view_tasks_readonly": bool(visibility.get("can_view_tasks")),
        }

    return {
        "privileged": False,
        "scope_unit_id": None,
        "scope_unit_ids": [],
        "has_personnel_visibility": False,
        "can_view_tasks_readonly": False,
    }


def require_personnel_visibility_or_403(user_ctx: Dict[str, Any], scope: Dict[str, Any]) -> None:
    if scope.get("privileged"):
        return
    if scope.get("has_personnel_visibility"):
        return
    raise HTTPException(status_code=403, detail="Personnel visibility is not granted.")


def load_ancestor_chain_units(
    *,
    leaf_unit_id: int,
    include_inactive: bool,
) -> List[OrgUnit]:
    where_ou = "" if include_inactive else "AND COALESCE(ou.is_active, true) = true"
    where_p = "" if include_inactive else "AND COALESCE(p.is_active, true) = true"

    schema = getattr(org_units, "_schema", "public")
    table = getattr(org_units, "_org_units_table", "org_units")

    sql = text(
        f"""
        WITH RECURSIVE up AS (
            SELECT
                ou.unit_id,
                ou.parent_unit_id,
                ou.name,
                ou.code,
                ou.group_id,
                COALESCE(ou.is_active, true) AS is_active
            FROM {schema}.{table} ou
            WHERE ou.unit_id = :leaf_unit_id
            {where_ou}

            UNION ALL

            SELECT
                p.unit_id,
                p.parent_unit_id,
                p.name,
                p.code,
                p.group_id,
                COALESCE(p.is_active, true) AS is_active
            FROM {schema}.{table} p
            JOIN up ON up.parent_unit_id = p.unit_id
            {where_p}
        )
        SELECT unit_id, parent_unit_id, name, code, group_id, is_active
        FROM up
        """
    )

    with engine.begin() as c:
        rows = c.execute(sql, {"leaf_unit_id": int(leaf_unit_id)}).mappings().all()

    out: List[OrgUnit] = []
    for r in rows:
        out.append(
            OrgUnit(
                unit_id=int(r["unit_id"]),
                parent_unit_id=int(r["parent_unit_id"]) if r["parent_unit_id"] is not None else None,
                name=str(r["name"]) if r["name"] is not None else "",
                code=str(r["code"]) if r["code"] is not None else None,
                group_id=int(r["group_id"]) if r.get("group_id") is not None else None,
                is_active=bool(r["is_active"]),
            )
        )
    return out
