"""Electronic HIRE contract on the disposable PostgreSQL database."""
from datetime import UTC, date, datetime
from decimal import Decimal
from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4

import json

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.personnel_applications.application import electronic_hire_service as hire
from app.personnel_applications.application.hire_order_draft_service import create_hire_order_draft_for_application
from app.personnel_applications.application.registration_service import register_personnel_application
from app.personnel_applications.domain.errors import PersonnelApplicationHireOrderError
from app.services.personnel_order_hire_from_person_service import validate_hire_person_candidate
from app.services.personnel_orders_editorial.mapper import build_item_ctx
from app.services import personnel_order_template_application_service as templates
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
    conn.execute(text("""
        INSERT INTO public.org_unit_allowed_positions(org_unit_id, position_id, is_active)
        VALUES (:unit, :position, TRUE)
        ON CONFLICT (org_unit_id, position_id) DO UPDATE SET is_active=TRUE
    """), {"unit": unit, "position": position})
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


def test_manual_position_create_keeps_catalog_unchanged(monkeypatch):
    from app.directory import electronic_hire_routes as routes

    with engine.connect() as conn:
        txn = conn.begin()
        try:
            actor = int(conn.execute(text("SELECT user_id FROM public.users WHERE is_active=TRUE ORDER BY user_id LIMIT 1")).scalar_one())
            unit = int(conn.execute(text("SELECT unit_id FROM public.org_units ORDER BY unit_id LIMIT 1")).scalar_one())
            positions_before = conn.execute(text("SELECT count(*) FROM public.positions")).scalar_one()
            links_before = conn.execute(text("SELECT count(*) FROM public.org_unit_allowed_positions")).scalar_one()
            monkeypatch.setattr(routes, "engine", SimpleNamespace(begin=lambda: nullcontext(conn)))
            monkeypatch.setattr(routes, "_hr_user_id", lambda user: actor)
            title = "Учебная ручная должность " + uuid4().hex[:12]
            created = routes.create_electronic_hire(routes.ElectronicHireCreateIn(
                iin=f"9{uuid4().int % 10**11:011d}", full_name="Тестова Айгуль",
                application_received_at=date(2026, 11, 23), planned_start_date=date(2026, 12, 4),
                org_unit_id=unit, manual_position_name=title,
                manual_position_document_ru="учебную ручную должность " + title.rsplit(" ", 1)[-1],
                employment_rate=Decimal("1"),
            ), user={"user_id": actor})
            reopened = hire.load_electronic_hire(conn, created["application_id"])
            assert created["position_id"] is None
            assert created["position_resolution"] == reopened["position_resolution"] == "unmatched_manual"
            assert reopened["manual_position_name"] == title
            assert conn.execute(text("SELECT count(*) FROM public.positions")).scalar_one() == positions_before
            assert conn.execute(text("SELECT count(*) FROM public.org_unit_allowed_positions")).scalar_one() == links_before
        finally:
            txn.rollback()
