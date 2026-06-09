# tests/test_contacts_org_scope.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import (
    auth_headers,
    get_columns,
    insert_returning_id,
    safe_delete_many,
    table_exists,
)


CONTACTS_WORKING_DDL = """
CREATE TABLE IF NOT EXISTS public.contacts_working (
    contact_id BIGINT NOT NULL,
    person_id BIGINT NULL,
    dept_code TEXT NULL
)
"""


@pytest.fixture(scope="module", autouse=True)
def ensure_contacts_working_bridge():
    with engine.begin() as conn:
        conn.execute(text(CONTACTS_WORKING_DDL))
    yield


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


def _list_contacts(client, privileged_headers, **params):
    return client.get(
        "/directory/contacts",
        params=params,
        headers=privileged_headers,
    )


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _create_unit_with_group(
    conn,
    *,
    name: str,
    code: str,
    group_id: int,
    parent_unit_id: Optional[int] = None,
) -> int:
    if not table_exists(conn, "org_units"):
        pytest.skip("org_units table not available")

    cols = get_columns(conn, "org_units")
    values: Dict[str, Any] = {"name": name, "code": code}
    if "group_id" in cols:
        values["group_id"] = int(group_id)
    if parent_unit_id is not None and "parent_unit_id" in cols:
        values["parent_unit_id"] = int(parent_unit_id)
    if "is_active" in cols:
        values["is_active"] = True

    filtered = {k: v for k, v in values.items() if k in cols}
    if "code" not in filtered:
        pytest.skip("org_units.code not available")

    return insert_returning_id(conn, table="org_units", id_col="unit_id", values=filtered)


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


def _create_contact(conn, *, full_name: str) -> int:
    if not table_exists(conn, "contacts"):
        pytest.skip("contacts table not available")

    return insert_returning_id(
        conn,
        table="contacts",
        id_col="contact_id",
        values={"full_name": full_name, "is_deleted": False},
    )


def _link_contact_to_unit(conn, *, contact_id: int, dept_code: str) -> None:
    conn.execute(
        text(
            """
            INSERT INTO public.contacts_working (contact_id, person_id, dept_code)
            VALUES (:contact_id, NULL, :dept_code)
            """
        ),
        {"contact_id": int(contact_id), "dept_code": str(dept_code)},
    )


def _contact_names_from_response(body: Dict[str, Any]) -> set[str]:
    return {str(x.get("full_name") or "") for x in body.get("items", [])}


def _cleanup_contacts_working(contact_ids: List[int]) -> None:
    if not contact_ids:
        return
    with engine.begin() as conn:
        if not table_exists(conn, "contacts_working"):
            return
        conn.execute(
            text("DELETE FROM public.contacts_working WHERE contact_id = ANY(:ids)"),
            {"ids": [int(x) for x in contact_ids]},
        )


def _cleanup_contacts(contact_ids: List[int]) -> None:
    if not contact_ids:
        return
    with engine.begin() as conn:
        safe_delete_many(conn, "contacts", "contact_id", contact_ids)


