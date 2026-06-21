# tests/test_adr044_phase_r2_4b_user_linkage_execute_preview.py
"""Tests for ADR-044 R2.4b user linkage execute preview service."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Optional
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.user_linkage_execute_service import (
    ACTION_FAIL_ALREADY_LINKED_DIFFERENT,
    ACTION_FAIL_EMPLOYEE_CONFLICT,
    ACTION_LINK,
    ACTION_NOOP_ALREADY_LINKED,
    ACTION_SKIP_CLASSIFICATION_REGRESSION,
    ACTION_SKIP_EXCLUDED,
    ACTION_SKIP_NOT_APPROVED,
    ACTION_SKIP_PREVIEW_DRIFT,
    OPERATION_EXECUTE_PREVIEW,
    STATUS_FAILED,
    STATUS_PLANNED,
    STATUS_SKIPPED,
    _build_user_linkage_execute_preview,
    execute_items_available,
)
from app.services.user_linkage_preview_service import CLASSIFICATION_REVIEW_REQUIRED
from app.services.user_linkage_review_service import (
    DECISION_APPROVE,
    DECISION_DEFER,
    DECISION_REJECT,
    record_user_linkage_review_decision,
    review_decisions_available,
)
from tests.conftest import get_columns, insert_returning_id, table_exists

DDL_REVISION = "e4f5a6b7c8d9"


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_r2_4b() -> None:
    with engine.connect() as conn:
        if not execute_items_available(conn):
            pytest.skip(
                f"ADR-044 R2.4b schema missing — run: alembic upgrade head (revision {DDL_REVISION})"
            )
        if not review_decisions_available(conn):
            pytest.skip("user_linkage_review_decisions table missing")


def _require_r2_tables() -> None:
    with engine.connect() as conn:
        for table in ("users", "employees", "user_linkage_review_decisions"):
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
            "google_login": f"r24b_{suffix}@pytest.local",
            "login": login,
            "role_id": int(role_id),
            "unit_id": int(org_unit_id),
            "employee_id": None,
            "is_active": True,
        },
    )


def _insert_review_decision(
    conn,
    *,
    reviewer_user_id: int,
    user_id: int,
    proposed_employee_id: Optional[int],
    decision: str,
    classification: str = CLASSIFICATION_REVIEW_REQUIRED,
    match_strategy: str = "LOGIN_SUFFIX",
) -> int:
    return int(
        conn.execute(
            text(
                """
                INSERT INTO public.user_linkage_review_decisions (
                    reviewer_user_id,
                    user_id,
                    proposed_employee_id,
                    classification,
                    match_strategy,
                    decision,
                    reason
                ) VALUES (
                    :reviewer_user_id,
                    :user_id,
                    :proposed_employee_id,
                    :classification,
                    :match_strategy,
                    :decision,
                    'execute preview test'
                )
                RETURNING decision_id
                """
            ),
            {
                "reviewer_user_id": int(reviewer_user_id),
                "user_id": int(user_id),
                "proposed_employee_id": proposed_employee_id,
                "classification": classification,
                "match_strategy": match_strategy,
                "decision": decision,
            },
        ).scalar_one()
    )


def _employee_id_for_user(conn, user_id: int) -> Optional[int]:
    value = conn.execute(
        text("SELECT employee_id FROM public.users WHERE user_id = :user_id"),
        {"user_id": int(user_id)},
    ).scalar_one()
    return int(value) if value is not None else None


def _linked_user_count(conn) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(*) AS cnt
                FROM public.users
                WHERE employee_id IS NOT NULL
                """
            )
        ).scalar_one()
    )


def _decision_count(conn) -> int:
    return int(
        conn.execute(
            text("SELECT COUNT(*) FROM public.user_linkage_review_decisions")
        ).scalar_one()
    )


def _item_for(result, user_id: int) -> dict:
    return next(item for item in result.items if item["user_id"] == user_id)


