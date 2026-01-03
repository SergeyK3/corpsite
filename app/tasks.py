# app/tasks.py
from __future__ import annotations

from typing import Any, Dict, Optional, Set

from fastapi import APIRouter, HTTPException, Query, Header, Path
from fastapi import Response

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
    # Явный предпочтительный дефолт
    if any(lbl.lower() == "functional" for lbl in allowed):
        return next(lbl for lbl in allowed if lbl.lower() == "functional")
    # Иначе — любой первый (стабильно: сортировка)
    return sorted(allowed)[0]


def _normalize_assignment_scope(conn, value: Any) -> str:
    """
    Нормализует assignment_scope под РЕАЛЬНЫЙ enum в БД.

    В вашей БД судя по 422: {"admin","functional"}.
    Поэтому:
    - default: functional (если есть), иначе любое допустимое значение
    - принимаем вход в любом регистре
    - поддерживаем маппинг старых значений ROLE/USER/ANY -> functional/admin (если это возможно)
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

    # 2) match by lower-case equivalence
    for lbl in allowed:
        if lbl.lower() == raw_l:
            return lbl

    # 3) backward-compatible mapping (если раньше использовались ROLE/USER/ANY)
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


def _scope_label_or_none(allowed: Set[str], wanted_lower: str) -> Optional[str]:
    for lbl in allowed:
        if lbl.lower() == wanted_lower:
            return lbl
    return None


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
    Выдача задач в рамках роли + ограничение по assignment_scope:

    - functional: видны всем пользователям данной роли
    - admin: видны только инициатору (initiator_user_id = текущий пользователь)
    """
    current_user_id = _get_current_user_id(x_user_id)

    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    with engine.begin() as conn:
        role_id = _get_user_role_id(conn, current_user_id)
        params["role_id"] = role_id
        params["current_user_id"] = current_user_id

        allowed = _load_assignment_scope_enum_labels(conn)
        if not allowed:
            raise HTTPException(status_code=500, detail="assignment_scope_t enum not found in DB")

        functional_lbl = _scope_label_or_none(allowed, "functional")
        admin_lbl = _scope_label_or_none(allowed, "admin")

        where = ["t.executor_role_id = :role_id"]

        if functional_lbl and admin_lbl:
            params["functional_scope"] = functional_lbl
            params["admin_scope"] = admin_lbl
            where.append(
                "("
                "t.assignment_scope = :functional_scope "
                "OR (t.assignment_scope = :admin_scope AND t.initiator_user_id = :current_user_id)"
                ")"
            )

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

