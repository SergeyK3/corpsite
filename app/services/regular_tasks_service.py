# app/services/regular_tasks_service.py

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.org_scope.apply import apply_org_scope
from app.org_scope.types import OrgScopeParams, OrgScopeStrategy


logger = logging.getLogger(__name__)

JOURNAL_ORPHAN_WARNING = (
    "Внимание: статистика запуска содержит результаты, но элементы журнала отсутствуют. "
    "Возможна неполная запись журнала."
)
JOURNAL_MISMATCH_WARNING = (
    "Внимание: число элементов журнала не совпадает с числом обработанных due-шаблонов. "
    "Возможна неполная запись журнала."
)


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

# Task metadata for generated regular tasks
REGULAR_TASK_KIND: str = (os.getenv("REGULAR_TASKS_TASK_KIND") or "regular").strip()
REGULAR_TASKS_SOURCE_KIND: str = (os.getenv("REGULAR_TASKS_SOURCE_KIND") or "regular_task").strip()

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

    return "Подготовить отчёт"


@dataclass(frozen=True)
class RunStats:
    templates_total: int
    templates_due: int
    created: int
    deduped: int
    errors: int


def _now_local() -> datetime:
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
            wd = _weekday_token_to_iso(byweekday_raw)
            if wd is not None:
                wanted.add(wd)

        if not wanted:
            return None

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


def _normalize_assignment_scope(value: Any) -> str:
    s = str(value or "").strip().lower()

    if not s:
        return "functional"

    aliases = {
        "functional": "functional",
        "func": "functional",
        "role": "functional",
        "structural": "structural",
        "structure": "structural",
        "dept": "structural",
        "department": "structural",
        "unit": "structural",
        "org_unit": "structural",
        "admin": "admin",
    }

    normalized = aliases.get(s)
    if not normalized:
        raise ValueError(f"unsupported assignment_scope: {s}")
    return normalized


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
        if tt is not None and now_local.time() < tt:
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


def _fallback_period_bounds(schedule_type: str, for_date: date) -> Tuple[date, date]:
    st = (schedule_type or "").strip().lower()
    if st == "weekly":
        return _prev_week_period_bounds_simple(for_date)
    if st == "yearly":
        return _prev_year_period_bounds(for_date)
    return _prev_month_period_bounds(for_date)


def _period_suffix_for_template(schedule_type: str, period_start: date, period_end: date) -> str:
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


def _dedup_item_meta(
    *,
    base_meta: Dict[str, Any],
    regular_task_id: int,
    task_id: Optional[int],
    task_title: str,
    period_id: int,
    executor_role_id: int,
    assignment_scope: str,
    occurrence_date: date,
    run_kind: str,
    dedupe_mode: str,
    **extra: Any,
) -> Dict[str, Any]:
    return {
        **base_meta,
        **extra,
        "regular_task_id": int(regular_task_id),
        "task_id": int(task_id) if task_id is not None else None,
        "task_title": str(task_title),
        "period_id": int(period_id),
        "executor_role_id": int(executor_role_id),
        "assignment_scope": str(assignment_scope),
        "occurrence_date": occurrence_date.isoformat(),
        "run_kind": str(run_kind),
        "dedupe_mode": str(dedupe_mode),
        "deduped": True,
    }


def _log_run_item(
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
    journal_errors: List[Dict[str, Any]],
) -> bool:
    try:
        with conn.begin_nested():
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
        return True
    except Exception as exc:
        logger.exception(
            "Failed to insert regular_task_run_items row (run_id=%s regular_task_id=%s)",
            run_id,
            regular_task_id,
        )
        journal_errors.append(
            {
                "kind": "journal_insert_failed",
                "regular_task_id": int(regular_task_id),
                "error": str(exc),
            }
        )
        return False


