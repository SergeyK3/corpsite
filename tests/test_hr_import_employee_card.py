"""Tests for employee import card (Карта2) lookup from HR staging."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.services.department_recoding_service import seed_department_recoding
from app.services.hr_import_employee_card_service import (
    EmployeeImportCardNotFoundError,
    get_employee_import_card,
)
from app.services.hr_import_service import import_control_list
from tests.conftest import auth_headers, get_columns, insert_returning_id, table_exists
from tests.test_import_hr_control_list import _build_sample_workbook


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _profile_staging_available() -> bool:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'hr_import_rows'
                  AND column_name = 'profile_override'
                """
            )
        ).first()
        return row is not None


def _require_profile_staging() -> None:
    if not _profile_staging_available():
        pytest.skip("profile staging columns not available — run alembic upgrade head")


def _create_employee(conn, *, full_name: str, org_unit_id: int) -> int:
    cols = get_columns(conn, "employees")
    values = {"full_name": full_name}
    if "org_unit_id" in cols:
        values["org_unit_id"] = org_unit_id
    if "is_active" in cols:
        values["is_active"] = True
    return insert_returning_id(conn, table="employees", id_col="employee_id", values=values)


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def staged_batch_with_employee(seed, tmp_path: Path):
    _require_profile_staging()
    source = tmp_path / f"card2_{uuid4().hex[:8]}.xlsx"
    _build_sample_workbook(source)
    employee_id: int | None = None
    batch_id: int | None = None
    with engine.begin() as conn:
        seed_department_recoding(conn)
        batch_id, _, _ = import_control_list(
            conn,
            file_path=source,
            imported_by=int(seed["initiator_user_id"]),
        )
        employee_id = _create_employee(
            conn,
            full_name="Иванов Иван Иванович",
            org_unit_id=int(seed["unit_id"]),
        )
    assert batch_id is not None
    assert employee_id is not None
    yield {"batch_id": batch_id, "employee_id": employee_id}
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.hr_import_batches WHERE batch_id = :batch_id"),
            {"batch_id": batch_id},
        )
        conn.execute(
            text("DELETE FROM public.employees WHERE employee_id = :employee_id"),
            {"employee_id": employee_id},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_import_card_found_by_employee_full_name_without_iin(staged_batch_with_employee):
    employee_id = staged_batch_with_employee["employee_id"]
    with engine.connect() as conn:
        card = get_employee_import_card(conn, employee_id)
    assert card["employee_id"] == employee_id
    assert card["full_name"] == "Иванов Иван Иванович"
    assert card["profile"]["basic"]["iin"] == "900101300123"
    assert card["batch_id"] == staged_batch_with_employee["batch_id"]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_import_card_api_returns_profile(staged_batch_with_employee, privileged_headers):
    employee_id = staged_batch_with_employee["employee_id"]
    client = TestClient(app)
    res = client.get(
        f"/directory/personnel/employees/{employee_id}/import-card",
        headers=privileged_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["full_name"] == "Иванов Иван Иванович"
    assert body["profile"]["basic"]["position_raw"] == "Директор"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_import_card_not_found_for_unknown_employee(seed):
    _require_profile_staging()
    with engine.begin() as conn:
        employee_id = _create_employee(
            conn,
            full_name="Нет В Импорте Сотрудник",
            org_unit_id=int(seed["unit_id"]),
        )
    try:
        with engine.connect() as conn:
            with pytest.raises(EmployeeImportCardNotFoundError):
                get_employee_import_card(conn, employee_id)
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public.employees WHERE employee_id = :employee_id"),
                {"employee_id": employee_id},
            )
