"""Read-only qualification categories report from the same profile as the PPR card."""
from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text

from app.personnel_intake.domain.additional_profile import merge_additional_profiles
from app.ppr.read.additional_reader import _json_dict


STATUS_LABELS = {
    "ACTIVE": "Действует",
    "EXPIRING_SOON": "Скоро истекает",
    "EXPIRED": "Истекла",
    "NO_EXPIRY": "Срок не указан",
    "NO_CATEGORY": "Категория не внесена",
}
CATEGORY_LABELS = {"highest": "Высшая", "first": "Первая", "second": "Вторая"}


def local_today() -> date:
    """Use the same organization timezone default as other Corpsite projections."""
    try:
        zone = ZoneInfo(os.getenv("ORGANIZATION_TIMEZONE") or "Asia/Almaty")
    except ZoneInfoNotFoundError:
        zone = ZoneInfo("Asia/Almaty")
    return datetime.now(zone).date()


def category_status(valid_until: str | None, today: date) -> tuple[str, str | None]:
    if not valid_until:
        return "NO_EXPIRY", None
    try:
        expiry = date.fromisoformat(valid_until)
    except ValueError:
        return "NO_EXPIRY", None
    days_left = (expiry - today).days
    if days_left < 0:
        return "EXPIRED", expiry.isoformat()
    if days_left <= 30:
        return "EXPIRING_SOON", expiry.isoformat()
    return "ACTIVE", expiry.isoformat()


def build_personnel_qualification_categories_report(db_engine: Any, *, today: date | None = None) -> dict[str, Any]:
    today = today or local_today()
    statement = text("""
        SELECT e.employee_id, e.person_id,
               COALESCE(NULLIF(BTRIM(p.full_name), ''), NULLIF(BTRIM(e.full_name), '')) AS full_name,
               ou.unit_id AS org_unit_id, ou.name AS org_unit_name,
               prm.additional_profile AS metadata_profile,
               intake.additional_profile AS intake_profile
        FROM public.employees e
        LEFT JOIN public.persons p ON p.person_id = e.person_id
        LEFT JOIN LATERAL (
            SELECT pa.org_unit_id FROM public.person_assignments pa
            WHERE pa.person_id = e.person_id AND pa.active_flag IS TRUE
              AND pa.is_primary IS TRUE AND pa.lifecycle_status = 'active'
              AND pa.start_date <= :today
              AND (pa.end_date IS NULL OR pa.end_date >= :today)
            ORDER BY pa.start_date DESC, pa.assignment_id DESC LIMIT 1
        ) current_assignment ON TRUE
        LEFT JOIN public.org_units ou
          ON ou.unit_id = COALESCE(current_assignment.org_unit_id, e.org_unit_id)
        LEFT JOIN public.personnel_record_metadata prm ON prm.person_id = e.person_id
        LEFT JOIN LATERAL (
            SELECT d.payload->'additional' AS additional_profile
            FROM public.personnel_intake_drafts d
            JOIN public.personnel_applications a ON a.application_id = d.application_id
            WHERE a.person_id = e.person_id
            ORDER BY d.updated_at DESC LIMIT 1
        ) intake ON TRUE
        WHERE COALESCE(e.is_active, FALSE) IS TRUE
          AND e.operational_status = 'active'
          AND COALESCE(e.date_from, :today) <= :today
          AND (e.date_to IS NULL OR e.date_to >= :today)
          AND COALESCE(p.person_status, 'active') = 'active'
        ORDER BY LOWER(COALESCE(p.full_name, e.full_name)), e.employee_id
    """)
    employees: list[dict[str, Any]] = []
    with db_engine.connect() as conn:
        rows = conn.execute(statement, {"today": today}).mappings().all()
        for row in rows:
            person_id = row["person_id"]
            metadata = _json_dict(row["metadata_profile"]) if person_id is not None else None
            intake = _json_dict(row["intake_profile"]) if person_id is not None else None
            # The card's import fallback contains awards/degrees only, never
            # qualification categories. Its category list is always empty.
            profile = merge_additional_profiles(metadata, intake)
            categories = []
            for item in profile.get("qualification_categories") or []:
                if not isinstance(item, dict) or not item.get("category"):
                    continue
                code, expiry = category_status(str(item.get("valid_until") or ""), today)
                categories.append({
                    "specialty": str(item.get("specialty") or ""),
                    "category": str(item["category"]),
                    "category_label": CATEGORY_LABELS.get(str(item["category"]), str(item["category"])),
                    "valid_until": expiry,
                    "status": code,
                    "status_label": STATUS_LABELS[code],
                    "document_status": "Наличие файла не установлено",
                })
            if not categories:
                categories = [{
                    "specialty": "", "category": "", "category_label": "—",
                    "valid_until": None, "status": "NO_CATEGORY",
                    "status_label": STATUS_LABELS["NO_CATEGORY"],
                    "document_status": "Наличие файла не установлено",
                }]
            employees.append({
                "employee_id": int(row["employee_id"]),
                "person_id": int(person_id) if person_id is not None else None,
                "full_name": str(row["full_name"] or ""),
                "org_unit_id": int(row["org_unit_id"]) if row["org_unit_id"] is not None else None,
                "org_unit_name": row["org_unit_name"],
                "categories": categories,
                "pending_categories": [],
            })
        pending_rows = conn.execute(text("""
            SELECT poi.employee_id,
                   poi.payload->'qualification_category'->>'name_ru' AS name_ru,
                   poi.payload->'qualification_category'->>'code' AS category_code,
                   poi.payload->'qualification_category'->>'category' AS legacy_category
            FROM public.personnel_order_items poi
            JOIN public.personnel_orders po ON po.order_id = poi.order_id
            WHERE poi.item_type_code = 'QUALIFICATION_CATEGORY'
              AND poi.item_status = 'ACTIVE'
              AND poi.employee_id IS NOT NULL
              AND po.status IN ('DRAFT', 'READY_FOR_SIGNATURE')
              AND po.deleted_at IS NULL AND po.archived_at IS NULL
            ORDER BY poi.employee_id, po.order_id DESC, poi.item_number
        """)).mappings().all()
        by_id = {employee["employee_id"]: employee for employee in employees}
        for pending in pending_rows:
            employee = by_id.get(int(pending["employee_id"]))
            if employee is None:
                continue
            code = str(pending["category_code"] or "")
            legacy = str(pending["legacy_category"] or "")
            label = (str(pending["name_ru"] or "").strip() if code in {"2", "3", "4"} else "") or CATEGORY_LABELS.get(legacy)
            if label and label not in employee["pending_categories"]:
                employee["pending_categories"].append(label)
    return {"report_code": "personnel_qualification_categories", "as_of_date": today.isoformat(), "employees": employees}
