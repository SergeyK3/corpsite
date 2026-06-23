# tests/test_adr042_admin_guard_split.py
"""Tests for ADR-042 / ADR-045 admin guard split (directory privileged ≠ sysadmin API)."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.security.directory_scope import SYSTEM_ADMIN_ROLE_ID
from app.services.access_grant_service import grant_access
from tests.conftest import auth_headers, create_role, create_user, get_columns, insert_returning_id, table_exists


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_b2() -> None:
    with engine.begin() as conn:
        for table in ("access_roles", "access_grants", "persons", "employees", "roles", "users"):
            if not table_exists(conn, table):
                pytest.skip(f"ADR-042 B2 table missing: {table}")


def _require_c4() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_lifecycle_runs"):
            pytest.skip("ADR-043 Phase C4 tables missing — run: alembic upgrade head")


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


def _ensure_system_admin_role(conn) -> None:
    cols = get_columns(conn, "roles")
    exists = conn.execute(
        text("SELECT 1 FROM public.roles WHERE role_id = :rid LIMIT 1"),
        {"rid": SYSTEM_ADMIN_ROLE_ID},
    ).first()
    if exists:
        return
    values: dict = {"role_id": SYSTEM_ADMIN_ROLE_ID, "name": "pytest_system_admin"}
    if "code" in cols:
        values["code"] = "SYSTEM_ADMIN"
    if "created_at" in cols:
        from tests.conftest import utcnow

        values["created_at"] = utcnow()
    insert_returning_id(conn, table="roles", id_col="role_id", values=values)


def _create_dep_admin_user(conn, seed, suffix: str) -> dict:
    dep_admin_role_id = create_role(conn, f"pytest_dep_admin_{suffix}")
    person_id = insert_returning_id(
        conn,
        table="persons",
        id_col="person_id",
        values={
            "full_name": f"Guard Split Person {suffix}",
            "match_key": f"name:guard split person {suffix}",
            "source": "manual",
            "person_status": "active",
        },
    )
    emp_values = {
        "full_name": f"Guard Split Person {suffix}",
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
            "full_name": f"Guard Split User {suffix}",
            "google_login": f"guard_split_{suffix}@pytest.local",
            "login": f"guard_split_{suffix}@pytest.local",
            "role_id": int(dep_admin_role_id),
            "unit_id": int(seed["unit_id"]),
            "employee_id": employee_id,
            "is_active": True,
        },
    )
    return {
        "person_id": person_id,
        "employee_id": employee_id,
        "user_id": user_id,
        "role_id": int(dep_admin_role_id),
    }


def _cleanup_user_bundle(created: dict, *, grant_ids: list[int] | None = None) -> None:
    with engine.begin() as conn:
        if grant_ids and table_exists(conn, "access_grants"):
            for gid in grant_ids:
                conn.execute(
                    text("DELETE FROM public.access_grants WHERE grant_id = :gid"),
                    {"gid": int(gid)},
                )
        if table_exists(conn, "access_grants") and created.get("role_id"):
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
        if created.get("role_id"):
            conn.execute(text("DELETE FROM public.roles WHERE role_id = :rid"), {"rid": created["role_id"]})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_dep_admin_privileged_role_denied_sysadmin_api(client: TestClient, seed, monkeypatch):
    """DEP_ADMIN: directory privileged + HR ROLE grant, no sysadmin API."""
    _require_b2()
    if not _role_target_type_allowed():
        pytest.skip("ROLE target_type migration not applied")

    suffix = uuid4().hex[:8]
    created: dict = {}
    grant_id: int | None = None

    with engine.begin() as conn:
        created = _create_dep_admin_user(conn, seed, suffix)
        hr_role_id = _get_access_role_id(conn, "HR_ENROLLMENT_MANAGER")

    monkeypatch.setenv("ADR042_ADMIN_GUARD_MODE", "legacy")
    monkeypatch.delenv("DIRECTORY_PRIVILEGED_USER_IDS", raising=False)
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_ROLE_IDS", str(created["role_id"]))

    granted = grant_access(
        access_role_id=hr_role_id,
        target_type="ROLE",
        target_id=created["role_id"],
        granted_by_user_id=int(seed["initiator_user_id"]),
    )
    grant_id = int(granted["grant_id"])
    headers = auth_headers(created["user_id"])

    try:
        me = client.get("/auth/me", headers=headers)
        assert me.status_code == 200
        body = me.json()
        assert body.get("is_privileged") is True
        assert body.get("is_system_admin") is False
        assert body.get("has_personnel_admin") is True
        assert body.get("has_hr_governance") is True
        assert body.get("has_sysadmin_api") is False

        assert client.get("/admin/users", headers=headers, params={"limit": 5}).status_code == 403
        assert client.get("/admin/access/grants", headers=headers, params={"limit": 5}).status_code == 403
    finally:
        _cleanup_user_bundle(created, grant_ids=[grant_id] if grant_id else None)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_dep_admin_can_access_personnel_admin_api(client: TestClient, seed, monkeypatch):
    _require_b2()
    _require_c4()
    if not _role_target_type_allowed():
        pytest.skip("ROLE target_type migration not applied")

    suffix = uuid4().hex[:8]
    created: dict = {}
    grant_id: int | None = None

    with engine.begin() as conn:
        created = _create_dep_admin_user(conn, seed, suffix)
        hr_role_id = _get_access_role_id(conn, "HR_ENROLLMENT_MANAGER")

    monkeypatch.setenv("DIRECTORY_PRIVILEGED_ROLE_IDS", str(created["role_id"]))
    monkeypatch.delenv("DIRECTORY_PRIVILEGED_USER_IDS", raising=False)

    granted = grant_access(
        access_role_id=hr_role_id,
        target_type="ROLE",
        target_id=created["role_id"],
        granted_by_user_id=int(seed["initiator_user_id"]),
    )
    grant_id = int(granted["grant_id"])
    headers = auth_headers(created["user_id"])

    try:
        resp = client.get("/admin/personnel/lifecycle/runs", headers=headers, params={"limit": 5})
        assert resp.status_code == 200, resp.text
    finally:
        _cleanup_user_bundle(created, grant_ids=[grant_id] if grant_id else None)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_system_admin_role_gets_sysadmin_api(client: TestClient, seed, monkeypatch):
    _require_b2()
    suffix = uuid4().hex[:8]
    user_id: int | None = None

    monkeypatch.delenv("DIRECTORY_PRIVILEGED_USER_IDS", raising=False)
    monkeypatch.delenv("DIRECTORY_PRIVILEGED_ROLE_IDS", raising=False)

    with engine.begin() as conn:
        _ensure_system_admin_role(conn)
        user_id = create_user(
            conn,
            full_name=f"Pytest Sysadmin {suffix}",
            role_id=SYSTEM_ADMIN_ROLE_ID,
            unit_id=int(seed["unit_id"]),
        )

    headers = auth_headers(user_id)
    try:
        me = client.get("/auth/me", headers=headers)
        assert me.status_code == 200
        assert me.json().get("has_sysadmin_api") is True

        resp = client.get("/admin/users", headers=headers, params={"limit": 5})
        assert resp.status_code == 200
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM public.users WHERE user_id = :uid"), {"uid": user_id})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_break_glass_user_gets_sysadmin_api(client: TestClient, seed, monkeypatch):
    _require_b2()
    monkeypatch.setenv("ADR042_ADMIN_GUARD_MODE", "legacy")
    monkeypatch.delenv("DIRECTORY_PRIVILEGED_ROLE_IDS", raising=False)
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["executor_user_id"]))

    headers = auth_headers(seed["executor_user_id"])
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json().get("has_sysadmin_api") is True

    resp = client.get("/admin/users", headers=headers, params={"limit": 5})
    assert resp.status_code == 200


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_sysadmin_cabinet_grant_opens_admin_api(client: TestClient, seed, monkeypatch):
    _require_b2()
    monkeypatch.setenv("ADR042_ADMIN_GUARD_MODE", "legacy")
    monkeypatch.delenv("DIRECTORY_PRIVILEGED_USER_IDS", raising=False)
    monkeypatch.delenv("DIRECTORY_PRIVILEGED_ROLE_IDS", raising=False)

    grant_id: int | None = None
    with engine.begin() as conn:
        role_id = _get_access_role_id(conn, "SYSADMIN_CABINET")

    granted = grant_access(
        access_role_id=role_id,
        target_type="USER",
        target_id=int(seed["executor_user_id"]),
        granted_by_user_id=int(seed["initiator_user_id"]),
    )
    grant_id = int(granted["grant_id"])
    headers = auth_headers(seed["executor_user_id"])

    try:
        me = client.get("/auth/me", headers=headers)
        assert me.status_code == 200
        assert me.json().get("has_sysadmin_api") is True

        resp = client.get("/admin/users", headers=headers, params={"limit": 5})
        assert resp.status_code == 200
    finally:
        if grant_id is not None:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM public.access_grants WHERE grant_id = :gid"),
                    {"gid": grant_id},
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_access_admin_grant_opens_admin_api(client: TestClient, seed, monkeypatch):
    _require_b2()
    monkeypatch.delenv("DIRECTORY_PRIVILEGED_USER_IDS", raising=False)
    monkeypatch.delenv("DIRECTORY_PRIVILEGED_ROLE_IDS", raising=False)

    grant_id: int | None = None
    with engine.begin() as conn:
        role_id = _get_access_role_id(conn, "ACCESS_ADMIN")

    granted = grant_access(
        access_role_id=role_id,
        target_type="USER",
        target_id=int(seed["executor_user_id"]),
        granted_by_user_id=int(seed["initiator_user_id"]),
    )
    grant_id = int(granted["grant_id"])
    headers = auth_headers(seed["executor_user_id"])

    try:
        resp = client.get("/admin/access/grants", headers=headers, params={"limit": 5})
        assert resp.status_code == 200
    finally:
        if grant_id is not None:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM public.access_grants WHERE grant_id = :gid"),
                    {"gid": grant_id},
                )
