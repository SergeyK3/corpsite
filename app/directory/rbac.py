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
from app.services.org_units_service import OrgUnitsService, OrgUnit

org_units = OrgUnitsService(engine)


def require_privileged_or_403(user_ctx: Dict[str, Any]) -> None:
    if not _is_privileged(user_ctx):
        raise HTTPException(status_code=403, detail="Forbidden.")


def compute_scope(
    uid: int,
    user_ctx: Dict[str, Any],
    include_inactive: bool = False,
) -> Dict[str, Any]:
    privileged = _is_privileged(user_ctx)

    scope_unit_id: Optional[int] = None
    scope_unit_ids: Optional[List[int]] = None

    mode = _rbac_mode()

    if mode == "dept" and not privileged:
        scope_unit_id = _require_dept_scope(user_ctx)
        try:
            s = org_units.compute_user_scope_unit_ids(uid, include_inactive=include_inactive)
        except PermissionError as pe:
            raise HTTPException(status_code=403, detail=str(pe))
        if s is not None:
            scope_unit_ids = sorted(list(s))

    if mode == "groups" and not privileged:
        try:
            s = org_units.compute_user_scope_unit_ids(uid, include_inactive=include_inactive)
        except PermissionError as pe:
            raise HTTPException(status_code=403, detail=str(pe))
        if s is not None:
            scope_unit_ids = sorted(list(s))
        scope_unit_id = None

    return {
        "privileged": bool(privileged),
        "scope_unit_id": scope_unit_id,
        "scope_unit_ids": scope_unit_ids,
    }


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
                COALESCE(p.is_active, true) AS is_active
            FROM {schema}.{table} p
            JOIN up ON up.parent_unit_id = p.unit_id
            {where_p}
        )
        SELECT unit_id, parent_unit_id, name, code, is_active
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
                is_active=bool(r["is_active"]),
            )
        )
    return out
