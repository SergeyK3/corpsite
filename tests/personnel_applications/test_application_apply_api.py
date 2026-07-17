# tests/personnel_applications/test_application_apply_api.py
"""API integration tests for HIRE apply + application completion (WP-PPR-APPLICANT-003)."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.personnel_applications.domain.status import (
    APPLICATION_STATUS_COMPLETED,
    APPLICATION_STATUS_ORDER_DRAFT_CREATED,
    VACANCY_CHECK_CONFIRMED_VISUALLY,
)
from app.ppr.domain.models import HR_RELATIONSHIP_CANDIDATE, HR_RELATIONSHIP_EMPLOYED
from tests.conftest import auth_headers, insert_returning_id, table_exists
from tests.personnel_applications.conftest import materialize_envelope
from tests.ppr.conftest import cleanup_person_graph, ppr_db_available
from tests.test_wp_po_003_personnel_orders_schema import (
    _delete_personnel_order_audit_rows,
    _require_schema,
)

pytestmark = [
    pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available"),
    pytest.mark.usefixtures("_require_wp_po_003_schema"),
]


@pytest.fixture(scope="module", autouse=True)
def _require_wp_po_003_schema():
    _require_schema()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def applicant_schema_ready():
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_applications"):
            pytest.skip("personnel_applications missing — run: alembic upgrade head")


def _unique_iin() -> str:
    return f"8{uuid4().int % 10_000_000_000_000:011d}"[:12]


def _placement_ids(conn) -> tuple[int | None, int | None]:
    org_unit_id = conn.execute(text("SELECT unit_id FROM public.org_units LIMIT 1")).scalar()
    position_id = conn.execute(text("SELECT position_id FROM public.positions LIMIT 1")).scalar()
    return (
        int(org_unit_id) if org_unit_id is not None else None,
        int(position_id) if position_id is not None else None,
    )


def _register_application(client, headers, *, org_unit_id: int, position_id: int) -> dict:
    reg = client.post(
        "/directory/personnel-applications",
        json={
            "iin": _unique_iin(),
            "full_name": "Apply Test Applicant",
            "application_received_at": "2026-07-17",
            "vacancy_check_status": VACANCY_CHECK_CONFIRMED_VISUALLY,
            "intended_org_unit_id": org_unit_id,
            "intended_position_id": position_id,
            "intended_employment_rate": 1.0,
            "idempotency_key": f"apply-{uuid4().hex}",
        },
        headers=headers,
    )
    assert reg.status_code == 200, reg.text
    return reg.json()


def _prepare_approved_with_draft_order(client, headers, *, org_unit_id: int, position_id: int) -> dict:
    reg = _register_application(
        client,
        headers,
        org_unit_id=org_unit_id,
        position_id=position_id,
    )
    app_id = reg["application_id"]
    person_id = reg["person_id"]

    with engine.begin() as conn:
        materialize_envelope(conn, person_id, hr_context=HR_RELATIONSHIP_CANDIDATE)
        conn.execute(
            text(
                """
                UPDATE public.personnel_applications
                SET status = 'review_completed', updated_at = now()
                WHERE application_id = :application_id
                """
            ),
            {"application_id": app_id},
        )

    client.post(
        f"/directory/personnel-applications/{app_id}/director-resolution/open",
        headers=headers,
    )
    client.post(
        f"/directory/personnel-applications/{app_id}/director-resolution",
        json={"outcome": "approved", "comment": "OK"},
        headers=headers,
    )
    draft = client.post(
        f"/directory/personnel-applications/{app_id}/hire-order-draft",
        headers=headers,
    )
    assert draft.status_code == 200, draft.text
    return {
        "application_id": app_id,
        "person_id": person_id,
        "personnel_order_id": draft.json()["personnel_order_id"],
    }


def _register_order(client, headers, order_id: int) -> None:
    patch_resp = client.patch(
        f"/directory/personnel-orders/{order_id}",
        json={"order_number": f"HIRE-APP-{uuid4().hex[:8]}"},
        headers=headers,
    )
    assert patch_resp.status_code == 200, patch_resp.text
    register_resp = client.post(
        f"/directory/personnel-orders/{order_id}/register",
        json={"target_status": "REGISTERED"},
        headers=headers,
    )
    assert register_resp.status_code == 200, register_resp.text


def _cleanup_application_graph(
    *,
    person_ids: list[int] | None = None,
    employee_ids: list[int] | None = None,
    order_ids: list[int] | None = None,
) -> None:
    with engine.begin() as conn:
        for order_id in order_ids or []:
            conn.execute(
                text("DELETE FROM public.employee_events WHERE order_id = :order_id"),
                {"order_id": int(order_id)},
            )
            _delete_personnel_order_audit_rows(conn, int(order_id))
        cleanup_person_graph(
            conn,
            person_ids=person_ids or [],
            employee_ids=employee_ids or [],
        )


def test_apply_route_registered(client, applicant_schema_ready) -> None:
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/directory/personnel-applications/{application_id}/apply" in paths


def test_application_apply_success_links_entities(
    client, applicant_schema_ready, privileged_headers
) -> None:
    person_ids: list[int] = []
    employee_ids: list[int] = []
    order_id = 0
    app_id = 0
    try:
        with engine.begin() as conn:
            org_unit_id, position_id = _placement_ids(conn)
            if org_unit_id is None or position_id is None:
                pytest.skip("org_units/positions seed data required")

        prepared = _prepare_approved_with_draft_order(
            client,
            privileged_headers,
            org_unit_id=org_unit_id,
            position_id=position_id,
        )
        person_ids.append(prepared["person_id"])
        app_id = prepared["application_id"]
        order_id = prepared["personnel_order_id"]
        _register_order(client, privileged_headers, order_id)

        apply_resp = client.post(
            f"/directory/personnel-applications/{app_id}/apply",
            headers=privileged_headers,
        )
        assert apply_resp.status_code == 200, apply_resp.text
        body = apply_resp.json()
        assert body["idempotent_replay"] is False
        assert body["application_status"] == APPLICATION_STATUS_COMPLETED
        assert body["personnel_order_id"] == order_id
        employee_id = int(body["employee_id"])
        employee_ids.append(employee_id)

        detail = client.get(
            f"/directory/personnel-applications/{app_id}",
            headers=privileged_headers,
        )
        assert detail.status_code == 200, detail.text
        detail_body = detail.json()
        assert detail_body["status"] == APPLICATION_STATUS_COMPLETED
        assert detail_body["employee_id"] == employee_id
        assert detail_body["is_read_only"] is True

        with engine.begin() as conn:
            app_row = conn.execute(
                text(
                    """
                    SELECT status, personnel_order_id, person_id
                    FROM public.personnel_applications
                    WHERE application_id = :application_id
                    """
                ),
                {"application_id": app_id},
            ).mappings().one()
            assert app_row["status"] == APPLICATION_STATUS_COMPLETED
            assert int(app_row["personnel_order_id"]) == order_id
            assert int(app_row["person_id"]) == prepared["person_id"]

            emp = conn.execute(
                text(
                    """
                    SELECT employee_id, person_id, is_active
                    FROM public.employees
                    WHERE employee_id = :employee_id
                    """
                ),
                {"employee_id": employee_id},
            ).mappings().one()
            assert int(emp["person_id"]) == prepared["person_id"]
            assert emp["is_active"] is True

            event = conn.execute(
                text(
                    """
                    SELECT employee_id, order_id, event_type
                    FROM public.employee_events
                    WHERE order_id = :order_id
                    """
                ),
                {"order_id": order_id},
            ).mappings().one()
            assert int(event["employee_id"]) == employee_id
            assert event["event_type"] == "HIRE"

            ctx = conn.execute(
                text(
                    """
                    SELECT hr_relationship_context
                    FROM public.personnel_record_metadata
                    WHERE person_id = :person_id
                    """
                ),
                {"person_id": prepared["person_id"]},
            ).scalar_one()
            assert ctx == HR_RELATIONSHIP_EMPLOYED

            employee_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.employees
                    WHERE person_id = :person_id
                    """
                ),
                {"person_id": prepared["person_id"]},
            ).scalar_one()
            assert int(employee_count) == 1
    finally:
        _cleanup_application_graph(
            order_ids=[order_id] if order_id else [],
            person_ids=person_ids,
            employee_ids=employee_ids,
        )


