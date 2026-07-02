# app/services/regular_task_scheduler_status.py
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.regular_tasks_service import (
    FORCE_DUE_ALL,
    FORCE_RUN_FOR_DATE,
    IGNORE_TIME_GATE_ENV,
    TZ_OFFSET_HOURS,
    _LOCAL_TZ,
    _prev_month_period_bounds,
    _prev_week_period_bounds_simple,
    _reporting_period_resolve,
    _target_date_for_template,
    resolve_catch_up_run_for_date,
    resolve_trigger_source,
)

SCHEDULER_OBSERVATION_WINDOW_DAYS = 8

SCHEDULER_HINT = (
    "Если автоматический запуск выключен или cron не настроен, "
    "новые регулярные задачи создаются только через догоняющий запуск."
)

STATUS_LABELS = {
    "working": "Включён — работает",
    "needs_attention": "Требует внимания",
    "no_data": "Выключен — нет автоматических запусков",
}

SCHEDULE_TYPE_TITLES = {
    "weekly": "Weekly",
    "monthly": "Monthly",
    "yearly": "Yearly",
}

DEFAULT_CRON_INTERVAL = timedelta(days=1)


def _isoformat_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    iso = getattr(value, "isoformat", None)
    if callable(iso):
        return iso()
    return str(value)


