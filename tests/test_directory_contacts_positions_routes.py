# tests/test_directory_contacts_positions_routes.py
from __future__ import annotations

from datetime import date
from threading import Event, Thread
from time import monotonic
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import exc as sa_exc, text
from sqlalchemy.engine import Connection

from app.directory.contacts_routes import (
    ContactUpsert,
    _can_manage_contacts,
    _can_read_contacts,
    create_contact,
    delete_contact,
    update_contact,
)
from app.directory import positions_routes
from app.db.engine import engine
from app.security.directory_scope import SYSTEM_ADMIN_ROLE_ID
from app.services.position_dependencies_service import (
    PositionDependencySummary,
    load_position_blocking_foreign_keys,
)
from tests.conftest import (
    auth_headers,
    create_unit,
    create_user,
    get_columns,
    insert_returning_id,
    utcnow,
)


def test_contacts_read_and_manage_access_are_separated(monkeypatch):
    monkeypatch.setattr(
        "app.directory.contacts_routes._is_privileged",
        lambda _user: False,
    )
    monkeypatch.setattr(
        "app.directory.contacts_routes.has_any_personnel_read_permission",
        lambda user_id: int(user_id) == 361,
    )

    personnel_reader = {"user_id": 361, "has_personnel_admin": False}
    personnel_admin = {"user_id": 999, "has_personnel_admin": True}

    assert _can_read_contacts(personnel_reader) is True
    assert _can_manage_contacts(personnel_reader) is False
    assert _can_read_contacts(personnel_admin) is True
    assert _can_manage_contacts(personnel_admin) is True


def test_personnel_reader_cannot_manage_contacts(monkeypatch):
    monkeypatch.setattr(
        "app.directory.contacts_routes._is_privileged",
        lambda _user: False,
    )
    monkeypatch.setattr(
        "app.directory.contacts_routes.has_any_personnel_read_permission",
        lambda user_id: int(user_id) == 361,
    )
    personnel_reader = {"user_id": 361, "has_personnel_admin": False}
    payload = ContactUpsert(full_name="Read-only contact")

    for action in (
        lambda: create_contact(payload, personnel_reader),
        lambda: update_contact(1, payload, personnel_reader),
        lambda: delete_contact(1, personnel_reader),
    ):
        with pytest.raises(HTTPException) as exc_info:
            action()
        assert exc_info.value.status_code == 403


def test_privileged_user_keeps_contacts_read_and_manage_access(monkeypatch):
    monkeypatch.setattr(
        "app.directory.contacts_routes._is_privileged",
        lambda _user: True,
    )
    user = {"user_id": 361, "has_personnel_admin": False}

    assert _can_read_contacts(user) is True
    assert _can_manage_contacts(user) is True


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
        headers = auth_headers(user_id)
        headers["X-Pytest-User-Id"] = str(user_id)
        yield headers
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


def _stage5_link(conn, *, org_unit_id: int, position_id: int):
    row = conn.execute(
        text(
            """
            SELECT
                org_unit_allowed_position_id,
                org_unit_id,
                position_id,
                sort_order,
                is_active,
                updated_at
            FROM public.org_unit_allowed_positions
            WHERE org_unit_id = :org_unit_id
              AND position_id = :position_id
            """
        ),
        {"org_unit_id": int(org_unit_id), "position_id": int(position_id)},
    ).mappings().first()
    return dict(row) if row else None


def _stage5_audit(conn, *, request_id: str):
    rows = conn.execute(
        text(
            """
            SELECT
                audit_id,
                event_type,
                actor_user_id,
                user_agent,
                success,
                metadata,
                request_id
            FROM public.security_audit_log
            WHERE request_id = :request_id
            """
        ),
        {"request_id": request_id},
    ).mappings().all()
    assert len(rows) <= 1, f"duplicate audit rows for request_id={request_id}"
    return dict(rows[0]) if rows else None


def _cleanup_stage5_rows(
    *,
    position_ids: list[int],
    request_ids: list[str] | None = None,
    employee_names: list[str] | None = None,
    org_unit_ids: list[int] | None = None,
) -> None:
    with engine.begin() as conn:
        if request_ids:
            conn.execute(
                text("DELETE FROM public.security_audit_log WHERE request_id = ANY(:request_ids)"),
                {"request_ids": request_ids},
            )
        if employee_names:
            conn.execute(
                text("DELETE FROM public.employees WHERE full_name = ANY(:employee_names)"),
                {"employee_names": employee_names},
            )
        if position_ids:
            conn.execute(
                text("DELETE FROM public.org_unit_allowed_positions WHERE position_id = ANY(:position_ids)"),
                {"position_ids": position_ids},
            )
            conn.execute(
                text("DELETE FROM public.positions WHERE position_id = ANY(:position_ids)"),
                {"position_ids": position_ids},
            )
        if org_unit_ids:
            conn.execute(
                text("DELETE FROM public.org_units WHERE unit_id = ANY(:org_unit_ids)"),
                {"org_unit_ids": org_unit_ids},
            )


def _wait_for_postgres_lock_wait(backend_pid: int, *, timeout_seconds: float = 5.0) -> None:
    deadline = monotonic() + timeout_seconds
    tick = Event()
    with engine.connect() as probe:
        while monotonic() < deadline:
            wait_event_type = probe.execute(
                text(
                    """
                    SELECT wait_event_type
                    FROM pg_stat_activity
                    WHERE pid = :backend_pid
                    """
                ),
                {"backend_pid": int(backend_pid)},
            ).scalar_one_or_none()
            if wait_event_type == "Lock":
                return
            tick.wait(0.02)
    raise AssertionError(f"backend {backend_pid} did not enter a PostgreSQL lock wait")


def _join_worker(worker: Thread, *, timeout_seconds: float = 5.0) -> None:
    worker.join(timeout_seconds)
    assert not worker.is_alive(), "PostgreSQL lock worker did not finish"


def test_position_with_allowed_link_is_blocked_and_preserved(client, seed, sysadmin_headers):
    position_id = 0
    link_id = 0
    unit_name = ""
    try:
        with engine.begin() as conn:
            position_id = _insert_position(conn, name=f"pytest_delete_position_{uuid4().hex}")
            link_id = int(conn.execute(
                text(
                    """
                    INSERT INTO public.org_unit_allowed_positions (
                        org_unit_id, position_id, is_active
                    )
                    VALUES (:unit_id, :position_id, TRUE)
                    RETURNING org_unit_allowed_position_id
                    """
                ),
                {"unit_id": int(seed["unit_id"]), "position_id": position_id},
            ).scalar_one())
            unit_name = str(conn.execute(
                text("SELECT name FROM public.org_units WHERE unit_id = :unit_id"),
                {"unit_id": int(seed["unit_id"])},
            ).scalar_one())

        assessment_response = client.get(
            f"/directory/positions/{position_id}/dependencies", headers=sysadmin_headers
        )
        assert assessment_response.status_code == 200, assessment_response.text
        assessment = assessment_response.json()
        assert assessment["can_delete"] is False
        assert assessment["total_dependencies"] == 1
        allowed_dependency = assessment["dependencies"][0]
        assert allowed_dependency["key"] == "org_unit_allowed_positions.position_id"
        assert allowed_dependency["allowed_position_links"] == [
            {
                "org_unit_allowed_position_id": link_id,
                "org_unit_id": int(seed["unit_id"]),
                "org_unit_name": unit_name,
                "is_active": True,
            }
        ]

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


