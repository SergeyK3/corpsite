# FILE: app/services/tasks_fsm.py
from __future__ import annotations

from typing import Any, Dict, Optional, Set

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.errors import ErrorCode, raise_error
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
    # просто проверка наличия (для инварианта)
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
    # (это закрывает дыру "статус выставили, отчёта нет").
    if to_status == "WAITING_APPROVAL":
        _ensure_report_exists(conn, task_id)

    status_id = get_status_id_by_code(conn, to_status)

    conn.execute(
        text("UPDATE tasks SET status_id = :sid WHERE task_id = :tid"),
        {"sid": int(status_id), "tid": int(task_id)},
    )


def _extract_report_link(payload: Dict[str, Any], *, task_id: int, from_status: str) -> str:
    # контракт: report_link обязателен для action=report
    v = payload.get("report_link")
    s = (v or "").strip()
    if not s:
        # ВАЖНО: не добавляем "самодельные" поля code/message,
        # чтобы не провоцировать 500 в обработчике ошибок.
        raise_error(
            ErrorCode.TASK_CONFLICT_ACTION_STATUS,
            extra={
                "task_id": int(task_id),
                "current_status": from_status,
                "allowed_from": ["WAITING_REPORT", "IN_PROGRESS"],
                "status_to": "WAITING_APPROVAL",
                "hint": "report_link is required",
            },
        )
    return s


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
    # 1) сначала валидируем from_status
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

    # 2) создаём/обновляем запись отчёта (ФАКТ отчёта)
    # В БД стоит unique constraint task_reports_task_id_key, значит на 1 task_id может быть только 1 report.
    # Поэтому делаем UPSERT по task_id, чтобы /report был идемпотентным и не падал на ретраях.
    report_link = _extract_report_link(payload, task_id=task_id, from_status=from_status)
    comment = _normalize_comment(payload)

    ins = conn.execute(
        text(
            """
            INSERT INTO task_reports (task_id, report_link, submitted_by, current_comment)
            VALUES (:tid, :link, :by, :comment)
            ON CONFLICT (task_id) DO UPDATE SET
                report_link = EXCLUDED.report_link,
                submitted_by = EXCLUDED.submitted_by,
                current_comment = EXCLUDED.current_comment
            RETURNING report_id
            """
        ),
        {"tid": int(task_id), "link": report_link, "by": int(actor_user_id), "comment": comment},
    ).mappings().first()

    report_id = int(ins["report_id"]) if ins and ins.get("report_id") is not None else None

    # 3) теперь переводим задачу в WAITING_APPROVAL (инвариант уже выполняется)
    _set_status(
        conn,
        task_id,
        from_status,
        to_status="WAITING_APPROVAL",
        allowed_from=allowed_from,
    )

    # 4) audit + event
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

    conn.execute(
        text(
            f"""
            UPDATE task_reports
            SET approved_at = now(),
                approved_by = :by,
                {_apply_comment_sql()}
            WHERE report_id = :rid
            """
        ),
        {"by": int(actor_user_id), "rid": int(report_id), "comment": comment},
    )

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


def _reject(
    conn: Connection,
    task_id: int,
    from_status: str,
    actor_user_id: int,
    actor_role_id: int,
    payload: Dict[str, Any],
) -> None:
    """
    reject имеет ДВА допустимых смысла (на текущий момент):
    1) Review reject: WAITING_APPROVAL -> WAITING_REPORT (отклонить отчёт, вернуть в работу).
    2) Task reject:   IN_PROGRESS/WAITING_REPORT -> REJECTED (отказ/отклонение задачи как сущности).

    Это сделано намеренно, чтобы поддержать "новый endpoint reject" без введения нового action-кода.
    Клиентам рекомендуется передавать reason (или current_comment) для обоих случаев.
    """

    # 1) Review reject: отклонение отчёта
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

    # 2) Task reject: отказ/отклонение задачи как сущности
    _set_status(
        conn,
        task_id,
        from_status,
        to_status="REJECTED",
        allowed_from={"IN_PROGRESS", "WAITING_REPORT"},
    )

    comment = _normalize_comment(payload)

    # Если есть task_reports — сохраним комментарий в current_comment (не создаём отчёт, если его нет).
    # Это даёт единое место хранения причины в UI.
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

    # ВАЖНО: ранее считалось, что события ARCHIVED в enum task_event_type НЕТ.
    # Но по факту в БД task_events уже есть event_type='ARCHIVED', и доставки в telegram существуют.
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

    # Создаём task_event, чтобы работали recipients/deliveries (в т.ч. telegram) по правилам routing.
    create_task_event_tx(
        conn,
        task_id=int(task_id),
        event_type="ARCHIVED",
        actor_user_id=int(actor_user_id),
        actor_role_id=int(actor_role_id),
        payload={"status_to": "ARCHIVED"},
    )
