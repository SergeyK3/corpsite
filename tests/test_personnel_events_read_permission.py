"""Narrow PERSONNEL_EVENTS_READ contract for the personnel event journal."""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.access_grant_service import grant_access
from app.services.personnel_event_visibility_service import create_event_visibility_assignment
from tests.conftest import auth_headers, create_role, insert_returning_id, table_exists
from tests.test_adr042_role_targeted_grants import _create_user, _db_available


def _role_id(conn, code: str) -> int:
    value = conn.execute(
        text("SELECT access_role_id FROM public.access_roles WHERE code = :code"),
        {"code": code},
    ).scalar_one_or_none()
    if value is None:
        pytest.skip("PERSONNEL_EVENTS_READ migration is not applied")
    return int(value)


def _cleanup(created: dict, *, event_visibility_ids: list[int], extra_employee_id: int | None, extra_person_id: int | None, extra_unit_id: int | None) -> None:
    with engine.begin() as conn:
        if table_exists(conn, "employee_events"):
            employee_ids = [value for value in (created.get("employee_id"), extra_employee_id) if value]
            if employee_ids:
                conn.execute(text("DELETE FROM public.employee_events WHERE employee_id = ANY(:ids)"), {"ids": employee_ids})
        for assignment_id in event_visibility_ids:
            conn.execute(
                text("DELETE FROM public.personnel_event_visibility_assignments WHERE assignment_id = :id"),
                {"id": assignment_id},
            )
        if created.get("user_id"):
            conn.execute(text("DELETE FROM public.access_grants WHERE target_type = 'USER' AND target_id = :id"), {"id": created["user_id"]})
            conn.execute(text("DELETE FROM public.users WHERE user_id = :id"), {"id": created["user_id"]})
        if created.get("employee_id"):
            conn.execute(text("DELETE FROM public.employee_assignment_links WHERE employee_id = :id"), {"id": created["employee_id"]})
            conn.execute(text("DELETE FROM public.employees WHERE employee_id = :id"), {"id": created["employee_id"]})
        if created.get("person_id"):
            conn.execute(text("DELETE FROM public.persons WHERE person_id = :id"), {"id": created["person_id"]})
        if extra_employee_id is not None:
            conn.execute(text("DELETE FROM public.employee_assignment_links WHERE employee_id = :id"), {"id": extra_employee_id})
            conn.execute(text("DELETE FROM public.employees WHERE employee_id = :id"), {"id": extra_employee_id})
        if extra_person_id is not None:
            conn.execute(text("DELETE FROM public.persons WHERE person_id = :id"), {"id": extra_person_id})
        if extra_unit_id is not None:
            conn.execute(text("DELETE FROM public.org_units WHERE unit_id = :id"), {"id": extra_unit_id})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_personnel_events_read_is_scoped_read_only_and_preserves_personnel_admin(client, seed):
    """A direct OBSERVER grant needs its event-only scope, not PPR visibility."""
    required = ("access_roles", "access_grants", "personnel_event_visibility_assignments", "employee_events")
    with engine.connect() as conn:
        if any(not table_exists(conn, table) for table in required):
            pytest.skip("personnel events read prerequisites are unavailable")

    suffix = uuid4().hex[:8]
    created: dict = {}
    event_visibility_ids: list[int] = []
    extra_employee_id: int | None = None
    extra_person_id: int | None = None
    extra_unit_id: int | None = None
    visible_event_id: int | None = None
    hidden_event_id: int | None = None
    temp_role_id: int | None = None

    with engine.begin() as conn:
        temp_role_id = create_role(conn, f"pytest_events_observer_{suffix}")
        created = _create_user(conn, seed, role_id=temp_role_id, suffix=f"events_{suffix}")
        permission_id = _role_id(conn, "PERSONNEL_EVENTS_READ")
        assert conn.execute(
            text("SELECT COUNT(*) FROM public.access_grants WHERE access_role_id = :id AND active_flag = TRUE"),
            {"id": permission_id},
        ).scalar_one() == 0
        extra_unit_id = insert_returning_id(
            conn,
            table="org_units",
            id_col="unit_id",
            values={"name": f"pytest events hidden unit {suffix}", "code": f"pev{suffix[:6]}", "is_active": True},
        )
        extra_person_id = insert_returning_id(
            conn,
            table="persons",
            id_col="person_id",
            values={"full_name": f"Events Hidden {suffix}", "match_key": f"events-hidden:{suffix}", "source": "manual", "person_status": "active"},
        )
        extra_employee_id = insert_returning_id(
            conn,
            table="employees",
            id_col="employee_id",
            values={"full_name": f"Events Hidden {suffix}", "person_id": extra_person_id, "org_unit_id": extra_unit_id, "is_active": True, "operational_status": "active", "enrollment_source": "manual_emergency"},
        )
        visible_event_id = insert_returning_id(
            conn,
            table="employee_events",
            id_col="event_id",
            values={"employee_id": created["employee_id"], "event_type": "HIRE", "effective_date": date(2026, 9, 20), "to_org_unit_id": seed["unit_id"], "created_by": seed["initiator_user_id"]},
        )
        hidden_event_id = insert_returning_id(
            conn,
            table="employee_events",
            id_col="event_id",
            values={"employee_id": extra_employee_id, "event_type": "HIRE", "effective_date": date(2026, 9, 20), "to_org_unit_id": extra_unit_id, "created_by": seed["initiator_user_id"]},
        )

    try:
        grant_access(
            access_role_id=permission_id,
            target_type="USER",
            target_id=created["user_id"],
            granted_by_user_id=seed["initiator_user_id"],
            reason="pytest narrow personnel events observer",
        )

        # Permission alone is insufficient: it does not supply event visibility.
        denied = client.get("/directory/personnel-events", headers=auth_headers(created["user_id"]))
        assert denied.status_code == 403, denied.text
        assert client.get("/directory/hr-event-registry", headers=auth_headers(created["user_id"])).status_code == 403

        event_visibility = create_event_visibility_assignment(
            target_user_id=created["user_id"],
            scope_type="DEPARTMENT",
            scope_department_id=seed["unit_id"],
            created_by_user_id=seed["initiator_user_id"],
        )
        event_visibility_ids.append(int(event_visibility["assignment_id"]))
        headers = auth_headers(created["user_id"])

        journal = client.get("/directory/personnel-events", headers=headers)
        assert journal.status_code == 200, journal.text
        event_ids = {item["event_id"] for item in journal.json()["items"]}
        assert visible_event_id in event_ids
        assert hidden_event_id not in event_ids
        assert client.get("/directory/hr-event-registry", headers=headers).status_code == 200
        me = client.get("/auth/me", headers=headers)
        assert me.status_code == 200
        assert me.json().get("has_personnel_events_read") is True
        assert me.json().get("has_personnel_admin") is False
        assert me.json().get("has_personnel_visibility") is False
        assert client.get("/directory/employees", headers=headers).status_code == 403
        assert client.get(f"/api/ppr/persons/{created['person_id']}/contacts", headers=headers).status_code == 403

        # Neither a JSON/query employee id nor the observer grant opens writers/admin APIs.
        write = client.post(
            f"/directory/employees/{created['employee_id']}/personnel-events",
            json={"event_type": "TRANSFER", "effective_date": "2026-09-20"},
            headers=headers,
        )
        assert write.status_code == 403, write.text
        assert client.get("/admin/personnel/events", headers=headers).status_code == 403
        assert client.post("/directory/personnel-events", headers=headers).status_code == 405
        assert client.post("/directory/hr-event-registry", headers=headers).status_code == 405

        # An organization event scope sees both event locations but still does
        # not create a generic personnel/PPR visibility assignment.
        organization_scope = create_event_visibility_assignment(
            target_user_id=created["user_id"],
            scope_type="ORGANIZATION",
            created_by_user_id=seed["initiator_user_id"],
        )
        event_visibility_ids.append(int(organization_scope["assignment_id"]))
        all_journal = client.get("/directory/personnel-events", headers=headers)
        assert all_journal.status_code == 200, all_journal.text
        assert hidden_event_id in {item["event_id"] for item in all_journal.json()["items"]}
        with engine.connect() as conn:
            assert conn.execute(
                text("SELECT COUNT(*) FROM public.personnel_visibility_assignments WHERE target_user_id = :id"),
                {"id": created["user_id"]},
            ).scalar_one() == 0

        # Existing HR enrollment/personnel-admin access remains accepted.
        with engine.begin() as conn:
            hr_role_id = _role_id(conn, "HR_ENROLLMENT_MANAGER")
        grant_access(
            access_role_id=hr_role_id,
            target_type="USER",
            target_id=created["user_id"],
            granted_by_user_id=seed["initiator_user_id"],
            reason="pytest existing personnel-admin compatibility",
        )
        assert client.get("/directory/personnel-events", headers=headers).status_code == 200
    finally:
        _cleanup(
            created,
            event_visibility_ids=event_visibility_ids,
            extra_employee_id=extra_employee_id,
            extra_person_id=extra_person_id,
            extra_unit_id=extra_unit_id,
        )
        if temp_role_id is not None:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM public.roles WHERE role_id = :id"), {"id": temp_role_id})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_personnel_events_read_requires_authentication(client):
    assert client.get("/directory/personnel-events").status_code == 401
    assert client.get("/directory/hr-event-registry").status_code == 401
