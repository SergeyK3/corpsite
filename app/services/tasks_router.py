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
    SYSTEM_ADMIN_ROLE_ID,
    SUPERVISOR_ROLE_IDS,
    DEPUTY_ROLE_IDS,
    DIRECTOR_ROLE_IDS,
    attach_allowed_actions,
    can_approve,
    can_report_or_update,
    compute_visible_executor_role_ids_for_tasks,
    ensure_task_visible_or_404,
    get_manual_task_role_options_for_user,
    get_status_id_by_code,
    get_user_role_id,
    load_assignment_scope_enum_labels,
    load_task_full,
    normalize_assignment_scope,
    parse_int_set_env,
    scope_label_or_none,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _is_system_admin_role_id(role_id: Any) -> bool:
    try:
        return int(role_id) == int(SYSTEM_ADMIN_ROLE_ID)
    except Exception:
        return False


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


def _as_bool(v: Any, default: bool) -> bool:
    if v is None:
        return bool(default)
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return bool(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"1", "true", "yes", "y", "on"}:
            return True
        if s in {"0", "false", "no", "n", "off"}:
            return False
    return bool(default)


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


def _normalize_status_filter(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip().lower()
    if not s:
        return None
    if s in {"active", "done", "rejected"}:
        return s
    raise HTTPException(status_code=422, detail="status_filter must be one of: active, done, rejected")


def _user_reported_task(conn, task_id: int, user_id: int) -> bool:
    row = (
        conn.execute(
            text(
                """
                SELECT 1
                FROM public.task_reports r
                WHERE r.task_id = :task_id
                  AND r.submitted_by = :user_id
                LIMIT 1
                """
            ),
            {"task_id": int(task_id), "user_id": int(user_id)},
        )
        .mappings()
        .first()
    )
    return bool(row)


def _user_is_approver_for_task(conn, task_id: int, user_id: int, role_id: int) -> bool:
    row = (
        conn.execute(
            text(
                """
                SELECT 1
                FROM public.tasks t
                LEFT JOIN public.task_statuses ts ON ts.status_id = t.status_id
                LEFT JOIN public.regular_tasks rt ON rt.regular_task_id = t.regular_task_id
                WHERE t.task_id = :task_id
                  AND COALESCE(ts.code,'') = 'WAITING_APPROVAL'
                  AND (
                        COALESCE(t.approver_user_id, 0) = :user_id
                        OR COALESCE(rt.target_role_id, 0) = :role_id
                  )
                LIMIT 1
                """
            ),
            {"task_id": int(task_id), "user_id": int(user_id), "role_id": int(role_id)},
        )
        .mappings()
        .first()
    )
    return bool(row)


@router.get("")
@router.get("/")
def list_tasks(
    period_id: Optional[int] = Query(None, ge=1),
    status_code: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(
        None,
        description="UI helper filter: active|done|rejected. If status_code is set, status_filter is ignored.",
    ),
    search: Optional[str] = Query(None),
    include_archived: bool = Query(False),
    executor_role_id: Optional[int] = Query(None, ge=1),
    assignment_scope: Optional[str] = Query(
        None,
        description="Filter by assignment scope: admin|functional|all. If omitted or 'all' -> no filtering.",
    ),
    task_kind: Optional[str] = Query(
        None,
        description="Filter by task kind: regular|adhoc",
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: Dict[str, Any] = Security(get_current_user),
) -> Dict[str, Any]:
    current_user_id = int(user["user_id"])
    params: Dict[str, Any] = {"limit": int(limit), "offset": int(offset)}

    sf = _normalize_status_filter(status_filter)

    with engine.begin() as conn:
        role_id = get_user_role_id(conn, current_user_id)
        params["role_id"] = int(role_id)
        params["current_user_id"] = int(current_user_id)

        privileged_role_ids = parse_int_set_env("DIRECTORY_PRIVILEGED_ROLE_IDS")
        privileged_user_ids = parse_int_set_env("DIRECTORY_PRIVILEGED_USER_IDS")

        is_system_admin = _is_system_admin_role_id(role_id)
        is_privileged = (
            is_system_admin
            or (int(current_user_id) in privileged_user_ids)
            or (int(role_id) in privileged_role_ids)
        )

        if is_system_admin:
            visible_roles_list: List[int] = []
            is_manager = True
        else:
            visible_roles: Set[int] = compute_visible_executor_role_ids_for_tasks(user_id=int(current_user_id))
            visible_roles_list = sorted({int(x) for x in visible_roles if int(x) > 0})

            if not visible_roles_list:
                visible_roles_list = [int(role_id)]

            is_manager = (
                is_privileged
                or (int(role_id) in DIRECTOR_ROLE_IDS)
                or (int(role_id) in DEPUTY_ROLE_IDS)
                or (int(role_id) in SUPERVISOR_ROLE_IDS)
                or (len(visible_roles_list) > 1)
            )

            if not is_manager:
                visible_roles_list = [int(role_id)]

            params["visible_role_ids"] = visible_roles_list

        allowed = load_assignment_scope_enum_labels(conn)
        if not allowed:
            raise HTTPException(status_code=500, detail="assignment_scope_t enum not found in DB")

        functional_lbl = scope_label_or_none(allowed, "functional")
        admin_lbl = scope_label_or_none(allowed, "admin")
        _ = functional_lbl, admin_lbl

        where: List[str] = []

        if not is_system_admin:
            report_visibility = """
                EXISTS (
                    SELECT 1
                    FROM public.task_reports rr
                    WHERE rr.task_id = t.task_id
                      AND rr.submitted_by = :current_user_id
                )
            """.strip()

            explicit_approver_visibility = """
                COALESCE(t.approver_user_id, 0) = :current_user_id
                AND COALESCE(ts.code,'') = 'WAITING_APPROVAL'
            """.strip()

            legacy_approver_visibility = """
                EXISTS (
                    SELECT 1
                    FROM public.regular_tasks rt
                    WHERE rt.regular_task_id = t.regular_task_id
                      AND COALESCE(rt.target_role_id, 0) = :role_id
                )
                AND COALESCE(ts.code,'') = 'WAITING_APPROVAL'
            """.strip()

            if is_manager:
                where.append(
                    "("
                    "(t.initiator_user_id = :current_user_id) "
                    "OR (t.created_by_user_id = :current_user_id) "
                    "OR (t.executor_role_id IN :visible_role_ids) "
                    f"OR ({report_visibility}) "
                    f"OR ({explicit_approver_visibility}) "
                    f"OR ({legacy_approver_visibility})"
                    ")"
                )
            else:
                where.append(
                    "("
                    "(t.executor_role_id IN :visible_role_ids) "
                    f"OR ({report_visibility}) "
                    f"OR ({explicit_approver_visibility}) "
                    f"OR ({legacy_approver_visibility})"
                    ")"
                )

        if executor_role_id is not None:
            erid = int(executor_role_id)
            where.append("t.executor_role_id = :executor_role_id")
            params["executor_role_id"] = erid

        if period_id is not None:
            where.append("t.period_id = :period_id")
            params["period_id"] = int(period_id)

        if status_code:
            where.append("ts.code = :status_code")
            params["status_code"] = status_code.strip()
        else:
            if sf == "active":
                where.append("COALESCE(ts.code,'') IN ('IN_PROGRESS','WAITING_REPORT','WAITING_APPROVAL')")
            elif sf == "done":
                where.append("COALESCE(ts.code,'') IN ('DONE')")
            elif sf == "rejected":
                where.append("COALESCE(ts.code,'') IN ('REJECTED')")
            else:
                if not include_archived:
                    where.append("COALESCE(ts.code,'') <> 'ARCHIVED'")

        scope_raw = (assignment_scope or "").strip().lower()
        if scope_raw and scope_raw != "all":
            norm_scope = normalize_assignment_scope(conn, scope_raw)
            where.append("t.assignment_scope = :assignment_scope")
            params["assignment_scope"] = norm_scope

        kind_raw = (task_kind or "").strip().lower()
        if kind_raw:
            if kind_raw not in {"regular", "adhoc"}:
                raise HTTPException(status_code=422, detail="task_kind must be one of: regular, adhoc")
            where.append("COALESCE(t.task_kind, 'regular') = :task_kind")
            params["task_kind"] = kind_raw

        if search:
            q = search.strip()
            if q:
                where.append("(t.title ILIKE :q OR COALESCE(t.description,'') ILIKE :q)")
                params["q"] = f"%{q}%"

        where_sql = " AND ".join(where) if where else "1=1"

        count_text = f"""
            SELECT COUNT(1)
            FROM public.tasks t
            LEFT JOIN public.task_statuses ts ON ts.status_id = t.status_id
            WHERE {where_sql}
        """
        select_text = f"""
            SELECT
                t.task_id,
                t.period_id,
                t.regular_task_id,
                t.title,
                t.description,
                t.initiator_user_id,
                t.created_by_user_id,
                t.approver_user_id,
                t.executor_role_id,
                t.assignment_scope,
                t.status_id,
                t.task_kind,
                t.requires_report,
                t.requires_approval,
                t.source_kind,
                t.source_note,
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
            FROM public.tasks t
            LEFT JOIN public.task_statuses ts ON ts.status_id = t.status_id
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
                FROM public.task_reports r
                LEFT JOIN public.users us ON us.user_id = r.submitted_by
                LEFT JOIN public.roles rs ON rs.role_id = us.role_id
                WHERE r.task_id = t.task_id
                ORDER BY
                    r.submitted_at DESC NULLS LAST,
                    r.approved_at  DESC NULLS LAST,
                    r.report_id    DESC
                LIMIT 1
            ) tr ON TRUE
            WHERE {where_sql}
            ORDER BY t.task_id DESC
            LIMIT :limit OFFSET :offset
        """

        if is_system_admin:
            count_sql = text(count_text)
            select_sql = text(select_text)
        else:
            count_sql = text(count_text).bindparams(bindparam("visible_role_ids", expanding=True))
            select_sql = text(select_text).bindparams(bindparam("visible_role_ids", expanding=True))

        total = (conn.execute(count_sql, params).scalar() or 0)
        rows = conn.execute(select_sql, params).mappings().all()

        items: List[Dict[str, Any]] = []
        for r in rows:
            t = dict(r)
            t = attach_allowed_actions(task=t, current_user_id=current_user_id, current_role_id=role_id)
            items.append(t)

    return {"total": int(total), "limit": int(limit), "offset": int(offset), "items": items}


@router.get("/manual/available-roles")
def get_manual_task_available_roles(
    period_id: Optional[int] = Query(None, ge=1),
    user: Dict[str, Any] = Security(get_current_user),
) -> Dict[str, Any]:
    current_user_id = int(user["user_id"])

    with engine.begin() as conn:
        result = get_manual_task_role_options_for_user(conn, current_user_id=int(current_user_id))

    return {
        "period_id": int(period_id) if period_id is not None else None,
        "can_create_manual_task": bool(result["can_create_manual_task"]),
        "items": result["items"],
    }


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

        try:
            task = ensure_task_visible_or_404(
                current_user_id=current_user_id,
                current_role_id=role_id,
                task_row=task,
                include_archived=include_archived,
            )
        except HTTPException as e:
            if e.status_code in (403, 404):
                if _user_reported_task(conn, task_id=int(task_id), user_id=int(current_user_id)):
                    task = task
                elif _user_is_approver_for_task(
                    conn,
                    task_id=int(task_id),
                    user_id=int(current_user_id),
                    role_id=int(role_id),
                ):
                    task = task
                else:
                    raise
            else:
                raise

        task = attach_allowed_actions(task=task, current_user_id=current_user_id, current_role_id=role_id)

    return dict(task)


@router.post("/manual")
def create_manual_task(
    payload: Dict[str, Any],
    user: Dict[str, Any] = Security(get_current_user),
) -> Dict[str, Any]:
    current_user_id = int(user["user_id"])

    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="title is required")

    period_id = _as_int_or_none(payload.get("period_id"))
    if period_id is None or period_id < 1:
        raise HTTPException(status_code=422, detail="period_id is required")

    executor_role_id = _as_int_or_none(payload.get("executor_role_id"))
    if executor_role_id is None or executor_role_id < 1:
        raise HTTPException(status_code=422, detail="executor_role_id is required")

    requires_report = _as_bool(payload.get("requires_report"), True)
    requires_approval = _as_bool(payload.get("requires_approval"), True)

    approver_user_id = _as_int_or_none(payload.get("approver_user_id"))
    description = _as_str_or_none(payload.get("description"))
    due_date = _as_str_or_none(payload.get("due_date"))
    source_note = _as_str_or_none(payload.get("source_note"))

    with engine.begin() as conn:
        manual_options = get_manual_task_role_options_for_user(conn, current_user_id=int(current_user_id))
        allowed_role_ids = {
            int(x["role_id"])
            for x in manual_options.get("items", [])
            if int(x.get("role_id") or 0) > 0
        }

        if int(executor_role_id) not in allowed_role_ids:
            raise HTTPException(status_code=403, detail="You cannot create manual task for this executor_role_id")

        assignment_scope = normalize_assignment_scope(conn, payload.get("assignment_scope"))
        status_id = get_status_id_by_code(conn, "IN_PROGRESS")

        initiator_user_id = int(current_user_id)

        row = conn.execute(
            text(
                """
                INSERT INTO public.tasks (
                    period_id,
                    regular_task_id,
                    title,
                    description,
                    initiator_user_id,
                    created_by_user_id,
                    approver_user_id,
                    executor_role_id,
                    assignment_scope,
                    status_id,
                    task_kind,
                    requires_report,
                    requires_approval,
                    source_kind,
                    source_note,
                    due_date
                )
                VALUES (
                    :period_id,
                    NULL,
                    :title,
                    :description,
                    :initiator_user_id,
                    :created_by_user_id,
                    :approver_user_id,
                    :executor_role_id,
                    :assignment_scope,
                    :status_id,
                    'adhoc',
                    :requires_report,
                    :requires_approval,
                    'manual',
                    :source_note,
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
                "title": title,
                "description": description,
                "initiator_user_id": int(initiator_user_id),
                "created_by_user_id": int(current_user_id),
                "approver_user_id": int(approver_user_id) if approver_user_id is not None else None,
                "executor_role_id": int(executor_role_id),
                "assignment_scope": assignment_scope,
                "status_id": int(status_id),
                "requires_report": bool(requires_report),
                "requires_approval": bool(requires_approval),
                "source_note": source_note,
                "due_date": due_date,
            },
        ).mappings().first()

        if not row or row.get("task_id") is None:
            raise HTTPException(status_code=500, detail="Failed to create manual task")

        task_id = int(row["task_id"])
        role_id = get_user_role_id(conn, current_user_id)

        task = load_task_full(conn, task_id=task_id)
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
    due_date = _as_str_or_none(payload.get("due_date"))

    created_by_user_id = _as_int_or_none(payload.get("created_by_user_id")) or int(current_user_id)
    initiator_user_id = _as_int_or_none(payload.get("initiator_user_id")) or int(current_user_id)
    approver_user_id = _as_int_or_none(payload.get("approver_user_id"))
    task_kind = (_as_str_or_none(payload.get("task_kind")) or ("regular" if regular_task_id is not None else "adhoc")).lower()
    requires_report = _as_bool(payload.get("requires_report"), True)
    requires_approval = _as_bool(payload.get("requires_approval"), True)
    source_kind = (_as_str_or_none(payload.get("source_kind")) or ("regular_task" if regular_task_id is not None else "manual")).lower()
    source_note = _as_str_or_none(payload.get("source_note"))

    if task_kind not in {"regular", "adhoc"}:
        raise HTTPException(status_code=422, detail="task_kind must be one of: regular, adhoc")

    if source_kind not in {"regular_task", "manual", "bot", "import"}:
        raise HTTPException(status_code=422, detail="source_kind must be one of: regular_task, manual, bot, import")

    if requires_approval and (approver_user_id is None or approver_user_id < 1):
        if task_kind == "adhoc":
            raise HTTPException(status_code=422, detail="approver_user_id is required when requires_approval=true for adhoc task")

    with engine.begin() as conn:
        assignment_scope = normalize_assignment_scope(conn, payload.get("assignment_scope"))
        status_id = get_status_id_by_code(conn, status_code)

        row = conn.execute(
            text(
                """
                INSERT INTO public.tasks (
                    period_id,
                    regular_task_id,
                    title,
                    description,
                    initiator_user_id,
                    created_by_user_id,
                    approver_user_id,
                    executor_role_id,
                    assignment_scope,
                    status_id,
                    task_kind,
                    requires_report,
                    requires_approval,
                    source_kind,
                    source_note,
                    due_date
                )
                VALUES (
                    :period_id,
                    :regular_task_id,
                    :title,
                    :description,
                    :initiator_user_id,
                    :created_by_user_id,
                    :approver_user_id,
                    :executor_role_id,
                    :assignment_scope,
                    :status_id,
                    :task_kind,
                    :requires_report,
                    :requires_approval,
                    :source_kind,
                    :source_note,
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
                "initiator_user_id": int(initiator_user_id),
                "created_by_user_id": int(created_by_user_id),
                "approver_user_id": int(approver_user_id) if approver_user_id is not None else None,
                "executor_role_id": int(executor_role_id),
                "assignment_scope": assignment_scope,
                "status_id": int(status_id),
                "task_kind": task_kind,
                "requires_report": bool(requires_report),
                "requires_approval": bool(requires_approval),
                "source_kind": source_kind,
                "source_note": source_note,
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
    current_user_id = int(user["user_id"])

    approve_raw = payload.get("approve", True)
    approve = bool(approve_raw) if isinstance(approve_raw, bool) else True

    reason = _pick_str(payload, ["reason", "current_comment", "comment"])
    current_comment = _pick_str(payload, ["current_comment", "comment"])

    with engine.begin() as conn:
        role_id = get_user_role_id(conn, current_user_id)

        task = load_task_full(conn, task_id=int(task_id))
        try:
            task = ensure_task_visible_or_404(
                current_user_id=current_user_id,
                current_role_id=role_id,
                task_row=task,
                include_archived=False,
            )
        except HTTPException as e:
            if e.status_code in (403, 404) and _user_is_approver_for_task(
                conn,
                task_id=int(task_id),
                user_id=int(current_user_id),
                role_id=int(role_id),
            ):
                task = task
            else:
                raise

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
    current_user_id = int(user["user_id"])

    reason = _pick_str(payload, ["reason", "current_comment", "comment"])
    current_comment = _pick_str(payload, ["current_comment", "comment"])

    with engine.begin() as conn:
        role_id = get_user_role_id(conn, current_user_id)

        task = load_task_full(conn, task_id=int(task_id))
        try:
            task = ensure_task_visible_or_404(
                current_user_id=current_user_id,
                current_role_id=role_id,
                task_row=task,
                include_archived=False,
            )
        except HTTPException as e:
            if e.status_code in (403, 404) and _user_is_approver_for_task(
                conn,
                task_id=int(task_id),
                user_id=int(current_user_id),
                role_id=int(role_id),
            ):
                task = task
            else:
                raise

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

        if (not _is_system_admin_role_id(role_id)) and int(task.get("initiator_user_id") or 0) != int(current_user_id):
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
    hard: bool = Query(False, description="For ADMIN: hard delete task and related reports/audit rows."),
    user: Dict[str, Any] = Security(get_current_user),
) -> Response:
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

        if hard:
            if not _is_system_admin_role_id(role_id):
                raise HTTPException(status_code=403, detail="Only ADMIN can hard-delete tasks")

            conn.execute(
                text(
                    """
                    DELETE FROM public.task_event_deliveries
                    WHERE audit_id IN (
                        SELECT e.audit_id
                        FROM public.task_events e
                        WHERE e.task_id = :task_id
                    )
                    """
                ),
                {"task_id": int(task_id)},
            )
            conn.execute(
                text(
                    """
                    DELETE FROM public.task_event_recipients
                    WHERE audit_id IN (
                        SELECT e.audit_id
                        FROM public.task_events e
                        WHERE e.task_id = :task_id
                    )
                    """
                ),
                {"task_id": int(task_id)},
            )
            conn.execute(
                text("DELETE FROM public.task_reports WHERE task_id = :task_id"),
                {"task_id": int(task_id)},
            )
            conn.execute(
                text("DELETE FROM public.task_audit_log WHERE task_id = :task_id"),
                {"task_id": int(task_id)},
            )
            conn.execute(
                text("DELETE FROM public.task_events WHERE task_id = :task_id"),
                {"task_id": int(task_id)},
            )
            conn.execute(
                text("DELETE FROM public.tasks WHERE task_id = :task_id"),
                {"task_id": int(task_id)},
            )
            return Response(status_code=204)

        if (not _is_system_admin_role_id(role_id)) and int(task.get("initiator_user_id") or 0) != int(current_user_id):
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