"""Physical HIRE deletion is atomic and cannot remove a signed order."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.personnel_applications.application.electronic_hire_delete_service import (
    ElectronicHireDeleteConflict,
    delete_electronic_hire,
    delete_preview,
)
from app.personnel_applications.application.hire_order_draft_service import create_hire_order_draft_for_application
from app.personnel_applications.application import hire_order_draft_service
from app.personnel_intake.application.intake_service import issue_intake_link, _resolve_link_by_token
from app.personnel_intake.domain.errors import PersonnelIntakeTokenError
from tests.personnel_applications.test_electronic_hire_postgres import _complete_card, _setup
from tests.ppr.conftest import insert_employee


def _ready_for_order(conn, application_id: int, person_id: int, actor_id: int) -> None:
    _complete_card(conn, person_id)
    conn.execute(text("""
        UPDATE public.electronic_hire_applications
        SET candidate_checked_at=now(), candidate_checked_by_user_id=:actor
        WHERE application_id=:application_id
    """), {"actor": actor_id, "application_id": application_id})
    conn.execute(text("""
        INSERT INTO public.personnel_intake_transfers
            (application_id, status, transferred_by_user_id, transferred_at,
             sections_transferred)
        VALUES (:application_id, 'completed', :actor, now(), '["general"]'::jsonb)
    """), {"application_id": application_id, "actor": actor_id})


def test_delete_application_without_order_and_its_public_link() -> None:
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            application, actor, _, _, _ = _setup(conn)
            application_id = application.application_id
            link = issue_intake_link(conn, application_id=application_id, issued_by_user_id=actor)
            assert delete_preview(conn, application_id)["can_delete"] is True
            assert delete_electronic_hire(conn, application_id)["deleted"] is True
            assert conn.execute(text("""
                SELECT count(*) FROM public.personnel_applications WHERE application_id=:id
            """), {"id": application_id}).scalar_one() == 0
            with pytest.raises(PersonnelIntakeTokenError):
                _resolve_link_by_token(conn, link.raw_token)
        finally:
            transaction.rollback()


def test_delete_application_and_numbered_draft_in_one_transaction(monkeypatch) -> None:
    monkeypatch.setattr(hire_order_draft_service, "queue_approval_notification", lambda *_args, **_kwargs: None)
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            application, actor, _, _, _ = _setup(conn)
            application_id = application.application_id
            _ready_for_order(conn, application_id, application.person_id, actor)
            order = create_hire_order_draft_for_application(
                conn, application_id=application_id, created_by_user_id=actor,
                employee_full_name_accusative_ru="Тестовую Айгуль",
            )
            order_id = order.personnel_order_id
            order_number = f"TEST-HIRE-{uuid4().hex[:8]}"
            conn.execute(text("""
                UPDATE public.personnel_orders SET order_number=:number WHERE order_id=:id
            """), {"number": order_number, "id": order_id})
            preview = delete_preview(conn, application_id)
            assert preview["can_delete"] is True
            assert preview["order_number"] == order_number
            assert delete_electronic_hire(conn, application_id)["deleted"] is True
            assert conn.execute(text("""
                SELECT count(*) FROM public.personnel_applications WHERE application_id=:id
            """), {"id": application_id}).scalar_one() == 0
            assert conn.execute(text("""
                SELECT count(*) FROM public.personnel_orders WHERE order_id=:id
            """), {"id": order_id}).scalar_one() == 0
        finally:
            transaction.rollback()


@pytest.mark.parametrize("status", ["SIGNED", "REGISTERED"])
def test_signed_and_registered_orders_protect_application(status: str, monkeypatch) -> None:
    monkeypatch.setattr(hire_order_draft_service, "queue_approval_notification", lambda *_args, **_kwargs: None)
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            application, actor, _, _, _ = _setup(conn)
            application_id = application.application_id
            _ready_for_order(conn, application_id, application.person_id, actor)
            order_id = create_hire_order_draft_for_application(
                conn, application_id=application_id, created_by_user_id=actor,
                employee_full_name_accusative_ru="Тестовую Айгуль",
            ).personnel_order_id
            conn.execute(text("""
                UPDATE public.personnel_orders SET status=:status WHERE order_id=:id
            """), {"status": status, "id": order_id})
            preview = delete_preview(conn, application_id)
            assert preview["can_delete"] is False
            assert status in preview["reason"]
            with pytest.raises(ElectronicHireDeleteConflict):
                delete_electronic_hire(conn, application_id)
            assert conn.execute(text("""
                SELECT count(*) FROM public.personnel_applications WHERE application_id=:id
            """), {"id": application_id}).scalar_one() == 1
            assert conn.execute(text("""
                SELECT count(*) FROM public.personnel_orders WHERE order_id=:id
            """), {"id": order_id}).scalar_one() == 1
        finally:
            transaction.rollback()


def test_conducted_order_event_protects_application_even_if_status_drifts(monkeypatch) -> None:
    monkeypatch.setattr(hire_order_draft_service, "queue_approval_notification", lambda *_args, **_kwargs: None)
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            application, actor, _, _, _ = _setup(conn)
            application_id = application.application_id
            _ready_for_order(conn, application_id, application.person_id, actor)
            order_id = create_hire_order_draft_for_application(
                conn, application_id=application_id, created_by_user_id=actor,
                employee_full_name_accusative_ru="Тестовую Айгуль",
            ).personnel_order_id
            employee_id = insert_employee(
                conn, full_name="Тестовая Айгуль", person_id=application.person_id, is_active=True,
            )
            conn.execute(text("""
                INSERT INTO public.employee_events
                    (employee_id, event_type, effective_date, order_id, order_ref, created_by)
                VALUES (:employee_id, 'HIRE', CURRENT_DATE, :order_id, :order_ref, :actor)
            """), {"employee_id": employee_id, "order_id": order_id,
                   "order_ref": f"TEST-HIRE-{uuid4().hex[:8]}", "actor": actor})
            preview = delete_preview(conn, application_id)
            assert preview["can_delete"] is False
            with pytest.raises(ElectronicHireDeleteConflict):
                delete_electronic_hire(conn, application_id)
            assert conn.execute(text("""
                SELECT count(*) FROM public.personnel_applications WHERE application_id=:id
            """), {"id": application_id}).scalar_one() == 1
        finally:
            transaction.rollback()
