"""Electronic HIRE contract on the disposable PostgreSQL database."""
from datetime import UTC, date, datetime
from decimal import Decimal
import json
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.personnel_applications.application import electronic_hire_service as hire
from app.personnel_applications.application.hire_approval_task_service import current_hire_task_period
from app.personnel_applications.application.hire_order_draft_service import create_hire_order_draft_for_application
from app.personnel_applications.application.registration_service import register_personnel_application
from app.personnel_applications.domain.errors import PersonnelApplicationHireOrderError
from app.services.personnel_order_hire_from_person_service import validate_hire_person_candidate
from app.services import personnel_order_template_application_service as templates
from app.services.tasks_service import _is_task_visible_to_user, attach_allowed_actions, load_task_full
from app.services.personnel_orders_apply_service import apply_personnel_order_in_conn
from app.services.personnel_orders_command_service import (
    PersonnelOrderValidationError,
    _require_hire_approval_for_order,
)
from app.personnel_intake.application.intake_service import issue_intake_link, _resolve_link_by_token
from app.personnel_intake.domain.errors import PersonnelIntakeTokenError
from tests.ppr.conftest import insert_employee


def _setup(conn, *, former: bool = False):
    user = int(conn.execute(text("SELECT user_id FROM public.users WHERE is_active=TRUE ORDER BY user_id LIMIT 1")).scalar_one())
    unit = int(conn.execute(text("SELECT unit_id FROM public.org_units ORDER BY unit_id LIMIT 1")).scalar_one())
    position = int(conn.execute(text("SELECT position_id FROM public.positions ORDER BY position_id LIMIT 1")).scalar_one())
    existing_head = conn.execute(text("SELECT user_id FROM public.org_unit_managers WHERE unit_id=:unit AND manager_type='HEAD' AND is_active=TRUE"), {"unit": unit}).scalar_one_or_none()
    if existing_head is None:
        conn.execute(text("INSERT INTO public.org_unit_managers(unit_id,user_id,manager_type,is_active) VALUES (:unit,:user,'HEAD',TRUE)"), {"unit": unit, "user": user})
    else:
        user = int(existing_head)
    iin = f"9{uuid4().int % 10**11:011d}"
    if former:
        person = int(conn.execute(text("""
            INSERT INTO public.persons(full_name,last_name,first_name,birth_date,iin,match_key,person_status,source)
            VALUES ('Тестова Айгуль', 'Тестова', 'Айгуль', '1990-01-01', :iin, :key, 'active', 'manual')
            RETURNING person_id
        """), {"iin": iin, "key": f"eha:{uuid4().hex}"}).scalar_one())
        employee = insert_employee(conn, full_name="Тестова Айгуль", person_id=person, is_active=False)
    else:
        person = None
        employee = None
    result = register_personnel_application(
        conn, iin_raw=iin, full_name="Тестова Айгуль", birth_date=date(1990, 1, 1),
        application_received_at=date(2026, 11, 20), vacancy_check_status="pending",
        vacancy_checked_at=None, vacancy_checked_by_user_id=None,
        intended_org_group_id=None, intended_org_unit_id=unit, intended_position_id=position,
        intended_employment_rate=Decimal("0.75"), intended_vacancy_text=None,
        contact_mobile_phone=None, contact_email=None, hr_note=None,
        idempotency_key=None, registered_by_user_id=user, actor_id=f"user:{user}",
        application_source="electronic",
    )
    conn.execute(text("INSERT INTO public.electronic_hire_applications(application_id, planned_start_date) VALUES (:id, '2026-12-01')"), {"id": result.application_id})
    return result, user, unit, position, employee


def _complete_card(conn, person_id: int):
    conn.execute(text("UPDATE public.persons SET last_name='Тестова', first_name='Айгуль' WHERE person_id=:id"), {"id": person_id})
    conn.execute(text("""
        INSERT INTO public.person_contacts(person_id, mobile_phone)
        VALUES (:id, '+77001234567')
        ON CONFLICT (person_id) DO UPDATE SET mobile_phone=EXCLUDED.mobile_phone
    """), {"id": person_id})
    conn.execute(text("""
        INSERT INTO public.person_education(person_id, education_kind, institution_name)
        SELECT :id, code, 'Вымышленный учебный центр'
        FROM public.education_program_kinds ORDER BY code LIMIT 1
    """), {"id": person_id})


