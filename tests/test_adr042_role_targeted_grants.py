# tests/test_adr042_role_targeted_grants.py
"""Tests for ADR-042 ROLE-targeted access_grants (DEP_ADMIN backport)."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.security.admin_permissions import has_any_personnel_read_permission
from app.services.access_grant_service import grant_access, revoke_access
from app.services.access_resolver_service import list_active_access_role_codes, resolve_effective_access
from tests.conftest import auth_headers, create_role, get_columns, insert_returning_id, table_exists


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_b2() -> None:
    with engine.begin() as conn:
        for table in ("access_roles", "access_grants", "persons", "employees", "roles"):
            if not table_exists(conn, table):
                pytest.skip(f"ADR-042 B2 table missing: {table}")


def _role_target_type_allowed() -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT pg_get_constraintdef(c.oid) AS def
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE n.nspname = 'public'
                  AND t.relname = 'access_grants'
                  AND c.conname = 'chk_ag_target_type'
                LIMIT 1
                """
            )
        ).mappings().first()
    if not row or not row.get("def"):
        return False
    return "ROLE" in str(row["def"])


def _get_access_role_id(conn, code: str) -> int:
    row = conn.execute(
        text("SELECT access_role_id FROM public.access_roles WHERE code = :code LIMIT 1"),
        {"code": code},
    ).scalar_one()
    return int(row)


