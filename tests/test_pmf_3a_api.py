# tests/test_pmf_3a_api.py
"""API tests for PMF-3A personnel migration draft layer."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_migration import (
    DOMAIN_CODE_EDUCATION,
    EDUCATION_KIND_BASIC,
    ITEM_STATUS_DRAFT,
    RUN_STATUS_DRAFT,
)
from app.services.education_migration_plugin import RECORD_KIND_EDUCATION
from tests.conftest import auth_headers, get_columns, insert_returning_id, table_exists
from tests.test_pmf_1_schema import PMF_TABLES, _require_schema

pytestmark = pytest.mark.usefixtures("_require_pmf_schema")


@pytest.fixture(scope="module", autouse=True)
def _require_pmf_schema():
    _require_schema()


@pytest.fixture(scope="module", autouse=True)
def _enable_education_domain():
    _require_schema()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE public.personnel_migration_domains
                SET is_enabled = TRUE
                WHERE domain_code = :domain_code
                """
            ),
            {"domain_code": DOMAIN_CODE_EDUCATION},
        )
    yield
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE public.personnel_migration_domains
                SET is_enabled = FALSE
                WHERE domain_code = :domain_code
                """
            ),
            {"domain_code": DOMAIN_CODE_EDUCATION},
        )


@pytest.fixture
def hr_admin_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def pmf_api_employee():
    _require_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = _insert_person(conn, full_name=f"PMF3A Person {suffix}")
        employee_id = _insert_employee(
            conn,
            full_name=f"PMF3A Employee {suffix}",
            person_id=person_id,
        )
    yield {"person_id": person_id, "employee_id": employee_id}
    _cleanup_person_employee(person_id=person_id, employee_id=employee_id)


@pytest.fixture
def pmf_api_employee_without_person():
    _require_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        employee_id = _insert_employee(conn, full_name=f"PMF3A Orphan {suffix}")
    yield {"employee_id": employee_id}
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.employees WHERE employee_id = :employee_id"),
            {"employee_id": employee_id},
        )


def _insert_person(conn, *, full_name: str) -> int:
    suffix = uuid4().hex[:12]
    match_key = f"pmf3a-test:{suffix}"
    cols = get_columns(conn, "persons")
    values: dict[str, Any] = {"full_name": full_name}
    if "match_key" in cols:
        values["match_key"] = match_key
    if "source" in cols:
        values["source"] = "manual"
    if "person_status" in cols:
        values["person_status"] = "active"
    return insert_returning_id(
        conn,
        table="persons",
        id_col="person_id",
        values=values,
    )


def _insert_employee(
    conn,
    *,
    full_name: str,
    person_id: int | None = None,
) -> int:
    values: dict[str, Any] = {"full_name": full_name, "is_active": True}
    cols = get_columns(conn, "employees")
    if "employment_rate" in cols:
        values["employment_rate"] = 1.00
    if person_id is not None and "person_id" in cols:
        values["person_id"] = person_id
    return insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values=values,
    )


def _cleanup_person_employee(*, person_id: int, employee_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                DELETE FROM public.personnel_record_events
                WHERE person_id = :person_id
                """
            ),
            {"person_id": person_id},
        )
        conn.execute(
            text(
                """
                DELETE FROM public.personnel_migration_items
                WHERE run_id IN (
                    SELECT run_id FROM public.personnel_migration_runs
                    WHERE person_id = :person_id
                )
                """
            ),
            {"person_id": person_id},
        )
        conn.execute(
            text(
                "DELETE FROM public.personnel_migration_runs WHERE person_id = :person_id"
            ),
            {"person_id": person_id},
        )
        conn.execute(
            text("DELETE FROM public.person_education WHERE person_id = :person_id"),
            {"person_id": person_id},
        )
        conn.execute(
            text("DELETE FROM public.person_training WHERE person_id = :person_id"),
            {"person_id": person_id},
        )
        conn.execute(
            text("DELETE FROM public.employees WHERE employee_id = :employee_id"),
            {"employee_id": employee_id},
        )
        conn.execute(
            text("DELETE FROM public.persons WHERE person_id = :person_id"),
            {"person_id": person_id},
        )


def _cleanup_run(run_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.personnel_migration_items WHERE run_id = :run_id"),
            {"run_id": run_id},
        )
        conn.execute(
            text("DELETE FROM public.personnel_migration_runs WHERE run_id = :run_id"),
            {"run_id": run_id},
        )


def test_list_domains_requires_auth(client):
    resp = client.get("/personnel-migration/domains")
    assert resp.status_code == 401


def test_list_domains_returns_education_seed(client, hr_admin_headers):
    resp = client.get("/personnel-migration/domains", headers=hr_admin_headers)
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert "items" in payload
    education = next(
        (row for row in payload["items"] if row["domain_code"] == DOMAIN_CODE_EDUCATION),
        None,
    )
    assert education is not None
    assert education["display_name"] == "Образование"
    assert education["is_enabled"] is True
    assert "person_education" in education["target_table_names"]


