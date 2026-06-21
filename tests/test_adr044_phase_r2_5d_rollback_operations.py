# tests/test_adr044_phase_r2_5d_rollback_operations.py
"""Tests for ADR-044 R2.5d rollback linkage operations."""
from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.user_linkage_journal_constants import (
    ACTION_LINK,
    ACTION_MANUAL_LINK,
    ACTION_MANUAL_UNLINK,
    ACTION_ROLLBACK_LINK,
    OPERATION_ROLLBACK_ITEM,
    REASON_ROLLBACK_ALREADY_APPLIED,
    REASON_ROLLBACK_TARGET_CHANGED,
    STATUS_APPLIED,
    STATUS_FAILED,
    STATUS_NOOP_ALREADY_ROLLED_BACK,
)
from app.services.user_linkage_execute_service import (
    build_user_linkage_execute_preview_report,
    execute_items_available,
    execute_user_linkage_from_preview,
)
from app.services.user_linkage_operations_service import (
    UserLinkageOperationsError,
    manual_link_user,
    manual_unlink_user,
    rollback_linkage_item_for_user,
)
from app.services.user_linkage_review_service import (
    DECISION_APPROVE,
    record_user_linkage_review_decision,
    review_decisions_available,
)
from tests.conftest import get_columns, insert_returning_id, table_exists

VALID_REASON = "Rollback operation per ticket HR-9920"


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_schema() -> None:
    with engine.connect() as conn:
        if not execute_items_available(conn):
            pytest.skip("ADR-044 R2.5 schema missing — run alembic upgrade head")
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
        if row is None:
            pytest.skip("ADR-044 R2.5b schema missing — run alembic upgrade head")
        constraint = conn.execute(
            text(
                """
                SELECT pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conname = 'chk_sal_event_type'
                LIMIT 1
                """
            )
        ).scalar_one_or_none()
        if not constraint or "USER_EMPLOYEE_LINK_ROLLED_BACK" not in str(constraint):
            pytest.skip("ADR-044 R2.5d audit event missing — run alembic upgrade head")


def _require_r2_tables() -> None:
    with engine.connect() as conn:
        for table in ("users", "employees", "security_audit_log"):
            if not table_exists(conn, table):
                pytest.skip(f"Required table missing: {table}")
        if not review_decisions_available(conn):
            pytest.skip("user_linkage_review_decisions table missing")


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
            "full_name": f"Rollback User {suffix}",
            "google_login": f"r25d_{suffix}@pytest.local",
            "login": login,
            "role_id": int(role_id),
            "unit_id": int(org_unit_id),
            "employee_id": None,
            "is_active": True,
        },
    )


def _employee_id_for_user(conn, user_id: int) -> Optional[int]:
    value = conn.execute(
        text("SELECT employee_id FROM public.users WHERE user_id = :user_id"),
        {"user_id": int(user_id)},
    ).scalar_one()
    return int(value) if value is not None else None


