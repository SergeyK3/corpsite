# tests/test_directory_contacts_positions_routes.py
from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.security.directory_scope import SYSTEM_ADMIN_ROLE_ID
from app.services.position_dependencies_service import load_position_blocking_foreign_keys
from tests.conftest import (
    auth_headers,
    create_user,
    get_columns,
    insert_returning_id,
    utcnow,
)


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


def _ensure_system_admin_role(conn) -> None:
    if conn.execute(
        text("SELECT 1 FROM public.roles WHERE role_id = :role_id"),
        {"role_id": SYSTEM_ADMIN_ROLE_ID},
    ).first():
        return

    columns = get_columns(conn, "roles")
    values = {"role_id": SYSTEM_ADMIN_ROLE_ID, "name": "pytest_system_admin"}
    if "code" in columns:
        values["code"] = "SYSTEM_ADMIN"
    if "created_at" in columns:
        values["created_at"] = utcnow()
    insert_returning_id(conn, table="roles", id_col="role_id", values=values)


@pytest.fixture
def sysadmin_headers(seed):
    user_id = 0
    try:
        with engine.begin() as conn:
            _ensure_system_admin_role(conn)
            user_id = create_user(
                conn,
                full_name=f"Pytest Position Admin {uuid4().hex[:8]}",
                role_id=SYSTEM_ADMIN_ROLE_ID,
                unit_id=int(seed["unit_id"]),
            )
        yield auth_headers(user_id)
    finally:
        if user_id:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM public.users WHERE user_id = :user_id"),
                    {"user_id": user_id},
                )


