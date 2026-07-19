"""Tests for HR Baseline + PublicationOrigin lifecycle."""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.hr_baseline_service import (
    BaselineDeleteError,
    BaselinePublishError,
    hard_delete_baseline,
    preview_baseline_publish,
    publish_baseline_from_batch,
    resolve_effective_baseline,
    restore_baseline,
    soft_delete_baseline,
)
from app.services.hr_import_service import import_control_list
from tests.conftest import table_exists
from tests.hr_import_fixtures import (
    cleanup_import_batch_with_baselines,
    complete_import_review_for_baseline_publish,
    write_control_list_workbook,
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _baseline_schema_available() -> bool:
    with engine.begin() as conn:
        return table_exists(conn, "hr_control_list_baselines") and table_exists(conn, "hr_publication_origins")


@pytest.fixture
def staged_batch(seed, tmp_path: Path):
    if not _baseline_schema_available():
        pytest.skip("baseline schema not applied")
    source = write_control_list_workbook(tmp_path, yymm="2606")
    with engine.begin() as conn:
        batch_id, _, _ = import_control_list(
            conn,
            file_path=source,
            imported_by=int(seed["initiator_user_id"]),
        )
    yield batch_id
    with engine.begin() as conn:
        cleanup_import_batch_with_baselines(conn, batch_id)


@pytest.fixture
def review_complete_batch(staged_batch):
    with engine.begin() as conn:
        complete_import_review_for_baseline_publish(conn, staged_batch)
    return staged_batch


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_publish_baseline_creates_origin_and_entries(review_complete_batch, seed):
    with engine.begin() as conn:
        result = publish_baseline_from_batch(
            conn,
            review_complete_batch,
            published_by=int(seed["initiator_user_id"]),
        )
        assert result["created"] is True
        baseline_id = int(result["baseline_id"])
        origin_id = int(result["publication_origin_id"])
        assert baseline_id > 0
        assert origin_id > 0
        entry_count = conn.execute(
            text("SELECT COUNT(*) FROM public.hr_baseline_entries WHERE baseline_id = :bid"),
            {"bid": baseline_id},
        ).scalar_one()
        assert int(entry_count) >= 1
        origin = conn.execute(
            text(
                """
                SELECT baseline_id, batch_id
                FROM public.hr_publication_origins
                WHERE publication_origin_id = :oid
                """
            ),
            {"oid": origin_id},
        ).mappings().one()
        assert int(origin["baseline_id"]) == baseline_id


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_preview_baseline_publish_reports_batch_composition(staged_batch):
    with engine.begin() as conn:
        preview = preview_baseline_publish(conn, staged_batch)
        assert preview["batch_id"] == staged_batch
        assert preview["baseline_entry_count"] >= 1
        assert preview["roster_baseline_entries"] >= 1
        assert preview["total_excel_rows"] >= preview["baseline_entry_count"]
        assert preview["publish_allowed"] is False
        assert preview["blockers"]
        assert "Baseline содержит утверждённый состав" in preview["explanation"]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_publish_blocked_for_in_review(staged_batch, seed):
    with engine.begin() as conn:
        with pytest.raises(BaselinePublishError) as exc:
            publish_baseline_from_batch(
                conn,
                staged_batch,
                published_by=int(seed["initiator_user_id"]),
            )
        assert any("IN_REVIEW" in item for item in exc.value.blockers)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_publish_allowed_after_review_complete(review_complete_batch, seed):
    with engine.begin() as conn:
        preview = preview_baseline_publish(conn, review_complete_batch)
        assert preview["publish_allowed"] is True
        assert preview["blockers"] == []
        result = publish_baseline_from_batch(
            conn,
            review_complete_batch,
            published_by=int(seed["initiator_user_id"]),
        )
        assert result["created"] is True


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_effective_baseline_is_max_published_at_per_period(review_complete_batch, seed):
    with engine.begin() as conn:
        first = publish_baseline_from_batch(
            conn,
            review_complete_batch,
            published_by=int(seed["initiator_user_id"]),
        )
        report_period = conn.execute(
            text("SELECT report_period FROM public.hr_control_list_baselines WHERE baseline_id = :bid"),
            {"bid": int(first["baseline_id"])},
        ).scalar_one()
        second = publish_baseline_from_batch(
            conn,
            review_complete_batch,
            published_by=int(seed["initiator_user_id"]),
            force=True,
        )
        effective = resolve_effective_baseline(conn, report_period)
        assert effective is not None
        assert int(effective["baseline_id"]) == int(second["baseline_id"])


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_soft_delete_restore_and_hard_delete(seed, tmp_path: Path):
    source = write_control_list_workbook(tmp_path, yymm="2611")
    with engine.begin() as conn:
        batch_id, summary, _ = import_control_list(
            conn,
            file_path=source,
            imported_by=int(seed["initiator_user_id"]),
        )
        import_code = str(summary["import_code"])
        complete_import_review_for_baseline_publish(conn, batch_id)
    try:
        with engine.begin() as conn:
            published = publish_baseline_from_batch(
                conn,
                batch_id,
                published_by=int(seed["initiator_user_id"]),
            )
            baseline_id = int(published["baseline_id"])
            origin_id = int(published["publication_origin_id"])
            report_period = conn.execute(
                text("SELECT report_period FROM public.hr_control_list_baselines WHERE baseline_id = :bid"),
                {"bid": baseline_id},
            ).scalar_one()

            soft = soft_delete_baseline(conn, baseline_id, deleted_by=int(seed["initiator_user_id"]))
            assert soft["soft_deleted"] is True
            assert resolve_effective_baseline(conn, report_period) is None

            restore_baseline(conn, baseline_id, restored_by=int(seed["initiator_user_id"]))
            soft_delete_baseline(conn, baseline_id, deleted_by=int(seed["initiator_user_id"]))
            with pytest.raises(BaselineDeleteError):
                soft_delete_baseline(conn, baseline_id, deleted_by=int(seed["initiator_user_id"]))

            restore_baseline(conn, baseline_id, restored_by=int(seed["initiator_user_id"]))
            soft_delete_baseline(conn, baseline_id, deleted_by=int(seed["initiator_user_id"]))
            hard = hard_delete_baseline(conn, baseline_id, deleted_by=int(seed["initiator_user_id"]))
            assert hard["hard_deleted"] is True
            origin = conn.execute(
                text(
                    "SELECT 1 FROM public.hr_publication_origins WHERE publication_origin_id = :oid"
                ),
                {"oid": origin_id},
            ).first()
            assert origin is not None
            entries = conn.execute(
                text("SELECT COUNT(*) FROM public.hr_baseline_entries WHERE baseline_id = :bid"),
                {"bid": baseline_id},
            ).scalar_one()
            assert int(entries) == 0
    finally:
        with engine.begin() as conn:
            cleanup_import_batch_with_baselines(conn, batch_id)
        with engine.connect() as conn:
            still = conn.execute(
                text("SELECT 1 FROM public.hr_import_batches WHERE import_code = :import_code"),
                {"import_code": import_code},
            ).first()
            assert still is None
