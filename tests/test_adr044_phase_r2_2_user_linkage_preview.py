# tests/test_adr044_phase_r2_2_user_linkage_preview.py
"""Tests for ADR-044 R2.2 user linkage preview engine."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Optional
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.services.tasks_service import SYSTEM_ADMIN_ROLE_ID
from app.services.user_linkage_preview_service import (
    CLASSIFICATION_AMBIGUOUS,
    CLASSIFICATION_EXCLUDED,
    CLASSIFICATION_IMPOSSIBLE,
    CLASSIFICATION_REVIEW_REQUIRED,
    MATCH_STRATEGY_LOGIN_SUFFIX,
    MATCH_STRATEGY_NORMALIZED_FIO,
    REASON_FIO_COLLISION,
    REASON_FIO_EXACT_MATCH,
    REASON_INACTIVE_EMPLOYEE,
    REASON_LOGIN_SUFFIX_MATCH,
    REASON_MISSING_EMPLOYEE,
    REASON_MULTIPLE_EMPLOYEE_MATCHES,
    REASON_MULTIPLE_USER_MATCHES,
    REASON_NO_MATCH,
    REASON_SERVICE_ACCOUNT,
    run_user_linkage_preview,
)
from tests.conftest import auth_headers, get_columns, insert_returning_id, table_exists


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_r2_tables() -> None:
    with engine.begin() as conn:
        for table in ("users", "employees"):
            if not table_exists(conn, table):
                pytest.skip(f"Required table missing: {table}")
        if "employee_id" not in get_columns(conn, "users"):
            pytest.skip("users.employee_id column missing")


@contextmanager
def _isolated_conn():
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            yield conn
        finally:
            trans.rollback()


def _create_employee(
    conn,
    *,
    full_name: str,
    org_unit_id: int,
    operational_status: str = "active",
) -> int:
    values: Dict[str, Any] = {
        "full_name": full_name,
        "org_unit_id": int(org_unit_id),
        "is_active": operational_status != "terminated",
        "operational_status": operational_status,
    }
    cols = get_columns(conn, "employees")
    if "employment_rate" in cols:
        values["employment_rate"] = 1.0
    return insert_returning_id(conn, table="employees", id_col="employee_id", values=values)


def _create_unlinked_user(
    conn,
    *,
    full_name: str,
    login: Optional[str],
    role_id: int,
    org_unit_id: int,
) -> int:
    suffix = uuid4().hex[:10]
    return insert_returning_id(
        conn,
        table="users",
        id_col="user_id",
        values={
            "full_name": full_name,
            "google_login": f"r22_{suffix}@pytest.local",
            "login": login,
            "role_id": int(role_id),
            "unit_id": int(org_unit_id),
            "employee_id": None,
            "is_active": True,
        },
    )


def _candidate_for(report: dict, user_id: int) -> dict:
    return next(item for item in report["candidates"] if item["user_id"] == user_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_login_suffix_match(seed):
    _require_r2_tables()
    with _isolated_conn() as conn:
        employee_id = _create_employee(
            conn,
            full_name="Login Suffix Employee",
            org_unit_id=int(seed["unit_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name="Login Suffix User",
            login=f"role_head_{employee_id}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        report = run_user_linkage_preview(conn)
        candidate = _candidate_for(report, user_id)
        assert candidate["classification"] == CLASSIFICATION_REVIEW_REQUIRED
        assert candidate["match_strategy"] == MATCH_STRATEGY_LOGIN_SUFFIX
        assert candidate["proposed_employee_id"] == employee_id
        assert REASON_LOGIN_SUFFIX_MATCH in candidate["reason_codes"]
        assert candidate["requires_manual_confirmation"] is True


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_fio_unique_match(seed):
    _require_r2_tables()
    shared_name = f"Fio Unique Match {uuid4().hex[:6]}"
    with _isolated_conn() as conn:
        employee_id = _create_employee(
            conn,
            full_name=shared_name,
            org_unit_id=int(seed["unit_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name=shared_name,
            login=f"fio_only_{uuid4().hex[:8]}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        report = run_user_linkage_preview(conn)
        candidate = _candidate_for(report, user_id)
        assert candidate["classification"] == CLASSIFICATION_REVIEW_REQUIRED
        assert candidate["match_strategy"] == MATCH_STRATEGY_NORMALIZED_FIO
        assert candidate["proposed_employee_id"] == employee_id
        assert REASON_FIO_EXACT_MATCH in candidate["reason_codes"]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_service_account_exclusion(seed):
    _require_r2_tables()
    with _isolated_conn() as conn:
        user_id = _create_unlinked_user(
            conn,
            full_name="System Operator",
            login="admin_service_99",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        report = run_user_linkage_preview(conn)
        candidate = _candidate_for(report, user_id)
        assert candidate["classification"] == CLASSIFICATION_EXCLUDED
        assert REASON_SERVICE_ACCOUNT in candidate["reason_codes"]
        assert candidate["requires_manual_confirmation"] is False


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_ambiguous_fio_collision(seed):
    _require_r2_tables()
    shared_name = f"Fio Collision {uuid4().hex[:6]}"
    with _isolated_conn() as conn:
        _create_employee(
            conn,
            full_name=shared_name,
            org_unit_id=int(seed["unit_id"]),
        )
        _create_employee(
            conn,
            full_name=shared_name,
            org_unit_id=int(seed["unit_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name=shared_name,
            login=f"collision_{uuid4().hex[:8]}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        report = run_user_linkage_preview(conn)
        candidate = _candidate_for(report, user_id)
        assert candidate["classification"] == CLASSIFICATION_AMBIGUOUS
        assert REASON_FIO_COLLISION in candidate["reason_codes"]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_ambiguous_multiple_users_same_login_target(seed):
    _require_r2_tables()
    with _isolated_conn() as conn:
        employee_id = _create_employee(
            conn,
            full_name="Shared Login Target",
            org_unit_id=int(seed["unit_id"]),
        )
        user_a = _create_unlinked_user(
            conn,
            full_name="Shared Login User A",
            login=f"dup_head_{employee_id}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        user_b = _create_unlinked_user(
            conn,
            full_name="Shared Login User B",
            login=f"dup_deputy_{employee_id}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        report = run_user_linkage_preview(conn)
        for user_id in (user_a, user_b):
            candidate = _candidate_for(report, user_id)
            assert candidate["classification"] == CLASSIFICATION_AMBIGUOUS
            assert REASON_MULTIPLE_USER_MATCHES in candidate["reason_codes"]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_impossible_missing_employee(seed):
    _require_r2_tables()
    with _isolated_conn() as conn:
        missing_id = 9_999_991
        user_id = _create_unlinked_user(
            conn,
            full_name="Missing Employee User",
            login=f"missing_head_{missing_id}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        report = run_user_linkage_preview(conn)
        candidate = _candidate_for(report, user_id)
        assert candidate["classification"] == CLASSIFICATION_IMPOSSIBLE
        assert REASON_MISSING_EMPLOYEE in candidate["reason_codes"]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_impossible_inactive_employee(seed):
    _require_r2_tables()
    with _isolated_conn() as conn:
        employee_id = _create_employee(
            conn,
            full_name="Inactive Employee Target",
            org_unit_id=int(seed["unit_id"]),
            operational_status="terminated",
        )
        user_id = _create_unlinked_user(
            conn,
            full_name="Inactive Target User",
            login=f"inactive_head_{employee_id}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        report = run_user_linkage_preview(conn)
        candidate = _candidate_for(report, user_id)
        assert candidate["classification"] == CLASSIFICATION_IMPOSSIBLE
        assert REASON_INACTIVE_EMPLOYEE in candidate["reason_codes"]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_impossible_no_match(seed):
    _require_r2_tables()
    with _isolated_conn() as conn:
        user_id = _create_unlinked_user(
            conn,
            full_name=f"No Match User {uuid4().hex[:8]}",
            login=f"nomatch_{uuid4().hex[:8]}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        report = run_user_linkage_preview(conn)
        candidate = _candidate_for(report, user_id)
        assert candidate["classification"] == CLASSIFICATION_IMPOSSIBLE
        assert REASON_NO_MATCH in candidate["reason_codes"]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_ambiguous_login_and_fio_disagree(seed):
    _require_r2_tables()
    fio_name = f"Disagree Fio {uuid4().hex[:6]}"
    with _isolated_conn() as conn:
        login_employee_id = _create_employee(
            conn,
            full_name="Login Employee Only",
            org_unit_id=int(seed["unit_id"]),
        )
        _create_employee(
            conn,
            full_name=fio_name,
            org_unit_id=int(seed["unit_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name=fio_name,
            login=f"disagree_head_{login_employee_id}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        report = run_user_linkage_preview(conn)
        candidate = _candidate_for(report, user_id)
        assert candidate["classification"] == CLASSIFICATION_AMBIGUOUS
        assert REASON_MULTIPLE_EMPLOYEE_MATCHES in candidate["reason_codes"]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_preview_summary_auto_link_safe_always_zero(seed):
    _require_r2_tables()
    with _isolated_conn() as conn:
        report = run_user_linkage_preview(conn)
        assert report["dry_run"] is True
        assert report["phase"] == "R2"
        assert report["summary"]["auto_link_safe"] == 0


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_api_preview_user_linkage(client: TestClient, seed, monkeypatch):
    _require_r2_tables()
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    headers = auth_headers(seed["initiator_user_id"])
    resp = client.get("/admin/personnel/identity/user-linkage/preview", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["phase"] == "R2"
    assert body["dry_run"] is True
    assert "summary" in body
    assert "candidates" in body
    assert body["summary"]["auto_link_safe"] == 0


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_api_preview_requires_personnel_admin(client: TestClient, seed):
    _require_r2_tables()
    headers = auth_headers(seed["executor_user_id"])
    resp = client.get("/admin/personnel/identity/user-linkage/preview", headers=headers)
    assert resp.status_code == 403


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_system_admin_role_excluded_even_with_login_match(seed):
    _require_r2_tables()
    with _isolated_conn() as conn:
        employee_id = _create_employee(
            conn,
            full_name="Admin Role Employee",
            org_unit_id=int(seed["unit_id"]),
        )
        user_id = insert_returning_id(
            conn,
            table="users",
            id_col="user_id",
            values={
                "full_name": "Admin Role User",
                "google_login": f"adminrole_{uuid4().hex[:8]}@pytest.local",
                "login": f"adminrole_{employee_id}",
                "role_id": int(SYSTEM_ADMIN_ROLE_ID),
                "unit_id": int(seed["unit_id"]),
                "employee_id": None,
                "is_active": True,
            },
        )
        report = run_user_linkage_preview(conn)
        candidate = _candidate_for(report, user_id)
        assert candidate["classification"] == CLASSIFICATION_EXCLUDED
        assert REASON_SERVICE_ACCOUNT in candidate["reason_codes"]
