"""Focused contract checks on a disposable PostgreSQL database only."""
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth import get_current_user
from app.db.engine import engine
from app.main import app as api_app
from app.personnel_applications.application import electronic_hire_service as hire
from app.personnel_applications.application.hire_order_draft_service import create_hire_order_draft_for_application
from tests.personnel_applications.test_electronic_hire_postgres import _complete_card, _setup


def _synthetic_position(conn, name: str, type_code: int) -> int:
    return int(conn.execute(text("""
        INSERT INTO public.positions (name, category, type_code, name_kk)
        VALUES (:name, 'medical', :type_code, :name) RETURNING position_id
    """), {"name": f"{name} {uuid4().hex[:8]}", "type_code": type_code}).scalar_one())


def test_medical_routes_use_position_type_and_unique_assignment():
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            unit = int(conn.execute(text("SELECT unit_id FROM public.org_units WHERE group_id=2 ORDER BY unit_id LIMIT 1")).scalar_one())
            head = int(conn.execute(text("""
                SELECT user_id FROM public.org_unit_managers
                WHERE unit_id=:unit AND manager_type='HEAD' AND is_active=TRUE LIMIT 1
            """), {"unit": unit}).scalar_one())
            nurse = int(conn.execute(text("SELECT user_id FROM public.users WHERE is_active AND user_id<>:head ORDER BY user_id LIMIT 1"),
                                    {"head": head}).scalar_one())
            conn.execute(text("""
                INSERT INTO public.org_unit_managers(unit_id,user_id,manager_type,is_active)
                VALUES (:unit,:nurse,'SENIOR_NURSE',TRUE)
            """), {"unit": unit, "nurse": nurse})
            for name, type_code, expected in (("Врач", 1, head), ("Медсестра", 2, nurse),
                                              ("Санитарка", 3, nurse), ("Сестра-хозяйка", 3, nurse)):
                pos = _synthetic_position(conn, name, type_code)
                application, _, _, _, _ = _setup(conn, unit_id=unit, position_id=pos)
                app = hire.load_electronic_hire(conn, application.application_id)
                assert hire.resolve_approval_recipient(conn, app) == expected
            unknown = _synthetic_position(conn, "Без категории", 4)
            application, _, _, _, _ = _setup(conn, unit_id=unit, position_id=unknown)
            with pytest.raises(hire.ElectronicHireError) as missing_type:
                hire.resolve_approval_recipient(conn, hire.load_electronic_hire(conn, application.application_id))
            assert missing_type.value.code == "POSITION_TYPE_REQUIRED"
            conn.execute(text("UPDATE public.org_unit_managers SET is_active=FALSE WHERE unit_id=:unit AND manager_type='SENIOR_NURSE'"), {"unit": unit})
            pos = _synthetic_position(conn, "Медсестра", 2)
            application, _, _, _, _ = _setup(conn, unit_id=unit, position_id=pos)
            with pytest.raises(hire.ElectronicHireError) as missing:
                hire.resolve_approval_recipient(conn, hire.load_electronic_hire(conn, application.application_id))
            assert missing.value.code == "APPROVER_NOT_CONFIGURED"
            conn.execute(text("UPDATE public.org_unit_managers SET is_active=TRUE WHERE unit_id=:unit AND manager_type='SENIOR_NURSE'"), {"unit": unit})
            second = int(conn.execute(text("SELECT user_id FROM public.users WHERE is_active AND user_id NOT IN (:head,:nurse) ORDER BY user_id LIMIT 1"),
                                      {"head": head, "nurse": nurse}).scalar_one())
            conn.execute(text("INSERT INTO public.org_unit_managers(unit_id,user_id,manager_type,is_active) VALUES (:unit,:user,'SENIOR_NURSE',TRUE)"),
                         {"unit": unit, "user": second})
            with pytest.raises(hire.ElectronicHireError) as ambiguous:
                hire.resolve_approval_recipient(conn, hire.load_electronic_hire(conn, application.application_id))
            assert ambiguous.value.code == "APPROVER_AMBIGUOUS"
        finally:
            tx.rollback()


def test_paper_mode_has_no_electronic_task_or_notification_and_requires_current_confirmation():
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            application, hr, unit, position, _ = _setup(conn, approval_mode="paper")
            _complete_card(conn, application.person_id)
            order = create_hire_order_draft_for_application(conn, application_id=application.application_id,
                                                            created_by_user_id=hr)
            assert conn.execute(text("SELECT count(*) FROM public.electronic_hire_approval_tasks WHERE application_id=:id"),
                                {"id": application.application_id}).scalar_one() == 0
            assert conn.execute(text("SELECT count(*) FROM public.electronic_hire_notifications WHERE application_id=:id"),
                                {"id": application.application_id}).scalar_one() == 0
            assert hire.dispatch_approval_notification(conn, application.application_id)["status"] == "paper"
            with pytest.raises(hire.ElectronicHireError) as required:
                hire.require_current_approval(conn, order.personnel_order_id)
            assert required.value.code == "PAPER_APPROVAL_REQUIRED"
            saved = hire.record_paper_confirmation(conn, application.application_id, actor_user_id=hr,
                                                   approver_name="Вымышленный согласующий", approved_on=date(2026, 11, 20),
                                                   note="Бумажное согласие")
            assert saved["is_current"]
            hire.require_current_approval(conn, order.personnel_order_id)
            hire.update_conditions(conn, application.application_id, org_unit_id=unit, position_id=position,
                                   employment_rate=Decimal("0.50"), planned_start_date=date(2026, 12, 2))
            assert hire.current_paper_confirmation(conn, hire.load_electronic_hire(conn, application.application_id))["is_current"] is False
            with pytest.raises(hire.ElectronicHireError) as stale:
                hire.require_current_approval(conn, order.personnel_order_id)
            assert stale.value.code == "PAPER_APPROVAL_REQUIRED"
            assert conn.execute(text("SELECT count(*) FROM public.electronic_hire_approval_tasks WHERE application_id=:id"),
                                {"id": application.application_id}).scalar_one() == 0
        finally:
            tx.rollback()


