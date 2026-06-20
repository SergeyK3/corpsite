# tests/test_adr042_phase_b3_access_resolver.py
"""Tests for ADR-042 Phase B3 access resolver and grant services."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.access_grant_service import grant_access, list_access_grants, revoke_access
from app.services.access_resolver_service import (
    explain_effective_access,
    resolve_effective_access,
    resolve_person_access,
)
from tests.conftest import get_columns, insert_returning_id, table_exists


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_b2() -> None:
    with engine.begin() as conn:
        for table in ("access_roles", "access_grants", "persons", "employees"):
            if not table_exists(conn, table):
                pytest.skip(f"ADR-042 B2 table missing: {table}")


def _get_access_role_id(conn, code: str) -> int:
    row = conn.execute(
        text("SELECT access_role_id FROM public.access_roles WHERE code = :code LIMIT 1"),
        {"code": code},
    ).scalar_one()
    return int(row)


def _create_person_employee_user(conn, seed, suffix: str) -> dict:
    person_id = insert_returning_id(
        conn,
        table="persons",
        id_col="person_id",
        values={
            "full_name": f"B3 Person {suffix}",
            "match_key": f"name:b3 person {suffix}",
            "source": "manual",
            "person_status": "active",
        },
    )
    emp_values = {
        "full_name": f"B3 Person {suffix}",
        "person_id": person_id,
        "org_unit_id": int(seed["unit_id"]),
        "is_active": True,
        "operational_status": "active",
        "enrollment_source": "manual_emergency",
    }
    cols = get_columns(conn, "employees")
    if "employment_rate" in cols:
        emp_values["employment_rate"] = 1.0
    employee_id = insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values=emp_values,
    )
    pos_id = conn.execute(
        text("SELECT position_id FROM public.positions ORDER BY position_id LIMIT 1")
    ).scalar_one()
    assignment_id = insert_returning_id(
        conn,
        table="person_assignments",
        id_col="assignment_id",
        values={
            "person_id": person_id,
            "org_unit_id": int(seed["unit_id"]),
            "position_id": int(pos_id),
            "employment_type": "primary",
            "rate": 1.0,
            "start_date": "2026-01-01",
            "active_flag": True,
            "is_primary": True,
            "lifecycle_status": "active",
            "assignment_key": f"{seed['unit_id']}|{pos_id}|primary|2026-01-01",
            "source": "manual",
        },
    )
    user_id = insert_returning_id(
        conn,
        table="users",
        id_col="user_id",
        values={
            "full_name": f"B3 User {suffix}",
            "google_login": f"b3_{suffix}@pytest.local",
            "login": f"b3_{suffix}@pytest.local",
            "role_id": int(seed["executor_role_id"]),
            "unit_id": int(seed["unit_id"]),
            "employee_id": employee_id,
            "is_active": True,
        },
    )
    return {
        "person_id": person_id,
        "employee_id": employee_id,
        "user_id": user_id,
        "assignment_id": assignment_id,
        "position_id": int(pos_id),
    }


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_user_grant_resolves_max_rank(seed):
    _require_b2()
    suffix = uuid4().hex[:8]
    created: dict = {}

    with engine.begin() as conn:
        created = _create_person_employee_user(conn, seed, suffix)
        observer_id = _get_access_role_id(conn, "ACCESS_OBSERVER")
        admin_id = _get_access_role_id(conn, "ACCESS_ADMIN")

    grant_access(
        access_role_id=observer_id,
        target_type="USER",
        target_id=created["user_id"],
        granted_by_user_id=int(seed["initiator_user_id"]),
    )
    grant_access(
        access_role_id=admin_id,
        target_type="USER",
        target_id=created["user_id"],
        granted_by_user_id=int(seed["initiator_user_id"]),
    )

    result = resolve_effective_access(created["user_id"])
    assert result["access_level"] == "ADMIN"
    assert result["level_rank"] == 30

    explained = explain_effective_access(user_id=created["user_id"])
    assert explained["explain_mode"] == "user"
    assert "steps" in explained["explanation"]

    grants = list_access_grants(target_type="USER", target_id=created["user_id"])
    for item in grants["items"]:
        revoke_access(grant_id=int(item["grant_id"]), revoked_by_user_id=int(seed["initiator_user_id"]))

    _cleanup(created, initiator_user_id=int(seed["initiator_user_id"]))


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_position_and_org_unit_inherited_grants(seed):
    _require_b2()
    suffix = uuid4().hex[:8]

    with engine.begin() as conn:
        created = _create_person_employee_user(conn, seed, suffix)
        manager_id = _get_access_role_id(conn, "ACCESS_MANAGER")

    grant_access(
        access_role_id=manager_id,
        target_type="POSITION",
        target_id=created["position_id"],
        granted_by_user_id=int(seed["initiator_user_id"]),
    )
    grant_access(
        access_role_id=manager_id,
        target_type="ORG_UNIT",
        target_id=int(seed["unit_id"]),
        granted_by_user_id=int(seed["initiator_user_id"]),
    )

    person_result = resolve_person_access(created["person_id"])
    assert person_result["level_rank"] == 20
    assert person_result["access_level"] == "MANAGER"

    grants = list_access_grants(active_only=True, limit=500)
    for item in grants["items"]:
        if item["target_type"] in ("POSITION", "ORG_UNIT") and int(item["target_id"]) in (
            created["position_id"],
            int(seed["unit_id"]),
        ):
            revoke_access(grant_id=int(item["grant_id"]), revoked_by_user_id=int(seed["initiator_user_id"]))

    _cleanup(created, initiator_user_id=int(seed["initiator_user_id"]))


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_revoked_grant_ignored_and_audit_written(seed):
    _require_b2()
    suffix = uuid4().hex[:8]

    with engine.begin() as conn:
        created = _create_person_employee_user(conn, seed, suffix)
        observer_id = _get_access_role_id(conn, "ACCESS_OBSERVER")

    granted = grant_access(
        access_role_id=observer_id,
        target_type="EMPLOYEE",
        target_id=created["employee_id"],
        granted_by_user_id=int(seed["initiator_user_id"]),
    )
    assert granted.get("audit_id")

    revoked = revoke_access(
        grant_id=int(granted["grant_id"]),
        revoked_by_user_id=int(seed["initiator_user_id"]),
    )
    assert revoked.get("audit_id")

    result = resolve_effective_access(created["user_id"])
    assert result["level_rank"] == 0
    assert result["access_level"] == "NONE"

    _cleanup(created, initiator_user_id=int(seed["initiator_user_id"]))


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_expired_grant_ignored(seed):
    _require_b2()
    suffix = uuid4().hex[:8]

    with engine.begin() as conn:
        created = _create_person_employee_user(conn, seed, suffix)
        observer_id = _get_access_role_id(conn, "ACCESS_OBSERVER")

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO public.access_grants (
                    access_role_id, target_type, target_id, resource_key,
                    scope_type, starts_at, ends_at, active_flag,
                    granted_by_user_id
                )
                VALUES (
                    :role_id, 'USER', :user_id, '*', 'GLOBAL',
                    now() - interval '2 days', now() - interval '1 day',
                    TRUE, :actor
                )
                """
            ),
            {
                "role_id": observer_id,
                "user_id": created["user_id"],
                "actor": int(seed["initiator_user_id"]),
            },
        )

    result = resolve_effective_access(created["user_id"])
    assert result["level_rank"] == 0

    _cleanup(created, initiator_user_id=int(seed["initiator_user_id"]))


