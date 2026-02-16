# FILE: app/services/regular_tasks_service.py
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Connection


def _env_int(name: str, default: int) -> int:
    v = (os.getenv(name) or "").strip()
    if not v:
        return default
    try:
        return int(v)
    except Exception:
        return default


SYSTEM_USER_ID: int = _env_int("REGULAR_TASKS_SYSTEM_USER_ID", 1)
TZ_OFFSET_HOURS: int = _env_int("REGULAR_TASKS_TZ_OFFSET_HOURS", 5)

# оставляем на всякий случай, но для вашей схемы мы используем reporting_periods
FALLBACK_PERIOD_ID: int = _env_int("REGULAR_TASKS_FALLBACK_PERIOD_ID", 1)

# Task statuses (public.task_statuses)
ARCHIVED_STATUS_ID: int = _env_int("TASK_STATUS_ID_ARCHIVED", 5)
IN_PROGRESS_STATUS_CODE: str = os.getenv("TASK_STATUS_CODE_IN_PROGRESS") or "IN_PROGRESS"


@dataclass(frozen=True)
class RunStats:
    templates_total: int
    templates_due: int
    created: int
    deduped: int
    errors: int


def _now_local() -> datetime:
    # фиксируем UTC+5 как в проекте (простая модель)
    return datetime.now(timezone.utc) + timedelta(hours=TZ_OFFSET_HOURS)


def _safe_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        if isinstance(v, bool):
            return None
        return int(v)
    except Exception:
        return None


def _parse_time_hhmm(s: str) -> Optional[time]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        parts = s.split(":")
        hh = int(parts[0])
        mm = int(parts[1]) if len(parts) > 1 else 0
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return time(hour=hh, minute=mm)
    except Exception:
        return None
    return None


def _weekday_iso(dt: date) -> int:
    # ISO weekday: Mon=1..Sun=7
    return dt.isoweekday()


def _first_day_of_month(d: date) -> date:
    return date(d.year, d.month, 1)


def _last_day_of_month(d: date) -> date:
    first_next = date(d.year + (1 if d.month == 12 else 0), 1 if d.month == 12 else d.month + 1, 1)
    return first_next - timedelta(days=1)


def _first_day_of_year(y: int) -> date:
    return date(y, 1, 1)


def _last_day_of_year(y: int) -> date:
    return date(y, 12, 31)


# ---------------------------
# Custom weekly window: Thu..Mon
# ---------------------------
def _week_start_thu(d: date) -> date:
    # ISO weekday: Mon=1..Sun=7; Thu=4
    # start = ближайший четверг <= d (в рамках 0..6 дней назад)
    delta = (_weekday_iso(d) - 4) % 7
    return d - timedelta(days=delta)


def _week_end_mon_from_thu(thu: date) -> date:
    # Thu + 4 days = Mon
    return thu + timedelta(days=4)


def _prev_week_period_bounds_thu_mon(for_date: date) -> Tuple[date, date]:
    # "предыдущая" неделя в вашей модели: Thu..Mon
    cur_thu = _week_start_thu(for_date)
    prev_thu = cur_thu - timedelta(days=7)
    prev_mon = _week_end_mon_from_thu(prev_thu)
    return prev_thu, prev_mon


def _anchor_monday_for_thu_week(thu: date) -> date:
    # Thu..Mon window anchor = Monday inside this window
    return thu + timedelta(days=4)


def _suffix_for_week_thu_mon(period_start_thu: date) -> str:
    anchor = _anchor_monday_for_thu_week(period_start_thu)
    iso_year, iso_week, _ = anchor.isocalendar()
    return f"{iso_year}-W{int(iso_week):02d}"