def _cleanup_units(unit_ids: List[int]) -> None:
    if not unit_ids:
        return
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.org_units WHERE unit_id = ANY(:ids)"),
            {"ids": [int(x) for x in unit_ids]},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_contacts_without_org_group_id_unchanged(client, seed, privileged_headers):
    unique_name = "PytestContactOrgScopeNoGroupFilter"
    created_contact_ids: List[int] = []

    try:
        with engine.begin() as conn:
            contact_id = _create_contact(conn, full_name=unique_name)
            created_contact_ids.append(contact_id)

        resp = _list_contacts(
            client,
            privileged_headers,
            q=unique_name,
            limit=50,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] >= 1
        assert unique_name in _contact_names_from_response(body)
    finally:
        _cleanup_contacts(created_contact_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_contacts_filters_by_org_group_id(client, seed, privileged_headers):
    unique_a = "PytestContactOrgScopeGroupA"
    unique_b = "PytestContactOrgScopeGroupB"
    created_contact_ids: List[int] = []
    created_unit_ids: List[int] = []

    try:
        with engine.begin() as conn:
            group_ids = _find_distinct_group_ids(conn, limit=2)
            if len(group_ids) < 2:
                group_a = 1
                group_b = 3
            else:
                group_a, group_b = group_ids[0], group_ids[1]

            unit_a = _create_unit_with_group(
                conn,
                name="pytest_contact_org_scope_a",
                code="pytest_contact_org_scope_a",
                group_id=group_a,
            )
            unit_b = _create_unit_with_group(
                conn,
                name="pytest_contact_org_scope_b",
                code="pytest_contact_org_scope_b",
                group_id=group_b,
            )
            created_unit_ids.extend([unit_a, unit_b])

            contact_a = _create_contact(conn, full_name=unique_a)
            contact_b = _create_contact(conn, full_name=unique_b)
            created_contact_ids.extend([contact_a, contact_b])

            _link_contact_to_unit(conn, contact_id=contact_a, dept_code="pytest_contact_org_scope_a")
            _link_contact_to_unit(conn, contact_id=contact_b, dept_code="pytest_contact_org_scope_b")

        filtered_a = _list_contacts(
            client,
            privileged_headers,
            org_group_id=group_a,
            q=unique_a,
        )
        assert filtered_a.status_code == 200, filtered_a.text
        assert filtered_a.json()["total"] == 1
        assert unique_a in _contact_names_from_response(filtered_a.json())

        filtered_b = _list_contacts(
            client,
            privileged_headers,
            org_group_id=group_b,
            q=unique_b,
        )
        assert filtered_b.status_code == 200, filtered_b.text
        assert filtered_b.json()["total"] == 1
        assert unique_b in _contact_names_from_response(filtered_b.json())

        cross = _list_contacts(
            client,
            privileged_headers,
            org_group_id=group_a,
            q=unique_b,
        )
        assert cross.status_code == 200, cross.text
        assert cross.json()["total"] == 0
    finally:
        _cleanup_contacts_working(created_contact_ids)
        _cleanup_contacts(created_contact_ids)
        _cleanup_units(created_unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_contacts_filters_by_org_unit_id_subtree(client, seed, privileged_headers):
    unique_name = "PytestContactOrgScopeSubtreeChild"
    created_contact_ids: List[int] = []
    created_unit_ids: List[int] = []

    try:
        with engine.begin() as conn:
            cols = get_columns(conn, "org_units")
            if "parent_unit_id" not in cols:
                pytest.skip("org_units.parent_unit_id not available")

            group_ids = _find_distinct_group_ids(conn, limit=1)
            group_id = group_ids[0] if group_ids else 1

            parent_unit = _create_unit_with_group(
                conn,
                name="pytest_contact_org_scope_parent",
                code="pytest_contact_org_scope_parent",
                group_id=group_id,
            )
            child_unit = _create_unit_with_group(
                conn,
                name="pytest_contact_org_scope_child",
                code="pytest_contact_org_scope_child",
                group_id=group_id,
                parent_unit_id=parent_unit,
            )
            sibling_unit = _create_unit_with_group(
                conn,
                name="pytest_contact_org_scope_sibling",
                code="pytest_contact_org_scope_sibling",
                group_id=group_id,
            )
            created_unit_ids.extend([parent_unit, child_unit, sibling_unit])

            contact_id = _create_contact(conn, full_name=unique_name)
            created_contact_ids.append(contact_id)
            _link_contact_to_unit(
                conn,
                contact_id=contact_id,
                dept_code="pytest_contact_org_scope_child",
            )

        filtered_parent = _list_contacts(
            client,
            privileged_headers,
            org_unit_id=parent_unit,
            q=unique_name,
        )
        assert filtered_parent.status_code == 200, filtered_parent.text
        assert filtered_parent.json()["total"] == 1
        assert unique_name in _contact_names_from_response(filtered_parent.json())

        filtered_sibling = _list_contacts(
            client,
            privileged_headers,
            org_unit_id=sibling_unit,
            q=unique_name,
        )
        assert filtered_sibling.status_code == 200, filtered_sibling.text
        assert filtered_sibling.json()["total"] == 0
    finally:
        _cleanup_contacts_working(created_contact_ids)
        _cleanup_contacts(created_contact_ids)
        _cleanup_units(created_unit_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_contacts_org_group_id_and_org_unit_id_and(client, seed, privileged_headers):
    unique_child = "PytestContactOrgScopeAndChild"
    unique_sibling = "PytestContactOrgScopeAndSibling"
    created_contact_ids: List[int] = []
    created_unit_ids: List[int] = []

    try:
        with engine.begin() as conn:
            cols = get_columns(conn, "org_units")
            if "parent_unit_id" not in cols:
                pytest.skip("org_units.parent_unit_id not available")

            group_ids = _find_distinct_group_ids(conn, limit=1)
            group_id = group_ids[0] if group_ids else 1

            parent_unit = _create_unit_with_group(
                conn,
                name="pytest_contact_org_scope_and_parent",
                code="pytest_contact_org_scope_and_parent",
                group_id=group_id,
            )
            child_unit = _create_unit_with_group(
                conn,
                name="pytest_contact_org_scope_and_child",
                code="pytest_contact_org_scope_and_child",
                group_id=group_id,
                parent_unit_id=parent_unit,
            )
            sibling_unit = _create_unit_with_group(
                conn,
                name="pytest_contact_org_scope_and_sibling",
                code="pytest_contact_org_scope_and_sibling",
                group_id=group_id,
            )
            created_unit_ids.extend([parent_unit, child_unit, sibling_unit])

            contact_child = _create_contact(conn, full_name=unique_child)
            contact_sibling = _create_contact(conn, full_name=unique_sibling)
            created_contact_ids.extend([contact_child, contact_sibling])

            _link_contact_to_unit(
                conn,
                contact_id=contact_child,
                dept_code="pytest_contact_org_scope_and_child",
            )
            _link_contact_to_unit(
                conn,
                contact_id=contact_sibling,
                dept_code="pytest_contact_org_scope_and_sibling",
            )

            group_id = _unit_group_id(conn, parent_unit) or group_id

        combined = _list_contacts(
            client,
            privileged_headers,
            org_group_id=group_id,
            org_unit_id=parent_unit,
            q="PytestContactOrgScopeAnd",
        )
        assert combined.status_code == 200, combined.text
        combined_names = _contact_names_from_response(combined.json())
        assert unique_child in combined_names
        assert unique_sibling not in combined_names

        group_only = _list_contacts(
            client,
            privileged_headers,
            org_group_id=group_id,
            q="PytestContactOrgScopeAnd",
        )
        assert group_only.status_code == 200, group_only.text
        group_only_names = _contact_names_from_response(group_only.json())
        assert unique_child in group_only_names
        assert unique_sibling in group_only_names
    finally:
        _cleanup_contacts_working(created_contact_ids)
        _cleanup_contacts(created_contact_ids)
        _cleanup_units(created_unit_ids)
