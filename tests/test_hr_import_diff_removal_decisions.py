"""Tests for diff removal decisions and auto-complete import review."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.hr_import import BATCH_STATUS_APPLY_PENDING, BATCH_STATUS_IN_REVIEW
from app.services.hr_import_complete_review_service import (
    assess_complete_import_review,
    maybe_auto_complete_import_review,
)
from app.services.hr_import_diff_removal_decision_service import (
    DECISION_CONFIRM_REMOVAL,
    DECISION_RESTORE,
    collect_mrd_forming_entries_from_batch,
    diff_removal_decisions_available,
    record_diff_removal_decision,
    revert_diff_removal_decision,
)
from app.services.hr_import_monthly_diff_service import compute_batch_monthly_diff, get_batch_diff_summary
from app.services.hr_import_service import import_control_list
from tests.conftest import table_exists
from tests.test_hr_import_complete_review import _approve_all_normalized
from tests.test_hr_import_phase_040a_canonical_snapshot import (
    _cleanup_promotion_batch,
    _ensure_roster_employee_metadata,
    _prepare_roster_row,
)
from tests.test_hr_import_phase_040b_monthly_diff import _require_phase_040b
from tests.test_hr_import_phase_040b_monthly_diff_business_scenarios import (
    _build_multi_row_workbook,
    _employee_spec,
    _promote_and_snapshot,
)
def _require_removal_decisions_schema() -> None:
    _require_phase_040b()
    with engine.begin() as conn:
        if not diff_removal_decisions_available(conn):
            pytest.skip("hr_import_diff_removals.decision column missing")


def _resolve_all_removals(conn, batch_id: int, *, actor_user_id: int) -> None:
    rows = conn.execute(
        text(
            """
            SELECT removal_id
            FROM public.hr_import_diff_removals
            WHERE batch_id = :batch_id
              AND decision IS NULL
            """
        ),
        {"batch_id": batch_id},
    ).scalars().all()
    for removal_id in rows:
        record_diff_removal_decision(
            conn,
            int(removal_id),
            decision=DECISION_CONFIRM_REMOVAL,
            decided_by=actor_user_id,
        )


def _promote_and_snapshot_ready(seed, batch_id: int) -> None:
    with engine.begin() as conn:
        _approve_all_normalized(conn, batch_id)
        _resolve_all_removals(conn, batch_id, actor_user_id=int(seed["initiator_user_id"]))
        maybe_auto_complete_import_review(
            conn,
            batch_id,
            actor_user_id=int(seed["initiator_user_id"]),
        )
    _promote_and_snapshot(seed, batch_id)


def _import_multi_employee_batch_named(
    seed,
    tmp_path: Path,
    *,
    rows: list[dict[str, str]],
    department: str,
    yymm: str,
) -> int:
    source = tmp_path / f"контрольный{yymm}.xlsx"
    _build_multi_row_workbook(source, rows)
    with engine.begin() as conn:
        batch_id, _, _ = import_control_list(
            conn,
            file_path=source,
            imported_by=int(seed["initiator_user_id"]),
        )
        db_rows = conn.execute(
            text(
                """
                SELECT row_id, normalized_payload->>'full_name' AS full_name
                FROM public.hr_import_rows
                WHERE batch_id = :batch_id
                ORDER BY row_id
                """
            ),
            {"batch_id": batch_id},
        ).mappings().all()
        for db_row in db_rows:
            full_name = str(db_row["full_name"] or "").strip()
            spec = next((row for row in rows if row["full_name"] == full_name), None)
            if spec is None:
                continue
            _prepare_roster_row(
                conn,
                batch_id=batch_id,
                row_id=int(db_row["row_id"]),
                full_name=spec["full_name"],
                iin=spec["iin"],
                department=department,
                org_unit_id=int(seed["unit_id"]),
            )
            _ensure_roster_employee_metadata(
                conn,
                batch_id=batch_id,
                row_id=int(db_row["row_id"]),
            )
    return int(batch_id)


@pytest.mark.skipif(not table_exists(engine.connect(), "hr_import_batches"), reason="no import schema")
def test_restore_decision_carries_entry_into_mrd_forming_entries(seed, tmp_path: Path) -> None:
    _require_removal_decisions_schema()
    suffix = uuid4().hex[:8]
    department = f"Pytest Dept {suffix}"
    keep = _employee_spec(label="Keep", suffix=suffix)
    removed = _employee_spec(label="Removed", suffix=suffix)

    batch_june = _import_multi_employee_batch_named(
        seed, tmp_path, rows=[keep, removed], department=department, yymm="2606"
    )
    batch_august = _import_multi_employee_batch_named(
        seed, tmp_path, rows=[keep], department=department, yymm="2608"
    )
    try:
        _promote_and_snapshot_ready(seed, batch_june)
        with engine.begin() as conn:
            compute_batch_monthly_diff(conn, batch_august)
            removal_id = conn.execute(
                text(
                    """
                    SELECT removal_id
                    FROM public.hr_import_diff_removals
                    WHERE batch_id = :batch_id
                    LIMIT 1
                    """
                ),
                {"batch_id": batch_august},
            ).scalar_one()
            record_diff_removal_decision(
                conn,
                int(removal_id),
                decision=DECISION_RESTORE,
                decided_by=int(seed["initiator_user_id"]),
            )
            _approve_all_normalized(conn, batch_august)
            match_keys = {
                str(row["match_key"])
                for row in collect_mrd_forming_entries_from_batch(conn, batch_august)
            }
            restored_match_key = conn.execute(
                text("SELECT match_key FROM public.hr_import_diff_removals WHERE removal_id = :removal_id"),
                {"removal_id": removal_id},
            ).scalar_one()
            assert str(restored_match_key) in match_keys
    finally:
        with engine.begin() as conn:
            _cleanup_promotion_batch(conn, batch_august)
            _cleanup_promotion_batch(conn, batch_june)


@pytest.mark.skipif(not table_exists(engine.connect(), "hr_import_batches"), reason="no import schema")
def test_pending_removals_block_auto_complete(seed, tmp_path: Path) -> None:
    _require_removal_decisions_schema()
    suffix = uuid4().hex[:8]
    department = f"Pytest Dept {suffix}"
    keep = _employee_spec(label="Keep", suffix=suffix)
    removed = _employee_spec(label="Removed", suffix=suffix)

    batch_june = _import_multi_employee_batch_named(
        seed, tmp_path, rows=[keep, removed], department=department, yymm="2606"
    )
    batch_august = _import_multi_employee_batch_named(
        seed, tmp_path, rows=[keep], department=department, yymm="2608"
    )
    try:
        _promote_and_snapshot_ready(seed, batch_june)
        with engine.begin() as conn:
            compute_batch_monthly_diff(conn, batch_august)
            _approve_all_normalized(conn, batch_august)
            import_code = conn.execute(
                text("SELECT import_code FROM public.hr_import_batches WHERE batch_id = :batch_id"),
                {"batch_id": batch_august},
            ).scalar_one()
            assessment = assess_complete_import_review(conn, str(import_code))
            assert assessment["complete_allowed"] is False
            assert any(item["code"] == "PENDING_REMOVED_DECISIONS" for item in assessment["blockers"])
    finally:
        with engine.begin() as conn:
            _cleanup_promotion_batch(conn, batch_august)
            _cleanup_promotion_batch(conn, batch_june)


@pytest.mark.skipif(not table_exists(engine.connect(), "hr_import_batches"), reason="no import schema")
def test_auto_complete_when_all_review_queues_cleared(seed, tmp_path: Path) -> None:
    _require_removal_decisions_schema()
    suffix = uuid4().hex[:8]
    department = f"Pytest Dept {suffix}"
    keep = _employee_spec(label="Keep", suffix=suffix)
    removed = _employee_spec(label="Removed", suffix=suffix)

    batch_june = _import_multi_employee_batch_named(
        seed, tmp_path, rows=[keep, removed], department=department, yymm="2606"
    )
    batch_august = _import_multi_employee_batch_named(
        seed, tmp_path, rows=[keep], department=department, yymm="2608"
    )
    try:
        _promote_and_snapshot_ready(seed, batch_june)
        with engine.begin() as conn:
            compute_batch_monthly_diff(conn, batch_august)
            _approve_all_normalized(conn, batch_august)
            _resolve_all_removals(conn, batch_august, actor_user_id=int(seed["initiator_user_id"]))
            result = maybe_auto_complete_import_review(
                conn,
                batch_august,
                actor_user_id=int(seed["initiator_user_id"]),
            )
            status = conn.execute(
                text("SELECT status FROM public.hr_import_batches WHERE batch_id = :batch_id"),
                {"batch_id": batch_august},
            ).scalar_one()
        assert result.get("auto_completed") or result.get("already_completed")
        assert status == BATCH_STATUS_APPLY_PENDING
    finally:
        with engine.begin() as conn:
            _cleanup_promotion_batch(conn, batch_august)
            _cleanup_promotion_batch(conn, batch_june)


@pytest.mark.skipif(not table_exists(engine.connect(), "hr_import_batches"), reason="no import schema")
def test_revert_restore_decision_returns_row_to_pending_and_reopens_review(seed, tmp_path: Path) -> None:
    _require_removal_decisions_schema()
    suffix = uuid4().hex[:8]
    department = f"Pytest Dept {suffix}"
    keep = _employee_spec(label="Keep", suffix=suffix)
    removed = _employee_spec(label="Removed", suffix=suffix)

    batch_june = _import_multi_employee_batch_named(
        seed, tmp_path, rows=[keep, removed], department=department, yymm="2606"
    )
    batch_august = _import_multi_employee_batch_named(
        seed, tmp_path, rows=[keep], department=department, yymm="2608"
    )
    try:
        _promote_and_snapshot_ready(seed, batch_june)
        with engine.begin() as conn:
            compute_batch_monthly_diff(conn, batch_august)
            removal_id = conn.execute(
                text(
                    """
                    SELECT removal_id
                    FROM public.hr_import_diff_removals
                    WHERE batch_id = :batch_id
                    LIMIT 1
                    """
                ),
                {"batch_id": batch_august},
            ).scalar_one()
            record_diff_removal_decision(
                conn,
                int(removal_id),
                decision=DECISION_RESTORE,
                decided_by=int(seed["initiator_user_id"]),
            )
            _approve_all_normalized(conn, batch_august)
            _resolve_all_removals(conn, batch_august, actor_user_id=int(seed["initiator_user_id"]))

        with engine.begin() as conn:
            revert_diff_removal_decision(
                conn,
                int(removal_id),
                reverted_by=int(seed["initiator_user_id"]),
                expected_batch_id=batch_august,
            )
            diff_summary = get_batch_diff_summary(conn, batch_august)
            status = conn.execute(
                text("SELECT status FROM public.hr_import_batches WHERE batch_id = :batch_id"),
                {"batch_id": batch_august},
            ).scalar_one()
            restored_match_key = conn.execute(
                text("SELECT match_key FROM public.hr_import_diff_removals WHERE removal_id = :removal_id"),
                {"removal_id": removal_id},
            ).scalar_one()
            match_keys = {
                str(row["match_key"])
                for row in collect_mrd_forming_entries_from_batch(conn, batch_august)
            }

        assert diff_summary["pending_removals"] == 1
        assert len(diff_summary["restored"]) == 0
        assert diff_summary["review_visibility"]["visible_records"] >= 1
        assert status == BATCH_STATUS_IN_REVIEW
        assert str(restored_match_key) not in match_keys
    finally:
        with engine.begin() as conn:
            _cleanup_promotion_batch(conn, batch_august)
            _cleanup_promotion_batch(conn, batch_june)