def _count_run_items(conn: Connection, run_id: int) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(1)
                FROM public.regular_task_run_items
                WHERE run_id = :run_id
                """
            ),
            {"run_id": int(run_id)},
        ).scalar()
        or 0
    )


def _resolve_journal_warning(
    *,
    stats: Dict[str, Any],
    item_count: int,
    templates_due: int,
) -> Optional[str]:
    existing = str(stats.get("journal_warning") or "").strip()
    if existing:
        return existing

    created = int(stats.get("created") or 0)
    deduped = int(stats.get("deduped") or 0)
    if item_count == 0 and (templates_due > 0 or (created + deduped) > 0):
        return JOURNAL_ORPHAN_WARNING
    if templates_due > 0 and item_count != templates_due:
        return JOURNAL_MISMATCH_WARNING
    return None


def _compose_task_title(*, base_title: str, role_name: str, suffix: str) -> str:
    bt = (base_title or "").strip() or "Без названия"
    rn = (role_name or "").strip() or "Без роли"
    suf = (suffix or "").strip()

    if suf and re.search(rf"\(\s*{re.escape(suf)}\s*\)\s*$", bt):
        bt = re.sub(rf"\(\s*{re.escape(suf)}\s*\)\s*$", "", bt).strip()

    if suf:
        return f"{bt} → {rn} ({suf})"
    return f"{bt} → {rn}"


_ORIGIN_METADATA_RUN_MARKER = "ID запуска:"


def _catch_up_period_label(preset: str) -> Optional[str]:
    labels = {
        "past_week": "Прошлая неделя",
        "past_month": "Прошлый месяц",
        "manual": "Ручная дата",
    }
    return labels.get((preset or "").strip().lower())


def _task_occurrence_date(*, today_effective: date) -> date:
    return today_effective


def _compose_task_origin_metadata_block(
    *,
    run_id: int,
    occurrence_date: date,
    catch_up_meta: Optional[Dict[str, Any]],
    period_suffix: str,
) -> str:
    lines: List[str] = []
    if catch_up_meta is not None:
        lines.append("Источник: Догоняющий запуск регулярной задачи")
        lines.append(f"ID запуска: {run_id}")
        lines.append(f"Дата возникновения задачи: {occurrence_date.isoformat()}")
        lines.append("Тип запуска: догоняющий")
        preset = str(catch_up_meta.get("preset") or "").strip().lower()
        period_label = _catch_up_period_label(preset)
        if period_label:
            lines.append(f"Период: {period_label}")
        elif period_suffix:
            lines.append(f"Период: {period_suffix}")
    else:
        lines.append("Источник: Автоматический запуск регулярной задачи")
        lines.append(f"ID запуска: {run_id}")
        lines.append(f"Дата возникновения задачи: {occurrence_date.isoformat()}")
        lines.append("Тип запуска: автоматический")
    return "\n---\n" + "\n".join(lines) + "\n---"


def _append_origin_metadata_to_description(
    existing: Optional[str],
    metadata_block: str,
    *,
    run_id: int,
) -> str:
    base = (existing or "").rstrip()
    marker = f"{_ORIGIN_METADATA_RUN_MARKER} {run_id}"
    if marker in base:
        return base
    if not base:
        return metadata_block.strip("\n")
    return f"{base}{metadata_block}"


def _append_origin_metadata_to_task(
    conn: Connection,
    *,
    task_id: int,
    run_id: int,
    occurrence_date: date,
    catch_up_meta: Optional[Dict[str, Any]],
    period_suffix: str,
) -> bool:
    row = conn.execute(
        text("SELECT description FROM public.tasks WHERE task_id = :task_id FOR UPDATE"),
        {"task_id": int(task_id)},
    ).mappings().first()
    if not row:
        return False
    block = _compose_task_origin_metadata_block(
        run_id=run_id,
        occurrence_date=occurrence_date,
        catch_up_meta=catch_up_meta,
        period_suffix=period_suffix,
    )
    new_desc = _append_origin_metadata_to_description(
        row.get("description"),
        block,
        run_id=run_id,
    )
    current = (row.get("description") or "").rstrip()
    if new_desc == current:
        return False
    conn.execute(
        text("UPDATE public.tasks SET description = :description WHERE task_id = :task_id"),
        {"description": new_desc, "task_id": int(task_id)},
    )
    return True


def _advisory_lock_key(
    *,
    regular_task_id: int,
    period_id: int,
    assignment_scope: str,
    executor_role_id: int,
) -> int:
    raw = f"{int(regular_task_id)}|{int(period_id)}|{assignment_scope}|{int(executor_role_id)}".encode("utf-8")
    digest = hashlib.sha1(raw).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False) & 0x7FFFFFFFFFFFFFFF


def _acquire_task_slot_lock(
    conn: Connection,
    *,
    regular_task_id: int,
    period_id: int,
    assignment_scope: str,
    executor_role_id: int,
) -> int:
    lock_key = _advisory_lock_key(
        regular_task_id=regular_task_id,
        period_id=period_id,
        assignment_scope=assignment_scope,
        executor_role_id=executor_role_id,
    )
    conn.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": int(lock_key)})
    return lock_key


@dataclass(frozen=True)
class CatchUpTemplateFilters:
    schedule_type: Optional[str] = None
    org_group_id: Optional[int] = None
    org_unit_id: Optional[int] = None
    executor_role_id: Optional[int] = None


def resolve_catch_up_run_for_date(
    preset: str,
    today: date,
    *,
    manual_date: Optional[date] = None,
) -> date:
    p = (preset or "").strip().lower()
    if p == "manual":
        if manual_date is None:
            raise ValueError("run_for_date is required when preset=manual")
        return manual_date
    if p == "past_month":
        first_cur = _first_day_of_month(today)
        last_prev = first_cur - timedelta(days=1)
        return _first_day_of_month(last_prev)
    if p == "past_week":
        start = today - timedelta(days=7)
        end = today - timedelta(days=1)
        last_wed: Optional[date] = None
        d = start
        while d <= end:
            if d.isoweekday() == 3:
                last_wed = d
            d += timedelta(days=1)
        if last_wed is not None:
            return last_wed
        d = today - timedelta(days=1)
        while d.isoweekday() != 3:
            d -= timedelta(days=1)
        return d
    raise ValueError(f"unsupported catch-up preset: {preset}")


def resolve_catch_up_schedule_type(preset: str, schedule_type: Optional[str]) -> Optional[str]:
    explicit = (schedule_type or "").strip().lower()
    if explicit:
        return explicit
    p = (preset or "").strip().lower()
    if p == "past_week":
        return "weekly"
    if p == "past_month":
        return "monthly"
    return None


def _load_regular_task_templates(
    conn: Connection,
    *,
    template_filters: Optional[CatchUpTemplateFilters] = None,
) -> List[Any]:
    filters: List[str] = ["COALESCE(rt.is_active, true) = true"]
    params: Dict[str, Any] = {}
    scope_prefix = ""

    if template_filters is not None:
        if template_filters.schedule_type:
            params["schedule_type"] = str(template_filters.schedule_type).strip().lower()
            filters.append("LOWER(TRIM(COALESCE(rt.schedule_type, ''))) = :schedule_type")

        if template_filters.executor_role_id is not None:
            params["executor_role_id"] = int(template_filters.executor_role_id)
            filters.append("rt.executor_role_id = :executor_role_id")

        org_scope = apply_org_scope(
            strategy=OrgScopeStrategy.OWNER_UNIT,
            params=OrgScopeParams(
                org_group_id=template_filters.org_group_id,
                org_unit_id=template_filters.org_unit_id,
            ),
            regular_task_alias="rt",
            owner_unit_column="owner_unit_id",
        )
        params.update(org_scope.params)
        if org_scope.where_sql != "TRUE":
            filters.append(f"({org_scope.where_sql})")
        scope_prefix = f"{org_scope.cte_sql}\n" if org_scope.cte_sql else ""

    where_sql = " AND ".join(filters)
    return conn.execute(
        text(
            f"""
            {scope_prefix}
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
            LEFT JOIN public.org_units ou ON ou.unit_id = rt.owner_unit_id
            WHERE {where_sql}
            ORDER BY rt.regular_task_id
            """
        ),
        params,
    ).mappings().all()


def run_regular_tasks_catch_up_tx(
    conn: Connection,
    *,
    preset: str,
    dry_run: bool = False,
    run_for_date_manual: Optional[date] = None,
    schedule_type: Optional[str] = None,
    org_group_id: Optional[int] = None,
    org_unit_id: Optional[int] = None,
    executor_role_id: Optional[int] = None,
) -> Tuple[int, Dict[str, Any], Dict[str, Any]]:
    today = _now_local().date()
    resolved_date = resolve_catch_up_run_for_date(
        preset,
        today,
        manual_date=run_for_date_manual,
    )
    resolved_schedule = resolve_catch_up_schedule_type(preset, schedule_type)
    filters = CatchUpTemplateFilters(
        schedule_type=resolved_schedule,
        org_group_id=org_group_id,
        org_unit_id=org_unit_id,
        executor_role_id=executor_role_id,
    )
    resolved: Dict[str, Any] = {
        "preset": (preset or "").strip().lower(),
        "run_for_date": resolved_date.isoformat(),
        "schedule_type": resolved_schedule,
        "org_group_id": int(org_group_id) if org_group_id is not None else None,
        "org_unit_id": int(org_unit_id) if org_unit_id is not None else None,
        "executor_role_id": int(executor_role_id) if executor_role_id is not None else None,
    }
    run_at_local = datetime.combine(resolved_date, time(12, 0), tzinfo=_LOCAL_TZ)
    run_id, stats = run_regular_tasks_generation_tx(
        conn,
        run_at_local=run_at_local,
        dry_run=dry_run,
        run_for_date=resolved_date,
        force_due=True,
        template_filters=filters,
        catch_up_meta=resolved,
    )
    resolved["templates_in_scope"] = int(stats.get("templates_total") or 0)
    return int(run_id), stats, resolved


def run_regular_tasks_generation_tx(
    conn: Connection,
    *,
    run_at_local: Optional[datetime] = None,
    dry_run: bool = False,
    run_for_date: Optional[date] = None,
    force_due: bool = False,
    template_filters: Optional[CatchUpTemplateFilters] = None,
    catch_up_meta: Optional[Dict[str, Any]] = None,
) -> Tuple[int, Dict[str, Any]]:
    if run_for_date is not None:
        now_local = run_at_local or datetime.combine(run_for_date, time(12, 0), tzinfo=_LOCAL_TZ)
        today_effective = run_for_date
        ignore_time_gate = True
    else:
        now_local = run_at_local or _now_local()
        today_effective = FORCE_RUN_FOR_DATE or now_local.date()
        ignore_time_gate = IGNORE_TIME_GATE_ENV or (FORCE_RUN_FOR_DATE is not None)

    run_id = conn.execute(
        text(
            """
            INSERT INTO public.regular_task_runs (started_at, status, stats, errors)
            VALUES (now(), 'ok', '{}'::jsonb, '[]'::jsonb)
            RETURNING run_id
            """
        )
    ).scalar_one()

    errors: List[Dict[str, Any]] = []
    journal_errors: List[Dict[str, Any]] = []

    templates = _load_regular_task_templates(conn, template_filters=template_filters)

    total = len(templates)
    due = 0
    created = 0
    deduped = 0

    for t in templates:
        rid = _safe_int(t.get("regular_task_id"))
        if rid is None:
            errors.append({"regular_task_id": None, "error": "regular_task_id is not an int"})
            continue

        run_kind = "catch_up" if catch_up_meta is not None else "automatic"
        base_meta: Dict[str, Any] = {
            "dry_run": bool(dry_run),
            "now_local": now_local.isoformat(),
            "today_effective": today_effective.isoformat(),
            "occurrence_date": today_effective.isoformat(),
            "run_kind": run_kind,
            "force_due_all": bool(FORCE_DUE_ALL or force_due),
            "force_run_for_date": FORCE_RUN_FOR_DATE.isoformat() if FORCE_RUN_FOR_DATE else None,
            "ignore_time_gate": bool(ignore_time_gate),
            "catch_up": catch_up_meta,
        }

        template_marked_due = False
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
                continue

            if FORCE_DUE_ALL or force_due:
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
            template_marked_due = True

            executor_role_id = _safe_int(t.get("executor_role_id"))
            if executor_role_id is None:
                msg = "executor_role_id is required (cannot be NULL) when template is due"
                errors.append({"regular_task_id": rid, "error": msg})
                _log_run_item(
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
                    journal_errors=journal_errors,
                )
                continue

            try:
                assignment_scope = _normalize_assignment_scope(t.get("assignment_scope"))
            except Exception as e:
                msg = str(e)
                errors.append({"regular_task_id": rid, "error": msg})
                _log_run_item(
                    conn,
                    run_id=int(run_id),
                    regular_task_id=int(rid),
                    period_id=None,
                    executor_role_id=int(executor_role_id),
                    is_due=True,
                    created_tasks=0,
                    status="error",
                    error=msg,
                    meta=base_meta,
                    journal_errors=journal_errors,
                )
                continue

            with conn.begin_nested():
                try:
                    period_id, period_start, period_end = _reporting_period_resolve(
                        conn,
                        schedule_type=schedule_type,
                        for_date=today_effective,
                    )
                except Exception:
                    period_id = int(FALLBACK_PERIOD_ID)
                    period_start, period_end = _fallback_period_bounds(schedule_type, today_effective)

                due_date_val = _due_date_from_reporting_period_end(
                    period_end=period_end,
                    due_offset_days=due_offset_days,
                )
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

                title_final = _compose_task_title(
                    base_title=base_title,
                    role_name=role_name,
                    suffix=suffix,
                )

                lock_key = _acquire_task_slot_lock(
                    conn,
                    regular_task_id=int(rid),
                    period_id=int(period_id),
                    assignment_scope=assignment_scope,
                    executor_role_id=int(executor_role_id),
                )

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
                        "advisory_lock_key": int(lock_key),
                        "task_kind": REGULAR_TASK_KIND,
                        "source_kind": REGULAR_TASKS_SOURCE_KIND,
                        "requires_report": True,
                        "requires_approval": True,
                    }
                )

                occurrence_date = _task_occurrence_date(today_effective=today_effective)
                origin_block = _compose_task_origin_metadata_block(
                    run_id=int(run_id),
                    occurrence_date=occurrence_date,
                    catch_up_meta=catch_up_meta,
                    period_suffix=suffix,
                )
                description_with_origin = _append_origin_metadata_to_description(
                    t.get("description"),
                    origin_block,
                    run_id=int(run_id),
                )
                base_meta["origin_metadata_text"] = origin_block.strip("\n")

                if dry_run:
                    _log_run_item(
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
                        journal_errors=journal_errors,
                    )
                    continue

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
                    desc_updated = _append_origin_metadata_to_task(
                        conn,
                        task_id=active_task_id,
                        run_id=int(run_id),
                        occurrence_date=occurrence_date,
                        catch_up_meta=catch_up_meta,
                        period_suffix=suffix,
                    )
                    deduped += 1
                    _log_run_item(
                        conn,
                        run_id=int(run_id),
                        regular_task_id=int(rid),
                        period_id=int(period_id),
                        executor_role_id=int(executor_role_id),
                        is_due=True,
                        created_tasks=0,
                        status="ok",
                        error=None,
                        meta=_dedup_item_meta(
                            base_meta=base_meta,
                            regular_task_id=int(rid),
                            task_id=active_task_id,
                            task_title=title_final,
                            period_id=int(period_id),
                            executor_role_id=int(executor_role_id),
                            assignment_scope=assignment_scope,
                            occurrence_date=occurrence_date,
                            run_kind=run_kind,
                            dedupe_mode="same_executor_active_exists",
                            archived_conflicts=0,
                            due_date_updated=bool(updated > 0),
                            description_metadata_appended=bool(desc_updated),
                        ),
                        journal_errors=journal_errors,
                    )
                    continue

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

                row = conn.execute(
                    text(
                        """
                        INSERT INTO public.tasks (
                            period_id,
                            regular_task_id,
                            task_kind,
                            source_kind,
                            title,
                            description,
                            initiator_user_id,
                            executor_role_id,
                            assignment_scope,
                            status_id,
                            due_date,
                            requires_report,
                            requires_approval
                        )
                        VALUES (
                            :period_id,
                            :regular_task_id,
                            :task_kind,
                            :source_kind,
                            :title,
                            :description,
                            :initiator_user_id,
                            :executor_role_id,
                            :assignment_scope,
                            :status_id,
                            :due_date,
                            :requires_report,
                            :requires_approval
                        )
                        RETURNING task_id, due_date
                        """
                    ),
                    {
                        "period_id": int(period_id),
                        "regular_task_id": int(rid),
                        "task_kind": REGULAR_TASK_KIND,
                        "source_kind": REGULAR_TASKS_SOURCE_KIND,
                        "title": title_final,
                        "description": description_with_origin,
                        "initiator_user_id": int(SYSTEM_USER_ID),
                        "executor_role_id": int(executor_role_id),
                        "assignment_scope": assignment_scope,
                        "status_id": int(in_progress_status_id),
                        "due_date": due_date_val,
                        "requires_report": True,
                        "requires_approval": True,
                    },
                ).mappings().first()

                if row and row.get("task_id"):
                    created += 1
                    _log_run_item(
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
                            "task_title": title_final,
                            "deduped": False,
                            "archived_conflicts": int(archived_conflicts),
                            "due_date_set": (row.get("due_date") is not None),
                            "insert_mode": "plain_insert_no_on_conflict",
                        },
                        journal_errors=journal_errors,
                    )
                else:
                    deduped += 1
                    _log_run_item(
                        conn,
                        run_id=int(run_id),
                        regular_task_id=int(rid),
                        period_id=int(period_id),
                        executor_role_id=int(executor_role_id),
                        is_due=True,
                        created_tasks=0,
                        status="ok",
                        error=None,
                        meta=_dedup_item_meta(
                            base_meta=base_meta,
                            regular_task_id=int(rid),
                            task_id=None,
                            task_title=title_final,
                            period_id=int(period_id),
                            executor_role_id=int(executor_role_id),
                            assignment_scope=assignment_scope,
                            occurrence_date=occurrence_date,
                            run_kind=run_kind,
                            dedupe_mode="plain_insert_no_return",
                            archived_conflicts=int(archived_conflicts),
                            insert_mode="plain_insert_no_return",
                        ),
                        journal_errors=journal_errors,
                    )

        except Exception as e:
            err_str = str(e)
            errors.append({"regular_task_id": rid, "error": err_str})
            if template_marked_due:
                _log_run_item(
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
                    journal_errors=journal_errors,
                )
            continue

    if journal_errors:
        errors.extend(journal_errors)

    item_count = _count_run_items(conn, int(run_id))

    stats_dict: Dict[str, Any] = {
        "templates_total": int(total),
        "templates_due": int(due),
        "created": int(created),
        "deduped": int(deduped),
        "errors": int(len(errors)),
        "item_count": int(item_count),
        "occurrence_date": today_effective.isoformat(),
        "run_kind": "catch_up" if catch_up_meta is not None else "automatic",
        "dry_run": bool(dry_run),
    }
    if catch_up_meta is not None:
        stats_dict["catch_up"] = catch_up_meta

    journal_warning = _resolve_journal_warning(
        stats=stats_dict,
        item_count=int(item_count),
        templates_due=int(due),
    )
    if journal_warning:
        stats_dict["journal_warning"] = journal_warning

    run_status = "ok"
    if len(errors) > 0 or journal_warning:
        run_status = "partial"

    conn.execute(
        text(
            """
            UPDATE public.regular_task_runs
            SET finished_at = now(),
                status = :status,
                stats = CAST(:stats AS jsonb),
                errors = CAST(:errors AS jsonb)
            WHERE run_id = :run_id
            """
        ),
        {
            "run_id": int(run_id),
            "status": run_status,
            "stats": json.dumps(stats_dict, ensure_ascii=False),
            "errors": json.dumps(errors, ensure_ascii=False),
        },
    )

    return int(run_id), stats_dict