def _parse_stats(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return {}


def _parse_errors(raw: Any) -> List[Any]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return list(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            return [raw]
    return [raw]


def is_automatic_live_run(stats: Dict[str, Any]) -> bool:
    if stats.get("dry_run") is True:
        return False
    run_kind = str(stats.get("run_kind") or "").strip().lower()
    if run_kind in {"catch_up", "preview"}:
        return False
    if stats.get("catch_up"):
        return False
    trigger = resolve_trigger_source(
        dry_run=bool(stats.get("dry_run")),
        catch_up_meta=stats.get("catch_up") if isinstance(stats.get("catch_up"), dict) else None,
        trigger_source_hint=str(stats.get("trigger_source") or ""),
    )
    return trigger == "automatic"


def _automatic_run_has_issues(run: Dict[str, Any]) -> bool:
    status = str(run.get("status") or "").strip().lower()
    stats = _parse_stats(run.get("stats"))
    errors = int(stats.get("errors") or 0)
    return status == "partial" or errors > 0


def _is_successful_automatic_run(run: Dict[str, Any]) -> bool:
    status = str(run.get("status") or "").strip().lower()
    stats = _parse_stats(run.get("stats"))
    errors = int(stats.get("errors") or 0)
    return status == "ok" and errors == 0


def _resolve_last_error(run: Dict[str, Any]) -> Optional[str]:
    stats = _parse_stats(run.get("stats"))
    journal_warning = str(stats.get("journal_warning") or "").strip()
    errors_raw = _parse_errors(run.get("errors"))
    parts: List[str] = []
    if journal_warning:
        parts.append(journal_warning)
    for err in errors_raw:
        if isinstance(err, dict):
            msg = str(err.get("error") or err.get("message") or err.get("detail") or "").strip()
            if msg:
                parts.append(msg)
                continue
        s = str(err).strip()
        if s:
            parts.append(s)
    if not parts and _automatic_run_has_issues(run):
        return "Запуск завершился с ошибками или частично"
    return " · ".join(parts) if parts else None


def _resolve_result_label(run: Dict[str, Any]) -> str:
    if _automatic_run_has_issues(run):
        status = str(run.get("status") or "").strip().lower()
        stats = _parse_stats(run.get("stats"))
        if status == "partial":
            return "Частично"
        if int(stats.get("errors") or 0) > 0:
            return "С ошибками"
    status = str(run.get("status") or "").strip().lower()
    if status == "ok":
        return "Успешно"
    if status == "partial":
        return "Частично"
    return status or "—"


def _within_observation_window(started_at: Any, now: datetime, window_days: int) -> bool:
    started_iso = _isoformat_or_none(started_at)
    if not started_iso:
        return False
    try:
        started = datetime.fromisoformat(started_iso.replace("Z", "+00:00"))
    except ValueError:
        return False
    if started.tzinfo is None:
        started = started.replace(tzinfo=_LOCAL_TZ)
    now_aware = now if now.tzinfo else now.replace(tzinfo=_LOCAL_TZ)
    return (now_aware - started) <= timedelta(days=window_days)


def _load_recent_runs(conn: Connection, *, limit: int = 200) -> List[Dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT run_id, started_at, finished_at, status, stats, errors
            FROM public.regular_task_runs
            ORDER BY run_id DESC
            LIMIT :limit
            """
        ),
        {"limit": int(limit)},
    ).mappings().all()
    return [dict(r) for r in rows]


def _compute_status(
    automatic_runs: List[Dict[str, Any]],
    *,
    now: datetime,
    observation_window_days: int,
) -> Tuple[str, bool]:
    if not automatic_runs:
        return "no_data", False

    last_run = automatic_runs[0]
    last_success = next((r for r in automatic_runs if _is_successful_automatic_run(r)), None)

    if _automatic_run_has_issues(last_run):
        return "needs_attention", False

    if last_success and _within_observation_window(
        last_success.get("started_at"), now, observation_window_days
    ):
        return "working", True

    return "needs_attention", False


def _parse_datetime(value: Any) -> Optional[datetime]:
    iso = _isoformat_or_none(value)
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_LOCAL_TZ)
    return dt


def _format_datetime_ru(dt: datetime) -> str:
    return dt.astimezone(_LOCAL_TZ).strftime("%d.%m.%Y %H:%M")


def _format_date_ru(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def _days_between(start: date, end: date) -> int:
    return max(0, (end - start).days)


def _infer_cron_interval(automatic_runs: List[Dict[str, Any]]) -> timedelta:
    if len(automatic_runs) < 2:
        return DEFAULT_CRON_INTERVAL

    parsed: List[datetime] = []
    for run in automatic_runs:
        dt = _parse_datetime(run.get("started_at"))
        if dt is not None:
            parsed.append(dt)
    parsed.sort(reverse=True)

    diffs: List[timedelta] = []
    for idx in range(len(parsed) - 1):
        delta = parsed[idx] - parsed[idx + 1]
        if timedelta(hours=1) <= delta <= timedelta(days=14):
            diffs.append(delta)

    if not diffs:
        return DEFAULT_CRON_INTERVAL

    diffs.sort()
    return diffs[len(diffs) // 2]


def _compute_cron_run_expectation(
    automatic_runs: List[Dict[str, Any]],
    *,
    now: datetime,
) -> Dict[str, Any]:
    if not automatic_runs:
        return {
            "expected_next_run_at": None,
            "expected_next_run_label": None,
            "is_overdue": False,
            "overdue_days": 0,
            "cron_interval_days": int(DEFAULT_CRON_INTERVAL.total_seconds() // 86400),
        }

    last_started = _parse_datetime(automatic_runs[0].get("started_at"))
    if last_started is None:
        return {
            "expected_next_run_at": None,
            "expected_next_run_label": None,
            "is_overdue": False,
            "overdue_days": 0,
            "cron_interval_days": int(DEFAULT_CRON_INTERVAL.total_seconds() // 86400),
        }

    interval = _infer_cron_interval(automatic_runs)
    expected = last_started + interval
    now_aware = now if now.tzinfo else now.replace(tzinfo=_LOCAL_TZ)
    is_overdue = now_aware > expected
    overdue_days = _days_between(expected.date(), now_aware.date()) if is_overdue else 0

    return {
        "expected_next_run_at": expected.isoformat(),
        "expected_next_run_label": _format_datetime_ru(expected),
        "is_overdue": is_overdue,
        "overdue_days": overdue_days,
        "cron_interval_days": max(1, int(interval.total_seconds() // 86400)),
    }


def _resolve_status_explanation(
    *,
    status: str,
    automatic_runs: List[Dict[str, Any]],
    last_run: Optional[Dict[str, Any]],
    last_success: Optional[Dict[str, Any]],
    now: datetime,
    observation_window_days: int,
    last_error: Optional[str],
) -> str:
    if status == "working":
        success_at = _parse_datetime(last_success.get("started_at") if last_success else None)
        if success_at:
            return (
                f"Автоматический cron обращался к системе недавно: "
                f"последний успешный запуск {_format_datetime_ru(success_at)}."
            )
        return "Автоматический cron работает в пределах окна наблюдения."

    if status == "no_data":
        return (
            "Автоматический scheduler ни разу не обращался к системе — "
            "в журнале нет live-запусков с trigger_source=automatic."
        )

    if last_run and _automatic_run_has_issues(last_run):
        result = _resolve_result_label(last_run)
        detail = last_error or result
        return f"Последний автоматический запуск завершился с проблемами: {detail}."

    reference = last_success or last_run
    reference_at = _parse_datetime(reference.get("started_at") if reference else None)
    if reference_at is None:
        return "Автоматический scheduler давно не обращался к системе."

    days_since = _days_between(reference_at.date(), now.date())
    reference_label = _format_datetime_ru(reference_at)

    if last_run and _is_successful_automatic_run(last_run):
        return (
            f"Последний запуск был успешным ({reference_label}), "
            f"но с тех пор прошло {days_since} дн. — "
            f"новых автоматических запусков не было (окно наблюдения: {observation_window_days} дн.)."
        )

    return (
        f"Последний автоматический запуск был {reference_label}. "
        f"С тех пор прошло {days_since} дн."
    )


def _resolve_recommended_action(
    *,
    status: str,
    automatic_enabled: bool,
    period_diagnostics: List[Dict[str, Any]],
    last_error: Optional[str],
    last_run: Optional[Dict[str, Any]],
) -> Dict[str, Optional[str]]:
    missing_periods = [p for p in period_diagnostics if not p.get("has_tasks")]

    if last_error and last_run:
        run_id = int(last_run.get("run_id") or 0)
        href = f"/regular-task-runs?run_id={run_id}" if run_id > 0 else "/regular-task-runs"
        return {
            "label": "Проверить журнал последнего запуска",
            "href": href,
            "kind": "journal",
        }

    if status == "no_data" or not automatic_enabled or missing_periods:
        return {
            "label": "Создать пропущенные задачи через догоняющий запуск",
            "href": "/admin/regular-tasks/catch-up",
            "kind": "catch_up",
        }

    return {
        "label": "Действий не требуется",
        "href": None,
        "kind": "none",
    }


def _build_primary_reason(
    *,
    has_tasks: bool,
    run_for_date: date,
    schedule_type: str,
    last_automatic_run_at: Optional[str],
    had_automatic_run_for_period: bool,
    last_item: Optional[Dict[str, Any]],
    active_templates: int,
) -> Optional[str]:
    if has_tasks:
        return None

    last_auto = _parse_datetime(last_automatic_run_at)
    if last_auto is None:
        return "Автоматический scheduler ни разу не обращался к системе."

    last_auto_date = last_auto.date()
    expected_label = _format_date_ru(run_for_date)

    if run_for_date > last_auto_date or not had_automatic_run_for_period:
        if schedule_type == "monthly":
            return f"Не было автоматического запуска {expected_label}."
        return f"После {_format_date_ru(last_auto_date)} автоматический запуск не выполнялся."

    if active_templates <= 0:
        return "Нет активных шаблонов с этой периодичностью."

    if last_item:
        meta = last_item.get("meta")
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        if not isinstance(meta, dict):
            meta = {}
        if last_item.get("is_due") is False:
            return "Шаблон не был due в момент запуска (дата, смещение или время)."
        dedupe_mode = str(meta.get("dedupe_mode") or "").strip()
        if dedupe_mode:
            return f"Задача не создана: дедупликация ({dedupe_mode})."
        err = str(last_item.get("error") or "").strip()
        if err:
            return err

    return "Причина не зафиксирована в журнале — проверьте шаблон и догоняющий запуск."

def _format_period_label(*, schedule_type: str, d0: date, d1: date) -> str:
    st = (schedule_type or "").strip().lower()
    if st == "weekly":
        return f"{d0.strftime('%d.%m.%Y')}–{d1.strftime('%d.%m.%Y')}"
    if st == "monthly":
        return d0.strftime("%m.%Y")
    return f"{d0.isoformat()}..{d1.isoformat()}"


def _count_active_templates(conn: Connection, *, schedule_type: str) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(1)
                FROM public.regular_tasks rt
                WHERE COALESCE(rt.is_active, FALSE) = TRUE
                  AND rt.archived_at IS NULL
                  AND lower(trim(rt.schedule_type)) = :schedule_type
                """
            ),
            {"schedule_type": schedule_type.strip().lower()},
        ).scalar()
        or 0
    )


