"""Tests for Complete Import Review workflow."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.hr_import import BATCH_STATUS_APPLY_PENDING, BATCH_STATUS_IN_REVIEW
from app.main import app
from app.services.hr_baseline_service import assess_baseline_publish_readiness
from app.services.hr_import_complete_review_service import (
    CompleteImportReviewError,
    assess_complete_import_review,
    complete_import_review,
)
from app.services.hr_import_normalized_record_service import REVIEW_STATUS_APPROVED
from app.services.hr_import_service import import_control_list
from tests.conftest import auth_headers, table_exists
from tests.hr_import_fixtures import cleanup_import_batch, write_control_list_workbook

client = TestClient(app)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _phase_2b_available() -> bool:
    with engine.begin() as conn:
        return table_exists(conn, "hr_import_batches")


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def staged_batch(seed, tmp_path: Path):
    if not _phase_2b_available():
        pytest.skip("HR import staging tables missing")
    source = write_control_list_workbook(tmp_path, yymm="2612")
    with engine.begin() as conn:
        batch_id, _, _ = import_control_list(
            conn,
            file_path=source,
            imported_by=int(seed["initiator_user_id"]),
        )
        import_code = conn.execute(
            text("SELECT import_code FROM public.hr_import_batches WHERE batch_id = :batch_id"),
            {"batch_id": batch_id},
        ).scalar_one()
    yield {"batch_id": batch_id, "import_code": str(import_code)}
    with engine.begin() as conn:
        cleanup_import_batch(conn, batch_id)


def _approve_all_normalized(conn, batch_id: int) -> None:
    conn.execute(
        text(
            """
            UPDATE public.hr_import_normalized_records
            SET review_status = :approved
            WHERE batch_id = :batch_id
              AND review_status = 'pending'
            """
        ),
        {"batch_id": batch_id, "approved": REVIEW_STATUS_APPROVED},
    )


def _resolve_all_pending_removals(conn, batch_id: int, *, actor_user_id: int) -> None:
    from app.services.hr_import_diff_removal_decision_service import (
        DECISION_CONFIRM_REMOVAL,
        diff_removal_decisions_available,
        record_diff_removal_decision,
    )

    if not diff_removal_decisions_available(conn):
        conn.execute(
            text("DELETE FROM public.hr_import_diff_removals WHERE batch_id = :batch_id"),
            {"batch_id": batch_id},
        )
        return

    removal_ids = conn.execute(
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
    for removal_id in removal_ids:
        record_diff_removal_decision(
            conn,
            int(removal_id),
            decision=DECISION_CONFIRM_REMOVAL,
            decided_by=actor_user_id,
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_assess_complete_review_blocked_with_pending_normalized(staged_batch):
    with engine.connect() as conn:
        result = assess_complete_import_review(conn, staged_batch["import_code"])
    assert result["complete_allowed"] is False
    assert result["batch_status"] == BATCH_STATUS_IN_REVIEW
    codes = {item["code"] for item in result["blockers"]}
    assert "PENDING_NORMALIZED" in codes


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_complete_review_success_transitions_to_apply_pending(staged_batch, seed):
    batch_id = staged_batch["batch_id"]
    import_code = staged_batch["import_code"]
    with engine.begin() as conn:
        _approve_all_normalized(conn, batch_id)
        _resolve_all_pending_removals(conn, batch_id, actor_user_id=int(seed["initiator_user_id"]))
        result = complete_import_review(
            conn,
            import_code,
            completed_by=int(seed["initiator_user_id"]),
        )
        status = conn.execute(
            text("SELECT status FROM public.hr_import_batches WHERE batch_id = :batch_id"),
            {"batch_id": batch_id},
        ).scalar_one()
    assert result["completed"] is True
    assert result["batch_status"] == BATCH_STATUS_APPLY_PENDING
    assert status == BATCH_STATUS_APPLY_PENDING


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_complete_review_idempotent_when_already_apply_pending(staged_batch, seed):
    batch_id = staged_batch["batch_id"]
    import_code = staged_batch["import_code"]
    with engine.begin() as conn:
        _approve_all_normalized(conn, batch_id)
        _resolve_all_pending_removals(conn, batch_id, actor_user_id=int(seed["initiator_user_id"]))
        complete_import_review(conn, import_code, completed_by=int(seed["initiator_user_id"]))
        second = complete_import_review(conn, import_code, completed_by=int(seed["initiator_user_id"]))
    assert second["already_completed"] is True
    assert second["batch_status"] == BATCH_STATUS_APPLY_PENDING


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_complete_review_raises_on_error_rows(staged_batch, seed):
    batch_id = staged_batch["batch_id"]
    import_code = staged_batch["import_code"]
    with engine.begin() as conn:
        _approve_all_normalized(conn, batch_id)
        conn.execute(
            text(
                """
                UPDATE public.hr_import_batches
                SET error_rows = 3
                WHERE batch_id = :batch_id
                """
            ),
            {"batch_id": batch_id},
        )
        with pytest.raises(CompleteImportReviewError) as exc:
            complete_import_review(conn, import_code, completed_by=int(seed["initiator_user_id"]))
    assert any(item["code"] == "ERROR_ROWS" for item in exc.value.blockers)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_complete_review_enables_baseline_publish_gate(staged_batch, seed):
    batch_id = staged_batch["batch_id"]
    import_code = staged_batch["import_code"]
    with engine.begin() as conn:
        _approve_all_normalized(conn, batch_id)
        _resolve_all_pending_removals(conn, batch_id, actor_user_id=int(seed["initiator_user_id"]))
        complete_import_review(conn, import_code, completed_by=int(seed["initiator_user_id"]))
        readiness = assess_baseline_publish_readiness(conn, batch_id)
    assert readiness["publish_allowed"] is True
    assert readiness["blockers"] == []


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_get_complete_review_api(staged_batch, privileged_headers):
    import_code = staged_batch["import_code"]
    resp = client.get(
        f"/directory/personnel/import/batches/{import_code}/complete-review",
        headers=privileged_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["import_code"] == import_code
    assert body["complete_allowed"] is False
    assert body["blockers"]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_post_complete_review_api_success(staged_batch, privileged_headers, seed):
    batch_id = staged_batch["batch_id"]
    import_code = staged_batch["import_code"]
    with engine.begin() as conn:
        _approve_all_normalized(conn, batch_id)
        _resolve_all_pending_removals(conn, batch_id, actor_user_id=int(seed["initiator_user_id"]))

    resp = client.post(
        f"/directory/personnel/import/batches/{import_code}/complete-review",
        headers=privileged_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["completed"] is True
    assert body["batch_status"] == BATCH_STATUS_APPLY_PENDING


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_post_complete_review_api_returns_409_with_blockers(staged_batch, privileged_headers):
    import_code = staged_batch["import_code"]
    resp = client.post(
        f"/directory/personnel/import/batches/{import_code}/complete-review",
        headers=privileged_headers,
    )
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["blockers"]
    assert any(item["code"] == "PENDING_NORMALIZED" for item in detail["blockers"])


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_post_complete_review_writes_audit_event(staged_batch, privileged_headers, seed):
    batch_id = staged_batch["batch_id"]
    import_code = staged_batch["import_code"]
    with engine.begin() as conn:
        _approve_all_normalized(conn, batch_id)
        _resolve_all_pending_removals(conn, batch_id, actor_user_id=int(seed["initiator_user_id"]))

    resp = client.post(
        f"/directory/personnel/import/batches/{import_code}/complete-review",
        headers=privileged_headers,
    )
    assert resp.status_code == 200

    with engine.connect() as conn:
        if not table_exists(conn, "security_audit_log"):
            pytest.skip("security_audit_log missing")
        row = conn.execute(
            text(
                """
                SELECT event_type, metadata
                FROM public.security_audit_log
                WHERE event_type = 'HR_IMPORT_REVIEW_COMPLETED'
                  AND metadata->>'batch_id' = :batch_id
                ORDER BY happened_at DESC
                LIMIT 1
                """
            ),
            {"batch_id": str(batch_id)},
        ).mappings().first()
    assert row is not None
    assert row["event_type"] == "HR_IMPORT_REVIEW_COMPLETED"