def test_hire_approval_tasks_follow_visa_and_condition_revisions(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "")
    with engine.connect() as conn:
        txn = conn.begin()
        try:
            application, head, unit, position, _ = _setup(conn)
            _complete_card(conn, application.person_id)
            created = create_hire_order_draft_for_application(
                conn, application_id=application.application_id, created_by_user_id=head)
            assert created.personnel_order_id > 0
            first = conn.execute(text("""
                SELECT h.task_id, h.conditions_hash, s.code, t.description, t.period_id
                FROM public.electronic_hire_approval_tasks h
                JOIN public.tasks t USING(task_id)
                JOIN public.task_statuses s ON s.status_id=t.status_id
                WHERE h.application_id=:id
            """), {"id": application.application_id}).mappings().one()
            assert first["code"] == "IN_PROGRESS"
            assert all(value in first["description"] for value in
                       ("Тестова Айгуль", "Отделение:", "Должность:", "0,75", "01.12.2026"))
            assert first["period_id"] == current_hire_task_period(conn)["period_id"]
            task = load_task_full(conn, task_id=int(first["task_id"]))
            assert task["electronic_hire_application_id"] == application.application_id
            assert _is_task_visible_to_user(conn, current_user_id=head,
                                            current_role_id=int(task["executor_role_id"]), task_row=task)
            other = conn.execute(text("""
                INSERT INTO public.users(full_name, role_id, unit_id, is_active, login)
                VALUES ('Вымышленный другой сотрудник', :role, :unit, TRUE, :login)
                RETURNING user_id
            """), {"role": task["executor_role_id"], "unit": unit,
                   "login": f"eha-other-{uuid4().hex}"}).scalar_one()
            assert not _is_task_visible_to_user(conn, current_user_id=int(other),
                                                current_role_id=int(task["executor_role_id"]), task_row=task)
            assert attach_allowed_actions(task=task, current_user_id=head,
                                          current_role_id=int(task["executor_role_id"]))["allowed_actions"] == []

            replay = create_hire_order_draft_for_application(
                conn, application_id=application.application_id, created_by_user_id=head)
            assert replay.idempotent_replay
            assert conn.execute(text("SELECT count(*) FROM public.electronic_hire_approval_tasks WHERE application_id=:id"),
                                {"id": application.application_id}).scalar_one() == 1

            hire.record_visa(conn, application.application_id, actor_user_id=head,
                             decision="rejected", explanation="Тестовое пояснение")
            rejected = load_task_full(conn, task_id=int(first["task_id"]))
            assert rejected["status_code"] == "REJECTED"
            assert rejected["electronic_hire_decision"] == "rejected"
            assert rejected["electronic_hire_explanation"] == "Тестовое пояснение"

            hire.update_conditions(conn, application.application_id, org_unit_id=unit, position_id=position,
                                   employment_rate=Decimal("0.50"), planned_start_date=date(2026, 12, 2))
            second = conn.execute(text("""
                SELECT h.task_id, h.conditions_hash, s.code FROM public.electronic_hire_approval_tasks h
                JOIN public.tasks t USING(task_id) JOIN public.task_statuses s ON s.status_id=t.status_id
                WHERE h.application_id=:id ORDER BY h.task_id DESC LIMIT 1
            """), {"id": application.application_id}).mappings().one()
            assert second["task_id"] != first["task_id"] and second["conditions_hash"] != first["conditions_hash"]
            assert second["code"] == "IN_PROGRESS"
            assert load_task_full(conn, task_id=int(first["task_id"]))["status_code"] == "REJECTED"
            hire.update_conditions(conn, application.application_id, org_unit_id=unit, position_id=position,
                                   employment_rate=Decimal("0.50"), planned_start_date=date(2026, 12, 2))
            assert conn.execute(text("SELECT count(*) FROM public.electronic_hire_approval_tasks WHERE application_id=:id"),
                                {"id": application.application_id}).scalar_one() == 2
            hire.record_visa(conn, application.application_id, actor_user_id=head,
                             decision="approved", explanation="Согласовано для теста")
            assert load_task_full(conn, task_id=int(second["task_id"]))["status_code"] == "DONE"

            hire.update_conditions(conn, application.application_id, org_unit_id=unit, position_id=position,
                                   employment_rate=Decimal("0.75"), planned_start_date=date(2026, 12, 1))
            assert hire.current_visa(conn, hire.load_electronic_hire(conn, application.application_id))["is_current"] is False
            assert conn.execute(text("SELECT count(*) FROM public.electronic_hire_approval_tasks WHERE application_id=:id"),
                                {"id": application.application_id}).scalar_one() == 3
            third = conn.execute(text("SELECT max(task_id) FROM public.electronic_hire_approval_tasks WHERE application_id=:id"),
                                 {"id": application.application_id}).scalar_one()
            assert load_task_full(conn, task_id=int(third))["status_code"] == "IN_PROGRESS"
            hire.update_conditions(conn, application.application_id, org_unit_id=unit, position_id=position,
                                   employment_rate=Decimal("0.60"), planned_start_date=date(2026, 12, 3))
            assert load_task_full(conn, task_id=int(third))["status_code"] == "ARCHIVED"
            assert conn.execute(text("SELECT count(*) FROM public.electronic_hire_approval_tasks WHERE application_id=:id"),
                                {"id": application.application_id}).scalar_one() == 4
        finally:
            txn.rollback()


