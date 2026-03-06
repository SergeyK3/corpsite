# FILE: app/services/tasks_fsm.py
from __future__ import annotations

from typing import Any, Dict, Optional, Set, Tuple

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.errors import ErrorCode, raise_error
from app.events import create_task_event_tx
from app.services.tasks_service import get_status_id_by_code, write_task_audit

LOCAL_TZ = "Asia/Almaty"


class TaskFSMError(Exception):
    pass


def transition(
    *,
    conn: Connection,
    task_id: int,
    action: str,
    actor_user_id: int,
    actor_role_id: int,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    payload = payload or {}

    row = conn.execute(
        text(
            """
            SELECT t.task_id, ts.code AS status_code
            FROM tasks t
            JOIN task_statuses ts ON ts.status_id = t.status_id
            WHERE t.task_id = :tid
            """
        ),
        {"tid": int(task_id)},
    ).mappings().first()

    if not row:
        raise TaskFSMError("Task not found")

    from_status = str(row["status_code"] or "")

    if action == "report":
        _report(conn, task_id, from_status, actor_user_id, actor_role_id, payload)
        return

    if action == "approve":
        _approve(conn, task_id, from_status, actor_user_id, actor_role_id, payload)
        return

    if action == "reject":
        _reject(conn, task_id, from_status, actor_user_id, actor_role_id, payload)
        return

    if action == "archive":
        _archive(conn, task_id, from_status, actor_user_id, actor_role_id)
        return

    raise TaskFSMError(f"Unknown action: {action}")


# ---------------------------
# Helpers
# ---------------------------

def _apply_comment_sql() -> str:
    return """
        current_comment = CASE
            WHEN :comment IS NULL OR :comment = '' THEN current_comment
            ELSE :comment
        END
    """


def _normalize_comment(payload: Dict[str, Any]) -> str:
    v = payload.get("current_comment")
    if v is None or str(v).strip() == "":
        v = payload.get("reason")
    return (v or "").strip()


def _get_latest_report_row(conn: Connection, task_id: int) -> Dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT report_id, submitted_by
            FROM public.task_reports
            WHERE task_id = :tid
            ORDER BY report_id DESC
            LIMIT 1
            """
        ),
        {"tid": int(task_id)},
    ).mappings().first()
    if not row or row.get("report_id") is None:
        raise_error(ErrorCode.TASK_CONFLICT_APPROVE_NO_REPORT, extra={"task_id": int(task_id)})
    return dict(row)


def _ensure_report_exists(conn: Connection, task_id: int) -> None:
    _get_latest_report_row(conn, task_id)


def _set_status(
    conn: Connection,
    task_id: int,
    from_status: str,
    to_status: str,
    allowed_from: Set[str],
) -> None:
    if from_status not in allowed_from:
        raise_error(
            ErrorCode.TASK_CONFLICT_ACTION_STATUS,
            extra={
                "task_id": int(task_id),
                "current_status": from_status,
                "allowed_from": sorted(allowed_from),
                "status_to": to_status,
            },
        )

    if to_status == "WAITING_APPROVAL":
        _ensure_report_exists(conn, task_id)

    status_id = get_status_id_by_code(conn, to_status)

    conn.execute(
        text("UPDATE tasks SET status_id = :sid WHERE task_id = :tid"),
        {"sid": int(status_id), "tid": int(task_id)},
    )


def _extract_report_link(payload: Dict[str, Any]) -> str:
    v = payload.get("report_link")
    s = (v or "").strip()
    if not s:
        raise HTTPException(status_code=422, detail="report_link is required")
    return s


def _get_roles_for_task_flow(conn: Connection, task_id: int) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """
    Возвращает (regular_task_id, performer_role_id, approver_role_id).

    Правило (долгосрок):
    - performer_role_id = regular_tasks.executor_role_id
    - approver_role_id  = regular_tasks.target_role_id

    Если regular_task_id NULL или записи нет — вернём (None, None, None).
    """
    row = conn.execute(
        text(
            """
            SELECT t.regular_task_id
            FROM public.tasks t
            WHERE t.task_id = :tid
            """
        ),
        {"tid": int(task_id)},
    ).mappings().first()
    if not row or row.get("regular_task_id") is None:
        return None, None, None

    rid = int(row["regular_task_id"])
    rt = conn.execute(
        text(
            """
            SELECT regular_task_id, executor_role_id, target_role_id
            FROM public.regular_tasks
            WHERE regular_task_id = :rid
            """
        ),
        {"rid": int(rid)},
    ).mappings().first()
    if not rt:
        return rid, None, None

    performer = rt.get("executor_role_id")
    approver = rt.get("target_role_id")
    try:
        performer_id = int(performer) if performer is not None else None
    except Exception:
        performer_id = None
    try:
        approver_id = int(approver) if approver is not None else None
    except Exception:
        approver_id = None

    return rid, performer_id, approver_id


def _set_executor_role_if_needed(conn: Connection, task_id: int, role_id: Optional[int]) -> None:
    if role_id is None or int(role_id) <= 0:
        return
    conn.execute(
        text("UPDATE public.tasks SET executor_role_id = :rid WHERE task_id = :tid"),
        {"rid": int(role_id), "tid": int(task_id)},
    )


def _get_user_unit_id(conn: Connection, user_id: int) -> Optional[int]:
    row = conn.execute(
        text(
            """
            SELECT u.unit_id
            FROM public.users u
            WHERE u.user_id = :uid
            """
        ),
        {"uid": int(user_id)},
    ).mappings().first()
    if not row or row.get("unit_id") is None:
        return None
    try:
        unit_id = int(row["unit_id"])
        return unit_id if unit_id > 0 else None
    except Exception:
        return None


def _get_user_role_id(conn: Connection, user_id: int) -> Optional[int]:
    rr = conn.execute(
        text(
            """
            SELECT role_id
            FROM public.users
            WHERE user_id = :uid
              AND is_active = TRUE
            """
        ),
        {"uid": int(user_id)},
    ).mappings().first()
    if not rr or rr.get("role_id") is None:
        return None
    try:
        rid = int(rr["role_id"])
        return rid if rid > 0 else None
    except Exception:
        return None


def _get_parent_unit_id(conn: Connection, unit_id: int) -> Optional[int]:
    parent = conn.execute(
        text(
            """
            SELECT parent_unit_id
            FROM public.org_units
            WHERE unit_id = :unit_id
            """
        ),
        {"unit_id": int(unit_id)},
    ).mappings().first()
    if not parent or parent.get("parent_unit_id") is None:
        return None
    try:
        pid = int(parent["parent_unit_id"])
        return pid if pid > 0 else None
    except Exception:
        return None


def _find_active_head_user_id(conn: Connection, unit_id: int) -> Optional[int]:
    """
    Ищет активного HEAD для подразделения с учетом:
    - manager_type может быть в разном регистре / с пробелами
    - дата действия может быть задана через date_from/date_to
    - сам пользователь должен быть active
    """
    row = conn.execute(
        text(
            """
            SELECT m.user_id
            FROM public.org_unit_managers m
            JOIN public.users u
              ON u.user_id = m.user_id
            WHERE m.unit_id = :unit_id
              AND upper(btrim(COALESCE(m.manager_type, ''))) = 'HEAD'
              AND m.is_active = TRUE
              AND u.is_active = TRUE
              AND (m.date_from IS NULL OR m.date_from <= CURRENT_DATE)
              AND (m.date_to   IS NULL OR m.date_to   >= CURRENT_DATE)
            ORDER BY
                CASE WHEN m.date_from IS NULL THEN 1 ELSE 0 END,
                m.date_from DESC NULLS LAST,
                m.manager_id DESC
            LIMIT 1
            """
        ),
        {"unit_id": int(unit_id)},
    ).mappings().first()
    if not row or row.get("user_id") is None:
        return None
    try:
        uid = int(row["user_id"])
        return uid if uid > 0 else None
    except Exception:
        return None


def _resolve_approver_role_id_by_actor(conn: Connection, actor_user_id: int) -> Optional[int]:
    """
    Вычисляет согласующего по оргструктуре:
      - берём unit_id автора отчёта (users.unit_id)
      - ищем активного HEAD в org_unit_managers для этого unit_id
      - если HEAD == автор отчёта -> поднимаемся на parent_unit_id и повторяем
      - если нашли HEAD != автор -> возвращаем role_id этого HEAD-пользователя
    """
    unit_id = _get_user_unit_id(conn, actor_user_id)
    if unit_id is None:
        return None

    visited: Set[int] = set()

    while unit_id and unit_id not in visited:
        visited.add(int(unit_id))

        head_user_id = _find_active_head_user_id(conn, int(unit_id))
        if head_user_id is not None and int(head_user_id) != int(actor_user_id):
            return _get_user_role_id(conn, int(head_user_id))

        unit_id = _get_parent_unit_id(conn, int(unit_id))

    return None


def _resolve_approver_role_id_by_task_initiator(
    conn: Connection,
    *,
    task_id: int,
    actor_user_id: int,
) -> Optional[int]:
    """
    Fallback:
    если по org-цепочке согласующего не нашли, пытаемся взять роль инициатора задачи.
    Это полезно для случаев, когда target_role_id ещё не заполнен, а задача уже создана
    и у неё есть реальный initiator_user_id.
    """
    row = conn.execute(
        text(
            """
            SELECT t.initiator_user_id
            FROM public.tasks t
            WHERE t.task_id = :tid
            """
        ),
        {"tid": int(task_id)},
    ).mappings().first()
    if not row or row.get("initiator_user_id") is None:
        return None

    try:
        initiator_user_id = int(row["initiator_user_id"])
    except Exception:
        return None

    if initiator_user_id <= 0 or initiator_user_id == int(actor_user_id):
        return None

    return _get_user_role_id(conn, initiator_user_id)


def _lookup_role_id_by_code(conn: Connection, role_code: str) -> Optional[int]:
    r = conn.execute(
        text("SELECT role_id FROM public.roles WHERE code = :code"),
        {"code": str(role_code)},
    ).mappings().first()
    if not r or r.get("role_id") is None:
        return None
    try:
        rid = int(r["role_id"])
        return rid if rid > 0 else None
    except Exception:
        return None


def _resolve_qm_head_fallback_role_id(conn: Connection, actor_role_id: int) -> Optional[int]:
    """
    Доменное правило для ОВЭиПП:
    согласующий для ролей экспертов ОВЭиПП = QM_HEAD.

    Здесь deliberately делаем простой fallback по коду роли,
    чтобы не зависеть от заполненности org_unit_managers для этого отдела.
    """
    qm_expert_role_ids = {1, 8, 11, 17}
    if int(actor_role_id) not in qm_expert_role_ids:
        return None
    return _lookup_role_id_by_code(conn, "QM_HEAD")


def _maybe_persist_target_role_id(conn: Connection, regular_task_id: Optional[int], target_role_id: Optional[int]) -> None:
    """
    Кэшируем вычисленного согласующего в regular_tasks.target_role_id, если там пусто.
    Это убирает ручные правки и делает поведение стабильным для будущих задач.
    """
    if regular_task_id is None or target_role_id is None:
        return
    if int(regular_task_id) <= 0 or int(target_role_id) <= 0:
        return

    conn.execute(
        text(
            """
            UPDATE public.regular_tasks
            SET target_role_id = :target_role_id
            WHERE regular_task_id = :rid
              AND (target_role_id IS NULL OR target_role_id <= 0)
            """
        ),
        {"rid": int(regular_task_id), "target_role_id": int(target_role_id)},
    )


def _find_active_task_by_regular_period_scope(
    conn: Connection,
    *,
    period_id: int,
    regular_task_id: int,
    assignment_scope: str,
) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT t.task_id, t.due_date
            FROM tasks t
            JOIN task_statuses ts ON ts.status_id = t.status_id
            WHERE t.period_id = :period_id
              AND t.regular_task_id = :regular_task_id
              AND t.assignment_scope = :assignment_scope
              AND COALESCE(ts.code,'') <> 'ARCHIVED'
            ORDER BY t.created_at DESC, t.task_id DESC
            LIMIT 1
            """
        ),
        {
            "period_id": int(period_id),
            "regular_task_id": int(regular_task_id),
            "assignment_scope": str(assignment_scope),
        },
    ).mappings().first()
    return dict(row) if row else None


