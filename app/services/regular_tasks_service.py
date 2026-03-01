# app/services/regular_tasks_service.py

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Connection


# ---------------------------
# ENV helpers
# ---------------------------

def _env_int(name: str, default: int) -> int:
    v = (os.getenv(name) or "").strip()
    if not v:
        return default
    try:
        return int(v)
    except Exception:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    if not v:
        return bool(default)
    if v in ("1", "true", "yes", "y", "on"):
        return True
    if v in ("0", "false", "no", "n", "off"):
        return False
    return bool(default)


def _env_date(name: str) -> Optional[date]:
    v = (os.getenv(name) or "").strip()
    if not v:
        return None
    try:
        # YYYY-MM-DD
        return date.fromisoformat(v)
    except Exception:
        return None


SYSTEM_USER_ID: int = _env_int("REGULAR_TASKS_SYSTEM_USER_ID", 1)
TZ_OFFSET_HOURS: int = _env_int("REGULAR_TASKS_TZ_OFFSET_HOURS", 5)

# fallback (если вдруг _reporting_period_resolve сломается)
FALLBACK_PERIOD_ID: int = _env_int("REGULAR_TASKS_FALLBACK_PERIOD_ID", 1)

# Task statuses (public.task_statuses)
ARCHIVED_STATUS_ID: int = _env_int("TASK_STATUS_ID_ARCHIVED", 5)
IN_PROGRESS_STATUS_CODE: str = os.getenv("TASK_STATUS_CODE_IN_PROGRESS") or "IN_PROGRESS"

# Force-run helpers:
# - REGULAR_TASKS_RUN_FOR_DATE=YYYY-MM-DD  -> считать, что "сегодня" = эта дата (для due-check + period-resolve)
# - REGULAR_TASKS_FORCE_DUE_ALL=1          -> игнорировать due-check (все активные шаблоны считаются due)
# - REGULAR_TASKS_IGNORE_TIME_GATE=1       -> игнорировать schedule_params.time (по умолчанию True, если задан RUN_FOR_DATE)
FORCE_RUN_FOR_DATE: Optional[date] = _env_date("REGULAR_TASKS_RUN_FOR_DATE")
FORCE_DUE_ALL: bool = _env_bool("REGULAR_TASKS_FORCE_DUE_ALL", False)
IGNORE_TIME_GATE_ENV: bool = _env_bool("REGULAR_TASKS_IGNORE_TIME_GATE", False)

_LOCAL_TZ = timezone(timedelta(hours=TZ_OFFSET_HOURS))


def _compute_base_title_from_template(*, report_code: str, template_title: str) -> str:
    """
    Source of truth for task title:
      1) template_title (rt.title) if present
      2) report_code otherwise

    No dependency on external ReportCatalog / env / json.
    """
    tt = (template_title or "").strip()
    if tt:
        return f"Подготовить {tt}"

    code = (report_code or "").strip()
    if code:
        return f"Подготовить {code}"

    # last resort
    return "Подготовить отчёт"


@dataclass(frozen=True)
class RunStats:
    templates_total: int
    templates_due: int
    created: int
    deduped: int
    errors: int


def _now_local() -> datetime:
    # фиксируем UTC+5 как в проекте (простая модель)
    return datetime.now(_LOCAL_TZ)


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
# Weekly period bounds
# ---------------------------
def _prev_week_period_bounds_simple(for_date: date) -> Tuple[date, date]:
    """
    Модель "предыдущая неделя" для ваших запусков:
      предыдущий период = [for_date - 7 дней .. for_date - 1 день]

    Пример:
      for_date = 2026-02-19 (четверг)
      -> prev = 2026-02-12 .. 2026-02-18
    """
    d1 = for_date - timedelta(days=1)
    d0 = for_date - timedelta(days=7)
    return d0, d1


def _prev_month_period_bounds(for_date: date) -> Tuple[date, date]:
    first_cur = _first_day_of_month(for_date)
    last_prev = first_cur - timedelta(days=1)
    return _first_day_of_month(last_prev), _last_day_of_month(last_prev)


def _prev_year_period_bounds(for_date: date) -> Tuple[date, date]:
    y = for_date.year - 1
    return _first_day_of_year(y), _last_day_of_year(y)