def test_first_published_hire_template_application_creates_editorial_blocks():
    with engine.connect() as conn:
        txn = conn.begin()
        try:
            published = conn.execute(text("""
                SELECT 1 FROM public.personnel_order_template_versions
                WHERE item_type_code='HIRE' AND status='PUBLISHED' LIMIT 1
            """)).first()
            if published is None:
                pytest.skip("requires the published HIRE template in the isolated test catalog")
            application, hr, _, _, _ = _setup(conn)
            _complete_card(conn, application.person_id)
            order = create_hire_order_draft_for_application(
                conn, application_id=application.application_id, created_by_user_id=hr)
            order_id = order.personnel_order_id
            item_id = int(conn.execute(text("SELECT item_id FROM public.personnel_order_items WHERE order_id=:id"),
                                       {"id": order_id}).scalar_one())
            conn.execute(text("""
                UPDATE public.personnel_order_items
                SET payload=payload || CAST(:extra AS jsonb)
                WHERE item_id=:id
            """), {"id": item_id, "extra": json.dumps({
                "document_forms_ru": {"employee_full_name_accusative_ru": "Тестову Айгуль"},
                "hire_basis": {"ru": "Заявление", "kk": "Өтініш"},
            }, ensure_ascii=False)})
            preview = templates._preview(conn, order_id)
            assert not preview["items"][0]["blocked"]
            assert templates._blocks(conn, order_id, [item_id]) == []

            templates.apply_template_application_tx(
                conn, order_id, hr, expected_document_revision=preview["order_revision"])

            blocks = templates._blocks(conn, order_id, [item_id])
            assert len(blocks) == 8
            generated = {(block["scope"], block["locale"], block["block_type"]): block["generated_text"]
                         for block in blocks}
            for locale in ("ru", "kk"):
                assert generated[("ORDER", locale, "title")] == preview["order_proposed"][f"title_{locale}"]
                assert generated[("ITEM", locale, "body")] == preview["items"][0]["proposed"][f"body_{locale}"]
                assert "0,75" in generated[("ITEM", locale, "body")]
        finally:
            txn.rollback()
