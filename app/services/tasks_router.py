# FILE: app/services/tasks_router.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Path, Query
from fastapi.responses import Response
from sqlalchemy import text

from app.db.engine import engine
from app.errors import ErrorCode, raise_error
from app.services.tasks_fsm import transition
from app.services.tasks_service import (
    attach_allowed_actions,
    can_approve,
    can_report_or_update,
    ensure_task_visible_or_404,
    get_current_user_id,
    get_status_id_by_code,
    get_user_role_id,
    is_supervisor_or_deputy,
    load_assignment_scope_enum_labels,
    load_task_full,
    normalize_assignment_scope,
    scope_label_or_none,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _as_int_or_none(v: Any) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return int(s)
        except Exception:
            return None
    try:
        return int(v)
    except Exception:
        return None


def _as_str_or_none(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        return s if s else None
    # для description лучше не пытаться "умно" сериализовать dict/list
    return str(v).strip() or None


@router.get("/")
def list_tasks(
    period_id: Optional[int] = Query(None, ge=1),
    status_code: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    include_archived: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    current_user_id = get_current_user_id(x_user_id)
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    with engine.begin() as conn:
        role_id = get_user_role_id(conn, current_user_id)
        params["role_id"] = role_id
        params["current_user_id"] = current_user_id

        allowed = load_assignment_scope_enum_labels(conn)
        if not allowed:
            raise HTTPException(status_code=500, detail="assignment_scope_t enum not found in DB")

        functional_lbl = scope_label_or_none(allowed, "functional")
        admin_lbl = scope_label_or_none(allowed, "admin")

        where: List[str] = []

        # RBAC-фильтр: суперв/деп видят всё (текущее поведение системы)
        if not is_supervisor_or_deputy(role_id):
            params["functional_scope"] = functional_lbl
            params["admin_scope"] = admin_lbl

            if functional_lbl and admin_lbl:
                where.append(
                    "("
                    "(t.executor_role_id = :role_id AND t.assignment_scope = :functional_scope) "
                    "OR (t.initiator_user_id = :current_user_id)"
                    ")"
                )
            else:
                where.append(
                    "("
                    "(t.executor_role_id = :role_id) "
                    "OR (t.initiator_user_id = :current_user_id)"
                    ")"
                )

        if period_id is not None:
            where.append("t.period_id = :period_id")
            params["period_id"] = period_id

        if status_code:
            where.append("ts.code = :status_code")
            params["status_code"] = status_code.strip()

        if (not status_code) and (not include_archived):
            where.append("COALESCE(ts.code,'') <> 'ARCHIVED'")

        if search:
            q = search.strip()
            if q:
                where.append("(t.title ILIKE :q OR COALESCE(t.description,'') ILIKE :q)")
                params["q"] = f"%{q}%"

        where_sql = " AND ".join(where) if where else "1=1"

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

        items: List[Dict[str, Any]] = []
        for r in rows:
            t = dict(r)
            t = attach_allowed_actions(task=t, current_user_id=current_user_id, current_role_id=role_id)
            items.append(t)

    return {"total": int(total), "limit": limit, "offset": offset, "items": items}


@router.get("/{task_id}")
def get_task(
    task_id: int = Path(..., ge=1),
    include_archived: bool = Query(False),
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    current_user_id = get_current_user_id(x_user_id)

    with engine.begin() as conn:
        role_id = get_user_role_id(conn, current_user_id)

        task = load_task_full(conn, task_id=int(task_id))
        task = ensure_task_visible_or_404(
            current_user_id=current_user_id,
            current_role_id=role_id,
            task_row=task,
            include_archived=include_archived,
        )

        task = attach_allowed_actions(task=task, current_user_id=current_user_id, current_role_id=role_id)

    return dict(task)


@router.post("/")
def create_task(
    payload: Dict[str, Any],
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    current_user_id = get_current_user_id(x_user_id)

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
    regular_task_id = _as_int_or_none(payload.get("regular_task_id"))
    description = _as_str_or_none(payload.get("description"))

    with engine.begin() as conn:
        assignment_scope = normalize_assignment_scope(conn, payload.get("assignment_scope"))
        status_id = get_status_id_by_code(conn, status_code)

        row = conn.execute(
            text(
                """
                INSERT INTO tasks (
                    period_id, regular_task_id, title, description,
                    initiator_user_id, executor_role_id, assignment_scope, status_id
                )
                VALUES (
                    :period_id, :regular_task_id, :title, :description,
                    :initiator_user_id, :executor_role_id, :assignment_scope, :status_id
                )
                RETURNING task_id
                """
            ),
            {
                "period_id": int(period_id),
                "regular_task_id": int(regular_task_id) if regular_task_id is not None else None,
                "title": title,
                "description": description,
                "initiator_user_id": int(current_user_id),
                "executor_role_id": int(executor_role_id),
                "assignment_scope": assignment_scope,
                "status_id": int(status_id),
            },
        ).mappings().first()

        if not row or row.get("task_id") is None:
            raise HTTPException(status_code=500, detail="Failed to create task")

        task_id = int(row["task_id"])
        role_id = get_user_role_id(conn, current_user_id)

        task = load_task_full(conn, task_id=task_id)
        task = attach_allowed_actions(task=task, current_user_id=current_user_id, current_role_id=role_id)

    return dict(task)


@router.post("/{task_id}/report")
def submit_report(
    payload: Dict[str, Any],
    task_id: int = Path(..., ge=1),
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    current_user_id = get_current_user_id(x_user_id)

    report_link = (payload.get("report_link") or "").strip()
    if not report_link:
        raise HTTPException(status_code=422, detail="report_link is required")

    current_comment = (payload.get("current_comment") or "").strip()

    with engine.begin() as conn:
        role_id = get_user_role_id(conn, current_user_id)

        task = load_task_full(conn, task_id=int(task_id))
        task = ensure_task_visible_or_404(
            current_user_id=current_user_id,
            current_role_id=role_id,
            task_row=task,
            include_archived=False,
        )

        if not can_report_or_update(current_user_id=current_user_id, current_role_id=role_id, task_row=task):
            raise_error(ErrorCode.TASK_FORBIDDEN_REPORT, extra={"task_id": int(task_id)})

        conn.execute(
            text(
                """
                INSERT INTO task_reports (task_id, submitted_by, report_link, current_comment, submitted_at)
                VALUES (:task_id, :submitted_by, :report_link, :current_comment, now())
                ON CONFLICT (task_id)
                DO UPDATE SET
                    submitted_by = EXCLUDED.submitted_by,
                    report_link = EXCLUDED.report_link,
                    current_comment = EXCLUDED.current_comment,
                    submitted_at = now(),
                    approved_at = NULL,
                    approved_by = NULL
                """
            ),
            {
                "task_id": int(task_id),
                "submitted_by": int(current_user_id),
                "report_link": report_link,
                "current_comment": current_comment,
            },
        )

        transition(
            conn=conn,
            task_id=int(task_id),
            action="report",
            actor_user_id=int(current_user_id),
            actor_role_id=int(role_id),
            payload={"report_link": report_link, "current_comment": current_comment},
        )

        updated = load_task_full(conn, task_id=int(task_id))
        updated = attach_allowed_actions(task=updated, current_user_id=current_user_id, current_role_id=role_id)

    return dict(updated)


@router.post("/{task_id}/approve")
def approve_report(
    payload: Dict[str, Any],
    task_id: int = Path(..., ge=1),
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    current_user_id = get_current_user_id(x_user_id)

    approve = payload.get("approve", True)
    if not isinstance(approve, bool):
        raise HTTPException(status_code=422, detail="approve must be boolean")

    current_comment = (payload.get("current_comment") or "").strip()

    with engine.begin() as conn:
        role_id = get_user_role_id(conn, current_user_id)

        task = load_task_full(conn, task_id=int(task_id))
        task = ensure_task_visible_or_404(
            current_user_id=current_user_id,
            current_role_id=role_id,
            task_row=task,
            include_archived=False,
        )

        if not can_approve(current_user_id=current_user_id, current_role_id=role_id, task_row=task):
            raise_error(
                ErrorCode.TASK_FORBIDDEN_APPROVE,
                extra={"task_id": int(task_id), "action": "approve" if approve else "reject"},
            )

        transition(
            conn=conn,
            task_id=int(task_id),
            action="approve" if approve else "reject",
            actor_user_id=int(current_user_id),
            actor_role_id=int(role_id),
            payload={"current_comment": current_comment},
        )

        updated = load_task_full(conn, task_id=int(task_id))
        updated = attach_allowed_actions(task=updated, current_user_id=current_user_id, current_role_id=role_id)

    return dict(updated)


@router.post("/{task_id}/reject")
def reject_report(
    payload: Dict[str, Any],
    task_id: int = Path(..., ge=1),
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    """
    Явный endpoint для отклонения отчёта.
    Нужен для UX и для сквозного сценария REPORT_SUBMITTED -> REJECTED -> delivery -> ACK.
    """
    current_user_id = get_current_user_id(x_user_id)

    reason = (payload.get("reason") or "").strip()
    current_comment = (payload.get("current_comment") or "").strip()

    with engine.begin() as conn:
        role_id = get_user_role_id(conn, current_user_id)

        task = load_task_full(conn, task_id=int(task_id))
        task = ensure_task_visible_or_404(
            current_user_id=current_user_id,
            current_role_id=role_id,
            task_row=task,
            include_archived=False,
        )

        if not can_approve(current_user_id=current_user_id, current_role_id=role_id, task_row=task):
            raise_error(
                ErrorCode.TASK_FORBIDDEN_APPROVE,
                extra={"task_id": int(task_id), "action": "reject"},
            )

        transition(
            conn=conn,
            task_id=int(task_id),
            action="reject",
            actor_user_id=int(current_user_id),
            actor_role_id=int(role_id),
            payload={
                "reason": reason,
                "current_comment": current_comment,
            },
        )

        updated = load_task_full(conn, task_id=int(task_id))
        updated = attach_allowed_actions(task=updated, current_user_id=current_user_id, current_role_id=role_id)

    return dict(updated)


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int = Path(..., ge=1),
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
) -> Response:
    current_user_id = get_current_user_id(x_user_id)

    with engine.begin() as conn:
        role_id = get_user_role_id(conn, current_user_id)

        task = load_task_full(conn, task_id=int(task_id))
        task = ensure_task_visible_or_404(
            current_user_id=current_user_id,
            current_role_id=role_id,
            task_row=task,
            include_archived=True,
        )

        # скрываем существование: не инициатор -> 404
        if int(task.get("initiator_user_id") or 0) != int(current_user_id):
            raise HTTPException(status_code=404, detail="Task not found")

        transition(
            conn=conn,
            task_id=int(task_id),
            action="archive",
            actor_user_id=int(current_user_id),
            actor_role_id=int(role_id),
            payload={},
        )

    return Response(status_code=204)
