# tests/personnel_applications/test_director_resolution_api.py
"""API integration tests for director resolution + HIRE draft (WP-PPR-APPLICANT-002)."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.personnel_applications.domain.status import (
    APPLICATION_STATUS_APPROVED,
    APPLICATION_STATUS_ORDER_DRAFT_CREATED,
    APPLICATION_STATUS_REJECTED,
    APPLICATION_STATUS_RESOLUTION_PENDING,
    APPLICATION_STATUS_REVIEW_COMPLETED,
    APPLICATION_STATUS_REVISION_REQUESTED,
    VACANCY_CHECK_CONFIRMED_VISUALLY,
)
from app.ppr.domain.models import HR_RELATIONSHIP_CANDIDATE
from tests.conftest import auth_headers, table_exists
from tests.personnel_applications.conftest import materialize_envelope
from tests.ppr.conftest import cleanup_person_graph, ppr_db_available


def _unique_iin() -> str:
    return f"8{uuid4().int % 10_000_000_000_000:011d}"[:12]


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def applicant_schema_ready():
    if not ppr_db_available():
        pytest.skip("PostgreSQL not available")
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_application_resolution_audit"):
            pytest.skip("personnel_application_resolution_audit missing — run: alembic upgrade head")


def _placement_ids(conn) -> tuple[int | None, int | None]:
    org_unit_id = conn.execute(text("SELECT unit_id FROM public.org_units LIMIT 1")).scalar()
    position_id = conn.execute(text("SELECT position_id FROM public.positions LIMIT 1")).scalar()
    return (
        int(org_unit_id) if org_unit_id is not None else None,
        int(position_id) if position_id is not None else None,
    )


def _register_application(
    client,
    headers,
    *,
    org_unit_id: int | None = None,
    position_id: int | None = None,
) -> dict:
    payload = {
        "iin": _unique_iin(),
        "full_name": "Resolution Test Applicant",
        "application_received_at": "2026-07-17",
        "vacancy_check_status": VACANCY_CHECK_CONFIRMED_VISUALLY,
        "idempotency_key": f"resolution-{uuid4().hex}",
    }
    if org_unit_id is not None:
        payload["intended_org_unit_id"] = org_unit_id
    if position_id is not None:
        payload["intended_position_id"] = position_id
        payload["intended_employment_rate"] = 1.0
    reg = client.post("/directory/personnel-applications", json=payload, headers=headers)
    assert reg.status_code == 200, reg.text
    return reg.json()


def _prepare_review_completed(conn, *, application_id: int, person_id: int) -> None:
    materialize_envelope(conn, person_id, hr_context=HR_RELATIONSHIP_CANDIDATE)
    conn.execute(
        text(
            """
            UPDATE public.personnel_applications
            SET status = :status, updated_at = now()
            WHERE application_id = :application_id
            """
        ),
        {"status": APPLICATION_STATUS_REVIEW_COMPLETED, "application_id": application_id},
    )


def test_resolution_routes_registered(client, applicant_schema_ready) -> None:
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/directory/personnel-applications/{application_id}/director-resolution/open" in paths
    assert "/directory/personnel-applications/{application_id}/director-resolution" in paths
    assert "/directory/personnel-applications/{application_id}/director-resolution/change" in paths
    assert "/directory/personnel-applications/{application_id}/hire-order-draft" in paths


def test_resolution_workflow_open_record_reopen_and_audit(
    client, applicant_schema_ready, privileged_headers
) -> None:
    person_ids: list[int] = []
    try:
        with engine.begin() as conn:
            org_unit_id, position_id = _placement_ids(conn)
        reg = _register_application(
            client,
            privileged_headers,
            org_unit_id=org_unit_id,
            position_id=position_id,
        )
        person_ids.append(reg["person_id"])
        app_id = reg["application_id"]

        with engine.begin() as conn:
            _prepare_review_completed(conn, application_id=app_id, person_id=reg["person_id"])

        opened = client.post(
            f"/directory/personnel-applications/{app_id}/director-resolution/open",
            headers=privileged_headers,
        )
        assert opened.status_code == 200, opened.text
        assert opened.json()["status"] == APPLICATION_STATUS_RESOLUTION_PENDING

        reject_no_comment = client.post(
            f"/directory/personnel-applications/{app_id}/director-resolution",
            json={"outcome": "rejected", "comment": "   "},
            headers=privileged_headers,
        )
        assert reject_no_comment.status_code == 422
        assert reject_no_comment.json()["detail"]["code"] == "RESOLUTION_COMMENT_REQUIRED"

        revision = client.post(
            f"/directory/personnel-applications/{app_id}/director-resolution",
            json={"outcome": "revision_requested", "comment": "Уточните ставку"},
            headers=privileged_headers,
        )
        assert revision.status_code == 200
        assert revision.json()["status"] == APPLICATION_STATUS_REVISION_REQUESTED

        reopened = client.post(
            f"/directory/personnel-applications/{app_id}/director-resolution/reopen",
            headers=privileged_headers,
        )
        assert reopened.status_code == 200
        assert reopened.json()["status"] == APPLICATION_STATUS_RESOLUTION_PENDING

        approved = client.post(
            f"/directory/personnel-applications/{app_id}/director-resolution",
            json={"outcome": "approved", "comment": "Согласовано"},
            headers=privileged_headers,
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == APPLICATION_STATUS_APPROVED

        audit = client.get(
            f"/directory/personnel-applications/{app_id}/director-resolution/audit",
            headers=privileged_headers,
        )
        assert audit.status_code == 200
        actions = [item["action"] for item in audit.json()["items"]]
        assert "opened" in actions
        assert "recorded" in actions
        assert "reopened" in actions

        repeat_record = client.post(
            f"/directory/personnel-applications/{app_id}/director-resolution",
            json={"outcome": "rejected", "comment": "Поздно"},
            headers=privileged_headers,
        )
        assert repeat_record.status_code == 422
        assert repeat_record.json()["detail"]["code"] == "RESOLUTION_RECORD_NOT_ALLOWED"

        changed = client.post(
            f"/directory/personnel-applications/{app_id}/director-resolution/change",
            json={"outcome": "rejected", "comment": "Изменено решение"},
            headers=privileged_headers,
        )
        assert changed.status_code == 200
        assert changed.json()["status"] == APPLICATION_STATUS_REJECTED
    finally:
        if person_ids:
            with engine.begin() as conn:
                cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_hire_order_draft_idempotent_and_blocks_second_order(
    client, applicant_schema_ready, privileged_headers
) -> None:
    person_ids: list[int] = []
    try:
        with engine.begin() as conn:
            org_unit_id, position_id = _placement_ids(conn)
            if org_unit_id is None or position_id is None:
                pytest.skip("org_units/positions seed data required")

        reg = _register_application(
            client,
            privileged_headers,
            org_unit_id=org_unit_id,
            position_id=position_id,
        )
        person_ids.append(reg["person_id"])
        app_id = reg["application_id"]

        with engine.begin() as conn:
            _prepare_review_completed(conn, application_id=app_id, person_id=reg["person_id"])

        client.post(
            f"/directory/personnel-applications/{app_id}/director-resolution/open",
            headers=privileged_headers,
        )
        client.post(
            f"/directory/personnel-applications/{app_id}/director-resolution",
            json={"outcome": "approved", "comment": "OK"},
            headers=privileged_headers,
        )

        draft = client.post(
            f"/directory/personnel-applications/{app_id}/hire-order-draft",
            headers=privileged_headers,
        )
        assert draft.status_code == 200, draft.text
        body = draft.json()
        assert body["idempotent_replay"] is False
        assert body["application_status"] == APPLICATION_STATUS_ORDER_DRAFT_CREATED
        order_id = body["personnel_order_id"]

        replay = client.post(
            f"/directory/personnel-applications/{app_id}/hire-order-draft",
            headers=privileged_headers,
        )
        assert replay.status_code == 200
        assert replay.json()["idempotent_replay"] is True
        assert replay.json()["personnel_order_id"] == order_id

        detail = client.get(
            f"/directory/personnel-applications/{app_id}",
            headers=privileged_headers,
        )
        assert detail.json()["personnel_order_id"] == order_id

        with engine.begin() as conn:
            linked = conn.execute(
                text(
                    """
                    SELECT application_id
                    FROM public.personnel_applications
                    WHERE personnel_order_id = :order_id
                    """
                ),
                {"order_id": order_id},
            ).scalar_one()
            assert int(linked) == app_id

            item = conn.execute(
                text(
                    """
                    SELECT payload::text, item_type_code
                    FROM public.personnel_order_items
                    WHERE order_id = :order_id
                    LIMIT 1
                    """
                ),
                {"order_id": order_id},
            ).mappings().one()
            assert item["item_type_code"] == "HIRE"
            assert str(reg["person_id"]) in item["payload"]

            order_status = conn.execute(
                text("SELECT status FROM public.personnel_orders WHERE order_id = :order_id"),
                {"order_id": order_id},
            ).scalar_one()
            assert order_status == "DRAFT"
    finally:
        if person_ids:
            with engine.begin() as conn:
                cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_hire_order_draft_blocked_before_approval(
    client, applicant_schema_ready, privileged_headers
) -> None:
    person_ids: list[int] = []
    try:
        with engine.begin() as conn:
            org_unit_id, position_id = _placement_ids(conn)
        reg = _register_application(
            client,
            privileged_headers,
            org_unit_id=org_unit_id,
            position_id=position_id,
        )
        person_ids.append(reg["person_id"])
        app_id = reg["application_id"]

        with engine.begin() as conn:
            _prepare_review_completed(conn, application_id=app_id, person_id=reg["person_id"])

        blocked = client.post(
            f"/directory/personnel-applications/{app_id}/hire-order-draft",
            headers=privileged_headers,
        )
        assert blocked.status_code == 422
        assert blocked.json()["detail"]["code"] == "HIRE_DRAFT_NOT_ALLOWED"
    finally:
        if person_ids:
            with engine.begin() as conn:
                cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_open_resolution_guard(client, applicant_schema_ready, privileged_headers) -> None:
    person_ids: list[int] = []
    try:
        reg = _register_application(client, privileged_headers)
        person_ids.append(reg["person_id"])
        app_id = reg["application_id"]

        res = client.post(
            f"/directory/personnel-applications/{app_id}/director-resolution/open",
            headers=privileged_headers,
        )
        assert res.status_code == 422
        assert res.json()["detail"]["code"] == "RESOLUTION_OPEN_NOT_ALLOWED"
    finally:
        if person_ids:
            with engine.begin() as conn:
                cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])
