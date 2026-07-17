# tests/employee_onboarding/test_onboarding_api.py
"""API integration tests for Employee Onboarding (WP-ONBOARDING-001)."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.employee_onboarding.application.bootstrap_service import create_onboarding_from_hire
from app.employee_onboarding.domain.status import (
    CHECKLIST_CODE_LNA,
    ONBOARDING_STATUS_ACTIVE,
    ONBOARDING_STATUS_CANCELLED,
    ONBOARDING_STATUS_COMPLETED,
    STANDARD_CHECKLIST_CODES,
)
from app.main import app
from tests.conftest import auth_headers, table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_employee, insert_person, ppr_db_available

pytestmark = pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def onboarding_schema_ready():
    with engine.begin() as conn:
        if not table_exists(conn, "employee_onboardings"):
            pytest.skip("employee_onboardings missing — run: alembic upgrade head")


def test_onboarding_routes_registered(client, onboarding_schema_ready) -> None:
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/directory/employee-onboarding" in paths
    assert "/directory/employee-onboarding/by-employee/{employee_id}" in paths


def test_create_onboarding_seeds_checklist(onboarding_schema_ready, seed) -> None:
    person_ids: list[int] = []
    employee_ids: list[int] = []
    try:
        with engine.begin() as conn:
            person_id = insert_person(conn, full_name="Onboarding Seed Test")
            person_ids.append(person_id)
            employee_id = insert_employee(conn, full_name="Onboarding Seed Test", person_id=person_id)
            employee_ids.append(employee_id)
            result = create_onboarding_from_hire(
                conn,
                employee_id=employee_id,
                application_id=None,
                responsible_hr_id=int(seed["initiator_user_id"]),
            )
            assert result.idempotent_replay is False
            items = conn.execute(
                text(
                    """
                    SELECT item_code, status
                    FROM public.employee_onboarding_checklist_items
                    WHERE onboarding_id = :onboarding_id
                    ORDER BY sort_order ASC
                    """
                ),
                {"onboarding_id": result.onboarding_id},
            ).mappings().all()
        assert len(items) == len(STANDARD_CHECKLIST_CODES)
        assert [row["item_code"] for row in items] == list(STANDARD_CHECKLIST_CODES)
        assert all(row["status"] == "pending" for row in items)
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)


def test_onboarding_bootstrap_idempotent(onboarding_schema_ready, seed) -> None:
    person_ids: list[int] = []
    employee_ids: list[int] = []
    application_id = 0
    try:
        with engine.begin() as conn:
            person_id = insert_person(conn, full_name="Onboarding Idempotent")
            person_ids.append(person_id)
            employee_id = insert_employee(conn, full_name="Onboarding Idempotent", person_id=person_id)
            employee_ids.append(employee_id)
            application_id = conn.execute(
                text(
                    """
                    INSERT INTO public.personnel_applications (
                        person_id,
                        status,
                        application_received_at,
                        application_source,
                        vacancy_check_status,
                        registered_by_user_id
                    )
                    VALUES (
                        :person_id,
                        'completed',
                        CURRENT_DATE,
                        'paper',
                        'confirmed_visually',
                        :registered_by_user_id
                    )
                    RETURNING application_id
                    """
                ),
                {
                    "person_id": person_id,
                    "registered_by_user_id": int(seed["initiator_user_id"]),
                },
            ).scalar_one()
            first = create_onboarding_from_hire(
                conn,
                employee_id=employee_id,
                application_id=int(application_id),
                responsible_hr_id=int(seed["initiator_user_id"]),
            )
            second = create_onboarding_from_hire(
                conn,
                employee_id=employee_id,
                application_id=int(application_id),
                responsible_hr_id=int(seed["initiator_user_id"]),
            )
        assert first.onboarding_id == second.onboarding_id
        assert second.idempotent_replay is True
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)


def test_complete_checklist_item_updates_progress(
    client, onboarding_schema_ready, privileged_headers, seed
) -> None:
    person_ids: list[int] = []
    employee_ids: list[int] = []
    onboarding_id = 0
    item_id = 0
    try:
        with engine.begin() as conn:
            person_id = insert_person(conn, full_name="Checklist Complete Test")
            person_ids.append(person_id)
            employee_id = insert_employee(conn, full_name="Checklist Complete Test", person_id=person_id)
            employee_ids.append(employee_id)
            bootstrap = create_onboarding_from_hire(
                conn,
                employee_id=employee_id,
                application_id=None,
                responsible_hr_id=int(seed["initiator_user_id"]),
            )
            onboarding_id = bootstrap.onboarding_id
            item_id = conn.execute(
                text(
                    """
                    SELECT item_id
                    FROM public.employee_onboarding_checklist_items
                    WHERE onboarding_id = :onboarding_id AND item_code = :item_code
                    """
                ),
                {"onboarding_id": onboarding_id, "item_code": CHECKLIST_CODE_LNA},
            ).scalar_one()

        complete = client.post(
            f"/directory/employee-onboarding/{onboarding_id}/checklist/{item_id}/complete",
            json={"comment": "Подписан лист ознакомления"},
            headers=privileged_headers,
        )
        assert complete.status_code == 200, complete.text
        body = complete.json()
        assert body["progress_percent"] > 0
        lna = next(item for item in body["checklist_items"] if item["item_code"] == CHECKLIST_CODE_LNA)
        assert lna["status"] == "completed"
        assert lna["comment"] == "Подписан лист ознакомления"
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)


def test_complete_and_cancel_onboarding(client, onboarding_schema_ready, privileged_headers, seed) -> None:
    person_ids: list[int] = []
    employee_ids: list[int] = []
    try:
        with engine.begin() as conn:
            person_id = insert_person(conn, full_name="Onboarding Complete Test")
            person_ids.append(person_id)
            employee_id = insert_employee(conn, full_name="Onboarding Complete Test", person_id=person_id)
            employee_ids.append(employee_id)
            bootstrap = create_onboarding_from_hire(
                conn,
                employee_id=employee_id,
                application_id=None,
                responsible_hr_id=int(seed["initiator_user_id"]),
            )
            onboarding_id = bootstrap.onboarding_id

        complete = client.post(
            f"/directory/employee-onboarding/{onboarding_id}/complete",
            json={"notes": "Адаптация завершена"},
            headers=privileged_headers,
        )
        assert complete.status_code == 200, complete.text
        completed_body = complete.json()
        assert completed_body["status"] == ONBOARDING_STATUS_COMPLETED
        assert completed_body["is_read_only"] is True

        with engine.begin() as conn:
            person_id2 = insert_person(conn, full_name="Onboarding Cancel Test")
            person_ids.append(person_id2)
            employee_id2 = insert_employee(conn, full_name="Onboarding Cancel Test", person_id=person_id2)
            employee_ids.append(employee_id2)
            bootstrap2 = create_onboarding_from_hire(
                conn,
                employee_id=employee_id2,
                application_id=None,
                responsible_hr_id=int(seed["initiator_user_id"]),
            )
            onboarding_id2 = bootstrap2.onboarding_id

        cancel = client.post(
            f"/directory/employee-onboarding/{onboarding_id2}/cancel",
            json={"reason": "Досрочное прекращение адаптации"},
            headers=privileged_headers,
        )
        assert cancel.status_code == 200, cancel.text
        cancelled_body = cancel.json()
        assert cancelled_body["status"] == ONBOARDING_STATUS_CANCELLED
        assert cancelled_body["is_read_only"] is True
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)


def test_journal_list_and_get_by_employee(client, onboarding_schema_ready, privileged_headers, seed) -> None:
    person_ids: list[int] = []
    employee_ids: list[int] = []
    try:
        with engine.begin() as conn:
            person_id = insert_person(conn, full_name="Journal Onboarding Test")
            person_ids.append(person_id)
            employee_id = insert_employee(conn, full_name="Journal Onboarding Test", person_id=person_id)
            employee_ids.append(employee_id)
            create_onboarding_from_hire(
                conn,
                employee_id=employee_id,
                application_id=None,
                responsible_hr_id=int(seed["initiator_user_id"]),
            )

        listed = client.get(
            "/directory/employee-onboarding?status=active&q=Journal",
            headers=privileged_headers,
        )
        assert listed.status_code == 200, listed.text
        items = listed.json()["items"]
        assert any(item["employee_id"] == employee_id for item in items)
        assert items[0]["status"] == ONBOARDING_STATUS_ACTIVE

        by_employee = client.get(
            f"/directory/employee-onboarding/by-employee/{employee_id}",
            headers=privileged_headers,
        )
        assert by_employee.status_code == 200, by_employee.text
        assert by_employee.json()["employee_id"] == employee_id
        assert len(by_employee.json()["checklist_items"]) == len(STANDARD_CHECKLIST_CODES)
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)


def test_read_only_blocks_checklist_mutation(client, onboarding_schema_ready, privileged_headers, seed) -> None:
    person_ids: list[int] = []
    employee_ids: list[int] = []
    try:
        with engine.begin() as conn:
            person_id = insert_person(conn, full_name="Readonly Onboarding Test")
            person_ids.append(person_id)
            employee_id = insert_employee(conn, full_name="Readonly Onboarding Test", person_id=person_id)
            employee_ids.append(employee_id)
            bootstrap = create_onboarding_from_hire(
                conn,
                employee_id=employee_id,
                application_id=None,
                responsible_hr_id=int(seed["initiator_user_id"]),
            )
            onboarding_id = bootstrap.onboarding_id
            item_id = conn.execute(
                text(
                    """
                    SELECT item_id
                    FROM public.employee_onboarding_checklist_items
                    WHERE onboarding_id = :onboarding_id
                    LIMIT 1
                    """
                ),
                {"onboarding_id": onboarding_id},
            ).scalar_one()

        client.post(
            f"/directory/employee-onboarding/{onboarding_id}/complete",
            json={},
            headers=privileged_headers,
        )
        blocked = client.post(
            f"/directory/employee-onboarding/{onboarding_id}/checklist/{item_id}/complete",
            json={},
            headers=privileged_headers,
        )
        assert blocked.status_code == 422
        assert blocked.json()["detail"]["code"] == "ONBOARDING_READ_ONLY"
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)
