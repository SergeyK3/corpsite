# tests/test_employees_org_scope.py
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.tasks_service import SYSTEM_ADMIN_ROLE_ID
from tests.conftest import (
    auth_headers,
    get_columns,
    insert_returning_id,
    table_exists,
)


def _list_employees(client, user_id: int, **params):
    return client.get(
        "/directory/employees",
        params=params,
        headers=auth_headers(user_id),
    )


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
    return 1


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


def _find_distinct_group_ids(conn, *, limit: int = 2) -> List[int]:
    rows = (
        conn.execute(
            text(
                """
                SELECT DISTINCT group_id
                FROM public.org_units
                WHERE group_id IS NOT NULL
                  AND group_id >= 1
                ORDER BY group_id
                LIMIT :limit
                """
            ),
            {"limit": int(limit)},
        )
        .mappings()
        .all()
    )
    return [int(r["group_id"]) for r in rows if r.get("group_id") is not None]


def _unit_group_id(conn, unit_id: int) -> Optional[int]:
    row = (
        conn.execute(
            text(
                """
                SELECT group_id
                FROM public.org_units
                WHERE unit_id = :unit_id
                LIMIT 1
                """
            ),
            {"unit_id": int(unit_id)},
        )
        .mappings()
        .first()
    )
    if not row or row.get("group_id") is None:
        return None
    return int(row["group_id"])


def _insert_employee(conn, *, full_name: str, org_unit_id: int) -> str:
    if not table_exists(conn, "employees"):
        pytest.skip("employees table not available")

    cols = get_columns(conn, "employees")
    values: Dict[str, Any] = {
        "full_name": full_name,
        "org_unit_id": int(org_unit_id),
        "is_active": True,
    }
    if "employment_rate" in cols:
        values["employment_rate"] = 1.00
    if "date_from" in cols:
        values["date_from"] = date.today()

    emp_id_col = next((c for c in ("employee_id", "id") if c in cols), None)
    if emp_id_col:
        probe = conn.execute(
            text(
                """
                SELECT data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'employees'
                  AND column_name = :col
                LIMIT 1
                """
            ),
            {"col": emp_id_col},
        ).first()
        if probe and str(probe[0]).lower() in {"text", "character varying"}:
            values[emp_id_col] = f"PY{uuid4().hex[:12].upper()}"

    filtered = {k: v for k, v in values.items() if k in cols}
    col_list = ", ".join(filtered.keys())
    bind_list = ", ".join(f":{k}" for k in filtered.keys())
    returning_col = emp_id_col or "full_name"
    row = conn.execute(
        text(
            f"""
            INSERT INTO public.employees ({col_list})
            VALUES ({bind_list})
            RETURNING {returning_col}
            """
        ),
        filtered,
    ).first()
    return str(row[0])


def _cleanup_employees(full_names: List[str]) -> None:
    if not full_names:
        return
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.employees WHERE full_name = ANY(:names)"),
            {"names": full_names},
        )


