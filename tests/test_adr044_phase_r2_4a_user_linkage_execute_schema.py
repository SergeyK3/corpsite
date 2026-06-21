# tests/test_adr044_phase_r2_4a_user_linkage_execute_schema.py
"""Schema tests for ADR-044 R2.4a user linkage execute journal DDL."""
from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Dict, Optional
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import get_columns, insert_returning_id, table_exists

DDL_REVISION = "e4f5a6b7c8d9"

R2_RUN_COLUMNS = (
    "run_id",
    "phase",
    "operation",
    "dry_run",
    "actor_user_id",
    "snapshot_id",
    "started_at",
    "finished_at",
    "status",
    "summary",
)

EXECUTE_ITEM_COLUMNS = (
    "item_id",
    "run_id",
    "user_id",
    "proposed_employee_id",
    "source_decision_id",
    "action",
    "status",
    "reason_codes",
    "preview_snapshot",
    "decision_snapshot",
    "before_user_snapshot",
    "after_user_snapshot",
    "rollback_payload",
    "created_at",
)

VALID_ACTIONS = (
    "LINK",
    "NOOP_ALREADY_LINKED",
    "SKIP_NOT_APPROVED",
    "SKIP_PREVIEW_DRIFT",
    "SKIP_CLASSIFICATION_REGRESSION",
    "SKIP_EXCLUDED",
    "FAIL_ALREADY_LINKED_DIFFERENT",
    "FAIL_EMPLOYEE_CONFLICT",
)

VALID_STATUSES = ("PLANNED", "APPLIED", "SKIPPED", "FAILED")


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _r2_4a_available() -> bool:
    with engine.connect() as conn:
        if not table_exists(conn, "user_linkage_execute_items"):
            return False
        cols = get_columns(conn, "identity_reconciliation_runs")
        return "operation" in cols


