"""ADR-059 Phase 1 — complete-review gate uses review-by-exception blockers."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.hr_import import BATCH_STATUS_APPLY_PENDING, BATCH_STATUS_IN_REVIEW
from app.mrd.domain.types import TECHNICAL_DIFF_CHANGED
from app.services.hr_import_complete_review_service import (
    assess_complete_import_review,
    maybe_auto_complete_import_review,
)
from app.services.hr_import_monthly_diff_service import DIFF_STATUS_UNCHANGED, compute_batch_monthly_diff
from app.services.hr_import_normalized_record_service import REVIEW_STATUS_PENDING
from app.services.hr_import_review_exception_service import (
    BLOCKER_UNRESOLVED_EXCEPTIONS,
    detected_differences_available,
    run_post_diff_review_completion,
)
from tests.conftest import table_exists
from tests.mrd_helpers import (
    insert_detected_difference,
    insert_ephemeral_active_mrd,
    release_test_mrd,
    unique_report_period,
)
from tests.test_hr_import_complete_review import _resolve_all_pending_removals, staged_batch  # noqa: F401
from tests.test_hr_import_phase_040b_monthly_diff_business_scenarios import _employee_spec
from tests.test_hr_import_diff_removal_decisions import (
    _import_multi_employee_batch_named,
    _promote_and_snapshot_ready,
    _require_removal_decisions_schema,
)
from tests.test_hr_import_phase_040a_canonical_snapshot import _cleanup_promotion_batch
from tests.test_hr_import_phase_040b_monthly_diff import _require_phase_040b


def _require_phase_059_gate() -> None:
    _require_phase_040b()


def _count_pending_normalized(conn, batch_id: int) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(*)::bigint
                FROM public.hr_import_normalized_records
                WHERE batch_id = :batch_id
                  AND review_status = :pending
                """
            ),
            {"batch_id": batch_id, "pending": REVIEW_STATUS_PENDING},
        ).scalar_one()
        or 0
    )


@pytest.mark.skipif(not table_exists(engine.connect(), "hr_import_batches"), reason="no import schema")
def test_unchanged_only_batch_auto_completes_to_apply_pending(staged_batch, seed) -> None:
    """ADR-059 AC-1: only UNCHANGED exceptions → auto APPLY_PENDING (pending normalized ignored)."""
    batch_id = staged_batch["batch_id"]
    import_code = staged_batch["import_code"]
    with engine.connect() as conn:
        if detected_differences_available(conn):
            unresolved_before = conn.execute(
                text(
                    """
                    SELECT COUNT(*)::bigint
                    FROM public.hr_detected_differences
                    WHERE lifecycle_status = 'DETECTED'
                      AND (origin_context->>'batch_id')::bigint = :batch_id
                    """
                ),
                {"batch_id": batch_id},
            ).scalar_one()
            assert int(unresolved_before or 0) == 0

    with engine.connect() as conn:
        status_before = conn.execute(
            text("SELECT status FROM public.hr_import_batches WHERE batch_id = :batch_id"),
            {"batch_id": batch_id},
        ).scalar_one()
        pending_before = _count_pending_normalized(conn, batch_id)

    with engine.begin() as conn:
        _resolve_all_pending_removals(conn, batch_id, actor_user_id=int(seed["initiator_user_id"]))
        conn.execute(
            text(
                """
                UPDATE public.hr_import_rows
                SET diff_status = :unchanged
                WHERE batch_id = :batch_id
                """
            ),
            {"batch_id": batch_id, "unchanged": DIFF_STATUS_UNCHANGED},
        )
        if table_exists(conn, "hr_import_normalized_records"):
            conn.execute(
                text(
                    """
                    UPDATE public.hr_import_normalized_records
                    SET diff_status = :unchanged
                    WHERE batch_id = :batch_id
                    """
                ),
                {"batch_id": batch_id, "unchanged": DIFF_STATUS_UNCHANGED},
            )

    with engine.begin() as conn:
        assessment = assess_complete_import_review(conn, import_code)
        status_mid = conn.execute(
            text("SELECT status FROM public.hr_import_batches WHERE batch_id = :batch_id"),
            {"batch_id": batch_id},
        ).scalar_one()
        if status_mid == BATCH_STATUS_IN_REVIEW:
            result = run_post_diff_review_completion(
                conn,
                batch_id,
                actor_user_id=int(seed["initiator_user_id"]),
            )
            assert result.get("auto_completed") is True
        status_after = conn.execute(
            text("SELECT status FROM public.hr_import_batches WHERE batch_id = :batch_id"),
            {"batch_id": batch_id},
        ).scalar_one()

    assert pending_before > 0
    assert status_before == BATCH_STATUS_IN_REVIEW
    assert assessment["review_progress"]["unresolved_exceptions"] == 0
    assert assessment["complete_allowed"] is True
    assert status_after == BATCH_STATUS_APPLY_PENDING


