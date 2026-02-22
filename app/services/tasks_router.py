# FILE: app/services/tasks_router.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, HTTPException, Path, Query, Security
from fastapi.responses import Response
from sqlalchemy import bindparam, text

from app.auth import get_current_user  # JWT dependency
from app.db.engine import engine
from app.errors import ErrorCode, raise_error
from app.services.tasks_fsm import transition
from app.services.tasks_service import (
    attach_allowed_actions,
    can_approve,
    can_report_or_update,
    compute_visible_executor_role_ids_for_tasks,
    ensure_task_visible_or_404,
    get_status_id_by_code,
    get_user_role_id,
    load_assignment_scope_enum_labels,
    load_task_full,
    normalize_assignment_scope,
    scope_label_or_none,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


# -----------------------
# small parsing helpers
# -----------------------
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
    return str(v).strip() or None


def _pick_str(payload: Dict[str, Any], keys: List[str]) -> str:
    for k in keys:
        v = payload.get(k)
        if isinstance(v, str):
            s = v.strip()
            if s:
                return s
    return ""


# -----------------------
# endpoints
# -----------------------

# Support both /tasks and /tasks/ to avoid 307 redirects in some clients.
@router.get("")
@router.get("/")
def list_tasks(
    period_id: Optional[int] = Query(None, ge=1),
    status_code: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    include_archived: bool = Query(False),
    # filter by executor role
    executor_role_id: Optional[int] = Query(None, ge=1),
    # filter by assignment scope: admin|functional|all
    assignment_scope: Optional[str] = Query(
        None,
        description="Filter by assignment scope: admin|functional|all. If omitted or 'all' -> no filtering.",
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: Dict[str, Any] = Security(get_current_user),
) -> Dict[str, Any]:
    current_user_id = int(user["user_id"])
    params: Dict[str, Any] = {"limit": int(limit), "offset": int(offset)}

    with engine.begin() as conn:
        role_id = get_user_role_id(conn, current_user_id)
        params["role_id"] = int(role_id)
        params["current_user_id"] = int(current_user_id)

        # Role-scope (2-level) for task visibility
        visible_roles: Set[int] = compute_visible_executor_role_ids_for_tasks(user_id=int(current_user_id))
        visible_roles_list = sorted({int(x) for x in visible_roles if int(x) > 0})
        if not visible_roles_list:
            # как минимум собственная роль должна быть, но если в БД мусор — деградируем безопасно
            visible_roles_list = [int(role_id)]
        params["visible_role_ids"] = visible_roles_list

        allowed = load_assignment_scope_enum_labels(conn)
        if not allowed:
            raise HTTPException(status_code=500, detail="assignment_scope_t enum not found in DB")

        functional_lbl = scope_label_or_none(allowed, "functional")
        admin_lbl = scope_label_or_none(allowed, "admin")
        _ = functional_lbl, admin_lbl  # silence linters

        where: List[str] = []

        # ЕДИНОЕ правило видимости:
        # - инициатор видит свои
        # - видит, если executor_role_id в role-scope (director->deputies; deputy->supervisors; supervisor->subordinates)
        where.append(
            "("
            "(t.initiator_user_id = :current_user_id) "
            "OR (t.executor_role_id IN :visible_role_ids)"
            ")"
        )

        # explicit executor_role_id filter (does NOT bypass RBAC)
        if executor_role_id is not None:
            erid = int(executor_role_id)
            if erid not in set(visible_roles_list):
                # фильтр просит чужую роль — гарантированно пусто
                return {"total": 0, "limit": int(limit), "offset": int(offset), "items": []}
            where.append("t.executor_role_id = :executor_role_id")
            params["executor_role_id"] = erid

        if period_id is not None:
            where.append("t.period_id = :period_id")
            params["period_id"] = int(period_id)

        if status_code:
            where.append("ts.code = :status_code")
            params["status_code"] = status_code.strip()

        if (not status_code) and (not include_archived):
            where.append("COALESCE(ts.code,'') <> 'ARCHIVED'")

        scope_raw = (assignment_scope or "").strip().lower()
        if scope_raw and scope_raw != "all":
            norm_scope = normalize_assignment_scope(conn, scope_raw)
            where.append("t.assignment_scope = :assignment_scope")
            params["assignment_scope"] = norm_scope

        if search:
            q = search.strip()
            if q:
                where.append("(t.title ILIKE :q OR COALESCE(t.description,'') ILIKE :q)")
                params["q"] = f"%{q}%"

        where_sql = " AND ".join(where) if where else "1=1"

        count_sql = (
            text(
                f"""
                SELECT COUNT(1)
                FROM tasks t
                LEFT JOIN task_statuses ts ON ts.status_id = t.status_id
                WHERE {where_sql}
                """
            )
            .bindparams(bindparam("visible_role_ids", expanding=True))
        )

        total = (conn.execute(count_sql, params).scalar() or 0)

        # IMPORTANT:
        # task_reports должен быть доступен в списке задач (UI).
        # Даже если когда-нибудь task_reports станет "много строк на task_id" (история),
        # мы всё равно должны возвращать "последний" отчёт. Поэтому используем LATERAL.
        #
        # Дополнительно:
        # - отдаём role_name/role_code отправителя отчёта (submitted_by),
        #   чтобы UI показывал "кто отправил" не как ID.
        select_sql = (
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
                    t.due_date,
                    ts.code AS status_code,
                    ts.name_ru AS status_name_ru,

                    tr.report_link AS report_link,
                    tr.submitted_at AS report_submitted_at,
                    tr.submitted_by AS report_submitted_by,
                    tr.submitted_by_role_name AS report_submitted_by_role_name,
                    tr.submitted_by_role_code AS report_submitted_by_role_code,

                    tr.approved_at AS report_approved_at,
                    tr.approved_by AS report_approved_by,
                    tr.current_comment AS report_current_comment
                FROM tasks t
                LEFT JOIN task_statuses ts ON ts.status_id = t.status_id
                LEFT JOIN LATERAL (
                    SELECT
                        r.report_link,
                        r.submitted_at,
                        r.submitted_by,
                        rs.name AS submitted_by_role_name,
                        rs.code AS submitted_by_role_code,
                        r.approved_at,
                        r.approved_by,
                        r.current_comment
                    FROM task_reports r
                    LEFT JOIN users us ON us.user_id = r.submitted_by
                    LEFT JOIN roles rs ON rs.role_id = us.role_id
                    WHERE r.task_id = t.task_id
                    ORDER BY
                        r.submitted_at DESC NULLS LAST,
                        r.approved_at  DESC NULLS LAST
                    LIMIT 1
                ) tr ON TRUE
                WHERE {where_sql}
                ORDER BY t.task_id DESC
                LIMIT :limit OFFSET :offset
                """
            )
            .bindparams(bindparam("visible_role_ids", expanding=True))
        )

        rows = conn.execute(select_sql, params).mappings().all()

        items: List[Dict[str, Any]] = []
        for r in rows:
            t = dict(r)
            t = attach_allowed_actions(task=t, current_user_id=current_user_id, current_role_id=role_id)
            items.append(t)

    return {"total": int(total), "limit": int(limit), "offset": int(offset), "items": items}


@router.get("/{task_id}")
def get_task(
    task_id: int = Path(..., ge=1),
    include_archived: bool = Query(False),
    user: Dict[str, Any] = Security(get_current_user),
) -> Dict[str, Any]:
    current_user_id = int(user["user_id"])

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
    user: Dict[str, Any] = Security(get_current_user),
) -> Dict[str, Any]:
    current_user_id = int(user["user_id"])

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

    # Optional: allow API callers to set due_date explicitly (YYYY-MM-DD).
    due_date = _as_str_or_none(payload.get("due_date"))

    with engine.begin() as conn:
        assignment_scope = normalize_assignment_scope(conn, payload.get("assignment_scope"))
        status_id = get_status_id_by_code(conn, status_code)

        row = conn.execute(
            text(
                """
                INSERT INTO tasks (
                    period_id, regular_task_id, title, description,
                    initiator_user_id, executor_role_id, assignment_scope, status_id,
                    due_date
                )
                VALUES (
                    :period_id, :regular_task_id, :title, :description,
                    :initiator_user_id, :executor_role_id, :assignment_scope, :status_id,
                    CASE
                        WHEN :due_date IS NULL OR :due_date = '' THEN NULL
                        ELSE (:due_date)::date
                    END
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
                "due_date": due_date,
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
    user: Dict[str, Any] = Security(get_current_user),
) -> Dict[str, Any]:
    current_user_id = int(user["user_id"])

    report_link = (payload.get("report_link") or "").strip()
    if not report_link:
        raise HTTPException(status_code=422, detail="report_link is required")

    current_comment = _pick_str(payload, ["current_comment", "comment"])
    reason = _pick_str(payload, ["reason"])

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
            payload={"report_link": report_link, "current_comment": current_comment, "reason": reason},
        )

        updated = load_task_full(conn, task_id=int(task_id))
        updated = attach_allowed_actions(task=updated, current_user_id=current_user_id, current_role_id=role_id)

    return dict(updated)


@router.post("/{task_id}/approve")
def approve_report(
    payload: Dict[str, Any],
    task_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Security(get_current_user),
) -> Dict[str, Any]:
    """
    UI contract: POST /tasks/{id}/approve { reason? }
    Backward-compat: supports { approve: true|false, current_comment? } and will route approve=false to REJECT.
    """
    current_user_id = int(user["user_id"])

    approve_raw = payload.get("approve", True)
    approve = bool(approve_raw) if isinstance(approve_raw, bool) else True

    reason = _pick_str(payload, ["reason", "current_comment", "comment"])
    current_comment = _pick_str(payload, ["current_comment", "comment"])

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
            payload={"reason": reason, "current_comment": current_comment},
        )

        updated = load_task_full(conn, task_id=int(task_id))
        updated = attach_allowed_actions(task=updated, current_user_id=current_user_id, current_role_id=role_id)

    return dict(updated)


@router.post("/{task_id}/reject")
def reject_report(
    payload: Dict[str, Any],
    task_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Security(get_current_user),
) -> Dict[str, Any]:
    """
    UI contract: POST /tasks/{id}/reject { reason? }
    """
    current_user_id = int(user["user_id"])

    reason = _pick_str(payload, ["reason", "current_comment", "comment"])
    current_comment = _pick_str(payload, ["current_comment", "comment"])

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
            payload={"reason": reason, "current_comment": current_comment},
        )

        updated = load_task_full(conn, task_id=int(task_id))
        updated = attach_allowed_actions(task=updated, current_user_id=current_user_id, current_role_id=role_id)

    return dict(updated)


