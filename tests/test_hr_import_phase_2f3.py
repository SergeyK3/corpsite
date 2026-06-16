"""Tests for HR Import Phase 2F.3 — employee education profiles UI."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.services.department_recoding_service import list_recoding_options, seed_department_recoding
from app.services.hr_import_document_candidate_service import list_document_candidates
from app.services.hr_import_education_profile_service import (
    archive_education_profile,
    get_education_profile,
    list_education_profiles,
    update_education_profile,
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


def _profile_staging_available() -> bool:
    with engine.begin() as conn:
        if not table_exists(conn, "department_recoding"):
            return False
        row = conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'hr_import_rows'
                  AND column_name = 'profile_override'
                """
            )
        ).first()
        return row is not None


def _require_profile_staging() -> None:
    if not _profile_staging_available():
        pytest.skip("Phase 2F.3 migration not applied — run alembic upgrade head")


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def staged_batch(seed, tmp_path: Path):
    _require_profile_staging()
    source = tmp_path / f"phase2f3_{uuid4().hex[:8]}.xlsx"
    _build_sample_workbook(source)
    with engine.begin() as conn:
        seed_department_recoding(conn)
        batch_id, _, _ = import_control_list(
            conn,
            file_path=source,
            imported_by=int(seed["initiator_user_id"]),
        )
    yield batch_id
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.hr_import_batches WHERE batch_id = :batch_id"),
            {"batch_id": batch_id},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_one_employee_one_profile_row_not_duplicated_by_candidates(staged_batch):
    with engine.connect() as conn:
        profiles = list_education_profiles(conn, staged_batch, limit=500)
        candidates = list_document_candidates(conn, staged_batch, limit=500)
    assert profiles["total"] >= 1
    if candidates["total"] > profiles["total"]:
        names = [p["full_name"] for p in profiles["items"]]
        assert len(names) == len(set(names)), "each employee must appear once in profile list"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_recoding_options_all_canonical_departments(staged_batch):
    with engine.connect() as conn:
        seed_department_recoding(conn)
        options = list_recoding_options(conn)
        db_count = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(DISTINCT LOWER(TRIM(org_unit_name)))
                    FROM public.department_recoding
                    WHERE is_active = TRUE AND TRIM(org_unit_name) <> ''
                    """
                )
            ).scalar_one()
        )
    assert len(options["departments"]) == db_count
    assert len(options["departments"]) >= 10


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_education_profile_card_sections(staged_batch):
    with engine.connect() as conn:
        profiles = list_education_profiles(conn, staged_batch, limit=1)
        profile_id = profiles["items"][0]["profile_id"]
        detail = get_education_profile(conn, staged_batch, profile_id)
    p = detail["profile"]
    assert "basic" in p
    assert "education_records" in p or "education" in p
    assert "training_records" in p
    assert "category_records" in p
    assert "certificate_records" in p
    assert "degrees" in p
    assert "award_records" in p
    assert "notes_raw" in p


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_save_profile_does_not_create_employees_or_documents(staged_batch):
    with engine.connect() as conn:
        before_employees = int(conn.execute(text("SELECT COUNT(*) FROM public.employees")).scalar_one())
        before_docs = int(
            conn.execute(text("SELECT COUNT(*) FROM public.employee_documents")).scalar_one()
        )
        profile_id = list_education_profiles(conn, staged_batch, limit=1)["items"][0]["profile_id"]
        detail = get_education_profile(conn, staged_batch, profile_id)
        updated = update_education_profile(
            conn,
            staged_batch,
            profile_id,
            profile={
                **detail["profile"],
                "basic": {**detail["profile"]["basic"], "full_name": "Тест Сохранения Профиля"},
            },
            review_status="reviewed",
        )
        after_employees = int(conn.execute(text("SELECT COUNT(*) FROM public.employees")).scalar_one())
        after_docs = int(
            conn.execute(text("SELECT COUNT(*) FROM public.employee_documents")).scalar_one()
        )
    assert updated["review_status"] == "reviewed"
    assert after_employees == before_employees
    assert after_docs == before_docs


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_archive_does_not_create_hr_events(staged_batch):
    with engine.connect() as conn:
        if not table_exists(conn, "employee_events"):
            pytest.skip("employee_events table not available")
        before_events = int(conn.execute(text("SELECT COUNT(*) FROM public.employee_events")).scalar_one())
        profile_id = list_education_profiles(conn, staged_batch, limit=1)["items"][0]["profile_id"]
        archived = archive_education_profile(conn, staged_batch, profile_id)
        after_events = int(conn.execute(text("SELECT COUNT(*) FROM public.employee_events")).scalar_one())
    assert archived["profile_status"] == "archived"
    assert after_events == before_events


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_duplicate_iin_aggregates_to_single_profile(staged_batch):
    """Same IIN on multiple staging rows → one profile row (e.g. Абдалимова case)."""
    with engine.connect() as conn:
        source_row = conn.execute(
            text(
                """
                SELECT row_id, normalized_payload, source_sheet, source_row_number
                FROM public.hr_import_rows
                WHERE batch_id = :batch_id
                ORDER BY row_id
                LIMIT 1
                """
            ),
            {"batch_id": staged_batch},
        ).mappings().first()
        assert source_row is not None
        payload = dict(source_row["normalized_payload"] or {})
        payload["full_name"] = "Абдалимова Айгуль Тестовна"
        payload["iin"] = "900101350123"
        import json

        payload_json = json.dumps(payload, ensure_ascii=False)
    row_id = int(source_row["row_id"])
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE public.hr_import_rows
                SET normalized_payload = CAST(:payload AS JSONB),
                    raw_payload = CAST(:payload AS JSONB)
                WHERE row_id = :row_id
                """
            ),
            {"payload": payload_json, "row_id": row_id},
        )
        conn.execute(
            text(
                """
                INSERT INTO public.hr_import_rows (
                    batch_id, source_sheet, source_row_number,
                    raw_payload, normalized_payload, match_status
                )
                SELECT :batch_id, source_sheet, source_row_number + 9000,
                       CAST(:payload AS JSONB), CAST(:payload AS JSONB), match_status
                FROM public.hr_import_rows
                WHERE row_id = :row_id
                """
            ),
            {
                "batch_id": staged_batch,
                "payload": payload_json,
                "row_id": row_id,
            },
        )
    try:
        with engine.connect() as conn:
            profiles = list_education_profiles(conn, staged_batch, q_name="Абдалимова", limit=500)
            matching = [p for p in profiles["items"] if "Абдалимова" in p["full_name"]]
        assert len(matching) == 1, "duplicate IIN rows must aggregate to one employee profile"
        assert matching[0]["source_row_ids"] and len(matching[0]["source_row_ids"]) >= 2
    finally:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    DELETE FROM public.hr_import_rows
                    WHERE batch_id = :batch_id AND source_row_number >= 9000
                    """
                ),
                {"batch_id": staged_batch},
            )
            conn.execute(
                text(
                    """
                    UPDATE public.hr_import_rows
                    SET normalized_payload = CAST(:payload AS JSONB),
                        raw_payload = CAST(:payload AS JSONB)
                    WHERE row_id = :row_id
                    """
                ),
                {
                    "payload": json.dumps(dict(source_row["normalized_payload"] or {}), ensure_ascii=False),
                    "row_id": row_id,
                },
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_education_profiles_api(client: TestClient, privileged_headers, staged_batch):
    resp = client.get(
        f"/directory/personnel/import/batches/{staged_batch}/education-profiles",
        headers=privileged_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] >= 1
    assert len(body["items"]) >= 1
    profile_id = body["items"][0]["profile_id"]
    detail_resp = client.get(
        f"/directory/personnel/import/batches/{staged_batch}/education-profiles/{profile_id}",
        headers=privileged_headers,
    )
    assert detail_resp.status_code == 200
    assert "profile" in detail_resp.json()
