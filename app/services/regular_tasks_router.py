# FILE: app/services/regular_tasks_router.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.db.engine import engine
from app.services.regular_tasks_service import run_regular_tasks_generation_tx
from app.services.tasks_service import SYSTEM_ADMIN_ROLE_ID

router = APIRouter(prefix="/internal/regular-tasks", tags=["internal-regular-tasks"])


def _require_system_admin(user: Dict[str, Any]) -> None:
    role_id = user.get("role_id")
    try:
        rid = int(role_id) if role_id is not None else None
    except (TypeError, ValueError):
        rid = None

    if rid != int(SYSTEM_ADMIN_ROLE_ID):
        raise HTTPException(status_code=403, detail="Only ADMIN can run regular tasks")


@router.post("/run")
def run_regular_tasks(
    payload: Optional[Dict[str, Any]] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Internal endpoint: запускается cron/worker/поддержкой.
    Доступ разрешён только system ADMIN.

    payload (опционально):
      - dry_run: bool
      - run_at_local_iso: str (например "2026-01-27T10:00:00") — для тестов
    """
    _require_system_admin(current_user)

    payload = payload or {}
    dry_run = bool(payload.get("dry_run", False))
    run_at_local_iso = payload.get("run_at_local_iso")

    run_at_local: Optional[datetime] = None
    if isinstance(run_at_local_iso, str) and run_at_local_iso.strip():
        # наивный ISO (без tz); интерпретируем как локальное время проекта (UTC+5)
        run_at_local = datetime.fromisoformat(run_at_local_iso.strip())

    with engine.begin() as conn:
        run_id, stats = run_regular_tasks_generation_tx(
            conn,
            run_at_local=run_at_local,
            dry_run=dry_run,
        )

    return {"run_id": int(run_id), "dry_run": dry_run, "stats": stats}