def test_inactive_allowed_link_is_not_a_dependency(client, seed, sysadmin_headers):
    position_id = 0
    try:
        with engine.begin() as conn:
            position_id = _insert_position(
                conn,
                name=f"pytest_inactive_allowed_dependency_{uuid4().hex}",
            )
            conn.execute(
                text(
                    """
                    INSERT INTO public.org_unit_allowed_positions (
                        org_unit_id, position_id, is_active
                    )
                    VALUES (:unit_id, :position_id, FALSE)
                    """
                ),
                {"unit_id": int(seed["unit_id"]), "position_id": position_id},
            )

        response = client.get(
            f"/directory/positions/{position_id}/dependencies",
            headers=sysadmin_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json() == {
            "position_id": position_id,
            "can_delete": True,
            "total_dependencies": 0,
            "dependencies": [],
        }
        with engine.connect() as conn:
            assert conn.execute(
                text(
                    """
                    SELECT 1
                    FROM public.org_unit_allowed_positions
                    WHERE position_id = :position_id
                      AND is_active = FALSE
                    """
                ),
                {"position_id": position_id},
            ).first() is not None
    finally:
        if position_id:
            _delete_position_fixture(position_id)


def test_mixed_allowed_links_report_only_active_rows(client, seed, sysadmin_headers):
    position_id = 0
    second_unit_id = 0
    active_link_id = 0
    active_unit_name = ""
    try:
        with engine.begin() as conn:
            position_id = _insert_position(
                conn,
                name=f"pytest_mixed_allowed_dependency_{uuid4().hex}",
            )
            second_unit_id = int(create_unit(conn, f"pytest_mixed_unit_{uuid4().hex}") or 0)
            assert second_unit_id > 0
            rows = conn.execute(
                text(
                    """
                    INSERT INTO public.org_unit_allowed_positions (
                        org_unit_id, position_id, is_active
                    )
                    VALUES
                        (:active_unit_id, :position_id, TRUE),
                        (:inactive_unit_id, :position_id, FALSE)
                    RETURNING org_unit_allowed_position_id, org_unit_id, is_active
                    """
                ),
                {
                    "active_unit_id": int(seed["unit_id"]),
                    "inactive_unit_id": second_unit_id,
                    "position_id": position_id,
                },
            ).mappings().all()
            active_link_id = int(next(row for row in rows if row["is_active"])["org_unit_allowed_position_id"])
            active_unit_name = str(conn.execute(
                text("SELECT name FROM public.org_units WHERE unit_id = :unit_id"),
                {"unit_id": int(seed["unit_id"])},
            ).scalar_one())

        response = client.get(
            f"/directory/positions/{position_id}/dependencies",
            headers=sysadmin_headers,
        )
        assert response.status_code == 200, response.text
        assessment = response.json()
        assert assessment["can_delete"] is False
        assert assessment["total_dependencies"] == 1
        assert assessment["dependencies"] == [
            {
                "key": "org_unit_allowed_positions.position_id",
                "label": assessment["dependencies"][0]["label"],
                "table": "public.org_unit_allowed_positions",
                "column": "position_id",
                "constraint": "org_unit_allowed_positions_position_id_fkey",
                "count": 1,
                "allowed_position_links": [
                    {
                        "org_unit_allowed_position_id": active_link_id,
                        "org_unit_id": int(seed["unit_id"]),
                        "org_unit_name": active_unit_name,
                        "is_active": True,
                    }
                ],
            }
        ]
        delete_response = client.delete(
            f"/directory/positions/{position_id}",
            headers=sysadmin_headers,
        )
        assert delete_response.status_code == 409, delete_response.text
        assert delete_response.json()["detail"]["error_code"] == "POSITION_HAS_DEPENDENCIES"
        with engine.connect() as conn:
            remaining = conn.execute(
                text(
                    """
                    SELECT is_active
                    FROM public.org_unit_allowed_positions
                    WHERE position_id = :position_id
                    ORDER BY org_unit_allowed_position_id
                    """
                ),
                {"position_id": position_id},
            ).scalars().all()
            assert sorted(bool(value) for value in remaining) == [False, True]
    finally:
        if position_id:
            _delete_position_fixture(position_id)
        if second_unit_id:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM public.org_units WHERE unit_id = :unit_id"),
                    {"unit_id": second_unit_id},
                )


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
    inactive_position_id = 0
    try:
        with engine.begin() as conn:
            clean_position_id = _insert_position(conn, name=f"{prefix}_clean")
            blocked_position_id = _insert_position(conn, name=f"{prefix}_blocked")
            inactive_position_id = _insert_position(conn, name=f"{prefix}_inactive")
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
            conn.execute(
                text(
                    """
                    INSERT INTO public.org_unit_allowed_positions (
                        org_unit_id, position_id, is_active
                    )
                    VALUES (:unit_id, :position_id, FALSE)
                    """
                ),
                {"unit_id": int(seed["unit_id"]), "position_id": inactive_position_id},
            )

        deletable = client.get(
            "/directory/positions",
            params={"q": prefix, "delete_status": "deletable"},
            headers=sysadmin_headers,
        )
        assert deletable.status_code == 200, deletable.text
        deletable_items = deletable.json()["items"]
        assert [item["position_id"] for item in deletable_items] == [
            clean_position_id,
            inactive_position_id,
        ]
        assert all(item["delete_assessment"]["can_delete"] is True for item in deletable_items)

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
        if inactive_position_id:
            _delete_position_fixture(inactive_position_id)


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