# ---------------------------
# Schedule parsing helpers
# ---------------------------

_WEEKDAY_MAP: Dict[str, int] = {
    # EN
    "MO": 1,
    "MON": 1,
    "MONDAY": 1,
    "TU": 2,
    "TUE": 2,
    "TUES": 2,
    "TUESDAY": 2,
    "WE": 3,
    "WED": 3,
    "WEDNESDAY": 3,
    "TH": 4,
    "THU": 4,
    "THUR": 4,
    "THURS": 4,
    "THURSDAY": 4,
    "FR": 5,
    "FRI": 5,
    "FRIDAY": 5,
    "SA": 6,
    "SAT": 6,
    "SATURDAY": 6,
    "SU": 7,
    "SUN": 7,
    "SUNDAY": 7,
    # RU
    "ПН": 1,
    "ПОН": 1,
    "ПОНЕДЕЛЬНИК": 1,
    "ВТ": 2,
    "ВТО": 2,
    "ВТОРНИК": 2,
    "СР": 3,
    "СРЕДА": 3,
    "ЧТ": 4,
    "ЧЕТ": 4,
    "ЧЕТВЕРГ": 4,
    "ПТ": 5,
    "ПЯТ": 5,
    "ПЯТНИЦА": 5,
    "СБ": 6,
    "СУБ": 6,
    "СУББОТА": 6,
    "ВС": 7,
    "ВОС": 7,
    "ВОСКРЕСЕНЬЕ": 7,
}


def _weekday_token_to_iso(x: Any) -> Optional[int]:
    if x is None:
        return None
    if isinstance(x, bool):
        return None
    if isinstance(x, int):
        return x if 1 <= x <= 7 else None
    if isinstance(x, float):
        try:
            v = int(x)
            return v if 1 <= v <= 7 else None
        except Exception:
            return None
    s = str(x).strip()
    if not s:
        return None
    # numeric string?
    try:
        v = int(s)
        return v if 1 <= v <= 7 else None
    except Exception:
        pass
    key = re.sub(r"\s+", "", s).upper()
    return _WEEKDAY_MAP.get(key)


def _as_int_list(v: Any) -> List[int]:
    if v is None:
        return []
    if isinstance(v, list):
        out: List[int] = []
        for x in v:
            try:
                out.append(int(x))
            except Exception:
                continue
        return out
    # allow scalar: 15, "15"
    try:
        return [int(v)]
    except Exception:
        return []


