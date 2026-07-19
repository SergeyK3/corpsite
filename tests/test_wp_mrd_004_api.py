# tests/test_wp_mrd_004_api.py
"""REST API tests for WP-MRD-004 MRD fork endpoints."""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.mrd.infrastructure.repository import mrd_tables_available
from tests.conftest import auth_headers
from tests.mrd_helpers import mrd_command_table_available, purge_mrd_report_period, seed_active_mrd, seed_mrd_entry, unique_report_period
from app.mrd.domain.period_window import get_creation_window_periods


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


@pytest.fixture
def personnel_admin_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def seeded_mrd(seed):
    _require_mrd_schema()
    period = unique_report_period()
    user_id = int(seed["initiator_user_id"])
    with engine.begin() as conn:
        purge_mrd_report_period(conn, period)
        mrd_id = seed_active_mrd(conn, report_period=period, created_by=user_id)
        seed_mrd_entry(conn, mrd_id=mrd_id, match_key="emp:api", payload={"position_raw": "Nurse"})
    payload = {"report_period": period.isoformat(), "mrd_id": mrd_id, "user_id": user_id, "period": period}
    yield payload
    with engine.begin() as conn:
        target_period = payload.get("_target_period")
        if target_period is not None:
            purge_mrd_report_period(conn, target_period)
        purge_mrd_report_period(conn, period)


