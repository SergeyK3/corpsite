# app/services/tasks_fsm.py
from __future__ import annotations

from typing import Dict, Any, Set

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.errors import raise_error, ErrorCode
from app.events import create_task_event_tx
from app.services.tasks_service import get_status_id_by_code, write_task_audit


class TaskFSMError(Exception):
    pass


def transition(
    *,
    conn: Connection,
    task_id: int,
    action: str,
    actor_user_id: int,
    actor_role_id: int,
    payload: Dict[str, Any] | None = None,
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
        {"tid": task_id},
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
                "task_id": task_id,
                "current_status": from_status,
                "allowed_from": sorted(allowed_from),
            },
        )

    status_id = get_status_id_by_code(conn, to_status)

    conn.execute(
        text("UPDATE tasks SET status_id = :sid WHERE task_id = :tid"),
        {"sid": status_id, "tid": task_id},
    )


def _ensure_report_exists(conn: Connection, task_id: int) -> None:
    rep = conn.execute(
        text("SELECT task_id FROM task_reports WHERE task_id = :tid"),
        {"tid": int(task_id)},
    ).mappings().first()

    if not rep:
        raise_error(
            ErrorCode.TASK_CONFLICT_APPROVE_NO_REPORT,
            extra={"task_id": int(task_id)},
        )


def _apply_comment_sql() -> str:
    # если comment пустой — не перезаписываем существующий current_comment
    return """
        current_comment = CASE
            WHEN :comment IS NULL OR :comment = '' THEN current_comment
            ELSE :comment
        END
    """


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
    _set_status(
        conn,
        task_id,
        from_status,
        to_status="WAITING_APPROVAL",
        allowed_from={"WAITING_REPORT", "IN_PROGRESS"},
    )

    write_task_audit(
        conn,
        task_id=task_id,
        actor_user_id=actor_user_id,
        actor_role_id=actor_role_id,
        action="REPORT_SUBMIT",
        fields_changed={"status_code": {"from": from_status, "to": "WAITING_APPROVAL"}},
        request_body=payload,
        event_type="REPORT_SUBMITTED",
        event_payload=payload,
    )

    create_task_event_tx(
        conn,
        task_id=task_id,
        event_type="REPORT_SUBMITTED",
        actor_user_id=actor_user_id,
        actor_role_id=actor_role_id,
        payload={**payload, "status_to": "WAITING_APPROVAL"},
    )


def _approve(
    conn: Connection,
    task_id: int,
    from_status: str,
    actor_user_id: int,
    actor_role_id: int,
    payload: Dict[str, Any],
) -> None:
    # 1) статус должен позволять approve
    if from_status not in {"WAITING_APPROVAL"}:
        raise_error(
            ErrorCode.TASK_CONFLICT_ACTION_STATUS,
            extra={
                "task_id": int(task_id),
                "current_status": from_status,
                "allowed_from": ["WAITING_APPROVAL"],
            },
        )

    # 2) должен быть отчёт; и перед DONE обязаны проставить approved_at/by (DB-trigger)
    _ensure_report_exists(conn, task_id)

    comment = (payload.get("current_comment") or "").strip()

    conn.execute(
        text(
            f"""
            UPDATE task_reports
            SET approved_at = now(),
                approved_by = :by,
                {_apply_comment_sql()}
            WHERE task_id = :tid
            """
        ),
        {"by": int(actor_user_id), "tid": int(task_id), "comment": comment},
    )

    # 3) теперь можно ставить DONE
    _set_status(
        conn,
        task_id,
        from_status,
        to_status="DONE",
        allowed_from={"WAITING_APPROVAL"},
    )

    write_task_audit(
        conn,
        task_id=task_id,
        actor_user_id=actor_user_id,
        actor_role_id=actor_role_id,
        action="APPROVE",
        fields_changed={"status_code": {"from": from_status, "to": "DONE"}},
        request_body=payload,
        event_type="APPROVED",
        event_payload=payload,
    )

    create_task_event_tx(
        conn,
        task_id=task_id,
        event_type="APPROVED",
        actor_user_id=actor_user_id,
        actor_role_id=actor_role_id,
        payload={**payload, "status_to": "DONE"},
    )


def _reject(
    conn: Connection,
    task_id: int,
    from_status: str,
    actor_user_id: int,
    actor_role_id: int,
    payload: Dict[str, Any],
) -> None:
    _set_status(
        conn,
        task_id,
        from_status,
        to_status="WAITING_REPORT",
        allowed_from={"WAITING_APPROVAL"},
    )

    # при reject сбрасываем approve-метки; comment (если передали) сохраняем
    comment = (payload.get("current_comment") or "").strip()
    conn.execute(
        text(
            f"""
            UPDATE task_reports
            SET approved_at = NULL,
                approved_by = NULL,
                {_apply_comment_sql()}
            WHERE task_id = :tid
            """
        ),
        {"tid": int(task_id), "comment": comment},
    )

    write_task_audit(
        conn,
        task_id=task_id,
        actor_user_id=actor_user_id,
        actor_role_id=actor_role_id,
        action="REJECT",
        fields_changed={"status_code": {"from": from_status, "to": "WAITING_REPORT"}},
        request_body=payload,
        event_type="REJECTED",
        event_payload=payload,
    )

    create_task_event_tx(
        conn,
        task_id=task_id,
        event_type="REJECTED",
        actor_user_id=actor_user_id,
        actor_role_id=actor_role_id,
        payload={**payload, "status_to": "WAITING_REPORT"},
    )


def _archive(
    conn: Connection,
    task_id: int,
    from_status: str,
    actor_user_id: int,
    actor_role_id: int,
) -> None:
    _set_status(
        conn,
        task_id,
        from_status,
        to_status="ARCHIVED",
        allowed_from={from_status},
    )

    write_task_audit(
        conn,
        task_id=task_id,
        actor_user_id=actor_user_id,
        actor_role_id=actor_role_id,
        action="ARCHIVE",
        fields_changed={"status_code": {"from": from_status, "to": "ARCHIVED"}},
        request_body=None,
        event_type=None,
        event_payload=None,
    )
