# tests/test_adr044_phase_r2_3_user_linkage_review.py
"""Tests for ADR-044 R2.3 user linkage review queue."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Optional
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.services.user_linkage_preview_service import (
    CLASSIFICATION_REVIEW_REQUIRED,
    MATCH_STRATEGY_LOGIN_SUFFIX,
)
from app.services.user_linkage_review_service import (
    DECISION_APPROVE,
    DECISION_DEFER,
    DECISION_PENDING,
    DECISION_REJECT,
    UserLinkageReviewError,
    list_user_linkage_review_audit,
    list_user_linkage_review_queue,
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


def _require_r2_tables() -> None:
    with engine.begin() as conn:
        for table in ("users", "employees"):
            if not table_exists(conn, table):
                pytest.skip(f"Required table missing: {table}")
        if "employee_id" not in get_columns(conn, "users"):
            pytest.skip("users.employee_id column missing")


def _require_review_table() -> None:
    _require_r2_tables()
    with engine.connect() as conn:
        if not review_decisions_available(conn):
            pytest.skip("user_linkage_review_decisions table missing")


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
            "google_login": f"r23_{suffix}@pytest.local",
            "login": login,
            "role_id": int(role_id),
            "unit_id": int(org_unit_id),
            "employee_id": None,
            "is_active": True,
        },
    )


def _employee_id_for_user(conn, user_id: int) -> Optional[int]:
    row = conn.execute(
        text("SELECT employee_id FROM public.users WHERE user_id = :user_id"),
        {"user_id": user_id},
    ).mappings().one()
    value = row.get("employee_id")
    return int(value) if value is not None else None


def _candidate_for_queue(report: dict, user_id: int) -> dict:
    return next(item for item in report["candidates"] if item["user_id"] == user_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_review_list_includes_preview_candidates(seed):
    _require_review_table()
    with _isolated_conn() as conn:
        employee_id = _create_employee(
            conn,
            full_name="Review Queue Employee",
            org_unit_id=int(seed["unit_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name="Review Queue Employee",
            login=f"review_head_{employee_id}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        report = list_user_linkage_review_queue(
            conn,
            search=f"review_head_{employee_id}",
        )
        candidate = _candidate_for_queue(report, user_id)
        assert candidate["classification"] == CLASSIFICATION_REVIEW_REQUIRED
        assert candidate["match_strategy"] == MATCH_STRATEGY_LOGIN_SUFFIX
        assert candidate["decision_state"] == DECISION_PENDING
        assert report["summary"]["review_required"] >= 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_review_list_filters_by_classification(seed):
    _require_review_table()
    with _isolated_conn() as conn:
        employee_id = _create_employee(
            conn,
            full_name="Filter Review Employee",
            org_unit_id=int(seed["unit_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name="Filter Review Employee",
            login=f"filter_head_{employee_id}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        filtered = list_user_linkage_review_queue(
            conn,
            classification=CLASSIFICATION_REVIEW_REQUIRED,
            search=f"filter_head_{employee_id}",
        )
        assert any(item["user_id"] == user_id for item in filtered["candidates"])


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_approve_records_decision_without_linking(seed):
    _require_review_table()
    with _isolated_conn() as conn:
        employee_id = _create_employee(
            conn,
            full_name="Approve Review Employee",
            org_unit_id=int(seed["unit_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name="Approve Review Employee",
            login=f"approve_head_{employee_id}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        decision = record_user_linkage_review_decision(
            conn,
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=user_id,
            decision=DECISION_APPROVE,
            reason="looks correct",
        )
        assert decision["decision"] == DECISION_APPROVE
        assert decision["proposed_employee_id"] == employee_id
        assert _employee_id_for_user(conn, user_id) is None

        queue = list_user_linkage_review_queue(conn, search=f"approve_head_{employee_id}")
        candidate = _candidate_for_queue(queue, user_id)
        assert candidate["decision_state"] == DECISION_APPROVE


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_reject_and_defer_record_decisions(seed):
    _require_review_table()
    with _isolated_conn() as conn:
        employee_id = _create_employee(
            conn,
            full_name="Reject Review Employee",
            org_unit_id=int(seed["unit_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name="Reject Review Employee",
            login=f"reject_head_{employee_id}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        reject = record_user_linkage_review_decision(
            conn,
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=user_id,
            decision=DECISION_REJECT,
            reason="not the same person",
        )
        assert reject["decision"] == DECISION_REJECT

        defer = record_user_linkage_review_decision(
            conn,
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=user_id,
            decision=DECISION_DEFER,
            reason="need more evidence",
        )
        assert defer["decision"] == DECISION_DEFER
        assert _employee_id_for_user(conn, user_id) is None

        queue = list_user_linkage_review_queue(
            conn,
            search=f"reject_head_{employee_id}",
            decision_state=DECISION_DEFER,
        )
        candidate = _candidate_for_queue(queue, user_id)
        assert candidate["decision_state"] == DECISION_DEFER


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_approve_rejected_for_impossible_classification(seed):
    _require_review_table()
    with _isolated_conn() as conn:
        user_id = _create_unlinked_user(
            conn,
            full_name=f"No Match Review {uuid4().hex[:8]}",
            login=f"nomatch_{uuid4().hex[:8]}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        with pytest.raises(UserLinkageReviewError):
            record_user_linkage_review_decision(
                conn,
                actor_user_id=int(seed["initiator_user_id"]),
                user_id=user_id,
                decision=DECISION_APPROVE,
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_audit_history_is_immutable_and_ordered(seed):
    _require_review_table()
    with _isolated_conn() as conn:
        employee_id = _create_employee(
            conn,
            full_name="Audit Review Employee",
            org_unit_id=int(seed["unit_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name="Audit Review Employee",
            login=f"audit_head_{employee_id}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        first = record_user_linkage_review_decision(
            conn,
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=user_id,
            decision=DECISION_DEFER,
            reason="first",
        )
        second = record_user_linkage_review_decision(
            conn,
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=user_id,
            decision=DECISION_APPROVE,
            reason="second",
        )

        audit = list_user_linkage_review_audit(conn, user_id=user_id)
        assert audit["total"] >= 2
        assert audit["items"][0]["decision_id"] == second["decision_id"]
        assert audit["items"][1]["decision_id"] == first["decision_id"]
        assert audit["items"][0]["reviewer_user_id"] == int(seed["initiator_user_id"])


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_api_review_list(client: TestClient, seed, monkeypatch):
    _require_review_table()
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    headers = auth_headers(seed["initiator_user_id"])
    resp = client.get("/admin/personnel/identity/user-linkage/review", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["phase"] == "R2"
    assert "summary" in body
    assert "candidates" in body


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_api_approve_reject_defer(client: TestClient, seed, monkeypatch):
    _require_review_table()
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    headers = auth_headers(seed["initiator_user_id"])

    employee_id: Optional[int] = None
    user_id: Optional[int] = None
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn,
                full_name="API Review Employee",
                org_unit_id=int(seed["unit_id"]),
            )
            user_id = _create_unlinked_user(
                conn,
                full_name="API Review Employee",
                login=f"link_head_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )

        approve = client.post(
            f"/admin/personnel/identity/user-linkage/review/{user_id}/approve",
            headers=headers,
            json={"reason": "approved via api"},
        )
        assert approve.status_code == 200, approve.text
        assert approve.json()["decision"] == DECISION_APPROVE

        reject = client.post(
            f"/admin/personnel/identity/user-linkage/review/{user_id}/reject",
            headers=headers,
            json={"reason": "changed mind"},
        )
        assert reject.status_code == 200, reject.text

        defer = client.post(
            f"/admin/personnel/identity/user-linkage/review/{user_id}/defer",
            headers=headers,
            json={"reason": "waiting"},
        )
        assert defer.status_code == 200, defer.text

        audit = client.get(
            "/admin/personnel/identity/user-linkage/review/audit",
            headers=headers,
            params={"user_id": user_id},
        )
        assert audit.status_code == 200, audit.text
        assert audit.json()["total"] >= 3

        with engine.connect() as conn:
            assert _employee_id_for_user(conn, int(user_id)) is None
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "DELETE FROM public.user_linkage_review_decisions WHERE user_id = :user_id"
                    ),
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
def test_api_review_requires_personnel_admin(client: TestClient, seed):
    _require_review_table()
    headers = auth_headers(seed["executor_user_id"])
    resp = client.get("/admin/personnel/identity/user-linkage/review", headers=headers)
    assert resp.status_code == 403
