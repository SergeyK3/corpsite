"""Tests for HR import analytics API and service (Analytics MVP)."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.services.hr_import_analytics_service import (
    age_distribution,
    batch_summary,
    certification_analytics,
    department_analytics,
    list_batch_rows,
    risk_analytics,
    training_analytics,
)
from app.services.hr_import_service import import_control_list
from tests.conftest import auth_headers, table_exists
from tests.hr_import_fixtures import cleanup_import_batch, write_control_list_workbook


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _phase_2b_available() -> bool:
    with engine.begin() as conn:
        return table_exists(conn, "hr_import_batches") and table_exists(conn, "hr_import_rows")


def _require_phase_2b() -> None:
    if not _phase_2b_available():
        pytest.skip("HR import staging tables missing — run alembic upgrade head")


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def staged_batch(seed, tmp_path: Path):
    _require_phase_2b()
    source = write_control_list_workbook(tmp_path, yymm="2606")
    with engine.begin() as conn:
        batch_id, _, _ = import_control_list(
            conn,
            file_path=source,
            imported_by=int(seed["initiator_user_id"]),
        )
    yield batch_id
    with engine.begin() as conn:
        cleanup_import_batch(conn, batch_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_summary_counts_total(staged_batch):
    with engine.connect() as conn:
        summary = batch_summary(conn, staged_batch)
    assert summary["batch_id"] == staged_batch
    assert summary["total_rows"] >= 5
    assert summary["valid_iin"] >= 4
    assert summary["duplicate_iin_groups"] >= 1
    assert "doctors" in summary["by_sheet_type"]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_age_distribution_groups(staged_batch):
    with engine.connect() as conn:
        result = age_distribution(conn, staged_batch)
        summary = batch_summary(conn, staged_batch)
    keys = {b["key"] for b in result["buckets"]}
    assert keys == {"under_30", "30_39", "40_49", "50_59", "60_64", "65_plus"}
    assert sum(b["count"] for b in result["buckets"]) + result["unknown"] == summary.get(
        "employee_roster_rows", summary["total_rows"]
    )
    assert sum(b["count"] for b in result["buckets"]) >= 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_department_analytics_groups(staged_batch):
    with engine.connect() as conn:
        result = department_analytics(conn, staged_batch)
    assert result["items"]
    first = result["items"][0]
    assert "department" in first
    assert first["total"] >= 1
    assert "average_age" in first


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_training_analytics_counts_training_raw(staged_batch):
    with engine.connect() as conn:
        training = training_analytics(conn, staged_batch)
        summary = batch_summary(conn, staged_batch)
    assert training["total_with_training"] == summary["with_training"]
    assert training["total_with_training"] >= 1
    assert training["examples"]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_certification_analytics_counts_certification_raw(staged_batch):
    with engine.connect() as conn:
        cert = certification_analytics(conn, staged_batch)
        summary = batch_summary(conn, staged_batch)
    assert cert["total_with_certification"] == summary["with_certification"]
    assert cert["total_with_certification"] >= 1
    groups = {g["group"]: g["count"] for g in cert["by_group"]}
    assert groups["none"] >= 0


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_risks_counts_invalid_missing_duplicates_65plus(staged_batch):
    with engine.connect() as conn:
        risks = risk_analytics(conn, staged_batch)
        summary = batch_summary(conn, staged_batch)
    by_type = {r["risk_type"]: r["count"] for r in risks["items"]}
    assert by_type["duplicate_iin"] == summary["duplicate_iin_rows"]
    assert by_type["invalid_iin"] >= 0
    assert by_type["missing_iin"] >= 0
    assert "age_65_plus" in by_type


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_rows_return_full_iin(staged_batch):
    with engine.connect() as conn:
        result = list_batch_rows(conn, staged_batch, limit=50)
    assert result["total"] >= 5
    for item in result["items"]:
        iin = item.get("iin", "")
        assert "iin_masked" not in item
        if iin and iin != "***":
            assert "****" not in iin
            assert len(iin) == 12 or not iin.isdigit()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_batches_route(client: TestClient, privileged_headers, staged_batch):
    resp = client.get("/directory/personnel/import/batches", headers=privileged_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ids = {item["batch_id"] for item in body["items"]}
    assert staged_batch in ids


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_summary_route(client: TestClient, privileged_headers, staged_batch):
    resp = client.get(
        f"/directory/personnel/import/batches/{staged_batch}/summary",
        headers=privileged_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_rows"] >= 5


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_rows_route_returns_full_iin(client: TestClient, privileged_headers, staged_batch):
    resp = client.get(
        f"/directory/personnel/import/batches/{staged_batch}/rows?limit=10",
        headers=privileged_headers,
    )
    assert resp.status_code == 200, resp.text
    for item in resp.json()["items"]:
        assert "iin" in item
        assert "iin_masked" not in item
        iin = item.get("iin") or ""
        if iin and iin != "***":
            assert "****" not in iin


def test_calc_category_validity_note_active():
    from datetime import date

    from app.services.hr_import_analytics_service import calc_record_validity_note

    note = calc_record_validity_note("2022-01-15", on=date(2024, 6, 17))
    assert note.startswith("осталось ")
    years_part = note.split("осталось ", 1)[1].removesuffix(" лет")
    assert years_part == "2,6"


def test_calc_category_validity_note_expired():
    from datetime import date

    from app.services.hr_import_analytics_service import (
        CATEGORY_VALIDITY_EXPIRED_NOTE,
        calc_category_validity_note,
    )

    note = calc_category_validity_note("2018-01-01", on=date(2026, 6, 17))
    assert note == CATEGORY_VALIDITY_EXPIRED_NOTE


def test_calc_category_validity_note_year_only_date():
    from datetime import date

    from app.services.hr_import_analytics_service import calc_category_validity_note

    note = calc_category_validity_note("2019", on=date(2026, 6, 17))
    assert note == "утратила силу"