def _run_preview(conn, *, actor_user_id: int, user_id: Optional[int] = None, limit: Optional[int] = None):
    return _build_user_linkage_execute_preview(
        conn,
        actor_user_id=int(actor_user_id),
        user_id=user_id,
        limit=limit,
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_approve_matching_preview_planned_link(seed):
    _require_r2_4b()
    _require_r2_tables()
    with _isolated_conn() as conn:
        employee_id = _create_employee(
            conn,
            full_name="Execute Link Employee",
            org_unit_id=int(seed["unit_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name="Execute Link Employee",
            login=f"exec_link_{employee_id}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        record_user_linkage_review_decision(
            conn,
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=user_id,
            decision=DECISION_APPROVE,
            reason="approved for execute",
        )
        before_employee_id = _employee_id_for_user(conn, user_id)
        result = _run_preview(conn, actor_user_id=int(seed["initiator_user_id"]), user_id=user_id)
        item = _item_for(result, user_id)
        assert item["action"] == ACTION_LINK
        assert item["status"] == STATUS_PLANNED
        assert item["proposed_employee_id"] == employee_id
        assert _employee_id_for_user(conn, user_id) == before_employee_id
        assert result.summary["planned_link"] >= 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.parametrize("decision", (DECISION_REJECT, DECISION_DEFER))
def test_non_approve_decision_skipped_not_approved(decision, seed):
    _require_r2_4b()
    _require_r2_tables()
    with _isolated_conn() as conn:
        employee_id = _create_employee(
            conn,
            full_name=f"Skip Decision Employee {decision}",
            org_unit_id=int(seed["unit_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name=f"Skip Decision Employee {decision}",
            login=f"skip_dec_{decision.lower()}_{employee_id}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        _insert_review_decision(
            conn,
            reviewer_user_id=int(seed["initiator_user_id"]),
            user_id=user_id,
            proposed_employee_id=employee_id,
            decision=decision,
        )
        result = _run_preview(conn, actor_user_id=int(seed["initiator_user_id"]), user_id=user_id)
        item = _item_for(result, user_id)
        assert item["action"] == ACTION_SKIP_NOT_APPROVED
        assert item["status"] == STATUS_SKIPPED


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_no_decision_skipped_not_approved(seed):
    _require_r2_4b()
    _require_r2_tables()
    with _isolated_conn() as conn:
        employee_id = _create_employee(
            conn,
            full_name="No Decision Employee",
            org_unit_id=int(seed["unit_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name="No Decision Employee",
            login=f"no_decision_{employee_id}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        result = _run_preview(conn, actor_user_id=int(seed["initiator_user_id"]), user_id=user_id)
        item = _item_for(result, user_id)
        assert item["action"] == ACTION_SKIP_NOT_APPROVED
        assert item["status"] == STATUS_SKIPPED


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_preview_drift_skipped(seed):
    _require_r2_4b()
    _require_r2_tables()
    with _isolated_conn() as conn:
        employee_a = _create_employee(
            conn,
            full_name="Drift Employee A",
            org_unit_id=int(seed["unit_id"]),
        )
        employee_b = _create_employee(
            conn,
            full_name="Drift Employee B",
            org_unit_id=int(seed["unit_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name="Drift Employee B",
            login=f"drift_head_{employee_a}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        _insert_review_decision(
            conn,
            reviewer_user_id=int(seed["initiator_user_id"]),
            user_id=user_id,
            proposed_employee_id=employee_a,
            decision=DECISION_APPROVE,
        )
        conn.execute(
            text("UPDATE public.users SET login = :login WHERE user_id = :user_id"),
            {"login": f"drift_head_{employee_b}", "user_id": int(user_id)},
        )
        result = _run_preview(conn, actor_user_id=int(seed["initiator_user_id"]), user_id=user_id)
        item = _item_for(result, user_id)
        assert item["action"] == ACTION_SKIP_PREVIEW_DRIFT
        assert item["status"] == STATUS_SKIPPED
        assert item["proposed_employee_id"] == employee_b


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_excluded_classification_skipped(seed):
    _require_r2_4b()
    _require_r2_tables()
    with _isolated_conn() as conn:
        employee_id = _create_employee(
            conn,
            full_name="Excluded Target Employee",
            org_unit_id=int(seed["unit_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name="System Operator",
            login=f"admin_exec_{employee_id}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        _insert_review_decision(
            conn,
            reviewer_user_id=int(seed["initiator_user_id"]),
            user_id=user_id,
            proposed_employee_id=employee_id,
            decision=DECISION_APPROVE,
        )
        result = _run_preview(conn, actor_user_id=int(seed["initiator_user_id"]), user_id=user_id)
        item = _item_for(result, user_id)
        assert item["action"] == ACTION_SKIP_EXCLUDED
        assert item["status"] == STATUS_SKIPPED


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_classification_regression_skipped(seed):
    _require_r2_4b()
    _require_r2_tables()
    with _isolated_conn() as conn:
        employee_id = _create_employee(
            conn,
            full_name="Regression Employee",
            org_unit_id=int(seed["unit_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name="Regression Employee",
            login=f"regression_{employee_id}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        _insert_review_decision(
            conn,
            reviewer_user_id=int(seed["initiator_user_id"]),
            user_id=user_id,
            proposed_employee_id=employee_id,
            decision=DECISION_APPROVE,
        )
        conn.execute(
            text("UPDATE public.users SET is_active = FALSE WHERE user_id = :user_id"),
            {"user_id": int(user_id)},
        )
        result = _run_preview(conn, actor_user_id=int(seed["initiator_user_id"]), user_id=user_id)
        item = _item_for(result, user_id)
        assert item["action"] == ACTION_SKIP_CLASSIFICATION_REGRESSION
        assert item["status"] == STATUS_SKIPPED


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_noop_already_linked_same_employee(seed):
    _require_r2_4b()
    _require_r2_tables()
    with _isolated_conn() as conn:
        employee_id = _create_employee(
            conn,
            full_name="Noop Linked Employee",
            org_unit_id=int(seed["unit_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name="Noop Linked Employee",
            login=f"noop_link_{employee_id}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        conn.execute(
            text(
                """
                UPDATE public.users
                SET employee_id = :employee_id
                WHERE user_id = :user_id
                """
            ),
            {"employee_id": int(employee_id), "user_id": int(user_id)},
        )
        _insert_review_decision(
            conn,
            reviewer_user_id=int(seed["initiator_user_id"]),
            user_id=user_id,
            proposed_employee_id=employee_id,
            decision=DECISION_APPROVE,
        )
        result = _run_preview(conn, actor_user_id=int(seed["initiator_user_id"]), user_id=user_id)
        item = _item_for(result, user_id)
        assert item["action"] == ACTION_NOOP_ALREADY_LINKED
        assert item["status"] == STATUS_SKIPPED
        assert _employee_id_for_user(conn, user_id) == employee_id


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_fail_already_linked_different_employee(seed):
    _require_r2_4b()
    _require_r2_tables()
    with _isolated_conn() as conn:
        linked_employee = _create_employee(
            conn,
            full_name="Current Link Employee",
            org_unit_id=int(seed["unit_id"]),
        )
        approved_employee = _create_employee(
            conn,
            full_name="Approved Different Employee",
            org_unit_id=int(seed["unit_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name="Conflict Link User",
            login=f"conflict_link_{approved_employee}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        conn.execute(
            text(
                """
                UPDATE public.users
                SET employee_id = :employee_id
                WHERE user_id = :user_id
                """
            ),
            {"employee_id": int(linked_employee), "user_id": int(user_id)},
        )
        _insert_review_decision(
            conn,
            reviewer_user_id=int(seed["initiator_user_id"]),
            user_id=user_id,
            proposed_employee_id=approved_employee,
            decision=DECISION_APPROVE,
        )
        result = _run_preview(conn, actor_user_id=int(seed["initiator_user_id"]), user_id=user_id)
        item = _item_for(result, user_id)
        assert item["action"] == ACTION_FAIL_ALREADY_LINKED_DIFFERENT
        assert item["status"] == STATUS_FAILED
        assert _employee_id_for_user(conn, user_id) == linked_employee


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_fail_employee_conflict(seed):
    _require_r2_4b()
    _require_r2_tables()
    with _isolated_conn() as conn:
        employee_id = _create_employee(
            conn,
            full_name="Shared Employee Conflict",
            org_unit_id=int(seed["unit_id"]),
        )
        occupied_user = _create_unlinked_user(
            conn,
            full_name="Occupying User",
            login=f"occupy_{uuid4().hex[:8]}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        conn.execute(
            text(
                """
                UPDATE public.users
                SET employee_id = :employee_id
                WHERE user_id = :user_id
                """
            ),
            {"employee_id": int(employee_id), "user_id": int(occupied_user)},
        )
        candidate_user = _create_unlinked_user(
            conn,
            full_name="Shared Employee Conflict",
            login=f"conflict_head_{employee_id}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        _insert_review_decision(
            conn,
            reviewer_user_id=int(seed["initiator_user_id"]),
            user_id=candidate_user,
            proposed_employee_id=employee_id,
            decision=DECISION_APPROVE,
        )
        result = _run_preview(
            conn,
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=candidate_user,
        )
        item = _item_for(result, candidate_user)
        assert item["action"] == ACTION_FAIL_EMPLOYEE_CONFLICT
        assert item["status"] == STATUS_FAILED


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_creates_r2_dry_run_run_row(seed):
    _require_r2_4b()
    _require_r2_tables()
    with _isolated_conn() as conn:
        result = _run_preview(conn, actor_user_id=int(seed["initiator_user_id"]), limit=1)
        row = conn.execute(
            text(
                """
                SELECT phase, operation, dry_run, actor_user_id, status, summary
                FROM public.identity_reconciliation_runs
                WHERE run_id = :run_id
                """
            ),
            {"run_id": int(result.run_id)},
        ).mappings().one()
        assert row["phase"] == "R2"
        assert row["operation"] == OPERATION_EXECUTE_PREVIEW
        assert row["dry_run"] is True
        assert int(row["actor_user_id"]) == int(seed["initiator_user_id"])
        assert row["status"] == "completed"
        assert "total_evaluated" in row["summary"]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_writes_execute_item_rows(seed):
    _require_r2_4b()
    _require_r2_tables()
    with _isolated_conn() as conn:
        employee_id = _create_employee(
            conn,
            full_name="Item Row Employee",
            org_unit_id=int(seed["unit_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name="Item Row Employee",
            login=f"item_row_{employee_id}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        record_user_linkage_review_decision(
            conn,
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=user_id,
            decision=DECISION_APPROVE,
        )
        result = _run_preview(conn, actor_user_id=int(seed["initiator_user_id"]), user_id=user_id)
        rows = conn.execute(
            text(
                """
                SELECT item_id, action, status, preview_snapshot, decision_snapshot,
                       before_user_snapshot, after_user_snapshot, rollback_payload
                FROM public.user_linkage_execute_items
                WHERE run_id = :run_id AND user_id = :user_id
                """
            ),
            {"run_id": int(result.run_id), "user_id": int(user_id)},
        ).mappings().all()
        assert len(rows) == 1
        row = rows[0]
        assert row["preview_snapshot"]
        assert row["decision_snapshot"]
        assert row["before_user_snapshot"]["employee_id"] is None
        assert row["after_user_snapshot"] is None
        assert row["rollback_payload"] is None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_users_employee_id_unchanged(seed):
    _require_r2_4b()
    _require_r2_tables()
    with engine.connect() as conn:
        before = _linked_user_count(conn)
    with _isolated_conn() as conn:
        employee_id = _create_employee(
            conn,
            full_name="Unchanged Employee",
            org_unit_id=int(seed["unit_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name="Unchanged Employee",
            login=f"unchanged_{employee_id}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        record_user_linkage_review_decision(
            conn,
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=user_id,
            decision=DECISION_APPROVE,
        )
        _run_preview(conn, actor_user_id=int(seed["initiator_user_id"]), user_id=user_id)
        assert _employee_id_for_user(conn, user_id) is None
    with engine.connect() as conn:
        after = _linked_user_count(conn)
    assert before == after


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_review_decisions_unchanged(seed):
    _require_r2_4b()
    _require_r2_tables()
    with _isolated_conn() as conn:
        employee_id = _create_employee(
            conn,
            full_name="Decision Stable Employee",
            org_unit_id=int(seed["unit_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name="Decision Stable Employee",
            login=f"dec_stable_{employee_id}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        decision = record_user_linkage_review_decision(
            conn,
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=user_id,
            decision=DECISION_APPROVE,
            reason="stable",
        )
        before_count = _decision_count(conn)
        before_row = conn.execute(
            text(
                """
                SELECT decision_id, decision, reason
                FROM public.user_linkage_review_decisions
                WHERE decision_id = :decision_id
                """
            ),
            {"decision_id": int(decision["decision_id"])},
        ).mappings().one()
        _run_preview(conn, actor_user_id=int(seed["initiator_user_id"]), user_id=user_id)
        after_count = _decision_count(conn)
        after_row = conn.execute(
            text(
                """
                SELECT decision_id, decision, reason
                FROM public.user_linkage_review_decisions
                WHERE decision_id = :decision_id
                """
            ),
            {"decision_id": int(decision["decision_id"])},
        ).mappings().one()
        assert before_count == after_count
        assert dict(before_row) == dict(after_row)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_idempotent_rerun_creates_new_run_without_user_mutation(seed):
    _require_r2_4b()
    _require_r2_tables()
    with _isolated_conn() as conn:
        employee_id = _create_employee(
            conn,
            full_name="Rerun Employee",
            org_unit_id=int(seed["unit_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name="Rerun Employee",
            login=f"rerun_{employee_id}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        record_user_linkage_review_decision(
            conn,
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=user_id,
            decision=DECISION_APPROVE,
        )
        first = _run_preview(conn, actor_user_id=int(seed["initiator_user_id"]), user_id=user_id)
        second = _run_preview(conn, actor_user_id=int(seed["initiator_user_id"]), user_id=user_id)
        assert first.run_id != second.run_id
        assert _employee_id_for_user(conn, user_id) is None
        item_count = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.user_linkage_execute_items
                WHERE user_id = :user_id
                """
            ),
            {"user_id": int(user_id)},
        ).scalar_one()
        assert int(item_count) == 2


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_limit_filter(seed):
    _require_r2_4b()
    _require_r2_tables()
    with _isolated_conn() as conn:
        created_users = []
        for idx in range(3):
            employee_id = _create_employee(
                conn,
                full_name=f"Limit Employee {idx}",
                org_unit_id=int(seed["unit_id"]),
            )
            user_id = _create_unlinked_user(
                conn,
                full_name=f"Limit Employee {idx}",
                login=f"limit_{idx}_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )
            created_users.append(user_id)
        result = _run_preview(conn, actor_user_id=int(seed["initiator_user_id"]), limit=1)
        assert result.summary["total_evaluated"] == 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_user_id_filter(seed):
    _require_r2_4b()
    _require_r2_tables()
    with _isolated_conn() as conn:
        employee_a = _create_employee(
            conn,
            full_name="Filter Employee A",
            org_unit_id=int(seed["unit_id"]),
        )
        employee_b = _create_employee(
            conn,
            full_name="Filter Employee B",
            org_unit_id=int(seed["unit_id"]),
        )
        user_a = _create_unlinked_user(
            conn,
            full_name="Filter Employee A",
            login=f"filter_a_{employee_a}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        user_b = _create_unlinked_user(
            conn,
            full_name="Filter Employee B",
            login=f"filter_b_{employee_b}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        result = _run_preview(
            conn,
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=user_a,
        )
        evaluated_ids = {item["user_id"] for item in result.items}
        assert user_a in evaluated_ids
        assert user_b not in evaluated_ids
        assert result.summary["total_evaluated"] == 1
