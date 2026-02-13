# FILE: app/directory/debug_routes.py
from __future__ import annotations

import os
from typing import Any, Dict, Optional, List

from fastapi import APIRouter, Header, Query

from app.security.directory_scope import (
    rbac_mode as _rbac_mode,
    privileged_user_ids as _privileged_user_ids,
    privileged_role_ids as _privileged_role_ids,
    require_user_id as _require_user_id,
    load_user_ctx as _load_user_ctx,
    is_privileged as _is_privileged,
)

from .common import as_http500
from .rbac import compute_scope, org_units

router = APIRouter()


@router.get("/_debug/rbac")
def debug_rbac(
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    include_inactive: bool = Query(default=True),
) -> Dict[str, Any]:
    try:
        uid = _require_user_id(x_user_id)
        user_ctx = _load_user_ctx(uid)

        try:
            scope = compute_scope(uid, user_ctx, include_inactive=include_inactive)
            scope_err: Optional[str] = None
        except Exception as e:
            scope = {
                "privileged": bool(_is_privileged(user_ctx)),
                "scope_unit_id": None,
                "scope_unit_ids": None,
            }
            scope_err = str(getattr(e, "detail", str(e)))

        assigned_units: List[int] = []
        try:
            assigned_units = org_units.list_group_unit_ids_for_deputy(uid, include_inactive=include_inactive)
        except Exception:
            assigned_units = []

        return {
            "rbac_mode": _rbac_mode(),
            "env": {
                "DIRECTORY_RBAC_MODE": (os.getenv("DIRECTORY_RBAC_MODE") or ""),
                "DIRECTORY_PRIVILEGED_ROLE_IDS": (os.getenv("DIRECTORY_PRIVILEGED_ROLE_IDS") or ""),
                "DIRECTORY_PRIVILEGED_USER_IDS": (os.getenv("DIRECTORY_PRIVILEGED_USER_IDS") or ""),
                "DIRECTORY_PRIVILEGED_IDS": (os.getenv("DIRECTORY_PRIVILEGED_IDS") or ""),
            },
            "parsed": {
                "privileged_role_ids": sorted(list(_privileged_role_ids())),
                "privileged_user_ids": sorted(list(_privileged_user_ids())),
            },
            "user_ctx": {
                "user_id": int(user_ctx.get("user_id")),
                "role_id": int(user_ctx.get("role_id")) if user_ctx.get("role_id") is not None else None,
                "unit_id": int(user_ctx.get("unit_id")) if user_ctx.get("unit_id") is not None else None,
                "is_active": bool(user_ctx.get("is_active")),
            },
            "computed": {
                "is_privileged": bool(scope["privileged"]),
                "scope_unit_id": scope["scope_unit_id"],
                "scope_unit_ids_count": len(scope["scope_unit_ids"] or []),
                "scope_unit_ids_preview": (scope["scope_unit_ids"] or [])[:20],
                "assigned_units_direct": assigned_units,
                "error": scope_err,
            },
        }

    except Exception as e:
        raise as_http500(e)
