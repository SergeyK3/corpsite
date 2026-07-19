# tests/test_mrd_hr_review_api.py
"""REST API smoke tests for HR review endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.mrd.infrastructure.repository import mrd_tables_available
from tests.conftest import auth_headers
from tests.mrd_helpers import (
    mrd_command_table_available,
    purge_mrd_report_period,
    seed_active_mrd,
    seed_mrd_entry,
    unique_report_period,
)


client = TestClient(app)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_mrd_schema() -> None:
    with engine.connect() as conn:
        if not mrd_tables_available(conn):
            pytest.skip("MRD schema missing")
        if not mrd_command_table_available(conn):
            pytest.skip("MRD command idempotency schema missing")


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
def personnel_admin_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def hr_review_api_seed(seed):
    _require_mrd_schema()
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    with engine.begin() as conn:
        org_unit_id = _org_unit_id(conn)
        purge_mrd_report_period(conn, period)
        mrd_id = seed_active_mrd(conn, report_period=period, created_by=user_id)
        seed_mrd_entry(
            conn,
            mrd_id=mrd_id,
            match_key="emp:9001",
            payload={
                "full_name": "Иванова А.А.",
                "position_raw": "Медсестра",
                "org_unit_id": org_unit_id,
            },
        )
        seed_mrd_entry(
            conn,
            mrd_id=mrd_id,
            match_key="emp:9002",
            payload={
                "full_name": "Петров П.П.",
                "position_raw": "Врач",
                "org_unit_id": org_unit_id,
            },
        )
    payload = {"mrd_id": mrd_id, "period": period, "org_unit_id": org_unit_id}
    yield payload
    with engine.begin() as conn:
        purge_mrd_report_period(conn, period)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_hr_review_api_org_structure(personnel_admin_headers, hr_review_api_seed) -> None:
    resp = client.get(
        f"/directory/personnel/monthly-references/{hr_review_api_seed['mrd_id']}/hr-review",
        headers=personnel_admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["employees"]["total"] == 0
    assert len(body["org_groups"]) >= 1
    assert len(body["departments"]) >= 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_hr_review_api_department_employees(personnel_admin_headers, hr_review_api_seed) -> None:
    resp = client.get(
        f"/directory/personnel/monthly-references/{hr_review_api_seed['mrd_id']}/hr-review",
        headers=personnel_admin_headers,
        params={"org_unit_id": hr_review_api_seed["org_unit_id"], "changed_only": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["employees"]["total"] == 2
    assert body["department_summary"]["total_employees"] == 2


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_hr_review_api_search(personnel_admin_headers, hr_review_api_seed) -> None:
    resp = client.get(
        f"/directory/personnel/monthly-references/{hr_review_api_seed['mrd_id']}/hr-review",
        headers=personnel_admin_headers,
        params={
            "org_unit_id": hr_review_api_seed["org_unit_id"],
            "changed_only": False,
            "search": "Петров",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["employees"]["total"] == 1
    assert body["employees"]["items"][0]["full_name"] == "Петров П.П."