def test_new_candidate_statement_card_gate_visa_and_reapproval(monkeypatch):
    with engine.connect() as conn:
        txn = conn.begin()
        try:
            result, head, unit, position, _ = _setup(conn)
            texts = hire.render_application(conn, result.application_id)
            assert "0,75" in texts["ru"] and "0,75" in texts["kk"]
            assert "прошу принять меня" in texts["ru"]
            assert "қабылдауыңызды сұраймын" in texts["kk"]
            with pytest.raises(PersonnelApplicationHireOrderError, match="Дата рождения|Фамилия") as incomplete:
                create_hire_order_draft_for_application(conn, application_id=result.application_id, created_by_user_id=head)
            assert "Мобильный телефон" in str(incomplete.value)
            assert "Образование" in str(incomplete.value)
            _complete_card(conn, result.person_id)
            created = create_hire_order_draft_for_application(conn, application_id=result.application_id, created_by_user_id=head)
            assert not created.idempotent_replay
            assert create_hire_order_draft_for_application(conn, application_id=result.application_id, created_by_user_id=head).idempotent_replay
            with pytest.raises(hire.ElectronicHireError, match="виза"):
                hire.require_current_approval(conn, created.personnel_order_id)
            with pytest.raises(PersonnelOrderValidationError, match="виза"):
                _require_hire_approval_for_order(conn, created.personnel_order_id)
            with pytest.raises(hire.ElectronicHireError) as denied:
                hire.record_visa(conn, result.application_id, actor_user_id=head + 999999,
                                 decision="approved", explanation=None)
            assert denied.value.code == "HEAD_ACCESS_DENIED"
            with pytest.raises(hire.ElectronicHireError, match="пояснение"):
                hire.record_visa(conn, result.application_id, actor_user_id=head, decision="rejected", explanation="")
            hire.record_visa(conn, result.application_id, actor_user_id=head, decision="approved", explanation=None)
            hire.require_current_approval(conn, created.personnel_order_id)
            hire.update_conditions(conn, result.application_id, org_unit_id=unit, position_id=position,
                                   employment_rate=Decimal("0.50"), planned_start_date=date(2026, 12, 2))
            with pytest.raises(hire.ElectronicHireError, match="виза"):
                hire.require_current_approval(conn, created.personnel_order_id)
            hire.record_visa(conn, result.application_id, actor_user_id=head, decision="approved", explanation=None)
            hire.require_current_approval(conn, created.personnel_order_id)
            sent = []
            monkeypatch.setenv("BOT_TOKEN", "fictional-test-token")
            monkeypatch.setattr(hire, "send_telegram_text", lambda chat_id, message, **kwargs: sent.append(message))
            conn.execute(text("UPDATE public.users SET telegram_id='123456789' WHERE user_id=:id"), {"id": head})
            delivery = hire.dispatch_approval_notification(conn, result.application_id)
            assert delivery["status"] == "sent" and len(sent) == 1
            assert hire.dispatch_approval_notification(conn, result.application_id)["status"] == "sent"
            assert len(sent) == 1
            conn.execute(text("""
                UPDATE public.personnel_orders SET order_number=:number, status='SIGNED'
                WHERE order_id=:id
            """), {"number": f"EHA-{uuid4().hex[:8]}", "id": created.personnel_order_id})
            apply_personnel_order_in_conn(conn, order_id=created.personnel_order_id, created_by=head)
            assert conn.execute(text("SELECT status FROM public.personnel_applications WHERE application_id=:id"), {"id": result.application_id}).scalar_one() == "completed"
            assert int(conn.execute(text("SELECT count(*) FROM public.employee_events WHERE order_id=:id AND event_type='HIRE'"), {"id": created.personnel_order_id}).scalar_one()) == 1
            assert int(conn.execute(text("SELECT count(*) FROM public.employees WHERE person_id=:id AND is_active=TRUE"), {"id": result.person_id}).scalar_one()) == 1
        finally:
            txn.rollback()


def test_direct_apply_requires_current_visa():
    with engine.connect() as conn:
        txn = conn.begin()
        try:
            result, head, _, _, _ = _setup(conn)
            _complete_card(conn, result.person_id)
            created = create_hire_order_draft_for_application(conn, application_id=result.application_id, created_by_user_id=head)
            conn.execute(text("UPDATE public.personnel_orders SET order_number=:number, status='SIGNED' WHERE order_id=:id"),
                         {"number": f"EHA-{uuid4().hex[:8]}", "id": created.personnel_order_id})
            with pytest.raises(PersonnelOrderValidationError, match="виза"):
                apply_personnel_order_in_conn(conn, order_id=created.personnel_order_id, created_by=head)
            assert conn.execute(text("SELECT count(*) FROM public.employee_events WHERE order_id=:id"),
                                {"id": created.personnel_order_id}).scalar_one() == 0
        finally:
            txn.rollback()