def _count_tasks_for_period(conn: Connection, *, period_id: int) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(1)
                FROM public.tasks t
                WHERE t.period_id = :period_id
                  AND t.regular_task_id IS NOT NULL
                """
            ),
            {"period_id": int(period_id)},
        ).scalar()
        or 0
    )


def _last_run_item_for_period(
    conn: Connection, *, period_id: int, schedule_type: str
) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT
                i.item_id,
                i.run_id,
                i.status,
                i.is_due,
                i.created_tasks,
                i.error,
                i.meta,
                r.started_at,
                r.stats AS run_stats
            FROM public.regular_task_run_items i
            JOIN public.regular_task_runs r ON r.run_id = i.run_id
            JOIN public.regular_tasks rt ON rt.regular_task_id = i.regular_task_id
            WHERE i.period_id = :period_id
              AND lower(trim(rt.schedule_type)) = :schedule_type
            ORDER BY i.item_id DESC
            LIMIT 1
            """
        ),
        {"period_id": int(period_id), "schedule_type": schedule_type.strip().lower()},
    ).mappings().first()
    return dict(row) if row else None


def _likely_reasons_for_missing_tasks(
    *,
    automatic_enabled: bool,
    active_templates: int,
    last_item: Optional[Dict[str, Any]],
    had_automatic_run_for_period: bool,
) -> List[str]:
    reasons: List[str] = []
    if active_templates <= 0:
        reasons.append("Нет активных шаблонов с этой периодичностью")
    if not automatic_enabled:
        reasons.append("Автоматический cron не выполнялся в окне наблюдения")
    if not had_automatic_run_for_period:
        reasons.append("Автоматический запуск не обрабатывал этот отчётный период")
    if last_item:
        meta = last_item.get("meta")
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        if not isinstance(meta, dict):
            meta = {}
        if last_item.get("is_due") is False:
            reasons.append("Шаблон не был due в момент запуска (дата/смещение/время)")
        if int(last_item.get("created_tasks") or 0) == 0:
            dedupe_mode = str(meta.get("dedupe_mode") or "").strip()
            if dedupe_mode:
                reasons.append(f"Дедупликация: {dedupe_mode}")
            reason = str(meta.get("reason") or "").strip()
            if reason:
                reasons.append(reason)
        err = str(last_item.get("error") or "").strip()
        if err:
            reasons.append(err)
    if not reasons:
        reasons.append("Причина не зафиксирована в журнале — проверьте шаблон и догоняющий запуск")
    return reasons


