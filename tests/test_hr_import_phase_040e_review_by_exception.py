"""Tests for ADR-040 Phase E — review by exception (hide UNCHANGED by default)."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from openpyxl import Workbook
from sqlalchemy import text

from app.db.engine import engine
from app.services.hr_import_analytics_service import list_batch_rows
from app.services.hr_import_monthly_diff_service import (
    DIFF_STATUS_CHANGED,
    DIFF_STATUS_UNCHANGED,
    build_review_visibility,
    compute_batch_monthly_diff,
    get_batch_diff_summary,
    monthly_diff_available,
)
from app.services.hr_import_normalized_record_service import (
    list_review_normalized_records,
    normalized_records_available,
)
from app.services.hr_import_roster_promotion_service import promote_roster_batch
from tests.test_hr_import_phase_040b_monthly_diff import (
    _import_prepared_batch,
    _require_phase_040b,
    _unique_iin,
)
from tests.test_hr_import_phase_040a_canonical_snapshot import (
    _cleanup_promotion_batch,
    _cyrillic_full_name,
)


def _require_phase_040e() -> None:
    _require_phase_040b()


def test_build_review_visibility_all_unchanged() -> None:
    visibility = build_review_visibility({DIFF_STATUS_UNCHANGED: 1847})
    assert visibility["visible_records"] == 0
    assert visibility["hidden_unchanged"] == 1847
    assert visibility["no_changes_detected"] is True
    assert visibility["review_complete"] is True


def test_build_review_visibility_mixed_counts() -> None:
    visibility = build_review_visibility(
        {
            DIFF_STATUS_UNCHANGED: 100,
            DIFF_STATUS_CHANGED: 4,
            "NEW": 12,
            "REMOVED": 2,
            "CONFLICT": 1,
        }
    )
    assert visibility["visible_records"] == 19
    assert visibility["hidden_unchanged"] == 100
    assert visibility["no_changes_detected"] is False


def test_repeat_import_review_list_empty_when_hide_unchanged(seed, tmp_path: Path) -> None:
    _require_phase_040e()
    suffix = uuid4().hex[:8]
    full_name = _cyrillic_full_name(f"Exc{suffix}")
    iin = _unique_iin(f"1{suffix}")
    department = f"Pytest Dept {suffix}"
    batch_id_1 = _import_prepared_batch(
        seed,
        tmp_path,
        full_name=full_name,
        iin=iin,
        department=department,
        position="Врач терапевт",
    )
    batch_id_2 = _import_prepared_batch(
        seed,
        tmp_path,
        full_name=full_name,
        iin=iin,
        department=department,
        position="Врач терапевт",
    )
    try:
        with engine.begin() as conn:
            promote_roster_batch(
                conn,
                batch_id_1,
                created_by=int(seed["initiator_user_id"]),
                dry_run=False,
            )
            compute_batch_monthly_diff(conn, batch_id_2)
            diff_summary = get_batch_diff_summary(conn, batch_id_2)
            assert diff_summary["summary"].get(DIFF_STATUS_UNCHANGED, 0) >= 1
            assert diff_summary["review_visibility"]["hidden_unchanged"] >= 1

            visible_rows = list_batch_rows(conn, batch_id_2, hide_unchanged=True, limit=500)
            assert visible_rows["total"] == 0
            assert visible_rows["items"] == []
            assert visible_rows["hide_unchanged"] is True

            all_rows = list_batch_rows(conn, batch_id_2, hide_unchanged=False, limit=500)
            assert all_rows["total"] >= 1
            assert all_rows["items"][0]["diff_status"] == DIFF_STATUS_UNCHANGED

            if diff_summary["review_visibility"]["visible_records"] == 0:
                assert diff_summary["review_visibility"]["no_changes_detected"] is True
    finally:
        with engine.begin() as conn:
            _cleanup_promotion_batch(conn, batch_id_1)
            _cleanup_promotion_batch(conn, batch_id_2)


def test_changed_row_visible_when_hide_unchanged(seed, tmp_path: Path) -> None:
    _require_phase_040e()
    suffix = uuid4().hex[:8]
    full_name = _cyrillic_full_name(f"Vis{suffix}")
    iin = _unique_iin(f"1{suffix}")
    department = f"Pytest Dept {suffix}"
    batch_id_1 = _import_prepared_batch(
        seed,
        tmp_path,
        full_name=full_name,
        iin=iin,
        department=department,
        position="Медицинский техник",
    )
    batch_id_2 = _import_prepared_batch(
        seed,
        tmp_path,
        full_name=full_name,
        iin=iin,
        department=department,
        position="Инженер по медицинскому оборудованию",
    )
    try:
        with engine.begin() as conn:
            promote_roster_batch(
                conn,
                batch_id_1,
                created_by=int(seed["initiator_user_id"]),
                dry_run=False,
            )
            compute_batch_monthly_diff(conn, batch_id_2)
            visible_rows = list_batch_rows(conn, batch_id_2, hide_unchanged=True, limit=500)
            assert visible_rows["total"] >= 1
            assert visible_rows["items"][0]["diff_status"] == DIFF_STATUS_CHANGED
    finally:
        with engine.begin() as conn:
            _cleanup_promotion_batch(conn, batch_id_1)
            _cleanup_promotion_batch(conn, batch_id_2)


def test_normalized_records_hide_unchanged(seed, tmp_path: Path) -> None:
    _require_phase_040e()
    with engine.begin() as conn:
        if not normalized_records_available(conn):
            pytest.skip("normalized records unavailable")
    suffix = uuid4().hex[:8]
    full_name = _cyrillic_full_name(f"Norm{suffix}")
    iin = _unique_iin(f"1{suffix}")
    department = f"Pytest Dept {suffix}"
    batch_id_1 = _import_prepared_batch(
        seed,
        tmp_path,
        full_name=full_name,
        iin=iin,
        department=department,
    )
    batch_id_2 = _import_prepared_batch(
        seed,
        tmp_path,
        full_name=full_name,
        iin=iin,
        department=department,
    )
    try:
        with engine.begin() as conn:
            promote_roster_batch(
                conn,
                batch_id_1,
                created_by=int(seed["initiator_user_id"]),
                dry_run=False,
            )
            compute_batch_monthly_diff(conn, batch_id_2)
            conn.execute(
                text(
                    """
                    UPDATE public.hr_import_normalized_records
                    SET diff_status = :unchanged
                    WHERE batch_id = :batch_id
                      AND diff_status IS NOT NULL
                    """
                ),
                {"batch_id": batch_id_2, "unchanged": DIFF_STATUS_UNCHANGED},
            )
            hidden = list_review_normalized_records(
                conn,
                batch_id=batch_id_2,
                hide_unchanged=True,
                limit=500,
            )
            all_records = list_review_normalized_records(
                conn,
                batch_id=batch_id_2,
                hide_unchanged=False,
                limit=500,
            )
            if all_records["total"] == 0:
                pytest.skip("batch has no normalized records to filter")
            assert hidden["total"] == 0
            assert all_records["total"] >= 1
    finally:
        with engine.begin() as conn:
            _cleanup_promotion_batch(conn, batch_id_1)
            _cleanup_promotion_batch(conn, batch_id_2)
