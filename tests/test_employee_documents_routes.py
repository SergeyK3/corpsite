# tests/test_employee_documents_routes.py
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.employee_documents_service import compute_expiry_status
from tests.conftest import auth_headers, get_columns, insert_returning_id, table_exists

REVISION_TABLES = (
    "medical_specialty_groups",
    "medical_specialties",
    "document_types",
    "document_kinds",
    "employee_documents",
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _phase_1a_available() -> bool:
    with engine.begin() as conn:
        return all(table_exists(conn, t) for t in REVISION_TABLES)


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


def _lookup_document_kind_id(conn, code: str) -> int:
    row = conn.execute(
        text(
            """
            SELECT document_kind_id
            FROM public.document_kinds
            WHERE code = :code
            LIMIT 1
            """
        ),
        {"code": code},
    ).first()
    assert row is not None, f"document kind {code} missing"
    return int(row[0])


def _lookup_document_type_id(conn, code: str) -> int:
    row = conn.execute(
        text(
            """
            SELECT document_type_id
            FROM public.document_types
            WHERE code = :code
            LIMIT 1
            """
        ),
        {"code": code},
    ).first()
    assert row is not None, f"document type {code} missing"
    return int(row[0])


def _lookup_specialty_id(conn, code: str) -> int:
    row = conn.execute(
        text(
            """
            SELECT medical_specialty_id
            FROM public.medical_specialties
            WHERE code = :code
            LIMIT 1
            """
        ),
        {"code": code},
    ).first()
    assert row is not None, f"specialty {code} missing"
    return int(row[0])


def _lookup_group_id(conn, code: str) -> int:
    row = conn.execute(
        text(
            """
            SELECT group_id
            FROM public.medical_specialty_groups
            WHERE code = :code
            LIMIT 1
            """
        ),
        {"code": code},
    ).first()
    assert row is not None, f"group {code} missing"
    return int(row[0])


def _create_position(conn, *, name: str) -> int:
    cols = get_columns(conn, "positions")
    values: Dict[str, Any] = {"name": name}
    if "category" in cols:
        values["category"] = "other"
    return insert_returning_id(conn, table="positions", id_col="position_id", values=values)


def _create_employee(
    conn,
    *,
    full_name: str,
    org_unit_id: int,
    position_id: int,
    is_active: bool = True,
) -> int:
    return insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values={
            "full_name": full_name,
            "org_unit_id": int(org_unit_id),
            "position_id": int(position_id),
            "employment_rate": 1.0,
            "is_active": is_active,
        },
    )


