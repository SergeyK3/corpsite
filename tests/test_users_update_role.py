# tests/test_users_update_role.py
from __future__ import annotations

from typing import Any, Dict, List
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers, create_role, get_columns, table_exists
from tests.test_users_create import (
    _cleanup_employees,
    _cleanup_positions,
    _cleanup_users_by_logins,
    _db_available,
    _make_employee,
)


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


def _cleanup_roles(role_ids: List[int]) -> None:
    if not role_ids:
        return
    with engine.begin() as conn:
        if table_exists(conn, "roles"):
            conn.execute(
                text("DELETE FROM public.roles WHERE role_id = ANY(:ids)"),
                {"ids": [int(x) for x in role_ids]},
            )


def _snapshot_user(conn, user_id: int) -> Dict[str, Any]:
    cols = get_columns(conn, "users")
    select_cols = ["user_id", "login", "role_id", "employee_id", "is_active"]
    if "password_hash" in cols:
        select_cols.append("password_hash")
    row = conn.execute(
        text(
            f"""
            SELECT {", ".join(select_cols)}
            FROM public.users
            WHERE user_id = :user_id
            """
        ),
        {"user_id": int(user_id)},
    ).mappings().first()
    assert row is not None
    return dict(row)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_update_user_role_changes_role_and_preserves_login(client, seed, privileged_headers):
    employee_id, _position_id, created_employee_ids, created_position_ids = _make_employee(seed)
    login = f"pytest_user_{uuid4().hex[:10]}"
    password = "SecretPass1"
    created_role_ids: List[int] = []

    with engine.begin() as conn:
        alt_role_id = create_role(conn, f"ops031_alt_{uuid4().hex[:8]}")
        created_role_ids.append(int(alt_role_id))

    try:
        create_resp = client.post(
            "/directory/users",
            json={
                "employee_id": employee_id,
                "role_id": int(seed["executor_role_id"]),
                "login": login,
                "password": password,
                "is_active": True,
            },
            headers=privileged_headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        user_id = int(create_resp.json()["user_id"])

        with engine.begin() as conn:
            before = _snapshot_user(conn, user_id)

        patch_resp = client.patch(
            f"/directory/users/{user_id}/role",
            json={"role_id": int(alt_role_id)},
            headers=privileged_headers,
        )
        assert patch_resp.status_code == 200, patch_resp.text
        body = patch_resp.json()
        assert body["user_id"] == user_id
        assert body["login"] == login
        assert body["role_id"] == int(alt_role_id)

        with engine.begin() as conn:
            after = _snapshot_user(conn, user_id)
            assert after["login"] == before["login"]
            assert after["employee_id"] == before["employee_id"]
            assert after["is_active"] == before["is_active"]
            assert after["role_id"] == int(alt_role_id)
            if "password_hash" in after:
                assert after["password_hash"] == before["password_hash"]
            audit_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.security_audit_log
                    WHERE event_type = 'ACCESS_CHANGED'
                      AND target_user_id = :uid
                    """
                ),
                {"uid": int(user_id)},
            ).scalar_one()
            assert int(audit_count) >= 1
    finally:
        _cleanup_users_by_logins([login])
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)
        _cleanup_roles(created_role_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_update_user_role_forbidden_for_non_privileged(client, seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    employee_id, _position_id, created_employee_ids, created_position_ids = _make_employee(seed)
    login = f"pytest_user_{uuid4().hex[:10]}"
    password = "SecretPass1"

    with engine.begin() as conn:
        alt_role_id = create_role(conn, f"ops031_alt_{uuid4().hex[:8]}")

    privileged_headers = auth_headers(seed["initiator_user_id"])
    executor_headers = auth_headers(seed["executor_user_id"])

    try:
        create_resp = client.post(
            "/directory/users",
            json={
                "employee_id": employee_id,
                "role_id": int(seed["executor_role_id"]),
                "login": login,
                "password": password,
                "is_active": True,
            },
            headers=privileged_headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        user_id = int(create_resp.json()["user_id"])

        patch_resp = client.patch(
            f"/directory/users/{user_id}/role",
            json={"role_id": int(alt_role_id)},
            headers=executor_headers,
        )
        assert patch_resp.status_code == 403, patch_resp.text
    finally:
        _cleanup_users_by_logins([login])
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)
        with engine.begin() as conn:
            if table_exists(conn, "roles"):
                conn.execute(text("DELETE FROM public.roles WHERE role_id = :rid"), {"rid": int(alt_role_id)})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_update_user_role_rejects_missing_role(client, seed, privileged_headers):
    employee_id, _position_id, created_employee_ids, created_position_ids = _make_employee(seed)
    login = f"pytest_user_{uuid4().hex[:10]}"
    password = "SecretPass1"

    try:
        create_resp = client.post(
            "/directory/users",
            json={
                "employee_id": employee_id,
                "role_id": int(seed["executor_role_id"]),
                "login": login,
                "password": password,
                "is_active": True,
            },
            headers=privileged_headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        user_id = int(create_resp.json()["user_id"])

        patch_resp = client.patch(
            f"/directory/users/{user_id}/role",
            json={"role_id": 999999999},
            headers=privileged_headers,
        )
        assert patch_resp.status_code == 404, patch_resp.text
    finally:
        _cleanup_users_by_logins([login])
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_update_user_role_rejects_inactive_role_when_supported(client, seed, privileged_headers):
    with engine.begin() as conn:
        role_cols = get_columns(conn, "roles")
        active_col = next((c for c in ("is_active", "active", "status") if c in role_cols), None)
    if not active_col:
        pytest.skip("roles table has no active/status column")

    employee_id, _position_id, created_employee_ids, created_position_ids = _make_employee(seed)
    login = f"pytest_user_{uuid4().hex[:10]}"
    password = "SecretPass1"

    with engine.begin() as conn:
        inactive_name = f"ops031_inactive_{uuid4().hex[:8]}"
        inactive_role_id = create_role(conn, inactive_name)
        if active_col == "status":
            conn.execute(
                text("UPDATE public.roles SET status = :status WHERE role_id = :role_id"),
                {"status": "inactive", "role_id": int(inactive_role_id)},
            )
        else:
            conn.execute(
                text(f"UPDATE public.roles SET {active_col} = FALSE WHERE role_id = :role_id"),
                {"role_id": int(inactive_role_id)},
            )

    try:
        create_resp = client.post(
            "/directory/users",
            json={
                "employee_id": employee_id,
                "role_id": int(seed["executor_role_id"]),
                "login": login,
                "password": password,
                "is_active": True,
            },
            headers=privileged_headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        user_id = int(create_resp.json()["user_id"])

        patch_resp = client.patch(
            f"/directory/users/{user_id}/role",
            json={"role_id": int(inactive_role_id)},
            headers=privileged_headers,
        )
        assert patch_resp.status_code == 404, patch_resp.text
    finally:
        _cleanup_users_by_logins([login])
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)
        with engine.begin() as conn:
            if table_exists(conn, "roles"):
                conn.execute(
                    text("DELETE FROM public.roles WHERE role_id = :role_id"),
                    {"role_id": int(inactive_role_id)},
                )