def test_department_setting_changes_only_new_applications_and_move_is_audited():
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            unit = int(conn.execute(text("SELECT unit_id FROM public.org_units WHERE group_id=3 ORDER BY unit_id LIMIT 1")).scalar_one())
            second_unit = int(conn.execute(text("SELECT unit_id FROM public.org_units WHERE group_id=3 AND unit_id<>:unit ORDER BY unit_id LIMIT 1"),
                                           {"unit": unit}).scalar_one())
            application, actor, _, position, _ = _setup(conn, unit_id=unit, approval_mode="paper")
            assert hire.configured_approval_mode(conn, unit) == "paper"
            conn.execute(text("""
                INSERT INTO public.hire_approval_unit_modes(unit_id, mode, updated_by_user_id)
                VALUES (:unit,'electronic',:actor)
            """), {"unit": unit, "actor": actor})
            assert hire.configured_approval_mode(conn, unit) == "electronic"
            assert hire.load_electronic_hire(conn, application.application_id)["approval_mode"] == "paper"
            with pytest.raises(hire.ElectronicHireError) as ack:
                hire.update_conditions(conn, application.application_id, org_unit_id=second_unit,
                                       position_id=position, employment_rate=Decimal("0.75"),
                                       planned_start_date=date(2026, 12, 1))
            assert ack.value.code == "MODE_CHANGE_ACK_REQUIRED"
            moved = hire.update_conditions(conn, application.application_id, org_unit_id=second_unit,
                                           position_id=position, employment_rate=Decimal("0.75"),
                                           planned_start_date=date(2026, 12, 1), actor_user_id=actor,
                                           mode_change_reason="Вымышленная смена отделения")
            assert moved["approval_mode"] == hire.configured_approval_mode(conn, second_unit)
            assert conn.execute(text("SELECT count(*) FROM public.hire_approval_mode_audit WHERE application_id=:id"),
                                {"id": application.application_id}).scalar_one() == 1
        finally:
            tx.rollback()


def test_admin_mode_api_audits_change_and_new_application_snapshots_mode():
    with engine.begin() as conn:
        actor = int(conn.execute(text("SELECT user_id FROM public.users WHERE is_active ORDER BY user_id LIMIT 1")).scalar_one())
        admin = conn.execute(text("""
            SELECT u.user_id, u.role_id FROM public.users u JOIN public.roles r USING (role_id)
            WHERE r.code='ADMIN' AND u.is_active=TRUE ORDER BY u.user_id LIMIT 1
        """)).mappings().one()
        hr = conn.execute(text("""
            SELECT u.user_id, u.role_id FROM public.users u JOIN public.roles r USING (role_id)
            WHERE r.code='HR_HEAD' AND u.is_active=TRUE ORDER BY u.user_id LIMIT 1
        """)).mappings().one()
        unit = int(conn.execute(text("""
            INSERT INTO public.org_units (name, code, group_id)
            VALUES ('Вымышленное подразделение внедрения', :code, 3) RETURNING unit_id
        """), {"code": f"EHA-ROLLOUT-{uuid4().hex[:8]}"}).scalar_one())
        old, _, _, position, _ = _setup(conn, unit_id=unit, approval_mode="paper")
    client = TestClient(api_app)
    try:
        api_app.dependency_overrides[get_current_user] = lambda: {"user_id": int(hr["user_id"]), "role_id": int(hr["role_id"])}
        assert client.get("/admin/hire-approval-rollout").status_code == 403
        assert client.put(f"/admin/hire-approval-rollout/{unit}",
                          json={"mode": "electronic", "reason": "Тест"}).status_code == 403
        api_app.dependency_overrides[get_current_user] = lambda: {"user_id": int(admin["user_id"]), "role_id": int(admin["role_id"])}
        result = client.put(f"/admin/hire-approval-rollout/{unit}",
                            json={"mode": "electronic", "reason": "Пилотное включение"})
        assert result.status_code == 200, result.text
        assert result.json()["retained_prior_mode_count"] == 1
        listing = client.get("/admin/hire-approval-rollout")
        assert listing.status_code == 200, listing.text
        entry = next(row for row in listing.json()["items"] if row["unit_id"] == unit)
        assert entry["mode"] == "electronic" and entry["retained_prior_mode_count"] == 1
        assert any(row["unit_id"] == unit and row["reason"] == "Пилотное включение"
                   for row in listing.json()["audit"])
        api_app.dependency_overrides[get_current_user] = lambda: {"user_id": int(hr["user_id"]), "role_id": int(hr["role_id"])}
        created = client.post("/directory/electronic-hire/applications", json={
            "iin": f"9{uuid4().int % 10**11:011d}", "full_name": "Вымышленная Тестова Айгуль",
            "birth_date": "1990-01-01", "application_received_at": "2026-11-20",
            "planned_start_date": "2026-12-01", "org_unit_id": unit,
            "position_id": position, "employment_rate": 0.5,
        })
        assert created.status_code == 200, created.text
        assert created.json()["approval_mode"] == "electronic"
        with engine.connect() as conn:
            assert hire.load_electronic_hire(conn, old.application_id)["approval_mode"] == "paper"
            assert hire.load_electronic_hire(conn, created.json()["application_id"])["approval_mode"] == "electronic"
    finally:
        api_app.dependency_overrides.pop(get_current_user, None)