# ---------------------------
# Schedule target date
# ---------------------------
def _target_date_for_template(d: date, schedule_type: str, schedule_params: Dict[str, Any]) -> Optional[date]:
    st = (schedule_type or "").strip().lower()

    if st == "weekly":
        byweekday = schedule_params.get("byweekday")
        if not isinstance(byweekday, list) or not byweekday:
            return None

        # v2 policy (project): week window = Thu..Mon, but we allow any ISO weekday 1..7;
        # target date = earliest date >= week_start_thu within 7 days that matches any byweekday.
        week_start = _week_start_thu(d)
        wanted: set[int] = set()
        for x in byweekday:
            try:
                wd = int(x)
            except Exception:
                continue
            if 1 <= wd <= 7:
                wanted.add(wd)
        if not wanted:
            return None

        for i in range(0, 7):
            cand = week_start + timedelta(days=i)
            if _weekday_iso(cand) in wanted:
                return cand
        return None

    if st == "monthly":
        bymonthday = schedule_params.get("bymonthday")
        if not isinstance(bymonthday, list) or not bymonthday:
            return None
        # v1 policy: берём первый валидный день месяца из списка
        for x in bymonthday:
            try:
                md = int(x)
            except Exception:
                continue
            if md == -1:
                return _last_day_of_month(d)
            if 1 <= md <= 31:
                last = _last_day_of_month(d)
                cand = date(d.year, d.month, min(md, last.day))
                return cand
        return None

    if st == "yearly":
        bymonth = schedule_params.get("bymonth")
        bymonthday = schedule_params.get("bymonthday")
        if not isinstance(bymonth, list) or not bymonth:
            return None
        if not isinstance(bymonthday, list) or not bymonthday:
            return None

        # v1 policy: берём первый валидный месяц и первый валидный день месяца
        mm: Optional[int] = None
        for x in bymonth:
            try:
                m = int(x)
            except Exception:
                continue
            if 1 <= m <= 12:
                mm = m
                break
        if mm is None:
            return None

        md: Optional[int] = None
        for x in bymonthday:
            try:
                dday = int(x)
            except Exception:
                continue
            if dday == -1:
                md = -1
                break
            if 1 <= dday <= 31:
                md = dday
                break
        if md is None:
            return None

        if md == -1:
            return _last_day_of_month(date(d.year, mm, 1))

        last = _last_day_of_month(date(d.year, mm, 1))
        return date(d.year, mm, min(int(md), last.day))

    return None


def _validate_template_schedule(schedule_type: str, schedule_params: Dict[str, Any]) -> Optional[str]:
    """
    Возвращает текст ошибки конфигурации расписания или None (если конфиг допустим).
    """
    st = (schedule_type or "").strip().lower()
    if not st:
        return "schedule_type is required"
    if st not in ("weekly", "monthly", "yearly"):
        return f"unsupported schedule_type: {st}"

    if st == "weekly":
        byweekday = schedule_params.get("byweekday")
        if not isinstance(byweekday, list) or not byweekday:
            return "schedule_params.byweekday must be a non-empty list for schedule_type=weekly"

    if st == "monthly":
        bymonthday = schedule_params.get("bymonthday")
        if not isinstance(bymonthday, list) or not bymonthday:
            return "schedule_params.bymonthday must be a non-empty list for schedule_type=monthly"

    if st == "yearly":
        bymonth = schedule_params.get("bymonth")
        bymonthday = schedule_params.get("bymonthday")
        if not isinstance(bymonth, list) or not bymonth:
            return "schedule_params.bymonth must be a non-empty list for schedule_type=yearly"
        if not isinstance(bymonthday, list) or not bymonthday:
            return "schedule_params.bymonthday must be a non-empty list for schedule_type=yearly"

    tt = schedule_params.get("time")
    if tt is not None:
        if _parse_time_hhmm(str(tt)) is None:
            return "schedule_params.time must be HH:MM (e.g. '10:00') if provided"

    return None


def _is_due_today_or_with_offset(
    *,
    now_local: datetime,
    schedule_type: str,
    schedule_params: Dict[str, Any],
    create_offset_days: int,
) -> bool:
    today = now_local.date()
    target_date = _target_date_for_template(today, schedule_type, schedule_params)
    if target_date is None:
        return False

    create_day = target_date - timedelta(days=max(int(create_offset_days), 0))
    if today != create_day:
        return False

    tt = _parse_time_hhmm(str(schedule_params.get("time") or ""))
    if tt is not None:
        if now_local.time() < tt:
            return False

    return True


def _prev_month_period_bounds(for_date: date) -> Tuple[date, date]:
    # предыдущий месяц относительно for_date
    first_cur = _first_day_of_month(for_date)
    last_prev = first_cur - timedelta(days=1)
    return _first_day_of_month(last_prev), _last_day_of_month(last_prev)