def test_former_candidate_reuses_person_and_inactive_employee():
    with engine.connect() as conn:
        txn = conn.begin()
        try:
            result, head, _, _, employee = _setup(conn, former=True)
            assert employee is not None
            old_event = int(conn.execute(text("""
                INSERT INTO public.employee_events
                    (employee_id, event_type, effective_date, order_ref, created_by)
                VALUES (:employee, 'TERMINATION', '2025-06-30', 'FICTIONAL-OLD-ORDER', :head)
                RETURNING event_id
            """), {"employee": employee, "head": head}).scalar_one())
            assert result.person_id == int(conn.execute(text("SELECT person_id FROM public.employees WHERE employee_id=:id"), {"id": employee}).scalar_one())
            validate_hire_person_candidate(conn, result.person_id)
            _complete_card(conn, result.person_id)
            created = create_hire_order_draft_for_application(conn, application_id=result.application_id, created_by_user_id=head)
            assert created.personnel_order_id > 0
            assert conn.execute(text("SELECT is_active FROM public.employees WHERE employee_id=:id"), {"id": employee}).scalar_one() is False
            assert int(conn.execute(text("SELECT count(*) FROM public.persons WHERE person_id=:id"), {"id": result.person_id}).scalar_one()) == 1
            hire.record_visa(conn, result.application_id, actor_user_id=head, decision="approved", explanation=None)
            conn.execute(text("UPDATE public.personnel_orders SET order_number=:number, status='SIGNED' WHERE order_id=:id"),
                         {"number": f"EHA-{uuid4().hex[:8]}", "id": created.personnel_order_id})
            apply_personnel_order_in_conn(conn, order_id=created.personnel_order_id, created_by=head)
            assert conn.execute(text("SELECT is_active FROM public.employees WHERE employee_id=:id"), {"id": employee}).scalar_one() is True
            assert int(conn.execute(text("SELECT count(*) FROM public.employees WHERE person_id=:id"), {"id": result.person_id}).scalar_one()) == 1
            assert conn.execute(text("SELECT order_ref FROM public.employee_events WHERE event_id=:id"), {"id": old_event}).scalar_one() == "FICTIONAL-OLD-ORDER"
            assert int(conn.execute(text("SELECT count(*) FROM public.employee_events WHERE employee_id=:id AND event_type='HIRE'"), {"id": employee}).scalar_one()) >= 1
        finally:
            txn.rollback()


def test_link_24_hours_reissue_keeps_draft_and_revokes_old(monkeypatch):
    monkeypatch.setenv("PERSONNEL_INTAKE_TOKEN_ENCRYPTION_KEY", "fictional-eha-test-key")
    with engine.connect() as conn:
        txn = conn.begin()
        try:
            result, head, _, _, _ = _setup(conn)
            first = issue_intake_link(conn, application_id=result.application_id, issued_by_user_id=head)
            assert 23.9 < (first.expires_at - datetime.now(UTC)).total_seconds() / 3600 <= 24.1
            conn.execute(text("UPDATE public.personnel_intake_drafts SET payload=CAST(:payload AS jsonb) WHERE application_id=:id"), {"id": result.application_id, "payload": '{"test":"keep"}'})
            second = issue_intake_link(conn, application_id=result.application_id, issued_by_user_id=head, reissue=True)
            assert second.link_id != first.link_id
            with pytest.raises(PersonnelIntakeTokenError):
                _resolve_link_by_token(conn, first.raw_token)
            assert _resolve_link_by_token(conn, second.raw_token)[1].link_id == second.link_id
            assert conn.execute(text("SELECT payload->>'test' FROM public.personnel_intake_drafts WHERE application_id=:id"), {"id": result.application_id}).scalar_one() == "keep"
            conn.execute(text("UPDATE public.personnel_intake_links SET expires_at=now()-interval '1 second' WHERE link_id=:id"), {"id": second.link_id})
            with pytest.raises(PersonnelIntakeTokenError):
                _resolve_link_by_token(conn, second.raw_token)
            assert conn.execute(text("SELECT payload->>'test' FROM public.personnel_intake_drafts WHERE application_id=:id"), {"id": result.application_id}).scalar_one() == "keep"
        finally:
            txn.rollback()
