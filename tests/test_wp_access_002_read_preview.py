"""WP-ACCESS-002 permission and read-only employee access projections."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.engine import engine
from app.services import employee_access_read_service
from tests.conftest import auth_headers, create_non_privileged_role, create_task, create_user


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture
def access_case(seed):
    suffix = uuid4().hex[:10]
    ids: dict[str, int] = {}
    created_permission_id: int | None = None
    created_task_status_id: int | None = None
    with engine.begin() as conn:
        position_id = int(conn.execute(text("""
            INSERT INTO public.positions (name, category)
            VALUES (:name, 'other')
            RETURNING position_id
        """), {"name": f"WP ACCESS position {suffix}"}).scalar_one())
        period_id = int(conn.execute(text("""
            INSERT INTO public.reporting_periods (kind, date_start, date_end, label, is_closed)
            VALUES ('test', CURRENT_DATE, CURRENT_DATE, :label, FALSE)
            RETURNING period_id
        """), {"label": f"WP ACCESS {suffix}"}).scalar_one())
        created_task_status_id = conn.execute(text("""
            INSERT INTO public.task_statuses (code, name_ru, is_terminal)
            VALUES ('NEW', 'New', FALSE)
            ON CONFLICT (code) DO NOTHING
            RETURNING status_id
        """)).scalar_one_or_none()
        person_id = int(conn.execute(text("""
            INSERT INTO public.persons (full_name, match_key, person_status, source)
            VALUES (:name, :key, 'active', 'manual') RETURNING person_id
        """), {"name": f"WP ACCESS {suffix}", "key": f"wp-access-002:{suffix}"}).scalar_one())
        employee_id = int(conn.execute(text("""
            INSERT INTO public.employees (person_id, full_name, org_unit_id, position_id, is_active, operational_status)
            VALUES (:person_id, :name, :unit_id, :position_id, TRUE, 'active') RETURNING employee_id
        """), {"person_id": person_id, "name": f"WP ACCESS {suffix}", "unit_id": seed["unit_id"], "position_id": position_id}).scalar_one())
        conn.execute(text("UPDATE public.users SET employee_id=:employee_id WHERE user_id=:user_id"), {"employee_id": employee_id, "user_id": seed["executor_user_id"]})
        conn.execute(text("""
            INSERT INTO public.person_assignments (person_id, org_unit_id, position_id, employment_type, rate, start_date, active_flag, is_primary, lifecycle_status, assignment_key, source)
            VALUES (:person_id, :unit_id, :position_id, 'primary', 1.0, CURRENT_DATE, TRUE, TRUE, 'active', :key, 'manual')
        """), {"person_id": person_id, "unit_id": seed["unit_id"], "position_id": position_id, "key": f"wp-access-assignment:{suffix}"})
        created_permission_id = conn.execute(text("""
            INSERT INTO public.access_roles (code, name, description, access_level, level_rank, is_system)
            VALUES ('USER_ACCESS_ADMIN', 'User Access Administrator', 'test catalogue row', 'MANAGER', 20, TRUE)
            ON CONFLICT (code) DO NOTHING
            RETURNING access_role_id
        """)).scalar_one_or_none()
        permission_id = int(conn.execute(text("SELECT access_role_id FROM public.access_roles WHERE code='USER_ACCESS_ADMIN'")).scalar_one())
        conn.execute(text("""
            INSERT INTO public.access_grants (access_role_id, target_type, target_id, granted_by_user_id, reason)
            VALUES (:role_id, 'USER', :user_id, :user_id, 'WP-ACCESS-002 test')
        """), {"role_id": permission_id, "user_id": seed["initiator_user_id"]})
        admin_role = create_non_privileged_role(conn, f"ADMIN_{suffix}")
        hr_role = create_non_privileged_role(conn, f"HR_HEAD_{suffix}")
        admin_user = create_user(conn, full_name=f"admin {suffix}", role_id=admin_role, unit_id=seed["unit_id"])
        hr_user = create_user(conn, full_name=f"hr {suffix}", role_id=hr_role, unit_id=seed["unit_id"])
        ids.update(
            person_id=person_id,
            employee_id=employee_id,
            position_id=position_id,
            period_id=period_id,
            admin_user=admin_user,
            hr_user=hr_user,
            admin_role=admin_role,
            hr_role=hr_role,
        )
    try:
        yield {**seed, **ids}
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM public.access_grants WHERE reason='WP-ACCESS-002 test'"))
            conn.execute(text("DELETE FROM public.tasks WHERE period_id=:period_id"), {"period_id": ids["period_id"]})
            conn.execute(text("UPDATE public.users SET employee_id=NULL WHERE user_id=:user_id"), {"user_id": seed["executor_user_id"]})
            conn.execute(text("DELETE FROM public.employee_onboardings WHERE employee_id=:employee_id"), {"employee_id": ids["employee_id"]})
            conn.execute(text("DELETE FROM public.users WHERE user_id IN (:a, :h)"), {"a": ids["admin_user"], "h": ids["hr_user"]})
            conn.execute(text("DELETE FROM public.roles WHERE role_id IN (:a, :h)"), {"a": ids["admin_role"], "h": ids["hr_role"]})
            conn.execute(text("DELETE FROM public.person_assignments WHERE person_id=:person_id"), {"person_id": ids["person_id"]})
            conn.execute(text("DELETE FROM public.employees WHERE employee_id=:employee_id"), {"employee_id": ids["employee_id"]})
            conn.execute(text("DELETE FROM public.persons WHERE person_id=:person_id"), {"person_id": ids["person_id"]})
            conn.execute(text("DELETE FROM public.positions WHERE position_id=:position_id"), {"position_id": ids["position_id"]})
            conn.execute(text("DELETE FROM public.reporting_periods WHERE period_id=:period_id"), {"period_id": ids["period_id"]})
            if created_task_status_id is not None:
                conn.execute(text("DELETE FROM public.task_statuses WHERE status_id=:status_id"), {"status_id": created_task_status_id})
            if created_permission_id is not None:
                conn.execute(text("DELETE FROM public.access_roles WHERE access_role_id=:access_role_id"), {"access_role_id": created_permission_id})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_access_read_requires_explicit_personal_permission(client, access_case):
    employee_id = access_case["employee_id"]
    allowed = client.get(f"/directory/personnel/employees/{employee_id}/access", headers=auth_headers(access_case["initiator_user_id"]))
    assert allowed.status_code == 200, allowed.text
    body = allowed.json()
    assert body["employee_id"] == employee_id
    assert body["person_id"] == access_case["person_id"]
    assert body["user_id"] == access_case["executor_user_id"]
    assert {"lock_active", "lock_reason", "locked_until", "automatic_lock_active"}.issubset(body)
    assert "manual_lock_active" not in body
    forbidden_headers = [auth_headers(access_case["admin_user"]), auth_headers(access_case["hr_user"]), auth_headers(access_case["executor_user_id"])]
    for headers in forbidden_headers:
        assert client.get(f"/directory/personnel/employees/{employee_id}/access", headers=headers).status_code == 403
    forbidden = {"password_hash", "password", "token", "access_token", "telegram_id", "google_login", "phone", "email", "iin"}
    assert not forbidden.intersection(body)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_preview_is_read_only_and_excludes_role_tasks(client, access_case):
    employee_id = access_case["employee_id"]
    before = None
    with engine.connect() as conn:
        before = conn.execute(text("SELECT is_active, token_version FROM public.users WHERE user_id=:user_id"), {"user_id": access_case["executor_user_id"]}).mappings().one()
    response = client.get(f"/directory/personnel/employees/{employee_id}/access/termination-preview", headers=auth_headers(access_case["initiator_user_id"]))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["linkage_state"] == "RESOLVED"
    assert body["has_active_assignment"] is True
    assert body["counts"]["unfinished_personal_tasks"] == 0
    assert body["counts"]["active_personal_approvals"] == 0
    with engine.connect() as conn:
        after = conn.execute(text("SELECT is_active, token_version FROM public.users WHERE user_id=:user_id"), {"user_id": access_case["executor_user_id"]}).mappings().one()
    assert dict(after) == dict(before)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_missing_user_linkage_and_unique_user_employee_constraint(client, access_case):
    employee_id = access_case["employee_id"]
    actor_headers = auth_headers(access_case["initiator_user_id"])
    with engine.begin() as conn:
        conn.execute(text("UPDATE public.users SET employee_id=NULL WHERE user_id=:user_id"), {"user_id": access_case["executor_user_id"]})
    try:
        missing = client.get(f"/directory/personnel/employees/{employee_id}/access", headers=actor_headers)
        assert missing.status_code == 409
        assert missing.json()["detail"]["code"] == "USER_MISSING"
        preview = client.get(f"/directory/personnel/employees/{employee_id}/access/termination-preview", headers=actor_headers)
        assert preview.status_code == 200
        assert preview.json()["linkage_state"] == "USER_MISSING"
    finally:
        with engine.begin() as conn:
            conn.execute(text("UPDATE public.users SET employee_id=:employee_id WHERE user_id=:user_id"), {"employee_id": employee_id, "user_id": access_case["executor_user_id"]})
    with engine.begin() as conn:
        with pytest.raises(IntegrityError):
            with conn.begin_nested():
                conn.execute(
                    text("UPDATE public.users SET employee_id=:employee_id WHERE user_id=:user_id"),
                    {"employee_id": employee_id, "user_id": access_case["admin_user"]},
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_inactive_state_and_direct_grant_preview_count(client, access_case):
    employee_id = access_case["employee_id"]
    uid = access_case["executor_user_id"]
    headers = auth_headers(access_case["initiator_user_id"])
    with engine.begin() as conn:
        permission_id = int(conn.execute(text("SELECT access_role_id FROM public.access_roles WHERE code='USER_ACCESS_ADMIN'")).scalar_one())
        conn.execute(text("UPDATE public.employees SET is_active=FALSE WHERE employee_id=:employee_id"), {"employee_id": employee_id})
        conn.execute(text("UPDATE public.users SET is_active=FALSE WHERE user_id=:user_id"), {"user_id": uid})
        conn.execute(text("""
            INSERT INTO public.access_grants (access_role_id, target_type, target_id, granted_by_user_id, reason)
            VALUES (:role_id, 'USER', :user_id, :actor_id, 'WP-ACCESS-002 preview count')
        """), {"role_id": permission_id, "user_id": uid, "actor_id": access_case["initiator_user_id"]})
    try:
        state = client.get(f"/directory/personnel/employees/{employee_id}/access", headers=headers)
        assert state.status_code == 200
        assert state.json()["employee_is_active"] is False
        assert state.json()["is_active"] is False
        preview = client.get(f"/directory/personnel/employees/{employee_id}/access/termination-preview", headers=headers)
        assert preview.status_code == 200
        assert preview.json()["counts"]["active_direct_grants_by_target_type"]["USER"] == 1
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM public.access_grants WHERE reason='WP-ACCESS-002 preview count'"))
            conn.execute(text("UPDATE public.employees SET is_active=TRUE WHERE employee_id=:employee_id"), {"employee_id": employee_id})
            conn.execute(text("UPDATE public.users SET is_active=TRUE WHERE user_id=:user_id"), {"user_id": uid})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_completed_personal_and_role_tasks_are_excluded(client, access_case):
    employee_id = access_case["employee_id"]
    uid = access_case["executor_user_id"]
    with engine.begin() as conn:
        onboarding_id = int(conn.execute(text("""
            INSERT INTO public.employee_onboardings (employee_id, status, responsible_hr_id)
            VALUES (:employee_id, 'active', :actor_id) RETURNING onboarding_id
        """), {"employee_id": employee_id, "actor_id": access_case["initiator_user_id"]}).scalar_one())
        for status in ("pending", "completed"):
            conn.execute(text("""
                INSERT INTO public.employee_onboarding_checklist_items
                    (onboarding_id, title, status, assignee_user_id)
                VALUES (:onboarding_id, :title, :status, :user_id)
            """), {"onboarding_id": onboarding_id, "title": f"item {status}", "status": status, "user_id": uid})
    create_task(
        period_id=access_case["period_id"], title="role-only task", initiator_user_id=access_case["initiator_user_id"],
        executor_role_id=access_case["executor_role_id"], assignment_scope=access_case["assignment_scope"], status_code="NEW", unit_id=access_case["unit_id"],
    )
    response = client.get(
        f"/directory/personnel/employees/{employee_id}/access/termination-preview",
        headers=auth_headers(access_case["initiator_user_id"]),
    )
    assert response.status_code == 200, response.text
    assert response.json()["counts"]["unfinished_personal_tasks"] == 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_preview_marks_missing_optional_source_unavailable(client, access_case, monkeypatch):
    original = employee_access_read_service._table_exists

    def table_exists_except_notifications(conn, table):
        if table == "notifications":
            return False
        return original(conn, table)

    monkeypatch.setattr(employee_access_read_service, "_table_exists", table_exists_except_notifications)
    response = client.get(
        f"/directory/personnel/employees/{access_case['employee_id']}/access/termination-preview",
        headers=auth_headers(access_case["initiator_user_id"]),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["counts"]["pending_notifications_deliveries"] is None
    assert body["counts"]["dependency_status"]["pending_notifications_deliveries"] == "unavailable"
    assert "DEPENDENCY_SOURCE_UNAVAILABLE:pending_notifications_deliveries" in body["warnings"]


def test_permission_migration_has_no_automatic_grants():
    source = open("alembic/versions/ua002_user_access_admin_permission.py", encoding="utf-8").read()
    assert "down_revision = \"adm001canonicalroles\"" in source
    assert "INSERT INTO public.access_grants" not in source
    assert "USER_ACCESS_ADMIN" in source