def _maybe_create_or_update_next_task_after_approved(
    conn: Connection,
    *,
    source_task_id: int,
    approved_at_ts: str,
) -> None:
    src = conn.execute(
        text(
            """
            SELECT
                t.task_id,
                t.period_id,
                t.regular_task_id,
                t.initiator_user_id,
                t.assignment_scope,
                t.title AS src_title
            FROM tasks t
            WHERE t.task_id = :tid
            """
        ),
        {"tid": int(source_task_id)},
    ).mappings().first()

    if not src:
        return

    regular_task_id = src.get("regular_task_id")
    if regular_task_id is None:
        return

    rt = conn.execute(
        text(
            """
            SELECT
                regular_task_id,
                title,
                target_role_id,
                escalation_offset_days
            FROM regular_tasks
            WHERE regular_task_id = :rid
              AND is_active = TRUE
            """
        ),
        {"rid": int(regular_task_id)},
    ).mappings().first()

    if not rt:
        return

    tr = rt.get("target_role_id")
    if tr is None:
        return
    try:
        target_role_id = int(tr)
    except Exception:
        return
    if target_role_id <= 0:
        return

    offset_days = int(rt.get("escalation_offset_days") or 0)

    period_id = int(src["period_id"])
    assignment_scope = str(src.get("assignment_scope") or "functional")

    existing = _find_active_task_by_regular_period_scope(
        conn,
        period_id=period_id,
        regular_task_id=int(regular_task_id),
        assignment_scope=assignment_scope,
    )

    description = (
        f"Основание: APPROVED по задаче #{int(source_task_id)} "
        f"({str(src.get('src_title') or '').strip()})"
    )

    if existing and existing.get("task_id"):
        conn.execute(
            text(
                """
                UPDATE tasks
                SET
                    due_date = CASE
                        WHEN due_date IS NULL THEN (
                            ((:approved_at_ts)::timestamptz AT TIME ZONE :tz)::date
                            + :offset_days
                        )
                        ELSE due_date
                    END,
                    description = CASE
                        WHEN (description IS NULL OR description = '') THEN :description
                        ELSE description
                    END
                WHERE task_id = :tid
                """
            ),
            {
                "tid": int(existing["task_id"]),
                "approved_at_ts": approved_at_ts,
                "tz": LOCAL_TZ,
                "offset_days": int(offset_days),
                "description": description,
            },
        )
        return

    status_id = get_status_id_by_code(conn, "IN_PROGRESS")

    conn.execute(
        text(
            """
            INSERT INTO tasks (
                period_id,
                regular_task_id,
                title,
                description,
                initiator_user_id,
                executor_role_id,
                assignment_scope,
                status_id,
                due_date
            )
            VALUES (
                :period_id,
                :regular_task_id,
                :title,
                :description,
                :initiator_user_id,
                :executor_role_id,
                :assignment_scope,
                :status_id,
                (
                    ((:approved_at_ts)::timestamptz AT TIME ZONE :tz)::date
                    + :offset_days
                )
            )
            """
        ),
        {
            "period_id": int(period_id),
            "regular_task_id": int(regular_task_id),
            "title": str(rt["title"]),
            "description": description,
            "initiator_user_id": int(src["initiator_user_id"]),
            "executor_role_id": int(target_role_id),
            "assignment_scope": assignment_scope,
            "status_id": int(status_id),
            "approved_at_ts": approved_at_ts,
            "tz": LOCAL_TZ,
            "offset_days": int(offset_days),
        },
    )


