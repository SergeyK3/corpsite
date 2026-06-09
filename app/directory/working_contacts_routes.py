# FILE: app/directory/working_contacts_routes.py
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from app.auth import get_current_user
from app.db.engine import engine
from app.org_scope.apply import apply_org_scope
from app.org_scope.types import OrgScopeParams, OrgScopeStrategy
from app.security.directory_scope import is_privileged as _is_privileged

router = APIRouter()


BASE_FROM_SQL = """
FROM public.users u
LEFT JOIN public.roles r
  ON r.role_id = u.role_id
LEFT JOIN public.org_units ou
  ON ou.unit_id = u.unit_id
"""

BASE_SELECT_SQL = f"""
SELECT
    u.user_id,
    u.unit_id AS org_unit_id,
    u.full_name,
    u.login,
    u.phone,
    u.telegram_username,
    r.name AS role_name,
    NULL::text AS role_name_ru,
    ou.name AS unit_name,
    ou.name AS unit_name_ru,
    COALESCE(u.is_active, false) AS is_active
{BASE_FROM_SQL}
"""


def _normalize_text(value: Any) -> Optional[str]:
    s = " ".join(str(value or "").split()).strip()
    return s or None


def _map_row(row: Dict[str, Any]) -> Dict[str, Any]:
    org_unit_id_raw = row.get("org_unit_id")
    return {
        "id": int(row["user_id"]),
        "user_id": int(row["user_id"]),
        "org_unit_id": int(org_unit_id_raw) if org_unit_id_raw is not None else None,
        "full_name": _normalize_text(row.get("full_name")),
        "login": _normalize_text(row.get("login")),
        "phone": _normalize_text(row.get("phone")),
        "telegram_username": _normalize_text(row.get("telegram_username")),
        "role_name": _normalize_text(row.get("role_name")),
        "role_name_ru": _normalize_text(row.get("role_name_ru")),
        "unit_name": _normalize_text(row.get("unit_name")),
        "unit_name_ru": _normalize_text(row.get("unit_name_ru")),
        "is_active": bool(row.get("is_active")),
    }


def _fetch_one(user_id: int) -> Optional[Dict[str, Any]]:
    q_one = text(
        f"""
        {BASE_SELECT_SQL}
        WHERE u.user_id = :user_id
        LIMIT 1
        """
    )

    with engine.begin() as conn:
        row = conn.execute(q_one, {"user_id": user_id}).mappings().first()

    return dict(row) if row else None


def _fetch_org_unit_name(org_unit_id: int) -> Optional[str]:
    q = text(
        """
        SELECT NULLIF(TRIM(name), '') AS unit_name
        FROM public.org_units
        WHERE unit_id = :org_unit_id
        LIMIT 1
        """
    )
    with engine.begin() as conn:
        row = conn.execute(q, {"org_unit_id": int(org_unit_id)}).mappings().first()
    if not row:
        return None
    return _normalize_text(row.get("unit_name"))


@router.get("/working-contacts")
def list_working_contacts(
    q: Optional[str] = Query(default=None),
    active_only: bool = Query(default=True),
    org_group_id: Optional[int] = Query(
        default=None,
        ge=1,
        description="Filter by top-level org group of user's unit.",
    ),
    org_unit_id: Optional[int] = Query(default=None, ge=1),
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not _is_privileged(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    params: Dict[str, Any] = {
        "limit": int(limit),
        "offset": int(offset),
        "active_only": bool(active_only),
    }

    where_parts = [
        "(:active_only = false OR COALESCE(u.is_active, false) = true)",
    ]

    org_scope = apply_org_scope(
        strategy=OrgScopeStrategy.OWNER_UNIT,
        params=OrgScopeParams(
            org_group_id=int(org_group_id) if org_group_id is not None else None,
            org_unit_id=int(org_unit_id) if org_unit_id is not None else None,
        ),
        regular_task_alias="u",
        owner_unit_column="unit_id",
    )
    params.update(org_scope.params)
    if org_scope.where_sql != "TRUE":
        where_parts.append(f"({org_scope.where_sql})")
    scope_prefix = f"{org_scope.cte_sql}\n" if org_scope.cte_sql else ""

    if q and q.strip():
        params["q"] = f"%{q.strip().lower()}%"
        where_parts.append(
            """
            (
                LOWER(COALESCE(CAST(u.user_id AS TEXT), '')) LIKE :q
                OR LOWER(COALESCE(CAST(u.full_name AS TEXT), '')) LIKE :q
                OR LOWER(COALESCE(CAST(u.login AS TEXT), '')) LIKE :q
                OR LOWER(COALESCE(CAST(u.phone AS TEXT), '')) LIKE :q
                OR LOWER(COALESCE(CAST(u.telegram_username AS TEXT), '')) LIKE :q
                OR LOWER(COALESCE(CAST(r.name AS TEXT), '')) LIKE :q
                OR LOWER(COALESCE(CAST(ou.name AS TEXT), '')) LIKE :q
            )
            """
        )

    where_sql = " AND ".join(where_parts)

    q_total = text(
        f"""
        {scope_prefix}
        SELECT COUNT(*) AS cnt
        {BASE_FROM_SQL}
        WHERE {where_sql}
        """
    )

    q_list = text(
        f"""
        {scope_prefix}
        {BASE_SELECT_SQL}
        WHERE {where_sql}
        ORDER BY
            COALESCE(u.is_active, false) DESC,
            LOWER(COALESCE(CAST(u.full_name AS TEXT), '')) ASC,
            u.user_id ASC
        LIMIT :limit OFFSET :offset
        """
    )

    with engine.begin() as conn:
        total = int(conn.execute(q_total, params).mappings().first()["cnt"])
        rows = conn.execute(q_list, params).mappings().all()

    items = [_map_row(dict(r)) for r in rows]
    filter_org_unit_name = _fetch_org_unit_name(int(org_unit_id)) if org_unit_id is not None else None

    return {
        "items": items,
        "total": total,
        "filter_org_unit_id": int(org_unit_id) if org_unit_id is not None else None,
        "filter_org_unit_name": filter_org_unit_name,
    }


@router.get("/working-contacts/{user_id}")
def get_working_contact(
    user_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not _is_privileged(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    row = _fetch_one(int(user_id))
    if not row:
        raise HTTPException(status_code=404, detail="Working contact not found.")

    return _map_row(row)