def _period_diagnostic(
    conn: Connection,
    *,
    key: str,
    preset: str,
    schedule_type: str,
    today: date,
    automatic_enabled: bool,
    automatic_runs: List[Dict[str, Any]],
    last_automatic_run_at: Optional[str],
    run_for_date_override: Optional[date] = None,
) -> Dict[str, Any]:
    if run_for_date_override is not None:
        run_for_date = run_for_date_override
    else:
        run_for_date = resolve_catch_up_run_for_date(preset, today)
    period_id, d0, d1 = _reporting_period_resolve(
        conn, schedule_type=schedule_type, for_date=run_for_date
    )
    period_display = _format_period_label(schedule_type=schedule_type, d0=d0, d1=d1)
    title = SCHEDULE_TYPE_TITLES.get(schedule_type.strip().lower(), schedule_type)
    active_templates = _count_active_templates(conn, schedule_type=schedule_type)
    tasks_count = _count_tasks_for_period(conn, period_id=period_id)
    last_item = _last_run_item_for_period(conn, period_id=period_id, schedule_type=schedule_type)

    had_automatic = False
    for run in automatic_runs:
        stats = _parse_stats(run.get("stats"))
        occ = str(stats.get("occurrence_date") or "").strip()
        if occ == run_for_date.isoformat():
            had_automatic = True
            break
        started = _parse_datetime(run.get("started_at"))
        if started is not None and started.date() >= run_for_date:
            had_automatic = True
            break

    has_tasks = tasks_count > 0
    primary_reason = _build_primary_reason(
        has_tasks=has_tasks,
        run_for_date=run_for_date,
        schedule_type=schedule_type,
        last_automatic_run_at=last_automatic_run_at,
        had_automatic_run_for_period=had_automatic,
        last_item=last_item,
        active_templates=active_templates,
    )

    likely_reasons: List[str] = []
    if not has_tasks:
        if primary_reason:
            likely_reasons.append(primary_reason)
        likely_reasons.extend(
            _likely_reasons_for_missing_tasks(
                automatic_enabled=automatic_enabled,
                active_templates=active_templates,
                last_item=last_item,
                had_automatic_run_for_period=had_automatic,
            )
        )
        seen: set[str] = set()
        deduped: List[str] = []
        for reason in likely_reasons:
            if reason not in seen:
                seen.add(reason)
                deduped.append(reason)
        likely_reasons = deduped

    last_item_summary: Optional[Dict[str, Any]] = None
    if last_item:
        last_item_summary = {
            "run_id": int(last_item["run_id"]),
            "status": last_item.get("status"),
            "is_due": bool(last_item.get("is_due")),
            "created_tasks": int(last_item.get("created_tasks") or 0),
            "error": last_item.get("error"),
            "started_at": _isoformat_or_none(last_item.get("started_at")),
        }

    return {
        "key": key,
        "preset": preset,
        "schedule_type": schedule_type,
        "title": title,
        "label": period_display,
        "period_display": period_display,
        "run_for_date": run_for_date.isoformat(),
        "expected_run_date": run_for_date.isoformat(),
        "period_id": int(period_id),
        "period_start": d0.isoformat(),
        "period_end": d1.isoformat(),
        "active_templates_count": active_templates,
        "tasks_count": tasks_count,
        "has_tasks": has_tasks,
        "creation_status": "created" if has_tasks else "missing",
        "creation_status_label": "\u0441\u043e\u0437\u0434\u0430\u043d" if has_tasks else "\u043d\u0435 \u0441\u043e\u0437\u0434\u0430\u043d",
        "primary_reason": primary_reason,
        "last_run_item": last_item_summary,
        "likely_reasons": likely_reasons,
    }


