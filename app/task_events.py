# FILE: app/task_events.py

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import text

from app.db.engine import engine

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _require_user_id(x_user_id: Optional[str]) -> int:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-Id header.")
    s = str(x_user_id).strip()
    if not s:
        raise HTTPException(status_code=400, detail="Invalid X-User-Id header.")
    try:
        return int(s)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-User-Id header.")


@router.get("/me/events")
def list_my_task_events(
    *,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    since_audit_id: int = Query(
        default=0,
        ge=0,
        description="Последний доставленный audit_id (cursor). Вернём события > since_audit_id.",
    ),
    limit: int = Query(default=50, ge=1, le=200),
) -> Dict[str, Any]:
    """
    Возвращает события задач, адресованные пользователю (через task_event_recipients),
    строго после since_audit_id (audit_id), по возрастанию audit_id.

    Контракт ответа:
      {
        "items": [...],
        "next_cursor": <int>
      }
    """
    uid = _require_user_id(x_user_id)

    q = text(
        """
        SELECT
          e.audit_id,
          e.task_id,
          e.event_type,
          e.actor_user_id,
          e.actor_role_id,
          e.payload
        FROM public.task_event_recipients r
        JOIN public.task_events e ON e.audit_id = r.audit_id
        WHERE r.user_id = :uid
          AND e.audit_id > :cursor
        ORDER BY e.audit_id ASC
        LIMIT :limit
        """
    )

    with engine.begin() as conn:
        rows = conn.execute(
            q,
            {
                "uid": int(uid),
                "cursor": int(since_audit_id),
                "limit": int(limit),
            },
        ).mappings().all()

    items: List[Dict[str, Any]] = []
    next_cursor = int(since_audit_id)

    for r in rows:
        payload = r.get("payload")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {"_raw": payload}

        audit_id = int(r["audit_id"])
        next_cursor = max(next_cursor, audit_id)

        items.append(
            {
                "audit_id": audit_id,
                "task_id": int(r["task_id"]),
                "event_type": str(r["event_type"] or ""),
                "actor_user_id": int(r["actor_user_id"]) if r.get("actor_user_id") is not None else None,
                "actor_role_id": int(r["actor_role_id"]) if r.get("actor_role_id") is not None else None,
                "payload": payload if isinstance(payload, dict) else (payload or {}),
            }
        )

    return {"items": items, "next_cursor": next_cursor}
