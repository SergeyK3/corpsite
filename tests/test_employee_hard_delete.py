# tests/test_employee_hard_delete.py
"""Administrative hard-delete for employees (sysadmin only)."""
from __future__ import annotations

from typing import Any, Dict, List
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.security.directory_scope import SYSTEM_ADMIN_ROLE_ID
from tests.conftest import auth_headers, create_user, get_columns, insert_returning_id, table_exists


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _ensure_system_admin_role(conn) -> None:
    cols = get_columns(conn, "roles")
    exists = conn.execute(
        text("SELECT 1 FROM public.roles WHERE role_id = :rid LIMIT 1"),
        {"rid": SYSTEM_ADMIN_ROLE_ID},
    ).first()
    if exists:
        return
    values: dict[str, Any] = {"role_id": SYSTEM_ADMIN_ROLE_ID, "name": "pytest_system_admin"}
    if "code" in cols:
        values["code"] = "SYSTEM_ADMIN"
    insert_returning_id(conn, table="roles", id_col="role_id", values=values)


def _create_position(conn, *, name: str) -> int:
    cols = get_columns(conn, "positions")
    values: Dict[str, Any] = {"name": name}
    if "category" in cols:
        values["category"] = "other"
    return insert_returning_id(conn, table="positions", id_col="position_id", values=values)


def _create_person(conn, *, full_name: str) -> int:
    suffix = uuid4().hex[:10]
    return insert_returning_id(
        conn,
        table="persons",
        id_col="person_id",
        values={
            "full_name": full_name,
            "match_key": f"pytest_{suffix}",
            "source": "manual",
            "person_status": "active",
        },
    )


def _create_employee(
    conn,
    *,
    full_name: str,
    org_unit_id: int,
    position_id: int,
    person_id: int | None = None,
    is_active: bool = True,
    operational_status: str | None = None,
) -> int:
    values: Dict[str, Any] = {
        "full_name": full_name,
        "org_unit_id": int(org_unit_id),
        "position_id": int(position_id),
        "employment_rate": 1.0,
        "is_active": is_active,
    }
    if person_id is not None and "person_id" in get_columns(conn, "employees"):
        values["person_id"] = int(person_id)
    if operational_status is not None and "operational_status" in get_columns(conn, "employees"):
        values["operational_status"] = operational_status
    return insert_returning_id(conn, table="employees", id_col="employee_id", values=values)


def _create_employee_event(conn, *, employee_id: int, created_by: int) -> None:
    if not table_exists(conn, "employee_events"):
        return
    conn.execute(
        text(
            """
            INSERT INTO public.employee_events (
                employee_id, event_type, effective_date, created_by
            )
            VALUES (:employee_id, 'HIRE', CURRENT_DATE, :created_by)
            """
        ),
        {"employee_id": int(employee_id), "created_by": int(created_by)},
    )


def _create_user_for_employee(conn, *, employee_id: int, role_id: int, unit_id: int) -> int:
    user_id = create_user(
        conn,
        full_name=f"Pytest User {uuid4().hex[:8]}",
        role_id=int(role_id),
        unit_id=int(unit_id),
    )
    if "employee_id" in get_columns(conn, "users"):
        conn.execute(
            text("UPDATE public.users SET employee_id = :eid WHERE user_id = :uid"),
            {"eid": int(employee_id), "uid": int(user_id)},
        )
    return int(user_id)


@pytest.fixture
def sysadmin_headers(seed, monkeypatch):
    monkeypatch.delenv("DIRECTORY_PRIVILEGED_USER_IDS", raising=False)
    monkeypatch.delenv("DIRECTORY_PRIVILEGED_ROLE_IDS", raising=False)
    suffix = uuid4().hex[:8]
    user_id: int | None = None
    with engine.begin() as conn:
        _ensure_system_admin_role(conn)
        user_id = create_user(
            conn,
            full_name=f"Pytest HardDelete Admin {suffix}",
            role_id=SYSTEM_ADMIN_ROLE_ID,
            unit_id=int(seed["unit_id"]),
        )
    headers = auth_headers(user_id)
    try:
        yield headers
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM public.users WHERE user_id = :uid"), {"uid": user_id})


@pytest.fixture
def observer_headers(seed):
    return auth_headers(seed["executor_user_id"])


