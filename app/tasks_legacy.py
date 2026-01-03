from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from app.db.engine import engine

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
def get_tasks(
    user_id: int = Query(..., ge=1),
    period_id: Optional[int] = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """
    Возвращает задачи, доступные пользователю как исполнителю по его роли.
    MVP-логика:
      1) находим пользователя
      2) берем его role_id
      3) показываем tasks, где executor_role_id = role_id
      4) опционально фильтруем по period_id
    """

    with engine.connect() as conn:
        # 1) User -> role
        user = conn.execute(
            text("SELECT user_id, role_id, full_name FROM users WHERE user_id = :uid"),
            {"uid": user_id},
        ).mappings().first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        role_id = int(user["role_id"])

        # 2) Count
        count_sql = """
            SELECT COUNT(*) AS cnt
            FROM tasks t
            WHERE t.executor_role_id = :role_id
              AND (:pid IS NULL OR t.period_id = :pid)
        """
        total = conn.execute(
            text(count_sql),
            {"role_id": role_id, "pid": period_id},
        ).scalar_one()

        # 3) Items
        items_sql = """
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
            WHERE t.executor_role_id = :role_id
              AND (:pid IS NULL OR t.period_id = :pid)
            ORDER BY t.task_id DESC
            LIMIT :limit OFFSET :offset
        """
        rows = conn.execute(
            text(items_sql),
            {
                "role_id": role_id,
                "pid": period_id,
                "limit": limit,
                "offset": offset,
            },
        ).mappings().all()

    return {
        "user": {
            "user_id": int(user["user_id"]),
            "full_name": user["full_name"],
            "role_id": role_id,
        },
        "total": int(total),
        "limit": limit,
        "offset": offset,
        "items": [dict(r) for r in rows],
    }