def test_stage5_lifecycle_routes_preserve_presence_transitions_and_audit(
    client,
    seed,
    sysadmin_headers,
):
    position_id = 0
    request_ids = {
        name: f"adr046-f2-stage5-{name}-{uuid4().hex}"
        for name in (
            "created",
            "noop",
            "integer",
            "null",
            "deactivated",
            "deactivate-noop",
            "reactivated",
        )
    }
    actor_user_id = int(sysadmin_headers["X-Pytest-User-Id"])
    base_url = ""

    def headers(name: str) -> dict[str, str]:
        return {
            **sysadmin_headers,
            "X-Request-ID": request_ids[name],
            "User-Agent": "adr046-f2-stage5-test",
        }

    try:
        with engine.begin() as conn:
            position_id = _insert_position(
                conn,
                name=f"pytest_stage5_lifecycle_{uuid4().hex}",
            )
        base_url = (
            f"/directory/org-units/{int(seed['unit_id'])}"
            f"/allowed-positions/{position_id}"
        )

        created_response = client.put(base_url, headers=headers("created"))
        assert created_response.status_code == 201, created_response.text
        created = created_response.json()
        assert set(created) == {"link", "transition", "previous_state", "current_state"}
        assert set(created["link"]) == {
            "org_unit_allowed_position_id",
            "org_unit_id",
            "position_id",
            "sort_order",
            "is_active",
        }
        assert created["transition"] == "created"
        assert created["previous_state"] is None
        assert created["current_state"] == {"is_active": True, "sort_order": None}
        assert created["link"]["org_unit_id"] == int(seed["unit_id"])
        assert created["link"]["position_id"] == position_id
        assert created["link"]["sort_order"] is None
        assert created["link"]["is_active"] is True
        link_id = int(created["link"]["org_unit_allowed_position_id"])

        noop_response = client.put(base_url, json={}, headers=headers("noop"))
        assert noop_response.status_code == 200, noop_response.text
        noop = noop_response.json()
        assert noop["transition"] == "noop"
        assert noop["previous_state"] == noop["current_state"] == {
            "is_active": True,
            "sort_order": None,
        }
        assert int(noop["link"]["org_unit_allowed_position_id"]) == link_id

        integer_response = client.put(
            base_url,
            json={"sort_order": 23},
            headers=headers("integer"),
        )
        assert integer_response.status_code == 200, integer_response.text
        integer_update = integer_response.json()
        assert integer_update["transition"] == "updated"
        assert integer_update["previous_state"] == {
            "is_active": True,
            "sort_order": None,
        }
        assert integer_update["current_state"] == {
            "is_active": True,
            "sort_order": 23,
        }

        null_response = client.put(
            base_url,
            json={"sort_order": None},
            headers=headers("null"),
        )
        assert null_response.status_code == 200, null_response.text
        null_update = null_response.json()
        assert null_update["transition"] == "updated"
        assert null_update["previous_state"]["sort_order"] == 23
        assert null_update["current_state"]["sort_order"] is None

        deactivated_response = client.delete(
            base_url,
            headers=headers("deactivated"),
        )
        assert deactivated_response.status_code == 200, deactivated_response.text
        deactivated = deactivated_response.json()
        assert set(deactivated) == {
            "org_unit_allowed_position_id",
            "org_unit_id",
            "position_id",
            "sort_order",
            "is_active",
        }
        assert int(deactivated["org_unit_allowed_position_id"]) == link_id
        assert deactivated["is_active"] is False
        assert deactivated["sort_order"] is None

        repeated_response = client.delete(
            base_url,
            headers=headers("deactivate-noop"),
        )
        assert repeated_response.status_code == 200, repeated_response.text
        assert repeated_response.json() == deactivated

        reactivated_response = client.put(
            base_url,
            headers=headers("reactivated"),
        )
        assert reactivated_response.status_code == 200, reactivated_response.text
        reactivated = reactivated_response.json()
        assert reactivated["transition"] == "reactivated"
        assert reactivated["previous_state"] == {
            "is_active": False,
            "sort_order": None,
        }
        assert reactivated["current_state"] == {
            "is_active": True,
            "sort_order": None,
        }
        assert int(reactivated["link"]["org_unit_allowed_position_id"]) == link_id

        with engine.connect() as conn:
            links = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.org_unit_allowed_positions
                    WHERE org_unit_id = :org_unit_id
                      AND position_id = :position_id
                    """
                ),
                {"org_unit_id": int(seed["unit_id"]), "position_id": position_id},
            ).scalar_one()
            assert links == 1
            stored = _stage5_link(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
            )
            assert int(stored["org_unit_allowed_position_id"]) == link_id
            assert stored["is_active"] is True
            assert stored["sort_order"] is None

            expected_events = {
                "created": "ORG_UNIT_ALLOWED_POSITION_CREATED",
                "integer": "ORG_UNIT_ALLOWED_POSITION_UPDATED",
                "null": "ORG_UNIT_ALLOWED_POSITION_UPDATED",
                "deactivated": "ORG_UNIT_ALLOWED_POSITION_DEACTIVATED",
                "reactivated": "ORG_UNIT_ALLOWED_POSITION_REACTIVATED",
            }
            for name, event_type in expected_events.items():
                audit = _stage5_audit(conn, request_id=request_ids[name])
                assert audit is not None
                assert int(audit["audit_id"]) > 0
                assert audit["event_type"] == event_type
                assert int(audit["actor_user_id"]) == actor_user_id
                assert audit["success"] is True
                assert audit["user_agent"] == "adr046-f2-stage5-test"
                assert audit["request_id"] == request_ids[name]
                assert int(audit["metadata"]["org_unit_allowed_position_id"]) == link_id
                assert int(audit["metadata"]["org_unit_id"]) == int(seed["unit_id"])
                assert int(audit["metadata"]["position_id"]) == position_id
            integer_audit = _stage5_audit(conn, request_id=request_ids["integer"])
            created_audit = _stage5_audit(conn, request_id=request_ids["created"])
            assert created_audit["metadata"]["previous_state"] is None
            assert created_audit["metadata"]["current_state"] == {
                "is_active": True,
                "sort_order": None,
            }
            assert integer_audit["metadata"]["previous_state"] == {
                "is_active": True,
                "sort_order": None,
            }
            assert integer_audit["metadata"]["current_state"] == {
                "is_active": True,
                "sort_order": 23,
            }
            assert integer_audit["metadata"]["previous_sort_order"] is None
            assert integer_audit["metadata"]["new_sort_order"] == 23
            null_audit = _stage5_audit(conn, request_id=request_ids["null"])
            assert null_audit["metadata"]["previous_state"] == {
                "is_active": True,
                "sort_order": 23,
            }
            assert null_audit["metadata"]["current_state"] == {
                "is_active": True,
                "sort_order": None,
            }
            assert null_audit["metadata"]["previous_sort_order"] == 23
            assert null_audit["metadata"]["new_sort_order"] is None
            deactivated_audit = _stage5_audit(
                conn,
                request_id=request_ids["deactivated"],
            )
            assert deactivated_audit["metadata"]["previous_state"] == {
                "is_active": True,
                "sort_order": None,
            }
            assert deactivated_audit["metadata"]["current_state"] == {
                "is_active": False,
                "sort_order": None,
            }
            reactivated_audit = _stage5_audit(
                conn,
                request_id=request_ids["reactivated"],
            )
            assert reactivated_audit["metadata"]["previous_state"] == {
                "is_active": False,
                "sort_order": None,
            }
            assert reactivated_audit["metadata"]["current_state"] == {
                "is_active": True,
                "sort_order": None,
            }
            assert _stage5_audit(conn, request_id=request_ids["noop"]) is None
            assert _stage5_audit(conn, request_id=request_ids["deactivate-noop"]) is None
    finally:
        if position_id:
            _cleanup_stage5_rows(
                position_ids=[position_id],
                request_ids=list(request_ids.values()),
            )


def test_stage5_lifecycle_routes_enforce_auth_and_presence_aware_validation(
    client,
    seed,
    sysadmin_headers,
    privileged_headers,
):
    position_id = 0
    request_ids: list[str] = []
    try:
        with engine.begin() as conn:
            position_id = _insert_position(
                conn,
                name=f"pytest_stage5_validation_{uuid4().hex}",
            )
        url = (
            f"/directory/org-units/{int(seed['unit_id'])}"
            f"/allowed-positions/{position_id}"
        )

        assert client.put(url).status_code == 401
        assert client.put(url, headers=privileged_headers).status_code == 403
        assert client.delete(url, headers=privileged_headers).status_code == 403
        ordinary_headers = auth_headers(int(seed["executor_user_id"]))
        assert client.put(url, headers=ordinary_headers).status_code == 403
        assert client.delete(url, headers=ordinary_headers).status_code == 403

        invalid_requests = (
            ({"sort_order": "23"}, None),
            ({"sort_order": True}, None),
            ({"sort_order": 1, "unexpected": 2}, None),
            (None, "{"),
        )
        for payload, raw_body in invalid_requests:
            request_id = f"adr046-f2-stage5-invalid-{uuid4().hex}"
            request_ids.append(request_id)
            headers = {**sysadmin_headers, "X-Request-ID": request_id}
            if raw_body is None:
                response = client.put(url, json=payload, headers=headers)
            else:
                response = client.put(
                    url,
                    content=raw_body,
                    headers={**headers, "Content-Type": "application/json"},
                )
            assert response.status_code == 422, response.text

        with engine.connect() as conn:
            assert _stage5_link(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
            ) is None
            for request_id in request_ids:
                assert _stage5_audit(conn, request_id=request_id) is None
    finally:
        if position_id:
            _cleanup_stage5_rows(
                position_ids=[position_id],
                request_ids=request_ids,
            )


def test_stage5_lifecycle_openapi_contract(client):
    def response_schema(operation, status: str):
        content = operation["responses"][status]["content"]
        assert len(content) == 1
        media_type, documented_schema = next(iter(content.items()))
        assert media_type.startswith("application/json")
        return documented_schema["schema"]

    schema = client.get("/openapi.json").json()
    lifecycle_path = schema["paths"][
        "/directory/org-units/{org_unit_id}/allowed-positions/{position_id}"
    ]
    assert set(lifecycle_path) >= {"put", "delete"}
    put_responses = lifecycle_path["put"]["responses"]
    delete_responses = lifecycle_path["delete"]["responses"]
    assert set(put_responses) == {"200", "201", "403", "404", "422"}
    assert set(delete_responses) == {"200", "403", "404", "422"}
    assert response_schema(lifecycle_path["put"], "403")["$ref"].endswith(
        "/HttpErrorOut"
    )
    assert response_schema(lifecycle_path["put"], "404")["$ref"].endswith(
        "/AllowedPositionNotFoundOut"
    )
    assert response_schema(lifecycle_path["delete"], "403")["$ref"].endswith(
        "/HttpErrorOut"
    )
    assert response_schema(lifecycle_path["delete"], "404")["$ref"].endswith(
        "/AllowedPositionNotFoundOut"
    )
    request_body = lifecycle_path["put"]["requestBody"]
    assert request_body.get("required") is not True
    payload_schema = request_body["content"]["application/json"]["schema"]
    assert payload_schema

    global_delete = schema["paths"]["/directory/positions/{position_id}"]["delete"]
    global_responses = global_delete["responses"]
    assert set(global_responses) == {"200", "403", "404", "409", "422"}
    assert response_schema(global_delete, "403")["$ref"].endswith("/HttpErrorOut")
    assert response_schema(global_delete, "404")["$ref"].endswith("/HttpErrorOut")
    assert response_schema(global_delete, "409")["$ref"].endswith(
        "/PositionDependencyConflictOut"
    )
    conflict_detail = schema["components"]["schemas"][
        "PositionDependencyConflictDetailOut"
    ]
    race_schema = conflict_detail["properties"]["race_detected"]
    assert {item.get("const") for item in race_schema["anyOf"]} >= {True}
    assert "race_detected" not in conflict_detail.get("required", [])
    assert {
        "error_code",
        "position_id",
        "can_delete",
        "total_dependencies",
        "dependencies",
    } <= set(conflict_detail["required"])

    conflict_envelope = schema["components"]["schemas"][
        "PositionDependencyConflictOut"
    ]
    detail_variants = conflict_envelope["properties"]["detail"]["anyOf"]
    assert {variant["$ref"].rsplit("/", 1)[-1] for variant in detail_variants} == {
        "PositionDependencyConflictDetailOut",
        "PositionDefensiveFkConflictDetailOut",
    }
    defensive_detail = schema["components"]["schemas"][
        "PositionDefensiveFkConflictDetailOut"
    ]
    assert set(defensive_detail["properties"]) == {"error_code", "race_detected"}
    assert set(defensive_detail["required"]) == {"error_code", "race_detected"}
    assert defensive_detail["properties"]["error_code"]["const"] == (
        "POSITION_HAS_DEPENDENCIES"
    )
    assert defensive_detail["properties"]["race_detected"]["const"] is True


def test_stage5_lifecycle_routes_map_parent_and_link_not_found_codes(
    client,
    seed,
    sysadmin_headers,
):
    position_id = 0
    try:
        with engine.begin() as conn:
            position_id = _insert_position(
                conn,
                name=f"pytest_stage5_not_found_{uuid4().hex}",
            )
            missing_position_id = int(
                conn.execute(
                    text("SELECT COALESCE(MAX(position_id), 0) + 1000000 FROM public.positions")
                ).scalar_one()
            )
            missing_org_unit_id = int(
                conn.execute(
                    text("SELECT COALESCE(MAX(unit_id), 0) + 1000000 FROM public.org_units")
                ).scalar_one()
            )

        both_missing = client.put(
            f"/directory/org-units/{missing_org_unit_id}/allowed-positions/{missing_position_id}",
            headers=sysadmin_headers,
        )
        assert both_missing.status_code == 404
        assert both_missing.json()["detail"] == {"error_code": "POSITION_NOT_FOUND"}
        delete_both_missing = client.delete(
            f"/directory/org-units/{missing_org_unit_id}/allowed-positions/{missing_position_id}",
            headers=sysadmin_headers,
        )
        assert delete_both_missing.status_code == 404
        assert delete_both_missing.json()["detail"] == {
            "error_code": "POSITION_NOT_FOUND"
        }

        org_missing = client.put(
            f"/directory/org-units/{missing_org_unit_id}/allowed-positions/{position_id}",
            headers=sysadmin_headers,
        )
        assert org_missing.status_code == 404
        assert org_missing.json()["detail"] == {"error_code": "ORG_UNIT_NOT_FOUND"}
        delete_org_missing = client.delete(
            f"/directory/org-units/{missing_org_unit_id}/allowed-positions/{position_id}",
            headers=sysadmin_headers,
        )
        assert delete_org_missing.status_code == 404
        assert delete_org_missing.json()["detail"] == {
            "error_code": "ORG_UNIT_NOT_FOUND"
        }

        link_missing = client.delete(
            f"/directory/org-units/{int(seed['unit_id'])}/allowed-positions/{position_id}",
            headers=sysadmin_headers,
        )
        assert link_missing.status_code == 404
        assert link_missing.json()["detail"] == {
            "error_code": "ALLOWED_POSITION_LINK_NOT_FOUND"
        }
    finally:
        if position_id:
            _cleanup_stage5_rows(position_ids=[position_id])


@pytest.mark.parametrize("error_kind", ["generic_integrity", "other_database"])
def test_stage5_direct_position_delete_non_defensive_errors_propagate(
    client,
    seed,
    sysadmin_headers,
    monkeypatch: pytest.MonkeyPatch,
    error_kind: str,
):
    class GenericOriginalError(Exception):
        sqlstate = None
        diag = None

    position_id = 0
    try:
        with engine.begin() as conn:
            position_id = _insert_position(
                conn, name=f"pytest_stage5_direct_error_{uuid4().hex}"
            )
            link_id = int(
                conn.execute(
                    text(
                        """
                        INSERT INTO public.org_unit_allowed_positions (
                            org_unit_id, position_id, is_active
                        )
                        VALUES (:org_unit_id, :position_id, FALSE)
                        RETURNING org_unit_allowed_position_id
                        """
                    ),
                    {"org_unit_id": int(seed["unit_id"]), "position_id": position_id},
                ).scalar_one()
            )

        if error_kind == "generic_integrity":
            injected_error: BaseException = sa_exc.IntegrityError(
                "not a PostgreSQL FK violation", {}, GenericOriginalError()
            )
        else:
            injected_error = RuntimeError("pytest non-IntegrityError database failure")

        original_execute = Connection.execute

        def fail_only_direct_position_delete(
            self, statement, parameters=None, *args, **kwargs
        ):
            normalized = " ".join(str(statement).lower().split())
            if (
                normalized.startswith("delete from public.positions")
                and "returning position_id" in normalized
            ):
                raise injected_error
            return original_execute(self, statement, parameters, *args, **kwargs)

        with monkeypatch.context() as scoped:
            scoped.setattr(Connection, "execute", fail_only_direct_position_delete)
            with pytest.raises(type(injected_error)) as raised:
                client.delete(
                    f"/directory/positions/{position_id}", headers=sysadmin_headers
                )
            assert raised.value is injected_error

        with engine.connect() as conn:
            assert conn.execute(text("SELECT 1")).scalar_one() == 1
            assert conn.execute(
                text("SELECT 1 FROM public.positions WHERE position_id = :position_id"),
                {"position_id": position_id},
            ).first() is not None
            restored_link = _stage5_link(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
            )
            assert int(restored_link["org_unit_allowed_position_id"]) == link_id
            assert restored_link["is_active"] is False
    finally:
        if position_id:
            _cleanup_stage5_rows(position_ids=[position_id])


def test_stage5_global_delete_removes_only_target_inactive_links(
    client,
    seed,
    sysadmin_headers,
):
    target_position_id = 0
    other_position_id = 0
    second_unit_id = 0
    try:
        with engine.begin() as conn:
            target_position_id = _insert_position(
                conn,
                name=f"pytest_stage5_delete_target_{uuid4().hex}",
            )
            other_position_id = _insert_position(
                conn,
                name=f"pytest_stage5_delete_other_{uuid4().hex}",
            )
            second_unit_id = int(
                create_unit(conn, f"pytest_stage5_delete_unit_{uuid4().hex}") or 0
            )
            assert second_unit_id > 0
            conn.execute(
                text(
                    """
                    INSERT INTO public.org_unit_allowed_positions (
                        org_unit_id, position_id, is_active
                    )
                    VALUES
                        (:first_unit_id, :target_position_id, FALSE),
                        (:second_unit_id, :target_position_id, FALSE),
                        (:first_unit_id, :other_position_id, FALSE)
                    """
                ),
                {
                    "first_unit_id": int(seed["unit_id"]),
                    "second_unit_id": second_unit_id,
                    "target_position_id": target_position_id,
                    "other_position_id": other_position_id,
                },
            )

        response = client.delete(
            f"/directory/positions/{target_position_id}",
            headers=sysadmin_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json() == {"ok": True, "position_id": target_position_id}

        with engine.connect() as conn:
            assert conn.execute(
                text("SELECT 1 FROM public.positions WHERE position_id = :position_id"),
                {"position_id": target_position_id},
            ).first() is None
            assert conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM public.org_unit_allowed_positions
                    WHERE position_id = :position_id
                    """
                ),
                {"position_id": target_position_id},
            ).scalar_one() == 0
            other_link = _stage5_link(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=other_position_id,
            )
            assert other_link is not None
            assert other_link["is_active"] is False
    finally:
        _cleanup_stage5_rows(
            position_ids=[pid for pid in (target_position_id, other_position_id) if pid],
            org_unit_ids=[second_unit_id] if second_unit_id else None,
        )