def _count_employee_events(conn, employee_id: int) -> int:
    if not table_exists(conn, "employee_events"):
        return 0
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.employee_events
                WHERE employee_id = :employee_id
                """
            ),
            {"employee_id": int(employee_id)},
        ).scalar()
        or 0
    )


def _cleanup_documents(document_ids: List[int]) -> None:
    if not document_ids:
        return
    with engine.begin() as conn:
        if table_exists(conn, "employee_documents"):
            conn.execute(
                text("DELETE FROM public.employee_documents WHERE document_id = ANY(:ids)"),
                {"ids": [int(x) for x in document_ids]},
            )


def _cleanup_employees(employee_ids: List[int], position_ids: List[int]) -> None:
    if employee_ids:
        _cleanup_documents_for_employees(employee_ids)
    with engine.begin() as conn:
        if employee_ids and table_exists(conn, "employees"):
            if table_exists(conn, "employee_events"):
                conn.execute(
                    text("DELETE FROM public.employee_events WHERE employee_id = ANY(:ids)"),
                    {"ids": employee_ids},
                )
            conn.execute(
                text("DELETE FROM public.employees WHERE employee_id = ANY(:ids)"),
                {"ids": employee_ids},
            )
        if position_ids and table_exists(conn, "positions"):
            conn.execute(
                text("DELETE FROM public.positions WHERE position_id = ANY(:ids)"),
                {"ids": position_ids},
            )


def _cleanup_documents_for_employees(employee_ids: List[int]) -> None:
    if not employee_ids:
        return
    with engine.begin() as conn:
        if table_exists(conn, "employee_documents"):
            conn.execute(
                text("DELETE FROM public.employee_documents WHERE employee_id = ANY(:ids)"),
                {"ids": employee_ids},
            )


def _make_employee(seed, *, is_active: bool = True) -> tuple[int, List[int], List[int]]:
    emp_ids: List[int] = []
    pos_ids: List[int] = []
    with engine.begin() as conn:
        if not _phase_1a_available():
            pytest.skip("ADR-037 Phase 1A tables missing — run alembic upgrade head")
        pos_id = _create_position(conn, name=f"pytest_edoc_{uuid4().hex[:8]}")
        pos_ids.append(pos_id)
        emp_id = _create_employee(
            conn,
            full_name=f"PytestEDoc {uuid4().hex[:8]}",
            org_unit_id=int(seed["unit_id"]),
            position_id=pos_id,
            is_active=is_active,
        )
        emp_ids.append(emp_id)
    return emp_id, emp_ids, pos_ids


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_compute_expiry_status_values():
    today = date(2026, 6, 16)
    assert compute_expiry_status(None, today=today) == "NO_EXPIRY"
    assert compute_expiry_status(today - timedelta(days=1), today=today) == "EXPIRED"
    assert compute_expiry_status(today + timedelta(days=10), today=today) == "EXPIRING_30"
    assert compute_expiry_status(today + timedelta(days=45), today=today) == "EXPIRING_60"
    assert compute_expiry_status(today + timedelta(days=120), today=today) == "VALID"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_document_kinds_seed(client, seed, privileged_headers):
    if not _phase_1a_available():
        pytest.skip("ADR-037 Phase 1A tables missing — run alembic upgrade head")

    resp = client.get("/directory/document-kinds", headers=privileged_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 6
    codes = {item["code"] for item in body["items"]}
    assert "CERTIFICATE" in codes
    assert "DIPLOMA" in codes


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_document_types_seed(client, seed, privileged_headers):
    if not _phase_1a_available():
        pytest.skip("ADR-037 Phase 1A tables missing — run alembic upgrade head")

    resp = client.get("/directory/document-types", headers=privileged_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 7
    codes = {item["code"] for item in body["items"]}
    assert "SPECIALIST_CERTIFICATION" in codes
    assert "SEMINAR_PARTICIPATION" in codes


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_reference_endpoints_unprivileged_forbidden(client, seed):
    if not _phase_1a_available():
        pytest.skip("ADR-037 Phase 1A tables missing — run alembic upgrade head")

    headers = auth_headers(seed["executor_user_id"])
    for path in (
        "/directory/document-types",
        "/directory/document-kinds",
        "/directory/medical-specialty-groups",
        "/directory/medical-specialties",
        "/directory/employee-documents",
    ):
        resp = client.get(path, headers=headers)
        assert resp.status_code == 403, path


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_create_update_soft_delete_and_no_employee_events(
    client, seed, privileged_headers
):
    emp_id, emp_ids, pos_ids = _make_employee(seed)
    document_ids: List[int] = []

    try:
        with engine.begin() as conn:
            specialist_type_id = _lookup_document_type_id(conn, "SPECIALIST_CERTIFICATION")
            specialty_id = _lookup_specialty_id(conn, "ONCOLOGY")
            cert_kind_id = _lookup_document_kind_id(conn, "CERTIFICATE")
            events_before = _count_employee_events(conn, emp_id)

        valid_until = date.today() + timedelta(days=45)
        create = client.post(
            "/directory/employee-documents",
            json={
                "employee_id": emp_id,
                "document_type_id": specialist_type_id,
                "document_kind_id": cert_kind_id,
                "medical_specialty_id": specialty_id,
                "training_title": "Программа повышения квалификации",
                "document_number": f"SP-{uuid4().hex[:6]}",
                "valid_until": valid_until.isoformat(),
                "file_url": "\\\\server\\share\\cert.pdf",
            },
            headers=privileged_headers,
        )
        assert create.status_code == 201, create.text
        created = create.json()
        document_ids.append(int(created["document_id"]))
        assert created["expiry_status"] == "EXPIRING_60"
        assert created["document_kind_code"] == "CERTIFICATE"
        assert created["training_title"] == "Программа повышения квалификации"
        assert created["file_url"] == "\\\\server\\share\\cert.pdf"
        assert created["lifecycle_status"] == "ACTIVE"

        with engine.begin() as conn:
            assert _count_employee_events(conn, emp_id) == events_before

        update = client.put(
            f"/directory/employee-documents/{created['document_id']}",
            json={"comment": "updated by pytest"},
            headers=privileged_headers,
        )
        assert update.status_code == 200, update.text
        assert update.json()["comment"] == "updated by pytest"

        with engine.begin() as conn:
            assert _count_employee_events(conn, emp_id) == events_before

        delete = client.delete(
            f"/directory/employee-documents/{created['document_id']}",
            headers=privileged_headers,
        )
        assert delete.status_code == 200, delete.text
        assert delete.json()["lifecycle_status"] == "SUPERSEDED"

        with engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT lifecycle_status
                    FROM public.employee_documents
                    WHERE document_id = :document_id
                    """
                ),
                {"document_id": int(created["document_id"])},
            ).first()
            assert row is not None
            assert str(row[0]) == "SUPERSEDED"
            assert _count_employee_events(conn, emp_id) == events_before

        listed = client.get("/directory/employee-documents", headers=privileged_headers)
        assert listed.status_code == 200
        ids = {item["document_id"] for item in listed.json()["items"]}
        assert int(created["document_id"]) not in ids
    finally:
        _cleanup_documents(document_ids)
        _cleanup_employees(emp_ids, pos_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_validation_specialty_and_valid_until_and_draft(
    client, seed, privileged_headers
):
    emp_id, emp_ids, pos_ids = _make_employee(seed)
    try:
        with engine.begin() as conn:
            specialist_type_id = _lookup_document_type_id(conn, "SPECIALIST_CERTIFICATION")
            seminar_type_id = _lookup_document_type_id(conn, "SEMINAR_PARTICIPATION")

        missing_specialty = client.post(
            "/directory/employee-documents",
            json={
                "employee_id": emp_id,
                "document_type_id": specialist_type_id,
                "valid_until": (date.today() + timedelta(days=30)).isoformat(),
            },
            headers=privileged_headers,
        )
        assert missing_specialty.status_code == 422

        seminar_with_expiry = client.post(
            "/directory/employee-documents",
            json={
                "employee_id": emp_id,
                "document_type_id": seminar_type_id,
                "valid_until": (date.today() + timedelta(days=30)).isoformat(),
            },
            headers=privileged_headers,
        )
        assert seminar_with_expiry.status_code == 422

        draft = client.post(
            "/directory/employee-documents",
            json={
                "employee_id": emp_id,
                "document_type_id": seminar_type_id,
                "lifecycle_status": "DRAFT",
            },
            headers=privileged_headers,
        )
        assert draft.status_code == 422
    finally:
        _cleanup_documents_for_employees(emp_ids)
        _cleanup_employees(emp_ids, pos_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_filters_and_inactive_employee_visibility(client, seed, privileged_headers):
    active_id, active_emp_ids, active_pos_ids = _make_employee(seed, is_active=True)
    inactive_id, inactive_emp_ids, inactive_pos_ids = _make_employee(seed, is_active=False)
    emp_ids = active_emp_ids + inactive_emp_ids
    pos_ids = active_pos_ids + inactive_pos_ids
    document_ids: List[int] = []

    try:
        with engine.begin() as conn:
            seminar_type_id = _lookup_document_type_id(conn, "SEMINAR_PARTICIPATION")
            doctor_group_id = _lookup_group_id(conn, "DOCTOR")

        for emp, suffix in ((active_id, "active"), (inactive_id, "inactive")):
            resp = client.post(
                "/directory/employee-documents",
                json={
                    "employee_id": emp,
                    "document_type_id": seminar_type_id,
                    "title": f"Seminar {suffix} {uuid4().hex[:4]}",
                    "document_number": f"SEM-{suffix}-{uuid4().hex[:4]}",
                    "issued_at": date.today().isoformat(),
                    "hours": 16,
                },
                headers=privileged_headers,
            )
            assert resp.status_code == 201, resp.text
            document_ids.append(int(resp.json()["document_id"]))

        all_list = client.get("/directory/employee-documents", headers=privileged_headers)
        assert all_list.status_code == 200
        listed_ids = {item["document_id"] for item in all_list.json()["items"]}
        assert set(document_ids).issubset(listed_ids)

        active_only = client.get(
            "/directory/employee-documents",
            params={"employee_is_active": "true"},
            headers=privileged_headers,
        )
        assert active_only.status_code == 200
        active_only_ids = {item["document_id"] for item in active_only.json()["items"]}
        assert document_ids[0] in active_only_ids
        assert document_ids[1] not in active_only_ids

        search = client.get(
            "/directory/employee-documents",
            params={"q": "Seminar inactive"},
            headers=privileged_headers,
        )
        assert search.status_code == 200
        assert search.json()["total"] >= 1

        expired_filter = client.get(
            "/directory/employee-documents",
            params={"expiry_status": "NO_EXPIRY"},
            headers=privileged_headers,
        )
        assert expired_filter.status_code == 200
        for item in expired_filter.json()["items"]:
            if item["document_id"] in document_ids:
                assert item["expiry_status"] == "NO_EXPIRY"

        group_filter = client.get(
            "/directory/employee-documents",
            params={"group_id": doctor_group_id},
            headers=privileged_headers,
        )
        assert group_filter.status_code == 200
        for item in group_filter.json()["items"]:
            if item["document_id"] in document_ids:
                pytest.fail("Seminar without specialty should not match doctor group filter")
    finally:
        _cleanup_documents(document_ids)
        _cleanup_employees(emp_ids, pos_ids)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_get_single_document(client, seed, privileged_headers):
    emp_id, emp_ids, pos_ids = _make_employee(seed)
    document_ids: List[int] = []
    try:
        with engine.begin() as conn:
            seminar_type_id = _lookup_document_type_id(conn, "SEMINAR_PARTICIPATION")

        create = client.post(
            "/directory/employee-documents",
            json={
                "employee_id": emp_id,
                "document_type_id": seminar_type_id,
                "title": "Single doc",
                "issued_at": date.today().isoformat(),
                "hours": 8,
            },
            headers=privileged_headers,
        )
        assert create.status_code == 201
        doc_id = int(create.json()["document_id"])
        document_ids.append(doc_id)

        get_one = client.get(
            f"/directory/employee-documents/{doc_id}",
            headers=privileged_headers,
        )
        assert get_one.status_code == 200
        assert get_one.json()["document_id"] == doc_id
        assert get_one.json()["title"] == "Single doc"
    finally:
        _cleanup_documents(document_ids)
        _cleanup_employees(emp_ids, pos_ids)