# ---------------------------
# Schedule target date
# ---------------------------
def _target_date_for_template(d: date, schedule_type: str, schedule_params: Dict[str, Any]) -> Optional[date]:
    st = (schedule_type or "").strip().lower()

    if st == "weekly":
        byweekday_raw = schedule_params.get("byweekday")
        if byweekday_raw is None:
            return None

        wanted: set[int] = set()
        if isinstance(byweekday_raw, list):
            for x in byweekday_raw:
                wd = _weekday_token_to_iso(x)
                if wd is not None:
                    wanted.add(wd)
        else:
            # allow scalar
            wd = _weekday_token_to_iso(byweekday_raw)
            if wd is not None:
                wanted.add(wd)

        if not wanted:
            return None

        # find next day in [d..d+6] matching wanted weekday
        for i in range(0, 7):
            cand = d + timedelta(days=i)
            if cand.isoweekday() in wanted:
                return cand
        return None

    if st == "monthly":
        bymonthday = schedule_params.get("bymonthday")
        md_list = _as_int_list(bymonthday)
        if not md_list:
            return None
        for md in md_list:
            if md == -1:
                return _last_day_of_month(d)
            if 1 <= md <= 31:
                last = _last_day_of_month(d)
                return date(d.year, d.month, min(md, last.day))
        return None

    if st == "yearly":
        bymonth = schedule_params.get("bymonth")
        bymonthday = schedule_params.get("bymonthday")

        m_list = _as_int_list(bymonth)
        md_list = _as_int_list(bymonthday)
        if not m_list or not md_list:
            return None

        mm: Optional[int] = None
        for m in m_list:
            if 1 <= m <= 12:
                mm = m
                break
        if mm is None:
            return None

        md: Optional[int] = None
        for dday in md_list:
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
    st = (schedule_type or "").strip().lower()
    if not st:
        return "schedule_type is required"
    if st not in ("weekly", "monthly", "yearly"):
        return f"unsupported schedule_type: {st}"

    if st == "weekly":
        byweekday = schedule_params.get("byweekday")
        if byweekday is None:
            return "schedule_params.byweekday must be provided for schedule_type=weekly"
        # accept scalar or list; validate after normalization
        wanted: List[int] = []
        if isinstance(byweekday, list):
            for x in byweekday:
                wd = _weekday_token_to_iso(x)
                if wd is not None:
                    wanted.append(wd)
        else:
            wd = _weekday_token_to_iso(byweekday)
            if wd is not None:
                wanted.append(wd)
        if not wanted:
            return "schedule_params.byweekday must contain weekday tokens (1..7 or MO/TU/... or ПН/ВТ/...) for schedule_type=weekly"

    if st == "monthly":
        bymonthday = schedule_params.get("bymonthday")
        md_list = _as_int_list(bymonthday)
        if not md_list:
            return "schedule_params.bymonthday must be provided (list or int) for schedule_type=monthly"

    if st == "yearly":
        bymonth = schedule_params.get("bymonth")
        bymonthday = schedule_params.get("bymonthday")
        m_list = _as_int_list(bymonth)
        md_list = _as_int_list(bymonthday)
        if not m_list:
            return "schedule_params.bymonth must be provided (list or int) for schedule_type=yearly"
        if not md_list:
            return "schedule_params.bymonthday must be provided (list or int) for schedule_type=yearly"

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
    today_override: Optional[date] = None,
    ignore_time_gate: bool = False,
) -> bool:
    today = today_override or now_local.date()

    target_date = _target_date_for_template(today, schedule_type, schedule_params)
    if target_date is None:
        return False

    create_day = target_date - timedelta(days=max(int(create_offset_days), 0))
    if today != create_day:
        return False

    if not ignore_time_gate:
        tt = _parse_time_hhmm(str(schedule_params.get("time") or ""))
        if tt is not None:
            if now_local.time() < tt:
                return False

    return True


def _reporting_period_resolve(
    conn: Connection,
    *,
    schedule_type: str,
    for_date: date,
) -> Tuple[int, date, date]:
    """
    Rule: task is created for PREVIOUS period:
      - weekly  -> [for_date-7 .. for_date-1]
      - monthly -> previous month
      - yearly  -> previous year
    """
    st = (schedule_type or "").strip().lower()
    if st == "weekly":
        d0, d1 = _prev_week_period_bounds_simple(for_date)
        kind = "weekly"
        label = f"{d0.isoformat()}..{d1.isoformat()}"
    elif st == "yearly":
        d0, d1 = _prev_year_period_bounds(for_date)
        kind = "yearly"
        label = f"{d0.year}"
    else:
        d0, d1 = _prev_month_period_bounds(for_date)
        kind = "monthly"
        label = f"{d0.isoformat()}..{d1.isoformat()}"

    row = conn.execute(
        text(
            """
            SELECT period_id
            FROM public.reporting_periods
            WHERE kind = :kind
              AND date_start = :ds
              AND date_end = :de
            """
        ),
        {"kind": kind, "ds": d0, "de": d1},
    ).mappings().first()
    if row and row.get("period_id"):
        return int(row["period_id"]), d0, d1

    inserted = conn.execute(
        text(
            """
            WITH existing AS (
              SELECT period_id
              FROM public.reporting_periods
              WHERE kind = :kind
                AND date_start = :ds
                AND date_end = :de
              LIMIT 1
            )
            INSERT INTO public.reporting_periods (kind, date_start, date_end, label, is_closed)
            SELECT :kind, :ds, :de, :label, false
            WHERE NOT EXISTS (SELECT 1 FROM existing)
            RETURNING period_id
            """
        ),
        {"kind": kind, "ds": d0, "de": d1, "label": label},
    ).scalar()

    if inserted is not None:
        return int(inserted), d0, d1

    row2 = conn.execute(
        text(
            """
            SELECT period_id
            FROM public.reporting_periods
            WHERE kind = :kind
              AND date_start = :ds
              AND date_end = :de
            """
        ),
        {"kind": kind, "ds": d0, "de": d1},
    ).scalar_one()
    return int(row2), d0, d1