@pytest.fixture
def employee_bundle(seed):
    created: Dict[str, Any] = {
        "position_ids": [],
        "person_ids": [],
        "employee_ids": [],
        "user_ids": [],
    }

    with engine.begin() as conn:
        if not table_exists(conn, "employees"):
            pytest.skip("employees table not available")

        position_id = _create_position(conn, name=f"pytest_hd_pos_{uuid4().hex[:8]}")
        created["position_ids"].append(position_id)

        person_id = _create_person(conn, full_name=f"Pytest HardDelete Person {uuid4().hex[:8]}")
        created["person_ids"].append(person_id)

        employee_id = _create_employee(
            conn,
            full_name=f"Pytest HardDelete Employee {uuid4().hex[:8]}",
            org_unit_id=int(seed["unit_id"]),
            position_id=position_id,
            person_id=person_id,
        )
        created["employee_ids"].append(employee_id)

        _create_employee_event(conn, employee_id=employee_id, created_by=int(seed["initiator_user_id"]))

        if table_exists(conn, "personnel_record_metadata"):
            insert_returning_id(
                conn,
                table="personnel_record_metadata",
                id_col="person_id",
                values={"person_id": person_id},
            )

        if table_exists(conn, "contacts") and "person_id" in get_columns(conn, "contacts"):
            conn.execute(
                text(
                    """
                    INSERT INTO public.contacts (person_id, full_name, phone)
                    VALUES (:person_id, 'Pytest Contact', '+70000000000')
                    """
                ),
                {"person_id": person_id},
            )

        user_id = _create_user_for_employee(
            conn,
            employee_id=employee_id,
            role_id=int(seed["executor_role_id"]),
            unit_id=int(seed["unit_id"]),
        )
        created["user_ids"].append(user_id)

        control_position_id = _create_position(conn, name=f"pytest_hd_ctrl_pos_{uuid4().hex[:8]}")
        created["position_ids"].append(control_position_id)
        control_person_id = _create_person(conn, full_name=f"Pytest Control Person {uuid4().hex[:8]}")
        created["person_ids"].append(control_person_id)
        control_employee_id = _create_employee(
            conn,
            full_name=f"Pytest Control Employee {uuid4().hex[:8]}",
            org_unit_id=int(seed["unit_id"]),
            position_id=control_position_id,
            person_id=control_person_id,
        )
        created["employee_ids"].append(control_employee_id)
        created["control_employee_id"] = control_employee_id
        created["control_person_id"] = control_person_id
        created["target_employee_id"] = employee_id
        created["target_person_id"] = person_id

    try:
        yield created
    finally:
        with engine.begin() as conn:
            for eid in created["employee_ids"]:
                if table_exists(conn, "employees") and conn.execute(
                    text("SELECT 1 FROM public.employees WHERE employee_id = :id LIMIT 1"),
                    {"id": int(eid)},
                ).first():
                    conn.execute(
                        text("DELETE FROM public.employee_events WHERE employee_id = :id"),
                        {"id": int(eid)},
                    )
                    conn.execute(
                        text("DELETE FROM public.users WHERE employee_id = :id"),
                        {"id": int(eid)},
                    )
                    conn.execute(
                        text("DELETE FROM public.employees WHERE employee_id = :id"),
                        {"id": int(eid)},
                    )
            for pid in created["person_ids"]:
                if table_exists(conn, "personnel_record_metadata"):
                    conn.execute(
                        text("DELETE FROM public.personnel_record_metadata WHERE person_id = :id"),
                        {"id": int(pid)},
                    )
                if table_exists(conn, "contacts"):
                    conn.execute(
                        text("DELETE FROM public.contacts WHERE person_id = :id"),
                        {"id": int(pid)},
                    )
                if table_exists(conn, "persons") and conn.execute(
                    text("SELECT 1 FROM public.persons WHERE person_id = :id LIMIT 1"),
                    {"id": int(pid)},
                ).first():
                    conn.execute(text("DELETE FROM public.persons WHERE person_id = :id"), {"id": int(pid)})
            for uid in created["user_ids"]:
                conn.execute(text("DELETE FROM public.users WHERE user_id = :id"), {"id": int(uid)})
            for pos_id in created["position_ids"]:
                conn.execute(
                    text("DELETE FROM public.positions WHERE position_id = :id"),
                    {"id": int(pos_id)},
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_hard_delete_forbidden_for_non_sysadmin(client, observer_headers, employee_bundle):
    employee_id = int(employee_bundle["target_employee_id"])
    resp = client.delete(
        f"/directory/employees/{employee_id}",
        headers=observer_headers,
    )
    assert resp.status_code == 403

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT 1 FROM public.employees WHERE employee_id = :id"),
            {"id": employee_id},
        ).first()
        assert row is not None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_hard_delete_cascade_and_audit(client, sysadmin_headers, employee_bundle):
    employee_id = int(employee_bundle["target_employee_id"])
    person_id = int(employee_bundle["target_person_id"])
    control_employee_id = int(employee_bundle["control_employee_id"])
    control_person_id = int(employee_bundle["control_person_id"])
    linked_user_id = int(employee_bundle["user_ids"][0])

    resp = client.delete(f"/directory/employees/{employee_id}", headers=sysadmin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("ok") is True
    assert int(body.get("employee_id")) == employee_id
    assert body.get("person_deleted") is True

    with engine.connect() as conn:
        assert conn.execute(
            text("SELECT 1 FROM public.employees WHERE employee_id = :id"),
            {"id": employee_id},
        ).first() is None
        assert conn.execute(
            text("SELECT 1 FROM public.persons WHERE person_id = :id"),
            {"id": person_id},
        ).first() is None
        assert conn.execute(
            text("SELECT 1 FROM public.users WHERE user_id = :id"),
            {"id": linked_user_id},
        ).first() is None
        if table_exists(conn, "employee_events"):
            count = conn.execute(
                text("SELECT COUNT(*)::int FROM public.employee_events WHERE employee_id = :id"),
                {"id": employee_id},
            ).scalar_one()
            assert int(count) == 0
        if table_exists(conn, "contacts"):
            count = conn.execute(
                text("SELECT COUNT(*)::int FROM public.contacts WHERE person_id = :id"),
                {"id": person_id},
            ).scalar_one()
            assert int(count) == 0

        assert conn.execute(
            text("SELECT 1 FROM public.employees WHERE employee_id = :id"),
            {"id": control_employee_id},
        ).first() is not None
        assert conn.execute(
            text("SELECT 1 FROM public.persons WHERE person_id = :id"),
            {"id": control_person_id},
        ).first() is not None

        if table_exists(conn, "security_audit_log"):
            audit = conn.execute(
                text(
                    """
                    SELECT event_type, metadata
                    FROM public.security_audit_log
                    WHERE event_type = 'EMPLOYEE_HARD_DELETED'
                      AND (metadata->>'employee_id')::bigint = :employee_id
                    ORDER BY audit_id DESC
                    LIMIT 1
                    """
                ),
                {"employee_id": employee_id},
            ).mappings().first()
            assert audit is not None
            assert audit["event_type"] == "EMPLOYEE_HARD_DELETED"
            meta = audit["metadata"]
            assert int(meta["employee_id"]) == employee_id
            assert meta.get("person_deleted") is True
            assert "full_name" in meta

    employee_bundle["employee_ids"].remove(employee_id)
    employee_bundle["person_ids"].remove(person_id)
    employee_bundle["user_ids"].remove(linked_user_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_hard_delete_preserves_person_with_other_employee(client, sysadmin_headers, seed):
    created_positions: List[int] = []
    created_person_ids: List[int] = []
    created_employee_ids: List[int] = []

    with engine.begin() as conn:
        position_id = _create_position(conn, name=f"pytest_hd_shared_pos_{uuid4().hex[:8]}")
        created_positions.append(position_id)
        person_id = _create_person(conn, full_name=f"Shared Person {uuid4().hex[:8]}")
        created_person_ids.append(person_id)
        employee_a = _create_employee(
            conn,
            full_name=f"Shared Employee A {uuid4().hex[:8]}",
            org_unit_id=int(seed["unit_id"]),
            position_id=position_id,
            person_id=person_id,
        )
        employee_b = _create_employee(
            conn,
            full_name=f"Shared Employee B {uuid4().hex[:8]}",
            org_unit_id=int(seed["unit_id"]),
            position_id=position_id,
            person_id=person_id,
            is_active=False,
            operational_status="terminated",
        )
        created_employee_ids.extend([employee_a, employee_b])

    try:
        resp = client.delete(f"/directory/employees/{employee_a}", headers=sysadmin_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json().get("person_deleted") is False

        with engine.connect() as conn:
            assert conn.execute(
                text("SELECT 1 FROM public.employees WHERE employee_id = :id"),
                {"id": int(employee_a)},
            ).first() is None
            assert conn.execute(
                text("SELECT 1 FROM public.employees WHERE employee_id = :id"),
                {"id": int(employee_b)},
            ).first() is not None
            assert conn.execute(
                text("SELECT 1 FROM public.persons WHERE person_id = :id"),
                {"id": int(person_id)},
            ).first() is not None
        created_employee_ids.remove(employee_a)
    finally:
        with engine.begin() as conn:
            for eid in created_employee_ids:
                conn.execute(text("DELETE FROM public.employees WHERE employee_id = :id"), {"id": int(eid)})
            for pid in created_person_ids:
                conn.execute(text("DELETE FROM public.persons WHERE person_id = :id"), {"id": int(pid)})
            for pos_id in created_positions:
                conn.execute(text("DELETE FROM public.positions WHERE position_id = :id"), {"id": int(pos_id)})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_hard_delete_rolls_back_on_audit_failure(client, sysadmin_headers, employee_bundle, monkeypatch):
    employee_id = int(employee_bundle["target_employee_id"])

    def _boom(**kwargs):
        raise RuntimeError("audit failed")

    monkeypatch.setattr(
        "app.services.employee_hard_delete_service.write_security_event",
        _boom,
    )

    resp = client.delete(f"/directory/employees/{employee_id}", headers=sysadmin_headers)
    assert resp.status_code == 500

    with engine.connect() as conn:
        assert conn.execute(
            text("SELECT 1 FROM public.employees WHERE employee_id = :id"),
            {"id": employee_id},
        ).first() is not None
        assert conn.execute(
            text("SELECT 1 FROM public.users WHERE employee_id = :id"),
            {"id": employee_id},
        ).first() is not None