def _create_user(conn, seed, *, role_id: int, suffix: str) -> dict:
    person_id = insert_returning_id(
        conn,
        table="persons",
        id_col="person_id",
        values={
            "full_name": f"Role Grant Person {suffix}",
            "match_key": f"name:role grant person {suffix}",
            "source": "manual",
            "person_status": "active",
        },
    )
    emp_values = {
        "full_name": f"Role Grant Person {suffix}",
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
    user_id = insert_returning_id(
        conn,
        table="users",
        id_col="user_id",
        values={
            "full_name": f"Role Grant User {suffix}",
            "google_login": f"role_grant_{suffix}@pytest.local",
            "login": f"role_grant_{suffix}@pytest.local",
            "role_id": int(role_id),
            "unit_id": int(seed["unit_id"]),
            "employee_id": employee_id,
            "is_active": True,
        },
    )
    return {
        "person_id": person_id,
        "employee_id": employee_id,
        "user_id": user_id,
        "role_id": int(role_id),
    }


def _cleanup(created: dict, *, role_grant_ids: list[int] | None = None) -> None:
    with engine.begin() as conn:
        if role_grant_ids and table_exists(conn, "access_grants"):
            for gid in role_grant_ids:
                conn.execute(
                    text("DELETE FROM public.access_grants WHERE grant_id = :gid"),
                    {"gid": int(gid)},
                )
        if table_exists(conn, "access_grants"):
            if created.get("user_id"):
                conn.execute(
                    text(
                        "DELETE FROM public.access_grants "
                        "WHERE target_type = 'USER' AND target_id = :id"
                    ),
                    {"id": created["user_id"]},
                )
            if created.get("role_id"):
                conn.execute(
                    text(
                        "DELETE FROM public.access_grants "
                        "WHERE target_type = 'ROLE' AND target_id = :id"
                    ),
                    {"id": created["role_id"]},
                )
        if created.get("user_id"):
            conn.execute(text("DELETE FROM public.users WHERE user_id = :id"), {"id": created["user_id"]})
        if created.get("employee_id"):
            conn.execute(
                text("DELETE FROM public.employee_assignment_links WHERE employee_id = :id"),
                {"id": created["employee_id"]},
            )
            conn.execute(text("DELETE FROM public.employees WHERE employee_id = :id"), {"id": created["employee_id"]})
        if created.get("person_id"):
            conn.execute(text("DELETE FROM public.persons WHERE person_id = :id"), {"id": created["person_id"]})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_role_grant_resolves_hr_enrollment_manager(seed):
    _require_b2()
    if not _role_target_type_allowed():
        pytest.skip("Migration i8j9k0l1m2n3 not applied (ROLE target_type unavailable)")

    suffix = uuid4().hex[:8]
    grant_id: int | None = None
    created: dict = {}

    with engine.begin() as conn:
        dep_admin_role_id = create_role(conn, f"pytest_dep_admin_{suffix}")
        created = _create_user(conn, seed, role_id=dep_admin_role_id, suffix=suffix)
        hr_role_id = _get_access_role_id(conn, "HR_ENROLLMENT_MANAGER")

    granted = grant_access(
        access_role_id=hr_role_id,
        target_type="ROLE",
        target_id=created["role_id"],
        granted_by_user_id=int(seed["initiator_user_id"]),
        reason="pytest role grant",
    )
    grant_id = int(granted["grant_id"])

    codes = list_active_access_role_codes(created["user_id"])
    assert "HR_ENROLLMENT_MANAGER" in codes

    result = resolve_effective_access(created["user_id"])
    assert result["effective_role_code"] == "HR_ENROLLMENT_MANAGER"
    assert result["access_level"] == "MANAGER"
    assert any(g["target_type"] == "ROLE" for g in result["matched_grants"])

    try:
        pass
    finally:
        _cleanup(created, role_grant_ids=[grant_id] if grant_id else None)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM public.roles WHERE role_id = :rid"), {"rid": created["role_id"]})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_auth_me_has_personnel_admin_via_role_grant(client: TestClient, seed):
    _require_b2()
    if not _role_target_type_allowed():
        pytest.skip("Migration i8j9k0l1m2n3 not applied (ROLE target_type unavailable)")

    suffix = uuid4().hex[:8]
    grant_id: int | None = None
    created: dict = {}

    with engine.begin() as conn:
        dep_admin_role_id = create_role(conn, f"pytest_dep_admin_me_{suffix}")
        created = _create_user(conn, seed, role_id=dep_admin_role_id, suffix=suffix)
        hr_role_id = _get_access_role_id(conn, "HR_ENROLLMENT_MANAGER")

    granted = grant_access(
        access_role_id=hr_role_id,
        target_type="ROLE",
        target_id=created["role_id"],
        granted_by_user_id=int(seed["initiator_user_id"]),
    )
    grant_id = int(granted["grant_id"])

    try:
        resp = client.get("/auth/me", headers=auth_headers(created["user_id"]))
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("has_personnel_admin") is True
        assert has_any_personnel_read_permission(created["user_id"]) is True
    finally:
        _cleanup(created, role_grant_ids=[grant_id] if grant_id else None)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM public.roles WHERE role_id = :rid"), {"rid": created["role_id"]})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_role_grant_not_applied_to_other_roles(seed):
    _require_b2()
    if not _role_target_type_allowed():
        pytest.skip("Migration i8j9k0l1m2n3 not applied (ROLE target_type unavailable)")

    suffix = uuid4().hex[:8]
    grant_id: int | None = None
    dep_admin: dict = {}
    other_user: dict = {}

    with engine.begin() as conn:
        dep_admin_role_id = create_role(conn, f"pytest_dep_admin_only_{suffix}")
        other_role_id = int(seed["executor_role_id"])
        dep_admin = _create_user(conn, seed, role_id=dep_admin_role_id, suffix=f"dep_{suffix}")
        other_user = _create_user(conn, seed, role_id=other_role_id, suffix=f"other_{suffix}")
        hr_role_id = _get_access_role_id(conn, "HR_ENROLLMENT_MANAGER")

    granted = grant_access(
        access_role_id=hr_role_id,
        target_type="ROLE",
        target_id=dep_admin["role_id"],
        granted_by_user_id=int(seed["initiator_user_id"]),
    )
    grant_id = int(granted["grant_id"])

    try:
        assert "HR_ENROLLMENT_MANAGER" in list_active_access_role_codes(dep_admin["user_id"])
        assert "HR_ENROLLMENT_MANAGER" not in list_active_access_role_codes(other_user["user_id"])
    finally:
        _cleanup(dep_admin, role_grant_ids=[grant_id] if grant_id else None)
        _cleanup(other_user)
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public.roles WHERE role_id = :rid"),
                {"rid": dep_admin["role_id"]},
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_user_grant_still_works_alongside_role_grant(seed):
    _require_b2()
    if not _role_target_type_allowed():
        pytest.skip("Migration i8j9k0l1m2n3 not applied (ROLE target_type unavailable)")

    suffix = uuid4().hex[:8]
    role_grant_id: int | None = None
    user_grant_id: int | None = None
    created: dict = {}

    with engine.begin() as conn:
        role_id = create_role(conn, f"pytest_mixed_{suffix}")
        created = _create_user(conn, seed, role_id=role_id, suffix=suffix)
        observer_id = _get_access_role_id(conn, "ACCESS_OBSERVER")
        admin_id = _get_access_role_id(conn, "ACCESS_ADMIN")

    role_granted = grant_access(
        access_role_id=observer_id,
        target_type="ROLE",
        target_id=created["role_id"],
        granted_by_user_id=int(seed["initiator_user_id"]),
    )
    role_grant_id = int(role_granted["grant_id"])

    user_granted = grant_access(
        access_role_id=admin_id,
        target_type="USER",
        target_id=created["user_id"],
        granted_by_user_id=int(seed["initiator_user_id"]),
    )
    user_grant_id = int(user_granted["grant_id"])

    try:
        result = resolve_effective_access(created["user_id"])
        assert result["access_level"] == "ADMIN"
        assert result["level_rank"] == 30
        matched_types = {g["target_type"] for g in result["matched_grants"]}
        assert "USER" in matched_types
    finally:
        _cleanup(
            created,
            role_grant_ids=[gid for gid in (role_grant_id, user_grant_id) if gid],
        )
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM public.roles WHERE role_id = :rid"), {"rid": created["role_id"]})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_revoked_and_inactive_role_grants_ignored(seed):
    _require_b2()
    if not _role_target_type_allowed():
        pytest.skip("Migration i8j9k0l1m2n3 not applied (ROLE target_type unavailable)")

    suffix = uuid4().hex[:8]
    active_grant_id: int | None = None
    created: dict = {}

    with engine.begin() as conn:
        role_id = create_role(conn, f"pytest_revoked_role_{suffix}")
        created = _create_user(conn, seed, role_id=role_id, suffix=suffix)
        hr_role_id = _get_access_role_id(conn, "HR_ENROLLMENT_MANAGER")

    active = grant_access(
        access_role_id=hr_role_id,
        target_type="ROLE",
        target_id=created["role_id"],
        granted_by_user_id=int(seed["initiator_user_id"]),
    )
    active_grant_id = int(active["grant_id"])
    assert "HR_ENROLLMENT_MANAGER" in list_active_access_role_codes(created["user_id"])

    revoke_access(
        grant_id=active_grant_id,
        revoked_by_user_id=int(seed["initiator_user_id"]),
    )

    assert "HR_ENROLLMENT_MANAGER" not in list_active_access_role_codes(created["user_id"])

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO public.access_grants (
                    access_role_id, target_type, target_id, resource_key,
                    scope_type, active_flag, granted_by_user_id,
                    revoked_at
                )
                VALUES (
                    :role_id, 'ROLE', :target_role_id, '*', 'GLOBAL',
                    FALSE, :actor, now()
                )
                """
            ),
            {
                "role_id": hr_role_id,
                "target_role_id": created["role_id"],
                "actor": int(seed["initiator_user_id"]),
            },
        )

    assert "HR_ENROLLMENT_MANAGER" not in list_active_access_role_codes(created["user_id"])

    try:
        pass
    finally:
        _cleanup(created, role_grant_ids=[active_grant_id] if active_grant_id else None)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM public.roles WHERE role_id = :rid"), {"rid": created["role_id"]})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_directory_privileged_role_denied_sysadmin_api_legacy_mode(
    client: TestClient,
    seed,
    monkeypatch,
):
    """DIRECTORY_PRIVILEGED_ROLE_IDS must not open sysadmin API after guard split."""
    _require_b2()
    suffix = uuid4().hex[:8]
    created: dict = {}

    with engine.begin() as conn:
        dep_admin_role_id = create_role(conn, f"pytest_privileged_gap_{suffix}")
        created = _create_user(conn, seed, role_id=dep_admin_role_id, suffix=suffix)

    monkeypatch.setenv("ADR042_ADMIN_GUARD_MODE", "legacy")
    monkeypatch.delenv("DIRECTORY_PRIVILEGED_USER_IDS", raising=False)
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_ROLE_IDS", str(created["role_id"]))

    headers = auth_headers(created["user_id"])
    try:
        resp = client.get("/auth/me", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("is_privileged") is True
        assert body.get("has_sysadmin_api") is False

        admin_resp = client.get("/admin/users", headers=headers, params={"limit": 5})
        assert admin_resp.status_code == 403
    finally:
        _cleanup(created)
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public.roles WHERE role_id = :rid"),
                {"rid": created["role_id"]},
            )
