# tests/test_regular_task_scheduler_status.py
from __future__ import annotations

from datetime import date, datetime, timezone, timedelta

import pytest

from app.services.regular_task_scheduler_status import (
    SCHEDULER_OBSERVATION_WINDOW_DAYS,
    _compute_cron_run_expectation,
    _compute_status,
    _infer_cron_interval,
    _likely_reasons_for_missing_tasks,
    _resolve_status_explanation,
    is_automatic_live_run,
)


def test_is_automatic_live_run_excludes_catch_up_and_dry_run():
    assert is_automatic_live_run({"run_kind": "automatic", "dry_run": False, "trigger_source": "automatic"})
    assert not is_automatic_live_run({"run_kind": "catch_up", "dry_run": False})
    assert not is_automatic_live_run({"run_kind": "automatic", "dry_run": True})
    assert not is_automatic_live_run({"trigger_source": "manual", "dry_run": False})


def test_compute_status_working_for_recent_success():
    now = datetime(2026, 6, 25, 12, 0, tzinfo=timezone(timedelta(hours=5)))
    runs = [
        {
            "run_id": 1,
            "started_at": "2026-06-25T10:00:00+05:00",
            "status": "ok",
            "stats": {"run_kind": "automatic", "dry_run": False, "errors": 0, "trigger_source": "automatic"},
        }
    ]
    status, enabled = _compute_status(runs, now=now, observation_window_days=SCHEDULER_OBSERVATION_WINDOW_DAYS)
    assert status == "working"
    assert enabled is True


def test_compute_status_no_data_without_automatic_runs():
    now = datetime(2026, 6, 25, 12, 0, tzinfo=timezone(timedelta(hours=5)))
    status, enabled = _compute_status([], now=now, observation_window_days=SCHEDULER_OBSERVATION_WINDOW_DAYS)
    assert status == "no_data"
    assert enabled is False


def test_compute_status_needs_attention_when_stale():
    now = datetime(2026, 6, 25, 12, 0, tzinfo=timezone(timedelta(hours=5)))
    stale = (now - timedelta(days=SCHEDULER_OBSERVATION_WINDOW_DAYS + 2)).isoformat()
    runs = [
        {
            "run_id": 2,
            "started_at": stale,
            "status": "ok",
            "stats": {"run_kind": "automatic", "dry_run": False, "errors": 0, "trigger_source": "automatic"},
        }
    ]
    status, enabled = _compute_status(runs, now=now, observation_window_days=SCHEDULER_OBSERVATION_WINDOW_DAYS)
    assert status == "needs_attention"
    assert enabled is False


def test_likely_reasons_when_scheduler_disabled():
    reasons = _likely_reasons_for_missing_tasks(
        automatic_enabled=False,
        active_templates=2,
        last_item=None,
        had_automatic_run_for_period=False,
    )
    assert any("cron" in r.lower() for r in reasons)


def test_weekly_period_bounds_for_june_24_30():
    from app.services.regular_tasks_service import _prev_week_period_bounds_simple

    d0, d1 = _prev_week_period_bounds_simple(date(2026, 7, 1))
    assert d0 == date(2026, 6, 24)
    assert d1 == date(2026, 6, 30)


def test_monthly_period_bounds_for_june_2026():
    from app.services.regular_tasks_service import _prev_month_period_bounds

    d0, d1 = _prev_month_period_bounds(date(2026, 7, 15))
    assert d0 == date(2026, 6, 1)
    assert d1 == date(2026, 6, 30)


def test_status_explanation_for_stale_successful_run():
    now = datetime(2026, 7, 2, 12, 0, tzinfo=timezone(timedelta(hours=5)))
    stale = "2026-06-22T07:41:00+05:00"
    runs = [
        {
            "run_id": 2,
            "started_at": stale,
            "status": "ok",
            "stats": {"run_kind": "automatic", "dry_run": False, "errors": 0, "trigger_source": "automatic"},
        }
    ]
    explanation = _resolve_status_explanation(
        status="needs_attention",
        automatic_runs=runs,
        last_run=runs[0],
        last_success=runs[0],
        now=now,
        observation_window_days=SCHEDULER_OBSERVATION_WINDOW_DAYS,
        last_error=None,
    )
    assert "успешным" in explanation.lower()
    assert "22.06.2026" in explanation


def test_cron_expectation_overdue_from_journal():
    now = datetime(2026, 7, 2, 12, 0, tzinfo=timezone(timedelta(hours=5)))
    runs = [
        {
            "run_id": 1,
            "started_at": "2026-06-22T07:41:00+05:00",
            "status": "ok",
            "stats": {"trigger_source": "automatic"},
        }
    ]
    result = _compute_cron_run_expectation(runs, now=now)
    assert result["is_overdue"] is True
    assert result["overdue_days"] >= 9
    assert "23.06.2026" in result["expected_next_run_label"]


def test_infer_cron_interval_defaults_to_one_day():
    runs = [{"started_at": "2026-06-25T10:00:00+05:00"}]
    assert _infer_cron_interval(runs) == timedelta(days=1)
