# tests/personnel_lk/test_personnel_lk_api.py
"""API contract tests for GET /directory/personnel/lk."""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.personnel_applications.domain.status import APPLICATION_STATUS_COMPLETED
from tests.conftest import auth_headers, table_exists
from tests.personnel_lk.conftest import (
    insert_application,
    load_org_fixture,
    require_personnel_lk_schema,
    seed_user_id,
    set_employee_assignment,
    unique_iin,
)
from tests.personnel_applications.conftest import insert_person_with_iin, materialize_envelope
from tests.ppr.conftest import cleanup_person_graph, insert_employee, ppr_db_available


def _suffix() -> str:
    return uuid4().hex[:8]


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def lk_api_env():
    require_personnel_lk_schema()


def test_directory_lk_route_registered(client, lk_api_env) -> None:
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/directory/personnel/lk" in paths


def test_list_response_contract(client, lk_api_env, privileged_headers) -> None:
    suffix = _suffix()
    person_ids: list[int] = []
    employee_ids: list[int] = []
    try:
        with engine.begin() as conn:
            user_id = seed_user_id(conn)
            org = load_org_fixture(conn)
            iin = unique_iin("8")
            person_id = insert_person_with_iin(
                conn,
                full_name=f"API Contract {suffix}",
                iin=iin,
            )
            person_ids.append(person_id)
            materialize_envelope(conn, person_id)
            application_id = insert_application(
                conn,
                person_id=person_id,
                registered_by_user_id=user_id,
                status="registered",
                intended_org_unit_id=org["org_unit_id"],
                intended_employment_rate=1.0,
            )

        resp = client.get(
            "/directory/personnel/lk",
            params={"q": suffix, "record_kind": "applicant", "status": "all"},
            headers=privileged_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body.keys()) == {"items", "total", "limit", "offset"}
        assert body["total"] >= 1
        item = next(row for row in body["items"] if row["person_id"] == person_id)
        assert item["record_kind"] == "applicant"
        assert item["person_id"] == person_id
        assert item["employee_id"] is None
        assert item["id"] is None
        assert item["active_application_id"] == application_id
        assert item["fio"] == f"API Contract {suffix}"
        assert item["iin"] == iin
        assert item["status"] == "applicant"
        assert item["application_status"] == "registered"
        assert "department" not in item
        assert "position" not in item

        hired = client.get(
            "/directory/personnel/lk",
            params={"q": suffix, "status": "all"},
            headers=privileged_headers,
        )
        assert hired.status_code == 200

        with engine.begin() as conn:
            employee_id = insert_employee(
                conn,
                full_name=f"API Contract {suffix}",
                person_id=person_id,
            )
            employee_ids.append(employee_id)
            set_employee_assignment(conn, employee_id=employee_id, org_unit_id=org["org_unit_id"])
            insert_application(
                conn,
                person_id=person_id,
                registered_by_user_id=user_id,
                status=APPLICATION_STATUS_COMPLETED,
                application_received_at=date(2026, 1, 1),
            )

        after_hire = client.get(
            "/directory/personnel/lk",
            params={"q": suffix, "status": "all"},
            headers=privileged_headers,
        )
        assert after_hire.status_code == 200
        rows = [row for row in after_hire.json()["items"] if row["person_id"] == person_id]
        assert len(rows) == 1
        assert rows[0]["record_kind"] == "employee"
        assert rows[0]["employee_id"] == employee_ids[0]
        assert rows[0]["id"] == employee_ids[0]
        assert rows[0]["active_application_id"] is None
        assert rows[0]["application_status"] is None
        assert rows[0]["status"] == "active"
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)


def test_list_requires_personnel_admin(client, lk_api_env, seed) -> None:
    if not ppr_db_available():
        pytest.skip("PostgreSQL not available")
    with engine.begin() as conn:
        if not table_exists(conn, "persons"):
            pytest.skip("persons table missing")
    resp = client.get(
        "/directory/personnel/lk",
        headers=auth_headers(seed["executor_user_id"]),
    )
    assert resp.status_code == 403