def test_list_contacts_returns_200(client, privileged_headers):
    resp = client.get("/directory/contacts", headers=privileged_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert isinstance(body["items"], list)


def test_list_positions_returns_200(client, privileged_headers):
    resp = client.get("/directory/positions", headers=privileged_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert isinstance(body["items"], list)


def _insert_position(conn, *, name: str) -> int:
    return int(
        conn.execute(
            text(
                """
                INSERT INTO public.positions (name, category)
                VALUES (:name, 'other')
                RETURNING position_id
                """
            ),
            {"name": name},
        ).scalar_one()
    )


def _delete_position_fixture(position_id: int, *, employee_name: str | None = None) -> None:
    with engine.begin() as conn:
        if employee_name:
            conn.execute(
                text("DELETE FROM public.employees WHERE full_name = :name"),
                {"name": employee_name},
            )
        conn.execute(
            text("DELETE FROM public.org_unit_allowed_positions WHERE position_id = :position_id"),
            {"position_id": position_id},
        )
        conn.execute(
            text("DELETE FROM public.positions WHERE position_id = :position_id"),
            {"position_id": position_id},
        )


def test_position_with_allowed_link_is_blocked_and_preserved(client, seed, sysadmin_headers):
    position_id = 0
    try:
        with engine.begin() as conn:
            position_id = _insert_position(conn, name=f"pytest_delete_position_{uuid4().hex}")
            conn.execute(
                text(
                    """
                    INSERT INTO public.org_unit_allowed_positions (
                        org_unit_id, position_id, is_active
                    )
                    VALUES (:unit_id, :position_id, TRUE)
                    """
                ),
                {"unit_id": int(seed["unit_id"]), "position_id": position_id},
            )

        assessment_response = client.get(
            f"/directory/positions/{position_id}/dependencies", headers=sysadmin_headers
        )
        assert assessment_response.status_code == 200, assessment_response.text
        assessment = assessment_response.json()
        assert assessment["can_delete"] is False
        assert assessment["total_dependencies"] == 1
        assert assessment["dependencies"][0]["key"] == "org_unit_allowed_positions.position_id"

        response = client.delete(
            f"/directory/positions/{position_id}", headers=sysadmin_headers
        )

        assert response.status_code == 409, response.text
        detail = response.json()["detail"]
        assert detail["error_code"] == "POSITION_HAS_DEPENDENCIES"
        assert detail["dependencies"] == assessment["dependencies"]
        with engine.connect() as conn:
            assert conn.execute(
                text("SELECT 1 FROM public.positions WHERE position_id = :position_id"),
                {"position_id": position_id},
            ).first() is not None
            assert conn.execute(
                text(
                    """
                    SELECT 1 FROM public.org_unit_allowed_positions
                    WHERE position_id = :position_id
                    """
                ),
                {"position_id": position_id},
            ).first() is not None
    finally:
        if position_id:
            _delete_position_fixture(position_id)


def test_delete_used_position_reports_all_blocking_dependencies(client, seed, sysadmin_headers):
    employee_name = f"pytest_delete_position_employee_{uuid4().hex}"
    position_id = 0
    try:
        with engine.begin() as conn:
            position_id = _insert_position(conn, name=f"pytest_delete_used_position_{uuid4().hex}")
            conn.execute(
                text(
                    """
                    INSERT INTO public.org_unit_allowed_positions (
                        org_unit_id, position_id, is_active
                    )
                    VALUES (:unit_id, :position_id, TRUE)
                    """
                ),
                {"unit_id": int(seed["unit_id"]), "position_id": position_id},
            )
            conn.execute(
                text(
                    """
                    INSERT INTO public.employees (
                        full_name, org_unit_id, position_id,
                        is_active, employment_rate, date_from
                    )
                    VALUES (
                        :name, :unit_id, :position_id,
                        TRUE, 1.00, :date_from
                    )
                    """
                ),
                {
                    "name": employee_name,
                    "unit_id": int(seed["unit_id"]),
                    "position_id": position_id,
                    "date_from": date.today(),
                },
            )

        response = client.delete(
            f"/directory/positions/{position_id}", headers=sysadmin_headers
        )

        assert response.status_code == 409, response.text
        detail = response.json()["detail"]
        assert detail["error_code"] == "POSITION_HAS_DEPENDENCIES"
        dependency_keys = {item["key"] for item in detail["dependencies"]}
        assert "employees.position_id" in dependency_keys
        assert "org_unit_allowed_positions.position_id" in dependency_keys
        with engine.connect() as conn:
            assert conn.execute(
                text(
                    """
                    SELECT 1 FROM public.org_unit_allowed_positions
                    WHERE position_id = :position_id AND is_active = TRUE
                    """
                ),
                {"position_id": position_id},
            ).first() is not None
    finally:
        if position_id:
            _delete_position_fixture(position_id, employee_name=employee_name)


def test_position_without_dependencies_is_assessed_and_deleted(client, sysadmin_headers):
    position_id = 0
    try:
        with engine.begin() as conn:
            position_id = _insert_position(conn, name=f"pytest_delete_clean_{uuid4().hex}")

        assessment_response = client.get(
            f"/directory/positions/{position_id}/dependencies", headers=sysadmin_headers
        )
        assert assessment_response.status_code == 200, assessment_response.text
        assert assessment_response.json() == {
            "position_id": position_id,
            "can_delete": True,
            "total_dependencies": 0,
            "dependencies": [],
        }

        response = client.delete(
            f"/directory/positions/{position_id}", headers=sysadmin_headers
        )
        assert response.status_code == 200, response.text
        assert response.json() == {"ok": True, "position_id": position_id}
    finally:
        if position_id:
            _delete_position_fixture(position_id)


def test_dependency_added_after_preflight_returns_controlled_409(
    client, seed, sysadmin_headers
):
    position_id = 0
    try:
        with engine.begin() as conn:
            position_id = _insert_position(conn, name=f"pytest_delete_race_{uuid4().hex}")

        assessment_response = client.get(
            f"/directory/positions/{position_id}/dependencies", headers=sysadmin_headers
        )
        assert assessment_response.status_code == 200, assessment_response.text
        assert assessment_response.json()["can_delete"] is True

        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO public.org_unit_allowed_positions (
                        org_unit_id, position_id, is_active
                    )
                    VALUES (:unit_id, :position_id, TRUE)
                    """
                ),
                {"unit_id": int(seed["unit_id"]), "position_id": position_id},
            )

        response = client.delete(
            f"/directory/positions/{position_id}", headers=sysadmin_headers
        )
        assert response.status_code == 409, response.text
        detail = response.json()["detail"]
        assert detail["error_code"] == "POSITION_HAS_DEPENDENCIES"
        assert detail["can_delete"] is False
        assert detail["dependencies"][0]["key"] == "org_unit_allowed_positions.position_id"
    finally:
        if position_id:
            _delete_position_fixture(position_id)


def test_privileged_non_admin_cannot_delete_position(client, privileged_headers):
    position_id = 0
    try:
        with engine.begin() as conn:
            position_id = _insert_position(
                conn, name=f"pytest_delete_position_forbidden_{uuid4().hex}"
            )

        response = client.delete(
            f"/directory/positions/{position_id}", headers=privileged_headers
        )

        assert response.status_code == 403, response.text
        with engine.connect() as conn:
            assert conn.execute(
                text("SELECT 1 FROM public.positions WHERE position_id = :position_id"),
                {"position_id": position_id},
            ).first() is not None
    finally:
        if position_id:
            _delete_position_fixture(position_id)


def test_delete_status_lists_use_the_same_dependency_detector(client, seed, sysadmin_headers):
    prefix = f"pytest_delete_status_{uuid4().hex}"
    clean_position_id = 0
    blocked_position_id = 0
    try:
        with engine.begin() as conn:
            clean_position_id = _insert_position(conn, name=f"{prefix}_clean")
            blocked_position_id = _insert_position(conn, name=f"{prefix}_blocked")
            conn.execute(
                text(
                    """
                    INSERT INTO public.org_unit_allowed_positions (
                        org_unit_id, position_id, is_active
                    )
                    VALUES (:unit_id, :position_id, TRUE)
                    """
                ),
                {"unit_id": int(seed["unit_id"]), "position_id": blocked_position_id},
            )

        deletable = client.get(
            "/directory/positions",
            params={"q": prefix, "delete_status": "deletable"},
            headers=sysadmin_headers,
        )
        assert deletable.status_code == 200, deletable.text
        assert [item["position_id"] for item in deletable.json()["items"]] == [clean_position_id]
        assert deletable.json()["items"][0]["delete_assessment"]["can_delete"] is True

        blocked = client.get(
            "/directory/positions",
            params={"q": prefix, "delete_status": "blocked"},
            headers=sysadmin_headers,
        )
        assert blocked.status_code == 200, blocked.text
        assert [item["position_id"] for item in blocked.json()["items"]] == [blocked_position_id]
        assessment = blocked.json()["items"][0]["delete_assessment"]
        assert assessment["can_delete"] is False
        assert assessment["dependencies"][0]["key"] == "org_unit_allowed_positions.position_id"
    finally:
        if blocked_position_id:
            _delete_position_fixture(blocked_position_id)
        if clean_position_id:
            _delete_position_fixture(clean_position_id)


def test_dependency_detector_matches_postgresql_blocking_foreign_keys():
    with engine.connect() as conn:
        expected = {
            str(name)
            for name in conn.execute(
                text(
                    """
                    SELECT conname
                    FROM pg_constraint
                    WHERE contype = 'f'
                      AND confrelid = 'public.positions'::regclass
                      AND confdeltype IN ('a', 'r')
                    """
                )
            ).scalars()
        }
        actual = {
            dependency.constraint_name
            for dependency in load_position_blocking_foreign_keys(conn)
        }

    assert actual == expected
