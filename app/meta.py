# app/meta.py
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import text

from app.db.engine import engine
from app.errors import raise_error, ErrorCode
from app.security.directory_scope import require_uid

router = APIRouter(prefix="/meta", tags=["meta"])


def _require_request_user_id(
    *,
    authorization: str | None,
    x_user_id: int | None,
    x_internal_api_token: str | None,
) -> int:
    try:
        return require_uid(
            authorization=authorization,
            x_user_id=str(int(x_user_id)) if x_user_id is not None else None,
            x_internal_api_token=x_internal_api_token,
        )
    except HTTPException:
        # Для UI сохраняем стабильный контракт 403/not-bound.
        raise_error(ErrorCode.META_FORBIDDEN_NOT_BOUND)


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
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    x_internal_api_token: str | None = Header(default=None, alias="X-Internal-Api-Token"),
):
    user_id = _require_request_user_id(
        authorization=authorization,
        x_user_id=x_user_id,
        x_internal_api_token=x_internal_api_token,
    )

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