@router.post("/{task_id}/archive")
def archive_task(
    payload: Dict[str, Any],
    task_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Security(get_current_user),
) -> Dict[str, Any]:
    """
    UI contract: POST /tasks/{id}/archive { reason? }
    Keeps legacy DELETE /tasks/{id} for backward compatibility.
    """
    current_user_id = int(user["user_id"])

    reason = _pick_str(payload, ["reason", "current_comment", "comment"])
    current_comment = _pick_str(payload, ["current_comment", "comment"])

    with engine.begin() as conn:
        role_id = get_user_role_id(conn, current_user_id)

        task = load_task_full(conn, task_id=int(task_id))
        task = ensure_task_visible_or_404(
            current_user_id=current_user_id,
            current_role_id=role_id,
            task_row=task,
            include_archived=True,
        )

        # current policy: hide existence if not initiator
        if int(task.get("initiator_user_id") or 0) != int(current_user_id):
            raise HTTPException(status_code=404, detail="Task not found")

        transition(
            conn=conn,
            task_id=int(task_id),
            action="archive",
            actor_user_id=int(current_user_id),
            actor_role_id=int(role_id),
            payload={"reason": reason, "current_comment": current_comment},
        )

        updated = load_task_full(conn, task_id=int(task_id))
        updated = attach_allowed_actions(task=updated, current_user_id=current_user_id, current_role_id=role_id)

    return dict(updated)


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int = Path(..., ge=1),
    user: Dict[str, Any] = Security(get_current_user),
) -> Response:
    """
    Legacy archive endpoint (kept).
    Prefer POST /tasks/{id}/archive for UI.
    """
    current_user_id = int(user["user_id"])

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