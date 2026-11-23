"""Read the HR records connected to a participant's first hire lesson attempt."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.engine import Connection

from app.learning import hire_bridge, service
from app.learning.model import hire_applications
from app.personnel_applications.application.electronic_hire_service import (
    load_electronic_hire,
    missing_card_fields,
)
from app.personnel_intake.infrastructure.repository import SqlAlchemyPersonnelIntakeRepository


def linked_records(conn: Connection, user: dict, attempt_id: str) -> dict:
    attempt = service.owned_attempt(conn, user, attempt_id)
    if not hire_bridge.is_hire_lesson(service.lesson_for_attempt(conn, attempt)):
        raise HTTPException(404, "Учебное заявление не найдено")
    link = conn.execute(select(hire_applications).where(
        hire_applications.c.attempt_id == attempt_id
    )).mappings().first()
    if link is None:
        raise HTTPException(404, "Учебное заявление ещё не сохранено")

    application_id = int(link["application_id"])
    saved = hire_bridge.application(application_id, attempt_id, conn=conn)
    application = load_electronic_hire(conn, application_id)
    person_id = int(link["person_id"])
    if person_id != int(saved["person_id"]) or person_id != int(application["person_id"]):
        raise HTTPException(409, "Нарушена связь заявления с учебной попыткой")

    missing = missing_card_fields(conn, person_id, application_id)
    intake = SqlAlchemyPersonnelIntakeRepository(conn).load_intake_summary(application_id)
    order_id = application["personnel_order_id"]
    order = None
    if order_id is not None:
        row = conn.execute(text("""
            SELECT order_id, status, order_number, order_date
            FROM public.personnel_orders
            WHERE order_id=:order_id AND deleted_at IS NULL
        """), {"order_id": int(order_id)}).mappings().first()
        if row is None:
            raise HTTPException(409, "Связанный проект приказа не найден")
        order = {"order_id": int(row["order_id"]), "status": row["status"],
                 "number": row["order_number"],
                 "date": row["order_date"].isoformat() if row["order_date"] else None}

    return {
        "source_attempt_id": attempt_id,
        "application_id": application_id,
        "application_status": application["status"],
        "person_id": person_id,
        "personal_card": {
            "complete": not missing,
            "missing_fields": missing,
            "candidate_checked_at": application["candidate_checked_at"].isoformat()
            if application["candidate_checked_at"] else None,
            "intake_link_status": intake.link_status if intake else None,
            "intake_draft_status": intake.draft_status if intake else None,
        },
        "order_draft": order,
    }
