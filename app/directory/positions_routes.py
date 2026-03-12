# FILE: app/directory/positions_routes.py
from __future__ import annotations

from typing import Any, Dict, Optional

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


@router.get("/positions")
def list_positions_crud(
    q: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not _is_privileged(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    params: Dict[str, Any] = {"limit": limit, "offset": offset}
    where_parts = ["TRUE"]

    if q and q.strip():
        params["q"] = f"%{q.strip().lower()}%"
        where_parts.append("LOWER(CAST(name AS TEXT)) LIKE :q")

    if category and category.strip():
        params["category"] = _normalize_category(category)
        where_parts.append("category = :category")

    where_sql = " AND ".join(where_parts)

    q_total = text(
        f"""
        SELECT COUNT(*) AS cnt
        FROM public.positions
        WHERE {where_sql}
        """
    )

    q_list = text(
        f"""
        SELECT position_id, name, category
        FROM public.positions
        WHERE {where_sql}
        ORDER BY name ASC, position_id ASC
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
    return {"items": items, "total": total}


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