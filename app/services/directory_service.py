# FILE: app/services/directory_service.py
from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import bindparam, text

from app.db.engine import engine
from app.services.hr_event_registry import get_event_class, get_event_label
from app.services.personnel_orders_query_service import personnel_orders_available
from app.org_scope.apply import apply_org_scope
from app.org_scope.types import OrgScopeParams, OrgScopeStrategy
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


def _fetch_linked_user(employee_id: Any) -> Optional[Dict[str, Any]]:
    if employee_id is None:
        return None
    try:
        emp_id = int(employee_id)
    except (TypeError, ValueError):
        return None

    q = text(
        """
        SELECT
            u.user_id,
            u.login,
            u.role_id,
            r.name AS role_name,
            u.is_active,
            u.telegram_id,
            u.telegram_username
        FROM public.users u
        LEFT JOIN public.roles r
          ON r.role_id = u.role_id
        WHERE u.employee_id = :employee_id
        LIMIT 1
        """
    )
    with engine.begin() as conn:
        row = conn.execute(q, {"employee_id": emp_id}).mappings().first()

    if not row:
        return None

    role_id_raw = row.get("role_id")
    tg_id_raw = row.get("telegram_id")
    telegram_id: Optional[int] = None
    if tg_id_raw is not None:
        try:
            tg_id = int(tg_id_raw)
            if tg_id > 0:
                telegram_id = tg_id
        except (TypeError, ValueError):
            pass

    tg_username_raw = row.get("telegram_username")
    telegram_username = (
        str(tg_username_raw).strip() if tg_username_raw is not None else None
    )
    if telegram_username == "":
        telegram_username = None

    return {
        "user_id": int(row["user_id"]),
        "login": str(row["login"]).strip() if row.get("login") is not None else None,
        "role_id": int(role_id_raw) if role_id_raw is not None else None,
        "role_name": str(row["role_name"]).strip() if row.get("role_name") is not None else None,
        "is_active": bool(row.get("is_active")),
        "telegram_id": telegram_id,
        "telegram_username": telegram_username,
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
    org_group_id: Optional[int] = None,
    org_unit_id: Optional[int] = None,
    include_children: bool = False,
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
        parts: List[str] = [f"LOWER(CAST(e.{emp_id_col} AS TEXT)) LIKE :q"]
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

    # org_unit_id filtering (3a-2 backward-compatible):
    # - legacy exact match when only org_unit_id is passed with include_children=false;
    # - unified subtree via apply_org_scope when include_children=true or org_group_id is set
    #   (frontend sidebar passes include_children=true).
    org_scope_unit_id: Optional[int] = None
    if org_unit_id is not None:
        unit_id_int = int(org_unit_id)
        if include_children or org_group_id is not None:
            org_scope_unit_id = unit_id_int
        else:
            params["org_unit_id"] = unit_id_int
            where.append("e.org_unit_id = :org_unit_id")

    if org_group_id is not None or org_scope_unit_id is not None:
        org_scope = apply_org_scope(
            strategy=OrgScopeStrategy.OWNER_UNIT,
            params=OrgScopeParams(
                org_group_id=int(org_group_id) if org_group_id is not None else None,
                org_unit_id=org_scope_unit_id,
            ),
            regular_task_alias="e",
            owner_unit_column="org_unit_id",
        )
        params.update(org_scope.params)
        if org_scope.where_sql != "TRUE":
            where.append(f"({org_scope.where_sql})")
        if org_scope.cte_sql:
            cte_parts.append(org_scope.cte_sql)

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

    result = _normalize_employee_joined(dict(row), emp_rel)
    result["user"] = _fetch_linked_user(row.get("e_id"))
    return result


def create_employee(
    *,
    full_name: str,
    org_unit_id: int,
    position_id: int,
    date_from: Optional[date] = None,
    employment_rate: Optional[float] = None,
    department_id: Optional[int] = None,
    created_by: int,
) -> str:
    normalized_name = " ".join((full_name or "").split()).strip()
    if not normalized_name:
        raise HTTPException(status_code=422, detail="full_name is required.")

    hired_on = date_from if date_from is not None else date.today()
    rate = 1.0 if employment_rate is None else float(employment_rate)

    q_insert = text(
        """
        INSERT INTO public.employees (
            full_name,
            org_unit_id,
            position_id,
            date_from,
            employment_rate,
            is_active,
            department_id
        )
        VALUES (
            :full_name,
            :org_unit_id,
            :position_id,
            :date_from,
            :employment_rate,
            TRUE,
            :department_id
        )
        RETURNING employee_id
        """
    )

    with engine.begin() as conn:
        row = conn.execute(
            q_insert,
            {
                "full_name": normalized_name,
                "org_unit_id": int(org_unit_id),
                "position_id": int(position_id),
                "date_from": hired_on,
                "employment_rate": rate,
                "department_id": int(department_id) if department_id is not None else None,
            },
        ).mappings().first()

        if not row or row.get("employee_id") is None:
            raise HTTPException(status_code=500, detail="create employee failed")

        emp_id = int(row["employee_id"])
        _insert_employee_event(
            conn,
            employee_id=emp_id,
            event_type="HIRE",
            event_class=get_event_class("HIRE"),
            lifecycle_status="APPROVED",
            metadata=None,
            effective_date=hired_on,
            from_org_unit_id=None,
            from_position_id=None,
            from_rate=None,
            to_org_unit_id=int(org_unit_id),
            to_position_id=int(position_id),
            to_rate=rate,
            order_ref=None,
            comment=None,
            created_by=int(created_by),
        )

    return str(emp_id)


def terminate_employee(
    *,
    employee_id: str,
    date_to: Optional[date] = None,
    created_by: int,
) -> str:
    """
    Terminate employee (HR record) and deactivate linked user account if present.

    Idempotency for date_to:
    - first call: date_to = provided value or today;
    - repeat without date_to in request: keep existing date_to;
    - repeat with date_to in request: update date_to to the provided value.
    """
    target_id_text = _normalize_employee_id_text(employee_id)
    if not target_id_text:
        raise HTTPException(status_code=404, detail="Employee not found.")

    q_fetch = text(
        """
        SELECT
            employee_id,
            org_unit_id,
            position_id,
            employment_rate,
            is_active,
            date_to
        FROM public.employees
        WHERE CAST(employee_id AS TEXT) = :id_text
        FOR UPDATE
        """
    )
    q_update_employee = text(
        """
        UPDATE public.employees
        SET is_active = FALSE,
            date_to = :date_to
        WHERE employee_id = :employee_id
        """
    )
    q_deactivate_user = text(
        """
        UPDATE public.users
        SET is_active = FALSE
        WHERE employee_id = :employee_id
        """
    )

    with engine.begin() as conn:
        row = conn.execute(q_fetch, {"id_text": target_id_text}).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Employee not found.")

        emp_id = int(row["employee_id"])
        already_inactive = row.get("is_active") is False

        if already_inactive and date_to is None and row.get("date_to") is not None:
            effective_date_to = row["date_to"]
        elif date_to is not None:
            effective_date_to = date_to
        else:
            effective_date_to = date.today()

        conn.execute(
            q_update_employee,
            {"employee_id": emp_id, "date_to": effective_date_to},
        )
        conn.execute(q_deactivate_user, {"employee_id": emp_id})

        if not already_inactive:
            from_rate_raw = row.get("employment_rate")
            from_rate = float(from_rate_raw) if from_rate_raw is not None else None
            from_position_raw = row.get("position_id")
            from_position_id = int(from_position_raw) if from_position_raw is not None else None
            _insert_employee_event(
                conn,
                employee_id=emp_id,
                event_type="TERMINATION",
                event_class=get_event_class("TERMINATION"),
                lifecycle_status="APPROVED",
                metadata=None,
                effective_date=effective_date_to,
                from_org_unit_id=int(row["org_unit_id"]),
                from_position_id=from_position_id,
                from_rate=from_rate,
                to_org_unit_id=None,
                to_position_id=None,
                to_rate=None,
                order_ref=None,
                comment=None,
                created_by=int(created_by),
            )

    return target_id_text


_PERSONNEL_PATCH_FORBIDDEN_MSG = "Use personnel event instead of direct employee patch"


def update_employee(
    *,
    employee_id: str,
    full_name: Optional[str] = None,
    employment_rate: Optional[float] = None,
    date_from: Optional[date] = None,
    position_id: Optional[int] = None,
) -> str:
    target_id_text = _normalize_employee_id_text(employee_id)
    if not target_id_text:
        raise HTTPException(status_code=404, detail="Employee not found.")

    if all(v is None for v in (full_name, employment_rate, date_from, position_id)):
        raise HTTPException(status_code=422, detail="At least one field is required.")

    if employment_rate is not None or date_from is not None or position_id is not None:
        raise HTTPException(status_code=422, detail=_PERSONNEL_PATCH_FORBIDDEN_MSG)

    q_fetch = text(
        """
        SELECT employee_id
        FROM public.employees
        WHERE CAST(employee_id AS TEXT) = :id_text
        LIMIT 1
        """
    )

    with engine.begin() as conn:
        row = conn.execute(q_fetch, {"id_text": target_id_text}).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Employee not found.")

        emp_id = int(row["employee_id"])

        if full_name is None:
            raise HTTPException(status_code=422, detail="At least one field is required.")

        normalized_name = " ".join((full_name or "").split()).strip()
        if not normalized_name:
            raise HTTPException(status_code=422, detail="full_name is required.")

        conn.execute(
            text(
                """
                UPDATE public.employees
                SET full_name = :full_name
                WHERE employee_id = :employee_id
                """
            ),
            {"employee_id": emp_id, "full_name": normalized_name},
        )

    return target_id_text


# ---------------------------
# Employee events (Phase 3b)
# ---------------------------
def _insert_employee_event(
    conn,
    *,
    employee_id: int,
    event_type: str,
    event_class: str,
    lifecycle_status: str,
    metadata: Optional[Dict[str, Any]],
    effective_date: date,
    from_org_unit_id: Optional[int],
    from_position_id: Optional[int],
    from_rate: Optional[float],
    to_org_unit_id: Optional[int],
    to_position_id: Optional[int],
    to_rate: Optional[float],
    order_ref: Optional[str],
    comment: Optional[str],
    created_by: int,
    order_id: Optional[int] = None,
    order_item_id: Optional[int] = None,
) -> Dict[str, Any]:
    metadata_json = json.dumps(metadata) if metadata is not None else None
    q_insert_event = text(
        """
        INSERT INTO public.employee_events (
            employee_id,
            event_type,
            event_class,
            lifecycle_status,
            metadata,
            effective_date,
            from_org_unit_id,
            from_position_id,
            from_rate,
            to_org_unit_id,
            to_position_id,
            to_rate,
            order_ref,
            order_id,
            order_item_id,
            comment,
            created_by
        )
        VALUES (
            :employee_id,
            :event_type,
            :event_class,
            :lifecycle_status,
            CAST(:metadata AS jsonb),
            :effective_date,
            :from_org_unit_id,
            :from_position_id,
            :from_rate,
            :to_org_unit_id,
            :to_position_id,
            :to_rate,
            :order_ref,
            :order_id,
            :order_item_id,
            :comment,
            :created_by
        )
        RETURNING
            event_id,
            event_type,
            event_class,
            lifecycle_status,
            metadata,
            effective_date,
            from_org_unit_id,
            from_position_id,
            from_rate,
            to_org_unit_id,
            to_position_id,
            to_rate,
            order_ref,
            order_id,
            order_item_id,
            comment,
            created_by,
            created_at
        """
    )
    event_row = conn.execute(
        q_insert_event,
        {
            "employee_id": int(employee_id),
            "event_type": event_type,
            "event_class": event_class,
            "lifecycle_status": lifecycle_status,
            "metadata": metadata_json,
            "effective_date": effective_date,
            "from_org_unit_id": from_org_unit_id,
            "from_position_id": from_position_id,
            "from_rate": from_rate,
            "to_org_unit_id": to_org_unit_id,
            "to_position_id": to_position_id,
            "to_rate": to_rate,
            "order_ref": order_ref,
            "order_id": int(order_id) if order_id is not None else None,
            "order_item_id": int(order_item_id) if order_item_id is not None else None,
            "comment": comment,
            "created_by": int(created_by),
        },
    ).mappings().first()
    if not event_row:
        raise HTTPException(status_code=500, detail="Failed to record employee event.")
    return _normalize_employee_event(dict(event_row))


def _normalize_employee_event(row: Dict[str, Any]) -> Dict[str, Any]:
    def _rate(v: Any) -> Optional[float]:
        if v is None:
            return None
        if isinstance(v, Decimal):
            return float(v)
        return float(v)

    effective = row.get("effective_date")
    created_at = row.get("created_at")
    event_type = str(row["event_type"])
    metadata_raw = row.get("metadata")
    metadata: Optional[Dict[str, Any]] = None
    if metadata_raw is not None:
        if isinstance(metadata_raw, dict):
            metadata = metadata_raw
        elif isinstance(metadata_raw, str):
            try:
                metadata = json.loads(metadata_raw)
            except json.JSONDecodeError:
                metadata = None

    event_class = row.get("event_class")
    if event_class is not None:
        event_class = str(event_class)
    else:
        event_class = get_event_class(event_type)

    lifecycle_status = row.get("lifecycle_status")
    if lifecycle_status is not None:
        lifecycle_status = str(lifecycle_status)
    else:
        lifecycle_status = "APPROVED"

    order_id = row.get("order_id")
    order_item_id = row.get("order_item_id")
    order_number = row.get("order_number")
    order_date = row.get("order_date")
    order_status = row.get("order_status")
    order_item_number = row.get("order_item_number")

    normalized: Dict[str, Any] = {
        "event_id": int(row["event_id"]),
        "event_type": event_type,
        "event_class": event_class,
        "event_label": get_event_label(event_type),
        "lifecycle_status": lifecycle_status,
        "metadata": metadata,
        "effective_date": effective.isoformat() if hasattr(effective, "isoformat") else effective,
        "from_org_unit_id": int(row["from_org_unit_id"]) if row.get("from_org_unit_id") is not None else None,
        "to_org_unit_id": int(row["to_org_unit_id"]) if row.get("to_org_unit_id") is not None else None,
        "from_position_id": int(row["from_position_id"]) if row.get("from_position_id") is not None else None,
        "to_position_id": int(row["to_position_id"]) if row.get("to_position_id") is not None else None,
        "from_rate": _rate(row.get("from_rate")),
        "to_rate": _rate(row.get("to_rate")),
        "order_ref": row.get("order_ref"),
        "comment": row.get("comment"),
        "created_by": int(row["created_by"]),
        "created_at": (
            created_at.isoformat()
            if isinstance(created_at, datetime)
            else created_at
        ),
    }

    if order_id is not None:
        normalized["order_id"] = int(order_id)
    if order_item_id is not None:
        normalized["order_item_id"] = int(order_item_id)
    if order_number is not None:
        normalized["order_number"] = str(order_number)
    if order_date is not None:
        normalized["order_date"] = (
            order_date.isoformat() if hasattr(order_date, "isoformat") else str(order_date)
        )
    if order_status is not None:
        normalized["order_status"] = str(order_status)
    if order_item_number is not None:
        normalized["order_item_number"] = int(order_item_number)

    return normalized


def _employee_events_order_columns_available() -> bool:
    with engine.begin() as conn:
        cols = {
            r[0]
            for r in conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'employee_events'
                    """
                )
            ).all()
        }
        return "order_id" in cols and "order_item_id" in cols


def _employee_events_list_select_sql(*, include_order_linkage: bool) -> str:
    base_columns = """
            ev.event_id,
            ev.event_type,
            ev.event_class,
            ev.lifecycle_status,
            ev.metadata,
            ev.effective_date,
            ev.from_org_unit_id,
            ev.from_position_id,
            ev.from_rate,
            ev.to_org_unit_id,
            ev.to_position_id,
            ev.to_rate,
            ev.order_ref,
            ev.comment,
            ev.created_by,
            ev.created_at
    """
    if not include_order_linkage:
        return base_columns

    order_columns = """
            ev.order_id,
            ev.order_item_id
    """
    if personnel_orders_available():
        return f"""
            {base_columns},
            {order_columns},
            po.order_number,
            po.order_date,
            po.status AS order_status,
            poi.item_number AS order_item_number
        """

    return f"""
            {base_columns},
            {order_columns}
    """


def _employee_events_list_from_sql(*, include_order_linkage: bool) -> str:
    if not include_order_linkage:
        return "public.employee_events ev"

    if personnel_orders_available():
        return """
            public.employee_events ev
            LEFT JOIN public.personnel_orders po ON po.order_id = ev.order_id
            LEFT JOIN public.personnel_order_items poi ON poi.item_id = ev.order_item_id
        """

    return "public.employee_events ev"


def _apply_employee_org_change(
    *,
    employee_id: str,
    event_type: str,
    to_org_unit_id: int,
    to_position_id: Optional[int],
    to_employment_rate: Optional[float],
    effective_date: date,
    order_ref: Optional[str],
    comment: Optional[str],
    created_by: int,
    require_active: bool,
    require_different_org_unit: bool,
) -> Dict[str, Any]:
    target_id_text = _normalize_employee_id_text(employee_id)
    if not target_id_text:
        raise HTTPException(status_code=404, detail="Employee not found.")

    q_fetch = text(
        """
        SELECT
            employee_id,
            org_unit_id,
            position_id,
            employment_rate,
            is_active
        FROM public.employees
        WHERE CAST(employee_id AS TEXT) = :id_text
        FOR UPDATE
        """
    )
    q_org_unit = text(
        """
        SELECT unit_id
        FROM public.org_units
        WHERE unit_id = :unit_id
        LIMIT 1
        """
    )
    q_position = text(
        """
        SELECT position_id
        FROM public.positions
        WHERE position_id = :position_id
        LIMIT 1
        """
    )
    q_update_employee = text(
        """
        UPDATE public.employees
        SET org_unit_id = :org_unit_id,
            position_id = :position_id,
            employment_rate = :employment_rate
        WHERE employee_id = :employee_id
        """
    )
    q_update_user_unit = text(
        """
        UPDATE public.users
        SET unit_id = :unit_id
        WHERE employee_id = :employee_id
        """
    )

    with engine.begin() as conn:
        row = conn.execute(q_fetch, {"id_text": target_id_text}).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Employee not found.")

        emp_id = int(row["employee_id"])
        is_active = row.get("is_active")
        if require_active and is_active is False:
            raise HTTPException(status_code=409, detail="Employee is inactive.")

        from_org_unit_id = int(row["org_unit_id"])
        from_position_raw = row.get("position_id")
        from_position_id = int(from_position_raw) if from_position_raw is not None else None
        from_rate_raw = row.get("employment_rate")
        from_rate = float(from_rate_raw) if from_rate_raw is not None else None

        org_row = conn.execute(q_org_unit, {"unit_id": int(to_org_unit_id)}).first()
        if org_row is None:
            raise HTTPException(status_code=404, detail="Org unit not found.")

        if to_position_id is not None:
            effective_to_position_id = int(to_position_id)
        elif from_position_id is not None:
            effective_to_position_id = from_position_id
        else:
            raise HTTPException(
                status_code=422,
                detail="Current position is missing; choose target position",
            )
        pos_row = conn.execute(q_position, {"position_id": effective_to_position_id}).first()
        if pos_row is None:
            raise HTTPException(status_code=404, detail="Position not found.")

        if to_employment_rate is not None:
            effective_to_rate = float(to_employment_rate)
            if effective_to_rate <= 0 or effective_to_rate > 2:
                raise HTTPException(status_code=422, detail="employment_rate must be > 0 and <= 2.")
        else:
            effective_to_rate = from_rate if from_rate is not None else 1.0

        if require_different_org_unit and from_org_unit_id == int(to_org_unit_id):
            raise HTTPException(
                status_code=422,
                detail="to_org_unit_id must differ from current org unit for transfer.",
            )

        if not require_different_org_unit:
            position_changed = to_position_id is not None and (
                from_position_id is None or int(to_position_id) != from_position_id
            )
            org_changed = from_org_unit_id != int(to_org_unit_id)
            if not org_changed and not position_changed:
                raise HTTPException(status_code=422, detail="At least one of org unit or position must change.")

        conn.execute(
            q_update_employee,
            {
                "employee_id": emp_id,
                "org_unit_id": int(to_org_unit_id),
                "position_id": effective_to_position_id,
                "employment_rate": effective_to_rate,
            },
        )
        conn.execute(
            q_update_user_unit,
            {"employee_id": emp_id, "unit_id": int(to_org_unit_id)},
        )

        event_row = _insert_employee_event(
            conn,
            employee_id=emp_id,
            event_type=event_type,
            event_class=get_event_class(event_type),
            lifecycle_status="APPROVED",
            metadata=None,
            effective_date=effective_date,
            from_org_unit_id=from_org_unit_id,
            from_position_id=from_position_id,
            from_rate=from_rate,
            to_org_unit_id=int(to_org_unit_id),
            to_position_id=effective_to_position_id,
            to_rate=effective_to_rate,
            order_ref=order_ref,
            comment=comment,
            created_by=int(created_by),
        )

    return event_row


def transfer_employee(
    *,
    employee_id: str,
    to_org_unit_id: int,
    to_position_id: Optional[int] = None,
    to_employment_rate: Optional[float] = None,
    effective_date: date,
    order_ref: Optional[str] = None,
    comment: Optional[str] = None,
    created_by: int,
) -> Dict[str, Any]:
    from app.services.personnel_events_service import create_personnel_event

    return create_personnel_event(
        employee_id=employee_id,
        event_type="TRANSFER",
        payload={
            "to_org_unit_id": to_org_unit_id,
            "to_position_id": to_position_id,
            "to_employment_rate": to_employment_rate,
            "effective_date": effective_date,
            "order_ref": order_ref,
            "comment": comment,
        },
        created_by=created_by,
    )


def correct_employee_org_unit(
    *,
    employee_id: str,
    to_org_unit_id: int,
    to_position_id: Optional[int] = None,
    effective_date: date,
    comment: str,
    created_by: int,
) -> Dict[str, Any]:
    normalized_comment = (comment or "").strip()
    if not normalized_comment:
        raise HTTPException(status_code=422, detail="comment is required.")

    return _apply_employee_org_change(
        employee_id=employee_id,
        event_type="CORRECTION",
        to_org_unit_id=to_org_unit_id,
        to_position_id=to_position_id,
        to_employment_rate=None,
        effective_date=effective_date,
        order_ref=None,
        comment=normalized_comment,
        created_by=created_by,
        require_active=False,
        require_different_org_unit=False,
    )


def _correction_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float, str, bool)):
        return value
    return str(value)


def _append_correction_change(
    changes: Dict[str, Dict[str, Any]],
    field: str,
    from_value: Any,
    to_value: Any,
) -> None:
    if from_value == to_value:
        return
    changes[field] = {"from": _correction_value(from_value), "to": _correction_value(to_value)}


def _validate_correction_comment_reason(*, comment: str, reason: str) -> Tuple[str, str]:
    normalized_comment = (comment or "").strip()
    normalized_reason = (reason or "").strip()
    if not normalized_comment:
        raise HTTPException(status_code=422, detail="comment is required.")
    if not normalized_reason:
        raise HTTPException(status_code=422, detail="reason is required.")
    return normalized_comment, normalized_reason


def _correct_employee_general(
    *,
    employee_id: str,
    full_name: str,
    effective_date: date,
    reason: str,
    comment: str,
    created_by: int,
) -> Dict[str, Any]:
    target_id_text = _normalize_employee_id_text(employee_id)
    if not target_id_text:
        raise HTTPException(status_code=404, detail="Employee not found.")

    normalized_name = " ".join((full_name or "").split()).strip()
    if not normalized_name:
        raise HTTPException(status_code=422, detail="full_name is required.")

    q_fetch = text(
        """
        SELECT
            employee_id,
            full_name,
            org_unit_id,
            position_id,
            employment_rate
        FROM public.employees
        WHERE CAST(employee_id AS TEXT) = :id_text
        FOR UPDATE
        """
    )

    with engine.begin() as conn:
        row = conn.execute(q_fetch, {"id_text": target_id_text}).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Employee not found.")

        emp_id = int(row["employee_id"])
        from_name = str(row["full_name"])
        if from_name == normalized_name:
            raise HTTPException(status_code=422, detail="No changes detected.")

        changes: Dict[str, Dict[str, Any]] = {}
        _append_correction_change(changes, "full_name", from_name, normalized_name)
        metadata = {"domain": "general", "reason": reason, "changes": changes}

        conn.execute(
            text(
                """
                UPDATE public.employees
                SET full_name = :full_name
                WHERE employee_id = :employee_id
                """
            ),
            {"employee_id": emp_id, "full_name": normalized_name},
        )

        from_position_raw = row.get("position_id")
        from_position_id = int(from_position_raw) if from_position_raw is not None else None
        from_rate_raw = row.get("employment_rate")
        from_rate = float(from_rate_raw) if from_rate_raw is not None else None

        return _insert_employee_event(
            conn,
            employee_id=emp_id,
            event_type="CORRECTION",
            event_class=get_event_class("CORRECTION"),
            lifecycle_status="APPROVED",
            metadata=metadata,
            effective_date=effective_date,
            from_org_unit_id=int(row["org_unit_id"]),
            from_position_id=from_position_id,
            from_rate=from_rate,
            to_org_unit_id=int(row["org_unit_id"]),
            to_position_id=from_position_id,
            to_rate=from_rate,
            order_ref=None,
            comment=comment,
            created_by=int(created_by),
        )


def _correct_employee_assignment(
    *,
    employee_id: str,
    org_unit_id: int,
    position_id: Optional[int],
    employment_rate: Optional[float],
    date_from: Optional[date],
    date_to: Optional[date],
    effective_date: date,
    reason: str,
    comment: str,
    created_by: int,
) -> Dict[str, Any]:
    target_id_text = _normalize_employee_id_text(employee_id)
    if not target_id_text:
        raise HTTPException(status_code=404, detail="Employee not found.")

    q_fetch = text(
        """
        SELECT
            employee_id,
            org_unit_id,
            position_id,
            employment_rate,
            date_from,
            date_to
        FROM public.employees
        WHERE CAST(employee_id AS TEXT) = :id_text
        FOR UPDATE
        """
    )
    q_org_unit = text(
        """
        SELECT unit_id
        FROM public.org_units
        WHERE unit_id = :unit_id
        LIMIT 1
        """
    )
    q_position = text(
        """
        SELECT position_id
        FROM public.positions
        WHERE position_id = :position_id
        LIMIT 1
        """
    )
    q_update_employee = text(
        """
        UPDATE public.employees
        SET org_unit_id = :org_unit_id,
            position_id = :position_id,
            employment_rate = :employment_rate,
            date_from = :date_from,
            date_to = :date_to
        WHERE employee_id = :employee_id
        """
    )
    q_update_user_unit = text(
        """
        UPDATE public.users
        SET unit_id = :unit_id
        WHERE employee_id = :employee_id
        """
    )

    with engine.begin() as conn:
        row = conn.execute(q_fetch, {"id_text": target_id_text}).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Employee not found.")

        emp_id = int(row["employee_id"])
        from_org_unit_id = int(row["org_unit_id"])
        from_position_raw = row.get("position_id")
        from_position_id = int(from_position_raw) if from_position_raw is not None else None
        from_rate_raw = row.get("employment_rate")
        from_rate = float(from_rate_raw) if from_rate_raw is not None else None
        from_date_from = row.get("date_from")
        from_date_to = row.get("date_to")

        org_row = conn.execute(q_org_unit, {"unit_id": int(org_unit_id)}).first()
        if org_row is None:
            raise HTTPException(status_code=404, detail="Org unit not found.")

        if position_id is not None:
            effective_to_position_id = int(position_id)
        elif from_position_id is not None:
            effective_to_position_id = from_position_id
        else:
            raise HTTPException(
                status_code=422,
                detail="Current position is missing; choose target position",
            )

        pos_row = conn.execute(q_position, {"position_id": effective_to_position_id}).first()
        if pos_row is None:
            raise HTTPException(status_code=404, detail="Position not found.")

        if employment_rate is not None:
            effective_to_rate = float(employment_rate)
            if effective_to_rate <= 0 or effective_to_rate > 2:
                raise HTTPException(status_code=422, detail="employment_rate must be > 0 and <= 2.")
        else:
            effective_to_rate = from_rate if from_rate is not None else 1.0

        effective_date_from = date_from
        effective_date_to = date_to

        changes: Dict[str, Dict[str, Any]] = {}
        _append_correction_change(changes, "org_unit_id", from_org_unit_id, int(org_unit_id))
        _append_correction_change(changes, "position_id", from_position_id, effective_to_position_id)
        _append_correction_change(changes, "employment_rate", from_rate, effective_to_rate)
        _append_correction_change(changes, "date_from", from_date_from, effective_date_from)
        _append_correction_change(changes, "date_to", from_date_to, effective_date_to)

        if not changes:
            raise HTTPException(status_code=422, detail="No changes detected.")

        metadata = {"domain": "assignment", "reason": reason, "changes": changes}

        conn.execute(
            q_update_employee,
            {
                "employee_id": emp_id,
                "org_unit_id": int(org_unit_id),
                "position_id": effective_to_position_id,
                "employment_rate": effective_to_rate,
                "date_from": effective_date_from,
                "date_to": effective_date_to,
            },
        )

        if from_org_unit_id != int(org_unit_id):
            conn.execute(
                q_update_user_unit,
                {"employee_id": emp_id, "unit_id": int(org_unit_id)},
            )

        return _insert_employee_event(
            conn,
            employee_id=emp_id,
            event_type="CORRECTION",
            event_class=get_event_class("CORRECTION"),
            lifecycle_status="APPROVED",
            metadata=metadata,
            effective_date=effective_date,
            from_org_unit_id=from_org_unit_id,
            from_position_id=from_position_id,
            from_rate=from_rate,
            to_org_unit_id=int(org_unit_id),
            to_position_id=effective_to_position_id,
            to_rate=effective_to_rate,
            order_ref=None,
            comment=comment,
            created_by=int(created_by),
        )


def correct_employee(
    *,
    employee_id: str,
    domain: str,
    effective_date: date,
    reason: str,
    comment: str,
    created_by: int,
    full_name: Optional[str] = None,
    org_unit_id: Optional[int] = None,
    position_id: Optional[int] = None,
    employment_rate: Optional[float] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> Dict[str, Any]:
    normalized_comment, normalized_reason = _validate_correction_comment_reason(
        comment=comment,
        reason=reason,
    )
    normalized_domain = (domain or "").strip().lower()
    if normalized_domain not in {"general", "assignment"}:
        raise HTTPException(status_code=422, detail="Invalid domain.")

    if normalized_domain == "general":
        if full_name is None:
            raise HTTPException(status_code=422, detail="full_name is required.")
        return _correct_employee_general(
            employee_id=employee_id,
            full_name=full_name,
            effective_date=effective_date,
            reason=normalized_reason,
            comment=normalized_comment,
            created_by=created_by,
        )

    if org_unit_id is None:
        raise HTTPException(status_code=422, detail="org_unit_id is required.")

    return _correct_employee_assignment(
        employee_id=employee_id,
        org_unit_id=int(org_unit_id),
        position_id=position_id,
        employment_rate=employment_rate,
        date_from=date_from,
        date_to=date_to,
        effective_date=effective_date,
        reason=normalized_reason,
        comment=normalized_comment,
        created_by=created_by,
    )


def list_employee_events(
    *,
    employee_id: str,
    event_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    target_id_text = _normalize_employee_id_text(employee_id)
    if not target_id_text:
        raise HTTPException(status_code=404, detail="Employee not found.")

    allowed_types = {
        "TRANSFER",
        "CORRECTION",
        "HIRE",
        "TERMINATION",
        "POSITION_CHANGE",
        "RATE_CHANGE",
    }
    if event_type is not None:
        normalized_type = event_type.strip().upper()
        if normalized_type not in allowed_types:
            raise HTTPException(status_code=422, detail="Invalid event_type filter.")
        event_type = normalized_type

    q_exists = text(
        """
        SELECT employee_id
        FROM public.employees
        WHERE CAST(employee_id AS TEXT) = :id_text
        LIMIT 1
        """
    )

    include_order_linkage = _employee_events_order_columns_available()
    select_sql = _employee_events_list_select_sql(include_order_linkage=include_order_linkage)
    from_sql = _employee_events_list_from_sql(include_order_linkage=include_order_linkage)

    where_parts = ["ev.employee_id = :employee_id"]
    params: Dict[str, Any] = {
        "employee_id": None,
        "limit": int(limit),
        "offset": int(offset),
    }

    if event_type is not None:
        where_parts.append("ev.event_type = :event_type")
        params["event_type"] = event_type

    where_sql = " AND ".join(where_parts)

    q_total = text(
        f"""
        SELECT COUNT(*) AS cnt
        FROM {from_sql}
        WHERE {where_sql}
        """
    )
    q_list = text(
        f"""
        SELECT
            {select_sql}
        FROM {from_sql}
        WHERE {where_sql}
        ORDER BY ev.effective_date DESC, ev.event_id DESC
        LIMIT :limit OFFSET :offset
        """
    )

    with engine.begin() as conn:
        emp_row = conn.execute(q_exists, {"id_text": target_id_text}).mappings().first()
        if not emp_row:
            raise HTTPException(status_code=404, detail="Employee not found.")

        params["employee_id"] = int(emp_row["employee_id"])
        total = int(conn.execute(q_total, params).mappings().first()["cnt"])
        rows = conn.execute(q_list, params).mappings().all()

    items = [_normalize_employee_event(dict(r)) for r in rows]
    return {"items": items, "total": total}


def list_personnel_events(
    *,
    event_type: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    org_group_id: Optional[int] = None,
    org_unit_id: Optional[int] = None,
    position_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """Org-wide personnel event register (Track B demo)."""
    allowed_types = {
        "TRANSFER",
        "CORRECTION",
        "HIRE",
        "TERMINATION",
        "POSITION_CHANGE",
        "RATE_CHANGE",
    }
    if event_type is not None:
        normalized_type = event_type.strip().upper()
        if normalized_type not in allowed_types:
            raise HTTPException(status_code=422, detail="Invalid event_type filter.")
        event_type = normalized_type

    where_parts: List[str] = ["TRUE"]
    params: Dict[str, Any] = {
        "limit": int(limit),
        "offset": int(offset),
    }

    if event_type is not None:
        where_parts.append("ev.event_type = :event_type")
        params["event_type"] = event_type
    if date_from is not None:
        where_parts.append("ev.effective_date >= :date_from")
        params["date_from"] = date_from
    if date_to is not None:
        where_parts.append("ev.effective_date <= :date_to")
        params["date_to"] = date_to
    if org_unit_id is not None:
        where_parts.append(
            "(ev.from_org_unit_id = :org_unit_id OR ev.to_org_unit_id = :org_unit_id)"
        )
        params["org_unit_id"] = int(org_unit_id)
    if org_group_id is not None:
        where_parts.append(
            """
            (
                EXISTS (
                    SELECT 1 FROM public.org_units oug
                    WHERE oug.unit_id = ev.from_org_unit_id
                      AND oug.group_id = :org_group_id
                )
                OR EXISTS (
                    SELECT 1 FROM public.org_units oug
                    WHERE oug.unit_id = ev.to_org_unit_id
                      AND oug.group_id = :org_group_id
                )
            )
            """.strip()
        )
        params["org_group_id"] = int(org_group_id)
    if position_id is not None:
        where_parts.append(
            "(ev.from_position_id = :position_id OR ev.to_position_id = :position_id)"
        )
        params["position_id"] = int(position_id)

    where_sql = " AND ".join(where_parts)

    q_total = text(
        f"""
        SELECT COUNT(*) AS cnt
        FROM public.employee_events ev
        WHERE {where_sql}
        """
    )
    q_list = text(
        f"""
        SELECT
            ev.event_id,
            ev.employee_id,
            e.full_name AS employee_name,
            ev.event_type,
            ev.event_class,
            ev.lifecycle_status,
            ev.metadata,
            ev.effective_date,
            ev.from_org_unit_id,
            fou.name AS from_org_unit_name,
            ev.to_org_unit_id,
            tou.name AS to_org_unit_name,
            ev.from_position_id,
            fp.name AS from_position_name,
            ev.to_position_id,
            tp.name AS to_position_name,
            ev.from_rate,
            ev.to_rate,
            ev.order_ref,
            ev.comment
        FROM public.employee_events ev
        JOIN public.employees e ON e.employee_id = ev.employee_id
        LEFT JOIN public.org_units fou ON fou.unit_id = ev.from_org_unit_id
        LEFT JOIN public.org_units tou ON tou.unit_id = ev.to_org_unit_id
        LEFT JOIN public.positions fp ON fp.position_id = ev.from_position_id
        LEFT JOIN public.positions tp ON tp.position_id = ev.to_position_id
        WHERE {where_sql}
        ORDER BY ev.effective_date DESC, ev.event_id DESC
        LIMIT :limit OFFSET :offset
        """
    )

    def _event_rate(v: Any) -> Optional[float]:
        if v is None:
            return None
        if isinstance(v, Decimal):
            return float(v)
        return float(v)

    with engine.begin() as conn:
        total = int(conn.execute(q_total, params).mappings().first()["cnt"])
        rows = conn.execute(q_list, params).mappings().all()

    items: List[Dict[str, Any]] = []
    for r in rows:
        eff = r.get("effective_date")
        event_type = str(r["event_type"])
        metadata_raw = r.get("metadata")
        metadata: Optional[Dict[str, Any]] = None
        if metadata_raw is not None:
            if isinstance(metadata_raw, dict):
                metadata = metadata_raw
            elif isinstance(metadata_raw, str):
                try:
                    metadata = json.loads(metadata_raw)
                except json.JSONDecodeError:
                    metadata = None

        event_class = r.get("event_class")
        if event_class is not None:
            event_class = str(event_class)
        else:
            event_class = get_event_class(event_type)

        lifecycle_status = r.get("lifecycle_status")
        if lifecycle_status is not None:
            lifecycle_status = str(lifecycle_status)
        else:
            lifecycle_status = "APPROVED"

        items.append(
            {
                "event_id": int(r["event_id"]),
                "employee_id": int(r["employee_id"]),
                "employee_name": str(r.get("employee_name") or ""),
                "event_type": event_type,
                "event_class": event_class,
                "event_label": get_event_label(event_type),
                "lifecycle_status": lifecycle_status,
                "metadata": metadata,
                "effective_date": eff.isoformat() if hasattr(eff, "isoformat") else eff,
                "from_org_unit_id": (
                    int(r["from_org_unit_id"]) if r.get("from_org_unit_id") is not None else None
                ),
                "from_org_unit_name": r.get("from_org_unit_name"),
                "to_org_unit_id": (
                    int(r["to_org_unit_id"]) if r.get("to_org_unit_id") is not None else None
                ),
                "to_org_unit_name": r.get("to_org_unit_name"),
                "from_position_id": (
                    int(r["from_position_id"]) if r.get("from_position_id") is not None else None
                ),
                "from_position_name": r.get("from_position_name"),
                "to_position_id": (
                    int(r["to_position_id"]) if r.get("to_position_id") is not None else None
                ),
                "to_position_name": r.get("to_position_name"),
                "from_rate": _event_rate(r.get("from_rate")),
                "to_rate": _event_rate(r.get("to_rate")),
                "order_ref": r.get("order_ref"),
                "comment": r.get("comment"),
            }
        )

    return {"items": items, "total": total}
