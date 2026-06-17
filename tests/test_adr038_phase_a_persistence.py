"""ADR-038 Phase A — employee-level overrides survive repeated imports."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.department_recoding_service import seed_department_recoding
from app.services.employee_import_profile_override_service import (
    employee_overrides_available,
    load_employee_override,
)
from app.services.hr_import_employee_card_service import get_employee_import_card, save_employee_import_card
from app.services.hr_import_profile_override_service import apply_profile_override
from app.services.hr_import_service import import_control_list
from tests.conftest import get_columns, insert_returning_id
from tests.test_import_hr_control_list import _build_sample_workbook


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_phase_a() -> None:
    with engine.connect() as conn:
        if not employee_overrides_available(conn):
            pytest.skip("employee_import_profile_overrides not available — run alembic upgrade head")


def _create_employee(conn, *, full_name: str, org_unit_id: int) -> int:
    cols = get_columns(conn, "employees")
    values = {"full_name": full_name}
    if "org_unit_id" in cols:
        values["org_unit_id"] = org_unit_id
    if "is_active" in cols:
        values["is_active"] = True
    return insert_returning_id(conn, table="employees", id_col="employee_id", values=values)


@pytest.fixture
def two_import_batches(seed, tmp_path: Path):
    _require_phase_a()
    source1 = tmp_path / f"phase_a_1_{uuid4().hex[:8]}.xlsx"
    source2 = tmp_path / f"phase_a_2_{uuid4().hex[:8]}.xlsx"
    _build_sample_workbook(source1)
    _build_sample_workbook(source2)
    employee_id: int | None = None
    batch_ids: list[int] = []
    with engine.begin() as conn:
        seed_department_recoding(conn)
        batch_id_1, _, _ = import_control_list(
            conn,
            file_path=source1,
            imported_by=int(seed["initiator_user_id"]),
        )
        batch_ids.append(int(batch_id_1))
        employee_id = _create_employee(
            conn,
            full_name="Иванов Иван Иванович",
            org_unit_id=int(seed["unit_id"]),
        )
        batch_id_2, _, _ = import_control_list(
            conn,
            file_path=source2,
            imported_by=int(seed["initiator_user_id"]),
        )
        batch_ids.append(int(batch_id_2))
    assert employee_id is not None
    yield {"employee_id": employee_id, "batch_ids": batch_ids}
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.employee_import_profile_overrides WHERE employee_id = :employee_id"),
            {"employee_id": employee_id},
        )
        for batch_id in batch_ids:
            conn.execute(
                text("DELETE FROM public.hr_import_batches WHERE batch_id = :batch_id"),
                {"batch_id": batch_id},
            )
        conn.execute(
            text("DELETE FROM public.employees WHERE employee_id = :employee_id"),
            {"employee_id": employee_id},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_manual_override_survives_second_import(two_import_batches):
    employee_id = two_import_batches["employee_id"]
    batch_id_2 = two_import_batches["batch_ids"][1]

    with engine.begin() as conn:
        detail = get_employee_import_card(conn, employee_id)
        edited = apply_profile_override(
            detail["profile"],
            {
                "notes": "ручная правка кадровика",
                "training": [{"title": "PK-2024", "organization": "Org", "year": "2024", "hours": 36}],
            },
        )
        save_employee_import_card(conn, employee_id, profile=edited)

    with engine.connect() as conn:
        stored = load_employee_override(conn, employee_id)
        card = get_employee_import_card(conn, employee_id)

    assert stored is not None
    assert stored["profile_override"]["notes"] == "ручная правка кадровика"
    assert card["batch_id"] == batch_id_2
    assert card["profile"]["notes_raw"] == "ручная правка кадровика"
    assert card["profile"]["training_records"][0]["title"] == "PK-2024"
    assert card["has_override"] is True


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_save_writes_employee_table_not_import_row(two_import_batches):
    employee_id = two_import_batches["employee_id"]

    with engine.begin() as conn:
        detail = get_employee_import_card(conn, employee_id)
        save_employee_import_card(
            conn,
            employee_id,
            profile=apply_profile_override(detail["profile"], {"notes": "only employee table"}),
        )
        row_override = conn.execute(
            text(
                """
                SELECT profile_override
                FROM public.hr_import_rows
                WHERE batch_id = :batch_id AND row_id = :row_id
                """
            ),
            {"batch_id": detail["batch_id"], "row_id": detail["row_id"]},
        ).scalar_one()
        employee_override = load_employee_override(conn, employee_id)

    assert row_override is None
    assert employee_override is not None
    assert employee_override["profile_override"]["notes"] == "only employee table"
