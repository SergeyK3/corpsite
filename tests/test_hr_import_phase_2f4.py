"""Tests for HR Import Phase 2F.4 — editable section overrides."""
from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.services.hr_import_education_profile_service import (
    get_education_profile,
    list_education_profiles,
    update_education_profile,
)
from app.services.employee_import_profile_override_service import load_employee_override
from app.services.hr_import_employee_card_service import get_employee_import_card, save_employee_import_card
from app.services.hr_import_profile_override_service import apply_profile_override, extract_editable_sections_override
from app.services.hr_import_service import import_control_list
from tests.conftest import auth_headers, get_columns, insert_returning_id, table_exists
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
        pytest.skip("profile staging columns not available — run alembic upgrade head")


def _create_employee(conn, *, full_name: str, org_unit_id: int) -> int:
    cols = get_columns(conn, "employees")
    values = {"full_name": full_name}
    if "org_unit_id" in cols:
        values["org_unit_id"] = org_unit_id
    if "is_active" in cols:
        values["is_active"] = True
    return insert_returning_id(conn, table="employees", id_col="employee_id", values=values)


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def staged_batch(seed, tmp_path: Path):
    _require_profile_staging()
    source = tmp_path / f"phase2f4_{uuid4().hex[:8]}.xlsx"
    _build_sample_workbook(source)
    with engine.begin() as conn:
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


def _profile_id(staged_batch: int) -> int:
    with engine.connect() as conn:
        return int(list_education_profiles(conn, staged_batch, limit=1)["items"][0]["profile_id"])


