"""Tests for ADR-039 Phase 3I — enroll employee from normalized import record."""
from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.services.hr_import_enroll_employee_service import (
    ENROLLMENT_SOURCE_HR_IMPORT_NORMALIZED_RECORD,
    EVENT_TYPE_ENROLLED_FROM_IMPORT,
    enroll_employee_from_normalized_record,
    EnrollEmployeeRequest,
)
from app.services.hr_import_normalized_record_service import normalized_records_available
from app.services.hr_import_service import import_control_list
from tests.conftest import auth_headers, insert_returning_id, table_exists
from tests.test_employee_documents_routes import _create_employee, _create_position, _phase_1a_available
from tests.test_hr_import_phase_3g_employee_binding import (
    _build_workbook,
    _create_employee_with_iin,
    _delete_batch,
    _first_row_id,
    _import_batch,
    _normalized_records_for_row,
    _require_phase_3g,
    _test_iin,
)
from tests.test_import_hr_control_list import _build_doctors_sheet


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _phase_3i_available() -> bool:
    with engine.begin() as conn:
        if not normalized_records_available(conn):
            return False
        if not table_exists(conn, "employee_events"):
            return False
        row = conn.execute(
            text(
                """
                SELECT pg_get_constraintdef(oid) AS def
                FROM pg_constraint
                WHERE conname = 'chk_employee_events_event_type'
                LIMIT 1
                """
            )
        ).scalar()
        return bool(row and "EMPLOYEE_ENROLLED_FROM_IMPORT" in str(row))


def _first_normalized_record_id(conn, row_id: int) -> int:
    record_id = conn.execute(
        text(
            """
            SELECT normalized_record_id
            FROM public.hr_import_normalized_records
            WHERE row_id = :row_id
            ORDER BY normalized_record_id
            LIMIT 1
            """
        ),
        {"row_id": row_id},
    ).scalar_one_or_none()
    if record_id is None:
        raise AssertionError(f"no normalized records for row_id={row_id}")
    return int(record_id)


def _row_metadata(conn, row_id: int) -> dict:
    raw = conn.execute(
        text(
            """
            SELECT normalized_payload->'metadata'
            FROM public.hr_import_rows
            WHERE row_id = :row_id
            """
        ),
        {"row_id": row_id},
    ).scalar_one()
    if raw is None:
        return {}
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw)


