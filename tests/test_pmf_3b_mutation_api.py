# tests/test_pmf_3b_mutation_api.py
"""API tests for PMF-3B personnel migration mutation layer."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_migration import (
    DOMAIN_CODE_EDUCATION,
    EDUCATION_KIND_BASIC,
    EVENT_TYPE_EDUCATION_MIGRATED,
    EVENT_TYPE_EDUCATION_SUPERSEDED,
    EVENT_TYPE_EDUCATION_VOIDED,
    LIFECYCLE_STATUS_ACTIVE,
    LIFECYCLE_STATUS_SUPERSEDED,
    LIFECYCLE_STATUS_VOIDED,
    RUN_STATUS_COMMITTED,
    RUN_STATUS_DRAFT,
    RUN_STATUS_VOIDED,
)
from app.services.education_migration_plugin import RECORD_KIND_EDUCATION
from tests.conftest import auth_headers, get_columns, insert_returning_id
from tests.test_pmf_1_schema import _require_schema

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
def pmf_employee():
    _require_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = _insert_person(conn, full_name=f"PMF3B Person {suffix}")
        employee_id = _insert_employee(
            conn,
            full_name=f"PMF3B Employee {suffix}",
            person_id=person_id,
        )
    yield {"person_id": person_id, "employee_id": employee_id}
    _cleanup_person_employee(person_id=person_id, employee_id=employee_id)


def _insert_person(conn, *, full_name: str) -> int:
    suffix = uuid4().hex[:12]
    match_key = f"pmf3b-test:{suffix}"
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
            text("DELETE FROM public.personnel_record_events WHERE person_id = :person_id"),
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
            text("DELETE FROM public.personnel_migration_runs WHERE person_id = :person_id"),
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


def _create_draft_run_with_item(client, headers, employee_id: int) -> int:
    run_resp = client.post(
        "/personnel-migration/runs/draft",
        json={
            "domain_code": DOMAIN_CODE_EDUCATION,
            "employee_context_id": employee_id,
        },
        headers=headers,
    )
    assert run_resp.status_code == 201, run_resp.text
    run_id = run_resp.json()["run"]["run_id"]

    item_resp = client.post(
        f"/personnel-migration/runs/{run_id}/items",
        json={
            "source_kind": "manual",
            "record_kind": RECORD_KIND_EDUCATION,
            "draft_payload": {
                "education_kind": EDUCATION_KIND_BASIC,
                "institution_name": "PMF3B University",
            },
        },
        headers=headers,
    )
    assert item_resp.status_code == 201, item_resp.text
    return int(run_id)


def test_commit_run_creates_person_education_and_events(client, hr_admin_headers, pmf_employee):
    run_id = _create_draft_run_with_item(
        client, hr_admin_headers, pmf_employee["employee_id"]
    )

    commit_resp = client.post(
        f"/personnel-migration/runs/{run_id}/commit",
        json={"confirm": True},
        headers=hr_admin_headers,
    )
    assert commit_resp.status_code == 200, commit_resp.text
    body = commit_resp.json()
    assert body["run"]["run_status"] == RUN_STATUS_COMMITTED
    assert len(body["committed_items"]) == 1
    assert len(body["event_ids"]) == 1

    education_id = body["committed_items"][0]["target_record_id"]
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT lifecycle_status, institution_name
                FROM public.person_education
                WHERE education_id = :education_id
                """
            ),
            {"education_id": education_id},
        ).mappings().one()
        event_type = conn.execute(
            text(
                """
                SELECT event_type
                FROM public.personnel_record_events
                WHERE event_id = :event_id
                """
            ),
            {"event_id": body["event_ids"][0]},
        ).scalar_one()

    assert row["lifecycle_status"] == LIFECYCLE_STATUS_ACTIVE
    assert row["institution_name"] == "PMF3B University"
    assert event_type == EVENT_TYPE_EDUCATION_MIGRATED


def test_commit_validation_returns_422_with_item_details(client, hr_admin_headers, pmf_employee):
    run_resp = client.post(
        "/personnel-migration/runs/draft",
        json={
            "domain_code": DOMAIN_CODE_EDUCATION,
            "employee_context_id": pmf_employee["employee_id"],
        },
        headers=hr_admin_headers,
    )
    run_id = run_resp.json()["run"]["run_id"]

    client.post(
        f"/personnel-migration/runs/{run_id}/items",
        json={
            "source_kind": "manual",
            "record_kind": RECORD_KIND_EDUCATION,
            "draft_payload": {"institution_name": "Missing kind"},
        },
        headers=hr_admin_headers,
    )

    commit_resp = client.post(
        f"/personnel-migration/runs/{run_id}/commit",
        json={"confirm": True},
        headers=hr_admin_headers,
    )
    assert commit_resp.status_code == 422, commit_resp.text
    detail = commit_resp.json()["detail"]
    assert isinstance(detail, dict)
    assert "items" in detail
    assert detail["items"][0]["item_id"] > 0
    assert "education_kind" in str(detail["items"][0]["validation_errors"]).lower()


