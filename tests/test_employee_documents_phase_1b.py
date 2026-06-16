# tests/test_employee_documents_phase_1b.py
from __future__ import annotations

from datetime import date, timedelta
from typing import List
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.employee_documents_service import (
    DEFAULT_TRAINING_HOURS_REQUIRED,
    TRAINING_HOURS_STATUS_BELOW,
    TRAINING_HOURS_STATUS_EMPTY,
    TRAINING_HOURS_STATUS_INCOMPLETE,
    TRAINING_HOURS_STATUS_MET,
    get_employee_training_hours_summary,
)
from tests.conftest import auth_headers, table_exists
from tests.test_employee_documents_routes import (
    _cleanup_documents,
    _cleanup_employees,
    _lookup_document_type_id,
    _lookup_specialty_id,
    _make_employee,
    _phase_1a_available,
)

REVISION_1B = "f2b3c4d5e6a7"


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _phase_1b_available() -> bool:
    if not _phase_1a_available():
        return False
    with engine.begin() as conn:
        cols = conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'employee_documents'
                  AND column_name = 'hours'
                """
            )
        ).first()
        return cols is not None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_document_types_tracks_hours_seed(client, seed, privileged_headers):
    if not _phase_1b_available():
        pytest.skip("ADR-037 Phase 1B migration missing — run alembic upgrade head")

    resp = client.get("/directory/document-types", headers=privileged_headers)
    assert resp.status_code == 200, resp.text
    by_code = {item["code"]: item for item in resp.json()["items"]}
    for code in (
        "CONTINUING_EDUCATION",
        "CONFERENCE_PARTICIPATION",
        "MASTERCLASS_PARTICIPATION",
        "SEMINAR_PARTICIPATION",
    ):
        assert by_code[code]["tracks_hours"] is True
    assert by_code["SPECIALIST_CERTIFICATION"]["tracks_hours"] is False


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_hours_validation_on_tracking_types(client, seed, privileged_headers):
    emp_id, emp_ids, pos_ids = _make_employee(seed)
    try:
        with engine.begin() as conn:
            seminar_type_id = _lookup_document_type_id(conn, "SEMINAR_PARTICIPATION")

        missing_hours = client.post(
            "/directory/employee-documents",
            json={
                "employee_id": emp_id,
                "document_type_id": seminar_type_id,
                "issued_at": date.today().isoformat(),
            },
            headers=privileged_headers,
        )
        assert missing_hours.status_code == 422

        zero_hours = client.post(
            "/directory/employee-documents",
            json={
                "employee_id": emp_id,
                "document_type_id": seminar_type_id,
                "issued_at": date.today().isoformat(),
                "hours": 0,
            },
            headers=privileged_headers,
        )
        assert zero_hours.status_code == 422

        missing_date = client.post(
            "/directory/employee-documents",
            json={
                "employee_id": emp_id,
                "document_type_id": seminar_type_id,
                "hours": 12,
            },
            headers=privileged_headers,
        )
        assert missing_date.status_code == 422
    finally:
        _cleanup_employees(emp_ids, pos_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_training_summary_rolling_window_and_statuses(client, seed, privileged_headers):
    if not _phase_1b_available():
        pytest.skip("ADR-037 Phase 1B migration missing — run alembic upgrade head")

    emp_id, emp_ids, pos_ids = _make_employee(seed)
    document_ids: List[int] = []
    as_of = date(2026, 6, 16)

    try:
        with engine.begin() as conn:
            seminar_type_id = _lookup_document_type_id(conn, "SEMINAR_PARTICIPATION")
            continuing_type_id = _lookup_document_type_id(conn, "CONTINUING_EDUCATION")
            specialty_id = _lookup_specialty_id(conn, "ONCOLOGY")

        empty = client.get(
            "/directory/employee-documents/training-summary",
            params={"employee_id": emp_id, "as_of": as_of.isoformat()},
            headers=privileged_headers,
        )
        assert empty.status_code == 200, empty.text
        empty_body = empty.json()
        assert empty_body["training_hours_last_5y"] == 0
        assert empty_body["training_hours_required"] == DEFAULT_TRAINING_HOURS_REQUIRED
        assert empty_body["training_hours_remaining"] == DEFAULT_TRAINING_HOURS_REQUIRED
        assert empty_body["training_hours_status"] == TRAINING_HOURS_STATUS_EMPTY
        assert empty_body["window_start"] == "2021-06-16"

        for hours, issued_at in ((72, as_of - timedelta(days=400)), (80, as_of - timedelta(days=200))):
            resp = client.post(
                "/directory/employee-documents",
                json={
                    "employee_id": emp_id,
                    "document_type_id": seminar_type_id,
                    "issued_at": issued_at.isoformat(),
                    "hours": hours,
                    "title": f"Seminar {uuid4().hex[:4]}",
                },
                headers=privileged_headers,
            )
            assert resp.status_code == 201, resp.text
            document_ids.append(int(resp.json()["document_id"]))

        below = client.get(
            "/directory/employee-documents/training-summary",
            params={"employee_id": emp_id, "as_of": as_of.isoformat()},
            headers=privileged_headers,
        )
        assert below.status_code == 200
        below_body = below.json()
        assert below_body["training_hours_last_5y"] == 152
        assert below_body["training_hours_status"] == TRAINING_HOURS_STATUS_MET
        assert below_body["training_hours_remaining"] == 0

        old_resp = client.post(
            "/directory/employee-documents",
            json={
                "employee_id": emp_id,
                "document_type_id": continuing_type_id,
                "medical_specialty_id": specialty_id,
                "issued_at": (as_of - timedelta(days=365 * 6)).isoformat(),
                "hours": 40,
                "training_title": "Old PK",
            },
            headers=privileged_headers,
        )
        assert old_resp.status_code == 201, old_resp.text
        document_ids.append(int(old_resp.json()["document_id"]))

        still_met = client.get(
            "/directory/employee-documents/training-summary",
            params={"employee_id": emp_id, "as_of": as_of.isoformat()},
            headers=privileged_headers,
        )
        assert still_met.json()["training_hours_last_5y"] == 152

        incomplete_resp = client.post(
            "/directory/employee-documents",
            json={
                "employee_id": emp_id,
                "document_type_id": seminar_type_id,
                "hours": 10,
                "title": "Incomplete seminar",
            },
            headers=privileged_headers,
        )
        assert incomplete_resp.status_code == 422

        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO public.employee_documents (
                        employee_id,
                        document_type_id,
                        lifecycle_status,
                        created_by,
                        hours
                    )
                    VALUES (:employee_id, :document_type_id, 'ACTIVE', :created_by, 10)
                    RETURNING document_id
                    """
                ),
                {
                    "employee_id": emp_id,
                    "document_type_id": seminar_type_id,
                    "created_by": int(seed["initiator_user_id"]),
                },
            )
            incomplete_id = conn.execute(
                text(
                    """
                    SELECT document_id
                    FROM public.employee_documents
                    WHERE employee_id = :employee_id
                      AND title IS NULL
                      AND hours = 10
                    ORDER BY document_id DESC
                    LIMIT 1
                    """
                ),
                {"employee_id": emp_id},
            ).scalar()
            document_ids.append(int(incomplete_id))

        incomplete = client.get(
            "/directory/employee-documents/training-summary",
            params={"employee_id": emp_id, "as_of": as_of.isoformat()},
            headers=privileged_headers,
        )
        assert incomplete.status_code == 200
        incomplete_body = incomplete.json()
        assert incomplete_body["training_hours_status"] == TRAINING_HOURS_STATUS_INCOMPLETE
        assert incomplete_body["incomplete_documents_count"] >= 1
        assert incomplete_body["training_hours_last_5y"] == 152

        delete = client.delete(
            f"/directory/employee-documents/{document_ids[-1]}",
            headers=privileged_headers,
        )
        assert delete.status_code == 200

        after_delete = client.get(
            "/directory/employee-documents/training-summary",
            params={"employee_id": emp_id, "as_of": as_of.isoformat()},
            headers=privileged_headers,
        )
        assert after_delete.json()["training_hours_status"] == TRAINING_HOURS_STATUS_MET

        service_summary = get_employee_training_hours_summary(
            employee_id=emp_id,
            as_of=as_of,
        )
        assert service_summary["training_hours_required"] == DEFAULT_TRAINING_HOURS_REQUIRED
        assert service_summary["training_hours_status"] == TRAINING_HOURS_STATUS_MET
    finally:
        _cleanup_documents(document_ids)
        _cleanup_employees(emp_ids, pos_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_training_summary_below_status(client, seed, privileged_headers):
    if not _phase_1b_available():
        pytest.skip("ADR-037 Phase 1B migration missing — run alembic upgrade head")

    emp_id, emp_ids, pos_ids = _make_employee(seed)
    document_ids: List[int] = []
    as_of = date(2026, 6, 16)

    try:
        with engine.begin() as conn:
            seminar_type_id = _lookup_document_type_id(conn, "SEMINAR_PARTICIPATION")

        resp = client.post(
            "/directory/employee-documents",
            json={
                "employee_id": emp_id,
                "document_type_id": seminar_type_id,
                "issued_at": as_of.isoformat(),
                "hours": 72,
            },
            headers=privileged_headers,
        )
        assert resp.status_code == 201
        document_ids.append(int(resp.json()["document_id"]))

        summary = client.get(
            "/directory/employee-documents/training-summary",
            params={"employee_id": emp_id, "as_of": as_of.isoformat()},
            headers=privileged_headers,
        )
        body = summary.json()
        assert body["training_hours_last_5y"] == 72
        assert body["training_hours_status"] == TRAINING_HOURS_STATUS_BELOW
        assert body["training_hours_remaining"] == DEFAULT_TRAINING_HOURS_REQUIRED - 72
    finally:
        _cleanup_documents(document_ids)
        _cleanup_employees(emp_ids, pos_ids)
