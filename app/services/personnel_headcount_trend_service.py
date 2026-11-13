"""Year-to-date register headcount, with gaps where historical coverage is unverified."""
from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.services.personnel_type_headcount_report_service import build_personnel_type_headcount_report


def _current_cards(engine: Engine) -> dict[int, str]:
    """Read the same employee cards and merged-card exclusion as the register."""
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT e.employee_id, e.is_active
            FROM public.employees e
            WHERE (to_jsonb(e)->>'merged_into_employee_id') IS NULL
        """)).mappings()
        return {
            int(row["employee_id"]): "active" if row["is_active"] else "inactive"
            for row in rows
        }


def _historical_counts(
    cards: dict[int, str], events: list[dict[str, Any]], *, today: date, current_total: int,
) -> dict[int, int] | None:
    """Use events only when every current card has an unambiguous lifecycle."""
    if not cards or any(status not in {"active", "inactive"} for status in cards.values()):
        return None

    by_employee: dict[int, dict[str, list[date]]] = defaultdict(lambda: {"HIRE": [], "TERMINATION": []})
    for event in events:
        employee_id = int(event["employee_id"])
        event_type = str(event["event_type"])
        if employee_id in cards and event_type in {"HIRE", "TERMINATION"}:
            by_employee[employee_id][event_type].append(event["effective_date"])

    lifecycle: dict[int, tuple[date, date | None]] = {}
    for employee_id, status in cards.items():
        hires = by_employee[employee_id]["HIRE"]
        terminations = by_employee[employee_id]["TERMINATION"]
        if len(hires) != 1 or hires[0] > today:
            return None
        if status == "active" and terminations:
            return None
        if status == "inactive" and (len(terminations) != 1 or terminations[0] < hires[0] or terminations[0] > today):
            return None
        lifecycle[employee_id] = (hires[0], terminations[0] if terminations else None)

    active_today = sum(1 for start, end in lifecycle.values() if start <= today and (end is None or end >= today))
    if active_today != current_total:
        return None

    return {
        month: sum(
            1 for start, end in lifecycle.values()
            if start <= date(today.year, month, monthrange(today.year, month)[1])
            and (end is None or end >= date(today.year, month, monthrange(today.year, month)[1]))
        )
        for month in range(1, today.month)
    }


def build_personnel_headcount_trend(engine: Engine, *, today: date | None = None) -> dict[str, Any]:
    """Never infer a past month from current status or an incomplete snapshot."""
    with engine.connect() as conn:
        report_date = today or conn.execute(text("SELECT CURRENT_DATE")).scalar_one()

    current_total = int(build_personnel_type_headcount_report()["total"])
    cards = _current_cards(engine)
    with engine.connect() as conn:
        events = [dict(row) for row in conn.execute(text("""
            SELECT employee_id, event_type, effective_date
            FROM public.employee_events
            WHERE lifecycle_status = 'APPROVED'
              AND event_type IN ('HIRE', 'TERMINATION')
              AND effective_date <= :today
        """), {"today": report_date}).mappings()]

    past_counts = _historical_counts(cards, events, today=report_date, current_total=current_total)
    months = []
    for month in range(1, report_date.month + 1):
        is_current = month == report_date.month
        count = current_total if is_current else past_counts.get(month) if past_counts is not None else None
        months.append({
            "month": month,
            "date": report_date.isoformat() if is_current else date(report_date.year, month, monthrange(report_date.year, month)[1]).isoformat(),
            "count": count,
            "source": "active_register" if is_current else "approved_employee_events" if count is not None else None,
            "is_current": is_current,
        })

    return {
        "report_code": "personnel_headcount_trend",
        "year": report_date.year,
        "as_of": report_date.isoformat(),
        "months": months,
        "history_complete": past_counts is not None,
    }
