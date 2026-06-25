# tests/test_ops026_contacts_task_contour.py
"""OPS-026 — Contacts page lists operational/task contour only."""
from __future__ import annotations

from typing import Any, Dict, List

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


def _create_contact(conn, *, full_name: str, person_id: int | None = None) -> int:
    if not table_exists(conn, "contacts"):
        pytest.skip("contacts table not available")

    values: Dict[str, Any] = {"full_name": full_name, "is_deleted": False}
    cols = get_columns(conn, "contacts")
    if person_id is not None and "person_id" in cols:
        values["person_id"] = int(person_id)

    return insert_returning_id(
        conn,
        table="contacts",
        id_col="contact_id",
        values=values,
    )


def _create_person(conn, *, full_name: str) -> int:
    if not table_exists(conn, "persons"):
        pytest.skip("persons table not available")

    cols = get_columns(conn, "persons")
    values: Dict[str, Any] = {"full_name": full_name}
    if "person_status" in cols:
        values["person_status"] = "active"
    if "match_key" in cols:
        values["match_key"] = f"pytest:{full_name}"

    return insert_returning_id(
        conn,
        table="persons",
        id_col="person_id",
        values=values,
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


def _cleanup_persons(person_ids: List[int]) -> None:
    if not person_ids:
        return
    with engine.begin() as conn:
        if not table_exists(conn, "persons"):
            return
        safe_delete_many(conn, "persons", "person_id", person_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_contacts_excludes_personnel_only_person_id(client, seed, privileged_headers):
    unique_name = "PytestOps026PersonnelOnlyContact"
    created_contact_ids: List[int] = []
    created_person_ids: List[int] = []

    try:
        with engine.begin() as conn:
            person_id = _create_person(conn, full_name=unique_name)
            created_person_ids.append(person_id)
            contact_id = _create_contact(conn, full_name=unique_name, person_id=person_id)
            created_contact_ids.append(contact_id)

        resp = _list_contacts(client, privileged_headers, q=unique_name, limit=50)
        assert resp.status_code == 200, resp.text
        names = {str(x.get("full_name") or "") for x in resp.json().get("items", [])}
        assert unique_name not in names
    finally:
        _cleanup_contacts_working(created_contact_ids)
        _cleanup_contacts(created_contact_ids)
        _cleanup_persons(created_person_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_contacts_includes_operational_bridge_contact(client, seed, privileged_headers):
    unique_name = "PytestOps026OperationalBridgeContact"
    created_contact_ids: List[int] = []
    created_person_ids: List[int] = []

    try:
        with engine.begin() as conn:
            person_id = _create_person(conn, full_name=unique_name)
            created_person_ids.append(person_id)
            contact_id = _create_contact(conn, full_name=unique_name, person_id=person_id)
            created_contact_ids.append(contact_id)
            _link_contact_to_unit(conn, contact_id=contact_id, dept_code="pytest_ops026_bridge")

        resp = _list_contacts(client, privileged_headers, q=unique_name, limit=50)
        assert resp.status_code == 200, resp.text
        names = {str(x.get("full_name") or "") for x in resp.json().get("items", [])}
        assert unique_name in names
    finally:
        _cleanup_contacts_working(created_contact_ids)
        _cleanup_contacts(created_contact_ids)
        _cleanup_persons(created_person_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_contacts_includes_manual_contact_without_person_id(client, seed, privileged_headers):
    unique_name = "PytestOps026ManualTaskContact"
    created_contact_ids: List[int] = []

    try:
        with engine.begin() as conn:
            contact_id = _create_contact(conn, full_name=unique_name, person_id=None)
            created_contact_ids.append(contact_id)

        resp = _list_contacts(client, privileged_headers, q=unique_name, limit=50)
        assert resp.status_code == 200, resp.text
        assert resp.json()["total"] >= 1
        assert unique_name in {str(x.get("full_name") or "") for x in resp.json().get("items", [])}
    finally:
        _cleanup_contacts(created_contact_ids)