def _period_suffix_for_template(schedule_type: str, period_start: date, period_end: date) -> str:
    """
    Unified suffix policy:
      weekly  -> DD.MM.YYYY–DD.MM.YYYY
      monthly -> MM.YYYY
      yearly  -> YYYY
    """
    st = (schedule_type or "").strip().lower()

    if st == "weekly":
        return f"{period_start:%d.%m.%Y}–{period_end:%d.%m.%Y}"

    if st == "monthly":
        return f"{period_start.month:02d}.{period_start.year}"

    if st == "yearly":
        return f"{period_start.year}"

    return f"{period_start.year}"


def _due_date_from_reporting_period_end(*, period_end: date, due_offset_days: int) -> date:
    return period_end + timedelta(days=int(due_offset_days or 0))


def _get_status_id(conn: Connection, code: str) -> int:
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


def _select_active_task_same_executor(
    conn: Connection,
    *,
    regular_task_id: int,
    period_id: int,
    assignment_scope: str,
    executor_role_id: int,
) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT task_id, executor_role_id, status_id, due_date
            FROM public.tasks
            WHERE regular_task_id = :regular_task_id
              AND period_id = :period_id
              AND assignment_scope = :assignment_scope
              AND executor_role_id = :executor_role_id
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
            "executor_role_id": int(executor_role_id),
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


def _compose_task_title(*, base_title: str, role_name: str, suffix: str) -> str:
    bt = (base_title or "").strip() or "Без названия"
    rn = (role_name or "").strip() or "Без роли"
    suf = (suffix or "").strip()

    if suf and re.search(rf"\(\s*{re.escape(suf)}\s*\)\s*$", bt):
        bt = re.sub(rf"\(\s*{re.escape(suf)}\s*\)\s*$", "", bt).strip()

    if suf:
        return f"{bt} → {rn} ({suf})"
    return f"{bt} → {rn}"


