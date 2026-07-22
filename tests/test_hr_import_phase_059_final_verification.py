"""ADR-059 final verification — correction lifecycle, override cleanup, resolved exceptions."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.mrd.domain.types import DIFFERENCE_LIFECYCLE_DETECTED, TECHNICAL_DIFF_CHANGED
from app.services.hr_import_monthly_diff_service import (
    DIFF_STATUS_CHANGED,
    DIFF_STATUS_CONFLICT,
    DIFF_STATUS_UNCHANGED,
    compute_batch_monthly_diff,
)
from app.services.hr_import_review_exception_detail_service import (
    ReviewExceptionAlreadyResolvedError,
    build_exception_key,
    clear_import_review_overrides_for_batch,
    correct_review_exception_import,
    get_review_exception_detail,
    list_review_exceptions,
)
from app.services.hr_import_review_exception_service import (
    count_unresolved_exceptions,
    detected_differences_available,
)
from tests.conftest import table_exists
from tests.mrd_helpers import insert_detected_difference, insert_ephemeral_active_mrd, release_test_mrd, unique_report_period
from tests.test_hr_import_complete_review import staged_batch  # noqa: F401
from tests.test_hr_import_phase_040b_monthly_diff import _require_phase_040b


def _require_phase_059_final() -> None:
    _require_phase_040b()


@pytest.mark.skipif(not table_exists(engine.connect(), "hr_import_batches"), reason="no import schema")
def test_correction_to_unchanged_removes_from_exception_list(staged_batch, seed) -> None:
    _require_phase_059_final()
    batch_id = staged_batch["batch_id"]
    actor = int(seed["initiator_user_id"])

    with engine.begin() as conn:
        compute_batch_monthly_diff(conn, batch_id)
        row = conn.execute(
            text(
                """
                SELECT row_id, field_diffs, diff_status
                FROM public.hr_import_rows
                WHERE batch_id = :batch_id
                  AND diff_status IN (:changed, :conflict)
                  AND field_diffs IS NOT NULL
                ORDER BY row_id
                LIMIT 1
                """
            ),
            {
                "batch_id": batch_id,
                "changed": DIFF_STATUS_CHANGED,
                "conflict": DIFF_STATUS_CONFLICT,
            },
        ).mappings().first()
        if row is None:
            pytest.skip("no staged row with computed field diffs")

        row_id = int(row["row_id"])
        field_diffs = row["field_diffs"]
        if isinstance(field_diffs, str):
            field_diffs = json.loads(field_diffs)
        diff_field = next(iter(field_diffs.keys()))
        canonical_value = field_diffs[diff_field]["canonical"]
        exception_key = build_exception_key(entity_type="row", entity_id=row_id)

        before = list_review_exceptions(conn, batch_id)
        assert any(item["exception_key"] == exception_key for item in before["items"])

        result = correct_review_exception_import(
            conn,
            batch_id,
            exception_key,
            corrections={diff_field: canonical_value},
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

    assert result["detail"]["resolved_by_correction"] is True
    assert status == DIFF_STATUS_UNCHANGED
    assert not any(item["exception_key"] == exception_key for item in after["items"])


@pytest.mark.skipif(not table_exists(engine.connect(), "hr_import_batches"), reason="no import schema")
def test_resolved_exception_detail_raises_already_resolved(staged_batch) -> None:
    _require_phase_059_final()
    batch_id = staged_batch["batch_id"]

    with engine.begin() as conn:
        compute_batch_monthly_diff(conn, batch_id)
        row_id = conn.execute(
            text(
                """
                SELECT row_id
                FROM public.hr_import_rows
                WHERE batch_id = :batch_id
                ORDER BY row_id
                LIMIT 1
                """
            ),
            {"batch_id": batch_id},
        ).scalar_one()
        conn.execute(
            text(
                """
                UPDATE public.hr_import_rows
                SET diff_status = :unchanged
                WHERE batch_id = :batch_id
                  AND row_id = :row_id
                """
            ),
            {"batch_id": batch_id, "row_id": row_id, "unchanged": DIFF_STATUS_UNCHANGED},
        )
        exception_key = build_exception_key(entity_type="row", entity_id=int(row_id))

        with pytest.raises(ReviewExceptionAlreadyResolvedError):
            get_review_exception_detail(conn, batch_id, exception_key)

        detail = get_review_exception_detail(
            conn,
            batch_id,
            exception_key,
            allow_resolved=True,
        )
        assert detail["resolved_by_correction"] is True


@pytest.mark.skipif(not table_exists(engine.connect(), "hr_import_batches"), reason="no import schema")
def test_clear_import_review_overrides_removes_staging_overrides(staged_batch) -> None:
    batch_id = staged_batch["batch_id"]

    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT row_id, normalized_payload
                FROM public.hr_import_rows
                WHERE batch_id = :batch_id
                ORDER BY row_id
                LIMIT 1
                """
            ),
            {"batch_id": batch_id},
        ).mappings().one()
        payload = dict(row["normalized_payload"] or {})
        metadata = dict(payload.get("metadata") or {})
        metadata["import_review_override"] = {"position_raw": "Corrected title"}
        payload["metadata"] = metadata
        conn.execute(
            text(
                """
                UPDATE public.hr_import_rows
                SET normalized_payload = CAST(:normalized_payload AS JSONB)
                WHERE batch_id = :batch_id
                  AND row_id = :row_id
                """
            ),
            {
                "batch_id": batch_id,
                "row_id": int(row["row_id"]),
                "normalized_payload": json.dumps(payload, ensure_ascii=False),
            },
        )
        if table_exists(conn, "hr_import_normalized_records"):
            conn.execute(
                text(
                    """
                    UPDATE public.hr_import_normalized_records
                    SET review_override_json = CAST(:override AS JSONB)
                    WHERE batch_id = :batch_id
                      AND normalized_record_id = (
                          SELECT normalized_record_id
                          FROM public.hr_import_normalized_records
                          WHERE batch_id = :batch_id
                          ORDER BY normalized_record_id
                          LIMIT 1
                      )
                    """
                ),
                {
                    "batch_id": batch_id,
                    "override": json.dumps({"title": "Override title"}, ensure_ascii=False),
                },
            )

        cleared = clear_import_review_overrides_for_batch(conn, batch_id)
        row_override = conn.execute(
            text(
                """
                SELECT normalized_payload->'metadata'->'import_review_override'
                FROM public.hr_import_rows
                WHERE batch_id = :batch_id
                  AND row_id = :row_id
                """
            ),
            {"batch_id": batch_id, "row_id": int(row["row_id"])},
        ).scalar_one()
        normalized_override = None
        if table_exists(conn, "hr_import_normalized_records"):
            normalized_override = conn.execute(
                text(
                    """
                    SELECT review_override_json
                    FROM public.hr_import_normalized_records
                    WHERE batch_id = :batch_id
                    LIMIT 1
                    """
                ),
                {"batch_id": batch_id},
            ).scalar_one_or_none()

    assert cleared["rows_cleared"] >= 1 or cleared["normalized_records_cleared"] >= 1
    assert row_override is None
    assert normalized_override is None


