# app/directory.py
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Header, HTTPException, Query, Path
from sqlalchemy import text

from app.db.engine import engine

router = APIRouter(prefix="/directory", tags=["directory"])


# ---------------------------
# Config
# ---------------------------
def _rbac_mode() -> str:
    # off | dept
    v = (os.getenv("DIRECTORY_RBAC_MODE") or "dept").strip().lower()
    return v if v in ("off", "dept") else "dept"


def _as_http500(e: Exception) -> HTTPException:
    return HTTPException(
        status_code=500,
        detail=f"directory error: {type(e).__name__}: {str(e)}",
    )


# ---------------------------
# Introspection helpers
# ---------------------------
def _list_relations(schema: str = "public") -> List[Tuple[str, str]]:
    q = text(
        """
        SELECT table_name AS name, 'table' AS kind
        FROM information_schema.tables
        WHERE table_schema = :schema AND table_type = 'BASE TABLE'
        UNION ALL
        SELECT table_name AS name, 'view' AS kind
        FROM information_schema.views
        WHERE table_schema = :schema
        ORDER BY name
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(q, {"schema": schema}).fetchall()
        return [(r[0], r[1]) for r in rows]


def _get_columns(rel: str, schema: str = "public") -> List[str]:
    q = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = :schema AND table_name = :rel
        ORDER BY ordinal_position
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(q, {"schema": schema, "rel": rel}).fetchall()
        return [r[0] for r in rows]


def _pick_first(existing: List[str], candidates: List[str]) -> Optional[str]:
    s = set(existing)
    for c in candidates:
        if c in s:
            return c
    return None


# ---------------------------
# Relation scoring (auto-detect)
# ---------------------------
def _score_employees(name: str, cols: List[str]) -> int:
    lc = {c.lower() for c in cols}
    n = name.lower()
    score = 0

    if "employee" in n or "employees" in n:
        score += 25
    if "person" in n or "people" in n:
        score += 10
    if "staff" in n or "workers" in n:
        score += 10
    if "dir" in n or "directory" in n:
        score += 8

    if lc.intersection({"employee_id", "tab_no", "tab_number", "personnel_no", "tn", "tabel", "id"}):
        score += 25

    if lc.intersection({"fio", "full_name", "name_ru", "employee_name"}):
        score += 20
    if lc.intersection({"last_name", "surname"}):
        score += 10

    if lc.intersection({"department_id", "dept_id", "org_unit_id", "department"}):
        score += 10
    if lc.intersection({"position_id", "pos_id", "position"}):
        score += 6

    return score


def _score_departments(name: str, cols: List[str]) -> int:
    lc = {c.lower() for c in cols}
    n = name.lower()
    score = 0

    if "department" in n or "departments" in n:
        score += 25
    if "dept" in n:
        score += 18
    if "org_unit" in n or "orgunit" in n or "unit" in n:
        score += 10

    # Must look like id+name dictionary
    if lc.intersection({"id", "department_id", "dept_id", "org_unit_id"}):
        score += 20
    if lc.intersection({"name", "name_ru", "dept_name", "department_name", "org_unit_name"}):
        score += 20

    return score


def _score_positions(name: str, cols: List[str]) -> int:
    lc = {c.lower() for c in cols}
    n = name.lower()
    score = 0

    if "position" in n or "positions" in n:
        score += 25
    if "post" in n or "job" in n:
        score += 10

    if lc.intersection({"id", "position_id", "pos_id"}):
        score += 20
    if lc.intersection({"name", "name_ru", "pos_name", "position_name"}):
        score += 20

    return score


def _best_relation(score_fn, min_score: int) -> Tuple[Optional[str], List[str], int]:
    rels = _list_relations("public")
    best_name: Optional[str] = None
    best_cols: List[str] = []
    best_score = -1

    for name, _kind in rels:
        cols = _get_columns(name, "public")
        if not cols:
            continue
        score = score_fn(name, cols)
        if score > best_score:
            best_name, best_cols, best_score = name, cols, score

    if best_name is None or best_score < min_score:
        return None, [], best_score

    return best_name, best_cols, best_score


def _employees_relation() -> Tuple[str, List[str]]:
    rel, cols, score = _best_relation(_score_employees, min_score=20)
    if not rel:
        raise HTTPException(status_code=500, detail=f"Cannot auto-detect employees relation (score={score}).")
    return rel, cols


def _departments_relation() -> Tuple[Optional[str], List[str]]:
    rel, cols, _ = _best_relation(_score_departments, min_score=30)
    return rel, cols


def _positions_relation() -> Tuple[Optional[str], List[str]]:
    rel, cols, _ = _best_relation(_score_positions, min_score=30)
    return rel, cols


# ---------------------------
# Column mapping
# ---------------------------
def _employees_id_col(cols: List[str]) -> str:
    c = _pick_first(cols, ["employee_id", "id", "tab_no", "tab_number", "personnel_no", "tn", "tabel"])
    if not c:
        raise HTTPException(status_code=500, detail="Employees relation has no recognizable id column.")
    return c


def _dept_fk_col(cols: List[str]) -> Optional[str]:
    return _pick_first(cols, ["department_id", "dept_id", "org_unit_id"])


def _pos_fk_col(cols: List[str]) -> Optional[str]:
    return _pick_first(cols, ["position_id", "pos_id"])


def _dict_id_col(cols: List[str], preferred: List[str]) -> Optional[str]:
    return _pick_first(cols, preferred + ["id"])


def _dict_name_col(cols: List[str], preferred: List[str]) -> Optional[str]:
    return _pick_first(cols, preferred + ["name", "name_ru"])


def _require_user_id(x_user_id: Optional[str]) -> str:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-Id header.")
    s = str(x_user_id).strip()
    if not s:
        raise HTTPException(status_code=400, detail="Invalid X-User-Id header.")
    return s


# ---------------------------
# RBAC helpers
# ---------------------------
def _load_employee_raw(employee_id_text: str) -> Tuple[Optional[Dict[str, Any]], str, List[str]]:
    rel, cols = _employees_relation()
    id_col = _employees_id_col(cols)
    q = text(f"SELECT * FROM public.{rel} WHERE CAST({id_col} AS TEXT) = :id_text LIMIT 1")
    with engine.begin() as conn:
        row = conn.execute(q, {"id_text": employee_id_text}).mappings().first()
        return (dict(row) if row else None), rel, cols


def _dept_key_from_row(row: Dict[str, Any], cols: List[str]) -> Optional[str]:
    fk = _dept_fk_col(cols)
    if fk and row.get(fk) is not None:
        return str(row.get(fk)).strip().lower()

    # fallback if some schemas store dept name directly
    dn = _pick_first(cols, ["department_name", "dept_name", "org_unit_name", "department"])
    if dn and row.get(dn):
        return str(row.get(dn)).strip().lower()

    return None


def _can_view_employee(viewer_id_text: str, target_id_text: str, target_row: Dict[str, Any], target_cols: List[str]) -> bool:
    if viewer_id_text == target_id_text:
        return True

    viewer_row, _, viewer_cols = _load_employee_raw(viewer_id_text)
    if not viewer_row:
        return False

    viewer_dept = _dept_key_from_row(viewer_row, viewer_cols)
    if not viewer_dept:
        return False

    target_dept = _dept_key_from_row(target_row, target_cols)
    if not target_dept:
        return False

    return viewer_dept == target_dept


# ---------------------------
# Dictionary endpoints
# ---------------------------
@router.get("/departments")
def list_departments(
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> Dict[str, Any]:
    try:
        rel, cols = _departments_relation()
        if not rel:
            return {"items": [], "total": 0}

        id_col = _dict_id_col(cols, ["department_id", "dept_id", "org_unit_id"])
        name_col = _dict_name_col(cols, ["department_name", "dept_name", "org_unit_name"])

        if not id_col or not name_col:
            return {"items": [], "total": 0}

        q_total = text(f"SELECT COUNT(*) AS cnt FROM public.{rel}")
        q_list = text(
            f"""
            SELECT {id_col} AS id, {name_col} AS name
            FROM public.{rel}
            ORDER BY CAST({id_col} AS TEXT) ASC
            LIMIT :limit OFFSET :offset
            """
        )

        with engine.begin() as conn:
            total = int(conn.execute(q_total).mappings().first()["cnt"])
            rows = conn.execute(q_list, {"limit": limit, "offset": offset}).mappings().all()

        items = [{"id": r["id"], "name": r["name"]} for r in rows]
        return {"items": items, "total": total}

    except Exception as e:
        raise _as_http500(e)


@router.get("/positions")
def list_positions(
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> Dict[str, Any]:
    try:
        rel, cols = _positions_relation()
        if not rel:
            return {"items": [], "total": 0}

        id_col = _dict_id_col(cols, ["position_id", "pos_id"])
        name_col = _dict_name_col(cols, ["position_name", "pos_name"])

        if not id_col or not name_col:
            return {"items": [], "total": 0}

        q_total = text(f"SELECT COUNT(*) AS cnt FROM public.{rel}")
        q_list = text(
            f"""
            SELECT {id_col} AS id, {name_col} AS name
            FROM public.{rel}
            ORDER BY CAST({id_col} AS TEXT) ASC
            LIMIT :limit OFFSET :offset
            """
        )

        with engine.begin() as conn:
            total = int(conn.execute(q_total).mappings().first()["cnt"])
            rows = conn.execute(q_list, {"limit": limit, "offset": offset}).mappings().all()

        items = [{"id": r["id"], "name": r["name"]} for r in rows]
        return {"items": items, "total": total}

    except Exception as e:
        raise _as_http500(e)


# ---------------------------
# Employees: list + card (with JOIN-enrichment)
# ---------------------------
def _employee_select_sql(
    emp_rel: str,
    emp_cols: List[str],
) -> Tuple[str, Dict[str, str]]:
    """
    Returns (sql_select_fragment, aliases) where aliases provide names for joined fields.
    We keep it resilient: if dict relations are not detected, return plain employee fields.
    """
    emp_id_col = _employees_id_col(emp_cols)

    fio_col = _pick_first(emp_cols, ["fio", "full_name", "name", "name_ru", "employee_name"])
    last_col = _pick_first(emp_cols, ["last_name", "surname"])
    first_col = _pick_first(emp_cols, ["first_name", "name_first", "given_name"])
    mid_col = _pick_first(emp_cols, ["middle_name", "patronymic"])

    status_col = _pick_first(emp_cols, ["status", "is_active", "active"])
    date_from_col = _pick_first(emp_cols, ["date_from", "start_date", "employment_date", "hired_at"])
    date_to_col = _pick_first(emp_cols, ["date_to", "end_date", "terminated_at", "fired_at"])
    rate_col = _pick_first(emp_cols, ["rate", "stavka", "fte", "workload", "employment_rate"])

    dept_fk = _dept_fk_col(emp_cols)
    pos_fk = _pos_fk_col(emp_cols)

    dep_rel, dep_cols = _departments_relation()
    pos_rel, pos_cols = _positions_relation()

    # detect dict id/name cols
    dep_id_col = _dict_id_col(dep_cols, ["department_id", "dept_id", "org_unit_id"]) if dep_rel else None
    dep_name_col = _dict_name_col(dep_cols, ["department_name", "dept_name", "org_unit_name"]) if dep_rel else None

    pos_id_col = _dict_id_col(pos_cols, ["position_id", "pos_id"]) if pos_rel else None
    pos_name_col = _dict_name_col(pos_cols, ["position_name", "pos_name"]) if pos_rel else None

    select_parts = [
        f"e.{emp_id_col} AS e_id",
        (f"e.{fio_col} AS e_fio" if fio_col else "NULL AS e_fio"),
        (f"e.{last_col} AS e_last" if last_col else "NULL AS e_last"),
        (f"e.{first_col} AS e_first" if first_col else "NULL AS e_first"),
        (f"e.{mid_col} AS e_mid" if mid_col else "NULL AS e_mid"),
        (f"e.{rate_col} AS e_rate" if rate_col else "NULL AS e_rate"),
        (f"e.{status_col} AS e_status" if status_col else "NULL AS e_status"),
        (f"e.{date_from_col} AS e_date_from" if date_from_col else "NULL AS e_date_from"),
        (f"e.{date_to_col} AS e_date_to" if date_to_col else "NULL AS e_date_to"),
        (f"e.{dept_fk} AS e_dept_id" if dept_fk else "NULL AS e_dept_id"),
        (f"e.{pos_fk} AS e_pos_id" if pos_fk else "NULL AS e_pos_id"),
    ]

    join_sql = ""

    # department join
    if dep_rel and dept_fk and dep_id_col and dep_name_col:
        select_parts.append(f"d.{dep_name_col} AS dept_name")
        join_sql += (
            f" LEFT JOIN public.{dep_rel} d"
            f" ON CAST(d.{dep_id_col} AS TEXT) = CAST(e.{dept_fk} AS TEXT)"
        )
    else:
        select_parts.append("NULL AS dept_name")

    # position join
    if pos_rel and pos_fk and pos_id_col and pos_name_col:
        select_parts.append(f"p.{pos_name_col} AS pos_name")
        join_sql += (
            f" LEFT JOIN public.{pos_rel} p"
            f" ON CAST(p.{pos_id_col} AS TEXT) = CAST(e.{pos_fk} AS TEXT)"
        )
    else:
        select_parts.append("NULL AS pos_name")

    sql = "SELECT " + ", ".join(select_parts) + f" FROM public.{emp_rel} e" + join_sql
    return sql, {"emp_id_col": emp_id_col}


def _normalize_employee_joined(row: Dict[str, Any], emp_rel: str) -> Dict[str, Any]:
    # fio fallback
    fio = (str(row.get("e_fio")).strip() if row.get("e_fio") else "").strip()
    if not fio:
        parts = []
        for k in ("e_last", "e_first", "e_mid"):
            if row.get(k):
                parts.append(str(row.get(k)).strip())
        fio = " ".join([p for p in parts if p]) or None

    # status normalize
    status_norm = "unknown"
    v = row.get("e_status")
    if isinstance(v, bool):
        status_norm = "active" if v else "inactive"
    elif v is None:
        status_norm = "unknown"
    else:
        s = str(v).strip().lower()
        if s in ("1", "true", "yes", "y", "on", "active", "работает", "в штате"):
            status_norm = "active"
        elif s in ("0", "false", "no", "n", "off", "inactive", "уволен", "не работает"):
            status_norm = "inactive"
        else:
            status_norm = s

    return {
        "id": str(row.get("e_id")) if row.get("e_id") is not None else None,
        "fio": fio,
        "department": {"id": row.get("e_dept_id"), "name": row.get("dept_name")},
        "position": {"id": row.get("e_pos_id"), "name": row.get("pos_name")},
        "rate": row.get("e_rate"),
        "status": status_norm,
        "date_from": row.get("e_date_from"),
        "date_to": row.get("e_date_to"),
        "source": {"relation": emp_rel},
    }


@router.get("/employees")
def list_employees(
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    status: str = Query(default="active", pattern="^(active|inactive|all)$"),
    q: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Dict[str, Any]:
    try:
        viewer_id_text = _require_user_id(x_user_id)

        emp_rel, emp_cols = _employees_relation()
        emp_id_col = _employees_id_col(emp_cols)

        base_sql, _ = _employee_select_sql(emp_rel, emp_cols)

        # Reuse the same search/status heuristics but now with alias "e."
        status_col = _pick_first(emp_cols, ["status", "is_active", "active"])
        fio_col = _pick_first(emp_cols, ["fio", "full_name", "name", "name_ru", "employee_name"])
        last_col = _pick_first(emp_cols, ["last_name", "surname"])
        first_col = _pick_first(emp_cols, ["first_name", "name_first", "given_name"])
        mid_col = _pick_first(emp_cols, ["middle_name", "patronymic"])

        dept_fk = _dept_fk_col(emp_cols)
        dept_name_direct = _pick_first(emp_cols, ["department_name", "dept_name", "org_unit_name", "department"])

        where: List[str] = []
        params: Dict[str, Any] = {"limit": limit, "offset": offset, "viewer_id_text": viewer_id_text}

        # Status
        if status != "all" and status_col:
            if status_col in ("is_active", "active"):
                where.append(f"e.{status_col} = :is_active")
                params["is_active"] = True if status == "active" else False
            else:
                if status == "active":
                    where.append(f"LOWER(CAST(e.{status_col} AS TEXT)) IN ('active','работает','в штате','1','true','yes')")
                else:
                    where.append(f"LOWER(CAST(e.{status_col} AS TEXT)) IN ('inactive','уволен','не работает','0','false','no')")

        # Search
        if q:
            qq = q.strip().lower()
            params["q"] = f"%{qq}%"
            parts = []
            if fio_col:
                parts.append(f"LOWER(CAST(e.{fio_col} AS TEXT)) LIKE :q")
            if last_col:
                parts.append(f"LOWER(CAST(e.{last_col} AS TEXT)) LIKE :q")
            if first_col:
                parts.append(f"LOWER(CAST(e.{first_col} AS TEXT)) LIKE :q")
            if mid_col:
                parts.append(f"LOWER(CAST(e.{mid_col} AS TEXT)) LIKE :q")
            if parts:
                where.append("(" + " OR ".join(parts) + ")")

        # RBAC
        if _rbac_mode() != "off":
            viewer_row, _, viewer_cols = _load_employee_raw(viewer_id_text)
            viewer_dept = _dept_key_from_row(viewer_row, viewer_cols) if viewer_row else None

            if not viewer_dept:
                where.append(f"CAST(e.{emp_id_col} AS TEXT) = :viewer_id_text")
            else:
                params["viewer_dept"] = viewer_dept
                if dept_fk:
                    where.append(
                        f"(CAST(e.{emp_id_col} AS TEXT) = :viewer_id_text OR LOWER(CAST(e.{dept_fk} AS TEXT)) = :viewer_dept)"
                    )
                elif dept_name_direct:
                    where.append(
                        f"(CAST(e.{emp_id_col} AS TEXT) = :viewer_id_text OR LOWER(CAST(e.{dept_name_direct} AS TEXT)) = :viewer_dept)"
                    )
                else:
                    where.append(f"CAST(e.{emp_id_col} AS TEXT) = :viewer_id_text")

        where_sql = " AND ".join(where) if where else "TRUE"

        q_list = text(
            f"""
            {base_sql}
            WHERE {where_sql}
            ORDER BY CAST(e.{emp_id_col} AS TEXT) ASC
            LIMIT :limit OFFSET :offset
            """
        )

        q_total = text(
            f"""
            SELECT COUNT(*) AS cnt
            FROM public.{emp_rel} e
            WHERE {where_sql}
            """
        )

        with engine.begin() as conn:
            total = int(conn.execute(q_total, params).mappings().first()["cnt"])
            rows = conn.execute(q_list, params).mappings().all()

        items = [_normalize_employee_joined(dict(r), emp_rel) for r in rows]
        return {"items": items, "total": total}

    except HTTPException:
        raise
    except Exception as e:
        raise _as_http500(e)


@router.get("/employees/{employee_id}")
def get_employee(
    employee_id: int = Path(..., ge=1),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    try:
        viewer_id_text = _require_user_id(x_user_id)
        target_id_text = str(employee_id)

        target_row_raw, emp_rel, emp_cols = _load_employee_raw(target_id_text)
        if not target_row_raw:
            raise HTTPException(status_code=404, detail="Employee not found.")

        if _rbac_mode() != "off":
            if not _can_view_employee(viewer_id_text, target_id_text, target_row_raw, emp_cols):
                raise HTTPException(status_code=404, detail="Employee not found.")

        # Fetch the same record but through JOIN select to fill dept/pos names
        emp_id_col = _employees_id_col(emp_cols)
        base_sql, _ = _employee_select_sql(emp_rel, emp_cols)
        q_one = text(
            f"""
            {base_sql}
            WHERE CAST(e.{emp_id_col} AS TEXT) = :id_text
            LIMIT 1
            """
        )
        with engine.begin() as conn:
            row = conn.execute(q_one, {"id_text": target_id_text}).mappings().first()

        if not row:
            # Should not happen, but keep semantics
            raise HTTPException(status_code=404, detail="Employee not found.")

        return _normalize_employee_joined(dict(row), emp_rel)

    except HTTPException:
        raise
    except Exception as e:
        raise _as_http500(e)
