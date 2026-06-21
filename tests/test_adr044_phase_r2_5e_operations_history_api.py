# tests/test_adr044_phase_r2_5e_operations_history_api.py
"""Tests for ADR-044 R2.5e user linkage operations history API."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.db.user_linkage_journal_constants import (
    ACTION_MANUAL_LINK,
    ACTION_ROLLBACK_LINK,
    OPERATION_MANUAL_LINK,
    OPERATION_ROLLBACK_ITEM,
    STATUS_APPLIED,
)
from app.main import app
from app.services.user_linkage_execute_service import execute_items_available
from app.services.user_linkage_operations_service import (
    manual_link_user,
    manual_unlink_user,
    rollback_linkage_item_for_user,
)
from tests.conftest import auth_headers, get_columns, insert_returning_id, table_exists

VALID_LINK_REASON = "HR confirmed manual linkage per ticket HR-9912"
VALID_ROLLBACK_REASON = "Rollback operation per ticket HR-9920"

RUNS_URL = "/admin/personnel/identity/user-linkage/operations/runs"
ITEMS_URL = "/admin/personnel/identity/user-linkage/operations/items"


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_r2_5b() -> None:
    with engine.connect() as conn:
        if not execute_items_available(conn):
            pytest.skip("ADR-044 R2.5b schema missing — run alembic upgrade head")


def _require_r2_tables() -> None:
    with engine.connect() as conn:
        for table in ("users", "employees", "security_audit_log"):
            if not table_exists(conn, table):
                pytest.skip(f"Required table missing: {table}")


def _create_employee(conn, *, full_name: str, org_unit_id: int) -> int:
    values: Dict[str, Any] = {
        "full_name": f"{full_name} {uuid4().hex[:8]}",
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
    login: str,
    role_id: int,
    org_unit_id: int,
) -> int:
    suffix = uuid4().hex[:8]
    return insert_returning_id(
        conn,
        table="users",
        id_col="user_id",
        values={
            "full_name": f"History API User {suffix}",
            "google_login": f"r25e_{suffix}@pytest.local",
            "login": login,
            "role_id": int(role_id),
            "unit_id": int(org_unit_id),
            "employee_id": None,
            "is_active": True,
        },
    )


def _cleanup(
    conn,
    *,
    user_ids: list[int],
    employee_ids: list[int],
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
    for user_id in user_ids:
        conn.execute(
            text("DELETE FROM public.security_audit_log WHERE target_user_id = :user_id"),
            {"user_id": int(user_id)},
        )
        conn.execute(
            text("DELETE FROM public.user_linkage_execute_items WHERE user_id = :user_id"),
            {"user_id": int(user_id)},
        )
        conn.execute(
            text("DELETE FROM public.users WHERE user_id = :user_id"),
            {"user_id": int(user_id)},
        )
    for employee_id in employee_ids:
        conn.execute(
            text(
                """
                UPDATE public.users
                SET employee_id = NULL
                WHERE employee_id = :employee_id
                """
            ),
            {"employee_id": int(employee_id)},
        )
        conn.execute(
            text("DELETE FROM public.employees WHERE employee_id = :employee_id"),
            {"employee_id": int(employee_id)},
        )


def _seed_manual_link_and_rollback(
    *,
    actor_user_id: int,
    role_id: int,
    org_unit_id: int,
) -> dict[str, int]:
    with engine.begin() as conn:
        employee_id = _create_employee(
            conn,
            full_name="History API Employee",
            org_unit_id=int(org_unit_id),
        )
        user_id = _create_unlinked_user(
            conn,
            login=f"history_api_{employee_id}",
            role_id=int(role_id),
            org_unit_id=int(org_unit_id),
        )

    link_result = manual_link_user(
        actor_user_id=int(actor_user_id),
        user_id=int(user_id),
        employee_id=int(employee_id),
        reason=VALID_LINK_REASON,
    )
    source_item_id = int(link_result["item_id"])
    link_run_id = int(link_result["run_id"])

    rollback_result = rollback_linkage_item_for_user(
        actor_user_id=int(actor_user_id),
        source_item_id=source_item_id,
        reason=VALID_ROLLBACK_REASON,
    )
    rollback_run_id = int(rollback_result["run_id"])
    rollback_item_id = int(rollback_result["item_id"])

    return {
        "user_id": int(user_id),
        "employee_id": int(employee_id),
        "source_item_id": source_item_id,
        "link_run_id": link_run_id,
        "rollback_run_id": rollback_run_id,
        "rollback_item_id": rollback_item_id,
    }


@pytest.fixture
def admin_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def non_admin_headers(seed):
    return auth_headers(seed["executor_user_id"])


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_operations_runs_list_returns_journal_runs(client: TestClient, seed, admin_headers):
    _require_r2_5b()
    _require_r2_tables()
    seeded = _seed_manual_link_and_rollback(
        actor_user_id=int(seed["initiator_user_id"]),
        role_id=int(seed["executor_role_id"]),
        org_unit_id=int(seed["unit_id"]),
    )
    try:
        resp = client.get(RUNS_URL, headers=admin_headers, params={"limit": 50})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "items" in body
        assert body["total"] >= 2
        run_ids = {row["run_id"] for row in body["items"]}
        assert seeded["link_run_id"] in run_ids
        assert seeded["rollback_run_id"] in run_ids

        link_row = next(row for row in body["items"] if row["run_id"] == seeded["link_run_id"])
        assert link_row["operation"] == OPERATION_MANUAL_LINK
        assert link_row["status"] == "completed"
        assert link_row["actor_user_id"] == int(seed["initiator_user_id"])
        assert link_row["item_count"] == 1
        assert link_row["audit_summary"]["user_employee_linked"] == 1
    finally:
        with engine.begin() as conn:
            _cleanup(
                conn,
                user_ids=[seeded["user_id"]],
                employee_ids=[seeded["employee_id"]],
                run_ids=[seeded["link_run_id"], seeded["rollback_run_id"]],
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_operations_runs_filter_by_operation(client: TestClient, seed, admin_headers):
    _require_r2_5b()
    _require_r2_tables()
    seeded = _seed_manual_link_and_rollback(
        actor_user_id=int(seed["initiator_user_id"]),
        role_id=int(seed["executor_role_id"]),
        org_unit_id=int(seed["unit_id"]),
    )
    try:
        resp = client.get(
            RUNS_URL,
            headers=admin_headers,
            params={"operation": OPERATION_ROLLBACK_ITEM, "limit": 100},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] >= 1
        assert all(row["operation"] == OPERATION_ROLLBACK_ITEM for row in body["items"])
        assert any(row["run_id"] == seeded["rollback_run_id"] for row in body["items"])
        assert all(row["run_id"] != seeded["link_run_id"] for row in body["items"])
    finally:
        with engine.begin() as conn:
            _cleanup(
                conn,
                user_ids=[seeded["user_id"]],
                employee_ids=[seeded["employee_id"]],
                run_ids=[seeded["link_run_id"], seeded["rollback_run_id"]],
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_operations_runs_filter_by_status_and_actor(client: TestClient, seed, admin_headers):
    _require_r2_5b()
    _require_r2_tables()
    seeded = _seed_manual_link_and_rollback(
        actor_user_id=int(seed["initiator_user_id"]),
        role_id=int(seed["executor_role_id"]),
        org_unit_id=int(seed["unit_id"]),
    )
    try:
        resp = client.get(
            RUNS_URL,
            headers=admin_headers,
            params={
                "status": "completed",
                "actor_user_id": seed["initiator_user_id"],
                "limit": 100,
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] >= 2
        assert all(row["status"] == "completed" for row in body["items"])
        assert all(row["actor_user_id"] == int(seed["initiator_user_id"]) for row in body["items"])
    finally:
        with engine.begin() as conn:
            _cleanup(
                conn,
                user_ids=[seeded["user_id"]],
                employee_ids=[seeded["employee_id"]],
                run_ids=[seeded["link_run_id"], seeded["rollback_run_id"]],
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_operations_runs_filter_by_created_range(client: TestClient, seed, admin_headers):
    _require_r2_5b()
    _require_r2_tables()
    seeded = _seed_manual_link_and_rollback(
        actor_user_id=int(seed["initiator_user_id"]),
        role_id=int(seed["executor_role_id"]),
        org_unit_id=int(seed["unit_id"]),
    )
    try:
        now = datetime.now(timezone.utc)
        resp = client.get(
            RUNS_URL,
            headers=admin_headers,
            params={
                "created_from": (now - timedelta(hours=1)).isoformat(),
                "created_to": (now + timedelta(hours=1)).isoformat(),
                "limit": 100,
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] >= 2
        run_ids = {row["run_id"] for row in body["items"]}
        assert seeded["link_run_id"] in run_ids
        assert seeded["rollback_run_id"] in run_ids
    finally:
        with engine.begin() as conn:
            _cleanup(
                conn,
                user_ids=[seeded["user_id"]],
                employee_ids=[seeded["employee_id"]],
                run_ids=[seeded["link_run_id"], seeded["rollback_run_id"]],
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_operations_run_detail_includes_counts_and_recent_items(
    client: TestClient,
    seed,
    admin_headers,
):
    _require_r2_5b()
    _require_r2_tables()
    seeded = _seed_manual_link_and_rollback(
        actor_user_id=int(seed["initiator_user_id"]),
        role_id=int(seed["executor_role_id"]),
        org_unit_id=int(seed["unit_id"]),
    )
    try:
        resp = client.get(
            f"{RUNS_URL}/{seeded['link_run_id']}",
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["run_id"] == seeded["link_run_id"]
        assert body["operation"] == OPERATION_MANUAL_LINK
        assert body["summary"]["trigger"] == "MANUAL"
        assert body["item_counts_by_status"][STATUS_APPLIED] == 1
        assert body["item_counts_by_action"][ACTION_MANUAL_LINK] == 1
        assert len(body["recent_items"]) == 1
        assert body["recent_items"][0]["user_id"] == seeded["user_id"]
        assert body["audit_summary"]["user_employee_linked"] == 1

        rollback_resp = client.get(
            f"{RUNS_URL}/{seeded['rollback_run_id']}",
            headers=admin_headers,
        )
        assert rollback_resp.status_code == 200, rollback_resp.text
        rollback_body = rollback_resp.json()
        assert rollback_body["source_item_id"] == seeded["source_item_id"]
        assert rollback_body["audit_summary"]["user_employee_link_rolled_back"] == 1
    finally:
        with engine.begin() as conn:
            _cleanup(
                conn,
                user_ids=[seeded["user_id"]],
                employee_ids=[seeded["employee_id"]],
                run_ids=[seeded["link_run_id"], seeded["rollback_run_id"]],
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_operations_run_detail_unknown_returns_404(client: TestClient, seed, admin_headers):
    _require_r2_5b()
    resp = client.get(f"{RUNS_URL}/999999999", headers=admin_headers)
    assert resp.status_code == 404


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_operations_items_list_and_filters(client: TestClient, seed, admin_headers):
    _require_r2_5b()
    _require_r2_tables()
    seeded = _seed_manual_link_and_rollback(
        actor_user_id=int(seed["initiator_user_id"]),
        role_id=int(seed["executor_role_id"]),
        org_unit_id=int(seed["unit_id"]),
    )
    try:
        resp = client.get(ITEMS_URL, headers=admin_headers, params={"limit": 100})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] >= 2
        item_ids = {row["item_id"] for row in body["items"]}
        assert seeded["source_item_id"] in item_ids
        assert seeded["rollback_item_id"] in item_ids

        by_run = client.get(
            ITEMS_URL,
            headers=admin_headers,
            params={"run_id": seeded["link_run_id"]},
        )
        assert by_run.status_code == 200
        assert all(row["run_id"] == seeded["link_run_id"] for row in by_run.json()["items"])

        by_action = client.get(
            ITEMS_URL,
            headers=admin_headers,
            params={"action": ACTION_ROLLBACK_LINK, "limit": 100},
        )
        assert by_action.status_code == 200
        assert all(row["action"] == ACTION_ROLLBACK_LINK for row in by_action.json()["items"])

        by_status = client.get(
            ITEMS_URL,
            headers=admin_headers,
            params={"status": STATUS_APPLIED, "user_id": seeded["user_id"], "limit": 100},
        )
        assert by_status.status_code == 200
        status_body = by_status.json()
        assert status_body["total"] >= 2
        assert all(row["status"] == STATUS_APPLIED for row in status_body["items"])
        assert all(row["user_id"] == seeded["user_id"] for row in status_body["items"])

        by_employee = client.get(
            ITEMS_URL,
            headers=admin_headers,
            params={"employee_id": seeded["employee_id"], "limit": 100},
        )
        assert by_employee.status_code == 200
        assert all(
            row["proposed_employee_id"] == seeded["employee_id"]
            for row in by_employee.json()["items"]
        )

        by_source = client.get(
            ITEMS_URL,
            headers=admin_headers,
            params={"source_item_id": seeded["source_item_id"], "limit": 100},
        )
        assert by_source.status_code == 200
        source_body = by_source.json()
        assert source_body["total"] >= 1
        assert any(row["item_id"] == seeded["rollback_item_id"] for row in source_body["items"])
    finally:
        with engine.begin() as conn:
            _cleanup(
                conn,
                user_ids=[seeded["user_id"]],
                employee_ids=[seeded["employee_id"]],
                run_ids=[seeded["link_run_id"], seeded["rollback_run_id"]],
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_operations_item_detail_includes_snapshots(client: TestClient, seed, admin_headers):
    _require_r2_5b()
    _require_r2_tables()
    seeded = _seed_manual_link_and_rollback(
        actor_user_id=int(seed["initiator_user_id"]),
        role_id=int(seed["executor_role_id"]),
        org_unit_id=int(seed["unit_id"]),
    )
    try:
        resp = client.get(
            f"{ITEMS_URL}/{seeded['source_item_id']}",
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["item_id"] == seeded["source_item_id"]
        assert body["action"] == ACTION_MANUAL_LINK
        assert body["before_user_snapshot"]["employee_id"] is None
        assert body["after_user_snapshot"]["employee_id"] == seeded["employee_id"]
        assert body["rollback_payload"]["employee_id"] == seeded["employee_id"]
    finally:
        with engine.begin() as conn:
            _cleanup(
                conn,
                user_ids=[seeded["user_id"]],
                employee_ids=[seeded["employee_id"]],
                run_ids=[seeded["link_run_id"], seeded["rollback_run_id"]],
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_operations_pagination(client: TestClient, seed, admin_headers):
    _require_r2_5b()
    _require_r2_tables()
    seeded = _seed_manual_link_and_rollback(
        actor_user_id=int(seed["initiator_user_id"]),
        role_id=int(seed["executor_role_id"]),
        org_unit_id=int(seed["unit_id"]),
    )
    try:
        page1 = client.get(
            RUNS_URL,
            headers=admin_headers,
            params={"operation": OPERATION_MANUAL_LINK, "limit": 1, "offset": 0},
        )
        page2 = client.get(
            RUNS_URL,
            headers=admin_headers,
            params={"operation": OPERATION_MANUAL_LINK, "limit": 1, "offset": 1},
        )
        assert page1.status_code == 200
        assert page2.status_code == 200
        body1 = page1.json()
        body2 = page2.json()
        assert body1["limit"] == 1
        assert body1["offset"] == 0
        assert len(body1["items"]) == 1
        if body1["total"] > 1:
            assert body1["items"][0]["run_id"] != body2["items"][0]["run_id"]
    finally:
        with engine.begin() as conn:
            _cleanup(
                conn,
                user_ids=[seeded["user_id"]],
                employee_ids=[seeded["employee_id"]],
                run_ids=[seeded["link_run_id"], seeded["rollback_run_id"]],
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_operations_unauthenticated_returns_401(client: TestClient):
    _require_r2_5b()
    resp = client.get(RUNS_URL)
    assert resp.status_code == 401


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_operations_non_admin_returns_403(client: TestClient, seed, non_admin_headers):
    _require_r2_5b()
    resp = client.get(RUNS_URL, headers=non_admin_headers)
    assert resp.status_code == 403

    resp_items = client.get(ITEMS_URL, headers=non_admin_headers)
    assert resp_items.status_code == 403


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_operations_manual_unlink_audit_count(client: TestClient, seed, admin_headers):
    _require_r2_5b()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn,
                full_name="Unlink History Employee",
                org_unit_id=int(seed["unit_id"]),
            )
            user_id = _create_unlinked_user(
                conn,
                login=f"unlink_hist_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )

        link_result = manual_link_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=int(user_id),
            employee_id=int(employee_id),
            reason=VALID_LINK_REASON,
        )
        run_ids.append(int(link_result["run_id"]))

        unlink_result = manual_unlink_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=int(user_id),
            reason=VALID_LINK_REASON,
        )
        run_ids.append(int(unlink_result["run_id"]))

        resp = client.get(
            f"{RUNS_URL}/{unlink_result['run_id']}",
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["audit_summary"]["user_employee_unlinked"] == 1
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                _cleanup(
                    conn,
                    user_ids=[int(user_id)],
                    employee_ids=[int(employee_id)] if employee_id is not None else [],
                    run_ids=run_ids,
                )