def _next_template_due_hint(conn: Connection, *, today: date) -> Optional[str]:
    rows = conn.execute(
        text(
            """
            SELECT schedule_type, schedule_params, create_offset_days
            FROM public.regular_tasks
            WHERE COALESCE(is_active, FALSE) = TRUE
              AND archived_at IS NULL
            """
        )
    ).mappings().all()
    candidates: List[date] = []
    for row in rows:
        schedule_type = str(row.get("schedule_type") or "")
        params = row.get("schedule_params") or {}
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except json.JSONDecodeError:
                params = {}
        if not isinstance(params, dict):
            params = {}
        offset = int(row.get("create_offset_days") or 0)
        for day_offset in range(0, 60):
            probe = today + timedelta(days=day_offset)
            target = _target_date_for_template(probe, schedule_type, params)
            if target is None:
                continue
            create_day = target - timedelta(days=max(offset, 0))
            if create_day >= today:
                candidates.append(create_day)
                break
    if not candidates:
        return None
    next_day = min(candidates)
    return next_day.isoformat()


def _read_config_snapshot() -> Dict[str, Any]:
    cron_user_id = (os.getenv("REGULAR_TASKS_CRON_USER_ID") or "").strip()
    internal_token_set = bool((os.getenv("INTERNAL_API_TOKEN") or "").strip())
    return {
        "has_master_disable_flag": False,
        "cron_endpoint": "POST /internal/regular-tasks/run",
        "cron_auth": "X-Internal-Api-Token + X-User-Id (system admin)",
        "cron_user_id_hint": cron_user_id or None,
        "internal_api_token_configured": internal_token_set,
        "regular_tasks_system_user_id": int(os.getenv("REGULAR_TASKS_SYSTEM_USER_ID") or "1"),
        "tz_offset_hours": TZ_OFFSET_HOURS,
        "force_run_for_date": FORCE_RUN_FOR_DATE.isoformat() if FORCE_RUN_FOR_DATE else None,
        "force_due_all": FORCE_DUE_ALL,
        "ignore_time_gate": IGNORE_TIME_GATE_ENV,
    }


