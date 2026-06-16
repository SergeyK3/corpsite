"""Tests for HR Import Phase 2F — review UI, department recoding, education portfolio."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.services.department_recoding_service import (
    infer_department_group,
    list_recoding_options,
    lookup_recoding,
    seed_department_recoding,
)
from app.services.hr_import_ai_extraction_service import run_ai_extraction
from app.services.hr_import_analytics_service import _infer_staff_type, list_batch_rows
from app.services.hr_import_document_candidate_service import education_portfolio
from app.services.hr_import_profile_service import build_import_profile
from app.services.hr_import_row_review_service import get_row_review_detail
from app.services.hr_import_service import import_control_list
from tests.conftest import auth_headers, insert_returning_id, table_exists
from tests.test_import_hr_control_list import _build_sample_workbook


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _phase_2f_available() -> bool:
    with engine.begin() as conn:
        return table_exists(conn, "department_recoding")


def _ai_drafts_available() -> bool:
    with engine.begin() as conn:
        return table_exists(conn, "hr_import_ai_extraction_drafts")


def _require_phase_2f() -> None:
    if not _phase_2f_available():
        pytest.skip("Phase 2F migration not applied — run alembic upgrade head")


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def staged_batch(seed, tmp_path: Path):
    _require_phase_2f()
    source = tmp_path / f"phase2f_{uuid4().hex[:8]}.xlsx"
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


def test_infer_department_group():
    assert infer_department_group(import_name="АДМИНИСТРАТИВНЫЙ ПЕРСОНАЛ", org_unit_name="Администрация") == "ADMINISTRATIVE"
    assert infer_department_group(import_name="КДЛ", org_unit_name="КДЛ") == "PARACLINICAL"
    assert infer_department_group(import_name="ОТДЕЛЕНИЕ ХИМИОТЕРАПИИ", org_unit_name="Химиотерапия 1") == "CLINICAL"


def test_infer_staff_type_from_position():
    assert _infer_staff_type({"sheet_type": "part_time", "position_raw": "врач-онколог"}) == "doctors"
    assert _infer_staff_type({"sheet_type": "nurses", "position_raw": "м/с"}) == "nurses"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_seed_department_recoding():
    _require_phase_2f()
    with engine.begin() as conn:
        result = seed_department_recoding(conn)
        count = int(
            conn.execute(text("SELECT COUNT(*) FROM public.department_recoding")).scalar_one()
        )
    assert result["inserted"] + result.get("updated", 0) >= 1 or count >= 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_personnel_filters_by_staff_type(staged_batch):
    with engine.connect() as conn:
        doctors = list_batch_rows(conn, staged_batch, roster_scope="personnel", staff_type="doctors")
        assert doctors["total"] >= 0
        for item in doctors["items"]:
            assert item.get("staff_type") == "doctors"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_row_review_detail(staged_batch):
    with engine.connect() as conn:
        rows = list_batch_rows(conn, staged_batch, roster_scope="personnel", limit=1)
        assert rows["total"] >= 1
        row_id = rows["items"][0]["row_id"]
        detail = get_row_review_detail(conn, staged_batch, row_id)
    assert detail["row_id"] == row_id
    assert "education" in detail
    assert "experience_raw" in detail
    assert "training" in detail


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_education_portfolio(staged_batch):
    with engine.connect() as conn:
        portfolio = education_portfolio(conn, staged_batch)
    assert "education" in portfolio
    assert "training" in portfolio
    assert "categories" in portfolio
    assert "certificates" in portfolio


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_review_api(client: TestClient, privileged_headers, staged_batch):
    with engine.connect() as conn:
        row_id = list_batch_rows(conn, staged_batch, roster_scope="personnel", limit=1)["items"][0]["row_id"]
    resp = client.get(
        f"/directory/personnel/import/batches/{staged_batch}/rows/{row_id}/review",
        headers=privileged_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["row_id"] == row_id


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_recoding_options_api(client: TestClient, privileged_headers, staged_batch):
    resp = client.get("/directory/personnel/import/department-recoding/options", headers=privileged_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "groups" in body
    assert "departments" in body


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_declarations_export_api(client: TestClient, privileged_headers, staged_batch):
    resp = client.get(
        f"/directory/personnel/import/batches/{staged_batch}/declarations/export",
        headers=privileged_headers,
    )
    assert resp.status_code == 200, resp.text
    assert "spreadsheetml" in resp.headers.get("content-type", "")


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_many_aliases_one_canonical_department():
    """Three import aliases → one canonical org unit; filter by org_unit_id returns all."""
    _require_phase_2f()
    canonical_name = f"Test Canonical {uuid4().hex[:6]}"
    aliases = [
        f"ОТДЕЛЕНИЕ ХИРУРГИИ № 3 {uuid4().hex[:4]}",
        f"Хирургия № 3 {uuid4().hex[:4]}",
        f"ОТДЕЛЕНИЕ ОПУХОЛИ ГОЛОВЫ И ШЕИ {uuid4().hex[:4]}",
    ]
    org_unit_id: int | None = None
    with engine.begin() as conn:
        org_unit_id = insert_returning_id(
            conn,
            table="org_units",
            id_col="unit_id",
            values={"name": canonical_name, "code": f"TEST_{uuid4().hex[:8]}", "is_active": True},
        )
        for alias in aliases:
            conn.execute(
                text(
                    """
                    INSERT INTO public.department_recoding (
                        import_department_name, org_unit_id, org_unit_name,
                        department_group, is_active
                    )
                    VALUES (:alias, :org_unit_id, :canonical, 'CLINICAL', TRUE)
                    """
                ),
                {"alias": alias, "org_unit_id": org_unit_id, "canonical": canonical_name},
            )
    try:
        with engine.connect() as conn:
            for alias in aliases:
                rec = lookup_recoding(conn, alias)
                assert rec is not None
                assert rec["org_unit_name"] == canonical_name
                assert int(rec["org_unit_id"]) == org_unit_id

            options = list_recoding_options(conn)
            matching = [
                d for d in options["departments"] if d["org_unit_id"] == org_unit_id
            ]
            assert len(matching) == 1
            assert matching[0]["org_unit_name"] == canonical_name
            assert matching[0]["alias_count"] >= 3
    finally:
        with engine.begin() as conn:
            for alias in aliases:
                conn.execute(
                    text(
                        "DELETE FROM public.department_recoding WHERE import_department_name = :alias"
                    ),
                    {"alias": alias},
                )
            conn.execute(text("DELETE FROM public.org_units WHERE unit_id = :id"), {"id": org_unit_id})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_lookup_recoding_exact_match_only():
    _require_phase_2f()
    alias = f"Exact Alias Only {uuid4().hex[:8]}"
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO public.department_recoding (
                    import_department_name, org_unit_id, org_unit_name,
                    department_group, is_active
                )
                VALUES (:alias, NULL, 'Exact Canonical', 'CLINICAL', TRUE)
                """
            ),
            {"alias": alias},
        )
    try:
        with engine.connect() as conn:
            assert lookup_recoding(conn, alias) is not None
            assert lookup_recoding(conn, alias[:10]) is None
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public.department_recoding WHERE import_department_name = :alias"),
                {"alias": alias},
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_row_review_profile_structure(staged_batch):
    with engine.connect() as conn:
        rows = list_batch_rows(conn, staged_batch, roster_scope="personnel", limit=1)
        detail = get_row_review_detail(conn, staged_batch, rows["items"][0]["row_id"])
    assert "profile" in detail
    assert "basic" in detail["profile"]
    assert "education_records" in detail["profile"]
    assert "training_records" in detail["profile"]
    assert "category_records" in detail["profile"]
    assert "certificate_records" in detail["profile"]
    assert "award_records" in detail["profile"]
    assert "department_source" in detail
    assert detail["profile"]["basic"]["department_source"] == detail["department"]


