# tests/test_auth_me_can_view_all_tasks.py
from __future__ import annotations

from typing import Any, Dict
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.tasks_service import SYSTEM_ADMIN_ROLE_ID
from tests.conftest import auth_headers, create_role, create_unit, create_user


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _admin_user_id(conn) -> int:
    row = conn.execute(
        text(
            """
            SELECT user_id
            FROM public.users
            WHERE role_id = :role_id
              AND COALESCE(is_active, TRUE) = TRUE
            LIMIT 1
            """
        ),
        {"role_id": int(SYSTEM_ADMIN_ROLE_ID)},
    ).first()
    if row:
        return int(row[0])

    unit_id = create_unit(conn, "pytest_auth_me_all_tasks_admin_unit")
    return create_user(
        conn,
        full_name="Pytest Auth Me All Tasks Admin",
        role_id=int(SYSTEM_ADMIN_ROLE_ID),
        unit_id=unit_id,
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_auth_me_can_view_all_tasks_false_for_plain_executor(client, seed: Dict[str, Any]) -> None:
    resp = client.get("/auth/me", headers=auth_headers(seed["executor_user_id"]))
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body.get("can_view_all_tasks") is False


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_auth_me_can_view_all_tasks_true_for_system_admin(client) -> None:
    with engine.begin() as conn:
        admin_user_id = _admin_user_id(conn)

    resp = client.get("/auth/me", headers=auth_headers(admin_user_id))
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body.get("can_view_all_tasks") is True


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_auth_me_can_view_all_tasks_true_for_manager_role(client) -> None:
    suffix = uuid4().hex[:8]
    manager_user_id: int | None = None

    try:
        with engine.begin() as conn:
            unit_id = create_unit(conn, f"pytest_auth_me_manager_unit_{suffix}")
            manager_role_id = create_role(conn, f"pytest_manager_{suffix}")
            conn.execute(
                text(
                    """
                    UPDATE public.roles
                    SET code = :code, name = :name
                    WHERE role_id = :role_id
                    """
                ),
                {
                    "role_id": int(manager_role_id),
                    "code": f"PYTEST_HEAD_{suffix}",
                    "name": "Руководитель отделения",
                },
            )
            manager_user_id = create_user(
                conn,
                full_name="Pytest Manager All Tasks",
                role_id=int(manager_role_id),
                unit_id=int(unit_id),
            )

        resp = client.get("/auth/me", headers=auth_headers(int(manager_user_id)))
        assert resp.status_code == 200, resp.text
        assert resp.json().get("can_view_all_tasks") is True
    finally:
        if manager_user_id is not None:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM public.users WHERE user_id = :uid"),
                    {"uid": int(manager_user_id)},
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_regular_executor_team_scope_still_forbidden(client, seed: Dict[str, Any]) -> None:
    resp = client.get(
        "/tasks",
        params={"scope": "team", "limit": 10, "status_filter": "active"},
        headers=auth_headers(seed["executor_user_id"]),
    )
    assert resp.status_code == 403, resp.text
