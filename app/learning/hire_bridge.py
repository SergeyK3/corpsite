"""Training hire form backed by the same isolated PostgreSQL database as attempts."""
from __future__ import annotations

import hashlib
import os
from datetime import date, timedelta
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.personnel_applications.application.electronic_hire_service import render_application
from app.personnel_applications.application.registration_service import register_personnel_application

HIRE_TITLE = "Создать электронное заявление о приёме на работу"
GUIDE_URL = "https://docs.google.com/document/d/1cFDLZHhb5pFaNYWXaKpdISJ3voR8KRpxLTBRKHMjN3Q/edit"
CRITERIA = [
    "Заявление сохранено, его номер читается",
    "ФИО вымышленного кандидата совпадает с заданием",
    "Отделение и должность указаны верно",
    "Ставка и дата начала работы совпадают с заданием",
    "На снимке видно, что выбран электронный способ оформления",
]
SHOTS = [
    "Снимок 1: номер заявления и ФИО кандидата",
    "Снимок 2: отделение, должность, ставка, дата и электронный способ",
]

def is_hire_lesson(lesson: dict) -> bool:
    return lesson["title"] == HIRE_TITLE and lesson.get("target_role") == "Кадровик"


def fixture(attempt_id: str) -> dict:
    digits = int(hashlib.sha256(attempt_id.encode()).hexdigest()[:16], 16) % 10**11
    return {
        "iin": f"9{digits:011d}",
        "full_name": "Учебная Алия Нурлановна",
        "birth_date": "1992-04-17",
        "application_received_at": date.today().isoformat(),
        "planned_start_date": (date.today() + timedelta(days=14)).isoformat(),
        "org_unit_id": int(os.getenv("CORPSITE_TRAINING_UNIT_ID", "1796")),
        "position_id": int(os.getenv("CORPSITE_TRAINING_POSITION_ID", "25")),
        "employment_rate": "0.50",
        "application_source": "electronic",
        "idempotency_key": f"learning-hire-{attempt_id}",
    }


def create_application(conn: Connection, attempt_id: str, participant_id: int, expected: dict) -> dict:
    result = register_personnel_application(
        conn, iin_raw=expected["iin"], full_name=expected["full_name"],
        birth_date=date.fromisoformat(expected["birth_date"]),
        application_received_at=date.fromisoformat(expected["application_received_at"]),
        vacancy_check_status="pending", vacancy_checked_at=None,
        vacancy_checked_by_user_id=None, intended_org_group_id=None,
        intended_org_unit_id=expected["org_unit_id"],
        intended_position_id=expected["position_id"],
        intended_employment_rate=Decimal(expected["employment_rate"]),
        intended_vacancy_text=None, contact_mobile_phone=None, contact_email=None,
        hr_note=f"Учебная попытка {attempt_id}",
        idempotency_key=expected["idempotency_key"],
        registered_by_user_id=participant_id, actor_id=f"user:{participant_id}",
        application_source="electronic",
    )
    if result.action == "created":
        conn.execute(text("""
            INSERT INTO public.electronic_hire_applications(application_id, planned_start_date)
            VALUES (:id, :start)
        """), {"id": result.application_id,
               "start": date.fromisoformat(expected["planned_start_date"])})
    saved = application(result.application_id, attempt_id, conn=conn)
    if saved["iin"] != expected["iin"] or saved["full_name"] != expected["full_name"]:
        raise HTTPException(409, "Кадровая запись не совпала с учебной попыткой")
    return saved


def application(application_id: int, attempt_id: str, *, conn: Connection | None = None) -> dict:
    def read(active: Connection):
        return active.execute(text("""
            SELECT a.application_id, a.person_id, a.idempotency_key, a.application_source,
                   a.status, a.intended_org_unit_id, a.intended_position_id,
                   a.intended_employment_rate, a.application_received_at,
                   e.planned_start_date, p.full_name, p.iin, p.birth_date,
                   ou.name AS org_unit_name, pos.name AS position_name
            FROM public.personnel_applications a
            JOIN public.electronic_hire_applications e USING (application_id)
            JOIN public.persons p ON p.person_id=a.person_id
            LEFT JOIN public.org_units ou ON ou.unit_id=a.intended_org_unit_id
            LEFT JOIN public.positions pos ON pos.position_id=a.intended_position_id
            WHERE a.application_id=:application_id
        """), {"application_id": application_id}).mappings().first()
    if conn is None:
        with engine.connect() as active:
            row = read(active)
    else:
        row = read(conn)
    if row is None or row["idempotency_key"] != f"learning-hire-{attempt_id}" or row["application_source"] != "electronic":
        raise HTTPException(404, "Учебное заявление не найдено")
    data = dict(row)
    for key in ("application_received_at", "planned_start_date", "birth_date"):
        if data[key] is not None:
            data[key] = data[key].isoformat()
    data["intended_employment_rate"] = str(data["intended_employment_rate"])
    return data


def print_preview(application_id: int, attempt_id: str) -> dict:
    saved = application(application_id, attempt_id)
    try:
        with engine.connect() as conn:
            return render_application(conn, application_id)
    except Exception as exc:
        # The existing print template needs a Russian declension for some test
        # positions. The saved confirmation still has the canonical form data.
        if "POSITION_FORM_REQUIRED" not in str(exc):
            raise
        return {"preview_type": "saved_confirmation", "application_id": application_id,
                "status": saved["status"], "full_name": saved["full_name"],
                "org_unit_name": saved["org_unit_name"], "position_name": saved["position_name"],
                "employment_rate": saved["intended_employment_rate"],
                "planned_start_date": saved["planned_start_date"], "application_source": "electronic"}


def evaluate(application_id: int, attempt_id: str, expected: dict) -> tuple[list[bool], str]:
    saved = application(application_id, attempt_id)
    criteria = [
        bool(saved["application_id"] and saved["status"]),
        saved["full_name"] == expected["full_name"],
        saved["intended_org_unit_id"] == expected["org_unit_id"] and saved["intended_position_id"] == expected["position_id"],
        Decimal(saved["intended_employment_rate"]) == Decimal(expected["employment_rate"]) and saved["planned_start_date"] == expected["planned_start_date"],
        saved["application_source"] == "electronic",
    ]
    return criteria, f"Проверено сохранённое электронное заявление № {application_id} в учебной базе"