def run_regular_tasks_generation_tx(
    conn: Connection,
    *,
    run_at_local: Optional[datetime] = None,
    dry_run: bool = False,
) -> Tuple[int, Dict[str, Any]]:
    now_local = run_at_local or _now_local()

    # "сегодня" для due-check + period-resolve
    today_effective: date = FORCE_RUN_FOR_DATE or now_local.date()

    # если задан REGULAR_TASKS_RUN_FOR_DATE — по умолчанию игнорируем time-gate, чтобы можно было прогонять ретроспективно
    ignore_time_gate: bool = IGNORE_TIME_GATE_ENV or (FORCE_RUN_FOR_DATE is not None)

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
                rt.regular_task_id,
                rt.is_active,

                rt.code AS report_code,
                rt.title,
                rt.description,

                rt.executor_role_id,
                rt.assignment_scope,
                rt.schedule_type,
                rt.schedule_params,
                rt.create_offset_days,
                rt.due_offset_days,

                r.name AS executor_role_name,
                r.code AS executor_role_code
            FROM public.regular_tasks rt
            LEFT JOIN public.roles r ON r.role_id = rt.executor_role_id
            WHERE COALESCE(rt.is_active, true) = true
            ORDER BY rt.regular_task_id
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
            "today_effective": today_effective.isoformat(),
            "force_due_all": bool(FORCE_DUE_ALL),
            "force_run_for_date": FORCE_RUN_FOR_DATE.isoformat() if FORCE_RUN_FOR_DATE else None,
            "ignore_time_gate": bool(ignore_time_gate),
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

            if FORCE_DUE_ALL:
                is_due = True
            else:
                is_due = _is_due_today_or_with_offset(
                    now_local=now_local,
                    schedule_type=schedule_type,
                    schedule_params=schedule_params,
                    create_offset_days=create_offset_days,
                    today_override=today_effective,
                    ignore_time_gate=ignore_time_gate,
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

            with conn.begin_nested():
                try:
                    period_id, period_start, period_end = _reporting_period_resolve(
                        conn, schedule_type=schedule_type, for_date=today_effective
                    )
                except Exception:
                    period_id = int(FALLBACK_PERIOD_ID)
                    period_start, period_end = _prev_month_period_bounds(today_effective)

                due_date_val = _due_date_from_reporting_period_end(period_end=period_end, due_offset_days=due_offset_days)
                suffix = _period_suffix_for_template(schedule_type, period_start, period_end)

                report_code = str(t.get("report_code") or "").strip()
                template_title = str(t.get("title") or "").strip()

                base_title = _compute_base_title_from_template(
                    report_code=report_code,
                    template_title=template_title,
                )

                role_name = str(t.get("executor_role_name") or "").strip()
                if not role_name:
                    role_name = str(t.get("executor_role_code") or "").strip() or f"role#{executor_role_id}"

                title_final = _compose_task_title(base_title=base_title, role_name=role_name, suffix=suffix)

                base_meta.update(
                    {
                        "period_id": int(period_id),
                        "period_start": period_start.isoformat(),
                        "period_end": period_end.isoformat(),
                        "due_date": due_date_val.isoformat() if due_date_val else None,
                        "title_suffix": suffix,
                        "title_final": title_final,
                        "assignment_scope": assignment_scope,
                        "executor_role_name": role_name,
                        "report_code": report_code,
                        "template_title": template_title,
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

                # 1) Если уже есть активная задача ровно под этого исполнителя — обновляем due_date (dedupe)
                same_exec_row = _select_active_task_same_executor(
                    conn,
                    regular_task_id=int(rid),
                    period_id=int(period_id),
                    assignment_scope=assignment_scope,
                    executor_role_id=int(executor_role_id),
                )
                if same_exec_row and same_exec_row.get("task_id"):
                    active_task_id = int(same_exec_row["task_id"])
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
                            "dedupe_mode": "same_executor_active_exists",
                        },
                    )
                    continue

                # 2) Если есть активная задача по шаблону/периоду/скоупу, но на другого исполнителя — архивируем конфликт
                archived_conflicts = 0
                active_row = _select_active_task_for_template(
                    conn,
                    regular_task_id=int(rid),
                    period_id=int(period_id),
                    assignment_scope=assignment_scope,
                )
                if active_row and active_row.get("task_id"):
                    active_task_id = int(active_row["task_id"])
                    archived_conflicts = _archive_task_by_id(conn, task_id=active_task_id)

                in_progress_status_id = _get_status_id(conn, IN_PROGRESS_STATUS_CODE)

                # ВАЖНО:
                # Раньше был ON CONFLICT(period_id, regular_task_id, executor_role_id) — у тебя в БД нет соответствующего unique/exclusion.
                # Поэтому вставляем без ON CONFLICT и дедупим через SELECT выше.
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
                        RETURNING task_id, due_date
                        """
                    ),
                    {
                        "period_id": int(period_id),
                        "regular_task_id": int(rid),
                        "title": title_final,
                        "description": t.get("description"),
                        "initiator_user_id": int(SYSTEM_USER_ID),
                        "executor_role_id": int(executor_role_id),
                        "assignment_scope": assignment_scope,
                        "status_id": int(in_progress_status_id),
                        "due_date": due_date_val,
                    },
                ).mappings().first()

                if row and row.get("task_id"):
                    created += 1
                    _log_run_item_safe(
                        conn,
                        run_id=int(run_id),
                        regular_task_id=int(rid),
                        period_id=int(period_id),
                        executor_role_id=int(executor_role_id),
                        is_due=True,
                        created_tasks=1,
                        status="ok",
                        error=None,
                        meta={
                            **base_meta,
                            "task_id": int(row["task_id"]),
                            "deduped": False,
                            "archived_conflicts": int(archived_conflicts),
                            "due_date_set": (row.get("due_date") is not None),
                            "insert_mode": "plain_insert_no_on_conflict",
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
                        meta={
                            **base_meta,
                            "task_id": None,
                            "deduped": True,
                            "archived_conflicts": int(archived_conflicts),
                            "insert_mode": "plain_insert_no_return",
                        },
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