def test_double_commit_returns_409(client, hr_admin_headers, pmf_employee):
    run_id = _create_draft_run_with_item(
        client, hr_admin_headers, pmf_employee["employee_id"]
    )
    first = client.post(
        f"/personnel-migration/runs/{run_id}/commit",
        json={"confirm": True},
        headers=hr_admin_headers,
    )
    assert first.status_code == 200, first.text

    second = client.post(
        f"/personnel-migration/runs/{run_id}/commit",
        json={"confirm": True},
        headers=hr_admin_headers,
    )
    assert second.status_code == 409, second.text


def test_void_run_requires_void_reason(client, hr_admin_headers, pmf_employee):
    run_id = _create_draft_run_with_item(
        client, hr_admin_headers, pmf_employee["employee_id"]
    )
    client.post(
        f"/personnel-migration/runs/{run_id}/commit",
        json={"confirm": True},
        headers=hr_admin_headers,
    )

    empty_resp = client.post(
        f"/personnel-migration/runs/{run_id}/void",
        json={"void_reason": ""},
        headers=hr_admin_headers,
    )
    assert empty_resp.status_code == 422

    blank_resp = client.post(
        f"/personnel-migration/runs/{run_id}/void",
        json={"void_reason": "   "},
        headers=hr_admin_headers,
    )
    assert blank_resp.status_code == 422


def test_void_run_voids_target_and_emits_event(client, hr_admin_headers, pmf_employee):
    run_id = _create_draft_run_with_item(
        client, hr_admin_headers, pmf_employee["employee_id"]
    )
    commit_resp = client.post(
        f"/personnel-migration/runs/{run_id}/commit",
        json={"confirm": True},
        headers=hr_admin_headers,
    )
    education_id = commit_resp.json()["committed_items"][0]["target_record_id"]

    void_resp = client.post(
        f"/personnel-migration/runs/{run_id}/void",
        json={"void_reason": "API rollback test"},
        headers=hr_admin_headers,
    )
    assert void_resp.status_code == 200, void_resp.text
    body = void_resp.json()
    assert body["run"]["run_status"] == RUN_STATUS_VOIDED
    assert body["voided_items"][0]["target_record_id"] == education_id

    with engine.begin() as conn:
        lifecycle = conn.execute(
            text(
                """
                SELECT lifecycle_status
                FROM public.person_education
                WHERE education_id = :education_id
                """
            ),
            {"education_id": education_id},
        ).scalar_one()
        event_type = conn.execute(
            text(
                """
                SELECT event_type
                FROM public.personnel_record_events
                WHERE event_id = :event_id
                """
            ),
            {"event_id": body["event_ids"][0]},
        ).scalar_one()

    assert lifecycle == LIFECYCLE_STATUS_VOIDED
    assert event_type == EVENT_TYPE_EDUCATION_VOIDED


def test_double_void_returns_409(client, hr_admin_headers, pmf_employee):
    run_id = _create_draft_run_with_item(
        client, hr_admin_headers, pmf_employee["employee_id"]
    )
    client.post(
        f"/personnel-migration/runs/{run_id}/commit",
        json={"confirm": True},
        headers=hr_admin_headers,
    )
    client.post(
        f"/personnel-migration/runs/{run_id}/void",
        json={"void_reason": "First void"},
        headers=hr_admin_headers,
    )

    second = client.post(
        f"/personnel-migration/runs/{run_id}/void",
        json={"void_reason": "Second void"},
        headers=hr_admin_headers,
    )
    assert second.status_code == 409, second.text