def build_regular_task_scheduler_status(
    conn: Connection,
    *,
    now: Optional[datetime] = None,
    observation_window_days: int = SCHEDULER_OBSERVATION_WINDOW_DAYS,
) -> Dict[str, Any]:
    now_local = now or datetime.now(tz=_LOCAL_TZ)
    today = now_local.date()

    all_runs = _load_recent_runs(conn)
    automatic_runs = [
        r for r in all_runs if is_automatic_live_run(_parse_stats(r.get("stats")))
    ]

    status, automatic_enabled = _compute_status(
        automatic_runs,
        now=now_local,
        observation_window_days=observation_window_days,
    )

    last_run = automatic_runs[0] if automatic_runs else None
    last_success = next((r for r in automatic_runs if _is_successful_automatic_run(r)), None)

    last_error: Optional[str] = None
    if last_run and _automatic_run_has_issues(last_run):
        last_error = _resolve_last_error(last_run)

    last_automatic_run_at = _isoformat_or_none(last_run.get("started_at")) if last_run else None

    cron_expectation = _compute_cron_run_expectation(automatic_runs, now=now_local)
    next_template_due_at = _next_template_due_hint(conn, today=today)

    status_explanation = _resolve_status_explanation(
        status=status,
        automatic_runs=automatic_runs,
        last_run=last_run,
        last_success=last_success,
        now=now_local,
        observation_window_days=observation_window_days,
        last_error=last_error,
    )

    period_diagnostics = [
        _period_diagnostic(
            conn,
            key="past_week",
            preset="past_week",
            schedule_type="weekly",
            today=today,
            automatic_enabled=automatic_enabled,
            automatic_runs=automatic_runs,
            last_automatic_run_at=last_automatic_run_at,
        ),
        _period_diagnostic(
            conn,
            key="monthly_reporting",
            preset="manual",
            schedule_type="monthly",
            today=today,
            automatic_enabled=automatic_enabled,
            automatic_runs=automatic_runs,
            last_automatic_run_at=last_automatic_run_at,
            run_for_date_override=today.replace(day=1),
        ),
    ]

    recommended = _resolve_recommended_action(
        status=status,
        automatic_enabled=automatic_enabled,
        period_diagnostics=period_diagnostics,
        last_error=last_error,
        last_run=last_run,
    )

    return {
        "automatic_enabled": automatic_enabled,
        "status": status,
        "status_label": STATUS_LABELS.get(status, status),
        "status_explanation": status_explanation,
        "observation_window_days": observation_window_days,
        "last_run_at": last_automatic_run_at,
        "last_run_status": last_run.get("status") if last_run else None,
        "last_successful_run_at": _isoformat_or_none(last_success.get("started_at"))
        if last_success
        else None,
        "last_result_label": _resolve_result_label(last_run) if last_run else "—",
        "last_error": last_error,
        "expected_next_run_at": cron_expectation.get("expected_next_run_at"),
        "expected_next_run_label": cron_expectation.get("expected_next_run_label"),
        "is_cron_overdue": bool(cron_expectation.get("is_overdue")),
        "cron_overdue_days": int(cron_expectation.get("overdue_days") or 0),
        "cron_interval_days": int(cron_expectation.get("cron_interval_days") or 1),
        "next_template_due_at": next_template_due_at,
        "next_expected_run_at": cron_expectation.get("expected_next_run_at"),
        "next_expected_run_label": cron_expectation.get("expected_next_run_label"),
        "hint": SCHEDULER_HINT,
        "recommended_action": recommended,
        "config": _read_config_snapshot(),
        "period_diagnostics": period_diagnostics,
        "checked_at": now_local.isoformat(),
        "automatic_runs_in_journal": len(automatic_runs),
    }
