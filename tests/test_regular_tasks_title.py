# tests/test_regular_tasks_title.py
from __future__ import annotations

from datetime import date

from app.services.regular_tasks_service import (
    _compose_task_title,
    _compute_base_title_from_template,
    _period_suffix_for_template,
)


def test_compose_task_title_monthly_without_role():
    base = _compute_base_title_from_template(
        report_code="MDG_MONTHLY",
        template_title="Ежемесячный отчет по протоколам МДГ",
    )
    suffix = _period_suffix_for_template("monthly", date(2025, 4, 1), date(2025, 4, 30))
    assert suffix == "04.2025"
    assert _compose_task_title(base_title=base, suffix=suffix) == (
        "Ежемесячный отчет по протоколам МДГ (04.2025)"
    )
    assert "→" not in _compose_task_title(base_title=base, suffix=suffix)


def test_compose_task_title_weekly_without_role():
    base = _compute_base_title_from_template(
        report_code="QM_WEEKLY",
        template_title="Пилот QM: еженедельный контроль",
    )
    suffix = _period_suffix_for_template("weekly", date(2026, 6, 17), date(2026, 6, 23))
    assert _compose_task_title(base_title=base, suffix=suffix) == (
        "Пилот QM: еженедельный контроль (17.06.2026–23.06.2026)"
    )


def test_compose_task_title_yearly_without_role():
    base = _compute_base_title_from_template(report_code="YEARLY", template_title="Годовой отчёт")
    suffix = _period_suffix_for_template("yearly", date(2025, 1, 1), date(2025, 12, 31))
    assert _compose_task_title(base_title=base, suffix=suffix) == "Годовой отчёт (2025)"


def test_compute_base_title_fallback_without_template_title():
    assert _compute_base_title_from_template(report_code="QM_WEEKLY", template_title="") == "QM_WEEKLY"
    assert _compute_base_title_from_template(report_code="", template_title="") == "Отчёт"


def test_compose_task_title_without_suffix():
    assert _compose_task_title(base_title="Отчёт", suffix="") == "Отчёт"