def test_stage5_global_delete_restores_inactive_cleanup_for_other_blocker(
    client,
    seed,
    sysadmin_headers,
):
    position_id = 0
    employee_name = f"pytest_stage5_delete_blocker_{uuid4().hex}"
    try:
        with engine.begin() as conn:
            position_id = _insert_position(
                conn,
                name=f"pytest_stage5_delete_rollback_{uuid4().hex}",
            )
            link_id = int(
                conn.execute(
                    text(
                        """
                        INSERT INTO public.org_unit_allowed_positions (
                            org_unit_id, position_id, is_active
                        )
                        VALUES (:org_unit_id, :position_id, FALSE)
                        RETURNING org_unit_allowed_position_id
                        """
                    ),
                    {"org_unit_id": int(seed["unit_id"]), "position_id": position_id},
                ).scalar_one()
            )
            conn.execute(
                text(
                    """
                    INSERT INTO public.employees (
                        full_name, org_unit_id, position_id,
                        is_active, employment_rate, date_from
                    )
                    VALUES (
                        :name, :org_unit_id, :position_id,
                        TRUE, 1.00, :date_from
                    )
                    """
                ),
                {
                    "name": employee_name,
                    "org_unit_id": int(seed["unit_id"]),
                    "position_id": position_id,
                    "date_from": date.today(),
                },
            )

        response = client.delete(
            f"/directory/positions/{position_id}",
            headers=sysadmin_headers,
        )
        assert response.status_code == 409, response.text
        detail = response.json()["detail"]
        assert detail["error_code"] == "POSITION_HAS_DEPENDENCIES"
        assert detail.get("race_detected") is None
        assert "employees.position_id" in {
            dependency["key"] for dependency in detail["dependencies"]
        }

        with engine.connect() as conn:
            assert conn.execute(
                text("SELECT 1 FROM public.positions WHERE position_id = :position_id"),
                {"position_id": position_id},
            ).first() is not None
            restored_link = _stage5_link(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
            )
            assert int(restored_link["org_unit_allowed_position_id"]) == link_id
            assert restored_link["is_active"] is False
    finally:
        if position_id:
            _cleanup_stage5_rows(
                position_ids=[position_id],
                employee_names=[employee_name],
            )


