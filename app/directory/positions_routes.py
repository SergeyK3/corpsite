# FILE: app/directory/positions_routes.py
from __future__ import annotations

from typing import Any, Dict, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth import get_current_user
from app.db.engine import engine
from app.org_scope.apply import apply_org_scope
from app.org_scope.types import OrgScopeParams, OrgScopeStrategy
from app.security.directory_scope import (
    is_privileged as _is_privileged,
    is_system_admin as _is_system_admin,
)

from app.directory.rbac import compute_scope, require_personnel_visibility_or_403
from app.services.org_unit_allowed_positions_service import (
    build_allowed_positions_exists_sql,
    build_allowed_positions_order_sql,
)
from app.services.position_dependencies_service import (
    build_position_blocked_exists_sql,
    check_position_dependencies,
    check_positions_dependencies,
    load_position_blocking_foreign_keys,
)

router = APIRouter()

ALLOWED_CATEGORIES = {"leaders", "medical", "admin", "technical", "other"}
POSITION_LIST_SCOPES = {"used", "allowed"}
POSITION_DELETE_STATUSES = {"deletable", "blocked"}


class PositionUpsert(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    category: str = Field(..., min_length=1, max_length=50)


def _normalize_name(value: str) -> str:
    return " ".join((value or "").replace(" -", "-").replace("- ", "-").split()).strip()


def _normalize_category(value: Optional[str]) -> str:
    s = str(value or "").strip().lower()
    if s not in ALLOWED_CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail="category must be one of: leaders, medical, admin, technical, other.",
        )
    return s


def _get_columns(rel: str, schema: str = "public") -> List[str]:
    q = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = :schema
          AND table_name = :rel
        ORDER BY ordinal_position
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(q, {"schema": schema, "rel": rel}).fetchall()
    return [str(r[0]) for r in rows]


def _pick_first(existing: List[str], candidates: List[str]) -> Optional[str]:
    s = set(existing)
    for c in candidates:
        if c in s:
            return c
    return None


def _employees_org_meta() -> Dict[str, str]:
    cols = _get_columns("employees", "public")
    if not cols:
        raise HTTPException(status_code=500, detail="employees table not found.")

    position_col = _pick_first(cols, ["position_id"])
    org_unit_col = _pick_first(cols, ["org_unit_id", "unit_id"])

    if not position_col or not org_unit_col:
        raise HTTPException(
            status_code=500,
            detail="employees table must contain position_id and org_unit_id (or unit_id).",
        )

    return {
        "position_col": position_col,
        "org_unit_col": org_unit_col,
    }


def _get_org_unit_caption(org_unit_id: int) -> str:
    q = text(
        """
        SELECT COALESCE(NULLIF(TRIM(name), ''), CONCAT('unit #', CAST(unit_id AS TEXT))) AS unit_name
        FROM public.org_units
        WHERE unit_id = :org_unit_id
        LIMIT 1
        """
    )
    with engine.begin() as conn:
        row = conn.execute(q, {"org_unit_id": int(org_unit_id)}).mappings().first()

    if not row:
        return f"unit #{int(org_unit_id)}"

    return str(row.get("unit_name") or f"unit #{int(org_unit_id)}").strip()


def _normalize_list_scope(
    scope: Optional[str],
    *,
    org_group_id: Optional[int],
    org_unit_id: Optional[int],
) -> str:
    normalized = str(scope or "used").strip().lower()
    if normalized not in POSITION_LIST_SCOPES:
        raise HTTPException(
            status_code=422,
            detail="scope must be one of: used, allowed.",
        )
    if normalized == "allowed" and org_group_id is None and org_unit_id is None:
        raise HTTPException(
            status_code=422,
            detail="scope=allowed requires org_unit_id and/or org_group_id.",
        )
    return normalized