def _prev_year_period_bounds(for_date: date) -> Tuple[date, date]:
    # предыдущий календарный год относительно for_date
    y = for_date.year - 1
    return _first_day_of_year(y), _last_day_of_year(y)


def _reporting_period_resolve(
    conn: Connection,
    *,
    schedule_type: str,
    for_date: date,
) -> Tuple[int, date, date]:
    """
    Основная модель для вашей БД:
      tasks.period_id -> reporting_periods.period_id

    Правило: создаём отчёт ЗА ПРЕДЫДУЩИЙ период.
      - monthly: предыдущий месяц
      - weekly:  предыдущая неделя (Thu..Mon)
      - yearly:  предыдущий год (Jan..Dec)

    Если периода нет — создаём (по uq_period).
    """
    st = (schedule_type or "").strip().lower()
    if st == "weekly":
        d0, d1 = _prev_week_period_bounds_thu_mon(for_date)
        kind = "WEEK"
        label = f"{d0.isoformat()}..{d1.isoformat()}"
    elif st == "yearly":
        d0, d1 = _prev_year_period_bounds(for_date)
        kind = "YEAR"
        label = f"{d0.year}"
    else:
        d0, d1 = _prev_month_period_bounds(for_date)
        kind = "MONTH"
        label = f"{d0.strftime('%B %Y')}"  # технический label

    row = conn.execute(
        text(
            """
            SELECT period_id
            FROM public.reporting_periods
            WHERE kind = (:kind)::period_kind_t
              AND date_start = :ds
              AND date_end = :de
            """
        ),
        {"kind": kind, "ds": d0, "de": d1},
    ).mappings().first()
    if row and row.get("period_id"):
        return int(row["period_id"]), d0, d1

    created = conn.execute(
        text(
            """
            INSERT INTO public.reporting_periods (kind, date_start, date_end, label, is_closed)
            VALUES ((:kind)::period_kind_t, :ds, :de, :label, false)
            ON CONFLICT (kind, date_start, date_end)
            DO UPDATE SET label = EXCLUDED.label
            RETURNING period_id
            """
        ),
        {"kind": kind, "ds": d0, "de": d1, "label": label},
    ).scalar_one()

    return int(created), d0, d1


def _append_period_suffix(base_title: str, suffix: str) -> str:
    bt = (base_title or "").strip()
    if not bt:
        bt = "Без названия"

    # If already has exact suffix at end -> keep
    if re.search(rf"\(\s*{re.escape(suffix)}\s*\)\s*$", bt):
        return bt

    return f"{bt} ({suffix})"


def _period_suffix_for_template(schedule_type: str, period_start: date) -> str:
    st = (schedule_type or "").strip().lower()
    if st == "monthly":
        return f"{int(period_start.month):02d}"
    if st == "yearly":
        return f"{int(period_start.year)}"
    if st == "weekly":
        # period_start is Thu for weekly periods in our model
        return _suffix_for_week_thu_mon(period_start_thu=period_start)
    # fallback
    return f"{int(period_start.year)}"


def _due_date_from_reporting_period_end(*, period_end: date, due_offset_days: int) -> date:
    # Policy (фиксируем): due_date = reporting_period.date_end + due_offset_days
    return period_end + timedelta(days=int(due_offset_days or 0))


def _get_status_id(conn: Connection, code: str) -> int:
    # легковесный lookup (в run вызовов немного)
    sid = conn.execute(
        text("SELECT status_id FROM public.task_statuses WHERE code = :code"),
        {"code": str(code)},
    ).scalar_one()
    return int(sid)


def _select_active_task_for_template(
    conn: Connection,
    *,
    regular_task_id: int,
    period_id: int,
    assignment_scope: str,
) -> Optional[Dict[str, Any]]:
    """
    Возвращает одну активную (не ARCHIVED) задачу по ключу:
      (regular_task_id, period_id, assignment_scope)
    Берём FOR UPDATE, чтобы сериализовать миграции исполнителя внутри одного run.
    """
    row = conn.execute(
        text(
            """
            SELECT task_id, executor_role_id, status_id, due_date
            FROM public.tasks
            WHERE regular_task_id = :regular_task_id
              AND period_id = :period_id
              AND assignment_scope = :assignment_scope
              AND status_id <> :archived_status_id
            ORDER BY created_at DESC, task_id DESC
            LIMIT 1
            FOR UPDATE
            """
        ),
        {
            "regular_task_id": int(regular_task_id),
            "period_id": int(period_id),
            "assignment_scope": str(assignment_scope),
            "archived_status_id": int(ARCHIVED_STATUS_ID),
        },
    ).mappings().first()
    return dict(row) if row else None