# ---------------------------
# Transitions
# ---------------------------

def _report(
    conn: Connection,
    task_id: int,
    from_status: str,
    actor_user_id: int,
    actor_role_id: int,
    payload: Dict[str, Any],
) -> None:
    allowed_from = {"WAITING_REPORT", "IN_PROGRESS", "REJECTED"}
    if from_status not in allowed_from:
        raise_error(
            ErrorCode.TASK_CONFLICT_ACTION_STATUS,
            extra={
                "task_id": int(task_id),
                "current_status": from_status,
                "allowed_from": sorted(allowed_from),
                "status_to": "WAITING_APPROVAL",
            },
        )

    report_link = _extract_report_link(payload)
    comment = _normalize_comment(payload)

    ins = conn.execute(
        text(
            """
            INSERT INTO task_reports (task_id, report_link, submitted_by, current_comment, submitted_at)
            VALUES (:tid, :link, :by, :comment, now())
            RETURNING report_id
            """
        ),
        {"tid": int(task_id), "link": report_link, "by": int(actor_user_id), "comment": comment},
    ).mappings().first()

    report_id = int(ins["report_id"]) if ins and ins.get("report_id") is not None else None

    regular_task_id, _performer_role_id, approver_role_id = _get_roles_for_task_flow(conn, task_id)

    if approver_role_id is None:
        approver_role_id = _resolve_approver_role_id_by_actor(conn, actor_user_id)

    if approver_role_id is None:
        approver_role_id = _resolve_approver_role_id_by_task_initiator(
            conn,
            task_id=int(task_id),
            actor_user_id=int(actor_user_id),
        )

    if approver_role_id is None:
        approver_role_id = _resolve_qm_head_fallback_role_id(conn, actor_role_id)

    if approver_role_id is not None:
        _maybe_persist_target_role_id(conn, regular_task_id, approver_role_id)

    if approver_role_id is None:
        raise HTTPException(
            status_code=500,
            detail=(
                "Cannot resolve approver: regular_tasks.target_role_id is NULL, "
                "org chain HEAD not found, and task initiator fallback is empty"
            ),
        )

    _set_executor_role_if_needed(conn, task_id, approver_role_id)

    _set_status(
        conn,
        task_id,
        from_status,
        to_status="WAITING_APPROVAL",
        allowed_from=allowed_from,
    )

    write_task_audit(
        conn,
        task_id=int(task_id),
        actor_user_id=int(actor_user_id),
        actor_role_id=int(actor_role_id),
        action="REPORT_SUBMIT",
        fields_changed={"status_code": {"from": from_status, "to": "WAITING_APPROVAL"}},
        request_body=payload,
        meta={"report_id": report_id} if report_id is not None else None,
        event_type="REPORT_SUBMITTED",
        event_payload={**payload, "status_to": "WAITING_APPROVAL", "report_id": report_id},
    )

    create_task_event_tx(
        conn,
        task_id=int(task_id),
        event_type="REPORT_SUBMITTED",
        actor_user_id=int(actor_user_id),
        actor_role_id=int(actor_role_id),
        payload={**payload, "status_to": "WAITING_APPROVAL", "report_id": report_id},
    )