@router.get("/positions")
def list_positions_crud(
    q: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    org_group_id: Optional[int] = Query(
        default=None,
        ge=1,
        description="Filter by top-level org group of employee's unit.",
    ),
    org_unit_id: Optional[int] = Query(default=None, ge=1),
    scope: Optional[str] = Query(
        default=None,
        description="Org-unit filter semantics: used (employees) or allowed (junction table). Default: used.",
    ),
    delete_status: Optional[str] = Query(
        default=None,
        description="Sysadmin-only deletion assessment filter: deletable or blocked.",
    ),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = int(user["user_id"])
    visibility_scope = compute_scope(uid, user)
    require_personnel_visibility_or_403(user, visibility_scope)

    normalized_delete_status = str(delete_status or "").strip().lower() or None
    if normalized_delete_status is not None:
        if not _is_system_admin(user):
            raise HTTPException(status_code=403, detail="Forbidden.")
        if normalized_delete_status not in POSITION_DELETE_STATUSES:
            raise HTTPException(
                status_code=422,
                detail="delete_status must be one of: deletable, blocked.",
            )

    params: Dict[str, Any] = {"limit": limit, "offset": offset}
    where_parts = ["TRUE"]
    with_prefix = ""
    filter_org_unit_name: Optional[str] = None
    order_sql = "p.name ASC, p.position_id ASC"

    if q and q.strip():
        params["q"] = f"%{q.strip().lower()}%"
        where_parts.append("LOWER(CAST(p.name AS TEXT)) LIKE :q")

    if category and category.strip():
        params["category"] = _normalize_category(category)
        where_parts.append("p.category = :category")

    if scope is not None and str(scope).strip().lower() == "allowed":
        if org_group_id is None and org_unit_id is None:
            raise HTTPException(
                status_code=422,
                detail="scope=allowed requires org_unit_id and/or org_group_id.",
            )

    if org_group_id is not None or org_unit_id is not None:
        list_scope = _normalize_list_scope(
            scope,
            org_group_id=org_group_id,
            org_unit_id=org_unit_id,
        )
        if org_unit_id is not None:
            filter_org_unit_name = _get_org_unit_caption(int(org_unit_id))

        if list_scope == "allowed":
            allowed_exists, allowed_params = build_allowed_positions_exists_sql(
                org_group_id=int(org_group_id) if org_group_id is not None else None,
                org_unit_id=int(org_unit_id) if org_unit_id is not None else None,
            )
            params.update(allowed_params)
            where_parts.append(allowed_exists)
            allowed_order, allowed_order_params = build_allowed_positions_order_sql(
                org_group_id=int(org_group_id) if org_group_id is not None else None,
                org_unit_id=int(org_unit_id) if org_unit_id is not None else None,
            )
            params.update(allowed_order_params)
            order_sql = allowed_order
        else:
            emp_meta = _employees_org_meta()
            org_scope = apply_org_scope(
                strategy=OrgScopeStrategy.OWNER_UNIT,
                params=OrgScopeParams(
                    org_group_id=int(org_group_id) if org_group_id is not None else None,
                    org_unit_id=int(org_unit_id) if org_unit_id is not None else None,
                ),
                regular_task_alias="e",
                owner_unit_column=emp_meta["org_unit_col"],
            )
            params.update(org_scope.params)
            with_prefix = f"{org_scope.cte_sql}\n" if org_scope.cte_sql else ""

            where_parts.append(
                f"""
                EXISTS (
                    SELECT 1
                    FROM public.employees e
                    WHERE e.{emp_meta['position_col']} = p.position_id
                      AND ({org_scope.where_sql})
                )
                """.strip()
            )

    with engine.begin() as conn:
        dependency_specs = []
        if _is_system_admin(user):
            dependency_specs = load_position_blocking_foreign_keys(conn)
            if normalized_delete_status is not None:
                blocked_sql = build_position_blocked_exists_sql(
                    dependency_specs,
                    position_expression="p.position_id",
                )
                where_parts.append(
                    f"({blocked_sql})"
                    if normalized_delete_status == "blocked"
                    else f"NOT ({blocked_sql})"
                )

        where_sql = " AND ".join(where_parts)
        q_total = text(
            f"""
            {with_prefix}
            SELECT COUNT(*) AS cnt
            FROM public.positions p
            WHERE {where_sql}
            """
        )
        q_list = text(
            f"""
            {with_prefix}
            SELECT p.position_id, p.name, p.category
            FROM public.positions p
            WHERE {where_sql}
            ORDER BY {order_sql}
            LIMIT :limit OFFSET :offset
            """
        )
        total = int(conn.execute(q_total, params).mappings().first()["cnt"])
        rows = conn.execute(q_list, params).mappings().all()
        assessments = (
            check_positions_dependencies(
                conn,
                position_ids=[int(row["position_id"]) for row in rows],
                dependencies=dependency_specs,
            )
            if _is_system_admin(user)
            else {}
        )

    items = []
    for r in rows:
        position_id = int(r["position_id"])
        item = {
            "position_id": int(r["position_id"]),
            "name": str(r["name"] or "").strip(),
            "category": str(r["category"] or "").strip(),
        }
        assessment = assessments.get(position_id)
        if assessment is not None:
            item["delete_assessment"] = assessment.to_dict()
        items.append(item)
    return {
        "items": items,
        "total": total,
        "filter_org_unit_id": int(org_unit_id) if org_unit_id is not None else None,
        "filter_org_unit_name": filter_org_unit_name,
    }


@router.get("/positions/{position_id}")
def get_position(
    position_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    uid = int(user["user_id"])
    visibility_scope = compute_scope(uid, user)
    require_personnel_visibility_or_403(user, visibility_scope)

    q_one = text(
        """
        SELECT position_id, name, category
        FROM public.positions
        WHERE position_id = :position_id
        LIMIT 1
        """
    )

    with engine.begin() as conn:
        row = conn.execute(q_one, {"position_id": position_id}).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Position not found.")

    return {
        "position_id": int(row["position_id"]),
        "name": str(row["name"] or "").strip(),
        "category": str(row["category"] or "").strip(),
    }


@router.get("/positions/{position_id}/dependencies")
def get_position_dependencies(
    position_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not _is_system_admin(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    with engine.begin() as conn:
        exists = conn.execute(
            text(
                """
                SELECT 1 FROM public.positions
                WHERE position_id = :position_id
                LIMIT 1
                """
            ),
            {"position_id": int(position_id)},
        ).first()
        if not exists:
            raise HTTPException(status_code=404, detail="Position not found.")
        summary = check_position_dependencies(conn, position_id=int(position_id))
    return summary.to_dict()


@router.post("/positions")
def create_position(
    payload: PositionUpsert,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not _is_privileged(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    name = _normalize_name(payload.name)
    category = _normalize_category(payload.category)

    if not name:
        raise HTTPException(status_code=422, detail="name is required.")

    q_exists = text(
        """
        SELECT position_id, name
        FROM public.positions
        WHERE lower(name) = lower(:name)
        LIMIT 1
        """
    )

    q_insert = text(
        """
        INSERT INTO public.positions(name, category)
        VALUES (:name, :category)
        RETURNING position_id, name, category
        """
    )

    try:
        with engine.begin() as conn:
            exists = conn.execute(q_exists, {"name": name}).mappings().first()
            if exists:
                raise HTTPException(status_code=409, detail="Position already exists.")

            row = conn.execute(
                q_insert,
                {"name": name, "category": category},
            ).mappings().first()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Position already exists or conflicts with existing data.")

    return {
        "position_id": int(row["position_id"]),
        "name": str(row["name"] or "").strip(),
        "category": str(row["category"] or "").strip(),
    }


@router.put("/positions/{position_id}")
def update_position(
    position_id: int,
    payload: PositionUpsert,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not _is_privileged(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    name = _normalize_name(payload.name)
    category = _normalize_category(payload.category)

    if not name:
        raise HTTPException(status_code=422, detail="name is required.")

    q_exists = text(
        """
        SELECT position_id, name
        FROM public.positions
        WHERE position_id = :position_id
        LIMIT 1
        """
    )

    q_dup = text(
        """
        SELECT position_id
        FROM public.positions
        WHERE lower(name) = lower(:name)
          AND position_id <> :position_id
        LIMIT 1
        """
    )

    q_update = text(
        """
        UPDATE public.positions
        SET name = :name,
            category = :category
        WHERE position_id = :position_id
        RETURNING position_id, name, category
        """
    )

    try:
        with engine.begin() as conn:
            exists = conn.execute(q_exists, {"position_id": position_id}).mappings().first()
            if not exists:
                raise HTTPException(status_code=404, detail="Position not found.")

            dup = conn.execute(q_dup, {"position_id": position_id, "name": name}).first()
            if dup:
                raise HTTPException(status_code=409, detail="Position already exists.")

            row = conn.execute(
                q_update,
                {"position_id": position_id, "name": name, "category": category},
            ).mappings().first()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Position update conflicts with existing data.")

    return {
        "position_id": int(row["position_id"]),
        "name": str(row["name"] or "").strip(),
        "category": str(row["category"] or "").strip(),
    }


@router.delete("/positions/{position_id}")
def delete_position(
    position_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not _is_system_admin(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    q_exists = text(
        """
        SELECT position_id
        FROM public.positions
        WHERE position_id = :position_id
        LIMIT 1
        FOR UPDATE
        """
    )

    q_delete = text(
        """
        DELETE FROM public.positions
        WHERE position_id = :position_id
        """
    )

    try:
        with engine.begin() as conn:
            exists = conn.execute(q_exists, {"position_id": position_id}).first()
            if not exists:
                raise HTTPException(status_code=404, detail="Position not found.")

            summary = check_position_dependencies(conn, position_id=int(position_id))
            if not summary.can_delete:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error_code": "POSITION_HAS_DEPENDENCIES",
                        **summary.to_dict(),
                    },
                )

            conn.execute(q_delete, {"position_id": position_id})
    except IntegrityError as exc:
        # A dependency may be inserted after an earlier HTTP preflight. The FK
        # remains the final guard; refresh the shared assessment for a stable,
        # controlled 409 response instead of exposing the database error.
        with engine.begin() as conn:
            summary = check_position_dependencies(conn, position_id=int(position_id))
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "POSITION_HAS_DEPENDENCIES",
                "race_detected": True,
                **summary.to_dict(),
            },
        ) from exc

    return {"ok": True, "position_id": position_id}
