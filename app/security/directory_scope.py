from __future__ import annotations

import os
from typing import Any, Dict, Optional, Set, Tuple

from fastapi import HTTPException
from sqlalchemy import text

from app.db.engine import engine


# ---------------------------
# Config
# ---------------------------
def rbac_mode() -> str:
    # off | dept
    v = (os.getenv("DIRECTORY_RBAC_MODE") or "dept").strip().lower()
    return v if v in ("off", "dept") else "dept"


def _parse_int_set_env(name: str) -> Set[int]:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return set()
    out: Set[int] = set()
    for part in raw.split(","):
        s = part.strip()
        if not s:
            continue
        try:
            out.add(int(s))
        except ValueError:
            continue
    return out


def privileged_user_ids() -> Set[int]:
    # Preferred: DIRECTORY_PRIVILEGED_USER_IDS
    # Backward-compat: DIRECTORY_PRIVILEGED_IDS
    s = set()
    s |= _parse_int_set_env("DIRECTORY_PRIVILEGED_USER_IDS")
    s |= _parse_int_set_env("DIRECTORY_PRIVILEGED_IDS")
    return s


def privileged_role_ids() -> Set[int]:
    # Preferred: DIRECTORY_PRIVILEGED_ROLE_IDS
    return _parse_int_set_env("DIRECTORY_PRIVILEGED_ROLE_IDS")


# ---------------------------
# Requester context (RBAC)
# ---------------------------
def require_user_id(x_user_id: Optional[str]) -> int:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-Id header.")
    s = str(x_user_id).strip()
    if not s:
        raise HTTPException(status_code=400, detail="Invalid X-User-Id header.")
    try:
        return int(s)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-User-Id header.")


def load_user_ctx(user_id: int) -> Dict[str, Any]:
    q = text(
        """
        SELECT user_id, role_id, unit_id, is_active
        FROM public.users
        WHERE user_id = :uid
        LIMIT 1
        """
    )
    with engine.begin() as conn:
        row = conn.execute(q, {"uid": user_id}).mappings().first()

    if not row:
        raise HTTPException(status_code=401, detail="Unknown user.")
    if not bool(row.get("is_active")):
        raise HTTPException(status_code=403, detail="User is inactive.")
    return dict(row)


def is_privileged(user_ctx: Dict[str, Any]) -> bool:
    uid = int(user_ctx["user_id"])
    rid = int(user_ctx["role_id"]) if user_ctx.get("role_id") is not None else -1
    if uid in privileged_user_ids():
        return True
    if rid in privileged_role_ids():
        return True
    return False


def require_dept_scope(user_ctx: Dict[str, Any]) -> int:
    """
    For RBAC_MODE=dept: non-privileged users must have unit_id.
    unit_id is treated as scope root (org_units tree).
    """
    unit_id = user_ctx.get("unit_id")
    if unit_id is None:
        raise HTTPException(
            status_code=403,
            detail="directory: cannot determine department scope for user (unit_id is null).",
        )
    try:
        return int(unit_id)
    except Exception:
        raise HTTPException(
            status_code=403,
            detail="directory: invalid unit_id for department scope.",
        )


# ---------------------------
# RBAC helpers for services
# ---------------------------
def build_dept_scope_cte(
    *,
    scope_unit_id: Optional[int],
    alias: str = "e",
    column: str = "org_unit_id",
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Build CTE + WHERE fragment for dept RBAC scope.

    Returns:
      cte_sql      : string (WITH RECURSIVE ... or empty)
      where_sql    : string condition to be AND-ed
      params       : dict of SQL params

    If scope_unit_id is None -> returns empty fragments (no RBAC restriction).
    """
    if scope_unit_id is None:
        return "", "TRUE", {}

    cte_sql = """
    WITH RECURSIVE rbac_subtree AS (
        SELECT unit_id
        FROM public.org_units
        WHERE unit_id = :rbac_scope_unit_id
        UNION ALL
        SELECT ou.unit_id
        FROM public.org_units ou
        JOIN rbac_subtree s ON ou.parent_unit_id = s.unit_id
    )
    """.strip()

    where_sql = f"{alias}.{column} IN (SELECT unit_id FROM rbac_subtree)"
    params = {"rbac_scope_unit_id": int(scope_unit_id)}

    return cte_sql, where_sql, params
