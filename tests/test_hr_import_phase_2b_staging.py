"""Service tests for ADR-038 Phase 2B (parse → staging)."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.hr_import import (
    BATCH_STATUS_IN_REVIEW,
    BATCH_STATUS_UPLOADED,
    CLASSIFICATION_DUPLICATE_IIN,
    CLASSIFICATION_INVALID_IIN,
    MATCH_STATUS_NOT_PROCESSED,
    SOURCE_TYPE_HR_CONTROL_LIST,
)
from app.services.hr_import_service import (
    BATCH_STATUS_CREATED,
    BATCH_STATUS_REVIEW_READY,
    classify_row,
    create_batch,
    import_control_list,
    summarize_batch,
)
from scripts.import_hr_control_list import ParsedRow, build_audit, parse_workbook
from tests.conftest import table_exists
from tests.test_import_hr_control_list import _build_sample_workbook


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _phase_2a_available() -> bool:
    with engine.begin() as conn:
        return all(
            table_exists(conn, table)
            for table in (
                "hr_import_batches",
                "hr_import_rows",
            )
        )


def _phase_2b_available() -> bool:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'chk_hr_import_rows_match_status'
                  AND pg_get_constraintdef(oid) LIKE '%NOT_PROCESSED%'
                LIMIT 1
                """
            )
        ).first()
        return row is not None


def _require_phase_2b() -> None:
    if not _phase_2a_available():
        pytest.skip("Phase 2A tables missing — run: alembic upgrade head")
    if not _phase_2b_available():
        pytest.skip("Phase 2B migration missing — run: alembic upgrade head (d3e4f5a6b7c8)")