def _stored_override(staged_batch: int, profile_id: int) -> dict:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT profile_override
                FROM public.hr_import_rows
                WHERE batch_id = :batch_id AND row_id = :row_id
                """
            ),
            {"batch_id": staged_batch, "row_id": profile_id},
        ).scalar_one()
    return dict(row or {})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_patch_saves_training_override(staged_batch):
    profile_id = _profile_id(staged_batch)
    training_override = {
        "training": [
            {
                "title": "Менеджмент здравоохранения",
                "organization": "Стратегический менеджмент",
                "year": "15.03.2018",
                "hours": 54,
            },
            {
                "title": "Риск менеджмент",
                "organization": "КазНМУ",
                "year": "20.06.2020",
                "hours": 108,
            },
        ]
    }
    with engine.begin() as conn:
        update_education_profile(conn, staged_batch, profile_id, profile=training_override)
    stored = _stored_override(staged_batch, profile_id)
    assert stored["training"][0]["date"] == "2018-03-15"
    assert stored["training"][1]["date"] == "2020-06-20"
    assert "year" not in stored["training"][0]
    with engine.connect() as conn:
        detail = get_education_profile(conn, staged_batch, profile_id)
    assert len(detail["profile"]["training_records"]) == 2
    assert detail["profile"]["training_records"][0]["title"] == "Менеджмент здравоохранения"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_patch_saves_categories_override(staged_batch):
    profile_id = _profile_id(staged_batch)
    categories_override = {
        "categories": [
            {"category": "Высшая", "date": "15.03.2019", "specialty": "Терапия"},
        ]
    }
    with engine.begin() as conn:
        update_education_profile(conn, staged_batch, profile_id, profile=categories_override)
    stored = _stored_override(staged_batch, profile_id)
    assert stored["categories"][0]["category"] == "Высшая"
    assert stored["categories"][0]["date"] == "2019-03-15"
    with engine.connect() as conn:
        detail = get_education_profile(conn, staged_batch, profile_id)
    assert detail["profile"]["category_records"][0]["category"] == "Высшая"
    assert detail["profile"]["category_records"][0]["issued_at"] == "2019-03-15"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_patch_saves_certificates_override(staged_batch):
    profile_id = _profile_id(staged_batch)
    certificates_override = {
        "certificates": [
            {
                "kind": "Сертификат",
                "topic": "Кардиология",
                "date": "2021-05-10",
                "hours": 72,
                "link": "https://example.org/cert",
            }
        ]
    }
    with engine.begin() as conn:
        update_education_profile(conn, staged_batch, profile_id, profile=certificates_override)
    stored = _stored_override(staged_batch, profile_id)
    assert stored["certificates"][0]["topic"] == "Кардиология"
    with engine.connect() as conn:
        detail = get_education_profile(conn, staged_batch, profile_id)
    assert detail["profile"]["certificate_records"][0]["topic"] == "Кардиология"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_patch_saves_degree_awards_notes_override(staged_batch):
    profile_id = _profile_id(staged_batch)
    override = {
        "degree": [{"label": "Кандидат медицинских наук", "date": "15.03.2015"}],
        "awards": [{"title": "Почётная грамота", "date": "01.05.2022"}],
        "notes": "декрет до 2026",
    }
    with engine.begin() as conn:
        update_education_profile(conn, staged_batch, profile_id, profile=override)
    stored = _stored_override(staged_batch, profile_id)
    assert stored["degree"][0]["label"] == "Кандидат медицинских наук"
    assert stored["degree"][0]["date"] == "2015-03-15"
    assert stored["awards"][0]["title"] == "Почётная грамота"
    assert stored["awards"][0]["date"] == "2022-05-01"
    assert stored["notes"] == "декрет до 2026"
    with engine.connect() as conn:
        detail = get_education_profile(conn, staged_batch, profile_id)
    assert "Кандидат" in detail["profile"]["degrees"]["raw_text"]
    assert detail["profile"]["degrees"]["records"][0]["label"] == "Кандидат медицинских наук"
    assert detail["profile"]["degrees"]["records"][0]["completed_at"] == "2015-03-15"
    assert detail["profile"]["award_records"][0]["title"] == "Почётная грамота"
    assert detail["profile"]["award_records"][0]["date"] == "2022-05-01"
    assert detail["profile"]["notes_raw"] == "декрет до 2026"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_get_returns_merged_raw_plus_override(staged_batch):
    profile_id = _profile_id(staged_batch)
    with engine.connect() as conn:
        before = get_education_profile(conn, staged_batch, profile_id)
        base_name = before["profile"]["basic"]["full_name"]
    with engine.begin() as conn:
        update_education_profile(
            conn,
            staged_batch,
            profile_id,
            profile={"notes": "staging note", "training": [{"title": "Курс", "organization": "", "year": "2024", "hours": 24}]},
        )
    with engine.connect() as conn:
        after = get_education_profile(conn, staged_batch, profile_id)
    assert after["profile"]["basic"]["full_name"] == base_name
    assert after["profile"]["notes_raw"] == "staging note"
    assert after["profile"]["training_records"][0]["title"] == "Курс"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_highest_category_displayed_as_vysshaya(staged_batch):
    profile_id = _profile_id(staged_batch)
    with engine.begin() as conn:
        update_education_profile(
            conn,
            staged_batch,
            profile_id,
            profile={"categories": [{"category": "highest", "date": "2020", "specialty": ""}]},
        )
    with engine.connect() as conn:
        detail = get_education_profile(conn, staged_batch, profile_id)
    assert detail["profile"]["category_records"][0]["category"] == "Высшая"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_save_does_not_create_employees_documents_or_events(staged_batch, seed):
    profile_id = _profile_id(staged_batch)
    with engine.connect() as conn:
        before_employees = int(conn.execute(text("SELECT COUNT(*) FROM public.employees")).scalar_one())
        before_docs = int(conn.execute(text("SELECT COUNT(*) FROM public.employee_documents")).scalar_one())
        before_events = 0
        if table_exists(conn, "employee_events"):
            before_events = int(conn.execute(text("SELECT COUNT(*) FROM public.employee_events")).scalar_one())
    with engine.begin() as conn:
        update_education_profile(
            conn,
            staged_batch,
            profile_id,
            profile={
                "training": [{"title": "PK", "organization": "Org", "year": "2023", "hours": 36}],
                "notes": "test",
            },
        )
    with engine.connect() as conn:
        after_employees = int(conn.execute(text("SELECT COUNT(*) FROM public.employees")).scalar_one())
        after_docs = int(conn.execute(text("SELECT COUNT(*) FROM public.employee_documents")).scalar_one())
        after_events = before_events
        if table_exists(conn, "employee_events"):
            after_events = int(conn.execute(text("SELECT COUNT(*) FROM public.employee_events")).scalar_one())
    assert after_employees == before_employees
    assert after_docs == before_docs
    assert after_events == before_events


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_employee_import_card_save_uses_section_override(staged_batch, seed):
    employee_id = None
    with engine.begin() as conn:
        employee_id = _create_employee(
            conn,
            full_name="Иванов Иван Иванович",
            org_unit_id=int(seed["unit_id"]),
        )
        detail = get_employee_import_card(conn, employee_id)
        edited = apply_profile_override(
            detail["profile"],
            {"notes": "комментарий", "degree": "доктор медицинских наук"},
        )
        save_employee_import_card(conn, employee_id, profile=edited)
        employee_override = load_employee_override(conn, employee_id)
    assert employee_override is not None
    override = employee_override["profile_override"]
    assert "notes" in override
    assert "degree" in override
    assert "basic" not in override
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM public.employees WHERE employee_id = :employee_id"), {"employee_id": employee_id})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_education_profile_patch_api(client: TestClient, privileged_headers, staged_batch):
    profile_id = _profile_id(staged_batch)
    resp = client.patch(
        f"/directory/personnel/import/batches/{staged_batch}/education-profiles/{profile_id}",
        headers=privileged_headers,
        json={
            "profile": {
                "training": [{"title": "API курс", "organization": "API org", "year": "2025", "hours": 18}],
                "notes": "api note",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["profile"]["notes_raw"] == "api note"
    assert body["profile"]["training_records"][0]["title"] == "API курс"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_extract_editable_sections_shape(staged_batch):
    with engine.connect() as conn:
        profile_id = _profile_id(staged_batch)
        detail = get_education_profile(conn, staged_batch, profile_id)
        override = extract_editable_sections_override(detail["profile"])
    assert set(override.keys()) == {"education", "training", "categories", "certificates", "degree", "awards", "notes"}
    assert isinstance(override["education"], list)
    assert isinstance(override["degree"], list)
    assert isinstance(override["training"], list)
