# tests/test_adr044_phase_r2_5c_manual_link_unlink.py
"""Tests for ADR-044 R2.5c manual link/unlink operations service."""
from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.user_linkage_journal_constants import (
    ACTION_MANUAL_LINK,
    ACTION_MANUAL_UNLINK,
    OPERATION_MANUAL_LINK,
    OPERATION_MANUAL_UNLINK,
    REASON_LINK_TARGET_CONFLICT,
    STATUS_APPLIED,
    STATUS_FAILED,
    STATUS_NOOP_ALREADY_LINKED,
    STATUS_NOOP_ALREADY_UNLINKED,
)
from app.services.user_linkage_execute_service import execute_items_available
from app.services.user_linkage_operations_service import (
    UserLinkageOperationsError,
    manual_link_user,
    manual_link_user_employee,
    manual_unlink_user,
)
from tests.conftest import get_columns, insert_returning_id, table_exists

VALID_REASON = "HR confirmed manual linkage per ticket HR-9912"


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
    full_name: Optional[str] = None,
) -> int:
    suffix = uuid4().hex[:8]
    return insert_returning_id(
        conn,
        table="users",
        id_col="user_id",
        values={
            "full_name": full_name or f"Manual Ops User {suffix}",
            "google_login": f"r25c_{suffix}@pytest.local",
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


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_manual_link_links_unlinked_user_and_writes_journal(seed):
    _require_r2_5b()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Manual Link Employee", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                login=f"manual_link_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )

        result = manual_link_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=int(user_id),
            employee_id=int(employee_id),
            reason=VALID_REASON,
        )
        run_ids.append(int(result["run_id"]))

        assert result["operation"] == OPERATION_MANUAL_LINK
        assert result["action"] == ACTION_MANUAL_LINK
        assert result["status"] == STATUS_APPLIED
        assert result["applied"] is True
        assert result["audit_created"] is True
        assert result["before_user_snapshot"]["employee_id"] is None
        assert result["after_user_snapshot"]["employee_id"] == int(employee_id)
        assert result["rollback_payload"] == {
            "user_id": int(user_id),
            "previous_employee_id": None,
            "employee_id": int(employee_id),
            "decision_id": None,
        }

        with engine.connect() as conn:
            assert _employee_id_for_user(conn, int(user_id)) == int(employee_id)
            assert _audit_count(conn, event_type="USER_EMPLOYEE_LINKED", user_id=int(user_id)) == 1
            run_row = conn.execute(
                text(
                    """
                    SELECT operation, status, summary
                    FROM public.identity_reconciliation_runs
                    WHERE run_id = :run_id
                    """
                ),
                {"run_id": int(result["run_id"])},
            ).mappings().one()
            assert run_row["operation"] == OPERATION_MANUAL_LINK
            assert run_row["status"] == "completed"
            assert int(run_row["summary"]["applied"]) == 1
            item_row = conn.execute(
                text(
                    """
                    SELECT action, status, rollback_payload
                    FROM public.user_linkage_execute_items
                    WHERE item_id = :item_id
                    """
                ),
                {"item_id": int(result["item_id"])},
            ).mappings().one()
            assert item_row["action"] == ACTION_MANUAL_LINK
            assert item_row["status"] == STATUS_APPLIED
            assert item_row["rollback_payload"]["employee_id"] == int(employee_id)
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
def test_manual_link_same_target_is_idempotent(seed):
    _require_r2_5b()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Idempotent Link Employee", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                login=f"idempotent_link_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )

        first = manual_link_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=int(user_id),
            employee_id=int(employee_id),
            reason=VALID_REASON,
        )
        run_ids.append(int(first["run_id"]))
        second = manual_link_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=int(user_id),
            employee_id=int(employee_id),
            reason=VALID_REASON,
        )
        run_ids.append(int(second["run_id"]))

        assert second["status"] == STATUS_NOOP_ALREADY_LINKED
        assert second["applied"] is False
        assert second["audit_created"] is False
        with engine.connect() as conn:
            assert _audit_count(conn, event_type="USER_EMPLOYEE_LINKED", user_id=int(user_id)) == 1
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
def test_manual_link_different_target_fails_without_overwrite(seed):
    _require_r2_5b()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_a: Optional[int] = None
    employee_b: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_a = _create_employee(
                conn, full_name="Linked Employee A", org_unit_id=int(seed["unit_id"])
            )
            employee_b = _create_employee(
                conn, full_name="Linked Employee B", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                login=f"conflict_link_{employee_a}",
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
                {"employee_id": int(employee_a), "user_id": int(user_id)},
            )

        result = manual_link_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=int(user_id),
            employee_id=int(employee_b),
            reason=VALID_REASON,
        )
        run_ids.append(int(result["run_id"]))

        assert result["status"] == STATUS_FAILED
        assert result["applied"] is False
        with engine.connect() as conn:
            assert _employee_id_for_user(conn, int(user_id)) == int(employee_a)
            item_codes = conn.execute(
                text(
                    """
                    SELECT reason_codes
                    FROM public.user_linkage_execute_items
                    WHERE item_id = :item_id
                    """
                ),
                {"item_id": int(result["item_id"])},
            ).scalar_one()
            assert REASON_LINK_TARGET_CONFLICT in item_codes
            assert _audit_count(conn, event_type="USER_EMPLOYEE_LINKED", user_id=int(user_id)) == 0
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                _cleanup(
                    conn,
                    user_ids=[int(user_id)],
                    employee_ids=[int(employee_a), int(employee_b)],
                    run_ids=run_ids,
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_manual_link_employee_slot_conflict_fails(seed):
    _require_r2_5b()
    _require_r2_tables()
    user_a: Optional[int] = None
    user_b: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Occupied Employee", org_unit_id=int(seed["unit_id"])
            )
            user_a = _create_unlinked_user(
                conn,
                login=f"occupier_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )
            user_b = _create_unlinked_user(
                conn,
                login=f"blocked_{employee_id}",
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
                {"employee_id": int(employee_id), "user_id": int(user_a)},
            )

        result = manual_link_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=int(user_b),
            employee_id=int(employee_id),
            reason=VALID_REASON,
        )
        run_ids.append(int(result["run_id"]))

        assert result["status"] == STATUS_FAILED
        assert result["applied"] is False
        with engine.connect() as conn:
            assert _employee_id_for_user(conn, int(user_b)) is None
    finally:
        with engine.begin() as conn:
            _cleanup(
                conn,
                user_ids=[int(user_a), int(user_b)],
                employee_ids=[int(employee_id)] if employee_id else [],
                run_ids=run_ids,
            )


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"reason": ""}, "reason is required"),
        ({"reason": "short"}, "reason is required"),
        ({"actor_user_id": 0}, "actor_user_id is required"),
    ],
)
@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_manual_link_rejects_invalid_input(seed, kwargs, match):
    _require_r2_5b()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Reject Link Employee", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                login=f"reject_link_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )

        params = {
            "actor_user_id": int(seed["initiator_user_id"]),
            "user_id": int(user_id),
            "employee_id": int(employee_id),
            "reason": VALID_REASON,
        }
        params.update(kwargs)
        with pytest.raises(UserLinkageOperationsError, match=match):
            manual_link_user(**params)
        with engine.connect() as conn:
            assert _employee_id_for_user(conn, int(user_id)) is None
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                _cleanup(
                    conn,
                    user_ids=[int(user_id)],
                    employee_ids=[int(employee_id)] if employee_id else [],
                    run_ids=[],
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_manual_link_rejects_missing_user_and_employee(seed):
    _require_r2_5b()
    _require_r2_tables()
    with pytest.raises(UserLinkageOperationsError, match="user_id=999999999 not found"):
        manual_link_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=999999999,
            employee_id=999999998,
            reason=VALID_REASON,
        )

    employee_id: Optional[int] = None
    user_id: Optional[int] = None
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Missing User Employee", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                login=f"missing_user_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )
        with pytest.raises(UserLinkageOperationsError, match="employee_id=999999998 not found"):
            manual_link_user(
                actor_user_id=int(seed["initiator_user_id"]),
                user_id=int(user_id),
                employee_id=999999998,
                reason=VALID_REASON,
            )
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                _cleanup(
                    conn,
                    user_ids=[int(user_id)],
                    employee_ids=[int(employee_id)] if employee_id else [],
                    run_ids=[],
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_manual_link_blocks_service_account(seed):
    _require_r2_5b()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Service Block Employee", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                login="admin_service_account",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )
        with pytest.raises(UserLinkageOperationsError, match="service account"):
            manual_link_user(
                actor_user_id=int(seed["initiator_user_id"]),
                user_id=int(user_id),
                employee_id=int(employee_id),
                reason=VALID_REASON,
            )
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                _cleanup(
                    conn,
                    user_ids=[int(user_id)],
                    employee_ids=[int(employee_id)] if employee_id else [],
                    run_ids=[],
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_manual_unlink_unlinks_linked_user_and_writes_journal(seed):
    _require_r2_5b()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Manual Unlink Employee", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                login=f"manual_unlink_{employee_id}",
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

        result = manual_unlink_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=int(user_id),
            reason=VALID_REASON,
        )
        run_ids.append(int(result["run_id"]))

        assert result["operation"] == OPERATION_MANUAL_UNLINK
        assert result["action"] == ACTION_MANUAL_UNLINK
        assert result["status"] == STATUS_APPLIED
        assert result["applied"] is True
        assert result["audit_created"] is True
        assert result["before_user_snapshot"]["employee_id"] == int(employee_id)
        assert result["after_user_snapshot"]["employee_id"] is None
        assert result["rollback_payload"] == {
            "user_id": int(user_id),
            "previous_employee_id": int(employee_id),
            "employee_id": None,
            "decision_id": None,
        }
        with engine.connect() as conn:
            assert _employee_id_for_user(conn, int(user_id)) is None
            assert _audit_count(conn, event_type="USER_EMPLOYEE_UNLINKED", user_id=int(user_id)) == 1
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
def test_manual_unlink_already_unlinked_is_idempotent(seed):
    _require_r2_5b()
    _require_r2_tables()
    user_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            user_id = _create_unlinked_user(
                conn,
                login=f"already_unlinked_{uuid4().hex[:8]}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )

        result = manual_unlink_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=int(user_id),
            reason=VALID_REASON,
        )
        run_ids.append(int(result["run_id"]))

        assert result["status"] == STATUS_NOOP_ALREADY_UNLINKED
        assert result["applied"] is False
        assert result["audit_created"] is False
        with engine.connect() as conn:
            assert _audit_count(conn, event_type="USER_EMPLOYEE_UNLINKED", user_id=int(user_id)) == 0
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                _cleanup(conn, user_ids=[int(user_id)], employee_ids=[], run_ids=run_ids)


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"reason": ""}, "reason is required"),
        ({"actor_user_id": None}, "actor_user_id is required"),
    ],
)
@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_manual_unlink_rejects_invalid_input(seed, kwargs, match):
    _require_r2_5b()
    _require_r2_tables()
    user_id: Optional[int] = None
    try:
        with engine.begin() as conn:
            user_id = _create_unlinked_user(
                conn,
                login=f"reject_unlink_{uuid4().hex[:8]}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )
        params = {
            "actor_user_id": int(seed["initiator_user_id"]),
            "user_id": int(user_id),
            "reason": VALID_REASON,
        }
        params.update(kwargs)
        with pytest.raises(UserLinkageOperationsError, match=match):
            manual_unlink_user(**params)
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                _cleanup(conn, user_ids=[int(user_id)], employee_ids=[], run_ids=[])


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_manual_unlink_rejects_missing_user(seed):
    _require_r2_5b()
    _require_r2_tables()
    with pytest.raises(UserLinkageOperationsError, match="user_id=999999999 not found"):
        manual_unlink_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=999999999,
            reason=VALID_REASON,
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_manual_link_conn_api_is_atomic_on_failure(seed):
    _require_r2_5b()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_a: Optional[int] = None
    employee_b: Optional[int] = None
    try:
        with engine.begin() as conn:
            employee_a = _create_employee(
                conn, full_name="Atomic A", org_unit_id=int(seed["unit_id"])
            )
            employee_b = _create_employee(
                conn, full_name="Atomic B", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                login=f"atomic_{employee_a}",
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
                {"employee_id": int(employee_a), "user_id": int(user_id)},
            )

        with engine.begin() as conn:
            result = manual_link_user_employee(
                conn,
                actor_user_id=int(seed["initiator_user_id"]),
                user_id=int(user_id),
                employee_id=int(employee_b),
                reason=VALID_REASON,
            )
            assert result["status"] == STATUS_FAILED

        with engine.connect() as conn:
            run_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM public.identity_reconciliation_runs
                    WHERE operation = :operation
                      AND summary->>'reason' = :reason
                    """
                ),
                {"operation": OPERATION_MANUAL_LINK, "reason": VALID_REASON},
            ).scalar_one()
            assert int(run_count) == 1
            assert _employee_id_for_user(conn, int(user_id)) == int(employee_a)
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        DELETE FROM public.user_linkage_execute_items
                        WHERE user_id = :user_id
                        """
                    ),
                    {"user_id": int(user_id)},
                )
                conn.execute(
                    text(
                        """
                        DELETE FROM public.identity_reconciliation_runs
                        WHERE operation = :operation
                          AND summary->>'reason' = :reason
                        """
                    ),
                    {"operation": OPERATION_MANUAL_LINK, "reason": VALID_REASON},
                )
                _cleanup(
                    conn,
                    user_ids=[int(user_id)],
                    employee_ids=[int(employee_a), int(employee_b)],
                    run_ids=[],
                )