def _approve(
    conn: Connection,
    task_id: int,
    from_status: str,
    actor_user_id: int,
    actor_role_id: int,
    payload: Dict[str, Any],
) -> None:
    if from_status != "WAITING_APPROVAL":
        raise_error(
            ErrorCode.TASK_CONFLICT_ACTION_STATUS,
            extra={
                "task_id": int(task_id),
                "current_status": from_status,
                "allowed_from": ["WAITING_APPROVAL"],
                "status_to": "DONE",
            },
        )

    rr = _get_latest_report_row(conn, task_id)
    report_id = int(rr["report_id"])
    submitted_by = rr.get("submitted_by")

    try:
        if submitted_by is not None and int(submitted_by) == int(actor_user_id):
            raise HTTPException(status_code=403, detail="Cannot approve own report")
    except HTTPException:
        raise
    except Exception:
        pass

    comment = _normalize_comment(payload)

    upd = conn.execute(
        text(
            f"""
            UPDATE task_reports
            SET approved_at = now(),
                approved_by = :by,
                {_apply_comment_sql()}
            WHERE report_id = :rid
            RETURNING approved_at
            """
        ),
        {"by": int(actor_user_id), "rid": int(report_id), "comment": comment},
    ).mappings().first()

    approved_at = str(upd["approved_at"]) if upd and upd.get("approved_at") is not None else None

    _set_status(
        conn,
        task_id,
        from_status,
        to_status="DONE",
        allowed_from={"WAITING_APPROVAL"},
    )

    write_task_audit(
        conn,
        task_id=int(task_id),
        actor_user_id=int(actor_user_id),
        actor_role_id=int(actor_role_id),
        action="APPROVE",
        fields_changed={"status_code": {"from": from_status, "to": "DONE"}},
        request_body=payload,
        meta={"report_id": int(report_id)},
        event_type="APPROVED",
        event_payload={**payload, "status_to": "DONE", "report_id": int(report_id)},
    )

    create_task_event_tx(
        conn,
        task_id=int(task_id),
        event_type="APPROVED",
        actor_user_id=int(actor_user_id),
        actor_role_id=int(actor_role_id),
        payload={**payload, "status_to": "DONE", "report_id": int(report_id)},
    )

    if approved_at:
        _maybe_create_or_update_next_task_after_approved(
            conn,
            source_task_id=int(task_id),
            approved_at_ts=approved_at,
        )


