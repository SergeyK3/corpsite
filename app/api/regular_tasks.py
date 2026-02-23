# FILE: app/api/regular_tasks.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body
from pydantic import BaseModel
from sqlalchemy import text

from app.db.engine import engine
from app.services.regular_tasks_import_xlsx import import_regular_task_templates_xlsx_bytes


router = APIRouter(prefix="", tags=["Regular Tasks"])


# =========================
# Schemas
# =========================

class RegularTaskOut(BaseModel):
    regular_task_id: int
    code: str
    title: str
    periodicity: str
    initiator_role_id: int
    target_role_id: int
    executor_role_id: Optional[int] = None
    assignment_scope: str
    is_active: bool

    schedule_type: Optional[str] = None
    schedule_params: Dict[str, Any] = {}

    schedule_issue: Optional[str] = None


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


# =========================
# Helpers
# =========================

def _detect_schedule_issue(schedule_type: Optional[str], schedule_params: Optional[Dict[str, Any]]) -> Optional[str]:
    if schedule_type is None:
        return None

    if schedule_type == "yearly":
        return "UNSUPPORTED_YEARLY"

    if schedule_type == "monthly":
        if not schedule_params:
            return "MONTHLY_MISSING_BYMONTHDAY"

        bymonthday = schedule_params.get("bymonthday")
        if not isinstance(bymonthday, list) or len(bymonthday) == 0:
            return "MONTHLY_MISSING_BYMONTHDAY"

    return None


# =========================
# Endpoints
# =========================

@router.post("/import-xlsx")
def import_regular_tasks_xlsx(
    raw: bytes = Body(..., media_type="application/octet-stream")
) -> Dict[str, Any]:
    return import_regular_task_templates_xlsx_bytes(raw=raw)


@router.get("/regular-tasks", response_model=List[RegularTaskOut])
def list_regular_tasks() -> List[RegularTaskOut]:
    sql = text("""
        SELECT
            regular_task_id,
            code,
            title,
            periodicity::text AS periodicity,
            initiator_role_id,
            target_role_id,
            executor_role_id,
            assignment_scope::text AS assignment_scope,
            is_active,
            schedule_type,
            schedule_params
        FROM public.regular_tasks
        ORDER BY regular_task_id
    """)

    with engine.begin() as conn:
        rows = conn.execute(sql).mappings().all()

    result: List[RegularTaskOut] = []
    for r in rows:
        sp = r.get("schedule_params") or {}
        schedule_issue = _detect_schedule_issue(r.get("schedule_type"), sp)

        result.append(
            RegularTaskOut(
                regular_task_id=r["regular_task_id"],
                code=r["code"],
                title=r["title"],
                periodicity=r["periodicity"],
                initiator_role_id=r["initiator_role_id"],
                target_role_id=r["target_role_id"],
                executor_role_id=r["executor_role_id"],
                assignment_scope=r["assignment_scope"],
                is_active=r["is_active"],
                schedule_type=r.get("schedule_type"),
                schedule_params=sp,
                schedule_issue=schedule_issue,
            )
        )

    return result


@router.get("/regular-task-runs", response_model=List[RegularTaskRunOut])
def list_regular_task_runs() -> List[RegularTaskRunOut]:
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
def list_regular_task_run_items(run_id: int) -> List[RegularTaskRunItemOut]:
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