def test_stage5_child_dependency_before_position_lock_is_seen_by_real_preflight(seed):
    position_id = 0
    employee_name = f"pytest_stage5_child_before_lock_{uuid4().hex}"
    child_conn = None
    child_tx = None
    worker = None
    started = Event()
    acquired = Event()
    result: dict[str, object] = {}
    try:
        with engine.begin() as conn:
            position_id = _insert_position(
                conn, name=f"pytest_stage5_before_lock_position_{uuid4().hex}"
            )

        child_conn = engine.connect()
        child_tx = child_conn.begin()
        child_conn.execute(
            text(
                """
                INSERT INTO public.employees (
                    full_name, org_unit_id, position_id,
                    is_active, employment_rate, date_from
                )
                VALUES (:name, :org_unit_id, :position_id, TRUE, 1.00, :date_from)
                """
            ),
            {
                "name": employee_name,
                "org_unit_id": int(seed["unit_id"]),
                "position_id": position_id,
                "date_from": date.today(),
            },
        )

        def delete_preflight_worker() -> None:
            with engine.connect() as conn:
                tx = conn.begin()
                try:
                    result["backend_pid"] = int(
                        conn.execute(text("SELECT pg_backend_pid()")).scalar_one()
                    )
                    started.set()
                    conn.execute(
                        text(
                            """
                            SELECT position_id
                            FROM public.positions
                            WHERE position_id = :position_id
                            FOR UPDATE
                            """
                        ),
                        {"position_id": position_id},
                    ).one()
                    acquired.set()
                    result["summary"] = positions_routes.check_position_dependencies(
                        conn, position_id=position_id
                    )
                except BaseException as exc:
                    result["error"] = exc
                finally:
                    tx.rollback()

        worker = Thread(target=delete_preflight_worker, daemon=True)
        worker.start()
        assert started.wait(2.0)
        _wait_for_postgres_lock_wait(int(result["backend_pid"]))
        assert not acquired.is_set()

        child_tx.commit()
        child_tx = None
        assert acquired.wait(2.0)
        _join_worker(worker)
        assert "error" not in result
        summary = result["summary"]
        assert isinstance(summary, PositionDependencySummary)
        assert summary.can_delete is False
        assert "employees.position_id" in {item.key for item in summary.dependencies}
        with engine.connect() as conn:
            assert conn.execute(
                text("SELECT 1 FROM public.positions WHERE position_id = :position_id"),
                {"position_id": position_id},
            ).first() is not None
    finally:
        if child_tx is not None:
            child_tx.rollback()
        if child_conn is not None:
            child_conn.close()
        if worker is not None and worker.is_alive():
            worker.join(1.0)
        if position_id:
            _cleanup_stage5_rows(
                position_ids=[position_id], employee_names=[employee_name]
            )


