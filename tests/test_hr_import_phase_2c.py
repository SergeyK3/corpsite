"""Tests for HR Import Phase 2C — risk fix and document candidates."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.hr_import import (
    CLASSIFICATION_DECLARATION,
    CLASSIFICATION_NORMAL,
    CLASSIFICATION_SUMMARY_ROW,
)
from app.services.hr_import_analytics_service import (
    batch_summary,
    is_declaration_no_iin_row,
    is_missing_iin_employee_row,
    is_real_employee_row,
    is_technical_no_iin_row,
    risk_analytics,
)
from app.services.hr_import_document_parser import parse_education_raw
from app.services.hr_import_document_parser import (
    parse_certification_raw,
    parse_training_fragment,
    parse_training_raw,
    split_raw_fragments,
)
from app.services.hr_import_document_candidate_service import (
    list_document_candidates,
    parse_and_persist_document_candidates,
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
        cols = {c["name"] for c in conn.execute(text("""
            SELECT column_name AS name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'hr_import_document_candidates'
        """)).mappings()}
        return "batch_id" in cols and "raw_text" in cols


def _require_phase_2c() -> None:
    if not _phase_2c_available():
        pytest.skip("Phase 2C migration not applied — run alembic upgrade head")


def _delete_batch(conn, batch_id: int) -> None:
    conn.execute(
        text("DELETE FROM public.hr_import_batches WHERE batch_id = :batch_id"),
        {"batch_id": batch_id},
    )


def _employee_doc_count(conn) -> int:
    if not table_exists(conn, "employee_documents"):
        return 0
    return int(conn.execute(text("SELECT COUNT(*) FROM public.employee_documents")).scalar_one())


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def staged_batch(seed, tmp_path: Path):
    _require_phase_2c()
    source = tmp_path / f"phase2c_{uuid4().hex[:8]}.xlsx"
    _build_sample_workbook(source)
    with engine.begin() as conn:
        before_docs = _employee_doc_count(conn)
        batch_id, _, _ = import_control_list(
            conn,
            file_path=source,
            imported_by=int(seed["initiator_user_id"]),
        )
        after_docs = _employee_doc_count(conn)
    yield batch_id, before_docs, after_docs
    with engine.begin() as conn:
        _delete_batch(conn, batch_id)


def test_parser_education_uses_registry_type():
    parsed = parse_education_raw("КазНМУ, 1982", "Лечебное дело")
    assert len(parsed) == 1
    item = parsed[0]
    assert item.document_kind == "education"
    assert item.proposed_document_type == "EDUCATION_GRADUATION"
    assert item.category == "EDUCATION"
    assert item.organization == "КазНМУ"
    assert item.specialty == "Лечебное дело"
    assert item.parsed_issued_at is not None
    assert item.parsed_issued_at.year == 1982


def test_director_row_not_in_missing_iin_risk():
    row = {
        "classification": CLASSIFICATION_NORMAL,
        "sheet_type": "doctors",
        "iin": "580131300091",
        "full_name": "Тулеутаев Мухтар Есетжанович",
        "has_training": False,
        "has_certification": False,
        "department": "АДМИНИСТРАТИВНЫЙ ПЕРСОНАЛ",
    }
    assert not is_missing_iin_employee_row(row)


def test_is_real_employee_row_excludes_technical():
    assert not is_real_employee_row(
        {"classification": CLASSIFICATION_DECLARATION, "sheet_type": "doctors", "iin": ""}
    )
    assert not is_real_employee_row(
        {"classification": CLASSIFICATION_SUMMARY_ROW, "sheet_type": "doctors", "iin": ""}
    )
    assert not is_real_employee_row({"classification": CLASSIFICATION_NORMAL, "sheet_type": "declaration", "iin": ""})
    assert is_real_employee_row({"classification": CLASSIFICATION_NORMAL, "sheet_type": "doctors", "iin": ""})


def test_missing_iin_vs_technical_no_iin():
    employee = {
        "classification": CLASSIFICATION_NORMAL,
        "sheet_type": "doctors",
        "row_type": "EMPLOYEE",
        "is_employee_roster": True,
        "iin": "",
    }
    summary = {
        "classification": CLASSIFICATION_SUMMARY_ROW,
        "sheet_type": "doctors",
        "row_type": "SUMMARY_ROW",
        "is_employee_roster": False,
        "iin": "",
    }
    declaration = {
        "classification": CLASSIFICATION_DECLARATION,
        "sheet_type": "declaration",
        "row_type": "DECLARATION_ROW",
        "is_employee_roster": False,
        "iin": "",
    }

    assert is_missing_iin_employee_row(employee)
    assert not is_missing_iin_employee_row(summary)
    assert not is_missing_iin_employee_row(declaration)
    assert is_technical_no_iin_row(summary)
    assert is_declaration_no_iin_row(declaration)
    assert not is_technical_no_iin_row(declaration)


def test_parser_split_and_hours():
    fragments = split_raw_fragments("2024 курс ПК 72 ч; 2023 семинар 36ч")
    assert len(fragments) == 2
    parsed = parse_training_raw("2024 курс ПК 72 ч")
    assert len(parsed) == 1
    assert parsed[0].parsed_hours == Decimal("72")
    assert parsed[0].parsed_issued_at == date(2024, 1, 1)


def test_parser_date_dmy():
    parsed = parse_training_fragment("ПК до 31.12.2026 144 ч", fragment_index=0)
    assert parsed.parsed_valid_until == date(2026, 12, 31)
    assert parsed.parsed_hours == Decimal("144")


def test_parser_certification_category():
    parsed = parse_certification_raw("высшая категория № 123/45 до 01.06.2028")
    assert len(parsed) == 1
    assert parsed[0].category == "highest"
    assert parsed[0].certificate_number == "123/45"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_missing_iin_excludes_declaration_and_summary(seed):
    _require_phase_2c()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        batch_id = conn.execute(
            text(
                """
                INSERT INTO public.hr_import_batches (
                    source_type, file_name, imported_by, status,
                    total_rows, valid_rows, error_rows
                )
                VALUES ('HR_CONTROL_LIST', :file_name, :uid, 'PARSED', 3, 3, 0)
                RETURNING batch_id
                """
            ),
            {"file_name": f"risk_{suffix}.xlsx", "uid": int(seed["initiator_user_id"])},
        ).scalar_one()

        for sheet, row_num, payload in (
            (
                "doctors",
                1,
                {
                    "full_name": "Real Employee",
                    "iin": "",
                    "department": "X",
                        "metadata": {
                            "classification": CLASSIFICATION_NORMAL,
                            "sheet_type": "doctors",
                            "iin_valid": False,
                            "row_type": "EMPLOYEE",
                            "is_employee_roster": True,
                        },
                    },
                ),
                (
                    "doctors",
                    2,
                    {
                        "full_name": "",
                        "iin": "",
                        "metadata": {
                            "classification": CLASSIFICATION_SUMMARY_ROW,
                            "sheet_type": "doctors",
                            "iin_valid": False,
                            "row_type": "SUMMARY_ROW",
                            "is_employee_roster": False,
                        },
                    },
                ),
                (
                    "declaration",
                    3,
                    {
                        "full_name": "Decl",
                        "iin": "",
                        "metadata": {
                            "classification": CLASSIFICATION_DECLARATION,
                            "sheet_type": "declaration",
                            "iin_valid": False,
                            "row_type": "DECLARATION_ROW",
                            "is_employee_roster": False,
                            "declaration_group": "doctors",
                        },
                    },
                ),
        ):
            conn.execute(
                text(
                    """
                    INSERT INTO public.hr_import_rows (
                        batch_id, source_sheet, source_row_number,
                        raw_payload, normalized_payload,
                        match_status, review_status
                    )
                    VALUES (
                        :batch_id, :sheet, :row_num,
                        CAST(:raw AS jsonb), CAST(:norm AS jsonb),
                        'NOT_PROCESSED', 'PENDING'
                    )
                    """
                ),
                {
                    "batch_id": batch_id,
                    "sheet": sheet,
                    "row_num": row_num,
                    "raw": "{}",
                    "norm": __import__("json").dumps(payload, ensure_ascii=False),
                },
            )

        summary = batch_summary(conn, batch_id)
        risks = {r["risk_type"]: r["count"] for r in risk_analytics(conn, batch_id)["items"]}

    assert summary["missing_iin"] == 1
    assert summary["technical_no_iin_rows"] == 1
    assert summary["declaration_no_iin_rows"] == 1
    assert risks["missing_iin"] == 1
    assert risks["technical_no_iin"] == 1
    assert risks["declaration_no_iin"] == 1

    with engine.begin() as conn:
        _delete_batch(conn, int(batch_id))


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_document_candidates_created_from_training_raw(staged_batch):
    batch_id, before_docs, after_docs = staged_batch
    with engine.connect() as conn:
        result = list_document_candidates(conn, batch_id, document_kind="training")
    assert after_docs == before_docs
    assert result["total"] >= 1
    first = result["items"][0]
    assert first["document_kind"] == "training"
    assert first["raw_text"]
    assert "iin" in first
    assert "iin_masked" not in first
    iin = first.get("iin") or ""
    if iin:
        assert "****" not in iin


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_candidates_api_returns_full_iin(client: TestClient, privileged_headers, staged_batch):
    batch_id, _, _ = staged_batch
    resp = client.get(
        f"/directory/personnel/import/batches/{batch_id}/document-candidates?limit=20",
        headers=privileged_headers,
    )
    assert resp.status_code == 200, resp.text
    for item in resp.json()["items"]:
        assert "iin" in item
        assert "iin_masked" not in item
        iin = item.get("iin") or ""
        if iin:
            assert "****" not in iin


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_no_employee_documents_created(staged_batch):
    _, before_docs, after_docs = staged_batch
    assert after_docs == before_docs


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_rebuild_candidates_idempotent(staged_batch):
    batch_id, _, _ = staged_batch
    with engine.begin() as conn:
        first = parse_and_persist_document_candidates(conn, batch_id)
        second = parse_and_persist_document_candidates(conn, batch_id)
    assert first["total_candidates"] == second["total_candidates"]
