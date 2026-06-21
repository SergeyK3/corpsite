# tests/test_adr044_phase_r2_4d_user_linkage_execute.py
"""Tests for ADR-044 R2.4d user linkage execute engine."""
from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.services.user_linkage_execute_service import (
    ACTION_FAIL_EMPLOYEE_CONFLICT,
    ACTION_LINK,
    ACTION_NOOP_ALREADY_LINKED,
    ACTION_SKIP_NOT_APPROVED,
    ACTION_SKIP_PREVIEW_DRIFT,
    STATUS_APPLIED,
    STATUS_FAILED,
    STATUS_SKIPPED,
    UserLinkageExecuteError,
    build_user_linkage_execute_preview_report,
    execute_items_available,
    execute_user_linkage_from_preview,
)
from app.services.user_linkage_review_service import (
    DECISION_APPROVE,
    DECISION_REJECT,
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


def _require_execute() -> None:
    with engine.connect() as conn:
        if not execute_items_available(conn):
            pytest.skip("ADR-044 R2.4 execute schema missing — run alembic upgrade head")
        if not review_decisions_available(conn):
            pytest.skip("user_linkage_review_decisions table missing")


def _require_r2_tables() -> None:
    with engine.connect() as conn:
        for table in ("users", "employees", "security_audit_log"):
            if not table_exists(conn, table):
                pytest.skip(f"Required table missing: {table}")
        if "employee_id" not in get_columns(conn, "users"):
            pytest.skip("users.employee_id column missing")


def _create_employee(
    conn, *, full_name: str, org_unit_id: int, operational_status: str = "active"
) -> int:
    unique_name = f"{full_name} {uuid4().hex[:8]}"
    values: Dict[str, Any] = {
        "full_name": unique_name,
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
            "full_name": f"{full_name} {suffix}",
            "google_login": f"r24d_{suffix}@pytest.local",
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


def _audit_count_for_user(conn, user_id: int) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(*) AS cnt
                FROM public.security_audit_log
                WHERE event_type = 'USER_EMPLOYEE_LINKED'
                  AND target_user_id = :user_id
                """
            ),
            {"user_id": int(user_id)},
        ).scalar_one()
    )


def _cleanup_execute_artifacts(
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
            text("DELETE FROM public.user_linkage_execute_items WHERE user_id = :user_id"),
            {"user_id": int(user_id)},
        )
        conn.execute(
            text("DELETE FROM public.security_audit_log WHERE target_user_id = :user_id"),
            {"user_id": int(user_id)},
        )
        conn.execute(
            text(
                """
                UPDATE public.users
                SET employee_id = NULL
                WHERE user_id = :user_id
                """
            ),
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


def _preview_and_token(
    conn,
    *,
    actor_user_id: int,
    user_id: int,
) -> tuple[dict[str, Any], str]:
    report = build_user_linkage_execute_preview_report(
        conn,
        actor_user_id=int(actor_user_id),
        user_id=int(user_id),
    )
    return report, str(report["confirm_token"])


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_execute_successful_link(seed):
    _require_execute()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn,
                full_name="Execute Success Employee",
                org_unit_id=int(seed["unit_id"]),
            )
            user_id = _create_unlinked_user(
                conn,
                full_name="Execute Success Employee",
                login=f"exec_link_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )
            record_user_linkage_review_decision(
                conn,
                actor_user_id=int(seed["initiator_user_id"]),
                user_id=int(user_id),
                decision=DECISION_APPROVE,
            )
            preview, token = _preview_and_token(
                conn,
                actor_user_id=int(seed["initiator_user_id"]),
                user_id=int(user_id),
            )
            run_ids.append(int(preview["run_id"]))

        result = execute_user_linkage_from_preview(
            actor_user_id=int(seed["initiator_user_id"]),
            preview_run_id=int(preview["run_id"]),
            confirm_token=token,
        )
        run_ids.append(int(result["run_id"]))
        assert result["applied"] == 1
        assert result["failed"] == 0
        assert result["audit_records_created"] == 1
        item = result["items"][0]
        assert item["action"] == ACTION_LINK
        assert item["status"] == STATUS_APPLIED

        with engine.connect() as conn:
            assert _employee_id_for_user(conn, int(user_id)) == int(employee_id)
            assert _audit_count_for_user(conn, int(user_id)) == 1
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                _cleanup_execute_artifacts(
                    conn,
                    user_ids=[int(user_id)],
                    employee_ids=[int(employee_id)] if employee_id else [],
                    run_ids=run_ids,
                    reviewer_user_id=int(seed["initiator_user_id"]),
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_execute_preview_drift_at_apply(seed):
    _require_execute()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_a: Optional[int] = None
    employee_b: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_a = _create_employee(
                conn, full_name="Drift Execute A", org_unit_id=int(seed["unit_id"])
            )
            employee_b = _create_employee(
                conn, full_name="Drift Execute B", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                full_name="Drift Execute B",
                login=f"drift_link_{employee_a}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )
            record_user_linkage_review_decision(
                conn,
                actor_user_id=int(seed["initiator_user_id"]),
                user_id=int(user_id),
                decision=DECISION_APPROVE,
            )
            preview, token = _preview_and_token(
                conn,
                actor_user_id=int(seed["initiator_user_id"]),
                user_id=int(user_id),
            )
            run_ids.append(int(preview["run_id"]))
            conn.execute(
                text("UPDATE public.users SET login = :login WHERE user_id = :user_id"),
                {"login": f"drift_link_{employee_b}", "user_id": int(user_id)},
            )

        result = execute_user_linkage_from_preview(
            actor_user_id=int(seed["initiator_user_id"]),
            preview_run_id=int(preview["run_id"]),
            confirm_token=token,
        )
        run_ids.append(int(result["run_id"]))
        assert result["applied"] == 0
        assert result["skipped"] == 1
        item = result["items"][0]
        assert item["action"] == ACTION_SKIP_PREVIEW_DRIFT
        assert item["status"] == STATUS_SKIPPED
        with engine.connect() as conn:
            assert _employee_id_for_user(conn, int(user_id)) is None
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                _cleanup_execute_artifacts(
                    conn,
                    user_ids=[int(user_id)],
                    employee_ids=[int(employee_a), int(employee_b)],
                    run_ids=run_ids,
                    reviewer_user_id=int(seed["initiator_user_id"]),
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_execute_employee_conflict(seed):
    _require_execute()
    _require_r2_tables()
    user_id: Optional[int] = None
    occupier_id: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Conflict Execute Employee", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                full_name="Conflict Execute Employee",
                login=f"conflict_link_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )
            record_user_linkage_review_decision(
                conn,
                actor_user_id=int(seed["initiator_user_id"]),
                user_id=int(user_id),
                decision=DECISION_APPROVE,
            )
            preview, token = _preview_and_token(
                conn,
                actor_user_id=int(seed["initiator_user_id"]),
                user_id=int(user_id),
            )
            run_ids.append(int(preview["run_id"]))

        with engine.begin() as conn:
            occupier_id = _create_unlinked_user(
                conn,
                full_name="Conflict Occupier",
                login=f"occupy_{uuid4().hex[:8]}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )
            conn.execute(
                text(
                    "UPDATE public.users SET employee_id = :employee_id WHERE user_id = :user_id"
                ),
                {"employee_id": int(employee_id), "user_id": int(occupier_id)},
            )

        result = execute_user_linkage_from_preview(
            actor_user_id=int(seed["initiator_user_id"]),
            preview_run_id=int(preview["run_id"]),
            confirm_token=token,
        )
        run_ids.append(int(result["run_id"]))
        assert result["applied"] == 0
        assert result["failed"] == 1
        assert result["items"][0]["action"] == ACTION_FAIL_EMPLOYEE_CONFLICT
        with engine.connect() as conn:
            assert _employee_id_for_user(conn, int(user_id)) is None
    finally:
        with engine.begin() as conn:
            ids = [uid for uid in (user_id, occupier_id) if uid is not None]
            _cleanup_execute_artifacts(
                conn,
                user_ids=ids,
                employee_ids=[int(employee_id)] if employee_id else [],
                run_ids=run_ids,
                reviewer_user_id=int(seed["initiator_user_id"]),
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_execute_user_already_linked_different(seed):
    _require_execute()
    _require_r2_tables()
    user_id: Optional[int] = None
    linked_employee: Optional[int] = None
    approved_employee: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            linked_employee = _create_employee(
                conn, full_name="Linked Other Employee", org_unit_id=int(seed["unit_id"])
            )
            approved_employee = _create_employee(
                conn, full_name="Approved Execute Employee", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                full_name="User Conflict Execute",
                login=f"user_conflict_{approved_employee}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )
            record_user_linkage_review_decision(
                conn,
                actor_user_id=int(seed["initiator_user_id"]),
                user_id=int(user_id),
                decision=DECISION_APPROVE,
            )
            preview, token = _preview_and_token(
                conn,
                actor_user_id=int(seed["initiator_user_id"]),
                user_id=int(user_id),
            )
            run_ids.append(int(preview["run_id"]))

        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE public.users SET employee_id = :employee_id WHERE user_id = :user_id"
                ),
                {"employee_id": int(linked_employee), "user_id": int(user_id)},
            )

        result = execute_user_linkage_from_preview(
            actor_user_id=int(seed["initiator_user_id"]),
            preview_run_id=int(preview["run_id"]),
            confirm_token=token,
        )
        run_ids.append(int(result["run_id"]))
        assert result["applied"] == 0
        assert result["failed"] == 1
        with engine.connect() as conn:
            assert _employee_id_for_user(conn, int(user_id)) == int(linked_employee)
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                _cleanup_execute_artifacts(
                    conn,
                    user_ids=[int(user_id)],
                    employee_ids=[int(linked_employee), int(approved_employee)],
                    run_ids=run_ids,
                    reviewer_user_id=int(seed["initiator_user_id"]),
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_execute_reexecute_same_preview_noop(seed):
    _require_execute()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Reexecute Employee", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                full_name="Reexecute Employee",
                login=f"reexec_link_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )
            record_user_linkage_review_decision(
                conn,
                actor_user_id=int(seed["initiator_user_id"]),
                user_id=int(user_id),
                decision=DECISION_APPROVE,
            )
            preview, token = _preview_and_token(
                conn,
                actor_user_id=int(seed["initiator_user_id"]),
                user_id=int(user_id),
            )
            run_ids.append(int(preview["run_id"]))

        first = execute_user_linkage_from_preview(
            actor_user_id=int(seed["initiator_user_id"]),
            preview_run_id=int(preview["run_id"]),
            confirm_token=token,
        )
        second = execute_user_linkage_from_preview(
            actor_user_id=int(seed["initiator_user_id"]),
            preview_run_id=int(preview["run_id"]),
            confirm_token=token,
        )
        run_ids.extend([int(first["run_id"]), int(second["run_id"])])
        assert first["applied"] == 1
        assert second["applied"] == 0
        assert second["skipped"] == 1
        assert second["items"][0]["action"] == ACTION_NOOP_ALREADY_LINKED
        with engine.connect() as conn:
            assert _audit_count_for_user(conn, int(user_id)) == 1
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                _cleanup_execute_artifacts(
                    conn,
                    user_ids=[int(user_id)],
                    employee_ids=[int(employee_id)] if employee_id else [],
                    run_ids=run_ids,
                    reviewer_user_id=int(seed["initiator_user_id"]),
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_execute_decision_changed_after_preview(seed):
    _require_execute()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Decision Changed Employee", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                full_name="Decision Changed Employee",
                login=f"dec_chg_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )
            record_user_linkage_review_decision(
                conn,
                actor_user_id=int(seed["initiator_user_id"]),
                user_id=int(user_id),
                decision=DECISION_APPROVE,
            )
            preview, token = _preview_and_token(
                conn,
                actor_user_id=int(seed["initiator_user_id"]),
                user_id=int(user_id),
            )
            run_ids.append(int(preview["run_id"]))
            record_user_linkage_review_decision(
                conn,
                actor_user_id=int(seed["initiator_user_id"]),
                user_id=int(user_id),
                decision=DECISION_REJECT,
                reason="changed after preview",
            )

        result = execute_user_linkage_from_preview(
            actor_user_id=int(seed["initiator_user_id"]),
            preview_run_id=int(preview["run_id"]),
            confirm_token=token,
        )
        run_ids.append(int(result["run_id"]))
        assert result["applied"] == 0
        assert result["skipped"] == 1
        assert result["items"][0]["action"] == ACTION_SKIP_NOT_APPROVED
        with engine.connect() as conn:
            assert _employee_id_for_user(conn, int(user_id)) is None
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                _cleanup_execute_artifacts(
                    conn,
                    user_ids=[int(user_id)],
                    employee_ids=[int(employee_id)] if employee_id else [],
                    run_ids=run_ids,
                    reviewer_user_id=int(seed["initiator_user_id"]),
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_execute_confirm_token_mismatch_rejects_without_writes(seed):
    _require_execute()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Token Mismatch Employee", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                full_name="Token Mismatch Employee",
                login=f"token_bad_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )
            record_user_linkage_review_decision(
                conn,
                actor_user_id=int(seed["initiator_user_id"]),
                user_id=int(user_id),
                decision=DECISION_APPROVE,
            )
            preview, _token = _preview_and_token(
                conn,
                actor_user_id=int(seed["initiator_user_id"]),
                user_id=int(user_id),
            )
            run_ids.append(int(preview["run_id"]))

        with pytest.raises(UserLinkageExecuteError, match="confirm_token mismatch"):
            execute_user_linkage_from_preview(
                actor_user_id=int(seed["initiator_user_id"]),
                preview_run_id=int(preview["run_id"]),
                confirm_token="sha256:deadbeef",
            )
        with engine.connect() as conn:
            assert _employee_id_for_user(conn, int(user_id)) is None
            execute_runs = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM public.identity_reconciliation_runs
                    WHERE operation = 'USER_LINKAGE_EXECUTE'
                      AND summary->>'source_preview_run_id' = :preview_run_id
                    """
                ),
                {"preview_run_id": str(int(preview["run_id"]))},
            ).scalar_one()
            assert int(execute_runs) == 0
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                _cleanup_execute_artifacts(
                    conn,
                    user_ids=[int(user_id)],
                    employee_ids=[int(employee_id)] if employee_id else [],
                    run_ids=run_ids,
                    reviewer_user_id=int(seed["initiator_user_id"]),
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_execute_blocking_gates_reject(seed):
    _require_execute()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    gate_user_id: Optional[int] = None
    gate_employee_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            gate_employee_id = _create_employee(
                conn,
                full_name="Inactive Gate Employee",
                org_unit_id=int(seed["unit_id"]),
                operational_status="terminated",
            )
            gate_user_id = _create_unlinked_user(
                conn,
                full_name="Inactive Gate User",
                login=f"gate_user_{uuid4().hex[:8]}",
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
                {"employee_id": int(gate_employee_id), "user_id": int(gate_user_id)},
            )
            employee_id = _create_employee(
                conn, full_name="Gate Block Employee", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                full_name="Gate Block Employee",
                login=f"gate_block_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )
            record_user_linkage_review_decision(
                conn,
                actor_user_id=int(seed["initiator_user_id"]),
                user_id=int(user_id),
                decision=DECISION_APPROVE,
            )
            preview, token = _preview_and_token(
                conn,
                actor_user_id=int(seed["initiator_user_id"]),
                user_id=int(user_id),
            )
            run_ids.append(int(preview["run_id"]))

        with pytest.raises(UserLinkageExecuteError, match="blocking gates present"):
            execute_user_linkage_from_preview(
                actor_user_id=int(seed["initiator_user_id"]),
                preview_run_id=int(preview["run_id"]),
                confirm_token=token,
            )
        with engine.connect() as conn:
            assert _employee_id_for_user(conn, int(user_id)) is None
    finally:
        with engine.begin() as conn:
            _cleanup_execute_artifacts(
                conn,
                user_ids=[uid for uid in (user_id, gate_user_id) if uid is not None],
                employee_ids=[
                    eid for eid in (employee_id, gate_employee_id) if eid is not None
                ],
                run_ids=run_ids,
                reviewer_user_id=int(seed["initiator_user_id"]),
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_execute_partial_batch_one_applies_one_fails(seed):
    _require_execute()
    _require_r2_tables()
    user_a: Optional[int] = None
    user_b: Optional[int] = None
    employee_a: Optional[int] = None
    employee_b: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_a = _create_employee(
                conn, full_name="Partial A Employee", org_unit_id=int(seed["unit_id"])
            )
            employee_b = _create_employee(
                conn, full_name="Partial B Employee", org_unit_id=int(seed["unit_id"])
            )
            user_a = _create_unlinked_user(
                conn,
                full_name="Partial A Employee",
                login=f"partial_link_a_{employee_a}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )
            user_b = _create_unlinked_user(
                conn,
                full_name="Partial B Employee",
                login=f"partial_link_b_{employee_b}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )
            for uid in (user_a, user_b):
                record_user_linkage_review_decision(
                    conn,
                    actor_user_id=int(seed["initiator_user_id"]),
                    user_id=int(uid),
                    decision=DECISION_APPROVE,
                )
            preview = build_user_linkage_execute_preview_report(
                conn,
                actor_user_id=int(seed["initiator_user_id"]),
                user_ids=[int(user_a), int(user_b)],
            )
            token = str(preview["confirm_token"])
            run_ids.append(int(preview["run_id"]))

        with engine.begin() as conn:
            insert_returning_id(
                conn,
                table="users",
                id_col="user_id",
                values={
                    "full_name": "Occupier B",
                    "google_login": f"occ_b_{uuid4().hex[:8]}@pytest.local",
                    "login": f"occ_b_{uuid4().hex[:8]}",
                    "role_id": int(seed["executor_role_id"]),
                    "unit_id": int(seed["unit_id"]),
                    "employee_id": int(employee_b),
                    "is_active": True,
                },
            )

        result = execute_user_linkage_from_preview(
            actor_user_id=int(seed["initiator_user_id"]),
            preview_run_id=int(preview["run_id"]),
            confirm_token=token,
        )
        run_ids.append(int(result["run_id"]))
        assert result["applied"] == 1
        assert result["failed"] == 1
        with engine.connect() as conn:
            assert _employee_id_for_user(conn, int(user_a)) == int(employee_a)
            assert _employee_id_for_user(conn, int(user_b)) is None
    finally:
        with engine.begin() as conn:
            if employee_b is not None:
                conn.execute(
                    text(
                        """
                        DELETE FROM public.users
                        WHERE employee_id = :employee_id
                          AND user_id NOT IN (:user_a, :user_b)
                        """
                    ),
                    {
                        "employee_id": int(employee_b),
                        "user_a": int(user_a or 0),
                        "user_b": int(user_b or 0),
                    },
                )
            _cleanup_execute_artifacts(
                conn,
                user_ids=[int(user_a), int(user_b)],
                employee_ids=[int(employee_a), int(employee_b)],
                run_ids=run_ids,
                reviewer_user_id=int(seed["initiator_user_id"]),
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_api_execute_requires_personnel_admin(client: TestClient, seed):
    _require_execute()
    _require_r2_tables()
    headers = auth_headers(seed["executor_user_id"])
    resp = client.post(
        "/admin/personnel/identity/user-linkage/execute",
        headers=headers,
        json={"run_id": 1, "confirm_token": "sha256:abc"},
    )
    assert resp.status_code == 403


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_api_execute_success(seed, monkeypatch):
    _require_execute()
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
                conn, full_name="API Execute Employee", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                full_name="API Execute Employee",
                login=f"exec_api_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )
            record_user_linkage_review_decision(
                conn,
                actor_user_id=int(seed["initiator_user_id"]),
                user_id=int(user_id),
                decision=DECISION_APPROVE,
            )

        preview_resp = client.post(
            "/admin/personnel/identity/user-linkage/execute-preview",
            headers=headers,
            json={"user_id": int(user_id)},
        )
        assert preview_resp.status_code == 200, preview_resp.text
        preview_body = preview_resp.json()
        run_ids.append(int(preview_body["run_id"]))

        execute_resp = client.post(
            "/admin/personnel/identity/user-linkage/execute",
            headers=headers,
            json={
                "run_id": int(preview_body["run_id"]),
                "confirm_token": preview_body["confirm_token"],
            },
        )
        assert execute_resp.status_code == 200, execute_resp.text
        execute_body = execute_resp.json()
        run_ids.append(int(execute_body["run_id"]))
        assert execute_body["applied"] == 1
        assert execute_body["audit_records_created"] == 1

        with engine.connect() as conn:
            assert _employee_id_for_user(conn, int(user_id)) == int(employee_id)
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                _cleanup_execute_artifacts(
                    conn,
                    user_ids=[int(user_id)],
                    employee_ids=[int(employee_id)] if employee_id else [],
                    run_ids=run_ids,
                    reviewer_user_id=int(seed["initiator_user_id"]),
                )
