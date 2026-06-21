# tests/test_adr044_phase_r2_5f_repair_rerun_operations.py
"""Tests for ADR-044 R2.5f repair preview and controlled re-run execute."""
from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.db.user_linkage_journal_constants import (
    ACTION_REPAIR_PREVIEW,
    ACTION_RERUN_EXECUTE,
    OPERATION_REPAIR_PREVIEW,
    OPERATION_RERUN_EXECUTE,
    STATUS_APPLIED,
)
from app.main import app
from app.services.user_linkage_execute_service import (
    ACTION_LINK,
    ACTION_NOOP_ALREADY_LINKED,
    UserLinkageExecuteError,
    build_user_linkage_execute_preview_report,
    execute_items_available,
)
from app.services.user_linkage_operations_service import (
    DIAG_EMPLOYEE_LINKED_TO_DIFFERENT_USER,
    DIAG_LINK_OK,
    DIAG_SERVICE_ACCOUNT_EXCLUDED,
    DIAG_USER_LINKED_TO_DIFFERENT_EMPLOYEE,
    DIAG_USER_UNLINKED_EMPLOYEE_MATCH_FOUND,
    UserLinkageOperationsError,
    manual_link_user,
    repair_linkage_preview_for_user,
    rerun_user_linkage_execute,
)
from app.services.user_linkage_review_service import (
    DECISION_APPROVE,
    record_user_linkage_review_decision,
    review_decisions_available,
)
from tests.conftest import auth_headers, get_columns, insert_returning_id, table_exists

VALID_REASON = "Repair and rerun validation per ticket HR-9930"
REPAIR_URL = "/admin/personnel/identity/user-linkage/operations/repair-preview"
RERUN_URL = "/admin/personnel/identity/user-linkage/operations/rerun-execute"
RUNS_URL = "/admin/personnel/identity/user-linkage/operations/runs"


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_r2_5f() -> None:
    with engine.connect() as conn:
        if not execute_items_available(conn):
            pytest.skip("ADR-044 R2.5b schema missing — run alembic upgrade head")
        if not review_decisions_available(conn):
            pytest.skip("user_linkage_review_decisions table missing")


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
            "google_login": f"r25f_{suffix}@pytest.local",
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


def _preview_and_token(conn, *, actor_user_id: int, user_id: int) -> tuple[dict[str, Any], str]:
    report = build_user_linkage_execute_preview_report(
        conn,
        actor_user_id=int(actor_user_id),
        user_id=int(user_id),
    )
    return report, str(report["confirm_token"])


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
            text("DELETE FROM public.user_linkage_execute_items WHERE user_id = :user_id"),
            {"user_id": int(user_id)},
        )
        conn.execute(
            text("DELETE FROM public.security_audit_log WHERE target_user_id = :user_id"),
            {"user_id": int(user_id)},
        )
        conn.execute(
            text("DELETE FROM public.user_linkage_review_decisions WHERE user_id = :user_id"),
            {"user_id": int(user_id)},
        )
        conn.execute(
            text("UPDATE public.users SET employee_id = NULL WHERE user_id = :user_id"),
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
            text("UPDATE public.users SET employee_id = NULL WHERE employee_id = :employee_id"),
            {"employee_id": int(employee_id)},
        )
        conn.execute(
            text("DELETE FROM public.employees WHERE employee_id = :employee_id"),
            {"employee_id": int(employee_id)},
        )


