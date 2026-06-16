"""Tests for HR Import Phase 2E — batch delete, rebuild candidates, sheet diagnostics."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.services.hr_import_analytics_service import delete_batch, sheet_diagnostics
from app.services.hr_import_document_candidate_service import (
    rebuild_document_candidates,
)
from app.services.hr_import_service import import_control_list
from tests.conftest import auth_headers, table_exists
from tests.test_import_hr_control_list import _build_sample_workbook


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _phase_2c_available() -> bool:
    with engine.begin() as conn:
        if not table_exists(conn, "hr_import_document_candidates"):
            return False
        cols = {
            c["name"]
            for c in conn.execute(
                text(
                    """
                    SELECT column_name AS name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'hr_import_document_candidates'
                    """
                )
            ).mappings()
        }
        return "batch_id" in cols and "raw_text" in cols


def _require_phase_2c() -> None:
    if not _phase_2c_available():
        pytest.skip("Phase 2C migration not applied — run alembic upgrade head")


def _employee_doc_count(conn) -> int:
    if not table_exists(conn, "employee_documents"):
        return 0
    return int(conn.execute(text("SELECT COUNT(*) FROM public.employee_documents")).scalar_one())


def _employee_count(conn) -> int:
    if not table_exists(conn, "employees"):
        return 0
    return int(conn.execute(text("SELECT COUNT(*) FROM public.employees")).scalar_one())


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def staged_batch(seed, tmp_path: Path):
    _require_phase_2c()
    source = tmp_path / f"phase2e_{uuid4().hex[:8]}.xlsx"
    _build_sample_workbook(source)
    with engine.begin() as conn:
        before_employees = _employee_count(conn)
        before_docs = _employee_doc_count(conn)
        batch_id, _, _ = import_control_list(
            conn,
            file_path=source,
            imported_by=int(seed["initiator_user_id"]),
        )
    yield batch_id, before_employees, before_docs
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.hr_import_batches WHERE batch_id = :batch_id"),
            {"batch_id": batch_id},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_delete_batch_removes_rows_and_candidates_not_employees(staged_batch):
    batch_id, before_employees, before_docs = staged_batch
    with engine.begin() as conn:
        row_count = int(
            conn.execute(
                text("SELECT COUNT(*) FROM public.hr_import_rows WHERE batch_id = :bid"),
                {"bid": batch_id},
            ).scalar_one()
        )
        cand_count = int(
            conn.execute(
                text(
                    "SELECT COUNT(*) FROM public.hr_import_document_candidates WHERE batch_id = :bid"
                ),
                {"bid": batch_id},
            ).scalar_one()
        )
        assert row_count >= 1
        result = delete_batch(conn, batch_id)
        assert result["deleted"] is True
        assert result["deleted_rows"] == row_count
        assert result["deleted_candidates"] == cand_count
        assert (
            conn.execute(
                text("SELECT 1 FROM public.hr_import_batches WHERE batch_id = :bid"),
                {"bid": batch_id},
            ).first()
            is None
        )
        after_employees = _employee_count(conn)
        after_docs = _employee_doc_count(conn)
    assert after_employees == before_employees
    assert after_docs == before_docs


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_delete_batch_api(client: TestClient, privileged_headers, seed, tmp_path: Path):
    _require_phase_2c()
    source = tmp_path / f"phase2e_del_{uuid4().hex[:8]}.xlsx"
    _build_sample_workbook(source)
    with engine.begin() as conn:
        batch_id, _, _ = import_control_list(
            conn,
            file_path=source,
            imported_by=int(seed["initiator_user_id"]),
        )
    resp = client.delete(
        f"/directory/personnel/import/batches/{batch_id}",
        headers=privileged_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["deleted"] is True
    assert body["batch_id"] == batch_id


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_rebuild_candidates_idempotent(staged_batch):
    batch_id, _, _ = staged_batch
    with engine.begin() as conn:
        first = rebuild_document_candidates(conn, batch_id)
        second = rebuild_document_candidates(conn, batch_id)
    assert first["total_candidates"] == second["total_candidates"]
    assert first["total_candidates"] >= 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_rebuild_preserves_confirmed_candidates(staged_batch):
    batch_id, _, _ = staged_batch
    with engine.begin() as conn:
        approved_id = conn.execute(
            text(
                """
                UPDATE public.hr_import_document_candidates
                SET review_status = 'APPROVED'
                WHERE candidate_id = (
                    SELECT candidate_id
                    FROM public.hr_import_document_candidates
                    WHERE batch_id = :batch_id
                    ORDER BY candidate_id
                    LIMIT 1
                )
                RETURNING candidate_id
                """
            ),
            {"batch_id": batch_id},
        ).scalar_one()
        before_total = int(
            conn.execute(
                text(
                    "SELECT COUNT(*) FROM public.hr_import_document_candidates WHERE batch_id = :bid"
                ),
                {"bid": batch_id},
            ).scalar_one()
        )
        result = rebuild_document_candidates(conn, batch_id)
        after_total = int(
            conn.execute(
                text(
                    "SELECT COUNT(*) FROM public.hr_import_document_candidates WHERE batch_id = :bid"
                ),
                {"bid": batch_id},
            ).scalar_one()
        )
        preserved = conn.execute(
            text(
                """
                SELECT review_status
                FROM public.hr_import_document_candidates
                WHERE candidate_id = :cid
                """
            ),
            {"cid": approved_id},
        ).scalar_one()
    assert preserved == "APPROVED"
    assert result["preserved_candidates"] >= 1
    assert after_total >= before_total


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_rebuild_api(client: TestClient, privileged_headers, staged_batch):
    batch_id, _, _ = staged_batch
    resp = client.post(
        f"/directory/personnel/import/batches/{batch_id}/document-candidates/rebuild",
        headers=privileged_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["batch_id"] == batch_id
    assert body["total_candidates"] >= 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_sheet_diagnostics(staged_batch):
    batch_id, _, _ = staged_batch
    with engine.connect() as conn:
        result = sheet_diagnostics(conn, batch_id)
    assert result["batch_id"] == batch_id
    assert len(result["items"]) >= 1
    first = result["items"][0]
    assert "sheet_name" in first
    assert "sheet_type" in first
    assert "rows_total" in first
    assert "employee_rows" in first
    assert "declaration_rows" in first
    assert "technical_rows" in first
    assert "candidates_count" in first
    assert result["totals"]["rows_total"] >= 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_sheet_diagnostics_api(client: TestClient, privileged_headers, staged_batch):
    batch_id, _, _ = staged_batch
    resp = client.get(
        f"/directory/personnel/import/batches/{batch_id}/sheet-diagnostics",
        headers=privileged_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["batch_id"] == batch_id


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_training_route_api(client: TestClient, privileged_headers, staged_batch):
    batch_id, _, _ = staged_batch
    resp = client.get(
        f"/directory/personnel/import/batches/{batch_id}/document-candidates?limit=10",
        headers=privileged_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["batch_id"] == batch_id
    assert "items" in data