def _command_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_get_active_mrd(personnel_admin_headers, seeded_mrd) -> None:
    resp = client.get(
        "/directory/personnel/monthly-references/active",
        params={"report_period": seeded_mrd["report_period"][:7]},
        headers=personnel_admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["active"]["mrd_id"] == seeded_mrd["mrd_id"]
    assert body["active"]["status"] == "ACTIVE"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_period_versions(personnel_admin_headers, seeded_mrd) -> None:
    resp = client.get(
        "/directory/personnel/monthly-references",
        params={"report_period": seeded_mrd["report_period"]},
        headers=personnel_admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["active"]["mrd_id"] == seeded_mrd["mrd_id"]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_fork_sources(personnel_admin_headers, seeded_mrd) -> None:
    resp = client.get(
        "/directory/personnel/monthly-references/fork-sources",
        headers=personnel_admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert any(item["mrd_id"] == seeded_mrd["mrd_id"] for item in body["items"])


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_fork_version_api(personnel_admin_headers, seeded_mrd) -> None:
    command_id = _command_id("api-fork-v")
    resp = client.post(
        "/directory/personnel/monthly-references/fork-version",
        headers=personnel_admin_headers,
        json={
            "command_id": command_id,
            "source_mrd_id": seeded_mrd["mrd_id"],
            "expected_active_row_version": 1,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "committed"
    assert body["result"]["target_version"] == 2

    replay = client.post(
        "/directory/personnel/monthly-references/fork-version",
        headers=personnel_admin_headers,
        json={
            "command_id": command_id,
            "source_mrd_id": seeded_mrd["mrd_id"],
            "expected_active_row_version": 1,
        },
    )
    assert replay.status_code == 200
    assert replay.json()["status"] == "idempotent_replay"


def _fork_period_pair() -> tuple[date, date]:
    """Source in previous calendar month, target in current — both inside creation window."""
    from datetime import date

    previous, current, _next = get_creation_window_periods(date.today())
    return previous, current


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_fork_period_api(personnel_admin_headers, seeded_mrd) -> None:
    source_period, target_period = _fork_period_pair()
    user_id = seeded_mrd["user_id"]
    with engine.begin() as conn:
        purge_mrd_report_period(conn, source_period)
        purge_mrd_report_period(conn, target_period)
        source_mrd_id = seed_active_mrd(conn, report_period=source_period, created_by=user_id)
        seed_mrd_entry(conn, mrd_id=source_mrd_id, match_key="emp:api", payload={"position_raw": "Nurse"})
    seeded_mrd["_target_period"] = target_period
    resp = client.post(
        "/directory/personnel/monthly-references/fork-period",
        headers=personnel_admin_headers,
        json={
            "command_id": _command_id("api-fork-p"),
            "source_mrd_id": source_mrd_id,
            "target_report_period": target_period.isoformat(),
        },
    )
    assert resp.status_code == 201
    assert resp.json()["result"]["target_version"] == 1
    with engine.begin() as conn:
        purge_mrd_report_period(conn, target_period)
        purge_mrd_report_period(conn, source_period)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_fork_version_not_found_404(personnel_admin_headers) -> None:
    _require_mrd_schema()
    resp = client.post(
        "/directory/personnel/monthly-references/fork-version",
        headers=personnel_admin_headers,
        json={"command_id": _command_id("missing"), "source_mrd_id": 999999999},
    )
    assert resp.status_code == 404


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_fork_period_out_of_window_422(personnel_admin_headers, seeded_mrd) -> None:
    target_period = unique_report_period()
    resp = client.post(
        "/directory/personnel/monthly-references/fork-period",
        headers=personnel_admin_headers,
        json={
            "command_id": _command_id("out-window"),
            "source_mrd_id": seeded_mrd["mrd_id"],
            "target_report_period": target_period.isoformat(),
        },
    )
    assert resp.status_code == 422
    assert "допустимого окна" in resp.json()["detail"]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_fork_period_september_2026_422(personnel_admin_headers, seeded_mrd) -> None:
    resp = client.post(
        "/directory/personnel/monthly-references/fork-period",
        headers=personnel_admin_headers,
        json={
            "command_id": _command_id("sep-2026"),
            "source_mrd_id": seeded_mrd["mrd_id"],
            "target_report_period": "2026-09-01",
        },
    )
    assert resp.status_code == 422
    assert "допустимого окна" in resp.json()["detail"]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_creation_window_api(personnel_admin_headers) -> None:
    _require_mrd_schema()
    resp = client.get(
        "/directory/personnel/monthly-references/creation-window",
        headers=personnel_admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["allowed_periods"]) == 3


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_workspace_api(personnel_admin_headers, seeded_mrd) -> None:
    resp = client.get(
        f"/directory/personnel/monthly-references/{seeded_mrd['mrd_id']}/workspace",
        headers=personnel_admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["mrd_id"] == seeded_mrd["mrd_id"]
    assert body["entries"]["total"] >= 1
    assert "metrics" in body
    assert "confirmed_changes" in body


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_workspace_not_found_404(personnel_admin_headers) -> None:
    _require_mrd_schema()
    resp = client.get(
        "/directory/personnel/monthly-references/999999999/workspace",
        headers=personnel_admin_headers,
    )
    assert resp.status_code == 404


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_fork_period_duplicate_409(personnel_admin_headers, seeded_mrd) -> None:
    source_period, target_period = _fork_period_pair()
    user_id = seeded_mrd["user_id"]
    with engine.begin() as conn:
        purge_mrd_report_period(conn, source_period)
        purge_mrd_report_period(conn, target_period)
        source_mrd_id = seed_active_mrd(conn, report_period=source_period, created_by=user_id)
        seed_active_mrd(conn, report_period=target_period, created_by=user_id)
    resp = client.post(
        "/directory/personnel/monthly-references/fork-period",
        headers=personnel_admin_headers,
        json={
            "command_id": _command_id("dup-period"),
            "source_mrd_id": source_mrd_id,
            "target_report_period": target_period.isoformat(),
        },
    )
    assert resp.status_code == 409
    with engine.begin() as conn:
        purge_mrd_report_period(conn, target_period)
        purge_mrd_report_period(conn, source_period)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_fork_version_stale_active_409(personnel_admin_headers, seeded_mrd) -> None:
    resp = client.post(
        "/directory/personnel/monthly-references/fork-version",
        headers=personnel_admin_headers,
        json={
            "command_id": _command_id("stale"),
            "source_mrd_id": seeded_mrd["mrd_id"],
            "expected_active_row_version": 99,
        },
    )
    assert resp.status_code == 409


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_active_missing_returns_null(personnel_admin_headers) -> None:
    _require_mrd_schema()
    period = unique_report_period().isoformat()
    resp = client.get(
        "/directory/personnel/monthly-references/active",
        params={"report_period": period},
        headers=personnel_admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["active"] is None
