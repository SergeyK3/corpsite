# tests/test_admin_org_units_crud.py
"""Sysadmin org_units CRUD with dependency checks and audit."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.security.directory_scope import SYSTEM_ADMIN_ROLE_ID
from tests.conftest import (
    auth_headers,
    create_unit,
    create_user,
    get_columns,
    insert_returning_id,
    safe_delete,
    table_exists,
)

_ORG_UNIT_EVENT_TYPES = (
    "ORG_UNIT_CREATED",
    "ORG_UNIT_UPDATED",
    "ORG_UNIT_ACTIVATED",
    "ORG_UNIT_DEACTIVATED",
    "ORG_UNIT_DELETED",
    "ORG_UNIT_DELETE_REJECTED",
)

_baseline_org_unit_audit_ids: set[int] = set()


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
    values: dict = {"role_id": SYSTEM_ADMIN_ROLE_ID, "name": "pytest_system_admin"}
    if "code" in cols:
        values["code"] = "SYSTEM_ADMIN"
    if "created_at" in cols:
        from tests.conftest import utcnow

        values["created_at"] = utcnow()
    insert_returning_id(conn, table="roles", id_col="role_id", values=values)


def _snapshot_org_unit_audit_ids() -> set[int]:
    with engine.connect() as conn:
        if not table_exists(conn, "security_audit_log"):
            return set()
        rows = conn.execute(
            text(
                """
                SELECT audit_id
                FROM public.security_audit_log
                WHERE event_type LIKE 'ORG_UNIT_%'
                """
            )
        ).scalars().all()
    return {int(row) for row in rows}


def _org_unit_audit_row_count() -> int:
    return len(_snapshot_org_unit_audit_ids())


def _delete_org_unit_audit_for_units(conn, unit_ids: list[int]) -> None:
    if not unit_ids or not table_exists(conn, "security_audit_log"):
        return
    baseline = list(_baseline_org_unit_audit_ids) or [-1]
    for unit_id in unit_ids:
        conn.execute(
            text(
                """
                DELETE FROM public.security_audit_log
                WHERE audit_id <> ALL(:baseline)
                  AND event_type = ANY(:types)
                  AND (
                    (metadata->>'org_unit_id')::bigint = :uid
                    OR (metadata->'before'->>'unit_id')::bigint = :uid
                    OR (metadata->'after'->>'unit_id')::bigint = :uid
                    OR (metadata->'before'->>'id')::bigint = :uid
                    OR (metadata->'after'->>'id')::bigint = :uid
                  )
                """
            ),
            {"baseline": baseline, "types": list(_ORG_UNIT_EVENT_TYPES), "uid": int(unit_id)},
        )


def _purge_new_org_unit_audit_rows(conn) -> None:
    if not table_exists(conn, "security_audit_log"):
        return
    baseline = list(_baseline_org_unit_audit_ids) or [-1]
    conn.execute(
        text(
            """
            DELETE FROM public.security_audit_log
            WHERE event_type LIKE 'ORG_UNIT_%'
              AND audit_id <> ALL(:baseline)
            """
        ),
        {"baseline": baseline},
    )


def _cleanup_unit_artifacts(*unit_ids: int | None) -> None:
    ids = [int(unit_id) for unit_id in unit_ids if unit_id is not None]
    if not ids:
        return
    with engine.begin() as conn:
        _delete_org_unit_audit_for_units(conn, ids)
        for unit_id in ids:
            safe_delete(conn, "org_units", "unit_id = :uid", {"uid": unit_id})


def _cleanup_unit(unit_id: int) -> None:
    _cleanup_unit_artifacts(unit_id)


@pytest.fixture(scope="module", autouse=True)
def _org_unit_audit_isolation_guard():
    global _baseline_org_unit_audit_ids
    _baseline_org_unit_audit_ids = _snapshot_org_unit_audit_ids()
    yield
    with engine.begin() as conn:
        _purge_new_org_unit_audit_rows(conn)
    after_ids = _snapshot_org_unit_audit_ids()
    assert after_ids == _baseline_org_unit_audit_ids, (
        "ORG_UNIT_* audit rows leaked from tests/test_admin_org_units_crud.py: "
        f"baseline={len(_baseline_org_unit_audit_ids)}, after={len(after_ids)}"
    )


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
            full_name=f"Pytest OrgUnits Admin {suffix}",
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


def _create_child_unit(conn, *, name: str, parent_unit_id: int, group_id: int | None = None) -> int:
    cols = get_columns(conn, "org_units")
    values: dict = {"name": name, "parent_unit_id": int(parent_unit_id), "is_active": True}
    if "code" in cols:
        values["code"] = name
    if "group_id" in cols:
        values["group_id"] = group_id if group_id is not None else _ensure_org_group(conn)
    return insert_returning_id(conn, table="org_units", id_col="unit_id", values=values)


def _ensure_org_group(conn) -> int:
    if not table_exists(conn, "org_unit_groups"):
        return 1
    row = conn.execute(
        text("SELECT group_id FROM public.org_unit_groups ORDER BY group_id LIMIT 1")
    ).scalar_one_or_none()
    if row is not None:
        return int(row)
    cols = get_columns(conn, "org_unit_groups")
    values: dict = {"name": f"pytest_group_{uuid4().hex[:6]}"}
    if "is_active" in cols:
        values["is_active"] = True
    return insert_returning_id(conn, table="org_unit_groups", id_col="group_id", values=values)


@pytest.fixture
def org_group_id(seed):
    with engine.begin() as conn:
        return _ensure_org_group(conn)


def _audit_count(event_type: str, *, org_unit_id: int) -> int:
    with engine.begin() as conn:
        if not table_exists(conn, "security_audit_log"):
            return -1
        row = conn.execute(
            text(
                """
                SELECT COUNT(*)::int
                FROM public.security_audit_log
                WHERE event_type = :event_type
                  AND (metadata->>'org_unit_id')::bigint = :uid
                """
            ),
            {"event_type": event_type, "uid": int(org_unit_id)},
        ).scalar_one()
    return int(row or 0)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_non_admin_denied(client: TestClient, observer_headers):
    resp = client.get("/admin/org-units", headers=observer_headers)
    assert resp.status_code == 403


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_admin_can_list(client: TestClient, sysadmin_headers):
    resp = client.get("/admin/org-units", headers=sysadmin_headers, params={"limit": 10})
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_create_valid_org_unit(client: TestClient, sysadmin_headers, seed, org_group_id):
    suffix = uuid4().hex[:8]
    name = f"pytest_admin_ou_{suffix}"
    resp = client.post(
        "/admin/org-units",
        headers=sysadmin_headers,
        json={
            "name": name,
            "parent_unit_id": int(seed["unit_id"]),
            "group_id": org_group_id,
            "code": f"pytest_{suffix}",
        },
    )
    assert resp.status_code == 200, resp.text
    item = resp.json()["item"]
    unit_id = int(item["unit_id"])
    try:
        assert item["name"] == name
        assert item["parent_unit_id"] == int(seed["unit_id"])
        audit_n = _audit_count("ORG_UNIT_CREATED", org_unit_id=unit_id)
        if audit_n >= 0:
            assert audit_n >= 1
    finally:
        _cleanup_unit(unit_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_cannot_create_cycle(client: TestClient, sysadmin_headers, seed):
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        parent_id = _create_child_unit(conn, name=f"pytest_parent_{suffix}", parent_unit_id=int(seed["unit_id"]))
        child_id = _create_child_unit(conn, name=f"pytest_child_{suffix}", parent_unit_id=parent_id)
    try:
        resp = client.patch(
            f"/admin/org-units/{parent_id}",
            headers=sysadmin_headers,
            json={"parent_unit_id": child_id},
        )
        assert resp.status_code == 400
        assert "cycle" in resp.text.lower()
    finally:
        _cleanup_unit(child_id)
        _cleanup_unit(parent_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_cannot_set_self_as_parent(client: TestClient, sysadmin_headers, seed):
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        unit_id = _create_child_unit(conn, name=f"pytest_self_{suffix}", parent_unit_id=int(seed["unit_id"]))
    try:
        resp = client.patch(
            f"/admin/org-units/{unit_id}",
            headers=sysadmin_headers,
            json={"parent_unit_id": unit_id},
        )
        assert resp.status_code == 400
    finally:
        _cleanup_unit(unit_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_update_name_group_parent(client: TestClient, sysadmin_headers, seed, org_group_id):
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        unit_id = _create_child_unit(conn, name=f"pytest_upd_{suffix}", parent_unit_id=int(seed["unit_id"]))
        new_parent = _create_child_unit(conn, name=f"pytest_upd_parent_{suffix}", parent_unit_id=int(seed["unit_id"]))
    try:
        resp = client.patch(
            f"/admin/org-units/{unit_id}",
            headers=sysadmin_headers,
            json={
                "name": f"pytest_upd_renamed_{suffix}",
                "code": f"renamed_{suffix}",
                "parent_unit_id": new_parent,
                "group_id": org_group_id,
            },
        )
        assert resp.status_code == 200, resp.text
        item = resp.json()["item"]
        assert item["name"] == f"pytest_upd_renamed_{suffix}"
        assert item["parent_unit_id"] == new_parent
        audit_n = _audit_count("ORG_UNIT_UPDATED", org_unit_id=unit_id)
        if audit_n >= 0:
            assert audit_n >= 1
    finally:
        _cleanup_unit(unit_id)
        _cleanup_unit(new_parent)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_delete_empty_test_unit(client: TestClient, sysadmin_headers, seed):
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        unit_id = _create_child_unit(conn, name=f"pytest_del_ok_{suffix}", parent_unit_id=int(seed["unit_id"]))
    try:
        resp = client.delete(f"/admin/org-units/{unit_id}", headers=sysadmin_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json().get("ok") is True
        audit_n = _audit_count("ORG_UNIT_DELETED", org_unit_id=unit_id)
        if audit_n >= 0:
            assert audit_n >= 1
    finally:
        _cleanup_unit_artifacts(unit_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_delete_with_employee_forbidden(client: TestClient, sysadmin_headers, seed):
    suffix = uuid4().hex[:8]
    employee_id: int | None = None
    with engine.begin() as conn:
        unit_id = _create_child_unit(conn, name=f"pytest_del_emp_{suffix}", parent_unit_id=int(seed["unit_id"]))
        ecols = get_columns(conn, "employees")
        values: dict = {"full_name": f"Pytest Emp {suffix}"}
        if "org_unit_id" in ecols:
            values["org_unit_id"] = unit_id
        if "is_active" in ecols:
            values["is_active"] = True
        employee_id = insert_returning_id(conn, table="employees", id_col="employee_id", values=values)
    try:
        resp = client.delete(f"/admin/org-units/{unit_id}", headers=sysadmin_headers)
        assert resp.status_code == 409, resp.text
        detail = resp.json()["detail"]
        assert detail["error_code"] == "ORG_UNIT_HAS_DEPENDENCIES"
        assert detail["dependencies"].get("employees", 0) >= 1
    finally:
        with engine.begin() as conn:
            if employee_id is not None:
                conn.execute(text("DELETE FROM public.employees WHERE employee_id = :eid"), {"eid": employee_id})
        _cleanup_unit(unit_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_delete_with_child_forbidden(client: TestClient, sysadmin_headers, seed):
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        parent_id = _create_child_unit(conn, name=f"pytest_del_parent_{suffix}", parent_unit_id=int(seed["unit_id"]))
        child_id = _create_child_unit(conn, name=f"pytest_del_child_{suffix}", parent_unit_id=parent_id)
    try:
        resp = client.delete(f"/admin/org-units/{parent_id}", headers=sysadmin_headers)
        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert detail["dependencies"].get("child_org_units", 0) >= 1
    finally:
        _cleanup_unit(child_id)
        _cleanup_unit(parent_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_delete_with_visibility_forbidden(client: TestClient, sysadmin_headers, seed):
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_visibility_assignments"):
            pytest.skip("personnel_visibility_assignments missing")
    suffix = uuid4().hex[:8]
    assignment_id: int | None = None
    with engine.begin() as conn:
        unit_id = _create_child_unit(conn, name=f"pytest_del_vis_{suffix}", parent_unit_id=int(seed["unit_id"]))
        assignment_id = insert_returning_id(
            conn,
            table="personnel_visibility_assignments",
            id_col="assignment_id",
            values={
                "target_type": "DEPARTMENT",
                "target_department_id": unit_id,
                "scope_type": "ORGANIZATION",
                "can_view_personnel": True,
                "can_view_tasks": False,
                "is_active": True,
                "created_by_user_id": int(seed["initiator_user_id"]),
            },
        )
    try:
        resp = client.delete(f"/admin/org-units/{unit_id}", headers=sysadmin_headers)
        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert detail["dependencies"].get("personnel_visibility_assignments", 0) >= 1
    finally:
        with engine.begin() as conn:
            if assignment_id is not None:
                conn.execute(
                    text("DELETE FROM public.personnel_visibility_assignments WHERE assignment_id = :id"),
                    {"id": assignment_id},
                )
        _cleanup_unit(unit_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_delete_with_task_forbidden(client: TestClient, sysadmin_headers, seed):
    suffix = uuid4().hex[:8]
    task_id: int | None = None
    id_col = "task_id"
    with engine.begin() as conn:
        if not table_exists(conn, "regular_tasks"):
            pytest.skip("regular_tasks missing")
        unit_id = _create_child_unit(conn, name=f"pytest_del_task_{suffix}", parent_unit_id=int(seed["unit_id"]))
        tcols = get_columns(conn, "regular_tasks")
        values: dict = {"title": f"pytest task {suffix}"}
        if "owner_unit_id" in tcols:
            values["owner_unit_id"] = unit_id
        if "is_active" in tcols:
            values["is_active"] = True
        id_col = "task_id"
        if "task_id" not in tcols:
            if "regular_task_id" in tcols:
                id_col = "regular_task_id"
            elif "id" in tcols:
                id_col = "id"
            else:
                pytest.skip("regular_tasks id column not found")
        task_id = insert_returning_id(conn, table="regular_tasks", id_col=id_col, values=values)
    try:
        resp = client.delete(f"/admin/org-units/{unit_id}", headers=sysadmin_headers)
        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert detail["dependencies"].get("regular_tasks", 0) >= 1
    finally:
        with engine.begin() as conn:
            if task_id is not None:
                conn.execute(
                    text(f"DELETE FROM public.regular_tasks WHERE {id_col} = :tid"),
                    {"tid": task_id},
                )
        _cleanup_unit(unit_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_deactivate_used_unit(client: TestClient, sysadmin_headers, seed):
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        unit_id = _create_child_unit(conn, name=f"pytest_deact_{suffix}", parent_unit_id=int(seed["unit_id"]))
    try:
        resp = client.post(f"/admin/org-units/{unit_id}/deactivate", headers=sysadmin_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["item"]["is_active"] is False
        audit_n = _audit_count("ORG_UNIT_DEACTIVATED", org_unit_id=unit_id)
        if audit_n >= 0:
            assert audit_n >= 1
    finally:
        _cleanup_unit(unit_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_inactive_hidden_from_active_directory_list(client: TestClient, sysadmin_headers, seed):
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        unit_id = _create_child_unit(conn, name=f"pytest_inactive_{suffix}", parent_unit_id=int(seed["unit_id"]))
    try:
        deact = client.post(f"/admin/org-units/{unit_id}/deactivate", headers=sysadmin_headers)
        assert deact.status_code == 200

        # Directory list for active units should not include deactivated unit.
        resp = client.get(
            "/directory/org-units",
            headers=sysadmin_headers,
            params={"status": "active", "include_inactive": "false"},
        )
        assert resp.status_code == 200
        ids = {int(x.get("unit_id") or x.get("id")) for x in resp.json().get("items", [])}
        assert unit_id not in ids

        admin_resp = client.get(
            "/admin/org-units",
            headers=sysadmin_headers,
            params={"status": "inactive", "q": suffix},
        )
        assert admin_resp.status_code == 200
        admin_ids = {int(x["unit_id"]) for x in admin_resp.json().get("items", [])}
        assert unit_id in admin_ids
    finally:
        _cleanup_unit(unit_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_crud_scenario_does_not_leak_org_unit_audit_rows(
    client: TestClient, sysadmin_headers, seed, org_group_id
):
    before_ids = _snapshot_org_unit_audit_ids()
    suffix = uuid4().hex[:8]
    unit_id: int | None = None
    try:
        resp = client.post(
            "/admin/org-units",
            headers=sysadmin_headers,
            json={
                "name": f"pytest_iso_{suffix}",
                "parent_unit_id": int(seed["unit_id"]),
                "group_id": org_group_id,
                "code": f"pytest_iso_{suffix}",
            },
        )
        assert resp.status_code == 200, resp.text
        unit_id = int(resp.json()["item"]["unit_id"])
        delete_resp = client.delete(f"/admin/org-units/{unit_id}", headers=sysadmin_headers)
        assert delete_resp.status_code == 200, delete_resp.text
    finally:
        if unit_id is not None:
            _cleanup_unit_artifacts(unit_id)
    assert _snapshot_org_unit_audit_ids() == before_ids


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_bulk_delete_per_item_results(client: TestClient, sysadmin_headers, seed):
    suffix = uuid4().hex[:8]
    deletable_id: int | None = None
    blocked_id: int | None = None
    child_id: int | None = None
    with engine.begin() as conn:
        deletable_id = _create_child_unit(
            conn, name=f"pytest_bulk_ok_{suffix}", parent_unit_id=int(seed["unit_id"])
        )
        blocked_id = _create_child_unit(
            conn, name=f"pytest_bulk_block_{suffix}", parent_unit_id=int(seed["unit_id"])
        )
        child_id = _create_child_unit(conn, name=f"pytest_bulk_child_{suffix}", parent_unit_id=blocked_id)
    try:
        resp = client.post(
            "/admin/org-units/bulk-delete",
            headers=sysadmin_headers,
            json={"unit_ids": [deletable_id, blocked_id, 999999999]},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["requested"] == 3
        assert body["deleted"] == 1
        assert body["failed"] == 2
        by_id = {int(r["unit_id"]): r for r in body["results"]}
        assert by_id[deletable_id]["ok"] is True
        assert by_id[blocked_id]["ok"] is False
        assert by_id[blocked_id]["error_code"] == "ORG_UNIT_HAS_DEPENDENCIES"
        assert by_id[999999999]["ok"] is False
    finally:
        if child_id is not None:
            _cleanup_unit_artifacts(child_id)
        if blocked_id is not None:
            _cleanup_unit_artifacts(blocked_id)
        if deletable_id is not None:
            _cleanup_unit_artifacts(deletable_id)