def test_stage5_child_insert_after_position_lock_fails_on_child_statement(seed):
    position_id = 0
    employee_name = f"pytest_stage5_child_after_lock_{uuid4().hex}"
    parent_conn = None
    parent_tx = None
    worker = None
    started = Event()
    result: dict[str, object] = {}
    try:
        with engine.begin() as conn:
            position_id = _insert_position(
                conn, name=f"pytest_stage5_after_lock_position_{uuid4().hex}"
            )

        parent_conn = engine.connect()
        parent_tx = parent_conn.begin()
        parent_conn.execute(
            text(
                """
                SELECT position_id FROM public.positions
                WHERE position_id = :position_id
                FOR UPDATE
                """
            ),
            {"position_id": position_id},
        ).one()
        assert positions_routes.check_position_dependencies(
            parent_conn, position_id=position_id
        ).can_delete is True

        def child_insert_worker() -> None:
            with engine.connect() as conn:
                tx = conn.begin()
                try:
                    result["backend_pid"] = int(
                        conn.execute(text("SELECT pg_backend_pid()")).scalar_one()
                    )
                    started.set()
                    conn.execute(
                        text(
                            """
                            INSERT INTO public.employees (
                                full_name, org_unit_id, position_id,
                                is_active, employment_rate, date_from
                            )
                            VALUES (
                                :name, :org_unit_id, :position_id,
                                TRUE, 1.00, :date_from
                            )
                            """
                        ),
                        {
                            "name": employee_name,
                            "org_unit_id": int(seed["unit_id"]),
                            "position_id": position_id,
                            "date_from": date.today(),
                        },
                    )
                    tx.commit()
                    result["committed"] = True
                except sa_exc.IntegrityError as exc:
                    tx.rollback()
                    result["sqlstate"] = getattr(exc.orig, "sqlstate", None) or getattr(
                        exc.orig, "pgcode", None
                    )
                    result["constraint_name"] = getattr(
                        getattr(exc.orig, "diag", None), "constraint_name", None
                    )
                    result["connection_ok"] = conn.execute(text("SELECT 1")).scalar_one()
                except BaseException as exc:
                    tx.rollback()
                    result["error"] = exc

        worker = Thread(target=child_insert_worker, daemon=True)
        worker.start()
        assert started.wait(2.0)
        _wait_for_postgres_lock_wait(int(result["backend_pid"]))

        deleted_id = parent_conn.execute(
            text(
                """
                DELETE FROM public.positions
                WHERE position_id = :position_id
                RETURNING position_id
                """
            ),
            {"position_id": position_id},
        ).scalar_one()
        assert int(deleted_id) == position_id
        parent_tx.commit()
        parent_tx = None

        _join_worker(worker)
        assert "error" not in result
        assert result.get("committed") is None
        assert result["sqlstate"] == "23503"
        with engine.connect() as conn:
            expected_constraints = {
                dependency.constraint_name
                for dependency in load_position_blocking_foreign_keys(conn)
                if dependency.table_name == "employees"
            }
            assert result["constraint_name"] in expected_constraints
            assert result["connection_ok"] == 1
            assert conn.execute(
                text("SELECT 1 FROM public.positions WHERE position_id = :position_id"),
                {"position_id": position_id},
            ).first() is None
            assert conn.execute(
                text("SELECT 1 FROM public.employees WHERE full_name = :name"),
                {"name": employee_name},
            ).first() is None
    finally:
        if parent_tx is not None:
            parent_tx.rollback()
        if parent_conn is not None:
            parent_conn.close()
        if worker is not None and worker.is_alive():
            worker.join(1.0)
        if position_id:
            _cleanup_stage5_rows(
                position_ids=[position_id], employee_names=[employee_name]
            )


def test_stage5_child_update_after_position_lock_fails_and_preserves_original_fk(seed):
    source_position_id = 0
    target_position_id = 0
    employee_name = f"pytest_stage5_child_update_{uuid4().hex}"
    parent_conn = None
    parent_tx = None
    worker = None
    started = Event()
    result: dict[str, object] = {}
    try:
        with engine.begin() as conn:
            source_position_id = _insert_position(
                conn, name=f"pytest_stage5_update_source_{uuid4().hex}"
            )
            target_position_id = _insert_position(
                conn, name=f"pytest_stage5_update_target_{uuid4().hex}"
            )
            conn.execute(
                text(
                    """
                    INSERT INTO public.employees (
                        full_name, org_unit_id, position_id,
                        is_active, employment_rate, date_from
                    )
                    VALUES (
                        :name, :org_unit_id, :position_id,
                        TRUE, 1.00, :date_from
                    )
                    """
                ),
                {
                    "name": employee_name,
                    "org_unit_id": int(seed["unit_id"]),
                    "position_id": source_position_id,
                    "date_from": date.today(),
                },
            )

        parent_conn = engine.connect()
        parent_tx = parent_conn.begin()
        parent_conn.execute(
            text(
                """
                SELECT position_id FROM public.positions
                WHERE position_id = :position_id
                FOR UPDATE
                """
            ),
            {"position_id": target_position_id},
        ).one()
        assert positions_routes.check_position_dependencies(
            parent_conn, position_id=target_position_id
        ).can_delete is True

        def child_update_worker() -> None:
            with engine.connect() as conn:
                tx = conn.begin()
                try:
                    result["backend_pid"] = int(
                        conn.execute(text("SELECT pg_backend_pid()")).scalar_one()
                    )
                    started.set()
                    conn.execute(
                        text(
                            """
                            UPDATE public.employees
                            SET position_id = :target_position_id
                            WHERE full_name = :name
                            """
                        ),
                        {
                            "target_position_id": target_position_id,
                            "name": employee_name,
                        },
                    )
                    tx.commit()
                    result["committed"] = True
                except sa_exc.IntegrityError as exc:
                    tx.rollback()
                    result["sqlstate"] = getattr(exc.orig, "sqlstate", None) or getattr(
                        exc.orig, "pgcode", None
                    )
                    result["constraint_name"] = getattr(
                        getattr(exc.orig, "diag", None), "constraint_name", None
                    )
                    result["connection_ok"] = conn.execute(text("SELECT 1")).scalar_one()
                except BaseException as exc:
                    tx.rollback()
                    result["error"] = exc

        worker = Thread(target=child_update_worker, daemon=True)
        worker.start()
        assert started.wait(2.0)
        _wait_for_postgres_lock_wait(int(result["backend_pid"]))

        deleted_id = parent_conn.execute(
            text(
                """
                DELETE FROM public.positions
                WHERE position_id = :position_id
                RETURNING position_id
                """
            ),
            {"position_id": target_position_id},
        ).scalar_one()
        assert int(deleted_id) == target_position_id
        parent_tx.commit()
        parent_tx = None

        _join_worker(worker)
        assert "error" not in result
        assert result.get("committed") is None
        assert result["sqlstate"] == "23503"
        with engine.connect() as conn:
            expected_constraints = {
                dependency.constraint_name
                for dependency in load_position_blocking_foreign_keys(conn)
                if dependency.table_name == "employees"
            }
            assert result["constraint_name"] in expected_constraints
            assert result["connection_ok"] == 1
            assert conn.execute(
                text("SELECT 1 FROM public.positions WHERE position_id = :position_id"),
                {"position_id": target_position_id},
            ).first() is None
            assert int(
                conn.execute(
                    text(
                        """
                        SELECT position_id FROM public.employees
                        WHERE full_name = :name
                        """
                    ),
                    {"name": employee_name},
                ).scalar_one()
            ) == source_position_id
    finally:
        if parent_tx is not None:
            parent_tx.rollback()
        if parent_conn is not None:
            parent_conn.close()
        if worker is not None and worker.is_alive():
            worker.join(1.0)
        if source_position_id or target_position_id:
            _cleanup_stage5_rows(
                position_ids=[
                    position_id
                    for position_id in (source_position_id, target_position_id)
                    if position_id
                ],
                employee_names=[employee_name],
            )