def _require_r2_4a() -> None:
    if not _r2_4a_available():
        pytest.skip(
            f"ADR-044 R2.4a schema missing — run: alembic upgrade head (revision {DDL_REVISION})"
        )


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
            "google_login": f"r24a_{suffix}@pytest.local",
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
                    'REVIEW_REQUIRED',
                    'LOGIN_SUFFIX',
                    'APPROVE',
                    'schema test'
                )
                RETURNING decision_id
                """
            ),
            {
                "reviewer_user_id": int(reviewer_user_id),
                "user_id": int(user_id),
                "proposed_employee_id": proposed_employee_id,
            },
        ).scalar_one()
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_r2_4a_execute_items_table_exists():
    _require_r2_4a()
    with engine.connect() as conn:
        assert table_exists(conn, "user_linkage_execute_items")
        cols = set(get_columns(conn, "user_linkage_execute_items"))
        for col in EXECUTE_ITEM_COLUMNS:
            assert col in cols, f"missing column: {col}"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_r2_4a_run_table_extended_for_phase_r2():
    _require_r2_4a()
    with engine.connect() as conn:
        cols = set(get_columns(conn, "identity_reconciliation_runs"))
        for col in R2_RUN_COLUMNS:
            assert col in cols, f"missing column: {col}"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_r2_4a_run_phase_and_operation_constraints(seed):
    _require_r2_4a()
    with _isolated_conn() as conn:
        with pytest.raises(Exception):
            with conn.begin_nested():
                conn.execute(
                    text(
                        """
                        INSERT INTO public.identity_reconciliation_runs (
                            phase, operation, dry_run, actor_user_id, status
                        ) VALUES (
                            'R2', NULL, TRUE, :actor_user_id, 'running'
                        )
                        """
                    ),
                    {"actor_user_id": int(seed["initiator_user_id"])},
                )

        with pytest.raises(Exception):
            with conn.begin_nested():
                conn.execute(
                    text(
                        """
                        INSERT INTO public.identity_reconciliation_runs (
                            phase, operation, dry_run, actor_user_id, status
                        ) VALUES (
                            'R1a', 'USER_LINKAGE_EXECUTE', TRUE, :actor_user_id, 'running'
                        )
                        """
                    ),
                    {"actor_user_id": int(seed["initiator_user_id"])},
                )

        run_id = conn.execute(
            text(
                """
                INSERT INTO public.identity_reconciliation_runs (
                    phase, operation, dry_run, actor_user_id, status, summary
                ) VALUES (
                    'R2', 'USER_LINKAGE_EXECUTE_PREVIEW', TRUE, :actor_user_id, 'running', '{}'::jsonb
                )
                RETURNING run_id
                """
            ),
            {"actor_user_id": int(seed["initiator_user_id"])},
        ).scalar_one()
        assert int(run_id) > 0


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_r2_4a_execute_item_fk_and_snapshots(seed):
    _require_r2_4a()
    _require_r2_tables()
    with _isolated_conn() as conn:
        employee_id = _create_employee(
            conn,
            full_name="Execute Schema Employee",
            org_unit_id=int(seed["unit_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name="Execute Schema Employee",
            login=f"exec_schema_{employee_id}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        decision_id = _insert_review_decision(
            conn,
            reviewer_user_id=int(seed["initiator_user_id"]),
            user_id=user_id,
            proposed_employee_id=employee_id,
        )
        run_id = conn.execute(
            text(
                """
                INSERT INTO public.identity_reconciliation_runs (
                    phase, operation, dry_run, actor_user_id, status, summary
                ) VALUES (
                    'R2', 'USER_LINKAGE_EXECUTE', FALSE, :actor_user_id, 'running', '{}'::jsonb
                )
                RETURNING run_id
                """
            ),
            {"actor_user_id": int(seed["initiator_user_id"])},
        ).scalar_one()

        preview_snapshot = {"classification": "REVIEW_REQUIRED", "proposed_employee_id": employee_id}
        decision_snapshot = {"decision_id": decision_id, "decision": "APPROVE"}
        before_snapshot = {"user_id": user_id, "employee_id": None}
        item_id = conn.execute(
            text(
                """
                INSERT INTO public.user_linkage_execute_items (
                    run_id,
                    user_id,
                    proposed_employee_id,
                    source_decision_id,
                    action,
                    status,
                    reason_codes,
                    preview_snapshot,
                    decision_snapshot,
                    before_user_snapshot,
                    after_user_snapshot,
                    rollback_payload
                ) VALUES (
                    :run_id,
                    :user_id,
                    :proposed_employee_id,
                    :source_decision_id,
                    'SKIP_PREVIEW_DRIFT',
                    'SKIPPED',
                    CAST(:reason_codes AS jsonb),
                    CAST(:preview_snapshot AS jsonb),
                    CAST(:decision_snapshot AS jsonb),
                    CAST(:before_user_snapshot AS jsonb),
                    CAST(:after_user_snapshot AS jsonb),
                    CAST(:rollback_payload AS jsonb)
                )
                RETURNING item_id
                """
            ),
            {
                "run_id": int(run_id),
                "user_id": int(user_id),
                "proposed_employee_id": int(employee_id),
                "source_decision_id": int(decision_id),
                "reason_codes": json.dumps(["PREVIEW_DRIFT"]),
                "preview_snapshot": json.dumps(preview_snapshot),
                "decision_snapshot": json.dumps(decision_snapshot),
                "before_user_snapshot": json.dumps(before_snapshot),
                "after_user_snapshot": json.dumps(before_snapshot),
                "rollback_payload": json.dumps({"user_id": user_id, "previous_employee_id": None}),
            },
        ).scalar_one()
        assert int(item_id) > 0

        row = conn.execute(
            text(
                """
                SELECT action, status, preview_snapshot, decision_snapshot
                FROM public.user_linkage_execute_items
                WHERE item_id = :item_id
                """
            ),
            {"item_id": int(item_id)},
        ).mappings().one()
        assert row["action"] == "SKIP_PREVIEW_DRIFT"
        assert row["status"] == "SKIPPED"
        assert row["preview_snapshot"]["classification"] == "REVIEW_REQUIRED"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.parametrize("bad_action", ("INVALID_ACTION", "UPDATE_USERS_EMPLOYEE_ID"))
def test_r2_4a_execute_item_action_check_rejects_invalid(bad_action, seed):
    _require_r2_4a()
    _require_r2_tables()
    with _isolated_conn() as conn:
        run_id = conn.execute(
            text(
                """
                INSERT INTO public.identity_reconciliation_runs (
                    phase, operation, dry_run, actor_user_id, status
                ) VALUES (
                    'R2', 'USER_LINKAGE_EXECUTE_PREVIEW', TRUE, :actor_user_id, 'running'
                )
                RETURNING run_id
                """
            ),
            {"actor_user_id": int(seed["initiator_user_id"])},
        ).scalar_one()
        user_id = _create_unlinked_user(
            conn,
            full_name=f"Bad Action User {uuid4().hex[:6]}",
            login=f"bad_action_{uuid4().hex[:8]}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        with pytest.raises(Exception):
            conn.execute(
                text(
                    """
                    INSERT INTO public.user_linkage_execute_items (
                        run_id, user_id, action, status
                    ) VALUES (
                        :run_id, :user_id, :action, 'PLANNED'
                    )
                    """
                ),
                {"run_id": int(run_id), "user_id": int(user_id), "action": bad_action},
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.parametrize("action", VALID_ACTIONS)
@pytest.mark.parametrize("status", VALID_STATUSES)
def test_r2_4a_execute_item_action_status_values_accepted(action, status, seed):
    _require_r2_4a()
    _require_r2_tables()
    with _isolated_conn() as conn:
        run_id = conn.execute(
            text(
                """
                INSERT INTO public.identity_reconciliation_runs (
                    phase, operation, dry_run, actor_user_id, status
                ) VALUES (
                    'R2', 'USER_LINKAGE_EXECUTE_PREVIEW', TRUE, :actor_user_id, 'running'
                )
                RETURNING run_id
                """
            ),
            {"actor_user_id": int(seed["initiator_user_id"])},
        ).scalar_one()
        user_id = _create_unlinked_user(
            conn,
            full_name=f"Enum User {uuid4().hex[:6]}",
            login=f"enum_{uuid4().hex[:8]}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        item_id = conn.execute(
            text(
                """
                INSERT INTO public.user_linkage_execute_items (
                    run_id, user_id, action, status
                ) VALUES (
                    :run_id, :user_id, :action, :status
                )
                RETURNING item_id
                """
            ),
            {
                "run_id": int(run_id),
                "user_id": int(user_id),
                "action": action,
                "status": status,
            },
        ).scalar_one()
        assert int(item_id) > 0


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_r2_4a_users_employee_id_unchanged_by_schema(seed):
    _require_r2_4a()
    _require_r2_tables()
    with engine.connect() as conn:
        before = _linked_user_count(conn)
    with _isolated_conn() as conn:
        employee_id = _create_employee(
            conn,
            full_name="No Link Employee",
            org_unit_id=int(seed["unit_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name="No Link Employee",
            login=f"no_link_{employee_id}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        decision_id = _insert_review_decision(
            conn,
            reviewer_user_id=int(seed["initiator_user_id"]),
            user_id=user_id,
            proposed_employee_id=employee_id,
        )
        run_id = conn.execute(
            text(
                """
                INSERT INTO public.identity_reconciliation_runs (
                    phase, operation, dry_run, actor_user_id, status
                ) VALUES (
                    'R2', 'USER_LINKAGE_EXECUTE_PREVIEW', TRUE, :actor_user_id, 'completed'
                )
                RETURNING run_id
                """
            ),
            {"actor_user_id": int(seed["initiator_user_id"])},
        ).scalar_one()
        conn.execute(
            text(
                """
                INSERT INTO public.user_linkage_execute_items (
                    run_id,
                    user_id,
                    proposed_employee_id,
                    source_decision_id,
                    action,
                    status,
                    before_user_snapshot,
                    after_user_snapshot
                ) VALUES (
                    :run_id,
                    :user_id,
                    :proposed_employee_id,
                    :source_decision_id,
                    'SKIP_NOT_APPROVED',
                    'PLANNED',
                    CAST(:before_user_snapshot AS jsonb),
                    CAST(:before_user_snapshot AS jsonb)
                )
                """
            ),
            {
                "run_id": int(run_id),
                "user_id": int(user_id),
                "proposed_employee_id": int(employee_id),
                "source_decision_id": int(decision_id),
                "before_user_snapshot": json.dumps({"user_id": user_id, "employee_id": None}),
            },
        )
        assert conn.execute(
            text("SELECT employee_id FROM public.users WHERE user_id = :user_id"),
            {"user_id": int(user_id)},
        ).scalar_one() is None
    with engine.connect() as conn:
        after = _linked_user_count(conn)
    assert before == after


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_r2_4a_review_decisions_remain_readable(seed):
    _require_r2_4a()
    _require_r2_tables()
    with _isolated_conn() as conn:
        employee_id = _create_employee(
            conn,
            full_name="Review Readable Employee",
            org_unit_id=int(seed["unit_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name="Review Readable Employee",
            login=f"review_read_{employee_id}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        decision_id = _insert_review_decision(
            conn,
            reviewer_user_id=int(seed["initiator_user_id"]),
            user_id=user_id,
            proposed_employee_id=employee_id,
        )
        row = conn.execute(
            text(
                """
                SELECT decision_id, user_id, proposed_employee_id, decision, reason
                FROM public.user_linkage_review_decisions
                WHERE decision_id = :decision_id
                """
            ),
            {"decision_id": int(decision_id)},
        ).mappings().one()
        assert int(row["decision_id"]) == int(decision_id)
        assert row["decision"] == "APPROVE"
        assert int(row["proposed_employee_id"]) == int(employee_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_r2_4a_users_employee_id_unique_index_exists():
    _require_r2_4a()
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'users'
                  AND indexname = 'uq_users_employee_id'
                """
            )
        ).first()
        assert row is not None, "uq_users_employee_id partial unique index must exist (migration c3d8e12a5f01)"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_r2_4a_r1a_runs_remain_backward_compatible(seed):
    _require_r2_4a()
    with _isolated_conn() as conn:
        run_id = conn.execute(
            text(
                """
                INSERT INTO public.identity_reconciliation_runs (
                    phase, dry_run, actor_user_id, status, summary
                ) VALUES (
                    'R1a', TRUE, :actor_user_id, 'running', '{}'::jsonb
                )
                RETURNING run_id
                """
            ),
            {"actor_user_id": int(seed["initiator_user_id"])},
        ).scalar_one()
        assert int(run_id) > 0


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_r2_4a_security_audit_accepts_user_employee_linked(seed):
    _require_r2_4a()
    with _isolated_conn() as conn:
        cols = get_columns(conn, "security_audit_log")
        if "event_type" not in cols:
            pytest.skip("security_audit_log.event_type missing")
        conn.execute(
            text(
                """
                INSERT INTO public.security_audit_log (event_type, actor_user_id, metadata)
                VALUES ('USER_EMPLOYEE_LINKED', :actor_user_id, '{}'::jsonb)
                """
            ),
            {"actor_user_id": int(seed["initiator_user_id"])},
        )
