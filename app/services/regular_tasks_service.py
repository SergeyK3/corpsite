# FILE: app/services/regular_tasks_service.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
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

# fallback для проектов, где модель periods ещё не расширена:
FALLBACK_PERIOD_ID: int = _env_int("REGULAR_TASKS_FALLBACK_PERIOD_ID", 1)


@dataclass(frozen=True)
class RunStats:
    templates_total: int
    templates_due: int
    created: int
    deduped: int
    errors: int


def _now_local() -> datetime:
    # фиксируем UTC+5 как в проекте (простая модель)
    return datetime.utcnow() + timedelta(hours=TZ_OFFSET_HOURS)


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


def _target_date_for_template(d: date, schedule_type: str, schedule_params: Dict[str, Any]) -> Optional[date]:
    st = (schedule_type or "").strip().lower()

    if st == "weekly":
        byweekday = schedule_params.get("byweekday")
        if not isinstance(byweekday, list) or not byweekday:
            return None
        # выбираем ближайший день недели В ТЕКУЩЕЙ неделе (ISO), который соответствует byweekday
        # v1 policy: "точка" = первый совпадающий день недели, начиная с понедельника текущей недели
        # (простая и предсказуемая модель)
        week_start = d - timedelta(days=_weekday_iso(d) - 1)
        candidates: List[date] = []
        for x in byweekday:
            try:
                wd = int(x)
            except Exception:
                continue
            if wd < 1 or wd > 7:
                continue
            candidates.append(week_start + timedelta(days=wd - 1))
        if not candidates:
            return None
        return min(candidates)

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
                # ограничиваем в рамках месяца
                first = _first_day_of_month(d)
                last = _last_day_of_month(d)
                cand = date(d.year, d.month, min(md, last.day))
                if first <= cand <= last:
                    return cand
        return None

    return None


def _validate_template_schedule(schedule_type: str, schedule_params: Dict[str, Any]) -> Optional[str]:
    """
    Возвращает текст ошибки конфигурации расписания или None (если конфиг допустим).
    """
    st = (schedule_type or "").strip().lower()
    if not st:
        return "schedule_type is required"
    if st not in ("weekly", "monthly"):
        return f"unsupported schedule_type: {st}"

    if st == "weekly":
        byweekday = schedule_params.get("byweekday")
        if not isinstance(byweekday, list) or not byweekday:
            return "schedule_params.byweekday must be a non-empty list for schedule_type=weekly"

    if st == "monthly":
        bymonthday = schedule_params.get("bymonthday")
        if not isinstance(bymonthday, list) or not bymonthday:
            return "schedule_params.bymonthday must be a non-empty list for schedule_type=monthly"

    tt = schedule_params.get("time")
    if tt is not None:
        # если time задан — он должен парситься как HH:MM
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

    # если offset=0, создаём в день "точки"
    # если offset>0, создаём заранее (target - offset)
    create_day = target_date - timedelta(days=max(int(create_offset_days), 0))
    if today != create_day:
        return False

    # если задано время, создаём не раньше этого времени
    tt = _parse_time_hhmm(str(schedule_params.get("time") or ""))
    if tt is not None:
        if now_local.time() < tt:
            return False

    return True


def _period_resolve(conn: Connection, *, schedule_type: str, for_date: date) -> int:
    """
    v1: пытаемся использовать periods(period_type, period_key) если они существуют.
    иначе fallback на REGULAR_TASKS_FALLBACK_PERIOD_ID (для запуска уже сейчас).
    """
    cols = conn.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'periods'
              AND column_name IN ('period_type', 'period_key')
            """
        )
    ).scalars().all()
    has_period_type = "period_type" in cols
    has_period_key = "period_key" in cols

    st = (schedule_type or "").strip().lower()
    if has_period_type and has_period_key:
        if st == "weekly":
            iso_year, iso_week, _ = for_date.isocalendar()
            period_type = "week"
            period_key = f"{iso_year}-W{iso_week:02d}"
        else:
            period_type = "month"
            period_key = f"{for_date.year}-{for_date.month:02d}"

        row = conn.execute(
            text(
                """
                SELECT period_id
                FROM public.periods
                WHERE period_type = :pt AND period_key = :pk
                """
            ),
            {"pt": period_type, "pk": period_key},
        ).mappings().first()
        if row and row.get("period_id"):
            return int(row["period_id"])

        created = conn.execute(
            text(
                """
                INSERT INTO public.periods (period_type, period_key)
                VALUES (:pt, :pk)
                RETURNING period_id
                """
            ),
            {"pt": period_type, "pk": period_key},
        ).scalar_one()
        return int(created)

    return int(FALLBACK_PERIOD_ID)


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
    """
    Пишем подробный журнал по шаблону в рамках запуска.
    Никогда не валим весь ран из-за проблем логирования.
    """
    try:
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
        # intentionally swallow
        return


def run_regular_tasks_generation_tx(
    conn: Connection,
    *,
    run_at_local: Optional[datetime] = None,
    dry_run: bool = False,
) -> Tuple[int, RunStats]:
    """
    Запуск генерации (в текущей транзакции).
    Возвращает (run_id, stats).
    """
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

        # Базовый meta для журнала
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
            base_meta.update(
                {
                    "schedule_type": schedule_type,
                    "schedule_params": schedule_params,
                    "create_offset_days": int(create_offset_days),
                    "due_offset_days": int(_safe_int(t.get("due_offset_days")) or 0),
                }
            )

            # Валидация расписания. Если конфиг битый — фиксируем ошибку, но не падаем.
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

            # Если "пора создавать", то требуем executor_role_id
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

            period_id = _period_resolve(conn, schedule_type=schedule_type, for_date=now_local.date())

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

            row = conn.execute(
                text(
                    """
                    INSERT INTO public.tasks (
                        period_id, regular_task_id,
                        title, description,
                        initiator_user_id,
                        executor_role_id,
                        assignment_scope,
                        status_id
                    )
                    VALUES (
                        :period_id, :regular_task_id,
                        :title, :description,
                        :initiator_user_id,
                        :executor_role_id,
                        :assignment_scope,
                        (SELECT status_id FROM public.task_statuses WHERE code = 'IN_PROGRESS')
                    )
                    ON CONFLICT (regular_task_id, period_id, executor_role_id)
                    DO NOTHING
                    RETURNING task_id
                    """
                ),
                {
                    "period_id": int(period_id),
                    "regular_task_id": int(rid),
                    "title": str(t.get("title") or "").strip() or f"Regular task #{rid}",
                    "description": t.get("description"),
                    "initiator_user_id": int(SYSTEM_USER_ID),
                    "executor_role_id": int(executor_role_id),
                    "assignment_scope": str(t.get("assignment_scope") or "functional"),
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
                    meta={**base_meta, "task_id": int(row["task_id"]), "deduped": False},
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
                    meta={**base_meta, "task_id": None, "deduped": True},
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
                is_due=True,  # мы в блоке due/создания; если исключение раньше — не критично
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