def _cleanup_units(unit_ids: List[int]) -> None:
    if not unit_ids:
        return
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.org_units WHERE unit_id = ANY(:ids)"),
            {"ids": [int(x) for x in unit_ids]},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_employees_without_org_group_id_unchanged(client, seed):
    unique_name = "PytestEmpOrgScopeNoGroupFilter"
    created_names: List[str] = []
    admin_user_id: Optional[int] = None

    try:
        with engine.begin() as conn:
            admin_user_id = _admin_user_id(conn)
            _insert_employee(
                conn,
                full_name=unique_name,
                org_unit_id=int(seed["unit_id"]),
            )
            created_names.append(unique_name)

        resp = _list_employees(
            client,
            int(admin_user_id),
            status="all",
            q=unique_name,
            limit=50,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] >= 1
        fios = {str(x.get("fio") or "") for x in body["items"]}
        assert unique_name in fios
    finally:
        _cleanup_employees(created_names)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_employees_filters_by_org_group_id(client, seed):
    unique_a = "PytestEmpOrgScopeGroupA"
    unique_b = "PytestEmpOrgScopeGroupB"
    created_names: List[str] = []
    created_unit_ids: List[int] = []
    admin_user_id: Optional[int] = None

    try:
        with engine.begin() as conn:
            admin_user_id = _admin_user_id(conn)
            group_ids = _find_distinct_group_ids(conn, limit=2)
            if len(group_ids) < 2:
                group_a = 1
                group_b = 3
            else:
                group_a, group_b = group_ids[0], group_ids[1]

            unit_a = _create_unit_with_group(conn, name="pytest_emp_org_scope_a", group_id=group_a)
            unit_b = _create_unit_with_group(conn, name="pytest_emp_org_scope_b", group_id=group_b)
            created_unit_ids.extend([unit_a, unit_b])

            _insert_employee(conn, full_name=unique_a, org_unit_id=unit_a)
            _insert_employee(conn, full_name=unique_b, org_unit_id=unit_b)
            created_names.extend([unique_a, unique_b])

        filtered_a = _list_employees(
            client,
            int(admin_user_id),
            status="all",
            org_group_id=group_a,
            q=unique_a,
        )
        assert filtered_a.status_code == 200, filtered_a.text
        assert filtered_a.json()["total"] == 1
        assert filtered_a.json()["items"][0]["fio"] == unique_a

        filtered_b = _list_employees(
            client,
            int(admin_user_id),
            status="all",
            org_group_id=group_b,
            q=unique_b,
        )
        assert filtered_b.status_code == 200, filtered_b.text
        assert filtered_b.json()["total"] == 1
        assert filtered_b.json()["items"][0]["fio"] == unique_b

        cross = _list_employees(
            client,
            int(admin_user_id),
            status="all",
            org_group_id=group_a,
            q=unique_b,
        )
        assert cross.status_code == 200, cross.text
        assert cross.json()["total"] == 0
    finally:
        _cleanup_employees(created_names)
        _cleanup_units(created_unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_employees_filters_by_org_unit_id_exact_match_without_include_children(client, seed):
    """Legacy: org_unit_id alone (include_children=false) matches the unit exactly, not subtree."""
    unique_parent = "PytestEmpOrgScopeExactParent"
    unique_child = "PytestEmpOrgScopeExactChild"
    created_names: List[str] = []
    created_unit_ids: List[int] = []
    admin_user_id: Optional[int] = None

    try:
        with engine.begin() as conn:
            cols = get_columns(conn, "org_units")
            if "parent_unit_id" not in cols:
                pytest.skip("org_units.parent_unit_id not available")

            admin_user_id = _admin_user_id(conn)
            group_ids = _find_distinct_group_ids(conn, limit=1)
            group_id = group_ids[0] if group_ids else 1

            parent_unit = _create_unit_with_group(
                conn,
                name="pytest_emp_org_scope_exact_parent",
                group_id=group_id,
            )
            child_unit = _create_unit_with_group(
                conn,
                name="pytest_emp_org_scope_exact_child",
                group_id=group_id,
                parent_unit_id=parent_unit,
            )
            created_unit_ids.extend([parent_unit, child_unit])

            _insert_employee(conn, full_name=unique_parent, org_unit_id=parent_unit)
            _insert_employee(conn, full_name=unique_child, org_unit_id=child_unit)
            created_names.extend([unique_parent, unique_child])

        # Parent unit only — child employee must not appear.
        parent_only = _list_employees(
            client,
            int(admin_user_id),
            status="all",
            org_unit_id=parent_unit,
            q="PytestEmpOrgScopeExact",
        )
        assert parent_only.status_code == 200, parent_only.text
        parent_fios = {str(x.get("fio") or "") for x in parent_only.json()["items"]}
        assert unique_parent in parent_fios
        assert unique_child not in parent_fios
    finally:
        _cleanup_employees(created_names)
        _cleanup_units(created_unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_employees_filters_by_org_unit_id_subtree_via_include_children(client, seed):
    """Subtree via include_children=true (frontend sidebar path); not legacy exact match."""
    unique_name = "PytestEmpOrgScopeSubtreeChild"
    created_names: List[str] = []
    created_unit_ids: List[int] = []
    admin_user_id: Optional[int] = None

    try:
        with engine.begin() as conn:
            cols = get_columns(conn, "org_units")
            if "parent_unit_id" not in cols:
                pytest.skip("org_units.parent_unit_id not available")

            admin_user_id = _admin_user_id(conn)
            group_ids = _find_distinct_group_ids(conn, limit=1)
            group_id = group_ids[0] if group_ids else 1

            parent_unit = _create_unit_with_group(
                conn,
                name="pytest_emp_org_scope_parent",
                group_id=group_id,
            )
            child_unit = _create_unit_with_group(
                conn,
                name="pytest_emp_org_scope_child",
                group_id=group_id,
                parent_unit_id=parent_unit,
            )
            created_unit_ids.extend([parent_unit, child_unit])

            _insert_employee(conn, full_name=unique_name, org_unit_id=child_unit)
            created_names.append(unique_name)

        filtered = _list_employees(
            client,
            int(admin_user_id),
            status="all",
            org_unit_id=parent_unit,
            include_children=True,
            q=unique_name,
        )
        assert filtered.status_code == 200, filtered.text
        body = filtered.json()
        assert body["total"] == 1
        assert body["items"][0]["fio"] == unique_name
    finally:
        _cleanup_employees(created_names)
        _cleanup_units(created_unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_employees_org_group_and_unit_combined_with_and(client, seed):
    unique_child = "PytestEmpOrgScopeAndChild"
    unique_sibling = "PytestEmpOrgScopeAndSibling"
    created_names: List[str] = []
    created_unit_ids: List[int] = []
    admin_user_id: Optional[int] = None

    try:
        with engine.begin() as conn:
            cols = get_columns(conn, "org_units")
            if "parent_unit_id" not in cols:
                pytest.skip("org_units.parent_unit_id not available")

            admin_user_id = _admin_user_id(conn)
            group_ids = _find_distinct_group_ids(conn, limit=1)
            group_id = group_ids[0] if group_ids else 1

            parent_unit = _create_unit_with_group(
                conn,
                name="pytest_emp_org_scope_and_parent",
                group_id=group_id,
            )
            child_unit = _create_unit_with_group(
                conn,
                name="pytest_emp_org_scope_and_child",
                group_id=group_id,
                parent_unit_id=parent_unit,
            )
            sibling_unit = _create_unit_with_group(
                conn,
                name="pytest_emp_org_scope_and_sibling",
                group_id=group_id,
            )
            created_unit_ids.extend([parent_unit, child_unit, sibling_unit])

            _insert_employee(conn, full_name=unique_child, org_unit_id=child_unit)
            _insert_employee(conn, full_name=unique_sibling, org_unit_id=sibling_unit)
            created_names.extend([unique_child, unique_sibling])

            group_id = _unit_group_id(conn, parent_unit) or group_id

        combined = _list_employees(
            client,
            int(admin_user_id),
            status="all",
            org_group_id=group_id,
            org_unit_id=parent_unit,
            include_children=True,
            q="PytestEmpOrgScopeAnd",
        )
        assert combined.status_code == 200, combined.text
        combined_fios = {str(x.get("fio") or "") for x in combined.json()["items"]}
        assert unique_child in combined_fios
        assert unique_sibling not in combined_fios

        group_only = _list_employees(
            client,
            int(admin_user_id),
            status="all",
            org_group_id=group_id,
            q="PytestEmpOrgScopeAnd",
        )
        assert group_only.status_code == 200, group_only.text
        group_fios = {str(x.get("fio") or "") for x in group_only.json()["items"]}
        assert unique_child in group_fios
        assert unique_sibling in group_fios
    finally:
        _cleanup_employees(created_names)
        _cleanup_units(created_unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_employees_rbac_not_bypassed_by_org_group_id(client, seed, monkeypatch):
    unique_name = "PytestEmpOrgScopeRbacBypass"
    created_names: List[str] = []
    created_unit_ids: List[int] = []
    admin_user_id: Optional[int] = None

    monkeypatch.setenv("DIRECTORY_RBAC_MODE", "dept")

    try:
        with engine.begin() as conn:
            admin_user_id = _admin_user_id(conn)
            group_ids = _find_distinct_group_ids(conn, limit=1)
            group_id = group_ids[0] if group_ids else 3

            scoped_unit = int(seed["unit_id"])
            outsider_unit = _create_unit_with_group(
                conn,
                name="pytest_emp_org_scope_rbac_outsider",
                group_id=group_id,
            )
            created_unit_ids.append(outsider_unit)

            _insert_employee(conn, full_name=unique_name, org_unit_id=outsider_unit)
            created_names.append(unique_name)

        scoped_resp = _list_employees(
            client,
            int(seed["executor_user_id"]),
            status="all",
            org_group_id=group_id,
            q=unique_name,
        )
        assert scoped_resp.status_code == 200, scoped_resp.text
        assert scoped_resp.json()["total"] == 0

        admin_resp = _list_employees(
            client,
            int(admin_user_id),
            status="all",
            org_group_id=group_id,
            q=unique_name,
        )
        assert admin_resp.status_code == 200, admin_resp.text
        assert admin_resp.json()["total"] == 1
        assert admin_resp.json()["items"][0]["fio"] == unique_name

        _ = scoped_unit
    finally:
        _cleanup_employees(created_names)
        _cleanup_units(created_unit_ids)
