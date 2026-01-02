# app/tasks.py
from __future__ import annotations

from typing import Any, Dict, Optional, Set

from fastapi import APIRouter, HTTPException, Query, Header, Path
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
    Например: {"admin","functional"}.
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


def _pick_default_scope(allowed: Set[str]) -> str:
    if "functional" in allowed:
        return "functional"
    if "FUNCTIONAL" in allowed:
        return "FUNCTIONAL"
    return sorted(allowed)[0]


def _normalize_assignment_scope(conn, value: Any) -> str:
    """
    Нормализует assignment_scope под РЕАЛЬНЫЙ enum в БД.

    В вашей БД (судя по ошибке) допустимо: {"admin","functional"}.
    Поэтому:
    - default: functional (если есть), иначе любое допустимое значение
    - принимаем вход в любом регистре
    - поддерживаем маппинг старых значений ROLE/USER/ANY -> functional/admin
    """
    allowed = _load_assignment_scope_enum_labels(conn)
    if not allowed:
        raise HTTPException(status_code=500, detail="assignment_scope_t enum not found in DB")

    # default
    if value is None or (isinstance(value, str) and not value.strip()):
        return _pick_default_scope(allowed)

    raw = str(value).strip()

    # 1) exact match
    if raw in allowed:
        return raw

    raw_l = raw.lower()

    # 2) case-insensitive match
    for lbl in allowed:
        if lbl.lower() == raw_l:
            return lbl

    # 3) backward-compatible mapping
    legacy_map = {
        "role": "functional",
        "any": "functional",
        "user": "admin",
    }
    if raw_l in legacy_map:
        target = legacy_map[raw_l]
        for lbl in allowed:
            if lbl.lower() == target:
                return lbl

    raise HTTPException(
        status_code=422,
        detail=f"assignment_scope must be one of: {', '.join(sorted(allowed))}",
    )


def _read_task(conn, task_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute(
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
    return dict(row) if row else None


def _can_edit_task(current_user_id: int, current_role_id: int, task: Dict[str, Any]) -> bool:
    """
    Правила PATCH:
    1) Инициатор всегда может редактировать.
    2) Если assignment_scope == "functional", то редактировать можно по роли:
       executor_role_id == текущая роль пользователя.
    3) Если assignment_scope == "admin", то только инициатор.
    """
    if int(task["initiator_user_id"]) == int(current_user_id):
        return True

    scope = str(task.get("assignment_scope") or "").lower()
    if scope == "functional":
        return int(task["executor_role_id"]) == int(current_role_id)

    # scope == "admin" (или любое другое) — только инициатор (см. правило выше)
    return False


@router.get("")
def list_tasks(
    period_id: Optional[int] = Query(None, ge=1),
    status_code: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
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
        task = _read_task(conn, task_id)
        if not task:
            raise HTTPException(status_code=500, detail="Task created but not found")

    return task


@router.patch("/{task_id}")
def patch_task(
    payload: Dict[str, Any],
    task_id: int = Path(..., ge=1),
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    """
    Частичное редактирование задачи:
      - title
      - description
      - assignment_scope
    """
    current_user_id = _get_current_user_id(x_user_id)

    # Разрешённые поля PATCH
    allowed_fields = {"title", "description", "assignment_scope"}
    unknown = [k for k in payload.keys() if k not in allowed_fields]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown fields: {', '.join(unknown)}")

    if not any(k in payload for k in allowed_fields):
        raise HTTPException(status_code=422, detail="No fields to update")

    updates: Dict[str, Any] = {}

    if "title" in payload:
        new_title = (payload.get("title") or "").strip()
        if not new_title:
            raise HTTPException(status_code=422, detail="title must be a non-empty string")
        updates["title"] = new_title

    if "description" in payload:
        desc = payload.get("description")
        if desc is None:
            updates["description"] = None
        else:
            updates["description"] = str(desc)

    with engine.begin() as conn:
        # Проверка прав
        role_id = _get_user_role_id(conn, current_user_id)
        task = _read_task(conn, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        if not _can_edit_task(current_user_id, role_id, task):
            raise HTTPException(status_code=403, detail="Forbidden")

        if "assignment_scope" in payload:
            updates["assignment_scope"] = _normalize_assignment_scope(conn, payload.get("assignment_scope"))

        # Сформировать SET-часть
        set_parts = []
        params: Dict[str, Any] = {"task_id": task_id}

        for i, (k, v) in enumerate(updates.items(), start=1):
            p = f"p{i}"
            set_parts.append(f"{k} = :{p}")
            params[p] = v

        # обновим updated_at если колонка есть (у вас она есть по трейсбеку)
        set_parts.append("updated_at = now()")

        set_sql = ", ".join(set_parts)

        conn.execute(
            text(f"UPDATE tasks SET {set_sql} WHERE task_id = :task_id"),
            params,
        )

        updated = _read_task(conn, task_id)
        if not updated:
            raise HTTPException(status_code=500, detail="Task updated but not found")

    return updated
