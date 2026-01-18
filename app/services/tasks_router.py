# app/routers/tasks_router.py
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Path, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import text

from app.db.engine import engine
from app.errors import raise_error, ErrorCode
from app.services.tasks_fsm import transition
from app.services.tasks_service import (
    get_current_user_id,
    get_user_role_id,
    is_supervisor_or_deputy,
    load_assignment_scope_enum_labels,
    normalize_assignment_scope,
    scope_label_or_none,
    get_status_id_by_code,
    load_task_full,
    ensure_task_visible_or_404,
    attach_allowed_actions,
    can_report_or_update,
    can_approve,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


# ---------------------------
# Events API models
# ---------------------------

class TaskEventOut(BaseModel):
    event_type: str
    actor_user_id: Optional[int] = None
    actor_role_id: Optional[int] = None
    created_at: str
    payload: Dict[str, Any] = {}


class MeEventOut(BaseModel):
    audit_id: int
    event_id: int
    task_id: int
    event_type: str
    actor_user_id: Optional[int] = None
    actor_role_id: Optional[int] = None
    created_at: str
    payload: Dict[str, Any] = {}


# ---------------------------
# Endpoints
# ---------------------------

@router.get("")
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

        if is_supervisor_or_deputy(role_id):
            where.append("1=1")
        else:
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
            where.append("(t.title ILIKE :q OR COALESCE(t.description,'') ILIKE :q)")
            params["q"] = f"%{search}%"

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


# IMPORTANT: /me/events MUST be defined before "/{task_id}" routes
@router.get("/me/events", response_model=List[MeEventOut])
def get_my_events(
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    since_audit_id: Optional[int] = Query(None, ge=1),
    after_id: Optional[int] = Query(None, ge=1),
    event_type: Optional[str] = Query(None),
) -> List[Dict[str, Any]]:
    current_user_id = get_current_user_id(x_user_id)
    cursor = since_audit_id if since_audit_id is not None else after_id

    et = (event_type or "").strip().upper() or None

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT
                    e.audit_id,
                    e.audit_id AS event_id,
                    e.task_id,
                    e.event_type,
                    e.actor_user_id,
                    e.actor_role_id,
                    e.created_at,
                    e.payload::text AS payload_text
                FROM task_event_recipients r
                JOIN task_events e ON e.audit_id = r.audit_id
                JOIN tasks t ON t.task_id = e.task_id
                LEFT JOIN task_statuses ts ON ts.status_id = t.status_id
                WHERE r.user_id = :uid
                  AND (:event_type IS NULL OR e.event_type = :event_type)
                  AND (:cursor IS NULL OR e.audit_id > :cursor)
                  AND COALESCE(ts.code,'') <> 'ARCHIVED'
                ORDER BY e.audit_id ASC
                LIMIT :limit OFFSET :offset
                """
            ),
            {
                "uid": int(current_user_id),
                "limit": int(limit),
                "offset": int(offset),
                "cursor": int(cursor) if cursor is not None else None,
                "event_type": et,
            },
        ).mappings().all()

    out: List[Dict[str, Any]] = []
    for r in rows:
        payload = {}
        try:
            if r.get("payload_text"):
                payload = json.loads(r["payload_text"])
        except Exception:
            payload = {}

        created_at = r.get("created_at")
        out.append(
            {
                "audit_id": int(r["audit_id"]),
                "event_id": int(r["event_id"]),
                "task_id": int(r["task_id"]),
                "event_type": r["event_type"],
                "actor_user_id": r["actor_user_id"],
                "actor_role_id": r["actor_role_id"],
                "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
                "payload": payload,
            }
        )

    return out


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


@router.post("")
def create_task(
    payload: Dict[str, Any],
    x_user_id: Optional[int] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    """
    CREATE НЕ ЯВЛЯЕТСЯ ACTION FSM.
    FSM применяется только к переходам статуса: report/approve/reject/archive.
    """
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
                "regular_task_id": payload.get("regular_task_id"),
                "title": title,
                "description": payload.get("description"),
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