def test_application_apply_idempotent_replay(
    client, applicant_schema_ready, privileged_headers
) -> None:
    person_ids: list[int] = []
    employee_ids: list[int] = []
    order_id = 0
    app_id = 0
    try:
        with engine.begin() as conn:
            org_unit_id, position_id = _placement_ids(conn)
            if org_unit_id is None or position_id is None:
                pytest.skip("org_units/positions seed data required")

        prepared = _prepare_approved_with_draft_order(
            client,
            privileged_headers,
            org_unit_id=org_unit_id,
            position_id=position_id,
        )
        person_ids.append(prepared["person_id"])
        app_id = prepared["application_id"]
        order_id = prepared["personnel_order_id"]
        _register_order(client, privileged_headers, order_id)

        first = client.post(
            f"/directory/personnel-applications/{app_id}/apply",
            headers=privileged_headers,
        )
        assert first.status_code == 200, first.text
        employee_id = int(first.json()["employee_id"])
        employee_ids.append(employee_id)

        second = client.post(
            f"/directory/personnel-applications/{app_id}/apply",
            headers=privileged_headers,
        )
        assert second.status_code == 200, second.text
        replay = second.json()
        assert replay["idempotent_replay"] is True
        assert replay["employee_id"] == employee_id
        assert replay["application_status"] == APPLICATION_STATUS_COMPLETED

        with engine.begin() as conn:
            count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.employees
                    WHERE person_id = :person_id
                    """
                ),
                {"person_id": prepared["person_id"]},
            ).scalar_one()
            assert int(count) == 1
    finally:
        _cleanup_application_graph(
            order_ids=[order_id] if order_id else [],
            person_ids=person_ids,
            employee_ids=employee_ids,
        )


def test_application_apply_via_order_endpoint_completes_application(
    client, applicant_schema_ready, privileged_headers
) -> None:
    person_ids: list[int] = []
    employee_ids: list[int] = []
    order_id = 0
    app_id = 0
    try:
        with engine.begin() as conn:
            org_unit_id, position_id = _placement_ids(conn)
            if org_unit_id is None or position_id is None:
                pytest.skip("org_units/positions seed data required")

        prepared = _prepare_approved_with_draft_order(
            client,
            privileged_headers,
            org_unit_id=org_unit_id,
            position_id=position_id,
        )
        person_ids.append(prepared["person_id"])
        app_id = prepared["application_id"]
        order_id = prepared["personnel_order_id"]
        _register_order(client, privileged_headers, order_id)

        order_apply = client.post(
            f"/directory/personnel-orders/{order_id}/apply",
            headers=privileged_headers,
        )
        assert order_apply.status_code == 200, order_apply.text
        employee_id = int(order_apply.json()["events"][0]["employee_id"])
        employee_ids.append(employee_id)

        detail = client.get(
            f"/directory/personnel-applications/{app_id}",
            headers=privileged_headers,
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["status"] == APPLICATION_STATUS_COMPLETED
        assert detail.json()["employee_id"] == employee_id
    finally:
        _cleanup_application_graph(
            order_ids=[order_id] if order_id else [],
            person_ids=person_ids,
            employee_ids=employee_ids,
        )


def test_application_apply_rollback_when_person_already_employed(
    client, applicant_schema_ready, privileged_headers
) -> None:
    person_ids: list[int] = []
    employee_ids: list[int] = []
    order_id = 0
    app_id = 0
    try:
        with engine.begin() as conn:
            org_unit_id, position_id = _placement_ids(conn)
            if org_unit_id is None or position_id is None:
                pytest.skip("org_units/positions seed data required")

        prepared = _prepare_approved_with_draft_order(
            client,
            privileged_headers,
            org_unit_id=org_unit_id,
            position_id=position_id,
        )
        person_ids.append(prepared["person_id"])
        app_id = prepared["application_id"]
        order_id = prepared["personnel_order_id"]
        _register_order(client, privileged_headers, order_id)

        with engine.begin() as conn:
            existing_employee_id = insert_returning_id(
                conn,
                table="employees",
                id_col="employee_id",
                values={
                    "full_name": "Already employed",
                    "person_id": prepared["person_id"],
                    "org_unit_id": org_unit_id,
                    "position_id": position_id,
                    "employment_rate": 1.0,
                    "is_active": True,
                },
            )
            employee_ids.append(existing_employee_id)

        apply_resp = client.post(
            f"/directory/personnel-applications/{app_id}/apply",
            headers=privileged_headers,
        )
        assert apply_resp.status_code == 422, apply_resp.text
        assert apply_resp.json()["detail"]["code"] == "ACTIVE_EMPLOYEE_EXISTS"

        with engine.begin() as conn:
            app_status = conn.execute(
                text("SELECT status FROM public.personnel_applications WHERE application_id = :id"),
                {"id": app_id},
            ).scalar_one()
            assert app_status in {APPLICATION_STATUS_ORDER_DRAFT_CREATED, "approved"}
            event_count = conn.execute(
                text("SELECT COUNT(*) FROM public.employee_events WHERE order_id = :order_id"),
                {"order_id": order_id},
            ).scalar_one()
            assert int(event_count) == 0
    finally:
        _cleanup_application_graph(
            order_ids=[order_id] if order_id else [],
            person_ids=person_ids,
            employee_ids=employee_ids,
        )


def test_application_apply_blocked_without_registered_order(
    client, applicant_schema_ready, privileged_headers
) -> None:
    person_ids: list[int] = []
    order_id = 0
    app_id = 0
    try:
        with engine.begin() as conn:
            org_unit_id, position_id = _placement_ids(conn)
            if org_unit_id is None or position_id is None:
                pytest.skip("org_units/positions seed data required")

        prepared = _prepare_approved_with_draft_order(
            client,
            privileged_headers,
            org_unit_id=org_unit_id,
            position_id=position_id,
        )
        person_ids.append(prepared["person_id"])
        app_id = prepared["application_id"]
        order_id = prepared["personnel_order_id"]

        blocked = client.post(
            f"/directory/personnel-applications/{app_id}/apply",
            headers=privileged_headers,
        )
        assert blocked.status_code == 422, blocked.text
        assert blocked.json()["detail"]["code"] == "ORDER_NOT_APPLIABLE"
    finally:
        _cleanup_application_graph(
            order_ids=[order_id] if order_id else [],
            person_ids=person_ids,
            employee_ids=[],
        )


def test_application_apply_blocked_before_approval(
    client, applicant_schema_ready, privileged_headers
) -> None:
    person_ids: list[int] = []
    app_id = 0
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

        blocked = client.post(
            f"/directory/personnel-applications/{app_id}/apply",
            headers=privileged_headers,
        )
        assert blocked.status_code == 422, blocked.text
        assert blocked.json()["detail"]["code"] == "APPLY_NOT_ALLOWED"
    finally:
        _cleanup_application_graph(
            person_ids=person_ids,
            employee_ids=[],
        )