@pytest.mark.skipif(not table_exists(engine.connect(), "hr_import_batches"), reason="no import schema")
def test_clear_import_review_overrides_for_batch_is_idempotent(staged_batch) -> None:
    batch_id = staged_batch["batch_id"]
    with engine.begin() as conn:
        first = clear_import_review_overrides_for_batch(conn, batch_id)
        second = clear_import_review_overrides_for_batch(conn, batch_id)
    assert first["rows_cleared"] >= 0
    assert second == {"normalized_records_cleared": 0, "rows_cleared": 0}


@pytest.mark.skipif(not table_exists(engine.connect(), "hr_import_batches"), reason="no import schema")
def test_correction_dismisses_mrd_difference_when_unchanged(staged_batch, seed) -> None:
    _require_phase_059_final()
    batch_id = staged_batch["batch_id"]
    actor = int(seed["initiator_user_id"])
    report_period = unique_report_period()

    with engine.connect() as conn:
        if not detected_differences_available(conn):
            pytest.skip("hr_detected_differences missing")

    mrd_id: int | None = None
    difference_id: int | None = None
    try:
        with engine.begin() as conn:
            compute_batch_monthly_diff(conn, batch_id)
            row = conn.execute(
                text(
                    """
                    SELECT row_id, field_diffs
                    FROM public.hr_import_rows
                    WHERE batch_id = :batch_id
                      AND diff_status IN (:changed, :conflict)
                      AND field_diffs IS NOT NULL
                    ORDER BY row_id
                    LIMIT 1
                    """
                ),
                {
                    "batch_id": batch_id,
                    "changed": DIFF_STATUS_CHANGED,
                    "conflict": DIFF_STATUS_CONFLICT,
                },
            ).mappings().first()
            if row is None:
                pytest.skip("no staged row with computed field diffs")

            row_id = int(row["row_id"])
            field_diffs = row["field_diffs"]
            if isinstance(field_diffs, str):
                field_diffs = json.loads(field_diffs)
            diff_field = next(iter(field_diffs.keys()))
            canonical_value = field_diffs[diff_field]["canonical"]
            incoming_value = field_diffs[diff_field]["incoming"]
            conn.execute(
                text(
                    """
                    UPDATE public.hr_import_rows
                    SET diff_status = :conflict
                    WHERE batch_id = :batch_id
                      AND row_id = :row_id
                    """
                ),
                {"batch_id": batch_id, "row_id": row_id, "conflict": DIFF_STATUS_CONFLICT},
            )
            mrd_id = insert_ephemeral_active_mrd(
                conn,
                report_period=report_period,
                created_by=actor,
            )
            difference_id = insert_detected_difference(
                conn,
                report_period=report_period,
                mrd_id=mrd_id,
                logical_key=f"batch:{batch_id}:row:{row_id}:{diff_field}",
                entity_scope=f"row:{row_id}",
                attribute=diff_field,
                business_type="PERIOD_CHANGED",
                old_value=canonical_value,
                new_value=incoming_value,
                technical_diff_class=TECHNICAL_DIFF_CHANGED,
                origin_context={"batch_id": batch_id, "row_id": row_id},
            )
            exception_key = build_exception_key(entity_type="row", entity_id=row_id)
            assert count_unresolved_exceptions(conn, batch_id) >= 1

            correct_review_exception_import(
                conn,
                batch_id,
                exception_key,
                corrections={diff_field: canonical_value},
                actor_user_id=actor,
            )
            lifecycle = conn.execute(
                text(
                    """
                    SELECT lifecycle_status
                    FROM public.hr_detected_differences
                    WHERE difference_id = :difference_id
                    """
                ),
                {"difference_id": difference_id},
            ).scalar_one()
            unresolved = count_unresolved_exceptions(conn, batch_id)

        assert lifecycle != DIFFERENCE_LIFECYCLE_DETECTED
        assert unresolved == 0
    finally:
        if mrd_id is not None:
            with engine.begin() as conn:
                release_test_mrd(conn, mrd_id)
