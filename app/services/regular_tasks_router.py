# FILE: app/services/regular_tasks_router.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header
from sqlalchemy import text

from app.db.engine import engine
from app.services.regular_tasks_service import run_regular_tasks_generation_tx

router = APIRouter(prefix="/internal/regular-tasks", tags=["internal-regular-tasks"])


@router.post("/run")
def run_regular_tasks(
    payload: Optional[Dict[str, Any]] = None,
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    """
    Internal endpoint: запускается cron/worker/поддержкой.
    payload (опционально):
      - dry_run: bool
      - run_at_local_iso: str (например "2026-01-27T10:00:00") — для тестов
    """
    payload = payload or {}
    dry_run = bool(payload.get("dry_run", False))
    run_at_local_iso = payload.get("run_at_local_iso")

    run_at_local: Optional[datetime] = None
    if isinstance(run_at_local_iso, str) and run_at_local_iso.strip():
        # наивный ISO (без tz); мы интерпретируем как локальное проекта (UTC+5)
        run_at_local = datetime.fromisoformat(run_at_local_iso.strip())

    # минимальная защита: не пускать без X-User-Id, но это internal — решишь сам
    if not x_user_id:
        # можно ослабить: убрать проверку и запускать вообще без заголовка
        raise Exception("X-User-Id is required for internal run (adjust policy if needed)")

    with engine.begin() as conn:
        # (опционально) можно проверять роль/админов — пока не фиксируем
        # Просто пишем в meta run_id, stats.
        run_id, stats = run_regular_tasks_generation_tx(conn, run_at_local=run_at_local, dry_run=dry_run)

        return {"run_id": int(run_id), "dry_run": dry_run, "stats": stats}
