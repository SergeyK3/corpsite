# FILE: app/services/tasks_fsm.py
from __future__ import annotations

from typing import Any, Dict, Optional, Set

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.errors import ErrorCode, raise_error
from app.events import create_task_event_tx
from app.services.tasks_service import get_status_id_by_code, write_task_audit

LOCAL_TZ = "Asia/Qyzylorda"


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
    # если comment пустой — не перезаписываем существующий current_comment
    return """
        current_comment = CASE
            WHEN :comment IS NULL OR :comment = '' THEN current_comment
            ELSE :comment
        END
    """


def _normalize_comment(payload: Dict[str, Any]) -> str:
    # Поддержка обоих ключей: current_comment (старый контракт) и reason (новый/долгосрок).
    v = payload.get("current_comment")
    if v is None or str(v).strip() == "":
        v = payload.get("reason")
    return (v or "").strip()


def _get_latest_report_id(conn: Connection, task_id: int) -> int:
    rid = conn.execute(
        text("SELECT max(report_id) AS rid FROM task_reports WHERE task_id = :tid"),
        {"tid": int(task_id)},
    ).mappings().first()

    v = rid["rid"] if rid else None
    if v is None:
        raise_error(
            ErrorCode.TASK_CONFLICT_APPROVE_NO_REPORT,
            extra={"task_id": int(task_id)},
        )
    return int(v)


def _ensure_report_exists(conn: Connection, task_id: int) -> None:
    _get_latest_report_id(conn, task_id)


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

    # Инвариант: WAITING_APPROVAL допустим ТОЛЬКО если уже есть task_reports
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
        # payload validation (не конфликт статуса)
        raise HTTPException(status_code=422, detail="report_link is required")
    return s


def _maybe_create_or_update_next_task_after_approved(
    conn: Connection,
    *,
    source_task_id: int,
    approved_at_ts: str,
) -> None:
    """
    Каскад: после APPROVED по задаче, созданной из regular_tasks (regular_task_id != NULL),
    создаём (или обновляем, если уже существует) задачу для target_role_id из public.regular_tasks.

    Идемпотентность:
      - если задача для (period_id, regular_task_id, executor_role_id=target_role_id) уже есть —
        НЕ создаём дубль, а:
          - если due_date IS NULL -> заполняем;
          - иначе оставляем как есть.

    due_date = local_date(approved_at) + escalation_offset_days (TZ Asia/Qyzylorda).
    """
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

    target_role_id = int(rt["target_role_id"])
    offset_days = int(rt.get("escalation_offset_days") or 0)

    existing = conn.execute(
        text(
            """
            SELECT t.task_id, t.due_date
            FROM tasks t
            WHERE t.period_id = :period_id
              AND t.regular_task_id = :regular_task_id
              AND t.executor_role_id = :executor_role_id
            ORDER BY t.task_id DESC
            LIMIT 1
            """
        ),
        {
            "period_id": int(src["period_id"]),
            "regular_task_id": int(regular_task_id),
            "executor_role_id": int(target_role_id),
        },
    ).mappings().first()

    if existing:
        if existing.get("due_date") is None:
            conn.execute(
                text(
                    """
                    UPDATE tasks
                    SET due_date = (
                        ((:approved_at_ts)::timestamptz AT TIME ZONE :tz)::date
                        + :offset_days
                    )
                    WHERE task_id = :tid
                      AND due_date IS NULL
                    """
                ),
                {
                    "tid": int(existing["task_id"]),
                    "approved_at_ts": approved_at_ts,
                    "tz": LOCAL_TZ,
                    "offset_days": int(offset_days),
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
            "period_id": int(src["period_id"]),
            "regular_task_id": int(regular_task_id),
            "title": str(rt["title"]),
            "description": f"Основание: APPROVED по задаче #{int(source_task_id)} ({str(src.get('src_title') or '').strip()})",
            "initiator_user_id": int(src["initiator_user_id"]),
            "executor_role_id": int(target_role_id),
            "assignment_scope": src["assignment_scope"],
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
    allowed_from = {"WAITING_REPORT", "IN_PROGRESS"}
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

    # Идемпотентный upsert отчёта (совместимо с текущим router, даже если он тоже пишет report)
    ins = conn.execute(
        text(
            """
            INSERT INTO task_reports (task_id, report_link, submitted_by, current_comment, submitted_at)
            VALUES (:tid, :link, :by, :comment, now())
            ON CONFLICT (task_id) DO UPDATE SET
                report_link = EXCLUDED.report_link,
                submitted_by = EXCLUDED.submitted_by,
                current_comment = EXCLUDED.current_comment,
                submitted_at = now(),
                approved_at = NULL,
                approved_by = NULL
            RETURNING report_id
            """
        ),
        {"tid": int(task_id), "link": report_link, "by": int(actor_user_id), "comment": comment},
    ).mappings().first()

    report_id = int(ins["report_id"]) if ins and ins.get("report_id") is not None else None

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

    report_id = _get_latest_report_id(conn, task_id)
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
    """
    reject имеет ДВА допустимых смысла:
    1) Review reject: WAITING_APPROVAL -> WAITING_REPORT
    2) Task reject:   IN_PROGRESS/WAITING_REPORT -> REJECTED
    """

    if from_status == "WAITING_APPROVAL":
        report_id = _get_latest_report_id(conn, task_id)

        _set_status(
            conn,
            task_id,
            from_status,
            to_status="WAITING_REPORT",
            allowed_from={"WAITING_APPROVAL"},
        )

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
