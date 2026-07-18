# tests/test_ops026_contacts_task_contour.py
"""OPS-026 — Contacts page lists operational/task contour only."""
from __future__ import annotations

from typing import Any, Dict, List

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers
from tests.contacts_bridge_helpers import (
    cleanup_contacts_bridge,
    create_test_contact,
    create_test_person,
    link_contact_to_dept_code,
    link_person_to_dept_code,
)


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


def test_list_contacts_excludes_person_without_canonical_contact_row(client, seed, privileged_headers):
    """Person/personnel without a contacts row must not appear in directory list."""
    unique_name = "PytestOps026PersonnelOnlyNoContact"
    created_person_ids: list[int] = []

    try:
        with engine.begin() as conn:
            person_id = create_test_person(conn, full_name=unique_name)
            created_person_ids.append(person_id)
            link_person_to_dept_code(
                conn,
                person_id=person_id,
                dept_code="pytest_ops026_personnel_only",
            )

        resp = _list_contacts(client, privileged_headers, q=unique_name, limit=50)
        assert resp.status_code == 200, resp.text
        names = {str(x.get("full_name") or "") for x in resp.json().get("items", [])}
        assert unique_name not in names
    finally:
        cleanup_contacts_bridge(person_ids=created_person_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_contacts_includes_operational_bridge_contact(client, seed, privileged_headers):
    unique_name = "PytestOps026OperationalBridgeContact"
    created_contact_ids: List[int] = []
    created_person_ids: List[int] = []

    try:
        with engine.begin() as conn:
            person_id = create_test_person(conn, full_name=unique_name)
            created_person_ids.append(person_id)
            contact_id = create_test_contact(conn, full_name=unique_name, person_id=person_id)
            created_contact_ids.append(contact_id)
            link_contact_to_dept_code(
                conn,
                contact_id=contact_id,
                dept_code="pytest_ops026_bridge",
                person_id=person_id,
            )

        resp = _list_contacts(client, privileged_headers, q=unique_name, limit=50)
        assert resp.status_code == 200, resp.text
        names = {str(x.get("full_name") or "") for x in resp.json().get("items", [])}
        assert unique_name in names
    finally:
        cleanup_contacts_bridge(contact_ids=created_contact_ids, person_ids=created_person_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_contacts_includes_manual_contact_without_person_id(client, seed, privileged_headers):
    unique_name = "PytestOps026ManualTaskContact"
    created_contact_ids: List[int] = []

    try:
        with engine.begin() as conn:
            contact_id = create_test_contact(conn, full_name=unique_name, person_id=None)
            created_contact_ids.append(contact_id)

        resp = _list_contacts(client, privileged_headers, q=unique_name, limit=50)
        assert resp.status_code == 200, resp.text
        assert resp.json()["total"] >= 1
        assert unique_name in {str(x.get("full_name") or "") for x in resp.json().get("items", [])}
    finally:
        cleanup_contacts_bridge(contact_ids=created_contact_ids)