def test_create_draft_run_requires_person_id(client, hr_admin_headers, pmf_api_employee_without_person):
    resp = client.post(
        "/personnel-migration/runs/draft",
        json={
            "domain_code": DOMAIN_CODE_EDUCATION,
            "employee_context_id": pmf_api_employee_without_person["employee_id"],
        },
        headers=hr_admin_headers,
    )
    assert resp.status_code == 422, resp.text
    assert "person_id" in resp.json()["detail"].lower()


def test_create_draft_run_success(client, hr_admin_headers, pmf_api_employee):
    resp = client.post(
        "/personnel-migration/runs/draft",
        json={
            "domain_code": DOMAIN_CODE_EDUCATION,
            "employee_context_id": pmf_api_employee["employee_id"],
            "metadata": {"source": "pmf-3a-test"},
        },
        headers=hr_admin_headers,
    )
    assert resp.status_code == 201, resp.text
    run = resp.json()["run"]
    assert run["run_status"] == RUN_STATUS_DRAFT
    assert run["domain_code"] == DOMAIN_CODE_EDUCATION
    assert run["person_id"] == pmf_api_employee["person_id"]
    assert run["employee_context_id"] == pmf_api_employee["employee_id"]
    assert run["items"] == []
    assert run["metadata"]["source"] == "pmf-3a-test"


def test_get_run_not_found(client, hr_admin_headers):
    resp = client.get("/personnel-migration/runs/999999999", headers=hr_admin_headers)
    assert resp.status_code == 404


def test_get_run_returns_items(client, hr_admin_headers, pmf_api_employee):
    create_resp = client.post(
        "/personnel-migration/runs/draft",
        json={
            "domain_code": DOMAIN_CODE_EDUCATION,
            "employee_context_id": pmf_api_employee["employee_id"],
        },
        headers=hr_admin_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    run_id = create_resp.json()["run"]["run_id"]

    item_resp = client.post(
        f"/personnel-migration/runs/{run_id}/items",
        json={
            "source_kind": "import_row_field",
            "record_kind": RECORD_KIND_EDUCATION,
            "draft_payload": {
                "education_kind": EDUCATION_KIND_BASIC,
                "institution_name": "API University",
            },
            "source_payload": {"column": "H"},
        },
        headers=hr_admin_headers,
    )
    assert item_resp.status_code == 201, item_resp.text
    item = item_resp.json()["item"]
    assert item["item_status"] == ITEM_STATUS_DRAFT
    assert item["draft_payload"]["institution_name"] == "API University"

    get_resp = client.get(f"/personnel-migration/runs/{run_id}", headers=hr_admin_headers)
    assert get_resp.status_code == 200, get_resp.text
    run = get_resp.json()
    assert run["run_id"] == run_id
    assert len(run["items"]) == 1
    assert run["items"][0]["item_id"] == item["item_id"]


def test_add_draft_item_to_non_draft_run_conflict(client, hr_admin_headers, pmf_api_employee):
    create_resp = client.post(
        "/personnel-migration/runs/draft",
        json={
            "domain_code": DOMAIN_CODE_EDUCATION,
            "employee_context_id": pmf_api_employee["employee_id"],
        },
        headers=hr_admin_headers,
    )
    run_id = create_resp.json()["run"]["run_id"]

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE public.personnel_migration_runs
                SET run_status = :run_status
                WHERE run_id = :run_id
                """
            ),
            {"run_status": "committed", "run_id": run_id},
        )

    try:
        item_resp = client.post(
            f"/personnel-migration/runs/{run_id}/items",
            json={
                "source_kind": "manual",
                "record_kind": RECORD_KIND_EDUCATION,
                "draft_payload": {"education_kind": EDUCATION_KIND_BASIC},
            },
            headers=hr_admin_headers,
        )
        assert item_resp.status_code == 409, item_resp.text
    finally:
        _cleanup_run(run_id)


def test_api_does_not_create_person_education_records(client, hr_admin_headers, pmf_api_employee):
    create_resp = client.post(
        "/personnel-migration/runs/draft",
        json={
            "domain_code": DOMAIN_CODE_EDUCATION,
            "employee_context_id": pmf_api_employee["employee_id"],
        },
        headers=hr_admin_headers,
    )
    run_id = create_resp.json()["run"]["run_id"]

    item_resp = client.post(
        f"/personnel-migration/runs/{run_id}/items",
        json={
            "source_kind": "manual",
            "record_kind": RECORD_KIND_EDUCATION,
            "draft_payload": {"education_kind": EDUCATION_KIND_BASIC},
        },
        headers=hr_admin_headers,
    )
    assert item_resp.status_code == 201, item_resp.text

    with engine.begin() as conn:
        count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.person_education
                WHERE person_id = :person_id
                """
            ),
            {"person_id": pmf_api_employee["person_id"]},
        ).scalar_one()
    assert int(count) == 0


def test_pmf_schema_tables_available_for_api():
    _require_schema()
    with engine.begin() as conn:
        assert all(table_exists(conn, table) for table in PMF_TABLES)
