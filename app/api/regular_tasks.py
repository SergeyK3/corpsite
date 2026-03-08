# FILE: app/api/regular_tasks.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.auth import get_current_user
from app.db.engine import engine
from app.security.directory_scope import is_privileged
from app.services.regular_tasks_import_xlsx import import_regular_task_templates_xlsx_bytes
from app.services.tasks_service import SYSTEM_ADMIN_ROLE_ID


router = APIRouter(prefix="", tags=["Regular Tasks"])


class RegularTaskRunOut(BaseModel):
    run_id: int
    started_at: str
    finished_at: Optional[str] = None
    status: str
    stats: Any = {}
    errors: Any = None


class RegularTaskRunItemOut(BaseModel):
    item_id: int
    run_id: int
    regular_task_id: int
    status: str
    started_at: str
    finished_at: Optional[str] = None
    period_id: Optional[int] = None
    executor_role_id: Optional[int] = None
    is_due: bool
    created_tasks: int
    error: Optional[str] = None


def _require_system_admin(user: Dict[str, Any]) -> None:
    role_id = user.get("role_id")
    try:
        rid = int(role_id) if role_id is not None else None
    except (TypeError, ValueError):
        rid = None

    if rid != int(SYSTEM_ADMIN_ROLE_ID):
        raise HTTPException(status_code=403, detail="Only ADMIN can import regular tasks")


def _require_admin_or_privileged(user: Dict[str, Any]) -> None:
    role_id = user.get("role_id")
    try:
        rid = int(role_id) if role_id is not None else None
    except (TypeError, ValueError):
        rid = None

    if rid == int(SYSTEM_ADMIN_ROLE_ID):
        return

    if is_privileged(user):
        return

    raise HTTPException(status_code=403, detail="Access denied")


@router.post("/import-xlsx")
def import_regular_tasks_xlsx(
    raw: bytes = Body(..., media_type="application/octet-stream"),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_system_admin(current_user)
    return import_regular_task_templates_xlsx_bytes(raw=raw)


@router.get("/regular-task-runs", response_model=List[RegularTaskRunOut])
def list_regular_task_runs(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> List[RegularTaskRunOut]:
    _require_admin_or_privileged(current_user)

    sql = text("""
        SELECT
            run_id,
            started_at,
            finished_at,
            status,
            stats,
            errors
        FROM public.regular_task_runs
        ORDER BY run_id DESC
        LIMIT 100
    """)

    with engine.begin() as conn:
        rows = conn.execute(sql).mappings().all()

    out: List[RegularTaskRunOut] = []
    for r in rows:
        out.append(
            RegularTaskRunOut(
                run_id=r["run_id"],
                started_at=r["started_at"].isoformat(),
                finished_at=r["finished_at"].isoformat() if r["finished_at"] else None,
                status=r["status"],
                stats=r.get("stats"),
                errors=r.get("errors"),
            )
        )
    return out


@router.get("/regular-task-runs/{run_id}/items", response_model=List[RegularTaskRunItemOut])
def list_regular_task_run_items(
    run_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> List[RegularTaskRunItemOut]:
    _require_admin_or_privileged(current_user)

    sql = text("""
        SELECT
            item_id,
            run_id,
            regular_task_id,
            status,
            started_at,
            finished_at,
            period_id,
            executor_role_id,
            is_due,
            created_tasks,
            error
        FROM public.regular_task_run_items
        WHERE run_id = :run_id
        ORDER BY item_id
    """)

    with engine.begin() as conn:
        rows = conn.execute(sql, {"run_id": run_id}).mappings().all()

    return [
        RegularTaskRunItemOut(
            item_id=r["item_id"],
            run_id=r["run_id"],
            regular_task_id=r["regular_task_id"],
            status=r["status"],
            started_at=r["started_at"].isoformat(),
            finished_at=r["finished_at"].isoformat() if r["finished_at"] else None,
            period_id=r["period_id"],
            executor_role_id=r["executor_role_id"],
            is_due=r["is_due"],
            created_tasks=r["created_tasks"],
            error=r["error"],
        )
        for r in rows
    ]