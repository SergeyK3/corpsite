# FILE: app/directory/roles_routes.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth import get_current_user
from app.db.engine import engine
from app.security.directory_scope import is_privileged as _is_privileged

router = APIRouter()


class RoleUpsert(BaseModel):
    role_code: str = Field(..., min_length=1, max_length=200)
    role_name: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    is_active: bool = True


def _list_tables(schema: str = "public") -> List[str]:
    q = text(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = :schema
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(q, {"schema": schema}).fetchall()
    return [str(r[0]) for r in rows]


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


def _score_roles(name: str, cols: List[str]) -> int:
    lc = {c.lower() for c in cols}
    n = name.lower()
    score = 0

    if n == "roles":
        score += 100
    if "role" in n:
        score += 40

    if "role_id" in lc or "id" in lc:
        score += 20
    if "role_code" in lc or "code" in lc:
        score += 25
    if "role_name" in lc or "name" in lc:
        score += 25
    if "is_active" in lc or "active" in lc or "status" in lc:
        score += 8
    if "description" in lc or "desc" in lc or "comment" in lc:
        score += 6

    return score


def _roles_relation() -> Tuple[str, List[str]]:
    best_rel: Optional[str] = None
    best_cols: List[str] = []
    best_score = -1

    for rel in _list_tables("public"):
        cols = _get_columns(rel, "public")
        if not cols:
            continue
        score = _score_roles(rel, cols)
        if score > best_score:
            best_rel, best_cols, best_score = rel, cols, score

    if not best_rel or best_score < 60:
        raise HTTPException(status_code=500, detail="Cannot auto-detect roles table.")

    return best_rel, best_cols


def _roles_meta() -> Dict[str, Optional[str]]:
    rel, cols = _roles_relation()

    id_col = _pick_first(cols, ["role_id", "id"])
    code_col = _pick_first(cols, ["role_code", "code"])
    name_col = _pick_first(cols, ["role_name", "name"])
    desc_col = _pick_first(cols, ["description", "desc", "comment", "notes"])
    active_col = _pick_first(cols, ["is_active", "active", "status"])

    if not id_col or not code_col or not name_col:
        raise HTTPException(
            status_code=500,
            detail="Roles table is missing one of required columns: id/code/name.",
        )

    return {
        "rel": rel,
        "id_col": id_col,
        "code_col": code_col,
        "name_col": name_col,
        "desc_col": desc_col,
        "active_col": active_col,
    }


def _org_units_meta() -> Dict[str, Optional[str]]:
    cols = _get_columns("org_units", "public")
    if not cols:
        return {
            "rel": "org_units",
            "id_col": "unit_id",
            "name_col": None,
        }

    id_col = _pick_first(cols, ["unit_id", "id"])
    name_col = _pick_first(cols, ["title", "name", "unit_name", "org_unit_name", "label"])

    return {
        "rel": "org_units",
        "id_col": id_col or "unit_id",
        "name_col": name_col,
    }


def _get_org_unit_caption(org_unit_id: int) -> str:
    meta = _org_units_meta()

    if not meta["name_col"]:
        return f"unit #{int(org_unit_id)}"

    q = text(
        f"""
        SELECT
            {meta['name_col']} AS unit_name
        FROM public.{meta['rel']}
        WHERE {meta['id_col']} = :org_unit_id
        LIMIT 1
        """
    )

    with engine.begin() as conn:
        row = conn.execute(q, {"org_unit_id": int(org_unit_id)}).mappings().first()

    if not row:
        return f"unit #{int(org_unit_id)}"

    value = str(row.get("unit_name") or "").strip()
    return value or f"unit #{int(org_unit_id)}"


def _normalize_active(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in ("1", "true", "yes", "y", "on", "active", "активна", "активен")


def _normalize_role_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "role_id": int(row["role_id"]) if row.get("role_id") is not None else None,
        "role_code": str(row.get("role_code") or "").strip(),
        "role_name": str(row.get("role_name") or "").strip(),
        "description": row.get("description"),
        "is_active": _normalize_active(row.get("is_active")),
    }


def _build_select_sql(meta: Dict[str, Optional[str]]) -> str:
    desc_expr = f"{meta['desc_col']} AS description" if meta["desc_col"] else "NULL AS description"

    if meta["active_col"] == "status":
        active_expr = "status AS is_active"
    elif meta["active_col"]:
        active_expr = f"{meta['active_col']} AS is_active"
    else:
        active_expr = "TRUE AS is_active"

    return f"""
        SELECT
            {meta['id_col']} AS role_id,
            {meta['code_col']} AS role_code,
            {meta['name_col']} AS role_name,
            {desc_expr},
            {active_expr}
        FROM public.{meta['rel']}
    """


@router.get("/roles")
def list_roles(
    q: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    org_unit_id: Optional[int] = Query(default=None, ge=1),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not _is_privileged(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    meta = _roles_meta()
    base_sql = _build_select_sql(meta)

    filters: List[str] = []
    params: Dict[str, Any] = {"limit": limit, "offset": offset}
    with_prefix = ""

    filter_org_unit_name: Optional[str] = None

    if q and q.strip():
        params["q"] = f"%{q.strip().lower()}%"
        filters.append(
            "(LOWER(CAST(role_code AS TEXT)) LIKE :q OR LOWER(CAST(role_name AS TEXT)) LIKE :q)"
        )

    if is_active is not None:
        if meta["active_col"] == "status":
            if is_active:
                filters.append(
                    "LOWER(CAST(is_active AS TEXT)) IN ('1','true','yes','y','on','active','активна','активен')"
                )
            else:
                filters.append(
                    "LOWER(CAST(is_active AS TEXT)) IN ('0','false','no','n','off','inactive','неактивна','неактивен')"
                )
        elif meta["active_col"]:
            filters.append("CAST(is_active AS BOOLEAN) = :is_active")
            params["is_active"] = bool(is_active)

    if org_unit_id is not None:
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

        filters.append(
            """
            EXISTS (
                SELECT 1
                FROM public.users u
                WHERE u.role_id = t.role_id
                  AND u.unit_id IN (SELECT unit_id FROM subtree)
                  AND COALESCE(u.is_active, TRUE) = TRUE
            )
            """.strip()
        )

    where_sql = "TRUE"
    if filters:
        where_sql = " AND ".join(filters)

    q_total = text(
        f"""
        {with_prefix}
        SELECT COUNT(*) AS cnt
        FROM ({base_sql}) t
        WHERE {where_sql}
        """
    )

    q_list = text(
        f"""
        {with_prefix}
        SELECT *
        FROM ({base_sql}) t
        WHERE {where_sql}
        ORDER BY role_id ASC
        LIMIT :limit OFFSET :offset
        """
    )

    with engine.begin() as conn:
        total = int(conn.execute(q_total, params).mappings().first()["cnt"])
        rows = conn.execute(q_list, params).mappings().all()

    items = [_normalize_role_row(dict(r)) for r in rows]
    return {
        "items": items,
        "total": total,
        "filter_org_unit_id": int(org_unit_id) if org_unit_id is not None else None,
        "filter_org_unit_name": filter_org_unit_name,
    }


@router.post("/roles")
def create_role(
    payload: RoleUpsert,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not _is_privileged(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    meta = _roles_meta()

    code = payload.role_code.strip()
    name = payload.role_name.strip()
    desc = (payload.description or "").strip() or None
    active = bool(payload.is_active)

    if not code:
        raise HTTPException(status_code=422, detail="role_code is required.")
    if not name:
        raise HTTPException(status_code=422, detail="role_name is required.")

    cols = [meta["code_col"], meta["name_col"]]
    vals = [":role_code", ":role_name"]
    params: Dict[str, Any] = {
        "role_code": code,
        "role_name": name,
    }

    if meta["desc_col"]:
        cols.append(meta["desc_col"])
        vals.append(":description")
        params["description"] = desc

    if meta["active_col"]:
        cols.append(meta["active_col"])
        vals.append(":is_active")
        if meta["active_col"] == "status":
            params["is_active"] = "active" if active else "inactive"
        else:
            params["is_active"] = active

    insert_sql = text(
        f"""
        INSERT INTO public.{meta['rel']} ({", ".join(str(c) for c in cols)})
        VALUES ({", ".join(vals)})
        RETURNING {meta['id_col']} AS role_id
        """
    )

    try:
        with engine.begin() as conn:
            created = conn.execute(insert_sql, params).mappings().first()
            role_id = int(created["role_id"])

            row = conn.execute(
                text(
                    f"""
                    SELECT *
                    FROM ({_build_select_sql(meta)}) t
                    WHERE role_id = :role_id
                    """
                ),
                {"role_id": role_id},
            ).mappings().first()

    except IntegrityError:
        raise HTTPException(status_code=409, detail="Role already exists or conflicts with existing data.")

    return _normalize_role_row(dict(row))


@router.put("/roles/{role_id}")
def update_role(
    role_id: int,
    payload: RoleUpsert,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not _is_privileged(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    meta = _roles_meta()

    code = payload.role_code.strip()
    name = payload.role_name.strip()
    desc = (payload.description or "").strip() or None
    active = bool(payload.is_active)

    if not code:
        raise HTTPException(status_code=422, detail="role_code is required.")
    if not name:
        raise HTTPException(status_code=422, detail="role_name is required.")

    set_parts = [
        f"{meta['code_col']} = :role_code",
        f"{meta['name_col']} = :role_name",
    ]
    params: Dict[str, Any] = {
        "role_id": int(role_id),
        "role_code": code,
        "role_name": name,
    }

    if meta["desc_col"]:
        set_parts.append(f"{meta['desc_col']} = :description")
        params["description"] = desc

    if meta["active_col"]:
        set_parts.append(f"{meta['active_col']} = :is_active")
        if meta["active_col"] == "status":
            params["is_active"] = "active" if active else "inactive"
        else:
            params["is_active"] = active

    q_exists = text(
        f"""
        SELECT 1
        FROM public.{meta['rel']}
        WHERE {meta['id_col']} = :role_id
        LIMIT 1
        """
    )

    q_update = text(
        f"""
        UPDATE public.{meta['rel']}
        SET {", ".join(set_parts)}
        WHERE {meta['id_col']} = :role_id
        """
    )

    try:
        with engine.begin() as conn:
            exists = conn.execute(q_exists, {"role_id": int(role_id)}).first()
            if not exists:
                raise HTTPException(status_code=404, detail="Role not found.")

            conn.execute(q_update, params)

            row = conn.execute(
                text(
                    f"""
                    SELECT *
                    FROM ({_build_select_sql(meta)}) t
                    WHERE role_id = :role_id
                    """
                ),
                {"role_id": int(role_id)},
            ).mappings().first()

    except IntegrityError:
        raise HTTPException(status_code=409, detail="Role update conflicts with existing data.")

    return _normalize_role_row(dict(row))


@router.delete("/roles/{role_id}")
def delete_role(
    role_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not _is_privileged(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    meta = _roles_meta()

    q_exists = text(
        f"""
        SELECT 1
        FROM public.{meta['rel']}
        WHERE {meta['id_col']} = :role_id
        LIMIT 1
        """
    )

    q_delete = text(
        f"""
        DELETE FROM public.{meta['rel']}
        WHERE {meta['id_col']} = :role_id
        """
    )

    try:
        with engine.begin() as conn:
            exists = conn.execute(q_exists, {"role_id": int(role_id)}).first()
            if not exists:
                raise HTTPException(status_code=404, detail="Role not found.")

            conn.execute(q_delete, {"role_id": int(role_id)})

    except IntegrityError:
        raise HTTPException(status_code=409, detail="Role cannot be deleted because related records still exist.")

    return {"ok": True, "role_id": int(role_id)}