def _audit_count(conn, *, event_type: str, user_id: int) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(*) AS cnt
                FROM public.security_audit_log
                WHERE event_type = :event_type
                  AND target_user_id = :user_id
                """
            ),
            {"event_type": event_type, "user_id": int(user_id)},
        ).scalar_one()
    )


def _source_item_unchanged(conn, source_item_id: int, *, action: str, status: str) -> None:
    row = conn.execute(
        text(
            """
            SELECT action, status, rollback_payload
            FROM public.user_linkage_execute_items
            WHERE item_id = :item_id
            """
        ),
        {"item_id": int(source_item_id)},
    ).mappings().one()
    assert row["action"] == action
    assert row["status"] == status
    assert row["rollback_payload"]


def _cleanup(
    conn,
    *,
    user_ids: list[int],
    employee_ids: list[int],
    run_ids: list[int],
    reviewer_user_id: Optional[int] = None,
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
            text("DELETE FROM public.user_linkage_review_decisions WHERE user_id = :user_id"),
            {"user_id": int(user_id)},
        )
        conn.execute(
            text("DELETE FROM public.users WHERE user_id = :user_id"),
            {"user_id": int(user_id)},
        )
    if reviewer_user_id is not None and user_ids:
        conn.execute(
            text(
                """
                DELETE FROM public.user_linkage_review_decisions
                WHERE reviewer_user_id = :reviewer_user_id
                  AND user_id = ANY(:user_ids)
                """
            ),
            {
                "reviewer_user_id": int(reviewer_user_id),
                "user_ids": [int(uid) for uid in user_ids],
            },
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


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_rollback_manual_link_restores_null(seed):
    _require_schema()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    source_item_id: Optional[int] = None
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Rollback Manual Link Employee", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                login=f"rb_manual_link_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )

        link = manual_link_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=int(user_id),
            employee_id=int(employee_id),
            reason=VALID_REASON,
        )
        run_ids.append(int(link["run_id"]))
        source_item_id = int(link["item_id"])

        result = rollback_linkage_item_for_user(
            actor_user_id=int(seed["initiator_user_id"]),
            source_item_id=int(source_item_id),
            reason=VALID_REASON,
        )
        run_ids.append(int(result["run_id"]))

        assert result["operation"] == OPERATION_ROLLBACK_ITEM
        assert result["action"] == ACTION_ROLLBACK_LINK
        assert result["status"] == STATUS_APPLIED
        assert result["applied"] is True
        assert result["restored_employee_id"] is None
        with engine.connect() as conn:
            assert _employee_id_for_user(conn, int(user_id)) is None
            assert (
                _audit_count(conn, event_type="USER_EMPLOYEE_LINK_ROLLED_BACK", user_id=int(user_id))
                == 1
            )
            _source_item_unchanged(
                conn,
                int(source_item_id),
                action=ACTION_MANUAL_LINK,
                status=STATUS_APPLIED,
            )
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                _cleanup(
                    conn,
                    user_ids=[int(user_id)],
                    employee_ids=[int(employee_id)] if employee_id else [],
                    run_ids=run_ids,
                    reviewer_user_id=int(seed["initiator_user_id"]),
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_rollback_manual_unlink_restores_employee(seed):
    _require_schema()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    source_item_id: Optional[int] = None
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Rollback Manual Unlink Employee", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                login=f"rb_manual_unlink_{employee_id}",
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

        unlink = manual_unlink_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=int(user_id),
            reason=VALID_REASON,
        )
        run_ids.append(int(unlink["run_id"]))
        source_item_id = int(unlink["item_id"])

        result = rollback_linkage_item_for_user(
            actor_user_id=int(seed["initiator_user_id"]),
            source_item_id=int(source_item_id),
            reason=VALID_REASON,
        )
        run_ids.append(int(result["run_id"]))

        assert result["status"] == STATUS_APPLIED
        assert result["restored_employee_id"] == int(employee_id)
        with engine.connect() as conn:
            assert _employee_id_for_user(conn, int(user_id)) == int(employee_id)
            _source_item_unchanged(
                conn,
                int(source_item_id),
                action=ACTION_MANUAL_UNLINK,
                status=STATUS_APPLIED,
            )
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                _cleanup(
                    conn,
                    user_ids=[int(user_id)],
                    employee_ids=[int(employee_id)] if employee_id else [],
                    run_ids=run_ids,
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_rollback_execute_link_item(seed):
    _require_schema()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    source_item_id: Optional[int] = None
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Rollback Execute Employee", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                login=f"rb_execute_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )
            record_user_linkage_review_decision(
                conn,
                actor_user_id=int(seed["initiator_user_id"]),
                user_id=int(user_id),
                decision=DECISION_APPROVE,
            )
            preview = build_user_linkage_execute_preview_report(
                conn,
                actor_user_id=int(seed["initiator_user_id"]),
                user_id=int(user_id),
            )
            token = str(preview["confirm_token"])
            run_ids.append(int(preview["run_id"]))

        execute = execute_user_linkage_from_preview(
            actor_user_id=int(seed["initiator_user_id"]),
            preview_run_id=int(preview["run_id"]),
            confirm_token=token,
        )
        run_ids.append(int(execute["run_id"]))
        source_item_id = int(execute["items"][0]["item_id"])

        result = rollback_linkage_item_for_user(
            actor_user_id=int(seed["initiator_user_id"]),
            source_item_id=int(source_item_id),
            reason=VALID_REASON,
        )
        run_ids.append(int(result["run_id"]))

        assert result["source_action"] == ACTION_LINK
        assert result["status"] == STATUS_APPLIED
        with engine.connect() as conn:
            assert _employee_id_for_user(conn, int(user_id)) is None
            row = conn.execute(
                text(
                    """
                    SELECT action, status
                    FROM public.user_linkage_execute_items
                    WHERE item_id = :item_id
                    """
                ),
                {"item_id": int(source_item_id)},
            ).mappings().one()
            assert row["action"] == ACTION_LINK
            assert row["status"] == STATUS_APPLIED
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                _cleanup(
                    conn,
                    user_ids=[int(user_id)],
                    employee_ids=[int(employee_id)] if employee_id else [],
                    run_ids=run_ids,
                    reviewer_user_id=int(seed["initiator_user_id"]),
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_rollback_second_call_is_idempotent(seed):
    _require_schema()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Rollback Idempotent Employee", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                login=f"rb_idempotent_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )

        link = manual_link_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=int(user_id),
            employee_id=int(employee_id),
            reason=VALID_REASON,
        )
        run_ids.append(int(link["run_id"]))
        first = rollback_linkage_item_for_user(
            actor_user_id=int(seed["initiator_user_id"]),
            source_item_id=int(link["item_id"]),
            reason=VALID_REASON,
        )
        run_ids.append(int(first["run_id"]))
        second = rollback_linkage_item_for_user(
            actor_user_id=int(seed["initiator_user_id"]),
            source_item_id=int(link["item_id"]),
            reason=VALID_REASON,
        )
        run_ids.append(int(second["run_id"]))

        assert first["applied"] is True
        assert second["status"] == STATUS_NOOP_ALREADY_ROLLED_BACK
        assert second["applied"] is False
        with engine.connect() as conn:
            assert _employee_id_for_user(conn, int(user_id)) is None
            assert (
                _audit_count(conn, event_type="USER_EMPLOYEE_LINK_ROLLED_BACK", user_id=int(user_id))
                == 1
            )
            codes = conn.execute(
                text(
                    """
                    SELECT reason_codes
                    FROM public.user_linkage_execute_items
                    WHERE item_id = :item_id
                    """
                ),
                {"item_id": int(second["item_id"])},
            ).scalar_one()
            assert REASON_ROLLBACK_ALREADY_APPLIED in codes
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                _cleanup(
                    conn,
                    user_ids=[int(user_id)],
                    employee_ids=[int(employee_id)] if employee_id else [],
                    run_ids=run_ids,
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_rollback_target_changed_fails(seed):
    _require_schema()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    other_employee_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Rollback Target Employee", org_unit_id=int(seed["unit_id"])
            )
            other_employee_id = _create_employee(
                conn, full_name="Rollback Other Employee", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                login=f"rb_target_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )

        link = manual_link_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=int(user_id),
            employee_id=int(employee_id),
            reason=VALID_REASON,
        )
        run_ids.append(int(link["run_id"]))
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE public.users
                    SET employee_id = :employee_id
                    WHERE user_id = :user_id
                    """
                ),
                {"employee_id": int(other_employee_id), "user_id": int(user_id)},
            )

        result = rollback_linkage_item_for_user(
            actor_user_id=int(seed["initiator_user_id"]),
            source_item_id=int(link["item_id"]),
            reason=VALID_REASON,
        )
        run_ids.append(int(result["run_id"]))

        assert result["status"] == STATUS_FAILED
        assert result["applied"] is False
        with engine.connect() as conn:
            assert _employee_id_for_user(conn, int(user_id)) == int(other_employee_id)
            codes = conn.execute(
                text(
                    """
                    SELECT reason_codes
                    FROM public.user_linkage_execute_items
                    WHERE item_id = :item_id
                    """
                ),
                {"item_id": int(result["item_id"])},
            ).scalar_one()
            assert REASON_ROLLBACK_TARGET_CHANGED in codes
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                _cleanup(
                    conn,
                    user_ids=[int(user_id)],
                    employee_ids=[int(employee_id), int(other_employee_id)],
                    run_ids=run_ids,
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_rollback_missing_payload_rejected(seed):
    _require_schema()
    _require_r2_tables()
    user_id: Optional[int] = None
    run_id: Optional[int] = None
    item_id: Optional[int] = None
    try:
        with engine.begin() as conn:
            user_id = _create_unlinked_user(
                conn,
                login=f"rb_missing_payload_{uuid4().hex[:8]}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )
            run_id = conn.execute(
                text(
                    """
                    INSERT INTO public.identity_reconciliation_runs (
                        phase, operation, dry_run, actor_user_id, status, summary
                    ) VALUES (
                        'R2', 'USER_LINKAGE_MANUAL_LINK', FALSE, :actor_user_id, 'completed', '{}'::jsonb
                    )
                    RETURNING run_id
                    """
                ),
                {"actor_user_id": int(seed["initiator_user_id"])},
            ).scalar_one()
            item_id = conn.execute(
                text(
                    """
                    INSERT INTO public.user_linkage_execute_items (
                        run_id, user_id, action, status, rollback_payload
                    ) VALUES (
                        :run_id, :user_id, 'MANUAL_LINK', 'APPLIED', '{}'::jsonb
                    )
                    RETURNING item_id
                    """
                ),
                {"run_id": int(run_id), "user_id": int(user_id)},
            ).scalar_one()

        with pytest.raises(UserLinkageOperationsError, match="rollback_payload"):
            rollback_linkage_item_for_user(
                actor_user_id=int(seed["initiator_user_id"]),
                source_item_id=int(item_id),
                reason=VALID_REASON,
            )
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                if item_id is not None:
                    conn.execute(
                        text(
                            "DELETE FROM public.user_linkage_execute_items WHERE item_id = :item_id"
                        ),
                        {"item_id": int(item_id)},
                    )
                if run_id is not None:
                    conn.execute(
                        text(
                            "DELETE FROM public.identity_reconciliation_runs WHERE run_id = :run_id"
                        ),
                        {"run_id": int(run_id)},
                    )
                _cleanup(conn, user_ids=[int(user_id)], employee_ids=[], run_ids=[])


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_rollback_source_item_not_mutated(seed):
    _require_schema()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Immutable Source Employee", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                login=f"rb_immutable_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )

        link = manual_link_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=int(user_id),
            employee_id=int(employee_id),
            reason=VALID_REASON,
        )
        run_ids.append(int(link["run_id"]))
        with engine.connect() as conn:
            before_payload = conn.execute(
                text(
                    """
                    SELECT rollback_payload
                    FROM public.user_linkage_execute_items
                    WHERE item_id = :item_id
                    """
                ),
                {"item_id": int(link["item_id"])},
            ).scalar_one()

        rollback = rollback_linkage_item_for_user(
            actor_user_id=int(seed["initiator_user_id"]),
            source_item_id=int(link["item_id"]),
            reason=VALID_REASON,
        )
        run_ids.append(int(rollback["run_id"]))

        with engine.connect() as conn:
            after_payload = conn.execute(
                text(
                    """
                    SELECT rollback_payload, action, status
                    FROM public.user_linkage_execute_items
                    WHERE item_id = :item_id
                    """
                ),
                {"item_id": int(link["item_id"])},
            ).mappings().one()
            assert after_payload["rollback_payload"] == before_payload
            assert after_payload["action"] == ACTION_MANUAL_LINK
            assert after_payload["status"] == STATUS_APPLIED
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                _cleanup(
                    conn,
                    user_ids=[int(user_id)],
                    employee_ids=[int(employee_id)] if employee_id else [],
                    run_ids=run_ids,
                )