def _delete_batch(conn, batch_id: int) -> None:
    conn.execute(
        text("DELETE FROM public.hr_import_batches WHERE batch_id = :batch_id"),
        {"batch_id": batch_id},
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_create_import_batch(seed):
    _require_phase_2b()

    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        batch_id = create_batch(
            conn,
            source_type=SOURCE_TYPE_HR_CONTROL_LIST,
            file_name=f"pytest_{suffix}.xlsx",
            imported_by=int(seed["initiator_user_id"]),
        )
        batch = conn.execute(
            text(
                """
                SELECT source_type, file_name, imported_by, status,
                       total_rows, valid_rows, error_rows
                FROM public.hr_import_batches
                WHERE batch_id = :batch_id
                """
            ),
            {"batch_id": batch_id},
        ).mappings().one()

    assert batch_id > 0
    assert batch["source_type"] == SOURCE_TYPE_HR_CONTROL_LIST
    assert batch["file_name"] == f"pytest_{suffix}.xlsx"
    assert int(batch["imported_by"]) == int(seed["initiator_user_id"])
    assert batch["status"] == BATCH_STATUS_CREATED == BATCH_STATUS_UPLOADED
    assert batch["total_rows"] == 0
    assert batch["valid_rows"] == 0
    assert batch["error_rows"] == 0

    with engine.begin() as conn:
        _delete_batch(conn, batch_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_stage_rows(seed, tmp_path: Path):
    _require_phase_2b()

    source = tmp_path / "control.xlsx"
    _build_sample_workbook(source)

    with engine.begin() as conn:
        batch_id, summary, warnings = import_control_list(
            conn,
            file_path=source,
            imported_by=int(seed["initiator_user_id"]),
        )
        batch = conn.execute(
            text(
                """
                SELECT status, total_rows, valid_rows, error_rows
                FROM public.hr_import_batches
                WHERE batch_id = :batch_id
                """
            ),
            {"batch_id": batch_id},
        ).mappings().one()
        row_count = conn.execute(
            text("SELECT COUNT(*) FROM public.hr_import_rows WHERE batch_id = :batch_id"),
            {"batch_id": batch_id},
        ).scalar_one()
        sample_row = conn.execute(
            text(
                """
                SELECT source_sheet, source_row_number, raw_payload, normalized_payload,
                       match_status, review_status, error_codes
                FROM public.hr_import_rows
                WHERE batch_id = :batch_id
                ORDER BY row_id
                LIMIT 1
                """
            ),
            {"batch_id": batch_id},
        ).mappings().one()

    assert batch_id > 0
    assert batch["status"] == BATCH_STATUS_REVIEW_READY == BATCH_STATUS_IN_REVIEW
    assert row_count == summary["total_rows"]
    assert batch["total_rows"] == summary["total_rows"]
    assert sample_row["match_status"] == MATCH_STATUS_NOT_PROCESSED
    assert sample_row["review_status"] == "PENDING"
    assert "metadata" in sample_row["normalized_payload"]
    assert "classification" in sample_row["normalized_payload"]["metadata"]
    assert isinstance(sample_row["raw_payload"], dict)
    assert any(w.startswith("skip_unknown_sheet:") for w in warnings)

    with engine.begin() as conn:
        _delete_batch(conn, batch_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_batch_summary(seed, tmp_path: Path):
    _require_phase_2b()

    source = tmp_path / "control.xlsx"
    _build_sample_workbook(source)

    rows, _ = parse_workbook(source)
    expected = build_audit(rows)
    expected_summary = {
        "total_rows": expected["total_rows"],
        "valid_iin": expected["valid_iin"],
        "invalid_iin": expected["invalid_iin"],
        "duplicate_iin_groups": expected["duplicate_iin"],
        "duplicate_iin_rows": expected["duplicate_iin_rows"],
        "missing_full_name": expected["missing_full_name"],
        "missing_department": expected["missing_department"],
        "with_training": expected["with_training"],
        "with_certification": expected["with_certification"],
    }

    with engine.begin() as conn:
        batch_id, summary, _ = import_control_list(
            conn,
            file_path=source,
            imported_by=int(seed["initiator_user_id"]),
        )
        persisted = summarize_batch(conn, batch_id)

    assert summary == expected_summary
    assert persisted == expected_summary

    with engine.begin() as conn:
        _delete_batch(conn, batch_id)


def test_duplicate_iin_classification():
    row_a = ParsedRow(
        data={"full_name": "A", "department": "D", "source_sheet": "s", "source_row_number": "1", "iin": "900101300123"},
        sheet_type="doctors",
        iin_valid=True,
        iin_digits="900101300123",
        errors=[],
    )
    row_b = ParsedRow(
        data={"full_name": "B", "department": "D", "source_sheet": "s", "source_row_number": "2", "iin": "900101300123"},
        sheet_type="doctors",
        iin_valid=True,
        iin_digits="900101300123",
        errors=[],
    )
    duplicate_iins = {"900101300123"}

    assert classify_row(row_a, duplicate_iins) == CLASSIFICATION_DUPLICATE_IIN
    assert classify_row(row_b, duplicate_iins) == CLASSIFICATION_DUPLICATE_IIN


def test_invalid_iin_classification():
    row = ParsedRow(
        data={"full_name": "Test", "department": "D", "source_sheet": "s", "source_row_number": "3", "iin": "12345"},
        sheet_type="doctors",
        iin_valid=False,
        iin_digits="12345",
        errors=["invalid_iin_length:5"],
    )

    assert classify_row(row, set()) == CLASSIFICATION_INVALID_IIN


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_duplicate_iin_classification_persisted(seed, tmp_path: Path):
    _require_phase_2b()

    source = tmp_path / "dup.xlsx"
    _build_sample_workbook(source)

    with engine.begin() as conn:
        batch_id, _, _ = import_control_list(
            conn,
            file_path=source,
            imported_by=int(seed["initiator_user_id"]),
        )
        dup_rows = conn.execute(
            text(
                """
                SELECT normalized_payload->'metadata'->>'classification' AS classification
                FROM public.hr_import_rows
                WHERE batch_id = :batch_id
                  AND normalized_payload->>'iin' = '900101300123'
                """
            ),
            {"batch_id": batch_id},
        ).scalars().all()

    assert len(dup_rows) >= 2
    assert all(item == CLASSIFICATION_DUPLICATE_IIN for item in dup_rows)

    with engine.begin() as conn:
        _delete_batch(conn, batch_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_invalid_iin_classification_persisted(seed, tmp_path: Path):
    _require_phase_2b()

    from datetime import datetime
    from openpyxl import Workbook

    path = tmp_path / "invalid_iin.xlsx"
    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet("врачи")
    for _ in range(6):
        ws.append([""] * 20)
    ws.append(
        [
            "№",
            "",
            "Фамилия, имя, отчество",
            "Год рождения",
            "ИИН",
            "пол",
        ]
        + [""] * 14
    )
    ws.append(
        [
            1,
            "ОТДЕЛ",
            "Невалидный ИИН",
            datetime(1990, 1, 1),
            "12345",
            "муж",
        ]
        + [""] * 14
    )
    wb.save(path)

    with engine.begin() as conn:
        batch_id, _, _ = import_control_list(
            conn,
            file_path=path,
            imported_by=int(seed["initiator_user_id"]),
        )
        classification = conn.execute(
            text(
                """
                SELECT normalized_payload->'metadata'->>'classification' AS classification
                FROM public.hr_import_rows
                WHERE batch_id = :batch_id
                LIMIT 1
                """
            ),
            {"batch_id": batch_id},
        ).scalar_one()

    assert classification == CLASSIFICATION_INVALID_IIN

    with engine.begin() as conn:
        _delete_batch(conn, batch_id)
