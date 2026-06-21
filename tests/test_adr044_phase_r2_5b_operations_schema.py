# tests/test_adr044_phase_r2_5b_operations_schema.py
"""Schema tests for ADR-044 R2.5b user linkage operations journal DDL."""
from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Dict, Optional
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.user_linkage_journal_constants import (
    EXECUTE_ITEM_ACTIONS,
    EXECUTE_ITEM_STATUSES,
    EVENT_USER_EMPLOYEE_UNLINKED,
    OPERATION_MANUAL_LINK,
    OPERATION_REPAIR_PREVIEW,
    OPERATION_RERUN_EXECUTE,
    OPERATION_ROLLBACK_ITEM,
    R2_5_REASON_CODES,
    R2_RUN_OPERATIONS,
)
from tests.conftest import get_columns, insert_returning_id, table_exists

DDL_REVISION_R2_4A = "e4f5a6b7c8d9"
DDL_REVISION_R2_5B = "f5a6b7c8d9e0"

R2_5_OPERATIONS = (
    "USER_LINKAGE_MANUAL_LINK",
    "USER_LINKAGE_MANUAL_UNLINK",
    "USER_LINKAGE_ROLLBACK_ITEM",
    "USER_LINKAGE_REPAIR_PREVIEW",
    "USER_LINKAGE_RERUN_EXECUTE",
)

R2_5_ACTIONS = (
    "MANUAL_LINK",
    "MANUAL_UNLINK",
    "ROLLBACK_LINK",
    "REPAIR_PREVIEW",
    "RERUN_EXECUTE",
)

R2_5_STATUSES = (
    "NOOP_ALREADY_LINKED",
    "NOOP_ALREADY_UNLINKED",
    "NOOP_ALREADY_ROLLED_BACK",
)

R2_4_OPERATIONS = (
    "USER_LINKAGE_EXECUTE_PREVIEW",
    "USER_LINKAGE_EXECUTE",
)

R2_4_ACTIONS = (
    "LINK",
    "NOOP_ALREADY_LINKED",
    "SKIP_NOT_APPROVED",
    "SKIP_PREVIEW_DRIFT",
    "SKIP_CLASSIFICATION_REGRESSION",
    "SKIP_EXCLUDED",
    "FAIL_ALREADY_LINKED_DIFFERENT",
    "FAIL_EMPLOYEE_CONFLICT",
)

R2_4_STATUSES = ("PLANNED", "APPLIED", "SKIPPED", "FAILED")

R2_5_INDEXES = (
    "ix_irr_r2_operation_status_started",
    "ix_irr_r2_actor_started",
    "ix_irr_r2_summary_source_item",
    "uq_irr_r2_execute_running_per_preview",
    "ix_ulei_run_status_action",
    "ix_ulei_link_applied_user",
    "ix_ulei_rollback_applied_source",
    "ix_sal_target_employee",
    "ix_sal_user_employee_linked",
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _r2_5b_available() -> bool:
    with engine.connect() as conn:
        if not table_exists(conn, "user_linkage_execute_items"):
            return False
        row = conn.execute(
            text(
                """
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = 'uq_irr_r2_execute_running_per_preview'
                LIMIT 1
                """
            )
        ).first()
        return row is not None


def _require_r2_5b() -> None:
    if not _r2_5b_available():
        pytest.skip(
            f"ADR-044 R2.5b schema missing — run: alembic upgrade head (revision {DDL_REVISION_R2_5B})"
        )


def _require_r2_tables() -> None:
    with engine.connect() as conn:
        for table in ("users", "employees", "user_linkage_review_decisions"):
            if not table_exists(conn, table):
                pytest.skip(f"Required table missing: {table}")


@contextmanager
def _isolated_conn():
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            yield conn
        finally:
            trans.rollback()


def _create_unlinked_user(
    conn,
    *,
    full_name: str,
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
            "google_login": f"r25b_{suffix}@pytest.local",
            "login": f"r25b_{suffix}",
            "role_id": int(role_id),
            "unit_id": int(org_unit_id),
            "employee_id": None,
            "is_active": True,
        },
    )