def test_stage5_defensive_position_delete_fk_classifier_restores_full_request(
    client,
    seed,
    sysadmin_headers,
    monkeypatch: pytest.MonkeyPatch,
):
    position_id = 0
    employee_name = f"pytest_stage5_fk_race_{uuid4().hex}"
    original_check = positions_routes.check_position_dependencies
    calls = 0
    refresh_state: dict[str, object] = {}
    try:
        with engine.begin() as conn:
            position_id = _insert_position(
                conn,
                name=f"pytest_stage5_fk_race_position_{uuid4().hex}",
            )
            link_id = int(
                conn.execute(
                    text(
                        """
                        INSERT INTO public.org_unit_allowed_positions (
                            org_unit_id, position_id, is_active
                        )
                        VALUES (:org_unit_id, :position_id, FALSE)
                        RETURNING org_unit_allowed_position_id
                        """
                    ),
                    {"org_unit_id": int(seed["unit_id"]), "position_id": position_id},
                ).scalar_one()
            )
            conn.execute(
                text(
                    """
                    INSERT INTO public.employees (
                        full_name, org_unit_id, position_id,
                        is_active, employment_rate, date_from
                    )
                    VALUES (
                        :name, :org_unit_id, :position_id,
                        TRUE, 1.00, :date_from
                    )
                    """
                ),
                {
                    "name": employee_name,
                    "org_unit_id": int(seed["unit_id"]),
                    "position_id": position_id,
                    "date_from": date.today(),
                },
            )

        def controlled_preflight(conn, *, position_id: int, dependencies=None):
            # Defensive-branch integration evidence only. Bypass the real
            # preflight once so the unchanged production Position DELETE reaches
            # a real PostgreSQL 23503 from a production restrictive inbound FK.
            # Position FOR UPDATE remains intact; the classifier, exception and
            # constraint identity are real. This does not test the production
            # dependency detector, demonstrate a reachable concurrency race, or
            # justify changing the approved lock order. Every later call delegates
            # to the unmodified production detector after request rollback.
            nonlocal calls
            calls += 1
            if calls == 1:
                return PositionDependencySummary(position_id=position_id, dependencies=())

            refresh_state["position_restored"] = conn.execute(
                text("SELECT 1 FROM public.positions WHERE position_id = :position_id"),
                {"position_id": position_id},
            ).first() is not None
            restored_link = _stage5_link(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
            )
            refresh_state["link_restored"] = (
                restored_link is not None and restored_link["is_active"] is False
            )
            summary = original_check(
                conn, position_id=position_id, dependencies=dependencies
            )
            refresh_state["production_summary"] = summary
            return summary

        monkeypatch.setattr(
            positions_routes,
            "check_position_dependencies",
            controlled_preflight,
        )
        response = client.delete(
            f"/directory/positions/{position_id}",
            headers=sysadmin_headers,
        )
        assert calls == 2
        assert refresh_state["position_restored"] is True
        assert refresh_state["link_restored"] is True
        refreshed_summary = refresh_state["production_summary"]
        assert isinstance(refreshed_summary, PositionDependencySummary)
        assert refreshed_summary.can_delete is False
        assert "employees.position_id" in {
            item.key for item in refreshed_summary.dependencies
        }
        assert response.status_code == 409, response.text
        assert response.json() == {
            "detail": {
                "error_code": "POSITION_HAS_DEPENDENCIES",
                "race_detected": True,
            }
        }
        detail = response.json()["detail"]
        assert detail == {
            "error_code": "POSITION_HAS_DEPENDENCIES",
            "race_detected": True,
        }
        assert "constraint" not in detail
        assert "dependencies" not in detail
        assert "schema" not in detail
        assert "table" not in detail
        serialized = response.text.lower()
        for forbidden in (
            "constraint",
            "schema",
            "table",
            "delete from",
            "sqlstate",
            "integrityerror",
            "driver",
            employee_name.lower(),
        ):
            assert forbidden not in serialized

        with engine.connect() as conn:
            assert conn.execute(
                text("SELECT 1 FROM public.positions WHERE position_id = :position_id"),
                {"position_id": position_id},
            ).first() is not None
            restored_link = _stage5_link(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
            )
            assert int(restored_link["org_unit_allowed_position_id"]) == link_id
            assert restored_link["is_active"] is False
            assert conn.execute(
                text("SELECT 1 FROM public.employees WHERE full_name = :name"),
                {"name": employee_name},
            ).first() is not None
    finally:
        if position_id:
            _cleanup_stage5_rows(
                position_ids=[position_id],
                employee_names=[employee_name],
            )


def test_stage5_position_delete_metadata_lookup_failure_is_not_defensive_409(
    client,
    seed,
    sysadmin_headers,
    monkeypatch: pytest.MonkeyPatch,
):
    position_id = 0
    employee_name = f"pytest_stage5_metadata_failure_{uuid4().hex}"
    metadata_error = RuntimeError("pytest metadata lookup failure")
    calls = 0
    try:
        with engine.begin() as conn:
            position_id = _insert_position(
                conn, name=f"pytest_stage5_metadata_position_{uuid4().hex}"
            )
            link_id = int(
                conn.execute(
                    text(
                        """
                        INSERT INTO public.org_unit_allowed_positions (
                            org_unit_id, position_id, is_active
                        )
                        VALUES (:org_unit_id, :position_id, FALSE)
                        RETURNING org_unit_allowed_position_id
                        """
                    ),
                    {"org_unit_id": int(seed["unit_id"]), "position_id": position_id},
                ).scalar_one()
            )
            conn.execute(
                text(
                    """
                    INSERT INTO public.employees (
                        full_name, org_unit_id, position_id,
                        is_active, employment_rate, date_from
                    )
                    VALUES (
                        :name, :org_unit_id, :position_id,
                        TRUE, 1.00, :date_from
                    )
                    """
                ),
                {
                    "name": employee_name,
                    "org_unit_id": int(seed["unit_id"]),
                    "position_id": position_id,
                    "date_from": date.today(),
                },
            )

        def controlled_first_preflight(conn, *, position_id: int, dependencies=None):
            nonlocal calls
            calls += 1
            return PositionDependencySummary(position_id=position_id, dependencies=())

        def fail_metadata_lookup(conn):
            raise metadata_error

        monkeypatch.setattr(
            positions_routes, "check_position_dependencies", controlled_first_preflight
        )
        monkeypatch.setattr(
            positions_routes, "load_position_blocking_foreign_keys", fail_metadata_lookup
        )
        with pytest.raises(RuntimeError) as raised:
            client.delete(
                f"/directory/positions/{position_id}", headers=sysadmin_headers
            )
        assert raised.value is metadata_error
        assert calls == 1

        with engine.connect() as conn:
            assert conn.execute(text("SELECT 1")).scalar_one() == 1
            assert conn.execute(
                text("SELECT 1 FROM public.positions WHERE position_id = :position_id"),
                {"position_id": position_id},
            ).first() is not None
            restored_link = _stage5_link(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
            )
            assert int(restored_link["org_unit_allowed_position_id"]) == link_id
            assert restored_link["is_active"] is False
            assert conn.execute(
                text("SELECT 1 FROM public.employees WHERE full_name = :name"),
                {"name": employee_name},
            ).first() is not None
    finally:
        if position_id:
            _cleanup_stage5_rows(
                position_ids=[position_id], employee_names=[employee_name]
            )


