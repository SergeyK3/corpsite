# tests/test_adr044_phase_r2_4c_user_linkage_execute_preview_api.py
"""Tests for ADR-044 R2.4c user linkage execute preview API."""
from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.services.user_linkage_execute_service import (
    ACTION_LINK,
    OPERATION_EXECUTE_PREVIEW,
    execute_items_available,
)
from app.services.user_linkage_review_service import (
    DECISION_APPROVE,
    record_user_linkage_review_decision,
    review_decisions_available,
)
from tests.conftest import auth_headers, get_columns, insert_returning_id, table_exists


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_r2_4c() -> None:
    with engine.connect() as conn:
        if not execute_items_available(conn):
            pytest.skip("ADR-044 R2.4 execute schema missing — run alembic upgrade head")
        if not review_decisions_available(conn):
            pytest.skip("user_linkage_review_decisions table missing")


def _require_r2_tables() -> None:
    with engine.connect() as conn:
        for table in ("users", "employees"):
            if not table_exists(conn, table):
                pytest.skip(f"Required table missing: {table}")
        if "employee_id" not in get_columns(conn, "users"):
            pytest.skip("users.employee_id column missing")


def _create_employee(conn, *, full_name: str, org_unit_id: int) -> int:
    values: Dict[str, Any] = {
        "full_name": full_name,
        "org_unit_id": int(org_unit_id),
        "is_active": True,
        "operational_status": "active",
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
            "google_login": f"r24c_{suffix}@pytest.local",
            "login": login,
            "role_id": int(role_id),
            "unit_id": int(org_unit_id),
            "employee_id": None,
            "is_active": True,
        },
    )


def _cleanup_execute_preview_artifacts(
    conn,
    *,
    user_id: int,
    employee_id: Optional[int],
    run_ids: list[int],
) -> None:
    for run_id in run_ids:
        conn.execute(
            text("DELETE FROM public.user_linkage_execute_items WHERE run_id = :run_id"),
            {"run_id": int(run_id)},
        )
        conn.execute(
            text("DELETE FROM public.identity_reconciliation_runs WHERE run_id = :run_id"),
            {"run_id": int(run_id)},
        )
    conn.execute(
        text("DELETE FROM public.user_linkage_review_decisions WHERE user_id = :user_id"),
        {"user_id": int(user_id)},
    )
    conn.execute(
        text("DELETE FROM public.users WHERE user_id = :user_id"),
        {"user_id": int(user_id)},
    )
    if employee_id is not None:
        conn.execute(
            text("DELETE FROM public.employees WHERE employee_id = :employee_id"),
            {"employee_id": int(employee_id)},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_api_execute_preview_planned_link(seed, monkeypatch):
    _require_r2_4c()
    _require_r2_tables()
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    headers = auth_headers(seed["initiator_user_id"])
    client = TestClient(app)

    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn,
                full_name="API Execute Preview Employee",
                org_unit_id=int(seed["unit_id"]),
            )
            user_id = _create_unlinked_user(
                conn,
                full_name="API Execute Preview Employee",
                login=f"exec_prev_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )
            record_user_linkage_review_decision(
                conn,
                actor_user_id=int(seed["initiator_user_id"]),
                user_id=int(user_id),
                decision=DECISION_APPROVE,
                reason="api execute preview",
            )

        resp = client.post(
            "/admin/personnel/identity/user-linkage/execute-preview",
            headers=headers,
            json={"user_id": int(user_id)},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        run_ids.append(int(body["run_id"]))
        assert body["phase"] == "R2"
        assert body["dry_run"] is True
        assert body["operation"] == OPERATION_EXECUTE_PREVIEW
        assert body["run_status"] == "completed"
        assert body["execute_allowed"] is True
        assert body["confirm_token"].startswith("sha256:")
        assert body["summary"]["planned_link"] >= 1
        assert body["summary"]["would_apply"] >= 1

        item = next(row for row in body["items"] if row["user_id"] == int(user_id))
        assert item["action"] == ACTION_LINK
        assert item["planned_outcome"] == "apply"
        assert item["proposed_employee_id"] == int(employee_id)
        assert item["decision_id"] is not None

        with engine.connect() as conn:
            assert (
                conn.execute(
                    text("SELECT employee_id FROM public.users WHERE user_id = :user_id"),
                    {"user_id": int(user_id)},
                ).scalar_one()
                is None
            )
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                _cleanup_execute_preview_artifacts(
                    conn,
                    user_id=int(user_id),
                    employee_id=employee_id,
                    run_ids=run_ids,
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_api_execute_preview_requires_personnel_admin(client: TestClient, seed):
    _require_r2_4c()
    _require_r2_tables()
    headers = auth_headers(seed["executor_user_id"])
    resp = client.post(
        "/admin/personnel/identity/user-linkage/execute-preview",
        headers=headers,
        json={},
    )
    assert resp.status_code == 403


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_api_execute_preview_rejects_conflicting_user_filters(client: TestClient, seed, monkeypatch):
    _require_r2_4c()
    _require_r2_tables()
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    headers = auth_headers(seed["initiator_user_id"])
    resp = client.post(
        "/admin/personnel/identity/user-linkage/execute-preview",
        headers=headers,
        json={"user_id": 1, "user_ids": [1, 2]},
    )
    assert resp.status_code == 400
    assert "user_id or user_ids" in resp.json()["detail"]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_api_execute_preview_user_ids_filter(seed, monkeypatch):
    _require_r2_4c()
    _require_r2_tables()
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    headers = auth_headers(seed["initiator_user_id"])
    client = TestClient(app)

    user_a: Optional[int] = None
    user_b: Optional[int] = None
    employee_a: Optional[int] = None
    employee_b: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_a = _create_employee(
                conn,
                full_name="Filter API Employee A",
                org_unit_id=int(seed["unit_id"]),
            )
            employee_b = _create_employee(
                conn,
                full_name="Filter API Employee B",
                org_unit_id=int(seed["unit_id"]),
            )
            user_a = _create_unlinked_user(
                conn,
                full_name="Filter API Employee A",
                login=f"filter_a_{employee_a}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )
            user_b = _create_unlinked_user(
                conn,
                full_name="Filter API Employee B",
                login=f"filter_b_{employee_b}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )

        resp = client.post(
            "/admin/personnel/identity/user-linkage/execute-preview",
            headers=headers,
            json={"user_ids": [int(user_a)]},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        run_ids.append(int(body["run_id"]))
        evaluated_ids = {row["user_id"] for row in body["items"]}
        assert int(user_a) in evaluated_ids
        assert int(user_b) not in evaluated_ids
    finally:
        with engine.begin() as conn:
            for user_id, employee_id in (
                (user_a, employee_a),
                (user_b, employee_b),
            ):
                if user_id is not None:
                    _cleanup_execute_preview_artifacts(
                        conn,
                        user_id=int(user_id),
                        employee_id=employee_id,
                        run_ids=run_ids,
                    )
