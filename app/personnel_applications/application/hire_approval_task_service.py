"""Shared task inbox projection of an electronic HIRE approval round."""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.personnel_orders_editorial.generators import _format_rate_value


def current_hire_task_period(conn: Connection, *, today: date | None = None, create: bool = False) -> dict[str, Any] | None:
    """Use the current monthly reporting period; task creation may establish it."""
    today = today or date.today()
    start = today.replace(day=1)
    end = today.replace(day=monthrange(today.year, today.month)[1])
    if create:
        conn.execute(text("SELECT pg_advisory_xact_lock(620002, :month_key)"),
                     {"month_key": today.year * 100 + today.month})
    row = conn.execute(text("""
        SELECT period_id, label FROM public.reporting_periods
        WHERE kind='MONTH' AND date_start=:start AND date_end=:end AND is_closed=FALSE
        ORDER BY period_id LIMIT 1
    """), {"start": start, "end": end}).mappings().first()
    if row is not None:
        return dict(row)
    if not create:
        return None
    label = today.strftime("%m.%Y")
    return dict(conn.execute(text("""
        INSERT INTO public.reporting_periods(kind, date_start, date_end, label, is_closed)
        VALUES ('MONTH', :start, :end, :label, FALSE)
        RETURNING period_id, label
    """), {"start": start, "end": end, "label": label}).mappings().one())


def ensure_hire_approval_task(conn: Connection, *, application: dict[str, Any],
                              fingerprint: str, head_user_id: int, created_by_user_id: int) -> dict[str, Any]:
    """Create one task for one immutable condition revision, in the order transaction."""
    application_id = int(application["application_id"])
    existing = conn.execute(text("""
        SELECT task_id, head_user_id, decision, explanation
        FROM public.electronic_hire_approval_tasks
        WHERE application_id=:application_id AND conditions_hash=:fingerprint
    """), {"application_id": application_id, "fingerprint": fingerprint}).mappings().first()
    if existing is not None:
        return dict(existing)
    head = conn.execute(text("""
        SELECT role_id FROM public.users WHERE user_id=:id AND is_active=TRUE
    """), {"id": head_user_id}).mappings().first()
    if head is None:
        raise ValueError("The assigned department head is inactive.")
    period = current_hire_task_period(conn, create=True)
    status_id = conn.execute(text("SELECT status_id FROM public.task_statuses WHERE code='IN_PROGRESS'")).scalar_one()
    rate = _format_rate_value(application["intended_employment_rate"])
    start = application["planned_start_date"].strftime("%d.%m.%Y")
    description = (f"Кандидат: {application['full_name']}\n"
                   f"Отделение: {application['org_unit_ru']}\n"
                   f"Должность: {application['position_ru']}\n"
                   f"Ставка: {rate}\n"
                   f"Дата начала работы: {start}\n"
                   f"Заявление №{application_id}, проект приказа №{application['personnel_order_id']}.")
    task_id = int(conn.execute(text("""
        INSERT INTO public.tasks
            (period_id, title, description, initiator_user_id, created_by_user_id,
             approver_user_id, executor_role_id, assignment_scope, status_id,
             task_kind, requires_report, requires_approval, source_kind, source_note)
        VALUES (:period_id, :title, :description, :creator, :creator,
                :head, :role_id, 'user', :status_id,
                'adhoc', FALSE, FALSE, 'electronic_hire', :source_note)
        RETURNING task_id
    """), {
        "period_id": int(period["period_id"]),
        "title": f"Согласовать приём: {application['full_name']}",
        "description": description,
        "creator": created_by_user_id,
        "head": head_user_id,
        "role_id": int(head["role_id"]),
        "status_id": int(status_id),
        "source_note": f"Электронное заявление №{application_id}",
    }).scalar_one())
    row = conn.execute(text("""
        INSERT INTO public.electronic_hire_approval_tasks
            (task_id, application_id, conditions_hash, head_user_id)
        VALUES (:task_id, :application_id, :fingerprint, :head)
        RETURNING task_id, head_user_id, decision, explanation
    """), {"task_id": task_id, "application_id": application_id,
           "fingerprint": fingerprint, "head": head_user_id}).mappings().one()
    return dict(row)


def archive_superseded_hire_tasks(conn: Connection, *, application_id: int, current_fingerprint: str) -> None:
    """Retire pending rounds; completed decisions stay visible in task history."""
    conn.execute(text("""
        UPDATE public.tasks t SET status_id=:archived, updated_at=now()
        FROM public.electronic_hire_approval_tasks h, public.task_statuses s
        WHERE h.task_id=t.task_id AND h.application_id=:application_id
          AND h.conditions_hash<>:fingerprint AND s.status_id=t.status_id
          AND s.code IN ('IN_PROGRESS', 'WAITING_APPROVAL')
    """), {
        "application_id": application_id,
        "fingerprint": current_fingerprint,
        "archived": conn.execute(text("SELECT status_id FROM public.task_statuses WHERE code='ARCHIVED'")).scalar_one(),
    })


def finish_hire_approval_task(conn: Connection, *, task_id: int, decision: str,
                              explanation: str | None, decided_at: datetime) -> None:
    status_code = "DONE" if decision == "approved" else "REJECTED"
    status_id = conn.execute(text("SELECT status_id FROM public.task_statuses WHERE code=:code"),
                             {"code": status_code}).scalar_one()
    conn.execute(text("""
        UPDATE public.tasks SET status_id=:status_id, updated_at=now() WHERE task_id=:task_id
    """), {"status_id": status_id, "task_id": task_id})
    conn.execute(text("""
        UPDATE public.electronic_hire_approval_tasks
        SET decision=:decision, explanation=:explanation, decided_at=:decided_at
        WHERE task_id=:task_id
    """), {"decision": decision, "explanation": explanation,
           "decided_at": decided_at, "task_id": task_id})