def _reject(
    conn: Connection,
    task_id: int,
    from_status: str,
    actor_user_id: int,
    actor_role_id: int,
    payload: Dict[str, Any],
) -> None:
    if from_status == "WAITING_APPROVAL":
        rr = _get_latest_report_row(conn, task_id)
        report_id = int(rr["report_id"])

        _set_status(
            conn,
            task_id,
            from_status,
            to_status="WAITING_REPORT",
            allowed_from={"WAITING_APPROVAL"},
        )

        _, performer_role_id, _ = _get_roles_for_task_flow(conn, task_id)
        if performer_role_id is not None:
            _set_executor_role_if_needed(conn, task_id, performer_role_id)

        comment = _normalize_comment(payload)
        conn.execute(
            text(
                f"""
                UPDATE task_reports
                SET approved_at = NULL,
                    approved_by = NULL,
                    {_apply_comment_sql()}
                WHERE report_id = :rid
                """
            ),
            {"rid": int(report_id), "comment": comment},
        )

        write_task_audit(
            conn,
            task_id=int(task_id),
            actor_user_id=int(actor_user_id),
            actor_role_id=int(actor_role_id),
            action="REJECT",
            fields_changed={"status_code": {"from": from_status, "to": "WAITING_REPORT"}},
            request_body=payload,
            meta={"report_id": int(report_id)},
            event_type="REJECTED",
            event_payload={**payload, "reject_kind": "review", "report_id": int(report_id)},
        )

        create_task_event_tx(
            conn,
            task_id=int(task_id),
            event_type="REJECTED",
            actor_user_id=int(actor_user_id),
            actor_role_id=int(actor_role_id),
            payload={
                **payload,
                "status_to": "WAITING_REPORT",
                "reject_kind": "review",
                "report_id": int(report_id),
            },
        )
        return

    _set_status(
        conn,
        task_id,
        from_status,
        to_status="REJECTED",
        allowed_from={"IN_PROGRESS", "WAITING_REPORT"},
    )

    comment = _normalize_comment(payload)

    conn.execute(
        text(
            f"""
            UPDATE task_reports
            SET {_apply_comment_sql()}
            WHERE report_id = (
                SELECT max(report_id) FROM task_reports WHERE task_id = :tid
            )
            """
        ),
        {"tid": int(task_id), "comment": comment},
    )

    write_task_audit(
        conn,
        task_id=int(task_id),
        actor_user_id=int(actor_user_id),
        actor_role_id=int(actor_role_id),
        action="REJECT_TASK",
        fields_changed={"status_code": {"from": from_status, "to": "REJECTED"}},
        request_body=payload,
        meta=None,
        event_type="REJECTED",
        event_payload={**payload, "status_to": "REJECTED", "reject_kind": "task"},
    )

    create_task_event_tx(
        conn,
        task_id=int(task_id),
        event_type="REJECTED",
        actor_user_id=int(actor_user_id),
        actor_role_id=int(actor_role_id),
        payload={**payload, "status_to": "REJECTED", "reject_kind": "task"},
    )