def test_stage5_fk_race_classifier_requires_discovered_position_fk_identity():
    class Diagnostic:
        def __init__(
            self,
            *,
            constraint_name: str | None,
            schema_name: str | None = None,
            table_name: str | None = None,
        ):
            self.constraint_name = constraint_name
            self.schema_name = schema_name
            self.table_name = table_name

    class OriginalError(Exception):
        def __init__(self, sqlstate: str, diag: Diagnostic):
            self.sqlstate = sqlstate
            self.diag = diag

    def integrity_error(
        *,
        sqlstate: str,
        constraint_name: str | None,
        schema_name: str | None = None,
        table_name: str | None = None,
        statement: str = "not a Position delete",
    ) -> sa_exc.IntegrityError:
        return sa_exc.IntegrityError(
            statement,
            {},
            OriginalError(
                sqlstate,
                Diagnostic(
                    constraint_name=constraint_name,
                    schema_name=schema_name,
                    table_name=table_name,
                ),
            ),
        )

    with engine.connect() as conn:
        dependencies = load_position_blocking_foreign_keys(conn)
        assert dependencies
        known = next(dep for dep in dependencies if dep.table_name == "employees")
        other_fk = conn.execute(
            text(
                """
                SELECT c.conname, child_ns.nspname, child.relname
                FROM pg_constraint c
                JOIN pg_class parent ON parent.oid = c.confrelid
                JOIN pg_namespace parent_ns ON parent_ns.oid = parent.relnamespace
                JOIN pg_class child ON child.oid = c.conrelid
                JOIN pg_namespace child_ns ON child_ns.oid = child.relnamespace
                WHERE c.contype = 'f'
                  AND NOT (
                      parent_ns.nspname = 'public'
                      AND parent.relname = 'positions'
                  )
                ORDER BY child_ns.nspname, child.relname, c.conname
                LIMIT 1
                """
            )
        ).mappings().one()

    confirmed = integrity_error(
        sqlstate="23503",
        constraint_name=known.constraint_name,
        schema_name=known.table_schema,
        table_name=known.table_name,
    )
    unknown_constraint = integrity_error(
        sqlstate="23503",
        constraint_name=f"pytest_unknown_fk_{uuid4().hex}",
    )
    unrelated_fk = integrity_error(
        sqlstate="23503",
        constraint_name=str(other_fk["conname"]),
        schema_name=str(other_fk["nspname"]),
        table_name=str(other_fk["relname"]),
    )
    missing_constraint = integrity_error(sqlstate="23503", constraint_name=None)
    empty_constraint = integrity_error(sqlstate="23503", constraint_name="")
    mismatched_schema = integrity_error(
        sqlstate="23503",
        constraint_name=known.constraint_name,
        schema_name=f"not_{known.table_schema}",
        table_name=known.table_name,
    )
    mismatched_table = integrity_error(
        sqlstate="23503",
        constraint_name=known.constraint_name,
        schema_name=known.table_schema,
        table_name=f"not_{known.table_name}",
    )
    non_fk = integrity_error(
        sqlstate="23505",
        constraint_name=known.constraint_name,
        schema_name=known.table_schema,
        table_name=known.table_name,
    )

    assert positions_routes._is_position_delete_fk_race(confirmed, dependencies) is True
    assert positions_routes._is_position_delete_fk_race(unknown_constraint, dependencies) is False
    assert positions_routes._is_position_delete_fk_race(unrelated_fk, dependencies) is False
    assert positions_routes._is_position_delete_fk_race(missing_constraint, dependencies) is False
    assert positions_routes._is_position_delete_fk_race(empty_constraint, dependencies) is False
    assert positions_routes._is_position_delete_fk_race(mismatched_schema, dependencies) is False
    assert positions_routes._is_position_delete_fk_race(mismatched_table, dependencies) is False
    assert positions_routes._is_position_delete_fk_race(non_fk, dependencies) is False


def test_stage5_fk_error_outside_direct_position_delete_is_not_classified_as_race(
    client,
    seed,
    sysadmin_headers,
    monkeypatch: pytest.MonkeyPatch,
):
    class Diagnostic:
        constraint_name: str
        schema_name: str
        table_name: str

    class OriginalError(Exception):
        sqlstate = "23503"
        diag = Diagnostic()

    position_id = 0
    try:
        with engine.begin() as conn:
            position_id = _insert_position(
                conn,
                name=f"pytest_stage5_non_delete_fk_{uuid4().hex}",
            )
            conn.execute(
                text(
                    """
                    INSERT INTO public.org_unit_allowed_positions (
                        org_unit_id, position_id, is_active
                    )
                    VALUES (:org_unit_id, :position_id, FALSE)
                    """
                ),
                {"org_unit_id": int(seed["unit_id"]), "position_id": position_id},
            )
            known = next(
                dependency
                for dependency in load_position_blocking_foreign_keys(conn)
                if dependency.table_name == "employees"
            )

        Diagnostic.constraint_name = known.constraint_name
        Diagnostic.schema_name = known.table_schema
        Diagnostic.table_name = known.table_name

        misleading_error = sa_exc.IntegrityError(
            "SELECT 1 /* DELETE FROM public.positions */",
            {},
            OriginalError(),
        )

        def fail_dependency_check(*args, **kwargs):
            raise misleading_error

        monkeypatch.setattr(
            positions_routes,
            "check_position_dependencies",
            fail_dependency_check,
        )
        with pytest.raises(sa_exc.IntegrityError) as raised:
            client.delete(
                f"/directory/positions/{position_id}",
                headers=sysadmin_headers,
            )
        assert raised.value is misleading_error

        with engine.connect() as conn:
            assert conn.execute(text("SELECT 1")).scalar_one() == 1
            assert conn.execute(
                text("SELECT 1 FROM public.positions WHERE position_id = :position_id"),
                {"position_id": position_id},
            ).first() is not None
            link = _stage5_link(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
            )
            assert link is not None
            assert link["is_active"] is False
    finally:
        if position_id:
            _cleanup_stage5_rows(position_ids=[position_id])