@pytest.mark.skipif(not table_exists(engine.connect(), "hr_import_batches"), reason="no import schema")
def test_unresolved_difference_blocks_auto_complete(staged_batch, seed) -> None:
    _require_phase_059_gate()
    batch_id = staged_batch["batch_id"]
    import_code = staged_batch["import_code"]
    report_period = unique_report_period()
    with engine.connect() as conn:
        if not detected_differences_available(conn):
            pytest.skip("hr_detected_differences missing")

    mrd_id: int | None = None
    with engine.begin() as conn:
        mrd_id = insert_ephemeral_active_mrd(
            conn,
            report_period=report_period,
            created_by=int(seed["initiator_user_id"]),
        )
        insert_detected_difference(
            conn,
            report_period=report_period,
            mrd_id=mrd_id,
            logical_key=f"batch:{batch_id}:position_raw",
            entity_scope="emp:999001",
            attribute="position_raw",
            business_type="PERIOD_CHANGED",
            old_value="Old",
            new_value="New",
            technical_diff_class=TECHNICAL_DIFF_CHANGED,
            origin_context={"batch_id": batch_id, "match_key": "emp:999001"},
        )
        assessment = assess_complete_import_review(conn, import_code)
        assert assessment["complete_allowed"] is False
        assert any(item["code"] == BLOCKER_UNRESOLVED_EXCEPTIONS for item in assessment["blockers"])

        result = maybe_auto_complete_import_review(
            conn,
            batch_id,
            actor_user_id=int(seed["initiator_user_id"]),
        )
        status = conn.execute(
            text("SELECT status FROM public.hr_import_batches WHERE batch_id = :batch_id"),
            {"batch_id": batch_id},
        ).scalar_one()

    assert result["auto_completed"] is False
    assert status == BATCH_STATUS_IN_REVIEW

    if mrd_id is not None:
        with engine.begin() as conn:
            release_test_mrd(conn, mrd_id)


@pytest.mark.skipif(not table_exists(engine.connect(), "hr_import_batches"), reason="no import schema")
def test_pending_removal_blocks_auto_complete(seed, tmp_path: Path) -> None:
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
            import_code = conn.execute(
                text("SELECT import_code FROM public.hr_import_batches WHERE batch_id = :batch_id"),
                {"batch_id": batch_august},
            ).scalar_one()
            assessment = assess_complete_import_review(conn, str(import_code))
            assert assessment["complete_allowed"] is False
            assert any(item["code"] == "PENDING_REMOVED_DECISIONS" for item in assessment["blockers"])

            result = maybe_auto_complete_import_review(
                conn,
                batch_august,
                actor_user_id=int(seed["initiator_user_id"]),
            )
            status = conn.execute(
                text("SELECT status FROM public.hr_import_batches WHERE batch_id = :batch_id"),
                {"batch_id": batch_august},
            ).scalar_one()

        assert result["auto_completed"] is False
        assert status == BATCH_STATUS_IN_REVIEW
    finally:
        with engine.begin() as conn:
            _cleanup_promotion_batch(conn, batch_august)
            _cleanup_promotion_batch(conn, batch_june)


@pytest.mark.skipif(not table_exists(engine.connect(), "hr_import_batches"), reason="no import schema")
def test_parse_errors_block_auto_complete(staged_batch, seed) -> None:
    batch_id = staged_batch["batch_id"]
    import_code = staged_batch["import_code"]
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE public.hr_import_batches
                SET error_rows = 2
                WHERE batch_id = :batch_id
                """
            ),
            {"batch_id": batch_id},
        )
        assessment = assess_complete_import_review(conn, import_code)
        assert assessment["complete_allowed"] is False
        assert any(item["code"] == "ERROR_ROWS" for item in assessment["blockers"])

        result = maybe_auto_complete_import_review(
            conn,
            batch_id,
            actor_user_id=int(seed["initiator_user_id"]),
        )
        status = conn.execute(
            text("SELECT status FROM public.hr_import_batches WHERE batch_id = :batch_id"),
            {"batch_id": batch_id},
        ).scalar_one()

    assert result["auto_completed"] is False
    assert status == BATCH_STATUS_IN_REVIEW


@pytest.mark.skipif(not table_exists(engine.connect(), "hr_import_batches"), reason="no import schema")
def test_pending_normalized_does_not_affect_gate(staged_batch) -> None:
    batch_id = staged_batch["batch_id"]
    import_code = staged_batch["import_code"]
    with engine.connect() as conn:
        pending = _count_pending_normalized(conn, batch_id)
        assessment = assess_complete_import_review(conn, import_code)

    assert pending > 0
    blocker_codes = {item["code"] for item in assessment["blockers"]}
    assert "PENDING_NORMALIZED" not in blocker_codes
