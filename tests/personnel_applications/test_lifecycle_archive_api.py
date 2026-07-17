# tests/personnel_applications/test_lifecycle_archive_api.py
"""API integration tests for lifecycle archive (WP-PPR-APPLICANT-004)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.personnel_applications.domain.status import (
    APPLICATION_STATUS_CANCELLED,
    APPLICATION_STATUS_EXPIRED,
    APPLICATION_STATUS_REGISTERED,
    VACANCY_CHECK_CONFIRMED_VISUALLY,
)
from app.personnel_intake.application.intake_service import _hash_token
from tests.conftest import auth_headers, table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_employee, ppr_db_available

pytestmark = pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def lifecycle_schema_ready():
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_applications"):
            pytest.skip("personnel_applications missing — run: alembic upgrade head")
        if not table_exists(conn, "personnel_application_lifecycle_audit"):
            pytest.skip("personnel_application_lifecycle_audit missing — run: alembic upgrade head")


def _unique_iin() -> str:
    return f"8{uuid4().int % 10_000_000_000_000:011d}"[:12]


def _register_application(client, headers, *, iin: str | None = None) -> dict:
    reg = client.post(
        "/directory/personnel-applications",
        json={
            "iin": iin or _unique_iin(),
            "full_name": "Lifecycle Test Applicant",
            "application_received_at": "2026-07-17",
            "vacancy_check_status": VACANCY_CHECK_CONFIRMED_VISUALLY,
            "idempotency_key": f"lifecycle-{uuid4().hex}",
        },
        headers=headers,
    )
    assert reg.status_code == 200, reg.text
    return reg.json()


def test_lifecycle_routes_registered(client, lifecycle_schema_ready) -> None:
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/directory/personnel-applications/{application_id}/cancel" in paths
    assert "/directory/personnel-applications/{application_id}/timeline" in paths
    assert "/directory/personnel-applications/{application_id}/lifecycle-audit" in paths


def test_cancel_application_success(client, lifecycle_schema_ready, privileged_headers) -> None:
    person_ids: list[int] = []
    try:
        reg = _register_application(client, privileged_headers)
        person_ids.append(reg["person_id"])
        app_id = reg["application_id"]

        cancel = client.post(
            f"/directory/personnel-applications/{app_id}/cancel",
            json={"reason": "Претендент отказался"},
            headers=privileged_headers,
        )
        assert cancel.status_code == 200, cancel.text
        body = cancel.json()
        assert body["status"] == APPLICATION_STATUS_CANCELLED
        assert body["audit"]["action"] == "cancelled"
        assert body["audit"]["comment"] == "Претендент отказался"

        detail = client.get(f"/directory/personnel-applications/{app_id}", headers=privileged_headers)
        assert detail.status_code == 200
        detail_body = detail.json()
        assert detail_body["status"] == APPLICATION_STATUS_CANCELLED
        assert detail_body["is_read_only"] is True
        assert detail_body["cancel_reason"] == "Претендент отказался"
        assert detail_body["closed_at"] is not None
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_cancel_requires_reason(client, lifecycle_schema_ready, privileged_headers) -> None:
    person_ids: list[int] = []
    try:
        reg = _register_application(client, privileged_headers)
        person_ids.append(reg["person_id"])
        app_id = reg["application_id"]

        cancel = client.post(
            f"/directory/personnel-applications/{app_id}/cancel",
            json={"reason": "   "},
            headers=privileged_headers,
        )
        assert cancel.status_code == 422
        assert cancel.json()["detail"]["code"] == "CANCEL_REASON_REQUIRED"
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_cancel_blocked_after_employee_exists(
    client, lifecycle_schema_ready, privileged_headers
) -> None:
    person_ids: list[int] = []
    employee_ids: list[int] = []
    try:
        reg = _register_application(client, privileged_headers)
        person_ids.append(reg["person_id"])
        app_id = reg["application_id"]

        with engine.begin() as conn:
            employee_id = insert_employee(conn, person_id=reg["person_id"], full_name="Lifecycle Employee")
            employee_ids.append(int(employee_id))

        cancel = client.post(
            f"/directory/personnel-applications/{app_id}/cancel",
            json={"reason": "Too late"},
            headers=privileged_headers,
        )
        assert cancel.status_code == 422
        assert cancel.json()["detail"]["code"] == "EMPLOYEE_EXISTS"
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(
                conn,
                person_ids=person_ids,
                employee_ids=employee_ids,
            )


def test_expire_on_list_moves_application_to_archive(
    client, lifecycle_schema_ready, privileged_headers
) -> None:
    person_ids: list[int] = []
    try:
        reg = _register_application(client, privileged_headers)
        person_ids.append(reg["person_id"])
        app_id = reg["application_id"]

        issue = client.post(
            f"/directory/personnel-applications/{app_id}/intake-link",
            headers=privileged_headers,
        )
        assert issue.status_code == 200, issue.text
        token = issue.json()["intake_url_path"].split("/intake/")[-1]
        token_hash = _hash_token(token)

        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE public.personnel_intake_links
                    SET expires_at = :past
                    WHERE token_hash = :token_hash
                    """
                ),
                {"past": datetime.now(UTC) - timedelta(hours=2), "token_hash": token_hash},
            )

        active = client.get(
            "/directory/personnel-applications?view=active",
            headers=privileged_headers,
        )
        assert active.status_code == 200
        active_ids = {item["application_id"] for item in active.json()["items"]}
        assert app_id not in active_ids

        archive = client.get(
            "/directory/personnel-applications?view=archive",
            headers=privileged_headers,
        )
        assert archive.status_code == 200
        archived = next(
            (item for item in archive.json()["items"] if item["application_id"] == app_id),
            None,
        )
        assert archived is not None
        assert archived["status"] == APPLICATION_STATUS_EXPIRED
        assert archived["is_read_only"] is True
        assert archived["closed_at"] is not None

        with engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT status, closed_at
                    FROM public.personnel_applications
                    WHERE application_id = :application_id
                    """
                ),
                {"application_id": app_id},
            ).mappings().one()
            assert row["status"] == APPLICATION_STATUS_EXPIRED
            assert row["closed_at"] is not None
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_archive_filter_and_active_excludes_terminal(
    client, lifecycle_schema_ready, privileged_headers
) -> None:
    person_ids: list[int] = []
    try:
        active_reg = _register_application(client, privileged_headers)
        person_ids.append(active_reg["person_id"])
        active_id = active_reg["application_id"]

        cancelled_reg = _register_application(client, privileged_headers)
        person_ids.append(cancelled_reg["person_id"])
        cancelled_id = cancelled_reg["application_id"]
        cancel = client.post(
            f"/directory/personnel-applications/{cancelled_id}/cancel",
            json={"reason": "Duplicate application"},
            headers=privileged_headers,
        )
        assert cancel.status_code == 200, cancel.text

        active_list = client.get(
            "/directory/personnel-applications?view=active",
            headers=privileged_headers,
        )
        assert active_list.status_code == 200
        active_ids = {item["application_id"] for item in active_list.json()["items"]}
        assert active_id in active_ids
        assert cancelled_id not in active_ids

        archive_list = client.get(
            f"/directory/personnel-applications?view=archive&q={cancelled_id}",
            headers=privileged_headers,
        )
        assert archive_list.status_code == 200
        archive_ids = {item["application_id"] for item in archive_list.json()["items"]}
        assert cancelled_id in archive_ids
        assert active_id not in archive_ids
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_timeline_and_combined_audit(client, lifecycle_schema_ready, privileged_headers) -> None:
    person_ids: list[int] = []
    try:
        reg = _register_application(client, privileged_headers)
        person_ids.append(reg["person_id"])
        app_id = reg["application_id"]

        timeline = client.get(
            f"/directory/personnel-applications/{app_id}/timeline",
            headers=privileged_headers,
        )
        assert timeline.status_code == 200, timeline.text
        timeline_body = timeline.json()
        assert timeline_body["application_id"] == app_id
        codes = {item["code"] for item in timeline_body["items"]}
        assert "registered" in codes

        cancel = client.post(
            f"/directory/personnel-applications/{app_id}/cancel",
            json={"reason": "Timeline audit test"},
            headers=privileged_headers,
        )
        assert cancel.status_code == 200

        audit = client.get(
            f"/directory/personnel-applications/{app_id}/lifecycle-audit",
            headers=privileged_headers,
        )
        assert audit.status_code == 200, audit.text
        audit_items = audit.json()["items"]
        assert any(item["action"] == "cancelled" for item in audit_items)

        timeline_after = client.get(
            f"/directory/personnel-applications/{app_id}/timeline",
            headers=privileged_headers,
        )
        after_codes = {item["code"] for item in timeline_after.json()["items"]}
        assert "cancelled" in after_codes
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_active_list_includes_registered_application(
    client, lifecycle_schema_ready, privileged_headers
) -> None:
    person_ids: list[int] = []
    try:
        reg = _register_application(client, privileged_headers)
        person_ids.append(reg["person_id"])
        app_id = reg["application_id"]

        listed = client.get(
            "/directory/personnel-applications?view=active",
            headers=privileged_headers,
        )
        assert listed.status_code == 200
        item = next(
            (row for row in listed.json()["items"] if row["application_id"] == app_id),
            None,
        )
        assert item is not None
        assert item["status"] == APPLICATION_STATUS_REGISTERED
        assert item["is_active"] is True
        assert item["is_read_only"] is False
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])
