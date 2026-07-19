"""Unit/integration tests for HR review read model (db_tx rollback)."""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.mrd.application.hr_review_service import (
    REVIEW_STATUS_PENDING,
    fetch_hr_review,
    hr_review_to_dict,
)
from app.mrd.infrastructure.repository import mrd_tables_available
from tests.mrd_helpers import (
    insert_detected_difference,
    seed_mrd_entry,
    unique_report_period,
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_schema(conn) -> None:
    if not mrd_tables_available(conn):
        pytest.skip("MRD schema missing")


def _org_unit_id(conn) -> int:
    row = conn.execute(
        text(
            """
            SELECT unit_id
            FROM public.org_units
            WHERE COALESCE(is_active, TRUE) = TRUE
              AND group_id IS NOT NULL
            ORDER BY unit_id
            LIMIT 1
            """
        )
    ).scalar_one_or_none()
    if row is None:
        pytest.skip("org_units seed missing")
    return int(row)


@pytest.fixture
def db_tx():
    conn = engine.connect()
    tx = conn.begin()
    try:
        yield conn
    finally:
        tx.rollback()
        conn.close()


def _seed_mrd(conn, *, report_period, created_by: int) -> int:
    row = conn.execute(
        text(
            """
            INSERT INTO public.hr_monthly_references (report_period, version, status, created_by)
            VALUES (:report_period, 1, 'ACTIVE', :created_by)
            RETURNING mrd_id
            """
        ),
        {"report_period": report_period, "created_by": created_by},
    ).scalar_one()
    return int(row)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_hr_review_changed_only_and_difference_fields(seed, db_tx) -> None:
    _require_schema(db_tx)
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    org_unit_id = _org_unit_id(db_tx)
    mrd_id = _seed_mrd(db_tx, report_period=period, created_by=user_id)
    seed_mrd_entry(
        db_tx,
        mrd_id=mrd_id,
        match_key="emp:9101",
        payload={
            "full_name": "Иванова А.А.",
            "position_raw": "Медсестра",
            "org_unit_id": org_unit_id,
        },
    )
    seed_mrd_entry(
        db_tx,
        mrd_id=mrd_id,
        match_key="emp:9102",
        payload={
            "full_name": "Петров П.П.",
            "position_raw": "Врач",
            "org_unit_id": org_unit_id,
        },
    )
    insert_detected_difference(
        db_tx,
        report_period=period,
        mrd_id=mrd_id,
        logical_key=f"{period.isoformat()}|{mrd_id}|emp:9101|position_raw|roster",
        entity_scope="emp:9101",
        attribute="position_raw",
        business_type="PERIOD_CHANGED",
        old_value="Медсестра",
        new_value="Старшая медсестра",
    )

    changed = hr_review_to_dict(
        fetch_hr_review(
            db_tx,
            mrd_id=mrd_id,
            org_unit_id=org_unit_id,
            changed_only=True,
        )
    )
    assert changed["employees"]["total"] == 1
    employee = changed["employees"]["items"][0]
    assert employee["review_status"] == REVIEW_STATUS_PENDING
    diff = employee["differences"][0]
    assert diff["field_label"] == "Должность"
    assert diff["old_value"] == "Медсестра"
    assert diff["detected_value"] == "Старшая медсестра"

    all_rows = hr_review_to_dict(
        fetch_hr_review(
            db_tx,
            mrd_id=mrd_id,
            org_unit_id=org_unit_id,
            changed_only=False,
        )
    )
    assert all_rows["employees"]["total"] == 2
    assert all_rows["department_summary"]["without_changes"] == 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_hr_review_isolates_other_mrd(seed, db_tx) -> None:
    _require_schema(db_tx)
    period_a = unique_report_period()
    period_b = unique_report_period()
    if period_b == period_a:
        period_b = date(period_a.year + (1 if period_a.month == 12 else 0), (period_a.month % 12) + 1, 1)
    user_id = int(seed["initiator_user_id"])
    org_unit_id = _org_unit_id(db_tx)
    mrd_a = _seed_mrd(db_tx, report_period=period_a, created_by=user_id)
    mrd_b = _seed_mrd(db_tx, report_period=period_b, created_by=user_id)
    seed_mrd_entry(
        db_tx,
        mrd_id=mrd_a,
        match_key="emp:9201",
        payload={"full_name": "A", "org_unit_id": org_unit_id, "position_raw": "N1"},
    )
    insert_detected_difference(
        db_tx,
        report_period=period_a,
        mrd_id=mrd_a,
        logical_key=f"{period_a.isoformat()}|{mrd_a}|emp:9201|position_raw|roster",
        entity_scope="emp:9201",
        attribute="position_raw",
        business_type="PERIOD_CHANGED",
        old_value="N1",
        new_value="N2",
    )
    insert_detected_difference(
        db_tx,
        report_period=period_b,
        mrd_id=mrd_b,
        logical_key=f"{period_b.isoformat()}|{mrd_b}|emp:9201|position_raw|roster",
        entity_scope="emp:9201",
        attribute="position_raw",
        business_type="PERIOD_CHANGED",
        old_value="X",
        new_value="Y",
    )

    payload = hr_review_to_dict(
        fetch_hr_review(db_tx, mrd_id=mrd_a, org_unit_id=org_unit_id, changed_only=True)
    )
    assert payload["employees"]["items"][0]["differences"][0]["old_value"] == "N1"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_hr_review_pagination(seed, db_tx) -> None:
    _require_schema(db_tx)
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    org_unit_id = _org_unit_id(db_tx)
    mrd_id = _seed_mrd(db_tx, report_period=period, created_by=user_id)
    for idx in range(3):
        seed_mrd_entry(
            db_tx,
            mrd_id=mrd_id,
            match_key=f"emp:930{idx}",
            payload={"full_name": f"Emp {idx}", "org_unit_id": org_unit_id, "position_raw": "P"},
        )
    page = hr_review_to_dict(
        fetch_hr_review(
            db_tx,
            mrd_id=mrd_id,
            org_unit_id=org_unit_id,
            changed_only=False,
            limit=2,
            offset=1,
        )
    )
    assert page["employees"]["total"] == 3
    assert len(page["employees"]["items"]) == 2