def _archive_task_by_id(conn: Connection, task_id: int) -> int:
    r = conn.execute(
        text("UPDATE public.tasks SET status_id = :arch WHERE task_id = :tid AND status_id <> :arch"),
        {"arch": int(ARCHIVED_STATUS_ID), "tid": int(task_id)},
    )
    return int(getattr(r, "rowcount", 0) or 0)


def _update_due_date_if_needed(conn: Connection, task_id: int, due_date_val: date) -> int:
    r = conn.execute(
        text(
            """
            UPDATE public.tasks
            SET due_date = :due_date
            WHERE task_id = :task_id
              AND (due_date IS DISTINCT FROM :due_date)
            """
        ),
        {"task_id": int(task_id), "due_date": due_date_val},
    )
    return int(getattr(r, "rowcount", 0) or 0)


def _log_run_item_safe(
    conn: Connection,
    *,
    run_id: int,
    regular_task_id: int,
    period_id: Optional[int],
    executor_role_id: Optional[int],
    is_due: bool,
    created_tasks: int,
    status: str,
    error: Optional[str],
    meta: Dict[str, Any],
) -> None:
    try:
        with conn.begin_nested():  # SAVEPOINT
            conn.execute(
                text(
                    """
                    INSERT INTO public.regular_task_run_items (
                        run_id,
                        regular_task_id,
                        period_id,
                        executor_role_id,
                        is_due,
                        created_tasks,
                        status,
                        error,
                        meta
                    )
                    VALUES (
                        :run_id,
                        :regular_task_id,
                        :period_id,
                        :executor_role_id,
                        :is_due,
                        :created_tasks,
                        :status,
                        :error,
                        CAST(:meta AS jsonb)
                    )
                    """
                ),
                {
                    "run_id": int(run_id),
                    "regular_task_id": int(regular_task_id),
                    "period_id": int(period_id) if period_id is not None else None,
                    "executor_role_id": int(executor_role_id) if executor_role_id is not None else None,
                    "is_due": bool(is_due),
                    "created_tasks": int(created_tasks),
                    "status": str(status),
                    "error": str(error) if error else None,
                    "meta": json.dumps(meta or {}, ensure_ascii=False),
                },
            )
    except Exception:
        return


