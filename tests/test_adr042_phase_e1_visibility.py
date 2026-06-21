# tests/test_adr042_phase_e1_visibility.py
"""ADR-042 Phase E1 — personnel visibility scope."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from uuid import uuid4

from app.db.engine import engine
from app.services.access_grant_service import grant_access
from app.services.personnel_visibility_resolver_service import resolve_effective_personnel_visibility
from app.services.personnel_visibility_service import (
    create_visibility_assignment,
    list_visibility_assignments,
    revoke_visibility_assignment,
)
from tests.conftest import auth_headers, create_unit, insert_returning_id, table_exists


def _require_e1() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_visibility_assignments"):
            pytest.skip("ADR-042 E1 table missing: personnel_visibility_assignments")


@pytest.fixture
def admin_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def observer_headers(seed):
    return auth_headers(seed["executor_user_id"])


def _create_position(conn) -> int:
    cols = conn.execute(
        text(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'positions'
            """
        )
    ).fetchall()
    col_names = {r[0] for r in cols}
    values = {"name": "E1 Test Position"}
    if "category" in col_names:
        values["category"] = "other"
    return insert_returning_id(conn, table="positions", id_col="position_id", values=values)


def _delete_user(user_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM public.users WHERE user_id = :uid"), {"uid": int(user_id)})


def _cleanup_assignment(assignment_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.personnel_visibility_assignments WHERE assignment_id = :id"),
            {"id": int(assignment_id)},
        )


def test_visibility_assignment_crud_and_audit(admin_headers):
    _require_e1()

    with engine.begin() as conn:
        unit_a = create_unit(conn, "e1_vis_unit_a")
        unit_b = create_unit(conn, "e1_vis_unit_b")
        position_id = _create_position(conn)
        user_id = insert_returning_id(
            conn,
            table="users",
            id_col="user_id",
            values={
                "full_name": "E1 Visibility User",
                "google_login": "e1_vis_user",
                "role_id": 3,
                "unit_id": unit_a,
                "is_active": True,
            },
        )

    created = create_visibility_assignment(
        target_type="USER",
        target_user_id=user_id,
        scope_type="DEPARTMENT",
        scope_department_id=unit_b,
        can_view_personnel=True,
        can_view_tasks=True,
        created_by_user_id=1,
    )
    assignment_id = int(created["assignment_id"])
    try:
        assert created["target_type"] == "USER"
        assert created["can_view_tasks"] is True

        listed = list_visibility_assignments(active_only=True, limit=50)
        assert any(int(i["assignment_id"]) == assignment_id for i in listed["items"])

        revoked = revoke_visibility_assignment(
            assignment_id=assignment_id,
            revoked_by_user_id=1,
            reason="test revoke",
        )
        assert revoked["is_active"] is False
        assert revoked["revoke_reason"] == "test revoke"

        with engine.connect() as conn:
            audit_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM public.security_audit_log
                    WHERE event_type IN ('VISIBILITY_GRANTED', 'VISIBILITY_REVOKED')
                      AND (metadata->>'assignment_id')::bigint = :aid
                    """
                ),
                {"aid": assignment_id},
            ).scalar_one()
        assert int(audit_count) >= 2
    finally:
        _cleanup_assignment(assignment_id)
        _delete_user(user_id)


def test_admin_api_visibility_endpoints(client: TestClient, admin_headers, seed):
    _require_e1()

    with engine.begin() as conn:
        unit_id = create_unit(conn, "e1_api_unit")
        target_user_id = insert_returning_id(
            conn,
            table="users",
            id_col="user_id",
            values={
                "full_name": "E1 API Target",
                "google_login": "e1_api_target",
                "role_id": seed["executor_role_id"],
                "unit_id": unit_id,
                "is_active": True,
            },
        )

    resp = client.post(
        "/admin/personnel/visibility/assignments",
        headers=admin_headers,
        json={
            "target_type": "USER",
            "target_user_id": target_user_id,
            "scope_type": "ORGANIZATION",
            "can_view_personnel": True,
            "can_view_tasks": False,
        },
    )
    assert resp.status_code == 200, resp.text
    assignment_id = int(resp.json()["assignment_id"])

    try:
        list_resp = client.get(
            "/admin/personnel/visibility/assignments",
            headers=admin_headers,
        )
        assert list_resp.status_code == 200
        assert any(int(i["assignment_id"]) == assignment_id for i in list_resp.json()["items"])

        eff_resp = client.get(
            "/admin/personnel/visibility/effective",
            headers=admin_headers,
            params={"user_id": target_user_id},
        )
        assert eff_resp.status_code == 200
        body = eff_resp.json()
        assert body["has_visibility"] is True
        assert body["organization_wide"] is True
        assert body["source"] == "assignment"

        revoke_resp = client.post(
            f"/admin/personnel/visibility/assignments/{assignment_id}/revoke",
            headers=admin_headers,
            json={"reason": "api test"},
        )
        assert revoke_resp.status_code == 200
        assert revoke_resp.json()["is_active"] is False
    finally:
        _cleanup_assignment(assignment_id)
        _delete_user(target_user_id)


def test_observer_without_assignment_has_no_visibility(client: TestClient, observer_headers, seed):
    _require_e1()

    me = client.get("/auth/me", headers=observer_headers)
    assert me.status_code == 200
    body = me.json()
    assert body.get("show_org_sidebar") is not True
    assert body.get("has_personnel_visibility") is not True

    tree = client.get("/directory/org-units/tree", headers=observer_headers)
    assert tree.status_code == 403


def test_user_assignment_enables_directory_read(client: TestClient, admin_headers, seed):
    _require_e1()

    with engine.begin() as conn:
        unit_id = create_unit(conn, "e1_read_unit")
        target_user_id = insert_returning_id(
            conn,
            table="users",
            id_col="user_id",
            values={
                "full_name": "E1 Read User",
                "google_login": "e1_read_user",
                "role_id": seed["executor_role_id"],
                "unit_id": unit_id,
                "is_active": True,
            },
        )

    created = create_visibility_assignment(
        target_type="USER",
        target_user_id=target_user_id,
        scope_type="ORGANIZATION",
        created_by_user_id=seed["initiator_user_id"],
    )
    assignment_id = int(created["assignment_id"])
    target_headers = auth_headers(target_user_id)

    try:
        me = client.get("/auth/me", headers=target_headers)
        assert me.status_code == 200
        assert me.json().get("show_org_sidebar") is True

        tree = client.get("/directory/org-units/tree", headers=target_headers)
        assert tree.status_code == 200, tree.text
    finally:
        _cleanup_assignment(assignment_id)
        _delete_user(target_user_id)


def test_position_target_assignment_resolves(client: TestClient, seed):
    _require_e1()

    with engine.begin() as conn:
        unit_id = create_unit(conn, "e1_pos_unit")
        position_id = _create_position(conn)
        user_id = insert_returning_id(
            conn,
            table="users",
            id_col="user_id",
            values={
                "full_name": "E1 Position User",
                "google_login": "e1_pos_user",
                "role_id": seed["executor_role_id"],
                "unit_id": unit_id,
                "is_active": True,
            },
        )

        person_id = None
        if table_exists(conn, "persons"):
            person_id = insert_returning_id(
                conn,
                table="persons",
                id_col="person_id",
                values={
                    "full_name": "E1 Position Person",
                    "person_status": "active",
                    "match_key": f"name:e1 position {uuid4().hex[:8]}",
                },
            )
            conn.execute(
                text("UPDATE public.users SET employee_id = NULL WHERE user_id = :uid"),
                {"uid": user_id},
            )
            if table_exists(conn, "employees"):
                emp_id = insert_returning_id(
                    conn,
                    table="employees",
                    id_col="employee_id",
                    values={"person_id": person_id, "full_name": "E1 Position Person"},
                )
                conn.execute(
                    text("UPDATE public.users SET employee_id = :eid WHERE user_id = :uid"),
                    {"eid": emp_id, "uid": user_id},
                )
            if table_exists(conn, "person_assignments"):
                insert_returning_id(
                    conn,
                    table="person_assignments",
                    id_col="assignment_id",
                    values={
                        "person_id": person_id,
                        "position_id": position_id,
                        "org_unit_id": unit_id,
                        "employment_type": "primary",
                        "rate": 1.0,
                        "start_date": "2026-01-01",
                        "active_flag": True,
                        "is_primary": True,
                        "lifecycle_status": "active",
                        "assignment_key": f"{unit_id}|{position_id}|primary|2026-01-01",
                        "source": "manual",
                    },
                )

    if person_id is None:
        pytest.skip("persons/assignments schema not available for position target test")

    created = create_visibility_assignment(
        target_type="POSITION",
        target_position_id=position_id,
        scope_type="ORGANIZATION",
        created_by_user_id=seed["initiator_user_id"],
    )
    assignment_id = int(created["assignment_id"])
    try:
        vis = resolve_effective_personnel_visibility(user_id)
        assert vis["has_visibility"] is True
        assert assignment_id in vis["matched_assignment_ids"]
    finally:
        _cleanup_assignment(assignment_id)
        _delete_user(user_id)
        if person_id is not None:
            with engine.begin() as conn:
                if table_exists(conn, "person_assignments"):
                    conn.execute(
                        text("DELETE FROM public.person_assignments WHERE person_id = :pid"),
                        {"pid": person_id},
                    )
                if table_exists(conn, "employees"):
                    conn.execute(
                        text("DELETE FROM public.employees WHERE person_id = :pid"),
                        {"pid": person_id},
                    )
                if table_exists(conn, "persons"):
                    conn.execute(
                        text("DELETE FROM public.persons WHERE person_id = :pid"),
                        {"pid": person_id},
                    )


def test_manager_access_level_implicit_visibility_without_assignment(seed):
    _require_e1()

    with engine.begin() as conn:
        if not table_exists(conn, "access_roles") or not table_exists(conn, "access_grants"):
            pytest.skip("access registry missing")

        unit_id = create_unit(conn, "e1_mgr_unit")
        user_id = insert_returning_id(
            conn,
            table="users",
            id_col="user_id",
            values={
                "full_name": "E1 Manager User",
                "google_login": "e1_mgr_user",
                "role_id": seed["executor_role_id"],
                "unit_id": unit_id,
                "is_active": True,
            },
        )
        role_id = conn.execute(
            text("SELECT access_role_id FROM public.access_roles WHERE code = 'ACCESS_MANAGER' LIMIT 1")
        ).scalar_one()

    grant_access(
        access_role_id=int(role_id),
        target_type="USER",
        target_id=user_id,
        granted_by_user_id=seed["initiator_user_id"],
    )

    try:
        vis = resolve_effective_personnel_visibility(user_id)
        assert vis["has_visibility"] is True
        assert vis["implicit_from_access_level"] is True
        assert vis["source"] == "access_level"
    finally:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    DELETE FROM public.access_grants
                    WHERE target_type = 'USER' AND target_id = :uid
                    """
                ),
                {"uid": user_id},
            )
        _delete_user(user_id)


def test_non_admin_cannot_manage_visibility(client: TestClient, observer_headers):
    _require_e1()

    resp = client.get("/admin/personnel/visibility/assignments", headers=observer_headers)
    assert resp.status_code == 403
