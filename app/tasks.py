# app/tasks.py
from __future__ import annotations

from typing import Any, Dict, Optional, Set

from fastapi import APIRouter, HTTPException, Query, Header
from sqlalchemy import text

from app.db.engine import engine

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _get_current_user_id(x_user_id: Optional[int]) -> int:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header is required")
    return int(x_user_id)


def _get_user_role_id(conn, user_id: int) -> int:
    row = conn.execute(
        text("SELECT user_id, role_id FROM users WHERE user_id = :uid"),
        {"uid": user_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    if row["role_id"] is None:
        raise HTTPException(status_code=400, detail="User role_id is NULL")
    return int(row["role_id"])


def _get_status_id_by_code(conn, code: str) -> int:
    row = conn.execute(
        text("SELECT status_id FROM task_statuses WHERE code = :code"),
        {"code": code},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=400, detail=f"Unknown status code: {code}")
    return int(row["status_id"])


def _load_assignment_scope_enum_labels(conn) -> Set[str]:
    """
    Читает реальный набор значений enum assignment_scope_t из Postgres.
    Возвращает set строк, например: {"role","user","any"} или {"ROLE","USER","ANY"}.
    """
    rows = conn.execute(
        text(
            """
            SELECT e.enumlabel
            FROM pg_enum e
            JOIN pg_type t ON t.oid = e.enumtypid
            WHERE t.typname = 'assignment_scope_t'
            ORDER BY e.enumsortorder
            """
        )
    ).all()
    return {r[0] for r in rows}


def _normalize_assignment_scope(conn, value: Any) -> str:
    """
    Нормализует assignment_scope и приводит к реальному значению enum в БД.

    Логика:
    - если value None -> "role"
    - принимаем вход в любом регистре: ROLE/role/User/ANY...
    - далее подбираем совпадающее значение из enum БД:
        1) точное совпадение
        2) совпадение по lower()
        3) совпадение по upper()
    """
    raw = "role" if value is None else str(value)
    raw = raw.strip()
    if not raw:
        raw = "role"

    allowed = _load_assignment_scope_enum_labels(conn)
    if not allowed:
        raise HTTPException(status_code=500, detail="assignment_scope_t enum not found in DB")

    # 1) exact
    if raw in allowed:
        return raw

    raw_l = raw.lower()
    raw_u = raw.upper()

    # 2) match by lower
    for lbl in allowed:
        if lbl.lower() == raw_l:
            return lbl

    # 3) match by upper
    for lbl in allowed:
        if lbl.upper() == raw_u:
            return lbl

    # Если не нашли — возвращаем 422 с подсказкой реальных значений
    raise HTTPException(
        status_code=422,
        detail=f"assignment_scope must be one of: {', '.join(sorted(allowed))}",
    )


@router.get("")
def list_tasks(
    period_id: Optional[int] = Query(None, ge=1),
    status_code: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    """
    Совместимо с текущей схемой БД:
    - tasks.executor_role_id
    - users.role_id
    """
    current_user_id = _get_current_user_id(x_user_id)

    where = ["t.executor_role_id = :role_id"]
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    with engine.begin() as conn:
        role_id = _get_user_role_id(conn, current_user_id)
        params["role_id"] = role_id

        if period_id is not None:
            where.append("t.period_id = :period_id")
            params["period_id"] = period_id

        if status_code:
            where.append("ts.code = :status_code")
            params["status_code"] = status_code.strip()

        if search:
            where.append("(t.title ILIKE :q OR COALESCE(t.description,'') ILIKE :q)")
            params["q"] = f"%{search}%"

        where_sql = " AND ".join(where)

        total = conn.execute(
            text(
                f"""
                SELECT COUNT(1)
                FROM tasks t
                LEFT JOIN task_statuses ts ON ts.status_id = t.status_id
                WHERE {where_sql}
                """
            ),
            params,
        ).scalar() or 0

        rows = conn.execute(
            text(
                f"""
                SELECT
                    t.task_id,
                    t.period_id,
                    t.regular_task_id,
                    t.title,
                    t.description,
                    t.initiator_user_id,
                    t.executor_role_id,
                    t.assignment_scope,
                    t.status_id,
                    ts.code AS status_code,
                    ts.name_ru AS status_name_ru
                FROM tasks t
                LEFT JOIN task_statuses ts ON ts.status_id = t.status_id
                WHERE {where_sql}
                ORDER BY t.task_id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings().all()

    return {"total": int(total), "limit": limit, "offset": offset, "items": [dict(r) for r in rows]}


@router.post("")
def create_task(
    payload: Dict[str, Any],
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    """
    MVP создание задачи (role-based).

    Body (JSON):
      title: str (required)
      executor_role_id: int (required)
      period_id: int (required)  <-- В БД NOT NULL
      description: str | null
      regular_task_id: int | null
      assignment_scope: str | null  (default role/ROLE — будет приведено к enum БД)
      status_code: str | null  (default IN_PROGRESS)
    """
    current_user_id = _get_current_user_id(x_user_id)

    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="title is required")

    executor_role_id = payload.get("executor_role_id")
    if not isinstance(executor_role_id, int) or executor_role_id < 1:
        raise HTTPException(status_code=422, detail="executor_role_id is required")

    period_id = payload.get("period_id")
    if not isinstance(period_id, int) or period_id < 1:
        raise HTTPException(status_code=422, detail="period_id is required")

    status_code = (payload.get("status_code") or "IN_PROGRESS").strip()

    with engine.begin() as conn:
        # ВАЖНО: нормализуем assignment_scope, зная реальные значения enum в БД
        assignment_scope = _normalize_assignment_scope(conn, payload.get("assignment_scope"))

        status_id = _get_status_id_by_code(conn, status_code)

        row = conn.execute(
            text(
                """
                INSERT INTO tasks (
                    period_id,
                    regular_task_id,
                    title,
                    description,
                    initiator_user_id,
                    executor_role_id,
                    assignment_scope,
                    status_id
                )
                VALUES (
                    :period_id,
                    :regular_task_id,
                    :title,
                    :description,
                    :initiator_user_id,
                    :executor_role_id,
                    :assignment_scope,
                    :status_id
                )
                RETURNING task_id
                """
            ),
            {
                "period_id": int(period_id),
                "regular_task_id": payload.get("regular_task_id"),
                "title": title,
                "description": payload.get("description"),
                "initiator_user_id": current_user_id,
                "executor_role_id": int(executor_role_id),
                "assignment_scope": assignment_scope,
                "status_id": status_id,
            },
        ).mappings().first()

        if not row or row.get("task_id") is None:
            raise HTTPException(status_code=500, detail="Failed to create task")

        task_id = int(row["task_id"])

        task = conn.execute(
            text(
                """
                SELECT
                    t.task_id,
                    t.period_id,
                    t.regular_task_id,
                    t.title,
                    t.description,
                    t.initiator_user_id,
                    t.executor_role_id,
                    t.assignment_scope,
                    t.status_id,
                    ts.code AS status_code,
                    ts.name_ru AS status_name_ru
                FROM tasks t
                LEFT JOIN task_statuses ts ON ts.status_id = t.status_id
                WHERE t.task_id = :task_id
                """
            ),
            {"task_id": task_id},
        ).mappings().first()

        if not task:
            raise HTTPException(status_code=500, detail="Task created but not found")

    return dict(task)