def test_build_import_profile_education_sections():
    profile = build_import_profile(
        {
            "full_name": "Test User",
            "education_raw": "КазНМУ, 2010; ординатура онкология 2013",
            "diploma_specialty_raw": "Лечебное дело",
            "certification_raw": "высшая категория 2020",
            "degree_raw": "кандидат медицинских наук",
            "awards_raw": "Почётная грамота 2019",
        }
    )
    assert profile["basic"]["full_name"] == "Test User"
    assert len(profile["education_records"]) >= 1
    assert profile["degrees"]["candidate_medical_sciences"] is True
    assert len(profile["award_records"]) >= 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_ai_extraction_draft_without_llm(staged_batch, monkeypatch):
    if not _ai_drafts_available():
        pytest.skip("AI extraction migration not applied")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with engine.connect() as conn:
        row_id = list_batch_rows(conn, staged_batch, roster_scope="personnel", limit=1)["items"][0]["row_id"]
    with engine.begin() as conn:
        draft = run_ai_extraction(conn, staged_batch, row_id)
    assert draft["requires_review"] is True
    assert draft["review_label"] == "AI-предложение. Требуется проверка."
    assert isinstance(draft["extraction"], dict)
    for key in ("education", "training", "certificates", "categories", "awards", "degrees", "warnings"):
        assert key in draft["extraction"]
    assert any("OPENAI_API_KEY" in w for w in draft["extraction"]["warnings"])


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_ai_extraction_api(client: TestClient, privileged_headers, staged_batch, monkeypatch):
    if not _ai_drafts_available():
        pytest.skip("AI extraction migration not applied")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with engine.connect() as conn:
        row_id = list_batch_rows(conn, staged_batch, roster_scope="personnel", limit=1)["items"][0]["row_id"]
    resp = client.post(
        f"/directory/personnel/import/batches/{staged_batch}/rows/{row_id}/ai-extraction",
        headers=privileged_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["requires_review"] is True
    assert "extraction" in body