def test_position_selection_two_units_manual_title_and_order_transfer():
    with engine.connect() as conn:
        txn = conn.begin()
        try:
            result, head, first_unit, first_position, _ = _setup(conn)
            second_unit = int(conn.execute(text("""
                SELECT unit_id FROM public.org_units WHERE unit_id<>:first ORDER BY unit_id LIMIT 1
            """), {"first": first_unit}).scalar_one())
            second_position = int(conn.execute(text("""
                SELECT position_id FROM public.positions WHERE position_id<>:first ORDER BY position_id LIMIT 1
            """), {"first": first_position}).scalar_one())
            conn.execute(text("""
                INSERT INTO public.org_unit_allowed_positions(org_unit_id, position_id, is_active)
                VALUES (:unit, :position, TRUE)
                ON CONFLICT (org_unit_id, position_id) DO UPDATE SET is_active=TRUE
            """), {"unit": second_unit, "position": second_position})
            assert hire.require_allowed_position(conn, org_unit_id=first_unit, position_id=first_position) is None
            assert hire.require_allowed_position(conn, org_unit_id=second_unit, position_id=second_position) is None
            with pytest.raises(hire.ElectronicHireError) as invalid:
                hire.require_allowed_position(conn, org_unit_id=second_unit, position_id=first_position)
            assert invalid.value.code == "POSITION_NOT_ALLOWED_IN_UNIT"
            with pytest.raises(hire.ElectronicHireError) as invalid_save:
                hire.update_conditions(conn, result.application_id, org_unit_id=second_unit,
                    position_id=first_position, employment_rate=Decimal("1"), planned_start_date=date(2026, 12, 3))
            assert invalid_save.value.code == "POSITION_NOT_ALLOWED_IN_UNIT"
            assert hire.load_electronic_hire(conn, result.application_id)["intended_org_unit_id"] == first_unit
            hire.update_conditions(conn, result.application_id, org_unit_id=second_unit,
                position_id=second_position, employment_rate=Decimal("1"), planned_start_date=date(2026, 12, 3))
            reopened = hire.load_electronic_hire(conn, result.application_id)
            assert (reopened["intended_org_unit_id"], reopened["intended_position_id"]) == (second_unit, second_position)
            title = "Учебная должность " + uuid4().hex[:12]
            document_title = "учебную должность " + title.rsplit(" ", 1)[-1]
            positions_before = conn.execute(text("SELECT count(*) FROM public.positions")).scalar_one()
            links_before = conn.execute(text("SELECT count(*) FROM public.org_unit_allowed_positions")).scalar_one()
            hire.update_conditions(conn, result.application_id, org_unit_id=second_unit,
                position_id=None, manual_position_name=title, manual_position_document_ru=document_title,
                employment_rate=Decimal("1"), planned_start_date=date(2026, 12, 3))
            manual = hire.load_electronic_hire(conn, result.application_id)
            assert manual["position_ru"] == manual["manual_position_name"] == title
            assert manual["intended_position_id"] is None
            assert manual["position_resolution"] == "unmatched_manual"
            assert conn.execute(text("SELECT count(*) FROM public.positions")).scalar_one() == positions_before
            assert conn.execute(text("SELECT count(*) FROM public.org_unit_allowed_positions")).scalar_one() == links_before
            assert document_title in hire.render_application(conn, result.application_id)["ru"]
            _complete_card(conn, result.person_id)
            draft = create_hire_order_draft_for_application(conn, application_id=result.application_id, created_by_user_id=head)
            payload = conn.execute(text("""
                SELECT payload FROM public.personnel_order_items WHERE order_id=:id AND item_type_code='HIRE'
            """), {"id": draft.personnel_order_id}).scalar_one()
            assert payload["org_unit_id"] == second_unit
            assert "position_id" not in payload
            assert payload["manual_position_name"] == title
            assert payload["manual_position_document_ru"] == document_title
            assert payload["position_resolution"] == "unmatched_manual"
            item_context = build_item_ctx({"item_type_code": "HIRE", "payload": payload,
                "effective_date": date(2026, 12, 3)}, None)
            assert item_context["position_name"] == title
            assert item_context["position_document_nominative_ru"] == document_title
            assert item_context["hire_position_manual_forms"]["ru"] is True
            second_head = hire.resolve_unit_head(conn, second_unit)
            if second_head is None:
                conn.execute(text("""
                    INSERT INTO public.org_unit_managers(unit_id,user_id,manager_type,is_active)
                    VALUES (:unit,:user,'HEAD',TRUE)
                """), {"unit": second_unit, "user": head})
                second_head = head
            hire.record_visa(conn, result.application_id, actor_user_id=second_head, decision="approved", explanation=None)
            with pytest.raises(hire.ElectronicHireError) as unmatched:
                hire.require_current_approval(conn, draft.personnel_order_id)
            assert unmatched.value.code == "POSITION_RECONCILIATION_REQUIRED"
            with pytest.raises(hire.ElectronicHireError) as direct_selection:
                hire.update_conditions(conn, result.application_id, org_unit_id=second_unit,
                    position_id=second_position, employment_rate=Decimal("1"), planned_start_date=date(2026, 12, 3))
            assert direct_selection.value.code == "POSITION_RECONCILIATION_REQUIRED"
        finally:
            txn.rollback()
def test_first_published_hire_template_application_creates_editorial_blocks():
    with engine.connect() as conn:
        txn = conn.begin()
        try:
            published = conn.execute(text("""
                SELECT print_title_ru, print_title_kk FROM public.personnel_order_template_versions
                WHERE item_type_code='HIRE' AND status='PUBLISHED' LIMIT 1
            """)).first()
            if published is None:
                pytest.skip("requires the published HIRE template in the isolated test catalog")
            if not all(str(value or "").strip() for value in published):
                pytest.skip("requires approved RU/KK print headings for the published HIRE template")
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
                "document_forms_ru": {"employee_full_name_accusative_ru": "Тестову Айгуль", "position_document_nominative_ru": "врача"},
                "document_forms_kk": {"position_document_possessive_kk": "дәрігердің"},
                "hire_position_manual_forms": {"ru": True},
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
            selected_payload = conn.execute(text("""
                SELECT payload FROM public.personnel_order_items WHERE order_id=:id AND item_type_code='HIRE'
            """), {"id": created.personnel_order_id}).scalar_one()
            assert (selected_payload["org_unit_id"], selected_payload["position_id"]) == (unit, position)
            assert selected_payload["position_resolution"] == "catalog"
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
            # The application and PostgreSQL clocks may differ by a few seconds.
            conn.execute(text("UPDATE public.personnel_intake_links SET expires_at=now()-interval '10 seconds' WHERE link_id=:id"), {"id": second.link_id})
            with pytest.raises(PersonnelIntakeTokenError):
                _resolve_link_by_token(conn, second.raw_token)
            assert conn.execute(text("SELECT payload->>'test' FROM public.personnel_intake_drafts WHERE application_id=:id"), {"id": result.application_id}).scalar_one() == "keep"
        finally:
            txn.rollback()