def _insert_r2_run(
    conn,
    *,
    operation: str,
    actor_user_id: int,
    status: str = "completed",
    dry_run: bool = False,
    summary: Optional[dict[str, Any]] = None,
) -> int:
    return int(
        conn.execute(
            text(
                """
                INSERT INTO public.identity_reconciliation_runs (
                    phase, operation, dry_run, actor_user_id, status, summary
                ) VALUES (
                    'R2', :operation, :dry_run, :actor_user_id, :status,
                    CAST(:summary AS jsonb)
                )
                RETURNING run_id
                """
            ),
            {
                "operation": operation,
                "dry_run": dry_run,
                "actor_user_id": int(actor_user_id),
                "status": status,
                "summary": json.dumps(summary or {}),
            },
        ).scalar_one()
    )


def _index_exists(conn, index_name: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = :index_name
            LIMIT 1
            """
        ),
        {"index_name": index_name},
    ).first()
    return row is not None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_r2_5b_constants_align_with_schema_enums():
    _require_r2_5b()
    assert OPERATION_MANUAL_LINK in R2_RUN_OPERATIONS
    assert OPERATION_ROLLBACK_ITEM in R2_RUN_OPERATIONS
    assert OPERATION_REPAIR_PREVIEW in R2_RUN_OPERATIONS
    assert OPERATION_RERUN_EXECUTE in R2_RUN_OPERATIONS
    for action in R2_5_ACTIONS:
        assert action in EXECUTE_ITEM_ACTIONS
    for status in R2_5_STATUSES:
        assert status in EXECUTE_ITEM_STATUSES
    assert EVENT_USER_EMPLOYEE_UNLINKED == "USER_EMPLOYEE_UNLINKED"
    assert len(R2_5_REASON_CODES) == 7


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.parametrize("operation", R2_5_OPERATIONS)
def test_r2_5b_run_operation_values_accepted(operation, seed):
    _require_r2_5b()
    with _isolated_conn() as conn:
        run_id = _insert_r2_run(
            conn,
            operation=operation,
            actor_user_id=int(seed["initiator_user_id"]),
        )
        assert run_id > 0


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.parametrize("operation", R2_4_OPERATIONS)
def test_r2_5b_r2_4_run_operations_remain_valid(operation, seed):
    _require_r2_5b()
    with _isolated_conn() as conn:
        run_id = _insert_r2_run(
            conn,
            operation=operation,
            actor_user_id=int(seed["initiator_user_id"]),
            dry_run=operation.endswith("_PREVIEW"),
        )
        assert run_id > 0


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.parametrize("action", R2_5_ACTIONS)
@pytest.mark.parametrize("status", list(R2_4_STATUSES) + list(R2_5_STATUSES))
def test_r2_5b_item_action_status_values_accepted(action, status, seed):
    _require_r2_5b()
    _require_r2_tables()
    with _isolated_conn() as conn:
        run_id = _insert_r2_run(
            conn,
            operation=OPERATION_MANUAL_LINK,
            actor_user_id=int(seed["initiator_user_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name=f"R25B User {uuid4().hex[:6]}",
            role_id=int(seed["executor_role_id"]),
            org_unit_id=int(seed["unit_id"]),
        )
        item_id = conn.execute(
            text(
                """
                INSERT INTO public.user_linkage_execute_items (
                    run_id, user_id, action, status, reason_codes
                ) VALUES (
                    :run_id, :user_id, :action, :status, CAST(:reason_codes AS jsonb)
                )
                RETURNING item_id
                """
            ),
            {
                "run_id": int(run_id),
                "user_id": int(user_id),
                "action": action,
                "status": status,
                "reason_codes": json.dumps(list(R2_5_REASON_CODES)[:1]),
            },
        ).scalar_one()
        assert int(item_id) > 0


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.parametrize("action", R2_4_ACTIONS)
@pytest.mark.parametrize("status", R2_4_STATUSES)
def test_r2_5b_r2_4_item_action_status_values_remain_valid(action, status, seed):
    _require_r2_5b()
    _require_r2_tables()
    with _isolated_conn() as conn:
        run_id = _insert_r2_run(
            conn,
            operation="USER_LINKAGE_EXECUTE_PREVIEW",
            actor_user_id=int(seed["initiator_user_id"]),
            dry_run=True,
        )
        user_id = _create_unlinked_user(
            conn,
            full_name=f"R24 Compat {uuid4().hex[:6]}",
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
def test_r2_5b_invalid_operation_rejected(seed):
    _require_r2_5b()
    with _isolated_conn() as conn:
        with pytest.raises(Exception):
            conn.execute(
                text(
                    """
                    INSERT INTO public.identity_reconciliation_runs (
                        phase, operation, dry_run, actor_user_id, status
                    ) VALUES (
                        'R2', 'USER_LINKAGE_REPAIR', TRUE, :actor_user_id, 'running'
                    )
                    """
                ),
                {"actor_user_id": int(seed["initiator_user_id"])},
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_r2_5b_invalid_action_rejected(seed):
    _require_r2_5b()
    _require_r2_tables()
    with _isolated_conn() as conn:
        run_id = _insert_r2_run(
            conn,
            operation=OPERATION_MANUAL_LINK,
            actor_user_id=int(seed["initiator_user_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name="Invalid Action User",
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
                        :run_id, :user_id, 'INVALID_OPS_ACTION', 'APPLIED'
                    )
                    """
                ),
                {"run_id": int(run_id), "user_id": int(user_id)},
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_r2_5b_invalid_status_rejected(seed):
    _require_r2_5b()
    _require_r2_tables()
    with _isolated_conn() as conn:
        run_id = _insert_r2_run(
            conn,
            operation=OPERATION_MANUAL_LINK,
            actor_user_id=int(seed["initiator_user_id"]),
        )
        user_id = _create_unlinked_user(
            conn,
            full_name="Invalid Status User",
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
                        :run_id, :user_id, 'MANUAL_LINK', 'INVALID_STATUS'
                    )
                    """
                ),
                {"run_id": int(run_id), "user_id": int(user_id)},
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.parametrize("index_name", R2_5_INDEXES)
def test_r2_5b_indexes_exist(index_name):
    _require_r2_5b()
    with engine.connect() as conn:
        assert _index_exists(conn, index_name), f"missing index: {index_name}"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_r2_5b_security_audit_accepts_user_employee_unlinked(seed):
    _require_r2_5b()
    with _isolated_conn() as conn:
        cols = get_columns(conn, "security_audit_log")
        if "event_type" not in cols:
            pytest.skip("security_audit_log.event_type missing")
        conn.execute(
            text(
                """
                INSERT INTO public.security_audit_log (event_type, actor_user_id, metadata)
                VALUES ('USER_EMPLOYEE_UNLINKED', :actor_user_id, '{}'::jsonb)
                """
            ),
            {"actor_user_id": int(seed["initiator_user_id"])},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_r2_5b_concurrent_execute_running_unique_per_preview(seed):
    _require_r2_5b()
    with _isolated_conn() as conn:
        preview_run_id = _insert_r2_run(
            conn,
            operation="USER_LINKAGE_EXECUTE_PREVIEW",
            actor_user_id=int(seed["initiator_user_id"]),
            dry_run=True,
        )
        summary = {"source_preview_run_id": int(preview_run_id)}
        first = _insert_r2_run(
            conn,
            operation="USER_LINKAGE_EXECUTE",
            actor_user_id=int(seed["initiator_user_id"]),
            status="running",
            summary=summary,
        )
        assert first > 0
        with pytest.raises(Exception):
            conn.execute(
                text(
                    """
                    INSERT INTO public.identity_reconciliation_runs (
                        phase, operation, dry_run, actor_user_id, status, summary
                    ) VALUES (
                        'R2', 'USER_LINKAGE_EXECUTE', FALSE, :actor_user_id, 'running',
                        CAST(:summary AS jsonb)
                    )
                    """
                ),
                {
                    "actor_user_id": int(seed["initiator_user_id"]),
                    "summary": json.dumps(summary),
                },
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_r2_5b_r1a_runs_remain_backward_compatible(seed):
    _require_r2_5b()
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
def test_r2_5b_rollback_run_summary_source_item_index_usable(seed):
    _require_r2_5b()
    with _isolated_conn() as conn:
        source_item_id = 424242
        run_id = _insert_r2_run(
            conn,
            operation=OPERATION_ROLLBACK_ITEM,
            actor_user_id=int(seed["initiator_user_id"]),
            summary={"source_item_id": source_item_id, "reason": "schema test"},
        )
        row = conn.execute(
            text(
                """
                SELECT run_id
                FROM public.identity_reconciliation_runs
                WHERE phase = 'R2'
                  AND operation = 'USER_LINKAGE_ROLLBACK_ITEM'
                  AND summary->>'source_item_id' = :source_item_id
                """
            ),
            {"source_item_id": str(source_item_id)},
        ).scalar_one()
        assert int(row) == int(run_id)
