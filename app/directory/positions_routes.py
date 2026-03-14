# FILE: app/directory/positions_routes.py
from __future__ import annotations

from typing import Any, Dict, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth import get_current_user
from app.db.engine import engine
from app.security.directory_scope import is_privileged as _is_privileged

router = APIRouter()

ALLOWED_CATEGORIES = {"leaders", "medical", "admin", "technical", "other"}


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


@router.get("/positions")
def list_positions_crud(
    q: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    org_unit_id: Optional[int] = Query(default=None, ge=1),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not _is_privileged(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    params: Dict[str, Any] = {"limit": limit, "offset": offset}
    where_parts = ["TRUE"]
    with_prefix = ""
    filter_org_unit_name: Optional[str] = None

    if q and q.strip():
        params["q"] = f"%{q.strip().lower()}%"
        where_parts.append("LOWER(CAST(p.name AS TEXT)) LIKE :q")

    if category and category.strip():
        params["category"] = _normalize_category(category)
        where_parts.append("p.category = :category")

    if org_unit_id is not None:
        emp_meta = _employees_org_meta()
        params["org_unit_id"] = int(org_unit_id)
        filter_org_unit_name = _get_org_unit_caption(int(org_unit_id))

        with_prefix = """
        WITH RECURSIVE subtree AS (
            SELECT ou.unit_id
            FROM public.org_units ou
            WHERE ou.unit_id = :org_unit_id

            UNION ALL

            SELECT child.unit_id
            FROM public.org_units child
            JOIN subtree s ON s.unit_id = child.parent_unit_id
        )
        """

        where_parts.append(
            f"""
            EXISTS (
                SELECT 1
                FROM public.employees e
                WHERE e.{emp_meta['position_col']} = p.position_id
                  AND e.{emp_meta['org_unit_col']} IN (SELECT unit_id FROM subtree)
            )
            """.strip()
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
        ORDER BY p.name ASC, p.position_id ASC
        LIMIT :limit OFFSET :offset
        """
    )

    with engine.begin() as conn:
        total = int(conn.execute(q_total, params).mappings().first()["cnt"])
        rows = conn.execute(q_list, params).mappings().all()

    items = [
        {
            "position_id": int(r["position_id"]),
            "name": str(r["name"] or "").strip(),
            "category": str(r["category"] or "").strip(),
        }
        for r in rows
    ]
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
    if not _is_privileged(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

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
    except IntegrityError as e:
        raise HTTPException(status_code=409, detail=f"create position failed: {str(e.orig)}")

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
    except IntegrityError as e:
        raise HTTPException(status_code=409, detail=f"update position failed: {str(e.orig)}")

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
    if not _is_privileged(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    q_exists = text(
        """
        SELECT position_id
        FROM public.positions
        WHERE position_id = :position_id
        LIMIT 1
        """
    )

    q_refs = text(
        """
        SELECT COUNT(*) AS cnt
        FROM public.employees
        WHERE position_id = :position_id
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

            refs = int(conn.execute(q_refs, {"position_id": position_id}).mappings().first()["cnt"])
            if refs > 0:
                raise HTTPException(
                    status_code=409,
                    detail="Position is used in employees and cannot be deleted.",
                )

            conn.execute(q_delete, {"position_id": position_id})
    except IntegrityError as e:
        raise HTTPException(status_code=409, detail=f"delete position failed: {str(e.orig)}")

    return {"ok": True, "position_id": position_id}