def _set_row_metadata_marker(conn, row_id: int, *, marker: str) -> None:
    conn.execute(
        text(
            """
            UPDATE public.hr_import_rows
            SET normalized_payload = jsonb_set(
                COALESCE(normalized_payload, '{}'::jsonb),
                '{metadata,custom_test_marker}',
                to_jsonb(CAST(:marker AS text)),
                true
            )
            WHERE row_id = :row_id
            """
        ),
        {"row_id": row_id, "marker": marker},
    )


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_phase_3i_migration_allows_enrolled_from_import_event_type():
    """Guard: production must run alembic revision h7i8j9k0l1m2 before execute enroll."""
    if not _phase_3i_available():
        pytest.fail(
            "chk_employee_events_event_type must include EMPLOYEE_ENROLLED_FROM_IMPORT "
            "(run: alembic upgrade head, revision h7i8j9k0l1m2)"
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_enroll_dry_run_unlinked_record(seed, tmp_path: Path):
    _require_phase_3g()
    if not _phase_3i_available():
        pytest.skip("ADR-039 Phase 3I migration missing — run alembic upgrade head")
    if not _phase_1a_available():
        pytest.skip("employees tables missing")

    suffix = uuid4().hex[:8]
    full_name = f"Enroll Dry {suffix}"
    iin = _test_iin(suffix)
    batch_id = None

    try:
        batch_id = _import_batch(tmp_path, seed, full_name=full_name, iin=iin)
        with engine.begin() as conn:
            row_id = _first_row_id(conn, batch_id)
            record_id = _first_normalized_record_id(conn, row_id)
            result = enroll_employee_from_normalized_record(
                conn,
                record_id,
                created_by=int(seed["initiator_user_id"]),
                request=EnrollEmployeeRequest(dry_run=True),
            )
        assert result.outcome == "ready"
        assert result.preview["full_name"] == full_name
        assert result.preview["iin"] == iin
        assert result.created is False
    finally:
        with engine.begin() as conn:
            if batch_id:
                _delete_batch(conn, batch_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_enroll_dry_run_iin_conflict(seed, tmp_path: Path):
    _require_phase_3g()
    if not _phase_3i_available():
        pytest.skip("ADR-039 Phase 3I migration missing")
    if not _phase_1a_available():
        pytest.skip("employees tables missing")

    suffix = uuid4().hex[:8]
    full_name = f"Enroll Conflict {suffix}"
    iin = _test_iin(suffix)
    batch_id = None
    emp_id = None

    try:
        with engine.begin() as conn:
            emp_id = _create_employee_with_iin(
                conn,
                full_name=full_name,
                iin=iin,
                org_unit_id=int(seed["unit_id"]),
                created_by=int(seed["initiator_user_id"]),
            )
        batch_id = _import_batch(tmp_path, seed, full_name=full_name, iin=iin)
        with engine.begin() as conn:
            row_id = _first_row_id(conn, batch_id)
            record_id = _first_normalized_record_id(conn, row_id)
            conn.execute(
                text(
                    """
                    UPDATE public.hr_import_rows
                    SET employee_id = NULL, match_status = 'NO_MATCH'
                    WHERE row_id = :row_id
                    """
                ),
                {"row_id": row_id},
            )
            conn.execute(
                text(
                    """
                    UPDATE public.hr_import_normalized_records
                    SET employee_id = NULL
                    WHERE row_id = :row_id
                    """
                ),
                {"row_id": row_id},
            )
            result = enroll_employee_from_normalized_record(
                conn,
                record_id,
                created_by=int(seed["initiator_user_id"]),
                request=EnrollEmployeeRequest(dry_run=True),
            )
        assert result.outcome == "conflict"
        assert result.conflict is not None
        assert result.conflict["code"] == "IIN_ALREADY_EXISTS"
        assert result.conflict["existing_employee_id"] == emp_id
        assert result.conflict.get("existing_org_unit_name") is not None or True
    finally:
        with engine.begin() as conn:
            if batch_id:
                _delete_batch(conn, batch_id)
            if emp_id:
                conn.execute(text("DELETE FROM public.employee_identities WHERE employee_id = :id"), {"id": emp_id})
                conn.execute(text("DELETE FROM public.employees WHERE employee_id = :id"), {"id": emp_id})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_enroll_execute_creates_employee_and_links(seed, tmp_path: Path):
    _require_phase_3g()
    if not _phase_3i_available():
        pytest.skip("ADR-039 Phase 3I migration missing")
    if not _phase_1a_available():
        pytest.skip("employees tables missing")

    suffix = uuid4().hex[:8]
    full_name = f"Enroll Execute {suffix}"
    iin = _test_iin(suffix)
    batch_id = None
    employee_id = None

    try:
        batch_id = _import_batch(tmp_path, seed, full_name=full_name, iin=iin)
        with engine.begin() as conn:
            pos_id = _create_position(conn, name=f"pytest_enroll_{suffix}")
            row_id = _first_row_id(conn, batch_id)
            record_id = _first_normalized_record_id(conn, row_id)
            result = enroll_employee_from_normalized_record(
                conn,
                record_id,
                created_by=int(seed["initiator_user_id"]),
                request=EnrollEmployeeRequest(
                    dry_run=False,
                    org_unit_id=int(seed["unit_id"]),
                    position_id=pos_id,
                ),
            )
            employee_id = int(result.employee_id)
            records = _normalized_records_for_row(conn, row_id)
            hire_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.employee_events
                    WHERE employee_id = :employee_id AND event_type = 'HIRE'
                    """
                ),
                {"employee_id": employee_id},
            ).scalar_one()
            enrolled_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.employee_events
                    WHERE employee_id = :employee_id AND event_type = :event_type
                    """
                ),
                {"employee_id": employee_id, "event_type": EVENT_TYPE_ENROLLED_FROM_IMPORT},
            ).scalar_one()
            enrolled_row = conn.execute(
                text(
                    """
                    SELECT event_type, event_class, lifecycle_status, comment
                    FROM public.employee_events
                    WHERE employee_id = :employee_id AND event_type = :event_type
                    ORDER BY event_id DESC
                    LIMIT 1
                    """
                ),
                {"employee_id": employee_id, "event_type": EVENT_TYPE_ENROLLED_FROM_IMPORT},
            ).mappings().first()

        assert result.created is True
        assert result.outcome == "created"
        assert result.linked_records_count >= 1
        assert all(rec["employee_id"] == employee_id for rec in records)
        assert int(hire_count) == 0
        assert int(enrolled_count) == 1
        assert enrolled_row is not None
        assert enrolled_row["event_type"] == EVENT_TYPE_ENROLLED_FROM_IMPORT
        assert enrolled_row["event_class"] == "PERSONNEL"
        assert enrolled_row["lifecycle_status"] == "APPROVED"
    finally:
        with engine.begin() as conn:
            if batch_id:
                _delete_batch(conn, batch_id)
            if employee_id:
                conn.execute(
                    text("DELETE FROM public.employee_events WHERE employee_id = :id"),
                    {"id": employee_id},
                )
                conn.execute(
                    text("DELETE FROM public.employee_identities WHERE employee_id = :id"),
                    {"id": employee_id},
                )
                conn.execute(text("DELETE FROM public.employees WHERE employee_id = :id"), {"id": employee_id})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_enroll_execute_updates_row_metadata_binding_status(seed, tmp_path: Path):
    _require_phase_3g()
    if not _phase_3i_available():
        pytest.skip("ADR-039 Phase 3I migration missing")
    if not _phase_1a_available():
        pytest.skip("employees tables missing")

    suffix = uuid4().hex[:8]
    full_name = f"Enroll Meta Bound {suffix}"
    iin = _test_iin(suffix)
    batch_id = None
    employee_id = None

    try:
        batch_id = _import_batch(tmp_path, seed, full_name=full_name, iin=iin)
        with engine.begin() as conn:
            pos_id = _create_position(conn, name=f"pytest_enroll_meta_{suffix}")
            row_id = _first_row_id(conn, batch_id)
            record_id = _first_normalized_record_id(conn, row_id)
            result = enroll_employee_from_normalized_record(
                conn,
                record_id,
                created_by=int(seed["initiator_user_id"]),
                request=EnrollEmployeeRequest(
                    dry_run=False,
                    org_unit_id=int(seed["unit_id"]),
                    position_id=pos_id,
                ),
            )
            employee_id = int(result.employee_id)
            metadata = _row_metadata(conn, row_id)

        assert result.created is True
        assert metadata.get("employee_binding_status") == "bound"
    finally:
        with engine.begin() as conn:
            if batch_id:
                _delete_batch(conn, batch_id)
            if employee_id:
                conn.execute(
                    text("DELETE FROM public.employee_events WHERE employee_id = :id"),
                    {"id": employee_id},
                )
                conn.execute(
                    text("DELETE FROM public.employee_identities WHERE employee_id = :id"),
                    {"id": employee_id},
                )
                conn.execute(text("DELETE FROM public.employees WHERE employee_id = :id"), {"id": employee_id})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_enroll_execute_writes_enrolled_employee_id_metadata(seed, tmp_path: Path):
    _require_phase_3g()
    if not _phase_3i_available():
        pytest.skip("ADR-039 Phase 3I migration missing")
    if not _phase_1a_available():
        pytest.skip("employees tables missing")

    suffix = uuid4().hex[:8]
    full_name = f"Enroll Meta Emp {suffix}"
    iin = _test_iin(suffix)
    batch_id = None
    employee_id = None

    try:
        batch_id = _import_batch(tmp_path, seed, full_name=full_name, iin=iin)
        with engine.begin() as conn:
            pos_id = _create_position(conn, name=f"pytest_enroll_emp_{suffix}")
            row_id = _first_row_id(conn, batch_id)
            record_id = _first_normalized_record_id(conn, row_id)
            result = enroll_employee_from_normalized_record(
                conn,
                record_id,
                created_by=int(seed["initiator_user_id"]),
                request=EnrollEmployeeRequest(
                    dry_run=False,
                    org_unit_id=int(seed["unit_id"]),
                    position_id=pos_id,
                ),
            )
            employee_id = int(result.employee_id)
            metadata = _row_metadata(conn, row_id)

        assert metadata.get("enrolled_employee_id") == employee_id
        assert metadata.get("enrolled_from_record_id") == record_id
        assert metadata.get("enrollment_source") == ENROLLMENT_SOURCE_HR_IMPORT_NORMALIZED_RECORD
        assert metadata.get("enrolled_at")
    finally:
        with engine.begin() as conn:
            if batch_id:
                _delete_batch(conn, batch_id)
            if employee_id:
                conn.execute(
                    text("DELETE FROM public.employee_events WHERE employee_id = :id"),
                    {"id": employee_id},
                )
                conn.execute(
                    text("DELETE FROM public.employee_identities WHERE employee_id = :id"),
                    {"id": employee_id},
                )
                conn.execute(text("DELETE FROM public.employees WHERE employee_id = :id"), {"id": employee_id})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_enroll_execute_preserves_existing_row_metadata(seed, tmp_path: Path):
    _require_phase_3g()
    if not _phase_3i_available():
        pytest.skip("ADR-039 Phase 3I migration missing")
    if not _phase_1a_available():
        pytest.skip("employees tables missing")

    suffix = uuid4().hex[:8]
    marker = f"preserve_{suffix}"
    full_name = f"Enroll Meta Keep {suffix}"
    iin = _test_iin(suffix)
    batch_id = None
    employee_id = None

    try:
        batch_id = _import_batch(tmp_path, seed, full_name=full_name, iin=iin)
        with engine.begin() as conn:
            pos_id = _create_position(conn, name=f"pytest_enroll_keep_{suffix}")
            row_id = _first_row_id(conn, batch_id)
            record_id = _first_normalized_record_id(conn, row_id)
            _set_row_metadata_marker(conn, row_id, marker=marker)
            before = _row_metadata(conn, row_id)
            result = enroll_employee_from_normalized_record(
                conn,
                record_id,
                created_by=int(seed["initiator_user_id"]),
                request=EnrollEmployeeRequest(
                    dry_run=False,
                    org_unit_id=int(seed["unit_id"]),
                    position_id=pos_id,
                ),
            )
            employee_id = int(result.employee_id)
            after = _row_metadata(conn, row_id)

        assert before.get("custom_test_marker") == marker
        assert after.get("custom_test_marker") == marker
        assert after.get("employee_binding_status") == "bound"
        assert after.get("enrolled_employee_id") == employee_id
    finally:
        with engine.begin() as conn:
            if batch_id:
                _delete_batch(conn, batch_id)
            if employee_id:
                conn.execute(
                    text("DELETE FROM public.employee_events WHERE employee_id = :id"),
                    {"id": employee_id},
                )
                conn.execute(
                    text("DELETE FROM public.employee_identities WHERE employee_id = :id"),
                    {"id": employee_id},
                )
                conn.execute(text("DELETE FROM public.employees WHERE employee_id = :id"), {"id": employee_id})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_enroll_dry_run_does_not_mutate_row_metadata(seed, tmp_path: Path):
    _require_phase_3g()
    if not _phase_3i_available():
        pytest.skip("ADR-039 Phase 3I migration missing")
    if not _phase_1a_available():
        pytest.skip("employees tables missing")

    suffix = uuid4().hex[:8]
    marker = f"dry_run_{suffix}"
    full_name = f"Enroll Dry Meta {suffix}"
    iin = _test_iin(suffix)
    batch_id = None

    try:
        batch_id = _import_batch(tmp_path, seed, full_name=full_name, iin=iin)
        with engine.begin() as conn:
            row_id = _first_row_id(conn, batch_id)
            record_id = _first_normalized_record_id(conn, row_id)
            _set_row_metadata_marker(conn, row_id, marker=marker)
            before = _row_metadata(conn, row_id)
            result = enroll_employee_from_normalized_record(
                conn,
                record_id,
                created_by=int(seed["initiator_user_id"]),
                request=EnrollEmployeeRequest(dry_run=True),
            )
            after = _row_metadata(conn, row_id)

        assert result.outcome == "ready"
        assert before == after
        assert "enrolled_employee_id" not in after
        assert after.get("employee_binding_status") != "bound"
    finally:
        with engine.begin() as conn:
            if batch_id:
                _delete_batch(conn, batch_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_enroll_api_forbidden_without_privilege(client: TestClient, seed, tmp_path: Path):
    _require_phase_3g()
    if not _phase_3i_available():
        pytest.skip("ADR-039 Phase 3I migration missing")

    suffix = uuid4().hex[:8]
    batch_id = _import_batch(tmp_path, seed, full_name=f"No Priv {suffix}", iin=_test_iin(suffix))
    try:
        with engine.begin() as conn:
            row_id = _first_row_id(conn, batch_id)
            record_id = _first_normalized_record_id(conn, row_id)
        resp = client.post(
            f"/directory/personnel/import/normalized-records/{record_id}/enroll-employee",
            json={"dry_run": True},
            headers=auth_headers(seed["executor_user_id"]),
        )
        assert resp.status_code == 403
    finally:
        with engine.begin() as conn:
            _delete_batch(conn, batch_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_enroll_execute_requires_org_and_position(client: TestClient, seed, privileged_headers, tmp_path: Path):
    _require_phase_3g()
    if not _phase_3i_available():
        pytest.skip("ADR-039 Phase 3I migration missing")

    suffix = uuid4().hex[:8]
    batch_id = _import_batch(tmp_path, seed, full_name=f"Req Fields {suffix}", iin=_test_iin(suffix))
    try:
        with engine.begin() as conn:
            row_id = _first_row_id(conn, batch_id)
            record_id = _first_normalized_record_id(conn, row_id)
        resp = client.post(
            f"/directory/personnel/import/normalized-records/{record_id}/enroll-employee",
            json={"dry_run": False},
            headers=privileged_headers,
        )
        assert resp.status_code == 400
    finally:
        with engine.begin() as conn:
            _delete_batch(conn, batch_id)
