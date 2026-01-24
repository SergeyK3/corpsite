# FILE: app/services/directory_service.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import bindparam, text

from app.db.engine import engine
from app.security.directory_scope import build_dept_scope_cte


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


def _normalize_employee_id_text(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


# ---------------------------
# Dictionaries (read)
# ---------------------------
def list_departments(
    *,
    limit: int,
    offset: int,
    dept_scope_id: Optional[int] = None,
    dept_scope_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    rel, cols = _departments_relation()
    if not rel:
        return {"items": [], "total": 0}

    id_col = _dict_id_col(cols, ["department_id", "dept_id", "org_unit_id"])
    name_col = _dict_name_col(cols, ["department_name", "dept_name", "org_unit_name"])
    if not id_col or not name_col:
        return {"items": [], "total": 0}

    params: Dict[str, Any] = {"limit": limit, "offset": offset}
    where_parts: List[str] = ["TRUE"]

    if dept_scope_ids is not None:
        ids = [int(x) for x in dept_scope_ids]
        if not ids:
            return {"items": [], "total": 0}
        where_parts.append(f"CAST({id_col} AS BIGINT) IN :dept_ids")
        params["dept_ids"] = ids
    elif dept_scope_id is not None:
        where_parts.append(f"CAST({id_col} AS BIGINT) = :dept_id")
        params["dept_id"] = int(dept_scope_id)

    where_sql = " AND ".join(where_parts)

    q_total = text(f"SELECT COUNT(*) AS cnt FROM public.{rel} WHERE {where_sql}")
    q_list = text(
        f"""
        SELECT {id_col} AS id, {name_col} AS name
        FROM public.{rel}
        WHERE {where_sql}
        ORDER BY CAST({id_col} AS TEXT) ASC
        LIMIT :limit OFFSET :offset
        """
    )

    if "dept_ids" in params:
        q_total = q_total.bindparams(bindparam("dept_ids", expanding=True))
        q_list = q_list.bindparams(bindparam("dept_ids", expanding=True))

    with engine.begin() as conn:
        total = int(conn.execute(q_total, params).mappings().first()["cnt"])
        rows = conn.execute(q_list, params).mappings().all()

    items = [{"id": r["id"], "name": r["name"]} for r in rows]
    return {"items": items, "total": total}


def list_positions(*, limit: int, offset: int) -> Dict[str, Any]:
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


# ---------------------------
# Employees select + normalize
# ---------------------------
def _employee_select_sql(emp_rel: str, emp_cols: List[str]) -> Tuple[str, Dict[str, str]]:
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

    # org_unit_id должен существовать (проверяется выше в list/get)
    org_unit_fk = "org_unit_id"

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
        f"e.{org_unit_fk} AS e_org_unit_id",
    ]

    join_sql = ""

    # Departments (auto-detect relation + columns)
    dept_rel, dept_cols = _departments_relation()
    dept_id_col = _dict_id_col(dept_cols, ["department_id", "dept_id", "org_unit_id"]) if dept_rel else None
    dept_name_col = _dict_name_col(dept_cols, ["department_name", "dept_name", "org_unit_name"]) if dept_rel else None

    if dept_fk and dept_rel and dept_id_col and dept_name_col:
        select_parts.append(f"d.{dept_name_col} AS dept_name")
        join_sql += (
            f" LEFT JOIN public.{dept_rel} d"
            f" ON CAST(d.{dept_id_col} AS TEXT) = CAST(e.{dept_fk} AS TEXT)"
        )
    else:
        select_parts.append("NULL AS dept_name")

    # Positions (auto-detect relation + columns)
    pos_rel, pos_cols = _positions_relation()
    pos_id_col = _dict_id_col(pos_cols, ["position_id", "pos_id"]) if pos_rel else None
    pos_name_col = _dict_name_col(pos_cols, ["position_name", "pos_name"]) if pos_rel else None

    if pos_fk and pos_rel and pos_id_col and pos_name_col:
        select_parts.append(f"p.{pos_name_col} AS pos_name")
        join_sql += (
            f" LEFT JOIN public.{pos_rel} p"
            f" ON CAST(p.{pos_id_col} AS TEXT) = CAST(e.{pos_fk} AS TEXT)"
        )
    else:
        select_parts.append("NULL AS pos_name")

    # Org Units (canonical table)
    select_parts += [
        "ou.name AS org_unit_name",
        "ou.code AS org_unit_code",
        "ou.parent_unit_id AS org_unit_parent_unit_id",
        "ou.is_active AS org_unit_is_active",
    ]
    join_sql += " LEFT JOIN public.org_units ou ON ou.unit_id = e.org_unit_id"

    sql = "SELECT " + ", ".join(select_parts) + f" FROM public.{emp_rel} e" + join_sql
    return sql, {"emp_id_col": emp_id_col}


def _normalize_employee_joined(row: Dict[str, Any], emp_rel: str) -> Dict[str, Any]:
    fio = (str(row.get("e_fio")).strip() if row.get("e_fio") else "").strip()
    if not fio:
        parts = []
        for k in ("e_last", "e_first", "e_mid"):
            if row.get(k):
                parts.append(str(row.get(k)).strip())
        fio = " ".join([p for p in parts if p]) or None

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

    org_unit_id = row.get("e_org_unit_id")
    if org_unit_id is not None:
        try:
            org_unit_id = int(org_unit_id)
        except Exception:
            pass

    parent_unit_id = row.get("org_unit_parent_unit_id")
    if parent_unit_id is not None:
        try:
            parent_unit_id = int(parent_unit_id)
        except Exception:
            pass

    org_unit_is_active = row.get("org_unit_is_active")
    if org_unit_is_active is not None:
        org_unit_is_active = bool(org_unit_is_active)

    return {
        "id": str(row.get("e_id")) if row.get("e_id") is not None else None,
        "fio": fio,
        "department": {"id": row.get("e_dept_id"), "name": row.get("dept_name")},
        "position": {"id": row.get("e_pos_id"), "name": row.get("pos_name")},
        "org_unit": {
            "unit_id": org_unit_id,
            "name": row.get("org_unit_name"),
            "code": row.get("org_unit_code"),
            "parent_unit_id": parent_unit_id,
            "is_active": org_unit_is_active,
        },
        "rate": row.get("e_rate"),
        "status": status_norm,
        "date_from": row.get("e_date_from"),
        "date_to": row.get("e_date_to"),
        "source": {"relation": emp_rel},
    }


# ---------------------------
# Employees (read)
# ---------------------------
def list_employees(
    *,
    scope_unit_id: Optional[int] = None,
    scope_unit_ids: Optional[List[int]] = None,
    rbac_scope_unit_id: Optional[int] = None,
    status: str,
    q: Optional[str],
    department_id: Optional[int],
    position_id: Optional[int],
    org_unit_id: Optional[int],
    include_children: bool,
    limit: int,
    offset: int,
    sort: Optional[str],
    order: Optional[str],
) -> Dict[str, Any]:
    emp_rel, emp_cols = _employees_relation()
    emp_id_col = _employees_id_col(emp_cols)

    if "org_unit_id" not in set(emp_cols):
        raise HTTPException(status_code=500, detail="directory: employees has no org_unit_id column.")

    base_sql, _ = _employee_select_sql(emp_rel, emp_cols)

    status_col = _pick_first(emp_cols, ["status", "is_active", "active"])
    fio_col = _pick_first(emp_cols, ["fio", "full_name", "name", "name_ru", "employee_name"])
    last_col = _pick_first(emp_cols, ["last_name", "surname"])
    first_col = _pick_first(emp_cols, ["first_name", "name_first", "given_name"])
    mid_col = _pick_first(emp_cols, ["middle_name", "patronymic"])

    dept_fk = _dept_fk_col(emp_cols)
    pos_fk = _pos_fk_col(emp_cols)

    where: List[str] = []
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    # status filter
    if status != "all" and status_col:
        if status_col in ("is_active", "active"):
            where.append(f"e.{status_col} = :is_active")
            params["is_active"] = True if status == "active" else False
        else:
            if status == "active":
                where.append(
                    f"LOWER(CAST(e.{status_col} AS TEXT)) IN ('active','работает','в штате','1','true','yes')"
                )
            else:
                where.append(
                    f"LOWER(CAST(e.{status_col} AS TEXT)) IN ('inactive','уволен','не работает','0','false','no')"
                )

    # search
    if q:
        qq = q.strip().lower()
        params["q"] = f"%{qq}%"
        parts: List[str] = []
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

    # RBAC dept subtree
    cte_parts: List[str] = []
    cte_prefix = ""

    effective_scope = scope_unit_id if scope_unit_id is not None else rbac_scope_unit_id
    rbac_cte, rbac_where, rbac_params = build_dept_scope_cte(scope_unit_id=effective_scope, alias="e")
    if rbac_cte:
        cte_parts.append(rbac_cte)
        where.append(rbac_where)
        params.update(rbac_params)

    # explicit scope list (groups-mode or precomputed list)
    if scope_unit_ids is not None:
        ids = [int(x) for x in scope_unit_ids]
        if not ids:
            return {"items": [], "total": 0}
        where.append("e.org_unit_id IN :rbac_unit_ids")
        params["rbac_unit_ids"] = ids

    # filter by org_unit_id (+ optionally children)
    if org_unit_id is not None:
        params["org_unit_id"] = int(org_unit_id)
        if include_children:
            # NOTE: this is a recursive CTE fragment (subtree references itself), so it must live under WITH RECURSIVE.
            cte_parts.append(
                """
                subtree AS (
                    SELECT unit_id
                    FROM public.org_units
                    WHERE unit_id = :org_unit_id
                    UNION ALL
                    SELECT ou.unit_id
                    FROM public.org_units ou
                    JOIN subtree s ON ou.parent_unit_id = s.unit_id
                )
                """.strip()
            )
            where.append("e.org_unit_id IN (SELECT unit_id FROM subtree)")
        else:
            where.append("e.org_unit_id = :org_unit_id")

    # stitch CTEs into a single WITH RECURSIVE ...
    if cte_parts:
        normalized: List[str] = []
        for p in cte_parts:
            p2 = p.strip()
            if p2.lower().startswith("with recursive"):
                p2 = p2[len("with recursive") :].strip()
            normalized.append(p2.strip().lstrip(","))
        cte_prefix = "WITH RECURSIVE\n" + ",\n".join([x for x in normalized if x])

    # department/position filters
    if department_id is not None and dept_fk:
        where.append(f"CAST(e.{dept_fk} AS TEXT) = :department_id_text")
        params["department_id_text"] = str(int(department_id))

    if position_id is not None and pos_fk:
        where.append(f"CAST(e.{pos_fk} AS TEXT) = :position_id_text")
        params["position_id_text"] = str(int(position_id))

    where_sql = " AND ".join(where) if where else "TRUE"

    # order
    ord_dir = "ASC" if (order or "").lower() != "desc" else "DESC"
    if (sort or "").lower() in ("full_name", "fio", "name") and fio_col:
        order_sql = f"LOWER(CAST(e.{fio_col} AS TEXT)) {ord_dir}, CAST(e.{emp_id_col} AS TEXT) ASC"
    elif (sort or "").lower() in ("full_name", "fio", "name") and last_col:
        if first_col:
            order_sql = (
                f"LOWER(CAST(e.{last_col} AS TEXT)) {ord_dir}, "
                f"LOWER(CAST(e.{first_col} AS TEXT)) {ord_dir}"
            )
        else:
            order_sql = f"LOWER(CAST(e.{last_col} AS TEXT)) {ord_dir}"
    else:
        order_sql = f"CAST(e.{emp_id_col} AS TEXT) ASC"

    q_list = text(
        f"""
        {cte_prefix}
        {base_sql}
        WHERE {where_sql}
        ORDER BY {order_sql}
        LIMIT :limit OFFSET :offset
        """
    )

    q_total = text(
        f"""
        {cte_prefix}
        SELECT COUNT(*) AS cnt
        FROM public.{emp_rel} e
        WHERE {where_sql}
        """
    )

    if "rbac_unit_ids" in params:
        q_list = q_list.bindparams(bindparam("rbac_unit_ids", expanding=True))
        q_total = q_total.bindparams(bindparam("rbac_unit_ids", expanding=True))

    with engine.begin() as conn:
        total = int(conn.execute(q_total, params).mappings().first()["cnt"])
        rows = conn.execute(q_list, params).mappings().all()

    items = [_normalize_employee_joined(dict(r), emp_rel) for r in rows]
    return {"items": items, "total": total}


def get_employee(
    *,
    scope_unit_id: Optional[int] = None,
    scope_unit_ids: Optional[List[int]] = None,
    rbac_scope_unit_id: Optional[int] = None,
    employee_id: str,
) -> Dict[str, Any]:
    target_id_text = _normalize_employee_id_text(employee_id)
    if not target_id_text:
        raise HTTPException(status_code=404, detail="Employee not found.")

    emp_rel, emp_cols = _employees_relation()
    emp_id_col = _employees_id_col(emp_cols)

    if "org_unit_id" not in set(emp_cols):
        raise HTTPException(status_code=500, detail="directory: employees has no org_unit_id column.")

    base_sql, _ = _employee_select_sql(emp_rel, emp_cols)

    where = [f"CAST(e.{emp_id_col} AS TEXT) = :id_text"]
    params: Dict[str, Any] = {"id_text": target_id_text}

    effective_scope = scope_unit_id if scope_unit_id is not None else rbac_scope_unit_id
    rbac_cte, rbac_where, rbac_params = build_dept_scope_cte(scope_unit_id=effective_scope, alias="e")
    if rbac_cte:
        params.update(rbac_params)
        where.append(rbac_where)

    if scope_unit_ids is not None:
        ids = [int(x) for x in scope_unit_ids]
        if not ids:
            raise HTTPException(status_code=404, detail="Employee not found.")
        where.append("e.org_unit_id IN :rbac_unit_ids")
        params["rbac_unit_ids"] = ids

    q_one = text(
        f"""
        {rbac_cte}
        {base_sql}
        WHERE {' AND '.join(where)}
        LIMIT 1
        """
    )

    if "rbac_unit_ids" in params:
        q_one = q_one.bindparams(bindparam("rbac_unit_ids", expanding=True))

    with engine.begin() as conn:
        row = conn.execute(q_one, params).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Employee not found.")

    return _normalize_employee_joined(dict(row), emp_rel)
