# FILE: app/api/regular_tasks.py
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.auth import get_current_user
from app.db.engine import engine
from app.security.directory_scope import is_privileged
from app.services.regular_tasks_import_xlsx import import_regular_task_templates_xlsx_bytes
from app.services.regular_tasks_service import _resolve_journal_warning
from app.services.tasks_service import SYSTEM_ADMIN_ROLE_ID


router = APIRouter(prefix="", tags=["Regular Tasks"])


def _isoformat_or_none(value: Union[datetime, date, str, None]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    iso = getattr(value, "isoformat", None)
    if callable(iso):
        return iso()
    return str(value)


class RegularTaskRunOut(BaseModel):
    run_id: int
    started_at: str
    finished_at: Optional[str] = None
    status: str
    stats: Any = {}
    errors: Any = None
    item_count: int = 0
    journal_warning: Optional[str] = None


class RegularTaskRunItemOut(BaseModel):
    item_id: int
    run_id: int
    regular_task_id: int
    status: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    period_id: Optional[int] = None
    executor_role_id: Optional[int] = None
    executor_role_name: Optional[str] = None
    executor_role_code: Optional[str] = None
    is_due: bool
    created_tasks: int
    error: Optional[str] = None
    meta: Any = None


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
    org_group_id: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> List[RegularTaskRunOut]:
    _require_admin_or_privileged(current_user)

    params: Dict[str, Any] = {}
    where_sql = ""

    if org_group_id is not None:
        params["org_group_id"] = int(org_group_id)
        where_sql = """
        WHERE EXISTS (
            SELECT 1
            FROM public.regular_task_run_items i
            JOIN public.users ux
              ON ux.role_id = i.executor_role_id
            JOIN public.org_units oux
              ON oux.unit_id = ux.unit_id
            WHERE i.run_id = r.run_id
              AND COALESCE(ux.is_active, TRUE) = TRUE
              AND COALESCE(oux.is_active, TRUE) = TRUE
              AND oux.group_id = :org_group_id
        )
        """

    sql = text(
        f"""
        SELECT
            r.run_id,
            r.started_at,
            r.finished_at,
            r.status,
            r.stats,
            r.errors,
            (
                SELECT COUNT(1)
                FROM public.regular_task_run_items i2
                WHERE i2.run_id = r.run_id
            ) AS item_count
        FROM public.regular_task_runs r
        {where_sql}
        ORDER BY r.run_id DESC
        LIMIT 100
        """
    )

    with engine.begin() as conn:
        rows = conn.execute(sql, params).mappings().all()

    out: List[RegularTaskRunOut] = []
    for r in rows:
        stats = r.get("stats") or {}
        if not isinstance(stats, dict):
            stats = {}
        item_count = int(r.get("item_count") or stats.get("item_count") or 0)
        journal_warning = _resolve_journal_warning(
            stats=stats,
            item_count=item_count,
            templates_due=int(stats.get("templates_due") or 0),
        )
        out.append(
            RegularTaskRunOut(
                run_id=r["run_id"],
                started_at=_isoformat_or_none(r["started_at"]) or "",
                finished_at=_isoformat_or_none(r["finished_at"]),
                status=r["status"],
                stats=stats,
                errors=r.get("errors"),
                item_count=item_count,
                journal_warning=journal_warning,
            )
        )
    return out


@router.get("/regular-task-runs/{run_id}/items", response_model=List[RegularTaskRunItemOut])
def list_regular_task_run_items(
    run_id: int,
    org_group_id: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> List[RegularTaskRunItemOut]:
    _require_admin_or_privileged(current_user)

    params: Dict[str, Any] = {"run_id": run_id}
    group_filter_sql = ""

    if org_group_id is not None:
        params["org_group_id"] = int(org_group_id)
        group_filter_sql = """
          AND EXISTS (
              SELECT 1
              FROM public.users ux
              JOIN public.org_units oux
                ON oux.unit_id = ux.unit_id
              WHERE ux.role_id = i.executor_role_id
                AND COALESCE(ux.is_active, TRUE) = TRUE
                AND COALESCE(oux.is_active, TRUE) = TRUE
                AND oux.group_id = :org_group_id
          )
        """

    sql = text(
        f"""
        SELECT
            i.item_id,
            i.run_id,
            i.regular_task_id,
            i.status,
            i.started_at,
            i.finished_at,
            i.period_id,
            i.executor_role_id,
            rol.name AS executor_role_name,
            rol.code AS executor_role_code,
            i.is_due,
            i.created_tasks,
            i.error,
            i.meta
        FROM public.regular_task_run_items i
        LEFT JOIN public.roles rol
          ON rol.role_id = i.executor_role_id
        WHERE i.run_id = :run_id
        {group_filter_sql}
        ORDER BY i.item_id
        """
    )

    with engine.begin() as conn:
        rows = conn.execute(sql, params).mappings().all()

    return [
        RegularTaskRunItemOut(
            item_id=r["item_id"],
            run_id=r["run_id"],
            regular_task_id=r["regular_task_id"],
            status=r["status"],
            started_at=_isoformat_or_none(r["started_at"]),
            finished_at=_isoformat_or_none(r["finished_at"]),
            period_id=r["period_id"],
            executor_role_id=r["executor_role_id"],
            executor_role_name=r.get("executor_role_name"),
            executor_role_code=r.get("executor_role_code"),
            is_due=r["is_due"],
            created_tasks=r["created_tasks"],
            error=r["error"],
            meta=r.get("meta"),
        )
        for r in rows
    ]