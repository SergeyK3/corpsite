"""Tests for ADR-059 Phase 2 import review exception diff viewer."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.hr_import_monthly_diff_service import (
    DIFF_STATUS_CHANGED,
    DIFF_STATUS_CONFLICT,
    DIFF_STATUS_NEW,
    DIFF_STATUS_UNCHANGED,
    compute_batch_monthly_diff,
)
from app.services.hr_import_review_exception_detail_service import (
    build_exception_key,
    get_review_exception_detail,
    list_review_exceptions,
    resolve_review_exception,
)
from tests.conftest import table_exists
from tests.test_hr_import_complete_review import staged_batch  # noqa: F401
from tests.test_hr_import_phase_040b_monthly_diff import _require_phase_040b


@pytest.mark.skipif(not table_exists(engine.connect(), "hr_import_batches"), reason="no import schema")
def test_review_exception_detail_for_changed_row(staged_batch) -> None:
    _require_phase_040b()
    batch_id = staged_batch["batch_id"]

    with engine.begin() as conn:
        compute_batch_monthly_diff(conn, batch_id)
        row = conn.execute(
            text(
                """
                SELECT row_id, diff_status
                FROM public.hr_import_rows
                WHERE batch_id = :batch_id
                  AND diff_status = :changed
                LIMIT 1
                """
            ),
            {"batch_id": batch_id, "changed": DIFF_STATUS_CHANGED},
        ).mappings().first()
        if row is None:
            conn.execute(
                text(
                    """
                    UPDATE public.hr_import_rows
                    SET diff_status = :changed,
                        field_diffs = CAST(:field_diffs AS JSONB)
                    WHERE batch_id = :batch_id
                      AND row_id = (
                          SELECT row_id
                          FROM public.hr_import_rows
                          WHERE batch_id = :batch_id
                          ORDER BY row_id
                          LIMIT 1
                      )
                    """
                ),
                {
                    "batch_id": batch_id,
                    "changed": DIFF_STATUS_CHANGED,
                    "field_diffs": '{"position_raw": {"canonical": "Old", "incoming": "New"}}',
                },
            )
            row = conn.execute(
                text(
                    """
                    SELECT row_id, diff_status
                    FROM public.hr_import_rows
                    WHERE batch_id = :batch_id
                      AND diff_status = :changed
                    LIMIT 1
                    """
                ),
                {"batch_id": batch_id, "changed": DIFF_STATUS_CHANGED},
            ).mappings().one()

        exception_key = build_exception_key(entity_type="row", entity_id=int(row["row_id"]))
        detail = get_review_exception_detail(conn, batch_id, exception_key)

    assert detail["exception_key"] == exception_key
    assert detail["baseline"]["source_label"] == "Canonical Baseline"
    assert detail["import_data"]["source_label"] == "Current Import"
    assert detail["actions_available"] is True
    assert len(detail["baseline"]["fields"]) > 0
    assert len(detail["import_data"]["fields"]) == len(detail["baseline"]["fields"])
    assert any(field["changed"] for field in detail["diff"]["fields"])


@pytest.mark.skipif(not table_exists(engine.connect(), "hr_import_batches"), reason="no import schema")
def test_resolve_review_exception_clears_staging_exception(staged_batch, seed) -> None:
    _require_phase_040b()
    batch_id = staged_batch["batch_id"]
    actor = int(seed["initiator_user_id"])

    with engine.begin() as conn:
        compute_batch_monthly_diff(conn, batch_id)
        conn.execute(
            text(
                """
                UPDATE public.hr_import_rows
                SET diff_status = :conflict,
                    field_diffs = CAST(:field_diffs AS JSONB)
                WHERE batch_id = :batch_id
                  AND row_id = (
                      SELECT row_id
                      FROM public.hr_import_rows
                      WHERE batch_id = :batch_id
                      ORDER BY row_id
                      LIMIT 1
                  )
                """
            ),
            {
                "batch_id": batch_id,
                "conflict": DIFF_STATUS_CONFLICT,
                "field_diffs": '{"full_name": {"canonical": "A", "incoming": "B"}}',
            },
        )
        row_id = conn.execute(
            text(
                """
                SELECT row_id
                FROM public.hr_import_rows
                WHERE batch_id = :batch_id
                  AND diff_status = :conflict
                LIMIT 1
                """
            ),
            {"batch_id": batch_id, "conflict": DIFF_STATUS_CONFLICT},
        ).scalar_one()
        exception_key = build_exception_key(entity_type="row", entity_id=int(row_id))
        before = list_review_exceptions(conn, batch_id)
        resolve_review_exception(
            conn,
            batch_id,
            exception_key,
            resolution="keep_baseline",
            actor_user_id=actor,
        )
        after = list_review_exceptions(conn, batch_id)
        status = conn.execute(
            text(
                """
                SELECT diff_status
                FROM public.hr_import_rows
                WHERE batch_id = :batch_id
                  AND row_id = :row_id
                """
            ),
            {"batch_id": batch_id, "row_id": row_id},
        ).scalar_one()

    assert any(item["exception_key"] == exception_key for item in before["items"])
    assert not any(item["exception_key"] == exception_key for item in after["items"])
    assert status == DIFF_STATUS_UNCHANGED


@pytest.mark.skipif(not table_exists(engine.connect(), "hr_import_batches"), reason="no import schema")
def test_new_row_exception_listed_without_employee(staged_batch) -> None:
    _require_phase_040b()
    batch_id = staged_batch["batch_id"]

    with engine.begin() as conn:
        compute_batch_monthly_diff(conn, batch_id)
        conn.execute(
            text(
                """
                UPDATE public.hr_import_rows
                SET diff_status = :new_status,
                    employee_id = NULL,
                    field_diffs = NULL
                WHERE batch_id = :batch_id
                  AND row_id = (
                      SELECT row_id
                      FROM public.hr_import_rows
                      WHERE batch_id = :batch_id
                      ORDER BY row_id
                      LIMIT 1
                  )
                """
            ),
            {"batch_id": batch_id, "new_status": DIFF_STATUS_NEW},
        )
        items = list_review_exceptions(conn, batch_id)["items"]

    assert any(item["diff_status"] == DIFF_STATUS_NEW for item in items)