@pytest.fixture
def admin_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_repair_preview_by_user_id_unlinked_with_candidate(seed):
    _require_r2_5f()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Repair User Target", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                full_name="Repair User Target",
                login=f"repair_user_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )

        result = repair_linkage_preview_for_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=int(user_id),
            reason=VALID_REASON,
        )
        run_ids.append(int(result["run_id"]))

        assert result["operation"] == OPERATION_REPAIR_PREVIEW
        assert result["dry_run"] is True
        assert result["diagnosis_code"] == DIAG_USER_UNLINKED_EMPLOYEE_MATCH_FOUND
        assert result["candidate_linkage"]["proposed_employee_id"] == int(employee_id)
        assert result["current_linkage"]["employee_id"] is None

        with engine.connect() as conn:
            assert _employee_id_for_user(conn, int(user_id)) is None
            item = conn.execute(
                text(
                    """
                    SELECT action, status
                    FROM public.user_linkage_execute_items
                    WHERE item_id = :item_id
                    """
                ),
                {"item_id": int(result["item_id"])},
            ).mappings().one()
            assert item["action"] == ACTION_REPAIR_PREVIEW
            assert item["status"] == STATUS_APPLIED
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
def test_repair_preview_by_employee_id(seed):
    _require_r2_5f()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Repair Employee Target", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                full_name="Repair Employee Target",
                login=f"repair_emp_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )

        result = repair_linkage_preview_for_user(
            actor_user_id=int(seed["initiator_user_id"]),
            employee_id=int(employee_id),
            reason=VALID_REASON,
        )
        run_ids.append(int(result["run_id"]))

        assert result["target"]["kind"] == "employee"
        assert result["target"]["employee_id"] == int(employee_id)
        assert result["target"]["diagnostic_user_id"] == int(user_id)
        assert result["diagnosis_code"] == DIAG_USER_UNLINKED_EMPLOYEE_MATCH_FOUND
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
def test_repair_preview_rejects_both_or_neither_targets(seed):
    _require_r2_5f()
    with pytest.raises(UserLinkageOperationsError, match="not both"):
        repair_linkage_preview_for_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=1,
            employee_id=2,
            reason=VALID_REASON,
        )
    with pytest.raises(UserLinkageOperationsError, match="required"):
        repair_linkage_preview_for_user(
            actor_user_id=int(seed["initiator_user_id"]),
            reason=VALID_REASON,
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_repair_preview_link_ok(seed):
    _require_r2_5f()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Repair Link OK", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                full_name="Repair Link OK",
                login=f"repair_ok_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )

        link_result = manual_link_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=int(user_id),
            employee_id=int(employee_id),
            reason=VALID_REASON,
        )
        run_ids.append(int(link_result["run_id"]))

        result = repair_linkage_preview_for_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=int(user_id),
            reason=VALID_REASON,
        )
        run_ids.append(int(result["run_id"]))
        assert result["diagnosis_code"] == DIAG_LINK_OK
        assert result["recommended_action"] == "NO_ACTION"
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
def test_repair_preview_linked_to_different_employee(seed):
    _require_r2_5f()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_a: Optional[int] = None
    employee_b: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_a = _create_employee(
                conn, full_name="Repair Linked A", org_unit_id=int(seed["unit_id"])
            )
            employee_b = _create_employee(
                conn, full_name="Repair Linked B", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                full_name="Repair Linked B",
                login=f"repair_diff_{employee_b}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )
            conn.execute(
                text("UPDATE public.users SET employee_id = :employee_id WHERE user_id = :user_id"),
                {"employee_id": int(employee_a), "user_id": int(user_id)},
            )

        result = repair_linkage_preview_for_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=int(user_id),
            reason=VALID_REASON,
        )
        run_ids.append(int(result["run_id"]))
        assert result["diagnosis_code"] == DIAG_USER_LINKED_TO_DIFFERENT_EMPLOYEE
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
def test_repair_preview_employee_linked_to_different_user(seed):
    _require_r2_5f()
    _require_r2_tables()
    user_a: Optional[int] = None
    user_b: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Repair Occupied Employee", org_unit_id=int(seed["unit_id"])
            )
            user_a = _create_unlinked_user(
                conn,
                full_name="Repair Occupied Employee",
                login=f"occupied_a_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )
            user_b = _create_unlinked_user(
                conn,
                full_name="Repair Occupied Employee",
                login=f"occupied_b_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )

        occupied = manual_link_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=int(user_a),
            employee_id=int(employee_id),
            reason=VALID_REASON,
        )
        run_ids.append(int(occupied["run_id"]))

        result = repair_linkage_preview_for_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=int(user_b),
            reason=VALID_REASON,
        )
        run_ids.append(int(result["run_id"]))
        assert result["diagnosis_code"] == DIAG_EMPLOYEE_LINKED_TO_DIFFERENT_USER
    finally:
        user_ids = [uid for uid in (user_a, user_b) if uid is not None]
        if user_ids:
            with engine.begin() as conn:
                _cleanup(
                    conn,
                    user_ids=[int(uid) for uid in user_ids],
                    employee_ids=[int(employee_id)] if employee_id else [],
                    run_ids=run_ids,
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_repair_preview_service_account_excluded(seed):
    _require_r2_5f()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Repair Service Employee", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                login="admin_service_account",
                full_name="Admin Service Account",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )

        result = repair_linkage_preview_for_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=int(user_id),
            reason=VALID_REASON,
        )
        run_ids.append(int(result["run_id"]))
        assert result["diagnosis_code"] == DIAG_SERVICE_ACCOUNT_EXCLUDED
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
def test_repair_preview_does_not_mutate_users(seed):
    _require_r2_5f()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Repair No Mutation", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                full_name="Repair No Mutation",
                login=f"repair_nomut_{employee_id}",
                role_id=int(seed["executor_role_id"]),
                org_unit_id=int(seed["unit_id"]),
            )
            before = conn.execute(
                text("SELECT employee_id FROM public.users WHERE user_id = :user_id"),
                {"user_id": int(user_id)},
            ).scalar_one()

        repair_linkage_preview_for_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=int(user_id),
            reason=VALID_REASON,
        )

        with engine.connect() as conn:
            after = conn.execute(
                text("SELECT employee_id FROM public.users WHERE user_id = :user_id"),
                {"user_id": int(user_id)},
            ).scalar_one()
            assert before == after
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
def test_rerun_execute_applies_with_confirm_token(seed):
    _require_r2_5f()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Rerun Execute Employee", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                full_name="Rerun Execute Employee",
                login=f"rerun_exec_{employee_id}",
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

        result = rerun_user_linkage_execute(
            actor_user_id=int(seed["initiator_user_id"]),
            source_preview_run_id=int(preview["run_id"]),
            confirm_token=token,
            reason=VALID_REASON,
        )
        run_ids.extend([int(result["rerun_run_id"]), int(result["execute_run_id"])])

        assert result["operation"] == OPERATION_RERUN_EXECUTE
        assert result["source_preview_run_id"] == int(preview["run_id"])
        assert result["execute"]["applied"] == 1
        assert result["execute"]["items"][0]["action"] == ACTION_LINK

        with engine.connect() as conn:
            assert _employee_id_for_user(conn, int(user_id)) == int(employee_id)
            rerun_run = conn.execute(
                text(
                    """
                    SELECT summary
                    FROM public.identity_reconciliation_runs
                    WHERE run_id = :run_id
                    """
                ),
                {"run_id": int(result["rerun_run_id"])},
            ).mappings().one()
            summary = rerun_run["summary"]
            if isinstance(summary, str):
                import json

                summary = json.loads(summary)
            assert summary["source_preview_run_id"] == int(preview["run_id"])
            assert summary["execute_run_id"] == int(result["execute_run_id"])
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
def test_rerun_execute_rejects_invalid_confirm_token(seed):
    _require_r2_5f()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Rerun Token Employee", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                full_name="Rerun Token Employee",
                login=f"rerun_token_{employee_id}",
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

        with pytest.raises(UserLinkageExecuteError, match="confirm_token"):
            rerun_user_linkage_execute(
                actor_user_id=int(seed["initiator_user_id"]),
                source_preview_run_id=int(preview["run_id"]),
                confirm_token="invalid-token-value",
                reason=VALID_REASON,
            )

        with engine.connect() as conn:
            assert _employee_id_for_user(conn, int(user_id)) is None
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
def test_rerun_execute_idempotent_when_already_linked(seed):
    _require_r2_5f()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="Rerun Idempotent Employee", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                full_name="Rerun Idempotent Employee",
                login=f"rerun_idem_{employee_id}",
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

        first = rerun_user_linkage_execute(
            actor_user_id=int(seed["initiator_user_id"]),
            source_preview_run_id=int(preview["run_id"]),
            confirm_token=token,
            reason=VALID_REASON,
        )
        run_ids.extend([int(first["rerun_run_id"]), int(first["execute_run_id"])])

        second = rerun_user_linkage_execute(
            actor_user_id=int(seed["initiator_user_id"]),
            source_preview_run_id=int(preview["run_id"]),
            confirm_token=token,
            reason=VALID_REASON,
        )
        run_ids.extend([int(second["rerun_run_id"]), int(second["execute_run_id"])])

        assert first["execute"]["applied"] == 1
        assert second["execute"]["applied"] == 0
        assert second["execute"]["items"][0]["action"] == ACTION_NOOP_ALREADY_LINKED

        with engine.connect() as conn:
            assert _employee_id_for_user(conn, int(user_id)) == int(employee_id)
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
def test_history_api_reads_repair_and_rerun_runs(client: TestClient, seed, admin_headers):
    _require_r2_5f()
    _require_r2_tables()
    user_id: Optional[int] = None
    employee_id: Optional[int] = None
    run_ids: list[int] = []
    try:
        with engine.begin() as conn:
            employee_id = _create_employee(
                conn, full_name="History Repair Employee", org_unit_id=int(seed["unit_id"])
            )
            user_id = _create_unlinked_user(
                conn,
                full_name="History Repair Employee",
                login=f"hist_repair_{employee_id}",
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

        repair = repair_linkage_preview_for_user(
            actor_user_id=int(seed["initiator_user_id"]),
            user_id=int(user_id),
            reason=VALID_REASON,
        )
        rerun = rerun_user_linkage_execute(
            actor_user_id=int(seed["initiator_user_id"]),
            source_preview_run_id=int(preview["run_id"]),
            confirm_token=token,
            reason=VALID_REASON,
        )
        run_ids.extend(
            [
                int(repair["run_id"]),
                int(rerun["rerun_run_id"]),
                int(rerun["execute_run_id"]),
            ]
        )

        repair_resp = client.get(
            RUNS_URL,
            headers=admin_headers,
            params={"operation": OPERATION_REPAIR_PREVIEW, "limit": 20},
        )
        assert repair_resp.status_code == 200
        repair_run_ids = {row["run_id"] for row in repair_resp.json()["items"]}
        assert int(repair["run_id"]) in repair_run_ids

        rerun_resp = client.get(
            RUNS_URL,
            headers=admin_headers,
            params={"operation": OPERATION_RERUN_EXECUTE, "limit": 20},
        )
        assert rerun_resp.status_code == 200
        rerun_run_ids = {row["run_id"] for row in rerun_resp.json()["items"]}
        assert int(rerun["rerun_run_id"]) in rerun_run_ids

        items_resp = client.get(
            "/admin/personnel/identity/user-linkage/operations/items",
            headers=admin_headers,
            params={"action": ACTION_RERUN_EXECUTE, "limit": 20},
        )
        assert items_resp.status_code == 200
        assert any(row["run_id"] == int(rerun["rerun_run_id"]) for row in items_resp.json()["items"])
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
def test_api_repair_preview_rejects_both_targets(client: TestClient, seed, admin_headers):
    _require_r2_5f()
    resp = client.post(
        REPAIR_URL,
        headers=admin_headers,
        json={"user_id": 1, "employee_id": 2, "reason": VALID_REASON},
    )
    assert resp.status_code == 400
    assert "not both" in resp.json()["detail"]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_api_rerun_execute_requires_personnel_admin(client: TestClient, seed):
    _require_r2_5f()
    headers = auth_headers(seed["executor_user_id"])
    resp = client.post(
        RERUN_URL,
        headers=headers,
        json={
            "source_preview_run_id": 1,
            "confirm_token": "0123456789abcdef",
            "reason": VALID_REASON,
        },
    )
    assert resp.status_code == 403