def _archive(
    conn: Connection,
    task_id: int,
    from_status: str,
    actor_user_id: int,
    actor_role_id: int,
) -> None:
    if from_status == "ARCHIVED":
        raise_error(
            ErrorCode.TASK_CONFLICT_ACTION_STATUS,
            extra={
                "task_id": int(task_id),
                "current_status": from_status,
                "allowed_from": ["IN_PROGRESS", "WAITING_REPORT", "WAITING_APPROVAL", "DONE"],
                "status_to": "ARCHIVED",
            },
        )

    _set_status(
        conn,
        task_id,
        from_status,
        to_status="ARCHIVED",
        allowed_from={"IN_PROGRESS", "WAITING_REPORT", "WAITING_APPROVAL", "DONE"},
    )

    write_task_audit(
        conn,
        task_id=int(task_id),
        actor_user_id=int(actor_user_id),
        actor_role_id=int(actor_role_id),
        action="ARCHIVE",
        fields_changed={"status_code": {"from": from_status, "to": "ARCHIVED"}},
        request_body=None,
        meta=None,
        event_type=None,
        event_payload=None,
    )

    create_task_event_tx(
        conn,
        task_id=int(task_id),
        event_type="ARCHIVED",
        actor_user_id=int(actor_user_id),
        actor_role_id=int(actor_role_id),
        payload={"status_to": "ARCHIVED"},
    )