def test_supersede_record_via_api(client, hr_admin_headers, pmf_employee):
    run_id = _create_draft_run_with_item(
        client, hr_admin_headers, pmf_employee["employee_id"]
    )
    commit_resp = client.post(
        f"/personnel-migration/runs/{run_id}/commit",
        json={"confirm": True},
        headers=hr_admin_headers,
    )
    old_id = commit_resp.json()["committed_items"][0]["target_record_id"]

    supersede_resp = client.post(
        "/personnel-migration/records/supersede",
        json={
            "domain_code": DOMAIN_CODE_EDUCATION,
            "employee_context_id": pmf_employee["employee_id"],
            "record_table_name": "person_education",
            "record_id": old_id,
            "replacement_payload": {
                "education_kind": EDUCATION_KIND_BASIC,
                "institution_name": "Superseded University",
            },
        },
        headers=hr_admin_headers,
    )
    assert supersede_resp.status_code == 200, supersede_resp.text
    body = supersede_resp.json()
    new_id = body["replacement_record_id"]

    with engine.begin() as conn:
        old_status = conn.execute(
            text(
                """
                SELECT lifecycle_status
                FROM public.person_education
                WHERE education_id = :education_id
                """
            ),
            {"education_id": old_id},
        ).scalar_one()
        new_row = conn.execute(
            text(
                """
                SELECT lifecycle_status, institution_name
                FROM public.person_education
                WHERE education_id = :education_id
                """
            ),
            {"education_id": new_id},
        ).mappings().one()
        event_types = conn.execute(
            text(
                """
                SELECT event_type
                FROM public.personnel_record_events
                WHERE person_id = :person_id
                ORDER BY event_id ASC
                """
            ),
            {"person_id": pmf_employee["person_id"]},
        ).scalars().all()

    assert old_status == LIFECYCLE_STATUS_SUPERSEDED
    assert new_row["lifecycle_status"] == LIFECYCLE_STATUS_ACTIVE
    assert new_row["institution_name"] == "Superseded University"
    assert EVENT_TYPE_EDUCATION_MIGRATED in event_types
    assert EVENT_TYPE_EDUCATION_SUPERSEDED in event_types


def test_list_and_get_record_events(client, hr_admin_headers, pmf_employee):
    run_id = _create_draft_run_with_item(
        client, hr_admin_headers, pmf_employee["employee_id"]
    )
    commit_resp = client.post(
        f"/personnel-migration/runs/{run_id}/commit",
        json={"confirm": True},
        headers=hr_admin_headers,
    )
    event_id = commit_resp.json()["event_ids"][0]

    by_run_resp = client.get(
        f"/personnel-migration/runs/{run_id}/record-events",
        headers=hr_admin_headers,
    )
    assert by_run_resp.status_code == 200, by_run_resp.text
    by_run = by_run_resp.json()
    assert by_run["total"] >= 1
    assert any(item["event_id"] == event_id for item in by_run["items"])

    list_resp = client.get(
        "/personnel-migration/record-events",
        params={"migration_run_id": run_id},
        headers=hr_admin_headers,
    )
    assert list_resp.status_code == 200, list_resp.text
    assert list_resp.json()["total"] >= 1

    get_resp = client.get(
        f"/personnel-migration/record-events/{event_id}",
        headers=hr_admin_headers,
    )
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()["event_type"] == EVENT_TYPE_EDUCATION_MIGRATED


def test_list_record_events_requires_filter(client, hr_admin_headers):
    resp = client.get("/personnel-migration/record-events", headers=hr_admin_headers)
    assert resp.status_code == 422


def test_commit_route_delegates_to_commit_engine_not_direct_sql(
    client, hr_admin_headers, pmf_employee,
):
    run_id = _create_draft_run_with_item(
        client, hr_admin_headers, pmf_employee["employee_id"]
    )

    with patch(
        "app.api.personnel_migration_router.commit_run_tx",
        wraps=__import__(
            "app.services.personnel_migration_commit_service",
            fromlist=["commit_run_tx"],
        ).commit_run_tx,
    ) as commit_mock:
        resp = client.post(
            f"/personnel-migration/runs/{run_id}/commit",
            json={"confirm": True},
            headers=hr_admin_headers,
        )
    assert resp.status_code == 200, resp.text
    commit_mock.assert_called_once()

    with engine.begin() as conn:
        count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.person_education
                WHERE person_id = :person_id
                """
            ),
            {"person_id": pmf_employee["person_id"]},
        ).scalar_one()
    assert int(count) == 1


def test_draft_item_api_does_not_create_person_education(client, hr_admin_headers, pmf_employee):
    run_id = _create_draft_run_with_item(
        client, hr_admin_headers, pmf_employee["employee_id"]
    )
    assert run_id > 0

    with engine.begin() as conn:
        count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.person_education
                WHERE person_id = :person_id
                """
            ),
            {"person_id": pmf_employee["person_id"]},
        ).scalar_one()
    assert int(count) == 0

    get_resp = client.get(
        f"/personnel-migration/runs/{run_id}",
        headers=hr_admin_headers,
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["run_status"] == RUN_STATUS_DRAFT
