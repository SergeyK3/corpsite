# tests/test_employees_transfer_rbac_scope.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import (
    auth_headers,
    create_role,
    create_user,
    get_columns,
    insert_returning_id,
    safe_delete_many,
    table_exists,
)
from tests.personnel_visibility_test_helpers import (
    grant_dept_manager_visibility,
    revoke_user_access_grants,
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


def _create_unit_with_group(
    conn,
    *,
    name: str,
    group_id: int,
    parent_unit_id: Optional[int] = None,
) -> int:
    if not table_exists(conn, "org_units"):
        pytest.skip("org_units table not available")

    cols = get_columns(conn, "org_units")
    values: Dict[str, Any] = {"name": name}
    if "code" in cols:
        values["code"] = name
    if "group_id" in cols:
        values["group_id"] = int(group_id)
    if parent_unit_id is not None and "parent_unit_id" in cols:
        values["parent_unit_id"] = int(parent_unit_id)
    if "is_active" in cols:
        values["is_active"] = True

    return insert_returning_id(conn, table="org_units", id_col="unit_id", values=values)


def _find_group_id(conn) -> int:
    row = conn.execute(
        text(
            """
            SELECT group_id
            FROM public.org_units
            WHERE group_id IS NOT NULL
            LIMIT 1
            """
        )
    ).first()
    if row:
        return int(row[0])
    return 1


def _create_position(conn, *, name: str) -> int:
    cols = get_columns(conn, "positions")
    values: Dict[str, Any] = {"name": name}
    if "category" in cols:
        values["category"] = "other"
    return insert_returning_id(conn, table="positions", id_col="position_id", values=values)


def _create_employee(
    conn,
    *,
    full_name: str,
    org_unit_id: int,
    position_id: int,
) -> int:
    return insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values={
            "full_name": full_name,
            "org_unit_id": int(org_unit_id),
            "position_id": int(position_id),
            "employment_rate": 1.0,
            "is_active": True,
        },
    )


def _employee_ids_visible_to(client, user_id: int, *, q: str) -> Set[str]:
    resp = client.get(
        "/directory/employees",
        params={"status": "all", "q": q, "limit": 50},
        headers=auth_headers(int(user_id)),
    )
    assert resp.status_code == 200, resp.text
    return {
        str(x.get("id"))
        for x in (resp.json().get("items") or [])
        if x.get("id") is not None
    }


def _cleanup_users_by_logins(logins: List[str]) -> None:
    if not logins:
        return
    with engine.begin() as conn:
        if table_exists(conn, "users"):
            conn.execute(
                text("DELETE FROM public.users WHERE login = ANY(:logins)"),
                {"logins": logins},
            )


def _cleanup_users(user_ids: List[int]) -> None:
    if not user_ids:
        return
    with engine.begin() as conn:
        safe_delete_many(conn, "users", "user_id", [int(x) for x in user_ids])


def _cleanup_employees(employee_ids: List[int]) -> None:
    if not employee_ids:
        return
    with engine.begin() as conn:
        if table_exists(conn, "employee_events"):
            conn.execute(
                text("DELETE FROM public.employee_events WHERE employee_id = ANY(:ids)"),
                {"ids": [int(x) for x in employee_ids]},
            )
        if table_exists(conn, "users"):
            conn.execute(
                text("DELETE FROM public.users WHERE employee_id = ANY(:ids)"),
                {"ids": [int(x) for x in employee_ids]},
            )
        if table_exists(conn, "employees"):
            conn.execute(
                text("DELETE FROM public.employees WHERE employee_id = ANY(:ids)"),
                {"ids": [int(x) for x in employee_ids]},
            )


def _cleanup_positions(position_ids: List[int]) -> None:
    if not position_ids:
        return
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.positions WHERE position_id = ANY(:ids)"),
            {"ids": [int(x) for x in position_ids]},
        )


def _cleanup_units(unit_ids: List[int]) -> None:
    if not unit_ids:
        return
    with engine.begin() as conn:
        if table_exists(conn, "org_units"):
            conn.execute(
                text("DELETE FROM public.org_units WHERE unit_id = ANY(:ids)"),
                {"ids": [int(x) for x in unit_ids]},
            )