@router.get("/{task_id}")
def get_task(
    task_id: int = Path(..., ge=1),
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    """
    Получение одной задачи.

    Права доступа (строго):
      - задача должна быть в рамках роли пользователя
      - functional: доступна всем в роли
      - admin: доступна только инициатору

    При любом нарушении — 404 (не раскрываем существование).
    """
    current_user_id = _get_current_user_id(x_user_id)

    with engine.begin() as conn:
        role_id = _get_user_role_id(conn, current_user_id)

        allowed = _load_assignment_scope_enum_labels(conn)
        if not allowed:
            raise HTTPException(status_code=500, detail="assignment_scope_t enum not found in DB")

        functional_lbl = _scope_label_or_none(allowed, "functional")
        admin_lbl = _scope_label_or_none(allowed, "admin")

        params: Dict[str, Any] = {
            "task_id": int(task_id),
            "role_id": int(role_id),
            "current_user_id": int(current_user_id),
        }

        where = [
            "t.task_id = :task_id",
            "t.executor_role_id = :role_id",
        ]

        if functional_lbl and admin_lbl:
            params["functional_scope"] = functional_lbl
            params["admin_scope"] = admin_lbl
            where.append(
                "("
                "t.assignment_scope = :functional_scope "
                "OR (t.assignment_scope = :admin_scope AND t.initiator_user_id = :current_user_id)"
                ")"
            )

        where_sql = " AND ".join(where)

        task = conn.execute(
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
                """
            ),
            params,
        ).mappings().first()

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

    return dict(task)


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
      assignment_scope: str | null  (default: functional/admin по enum БД)
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


@router.patch("/{task_id}")
def patch_task(
    payload: Dict[str, Any],
    task_id: int = Path(..., ge=1),
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    """
    Частичное обновление задачи.

    Права (MVP, безопасно):
      - менять может только инициатор задачи
      - и только в рамках своей роли (executor_role_id == role_id пользователя)

    Разрешены поля:
      - title (не пустой, если передан)
      - description (можно null)
      - assignment_scope (нормализуется под enum БД)
    """
    current_user_id = _get_current_user_id(x_user_id)

    allowed_fields = {"title", "description", "assignment_scope"}
    incoming_keys = [k for k in payload.keys() if k in allowed_fields]
    if not incoming_keys:
        raise HTTPException(status_code=422, detail="Nothing to update")

    with engine.begin() as conn:
        role_id = _get_user_role_id(conn, current_user_id)

        # ВАЖНО: проверка "видимости" задачи делается так же, как в list_tasks.
        # Если задача не видна текущему пользователю — возвращаем 404.
        allowed = _load_assignment_scope_enum_labels(conn)
        if not allowed:
            raise HTTPException(status_code=500, detail="assignment_scope_t enum not found in DB")

        functional_lbl = _scope_label_or_none(allowed, "functional")
        admin_lbl = _scope_label_or_none(allowed, "admin")

        params_vis: Dict[str, Any] = {
            "tid": int(task_id),
            "role_id": int(role_id),
            "current_user_id": int(current_user_id),
            "functional_scope": functional_lbl,
            "admin_scope": admin_lbl,
        }

        vis_sql = """
            SELECT
                t.task_id,
                t.initiator_user_id,
                t.executor_role_id,
                t.assignment_scope
            FROM tasks t
            WHERE t.task_id = :tid
              AND t.executor_role_id = :role_id
        """

        if functional_lbl and admin_lbl:
            vis_sql += """
              AND (
                    t.assignment_scope = :functional_scope
                    OR (t.assignment_scope = :admin_scope AND t.initiator_user_id = :current_user_id)
              )
            """

        task_row = conn.execute(text(vis_sql), params_vis).mappings().first()

        if not task_row:
            raise HTTPException(status_code=404, detail="Task not found")

        # Только инициатор может PATCH (и для functional тоже)
        if int(task_row["initiator_user_id"]) != int(current_user_id):
            raise HTTPException(status_code=403, detail="Only initiator can update task")

        set_parts = []
        params: Dict[str, Any] = {"tid": int(task_id)}

        if "title" in payload:
            title = (payload.get("title") or "").strip()
            if not title:
                raise HTTPException(status_code=422, detail="title cannot be empty")
            set_parts.append("title = :title")
            params["title"] = title

        if "description" in payload:
            desc = payload.get("description")
            params["description"] = None if desc is None else str(desc).strip()
            set_parts.append("description = :description")

        if "assignment_scope" in payload:
            scope = _normalize_assignment_scope(conn, payload.get("assignment_scope"))
            set_parts.append("assignment_scope = :assignment_scope")
            params["assignment_scope"] = scope

        if not set_parts:
            raise HTTPException(status_code=422, detail="Nothing to update")

        set_sql = ", ".join(set_parts)

        updated = conn.execute(
            text(
                f"""
                UPDATE tasks
                SET {set_sql}
                WHERE task_id = :tid
                RETURNING task_id
                """
            ),
            params,
        ).mappings().first()

        if not updated:
            raise HTTPException(status_code=500, detail="Failed to update task")

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
            {"task_id": int(task_id)},
        ).mappings().first()

        if not task:
            raise HTTPException(status_code=500, detail="Task updated but not found")

    return dict(task)

@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int = Path(..., ge=1),
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
) -> Response:
    """
    Удаление задачи.

    Права (MVP, безопасно):
      - удалять может только инициатор задачи
      - и только в рамках своей роли (executor_role_id == role_id пользователя)

    Поведение:
      - 204 No Content при успехе
      - 404 если нет задачи / чужая роль / не инициатор
    """
    current_user_id = _get_current_user_id(x_user_id)

    with engine.begin() as conn:
        role_id = _get_user_role_id(conn, current_user_id)

        task_row = conn.execute(
            text(
                """
                SELECT t.task_id, t.initiator_user_id, t.executor_role_id
                FROM tasks t
                WHERE t.task_id = :tid
                """
            ),
            {"tid": int(task_id)},
        ).mappings().first()

        if not task_row:
            raise HTTPException(status_code=404, detail="Task not found")

        # 1) защита по роли (как будто не существует)
        if int(task_row["executor_role_id"]) != int(role_id):
            raise HTTPException(status_code=404, detail="Task not found")

        # 2) только инициатор
        if int(task_row["initiator_user_id"]) != int(current_user_id):
            raise HTTPException(status_code=404, detail="Task not found")
            # если хотите явно: raise HTTPException(status_code=403, detail="Forbidden")

        deleted = conn.execute(
            text("DELETE FROM tasks WHERE task_id = :tid RETURNING task_id"),
            {"tid": int(task_id)},
        ).mappings().first()

        if not deleted:
            raise HTTPException(status_code=500, detail="Failed to delete task")

    return Response(status_code=204)