def run_regular_tasks_generation_tx(
    conn: Connection,
    *,
    run_at_local: Optional[datetime] = None,
    dry_run: bool = False,
) -> Tuple[int, Dict[str, Any]]:
    now_local = run_at_local or _now_local()

    run_id = conn.execute(
        text(
            """
            INSERT INTO public.regular_task_runs (started_at, status, stats)
            VALUES (now(), 'ok', '{}'::jsonb)
            RETURNING run_id
            """
        )
    ).scalar_one()

    errors: List[Dict[str, Any]] = []

    templates = conn.execute(
        text(
            """
            SELECT
                regular_task_id,
                is_active,
                title,
                description,
                executor_role_id,
                assignment_scope,
                schedule_type,
                schedule_params,
                create_offset_days,
                due_offset_days
            FROM public.regular_tasks
            WHERE COALESCE(is_active, true) = true
            ORDER BY regular_task_id
            """
        )
    ).mappings().all()

    total = len(templates)
    due = 0
    created = 0
    deduped = 0

    for t in templates:
        rid = _safe_int(t.get("regular_task_id"))
        if rid is None:
            errors.append({"regular_task_id": None, "error": "regular_task_id is not an int"})
            continue

        base_meta: Dict[str, Any] = {
            "dry_run": bool(dry_run),
            "now_local": now_local.isoformat(),
        }

        try:
            schedule_type = str(t.get("schedule_type") or "").strip().lower()
            schedule_params = t.get("schedule_params") or {}
            if not isinstance(schedule_params, dict):
                schedule_params = {}

            create_offset_days = _safe_int(t.get("create_offset_days")) or 0
            due_offset_days = _safe_int(t.get("due_offset_days")) or 0

            base_meta.update(
                {
                    "schedule_type": schedule_type,
                    "schedule_params": schedule_params,
                    "create_offset_days": int(create_offset_days),
                    "due_offset_days": int(due_offset_days),
                }
            )

            sched_err = _validate_template_schedule(schedule_type, schedule_params)
            if sched_err:
                errors.append({"regular_task_id": rid, "error": sched_err})
                _log_run_item_safe(
                    conn,
                    run_id=int(run_id),
                    regular_task_id=int(rid),
                    period_id=None,
                    executor_role_id=_safe_int(t.get("executor_role_id")),
                    is_due=False,
                    created_tasks=0,
                    status="error",
                    error=sched_err,
                    meta=base_meta,
                )
                continue

            is_due = _is_due_today_or_with_offset(
                now_local=now_local,
                schedule_type=schedule_type,
                schedule_params=schedule_params,
                create_offset_days=create_offset_days,
            )

            if not is_due:
                continue

            due += 1

            executor_role_id = _safe_int(t.get("executor_role_id"))
            if executor_role_id is None:
                msg = "executor_role_id is required (cannot be NULL) when template is due"
                errors.append({"regular_task_id": rid, "error": msg})
                _log_run_item_safe(
                    conn,
                    run_id=int(run_id),
                    regular_task_id=int(rid),
                    period_id=None,
                    executor_role_id=None,
                    is_due=True,
                    created_tasks=0,
                    status="error",
                    error=msg,
                    meta=base_meta,
                )
                continue

            assignment_scope = str(t.get("assignment_scope") or "functional")

            # period_id берём из reporting_periods (предыдущий период)
            try:
                period_id, period_start, period_end = _reporting_period_resolve(
                    conn, schedule_type=schedule_type, for_date=now_local.date()
                )
            except Exception:
                # если что-то сломалось — не блокируем run целиком, fallback как раньше
                period_id = int(FALLBACK_PERIOD_ID)
                period_start, period_end = _prev_month_period_bounds(now_local.date())

            # Policy (фиксируем): due_date = reporting_period.date_end + due_offset_days
            due_date_val = _due_date_from_reporting_period_end(period_end=period_end, due_offset_days=due_offset_days)

            # title suffix policy: based on reporting period identity
            suffix = _period_suffix_for_template(schedule_type, period_start)
            base_title = str(t.get("title") or "").strip() or f"Regular task #{rid}"
            title_with_suffix = _append_period_suffix(base_title, suffix)

            base_meta.update(
                {
                    "period_id": int(period_id),
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "due_date": due_date_val.isoformat() if due_date_val else None,
                    "title_suffix": suffix,
                    "title_final": title_with_suffix,
                    "assignment_scope": assignment_scope,
                }
            )

            if dry_run:
                _log_run_item_safe(
                    conn,
                    run_id=int(run_id),
                    regular_task_id=int(rid),
                    period_id=int(period_id),
                    executor_role_id=int(executor_role_id),
                    is_due=True,
                    created_tasks=0,
                    status="skip",
                    error=None,
                    meta={**base_meta, "reason": "dry_run"},
                )
                continue

            # New rule:
            #   Key for one ACTIVE task = (regular_task_id, period_id, assignment_scope)
            #   If active exists with different executor -> archive it; then insert new.
            #   If active exists with same executor -> dedupe (and align due_date to policy).
            archived_conflicts = 0
            active_row = _select_active_task_for_template(
                conn,
                regular_task_id=int(rid),
                period_id=int(period_id),
                assignment_scope=assignment_scope,
            )

            if active_row and active_row.get("task_id"):
                active_task_id = int(active_row["task_id"])
                active_exec = _safe_int(active_row.get("executor_role_id"))
                if active_exec == int(executor_role_id):
                    # same executor: treat as dedup; align due_date to policy
                    updated = _update_due_date_if_needed(conn, task_id=active_task_id, due_date_val=due_date_val)
                    deduped += 1
                    _log_run_item_safe(
                        conn,
                        run_id=int(run_id),
                        regular_task_id=int(rid),
                        period_id=int(period_id),
                        executor_role_id=int(executor_role_id),
                        is_due=True,
                        created_tasks=0,
                        status="ok",
                        error=None,
                        meta={
                            **base_meta,
                            "task_id": active_task_id,
                            "deduped": True,
                            "archived_conflicts": 0,
                            "due_date_updated": bool(updated > 0),
                        },
                    )
                    continue

                # different executor: archive existing active, then continue to insert
                archived_conflicts = _archive_task_by_id(conn, task_id=active_task_id)

            # Insert new task. We keep the older per-executor unique constraint,
            # but the new partial unique index (ux_tasks_regular_period_scope_active)
            # will prevent second ACTIVE task for same template/period/scope.
            in_progress_status_id = _get_status_id(conn, IN_PROGRESS_STATUS_CODE)

            row = conn.execute(
                text(
                    """
                    INSERT INTO public.tasks (
                        period_id, regular_task_id,
                        title, description,
                        initiator_user_id,
                        executor_role_id,
                        assignment_scope,
                        status_id,
                        due_date
                    )
                    VALUES (
                        :period_id, :regular_task_id,
                        :title, :description,
                        :initiator_user_id,
                        :executor_role_id,
                        :assignment_scope,
                        :status_id,
                        :due_date
                    )
                    ON CONFLICT ON CONSTRAINT uq_task_period_regular_role
                    DO UPDATE SET
                        -- title не трогаем (может быть отредактирован человеком),
                        -- due_date приводим к нашей политике
                        due_date = EXCLUDED.due_date
                    RETURNING task_id, (xmax = 0) AS inserted, due_date
                    """
                ),
                {
                    "period_id": int(period_id),
                    "regular_task_id": int(rid),
                    "title": title_with_suffix,
                    "description": t.get("description"),
                    "initiator_user_id": int(SYSTEM_USER_ID),
                    "executor_role_id": int(executor_role_id),
                    "assignment_scope": assignment_scope,
                    "status_id": int(in_progress_status_id),
                    "due_date": due_date_val,
                },
            ).mappings().first()

            if row and row.get("task_id"):
                inserted = bool(row.get("inserted"))
                if inserted:
                    created += 1
                else:
                    deduped += 1

                _log_run_item_safe(
                    conn,
                    run_id=int(run_id),
                    regular_task_id=int(rid),
                    period_id=int(period_id),
                    executor_role_id=int(executor_role_id),
                    is_due=True,
                    created_tasks=1 if inserted else 0,
                    status="ok",
                    error=None,
                    meta={
                        **base_meta,
                        "task_id": int(row["task_id"]),
                        "deduped": (not inserted),
                        "archived_conflicts": int(archived_conflicts),
                        "due_date_set": (row.get("due_date") is not None),
                    },
                )
            else:
                deduped += 1
                _log_run_item_safe(
                    conn,
                    run_id=int(run_id),
                    regular_task_id=int(rid),
                    period_id=int(period_id),
                    executor_role_id=int(executor_role_id),
                    is_due=True,
                    created_tasks=0,
                    status="ok",
                    error=None,
                    meta={**base_meta, "task_id": None, "deduped": True, "archived_conflicts": int(archived_conflicts)},
                )

        except Exception as e:
            err_str = str(e)
            errors.append({"regular_task_id": rid, "error": err_str})
            _log_run_item_safe(
                conn,
                run_id=int(run_id),
                regular_task_id=int(rid),
                period_id=None,
                executor_role_id=_safe_int(t.get("executor_role_id")),
                is_due=True,
                created_tasks=0,
                status="error",
                error=err_str,
                meta=base_meta,
            )
            continue

    stats = RunStats(
        templates_total=int(total),
        templates_due=int(due),
        created=int(created),
        deduped=int(deduped),
        errors=int(len(errors)),
    )

    conn.execute(
        text(
            """
            UPDATE public.regular_task_runs
            SET finished_at = now(),
                status = CASE WHEN :errors_cnt > 0 THEN 'partial' ELSE 'ok' END,
                stats = CAST(:stats AS jsonb),
                errors = CASE WHEN :errors_cnt > 0 THEN CAST(:errors AS jsonb) ELSE NULL END
            WHERE run_id = :run_id
            """
        ),
        {
            "run_id": int(run_id),
            "errors_cnt": int(len(errors)),
            "stats": json.dumps(stats.__dict__, ensure_ascii=False),
            "errors": json.dumps(errors, ensure_ascii=False),
        },
    )

    return int(run_id), stats.__dict__
