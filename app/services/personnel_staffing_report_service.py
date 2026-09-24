"""Staffing report based on factual primary-assignment intervals and HR events."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.services.personnel_reports_service import _load_report_org_options, _select_report_departments


TURNOVER_CODES = {
    "VOLUNTARY": "Увольнение по собственному желанию",
    "DISCIPLINARY": "Увольнение за нарушение трудовой дисциплины",
}


def _overlap_days(start: date, end: date | None, date_from: date, date_to: date) -> list[date]:
    left, right = max(start, date_from), min(end or date_to, date_to)
    if right < left:
        return []
    return [left + timedelta(days=index) for index in range((right - left).days + 1)]


def _classify(code: Any) -> str | None:
    return TURNOVER_CODES.get(str(code or "").strip().upper())


def calculate_staffing_metrics(
    assignments: list[dict[str, Any]], *, date_from: date, date_to: date,
) -> tuple[int, float, dict[int, dict[str, float]], bool]:
    """Return snapshot, daily average and per-unit values without per-day DB requests."""
    daily: dict[date, dict[int, set[int]]] = defaultdict(lambda: defaultdict(set))
    end_snapshot: dict[int, set[int]] = defaultdict(set)
    incomplete = False
    for row in assignments:
        if row.get("person_id") is None or row.get("org_unit_id") is None or row.get("start_date") is None:
            incomplete = True
            continue
        person_id, unit_id = int(row["person_id"]), int(row["org_unit_id"])
        for day in _overlap_days(row["start_date"], row.get("end_date"), date_from, date_to):
            daily[day][unit_id].add(person_id)
        if row["start_date"] <= date_to and (row.get("end_date") is None or row["end_date"] >= date_to):
            end_snapshot[unit_id].add(person_id)
    period_days = (date_to - date_from).days + 1
    total_daily = [set().union(*(daily[day].values())) if daily[day] else set() for day in (date_from + timedelta(days=i) for i in range(period_days))]
    total_snapshot = len(set().union(*end_snapshot.values())) if end_snapshot else 0
    per_unit: dict[int, dict[str, float]] = {}
    for unit_id in set(end_snapshot) | {unit for by_unit in daily.values() for unit in by_unit}:
        per_unit[unit_id] = {
            "current_headcount": float(len(end_snapshot[unit_id])),
            "average_headcount": sum(len(daily[day][unit_id]) for day in daily) / period_days,
        }
    return total_snapshot, sum(map(len, total_daily)) / period_days, per_unit, incomplete


def build_staffing_report(engine: Engine, *, scope_unit_ids: list[int] | None, date_from: date, date_to: date, group_id: int | None = None, org_unit_id: int | None = None, breakdown: str = "total") -> dict[str, Any]:
    if date_to < date_from:
        raise ValueError("Дата по не может быть раньше даты с.")
    if breakdown not in {"total", "groups", "units"}:
        raise ValueError("Недопустимый разрез отчёта.")
    with engine.connect() as conn:
        options = _load_report_org_options(conn, scope_unit_ids=scope_unit_ids)
        departments, selected_group, selected_unit = _select_report_departments(options, group_id=group_id, org_unit_id=org_unit_id)
        unit_ids = [int(item["unit_id"]) for item in departments]
        rows = conn.execute(text("""
            SELECT pa.person_id, pa.org_unit_id, pa.start_date, pa.end_date,
                   e.employee_id, COALESCE(NULLIF(BTRIM(p.full_name), ''), NULLIF(BTRIM(e.full_name), '')) full_name
            FROM public.person_assignments pa
            JOIN public.persons p ON p.person_id=pa.person_id
            LEFT JOIN public.employees e ON e.person_id=pa.person_id
            WHERE pa.is_primary IS TRUE AND pa.lifecycle_status <> 'voided'
              AND pa.org_unit_id=ANY(:unit_ids) AND pa.start_date<=:date_to
              AND (pa.end_date IS NULL OR pa.end_date>=:date_from)
        """), {"unit_ids": unit_ids, "date_from": date_from, "date_to": date_to}).mappings().all() if unit_ids else []
        events = conn.execute(text("""
            SELECT ee.employee_id, ee.event_type, ee.effective_date, ee.to_org_unit_id, ee.from_org_unit_id,
                   ee.metadata, COALESCE(NULLIF(BTRIM(p.full_name), ''), NULLIF(BTRIM(e.full_name), '')) full_name
            FROM public.employee_events ee JOIN public.employees e ON e.employee_id=ee.employee_id
            LEFT JOIN public.persons p ON p.person_id=e.person_id
            WHERE ee.lifecycle_status='APPROVED' AND ee.event_type IN ('HIRE','TERMINATION')
              AND ee.effective_date BETWEEN :date_from AND :date_to
        """), {"date_from": date_from, "date_to": date_to}).mappings().all()
    assignment_rows = [dict(row) for row in rows]
    current, average, per_unit, incomplete = calculate_staffing_metrics(assignment_rows, date_from=date_from, date_to=date_to)
    unit_map = {int(item["unit_id"]): item for item in departments}
    hires, terminations = {}, {}
    for event in events:
        item = dict(event); unit_id = item.get("to_org_unit_id") if item["event_type"] == "HIRE" else item.get("from_org_unit_id")
        if unit_id not in unit_map: continue
        target = hires if item["event_type"] == "HIRE" else terminations
        target.setdefault(int(item["employee_id"]), item | {"org_unit_id": unit_id})
    turnover_counts = defaultdict(int)
    for item in terminations.values():
        metadata = item.get("metadata") or {}; code = metadata.get("termination_reason_code") if isinstance(metadata, dict) else None
        item["reason"] = _classify(code) or "Причина не классифицирована"; item["turnover"] = _classify(code) is not None
        if item["turnover"]: turnover_counts[item["reason"]] += 1
    def row_for(unit_id: int) -> dict[str, Any]:
        values = per_unit.get(unit_id, {"current_headcount": 0.0, "average_headcount": 0.0})
        hired = sum(1 for item in hires.values() if item["org_unit_id"] == unit_id); fired = sum(1 for item in terminations.values() if item["org_unit_id"] == unit_id)
        turnover = sum(1 for item in terminations.values() if item["org_unit_id"] == unit_id and item["turnover"])
        average_value = values["average_headcount"]
        return {"current_headcount": int(values["current_headcount"]), "average_headcount": round(average_value, 2), "hired": hired, "terminated": fired, "turnover_terminated": turnover, "turnover_percent": round(turnover / average_value * 100, 2) if average_value else 0}
    breakdown_rows = []
    if breakdown == "units":
        for unit_id, unit in unit_map.items(): breakdown_rows.append({"label": unit["unit_name"], "group_name": next(g["group_name"] for g in options["groups"] if g["group_id"] == unit["group_id"]), **row_for(unit_id)})
    elif breakdown == "groups":
        for group in options["groups"]:
            ids = [u["unit_id"] for u in departments if u["group_id"] == group["group_id"]]; values = [row_for(i) for i in ids]
            avg = sum(v["average_headcount"] for v in values); turnover = sum(v["turnover_terminated"] for v in values)
            breakdown_rows.append({"label": group["group_name"], "current_headcount": sum(v["current_headcount"] for v in values), "average_headcount": round(avg, 2), "hired": sum(v["hired"] for v in values), "terminated": sum(v["terminated"] for v in values), "turnover_terminated": turnover, "turnover_percent": round(turnover / avg * 100, 2) if avg else 0})
    turnover_total = sum(turnover_counts.values())
    def event_item(x: dict[str, Any]) -> dict[str, Any]:
        unit = unit_map[int(x["org_unit_id"])]
        group_name = next(g["group_name"] for g in options["groups"] if g["group_id"] == unit["group_id"])
        return {"full_name": x.get("full_name") or "Не указано", "date": x["effective_date"].isoformat(), "group_name": group_name, "unit_name": unit["unit_name"], **({"reason": x["reason"]} if "reason" in x else {})}
    return {"date_from": date_from.isoformat(), "date_to": date_to.isoformat(), "filters": {"group": selected_group, "department": selected_unit}, "data_quality": {"requires_review": incomplete, "message": "Данные требуют проверки: у части назначений отсутствует история." if incomplete else None}, "metrics": {"current_headcount": current, "hired": len(hires), "terminated": len(terminations), "average_headcount": round(average, 2), "average_formula": f"Сумма списочной численности за {(date_to-date_from).days+1} календарных дней / {(date_to-date_from).days+1}", "turnover_numerator": turnover_total, "turnover_percent": round(turnover_total / average * 100, 2) if average else 0, "turnover_reasons": [{"reason": label, "count": turnover_counts[label]} for label in TURNOVER_CODES.values()]}, "hired_items": [event_item(x) for x in hires.values()], "terminated_items": [event_item(x) for x in terminations.values()], "breakdown": breakdown_rows}
