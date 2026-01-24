# app/meta.py
from __future__ import annotations

from fastapi import APIRouter, Header
from sqlalchemy import text

from app.db.engine import engine
from app.errors import raise_error, ErrorCode

router = APIRouter(prefix="/meta", tags=["meta"])


def _require_user_id(x_user_id: int | None) -> int:
    """
    Meta endpoints требуют авторизации через X-User-Id.
    Для UI-контракта используем 403, а не 400.
    """
    if x_user_id is None or int(x_user_id) <= 0:
        raise_error(ErrorCode.META_FORBIDDEN_NOT_BOUND)
    return int(x_user_id)


def _is_user_bound(user_id: int) -> bool:
    """
    Проверка привязки пользователя к системе.

    Вариант 1 (рекомендуемый): users.telegram_id не NULL
    Если у тебя привязка хранится иначе (tg_bindings), скажи — заменю SQL.
    """
    sql = """
    SELECT 1
    FROM users
    WHERE user_id = :user_id
      AND telegram_id IS NOT NULL
    LIMIT 1;
    """
    with engine.connect() as conn:
        row = conn.execute(text(sql), {"user_id": int(user_id)}).fetchone()
    return row is not None


@router.get("/task-statuses")
def get_task_statuses(
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
):
    user_id = _require_user_id(x_user_id)

    # Запрещаем доступ к meta тем, кто не прошёл привязку
    if not _is_user_bound(user_id):
        raise_error(ErrorCode.META_FORBIDDEN_NOT_BOUND, extra={"user_id": int(user_id)})

    sql = """
    SELECT code, name_ru, sort_order
    FROM task_statuses
    ORDER BY sort_order;
    """
    with engine.connect() as conn:
        rows = conn.execute(text(sql)).mappings().all()

    return {"items": list(rows)}