def _cleanup(created: dict, initiator_user_id: int | None = None) -> None:
    with engine.begin() as conn:
        if table_exists(conn, "access_grants"):
            if created.get("user_id"):
                conn.execute(
                    text("DELETE FROM public.access_grants WHERE target_type = 'USER' AND target_id = :id"),
                    {"id": created["user_id"]},
                )
            if created.get("employee_id"):
                conn.execute(
                    text(
                        "DELETE FROM public.access_grants "
                        "WHERE target_type = 'EMPLOYEE' AND target_id = :id"
                    ),
                    {"id": created["employee_id"]},
                )
            if created.get("position_id"):
                conn.execute(
                    text(
                        "DELETE FROM public.access_grants "
                        "WHERE target_type = 'POSITION' AND target_id = :id"
                    ),
                    {"id": created["position_id"]},
                )
            if initiator_user_id is not None:
                conn.execute(
                    text("DELETE FROM public.access_grants WHERE granted_by_user_id = :uid"),
                    {"uid": initiator_user_id},
                )
                conn.execute(
                    text("DELETE FROM public.access_grants WHERE revoked_by_user_id = :uid"),
                    {"uid": initiator_user_id},
                )
        if table_exists(conn, "security_audit_log") and initiator_user_id is not None:
            conn.execute(
                text("DELETE FROM public.security_audit_log WHERE actor_user_id = :uid"),
                {"uid": initiator_user_id},
            )
        if created.get("user_id"):
            conn.execute(text("DELETE FROM public.users WHERE user_id = :id"), {"id": created["user_id"]})
        if created.get("employee_id"):
            conn.execute(
                text("DELETE FROM public.employee_assignment_links WHERE employee_id = :id"),
                {"id": created["employee_id"]},
            )
            conn.execute(text("DELETE FROM public.employees WHERE employee_id = :id"), {"id": created["employee_id"]})
        if created.get("assignment_id"):
            conn.execute(
                text("DELETE FROM public.person_assignments WHERE assignment_id = :id"),
                {"id": created["assignment_id"]},
            )
        if created.get("person_id"):
            conn.execute(text("DELETE FROM public.persons WHERE person_id = :id"), {"id": created["person_id"]})