def _cleanup_roles(role_ids: List[int]) -> None:
    if not role_ids:
        return
    with engine.begin() as conn:
        if table_exists(conn, "roles"):
            conn.execute(
                text("DELETE FROM public.roles WHERE role_id = ANY(:ids)"),
                {"ids": [int(x) for x in role_ids]},
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_transfer_rbac_scoped_employee_visibility(client, seed, privileged_headers, monkeypatch):
    """Dept-scoped viewers: old unit sees employee before transfer, new unit after; old unit does not."""
    monkeypatch.setenv("DIRECTORY_RBAC_MODE", "dept")

    suffix = uuid4().hex[:8]
    search_q = f"PytestXferRbacScope{suffix}"
    transfer_name = f"{search_q} Transfer"
    created_employee_ids: List[int] = []
    created_position_ids: List[int] = []
    created_unit_ids: List[int] = []
    created_user_ids: List[int] = []
    created_role_ids: List[int] = []

    try:
        with engine.begin() as conn:
            if not table_exists(conn, "employees") or not table_exists(conn, "employee_events"):
                pytest.skip("employees / employee_events tables not available")

            group_id = _find_group_id(conn)
            from_unit_id = int(seed["unit_id"])
            to_unit_id = _create_unit_with_group(
                conn,
                name=f"pytest_xfer_rbac_to_{suffix}",
                group_id=group_id,
            )
            created_unit_ids.append(to_unit_id)

            viewer_role_id = create_role(conn, f"pytest_xfer_rbac_viewer_{suffix}")
            created_role_ids.append(viewer_role_id)
            new_unit_viewer_id = create_user(
                conn,
                full_name=f"PytestXferRbacViewer {suffix}",
                role_id=viewer_role_id,
                unit_id=to_unit_id,
            )
            created_user_ids.append(new_unit_viewer_id)

            position_id = _create_position(conn, name=f"pytest_xfer_rbac_pos_{suffix}")
            created_position_ids.append(position_id)

            transfer_employee_id = _create_employee(
                conn,
                full_name=transfer_name,
                org_unit_id=from_unit_id,
                position_id=position_id,
            )
            created_employee_ids.append(transfer_employee_id)

        grant_dept_manager_visibility(
            int(seed["executor_user_id"]),
            granted_by_user_id=int(seed["initiator_user_id"]),
        )
        grant_dept_manager_visibility(
            new_unit_viewer_id,
            granted_by_user_id=int(seed["initiator_user_id"]),
        )

        old_unit_viewer_id = int(seed["executor_user_id"])
        transfer_id = str(transfer_employee_id)

        before_old = _employee_ids_visible_to(client, old_unit_viewer_id, q=search_q)
        before_new = _employee_ids_visible_to(client, new_unit_viewer_id, q=search_q)
        assert transfer_id in before_old
        assert transfer_id not in before_new

        transfer = client.post(
            f"/directory/employees/{transfer_employee_id}/transfer",
            json={
                "to_org_unit_id": to_unit_id,
                "effective_date": "2026-06-15",
            },
            headers=privileged_headers,
        )
        assert transfer.status_code == 200, transfer.text

        after_old = _employee_ids_visible_to(client, old_unit_viewer_id, q=search_q)
        after_new = _employee_ids_visible_to(client, new_unit_viewer_id, q=search_q)
        assert transfer_id not in after_old
        assert transfer_id in after_new
    finally:
        revoke_user_access_grants(int(seed["executor_user_id"]))
        for user_id in created_user_ids:
            revoke_user_access_grants(user_id)
        _cleanup_employees(created_employee_ids)
        _cleanup_users(created_user_ids)
        _cleanup_roles(created_role_ids)
        _cleanup_positions(created_position_ids)
        _cleanup_units(created_unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_transfer_rbac_transferred_linked_user_scope_and_role(client, seed, privileged_headers, monkeypatch):
    """Transferred linked user: unit_id syncs, role_id unchanged, employee-list scope follows new unit."""
    monkeypatch.setenv("DIRECTORY_RBAC_MODE", "dept")

    suffix = uuid4().hex[:8]
    search_q = f"PytestXferRbacSelf{suffix}"
    transfer_name = f"{search_q} Self"
    peer_old_name = f"{search_q} PeerOld"
    peer_new_name = f"{search_q} PeerNew"
    created_employee_ids: List[int] = []
    created_position_ids: List[int] = []
    created_unit_ids: List[int] = []
    login: str | None = None
    linked_user_id: int | None = None
    role_id = int(seed["executor_role_id"])

    try:
        with engine.begin() as conn:
            if not table_exists(conn, "employees") or not table_exists(conn, "employee_events"):
                pytest.skip("employees / employee_events tables not available")

            group_id = _find_group_id(conn)
            from_unit_id = int(seed["unit_id"])
            to_unit_id = _create_unit_with_group(
                conn,
                name=f"pytest_xfer_rbac_self_to_{suffix}",
                group_id=group_id,
            )
            created_unit_ids.append(to_unit_id)

            position_id = _create_position(conn, name=f"pytest_xfer_rbac_self_pos_{suffix}")
            created_position_ids.append(position_id)

            transfer_employee_id = _create_employee(
                conn,
                full_name=transfer_name,
                org_unit_id=from_unit_id,
                position_id=position_id,
            )
            peer_old_id = _create_employee(
                conn,
                full_name=peer_old_name,
                org_unit_id=from_unit_id,
                position_id=position_id,
            )
            peer_new_id = _create_employee(
                conn,
                full_name=peer_new_name,
                org_unit_id=to_unit_id,
                position_id=position_id,
            )
            created_employee_ids.extend([transfer_employee_id, peer_old_id, peer_new_id])

        login = f"pytest_xfer_rbac_self_{uuid4().hex[:10]}"
        create_user_resp = client.post(
            "/directory/users",
            json={
                "employee_id": transfer_employee_id,
                "role_id": role_id,
                "login": login,
                "password": "SecretPass1",
            },
            headers=privileged_headers,
        )
        assert create_user_resp.status_code == 201, create_user_resp.text
        linked_user_id = int(create_user_resp.json()["user_id"])

        with engine.begin() as conn:
            before_user = conn.execute(
                text(
                    """
                    SELECT unit_id, role_id
                    FROM public.users
                    WHERE user_id = :user_id
                    """
                ),
                {"user_id": linked_user_id},
            ).mappings().first()
        assert before_user is not None
        assert int(before_user["unit_id"]) == from_unit_id
        assert int(before_user["role_id"]) == role_id

        grant_dept_manager_visibility(
            linked_user_id,
            granted_by_user_id=int(seed["initiator_user_id"]),
        )

        before_visible = _employee_ids_visible_to(client, linked_user_id, q=search_q)
        assert str(transfer_employee_id) in before_visible
        assert str(peer_old_id) in before_visible
        assert str(peer_new_id) not in before_visible

        transfer = client.post(
            f"/directory/employees/{transfer_employee_id}/transfer",
            json={
                "to_org_unit_id": to_unit_id,
                "effective_date": "2026-06-15",
            },
            headers=privileged_headers,
        )
        assert transfer.status_code == 200, transfer.text

        with engine.begin() as conn:
            after_user = conn.execute(
                text(
                    """
                    SELECT unit_id, role_id
                    FROM public.users
                    WHERE user_id = :user_id
                    """
                ),
                {"user_id": linked_user_id},
            ).mappings().first()
        assert after_user is not None
        assert int(after_user["unit_id"]) == to_unit_id
        assert int(after_user["role_id"]) == role_id

        after_visible = _employee_ids_visible_to(client, linked_user_id, q=search_q)
        assert str(transfer_employee_id) in after_visible
        assert str(peer_new_id) in after_visible
        assert str(peer_old_id) not in after_visible
    finally:
        if login:
            _cleanup_users_by_logins([login])
        if linked_user_id is not None:
            revoke_user_access_grants(linked_user_id)
        _cleanup_employees(created_employee_ids)
        _cleanup_positions(created_position_ids)
        _cleanup_units(created_unit_ids)
