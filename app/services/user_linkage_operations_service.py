"""ADR-044 R2.5c/R2.5d — manual and rollback user ↔ employee linkage operations."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.user_linkage_journal_constants import (
    ACTION_MANUAL_LINK,
    ACTION_MANUAL_UNLINK,
    ACTION_REPAIR_PREVIEW,
    ACTION_RERUN_EXECUTE,
    ACTION_ROLLBACK_LINK,
    EVENT_USER_EMPLOYEE_LINKED,
    EVENT_USER_EMPLOYEE_LINK_ROLLED_BACK,
    EVENT_USER_EMPLOYEE_UNLINKED,
    OPERATION_MANUAL_LINK,
    OPERATION_MANUAL_UNLINK,
    OPERATION_REPAIR_PREVIEW,
    OPERATION_RERUN_EXECUTE,
    OPERATION_ROLLBACK_ITEM,
    REASON_LINK_TARGET_CONFLICT,
    REASON_MANUAL_OPERATOR_DECISION,
    REASON_ROLLBACK_ALREADY_APPLIED,
    REASON_ROLLBACK_PAYLOAD_APPLIED,
    REASON_ROLLBACK_TARGET_CHANGED,
    REASON_UNLINK_TARGET_EMPTY,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    RUN_STATUS_RUNNING,
    STATUS_APPLIED,
    STATUS_FAILED,
    STATUS_NOOP_ALREADY_LINKED,
    STATUS_NOOP_ALREADY_ROLLED_BACK,
    STATUS_NOOP_ALREADY_UNLINKED,
    STATUS_SKIPPED,
)
from app.services.user_linkage_execute_service import (
    ACTION_LINK,
    ACTION_NOOP_ALREADY_LINKED,
    execute_items_available,
    execute_user_linkage_from_preview,
    _decision_snapshot,
    _evaluate_candidate,
    _load_latest_decisions,
)
from app.services.user_linkage_preview_service import (
    CLASSIFICATION_AMBIGUOUS,
    CLASSIFICATION_EXCLUDED,
    CLASSIFICATION_IMPOSSIBLE,
    CLASSIFICATION_REVIEW_REQUIRED,
    OPERATIONAL_EMPLOYEE_STATUSES,
    PHASE_R2,
    _UserRow,
    _build_context,
    _classify_user,
    _load_employees_for_lookup,
    is_service_account,
    normalize_fio,
    run_user_linkage_preview,
)

MIN_OPERATOR_REASON_LENGTH = 10

DIAG_LINK_OK = "LINK_OK"
DIAG_USER_UNLINKED_EMPLOYEE_MATCH_FOUND = "USER_UNLINKED_EMPLOYEE_MATCH_FOUND"
DIAG_USER_LINKED_TO_DIFFERENT_EMPLOYEE = "USER_LINKED_TO_DIFFERENT_EMPLOYEE"
DIAG_EMPLOYEE_LINKED_TO_DIFFERENT_USER = "EMPLOYEE_LINKED_TO_DIFFERENT_USER"
DIAG_NO_CANDIDATE_FOUND = "NO_CANDIDATE_FOUND"
DIAG_USER_NOT_FOUND = "USER_NOT_FOUND"
DIAG_EMPLOYEE_NOT_FOUND = "EMPLOYEE_NOT_FOUND"
DIAG_SERVICE_ACCOUNT_EXCLUDED = "SERVICE_ACCOUNT_EXCLUDED"
DIAG_INACTIVE_EMPLOYEE_TARGET = "INACTIVE_EMPLOYEE_TARGET"
DIAG_REVIEW_REQUIRED = "REVIEW_REQUIRED"
DIAG_CONFLICT_REQUIRES_MANUAL_DECISION = "CONFLICT_REQUIRES_MANUAL_DECISION"

ROLLBACKABLE_SOURCE_ACTIONS = frozenset(
    {ACTION_LINK, ACTION_MANUAL_LINK, ACTION_MANUAL_UNLINK}
)
LINK_SOURCE_ACTIONS = frozenset({ACTION_LINK, ACTION_MANUAL_LINK})


class UserLinkageOperationsError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def _validate_actor_user_id(actor_user_id: Optional[int]) -> int:
    if actor_user_id is None:
        raise UserLinkageOperationsError("actor_user_id is required")
    try:
        value = int(actor_user_id)
    except (TypeError, ValueError) as exc:
        raise UserLinkageOperationsError("actor_user_id is required") from exc
    if value < 1:
        raise UserLinkageOperationsError("actor_user_id is required")
    return value


def _validate_reason(reason: Optional[str]) -> str:
    normalized = str(reason or "").strip()
    if len(normalized) < MIN_OPERATOR_REASON_LENGTH:
        raise UserLinkageOperationsError("reason is required")
    return normalized


def _require_operations_schema(conn: Connection) -> None:
    if not execute_items_available(conn):
        raise UserLinkageOperationsError(
            "user_linkage_execute_items schema missing — run alembic upgrade head"
        )


def _load_user_row_for_update(conn: Connection, user_id: int) -> Optional[dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT user_id, login, google_login, full_name, employee_id, is_active, role_id
            FROM public.users
            WHERE user_id = :user_id
            FOR UPDATE
            """
        ),
        {"user_id": int(user_id)},
    ).mappings().first()
    return dict(row) if row else None


def _load_user_row(conn: Connection, user_id: int) -> Optional[dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT user_id, login, google_login, full_name, employee_id, is_active, role_id
            FROM public.users
            WHERE user_id = :user_id
            """
        ),
        {"user_id": int(user_id)},
    ).mappings().first()
    return dict(row) if row else None


def _load_employee_row(conn: Connection, employee_id: int) -> Optional[dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT employee_id, full_name, operational_status
            FROM public.employees
            WHERE employee_id = :employee_id
            """
        ),
        {"employee_id": int(employee_id)},
    ).mappings().first()
    return dict(row) if row else None


def _employee_linked_to_other_user(
    conn: Connection,
    *,
    employee_id: int,
    exclude_user_id: int,
) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM public.users
            WHERE employee_id = :employee_id
              AND user_id <> :exclude_user_id
              AND COALESCE(is_active, TRUE) = TRUE
            LIMIT 1
            """
        ),
        {
            "employee_id": int(employee_id),
            "exclude_user_id": int(exclude_user_id),
        },
    ).first()
    return row is not None


def _user_snapshot(user_row: dict[str, Any]) -> dict[str, Any]:
    employee_id = user_row.get("employee_id")
    return {
        "user_id": int(user_row["user_id"]),
        "login": user_row.get("login"),
        "full_name": user_row.get("full_name"),
        "employee_id": int(employee_id) if employee_id is not None else None,
        "is_active": user_row.get("is_active"),
        "role_id": user_row.get("role_id"),
    }


def _rollback_payload_for_link(
    *,
    user_id: int,
    previous_employee_id: Optional[int],
    employee_id: int,
) -> dict[str, Any]:
    return {
        "user_id": int(user_id),
        "previous_employee_id": int(previous_employee_id)
        if previous_employee_id is not None
        else None,
        "employee_id": int(employee_id),
        "decision_id": None,
    }


def _rollback_payload_for_unlink(
    *,
    user_id: int,
    previous_employee_id: int,
) -> dict[str, Any]:
    return {
        "user_id": int(user_id),
        "previous_employee_id": int(previous_employee_id),
        "employee_id": None,
        "decision_id": None,
    }


def _create_operations_run(
    conn: Connection,
    *,
    actor_user_id: int,
    operation: str,
    reason: str,
    trigger: str = "MANUAL",
    source_item_id: Optional[int] = None,
    dry_run: bool = False,
    extra_summary: Optional[dict[str, Any]] = None,
) -> int:
    summary: dict[str, Any] = {"reason": reason, "trigger": trigger}
    if source_item_id is not None:
        summary["source_item_id"] = int(source_item_id)
    if extra_summary:
        summary.update(extra_summary)
    row = conn.execute(
        text(
            """
            INSERT INTO public.identity_reconciliation_runs (
                phase, operation, dry_run, actor_user_id, status, summary
            )
            VALUES (
                :phase, :operation, :dry_run, :actor_user_id, :status,
                CAST(:summary AS jsonb)
            )
            RETURNING run_id
            """
        ),
        {
            "phase": PHASE_R2,
            "operation": operation,
            "dry_run": bool(dry_run),
            "actor_user_id": int(actor_user_id),
            "status": RUN_STATUS_RUNNING,
            "summary": json.dumps(summary),
        },
    ).mappings().one()
    return int(row["run_id"])


def _finalize_operations_run(
    conn: Connection,
    *,
    run_id: int,
    status: str,
    summary: dict[str, Any],
) -> None:
    conn.execute(
        text(
            """
            UPDATE public.identity_reconciliation_runs
            SET status = :status,
                finished_at = now(),
                summary = CAST(:summary AS jsonb)
            WHERE run_id = :run_id
            """
        ),
        {
            "run_id": int(run_id),
            "status": status,
            "summary": json.dumps(summary),
        },
    )


def _insert_operations_item(
    conn: Connection,
    *,
    run_id: int,
    user_id: int,
    proposed_employee_id: Optional[int],
    action: str,
    status: str,
    reason_codes: list[str],
    before_user_snapshot: dict[str, Any],
    after_user_snapshot: Optional[dict[str, Any]] = None,
    rollback_payload: Optional[dict[str, Any]] = None,
    preview_snapshot: Optional[dict[str, Any]] = None,
    decision_snapshot: Optional[dict[str, Any]] = None,
    source_decision_id: Optional[int] = None,
) -> int:
    row = conn.execute(
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
                :action,
                :status,
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
            "proposed_employee_id": proposed_employee_id,
            "source_decision_id": source_decision_id,
            "action": action,
            "status": status,
            "reason_codes": json.dumps(reason_codes),
            "preview_snapshot": json.dumps(preview_snapshot or {}),
            "decision_snapshot": json.dumps(decision_snapshot or {}),
            "before_user_snapshot": json.dumps(before_user_snapshot),
            "after_user_snapshot": json.dumps(after_user_snapshot or {}),
            "rollback_payload": json.dumps(rollback_payload or {}),
        },
    ).mappings().one()
    return int(row["item_id"])


def _operations_result(
    *,
    run_id: int,
    run_status: str,
    operation: str,
    item_id: int,
    user_id: int,
    employee_id: Optional[int],
    action: str,
    status: str,
    applied: bool,
    audit_created: bool,
    before_user_snapshot: dict[str, Any],
    after_user_snapshot: dict[str, Any],
    rollback_payload: dict[str, Any],
    audit_id: Optional[int] = None,
    source_item_id: Optional[int] = None,
    source_action: Optional[str] = None,
    restored_employee_id: Optional[int] = None,
) -> dict[str, Any]:
    return {
        "phase": PHASE_R2,
        "operation": operation,
        "run_id": int(run_id),
        "run_status": run_status,
        "item_id": int(item_id),
        "user_id": int(user_id),
        "employee_id": int(employee_id) if employee_id is not None else None,
        "action": action,
        "status": status,
        "applied": applied,
        "audit_created": audit_created,
        "audit_id": audit_id,
        "source_item_id": int(source_item_id) if source_item_id is not None else None,
        "source_action": source_action,
        "restored_employee_id": (
            int(restored_employee_id) if restored_employee_id is not None else None
        ),
        "before_user_snapshot": before_user_snapshot,
        "after_user_snapshot": after_user_snapshot,
        "rollback_payload": rollback_payload,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def manual_link_user_employee(
    conn: Connection,
    *,
    actor_user_id: int,
    user_id: int,
    employee_id: int,
    reason: str,
) -> dict[str, Any]:
    """Link one user to one employee inside an existing transaction."""
    from app.services.security_audit_service import write_security_event

    _require_operations_schema(conn)
    actor_id = _validate_actor_user_id(actor_user_id)
    operator_reason = _validate_reason(reason)
    target_user_id = int(user_id)
    target_employee_id = int(employee_id)

    user_row = _load_user_row_for_update(conn, target_user_id)
    if user_row is None:
        raise UserLinkageOperationsError(f"user_id={target_user_id} not found")

    employee_row = _load_employee_row(conn, target_employee_id)
    if employee_row is None:
        raise UserLinkageOperationsError(f"employee_id={target_employee_id} not found")

    if is_service_account(user_row):
        raise UserLinkageOperationsError(
            f"manual link blocked for service account user_id={target_user_id}"
        )

    if str(employee_row.get("operational_status") or "") not in OPERATIONAL_EMPLOYEE_STATUSES:
        raise UserLinkageOperationsError(
            f"employee_id={target_employee_id} is not operational"
        )

    before_snapshot = _user_snapshot(user_row)
    current_employee_id = user_row.get("employee_id")
    reason_codes = [REASON_MANUAL_OPERATOR_DECISION]

    run_id = _create_operations_run(
        conn,
        actor_user_id=actor_id,
        operation=OPERATION_MANUAL_LINK,
        reason=operator_reason,
    )

    if current_employee_id is not None:
        if int(current_employee_id) == target_employee_id:
            rollback_payload = _rollback_payload_for_link(
                user_id=target_user_id,
                previous_employee_id=None,
                employee_id=target_employee_id,
            )
            item_id = _insert_operations_item(
                conn,
                run_id=run_id,
                user_id=target_user_id,
                proposed_employee_id=target_employee_id,
                action=ACTION_MANUAL_LINK,
                status=STATUS_NOOP_ALREADY_LINKED,
                reason_codes=reason_codes,
                before_user_snapshot=before_snapshot,
                after_user_snapshot=before_snapshot,
                rollback_payload=rollback_payload,
            )
            run_summary = {
                "reason": operator_reason,
                "trigger": "MANUAL",
                "applied": 0,
                "noop": 1,
                "failed": 0,
            }
            _finalize_operations_run(
                conn,
                run_id=run_id,
                status=RUN_STATUS_COMPLETED,
                summary=run_summary,
            )
            return _operations_result(
                run_id=run_id,
                run_status=RUN_STATUS_COMPLETED,
                operation=OPERATION_MANUAL_LINK,
                item_id=item_id,
                user_id=target_user_id,
                employee_id=target_employee_id,
                action=ACTION_MANUAL_LINK,
                status=STATUS_NOOP_ALREADY_LINKED,
                applied=False,
                audit_created=False,
                before_user_snapshot=before_snapshot,
                after_user_snapshot=before_snapshot,
                rollback_payload=rollback_payload,
            )

        item_id = _insert_operations_item(
            conn,
            run_id=run_id,
            user_id=target_user_id,
            proposed_employee_id=target_employee_id,
            action=ACTION_MANUAL_LINK,
            status=STATUS_FAILED,
            reason_codes=[REASON_LINK_TARGET_CONFLICT],
            before_user_snapshot=before_snapshot,
            after_user_snapshot=before_snapshot,
        )
        run_summary = {
            "reason": operator_reason,
            "trigger": "MANUAL",
            "applied": 0,
            "noop": 0,
            "failed": 1,
        }
        _finalize_operations_run(
            conn,
            run_id=run_id,
            status=RUN_STATUS_FAILED,
            summary=run_summary,
        )
        return _operations_result(
            run_id=run_id,
            run_status=RUN_STATUS_FAILED,
            operation=OPERATION_MANUAL_LINK,
            item_id=item_id,
            user_id=target_user_id,
            employee_id=target_employee_id,
            action=ACTION_MANUAL_LINK,
            status=STATUS_FAILED,
            applied=False,
            audit_created=False,
            before_user_snapshot=before_snapshot,
            after_user_snapshot=before_snapshot,
            rollback_payload={},
        )

    if _employee_linked_to_other_user(
        conn,
        employee_id=target_employee_id,
        exclude_user_id=target_user_id,
    ):
        item_id = _insert_operations_item(
            conn,
            run_id=run_id,
            user_id=target_user_id,
            proposed_employee_id=target_employee_id,
            action=ACTION_MANUAL_LINK,
            status=STATUS_FAILED,
            reason_codes=[REASON_LINK_TARGET_CONFLICT],
            before_user_snapshot=before_snapshot,
            after_user_snapshot=before_snapshot,
        )
        run_summary = {
            "reason": operator_reason,
            "trigger": "MANUAL",
            "applied": 0,
            "noop": 0,
            "failed": 1,
        }
        _finalize_operations_run(
            conn,
            run_id=run_id,
            status=RUN_STATUS_FAILED,
            summary=run_summary,
        )
        return _operations_result(
            run_id=run_id,
            run_status=RUN_STATUS_FAILED,
            operation=OPERATION_MANUAL_LINK,
            item_id=item_id,
            user_id=target_user_id,
            employee_id=target_employee_id,
            action=ACTION_MANUAL_LINK,
            status=STATUS_FAILED,
            applied=False,
            audit_created=False,
            before_user_snapshot=before_snapshot,
            after_user_snapshot=before_snapshot,
            rollback_payload={},
        )

    conn.execute(
        text(
            """
            UPDATE public.users
            SET employee_id = :employee_id
            WHERE user_id = :user_id
              AND employee_id IS NULL
            """
        ),
        {
            "employee_id": target_employee_id,
            "user_id": target_user_id,
        },
    )
    after_row = _load_user_row(conn, target_user_id) or user_row
    after_snapshot = _user_snapshot(after_row)
    rollback_payload = _rollback_payload_for_link(
        user_id=target_user_id,
        previous_employee_id=None,
        employee_id=target_employee_id,
    )
    item_id = _insert_operations_item(
        conn,
        run_id=run_id,
        user_id=target_user_id,
        proposed_employee_id=target_employee_id,
        action=ACTION_MANUAL_LINK,
        status=STATUS_APPLIED,
        reason_codes=reason_codes,
        before_user_snapshot=before_snapshot,
        after_user_snapshot=after_snapshot,
        rollback_payload=rollback_payload,
    )
    audit_id = write_security_event(
        event_type=EVENT_USER_EMPLOYEE_LINKED,
        actor_user_id=actor_id,
        target_user_id=target_user_id,
        target_employee_id=target_employee_id,
        metadata={
            "user_id": target_user_id,
            "employee_id": target_employee_id,
            "previous_employee_id": None,
            "decision_id": None,
            "run_id": int(run_id),
            "operation": OPERATION_MANUAL_LINK,
            "reason": operator_reason,
            "manual": True,
        },
        conn=conn,
    )
    run_summary = {
        "reason": operator_reason,
        "trigger": "MANUAL",
        "applied": 1,
        "noop": 0,
        "failed": 0,
        "audit_records_created": 1 if audit_id is not None else 0,
    }
    _finalize_operations_run(
        conn,
        run_id=run_id,
        status=RUN_STATUS_COMPLETED,
        summary=run_summary,
    )
    return _operations_result(
        run_id=run_id,
        run_status=RUN_STATUS_COMPLETED,
        operation=OPERATION_MANUAL_LINK,
        item_id=item_id,
        user_id=target_user_id,
        employee_id=target_employee_id,
        action=ACTION_MANUAL_LINK,
        status=STATUS_APPLIED,
        applied=True,
        audit_created=audit_id is not None,
        audit_id=audit_id,
        before_user_snapshot=before_snapshot,
        after_user_snapshot=after_snapshot,
        rollback_payload=rollback_payload,
    )


def manual_unlink_user_employee(
    conn: Connection,
    *,
    actor_user_id: int,
    user_id: int,
    reason: str,
) -> dict[str, Any]:
    """Unlink one user from employee inside an existing transaction."""
    from app.services.security_audit_service import write_security_event

    _require_operations_schema(conn)
    actor_id = _validate_actor_user_id(actor_user_id)
    operator_reason = _validate_reason(reason)
    target_user_id = int(user_id)

    user_row = _load_user_row_for_update(conn, target_user_id)
    if user_row is None:
        raise UserLinkageOperationsError(f"user_id={target_user_id} not found")

    before_snapshot = _user_snapshot(user_row)
    current_employee_id = user_row.get("employee_id")

    run_id = _create_operations_run(
        conn,
        actor_user_id=actor_id,
        operation=OPERATION_MANUAL_UNLINK,
        reason=operator_reason,
    )

    if current_employee_id is None:
        item_id = _insert_operations_item(
            conn,
            run_id=run_id,
            user_id=target_user_id,
            proposed_employee_id=None,
            action=ACTION_MANUAL_UNLINK,
            status=STATUS_NOOP_ALREADY_UNLINKED,
            reason_codes=[REASON_UNLINK_TARGET_EMPTY, REASON_MANUAL_OPERATOR_DECISION],
            before_user_snapshot=before_snapshot,
            after_user_snapshot=before_snapshot,
            rollback_payload={},
        )
        run_summary = {
            "reason": operator_reason,
            "trigger": "MANUAL",
            "applied": 0,
            "noop": 1,
            "failed": 0,
        }
        _finalize_operations_run(
            conn,
            run_id=run_id,
            status=RUN_STATUS_COMPLETED,
            summary=run_summary,
        )
        return _operations_result(
            run_id=run_id,
            run_status=RUN_STATUS_COMPLETED,
            operation=OPERATION_MANUAL_UNLINK,
            item_id=item_id,
            user_id=target_user_id,
            employee_id=None,
            action=ACTION_MANUAL_UNLINK,
            status=STATUS_NOOP_ALREADY_UNLINKED,
            applied=False,
            audit_created=False,
            before_user_snapshot=before_snapshot,
            after_user_snapshot=before_snapshot,
            rollback_payload={},
        )

    previous_employee_id = int(current_employee_id)
    conn.execute(
        text(
            """
            UPDATE public.users
            SET employee_id = NULL
            WHERE user_id = :user_id
              AND employee_id = :employee_id
            """
        ),
        {
            "user_id": target_user_id,
            "employee_id": previous_employee_id,
        },
    )
    after_row = _load_user_row(conn, target_user_id) or user_row
    after_snapshot = _user_snapshot(after_row)
    rollback_payload = _rollback_payload_for_unlink(
        user_id=target_user_id,
        previous_employee_id=previous_employee_id,
    )
    item_id = _insert_operations_item(
        conn,
        run_id=run_id,
        user_id=target_user_id,
        proposed_employee_id=previous_employee_id,
        action=ACTION_MANUAL_UNLINK,
        status=STATUS_APPLIED,
        reason_codes=[REASON_MANUAL_OPERATOR_DECISION],
        before_user_snapshot=before_snapshot,
        after_user_snapshot=after_snapshot,
        rollback_payload=rollback_payload,
    )
    audit_id = write_security_event(
        event_type=EVENT_USER_EMPLOYEE_UNLINKED,
        actor_user_id=actor_id,
        target_user_id=target_user_id,
        target_employee_id=previous_employee_id,
        metadata={
            "user_id": target_user_id,
            "previous_employee_id": previous_employee_id,
            "employee_id": None,
            "run_id": int(run_id),
            "operation": OPERATION_MANUAL_UNLINK,
            "reason": operator_reason,
            "manual": True,
        },
        conn=conn,
    )
    run_summary = {
        "reason": operator_reason,
        "trigger": "MANUAL",
        "applied": 1,
        "noop": 0,
        "failed": 0,
        "audit_records_created": 1 if audit_id is not None else 0,
    }
    _finalize_operations_run(
        conn,
        run_id=run_id,
        status=RUN_STATUS_COMPLETED,
        summary=run_summary,
    )
    return _operations_result(
        run_id=run_id,
        run_status=RUN_STATUS_COMPLETED,
        operation=OPERATION_MANUAL_UNLINK,
        item_id=item_id,
        user_id=target_user_id,
        employee_id=None,
        action=ACTION_MANUAL_UNLINK,
        status=STATUS_APPLIED,
        applied=True,
        audit_created=audit_id is not None,
        audit_id=audit_id,
        before_user_snapshot=before_snapshot,
        after_user_snapshot=after_snapshot,
        rollback_payload=rollback_payload,
    )


def _normalize_json_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, str):
        return json.loads(value)
    if isinstance(value, dict):
        return dict(value)
    return {}


def _load_rollback_source_item(
    conn: Connection,
    source_item_id: int,
) -> dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT
                i.item_id,
                i.run_id,
                i.user_id,
                i.action,
                i.status,
                i.rollback_payload,
                i.proposed_employee_id,
                r.operation AS source_operation
            FROM public.user_linkage_execute_items i
            JOIN public.identity_reconciliation_runs r
              ON r.run_id = i.run_id
            WHERE i.item_id = :item_id
            """
        ),
        {"item_id": int(source_item_id)},
    ).mappings().first()
    if row is None:
        raise UserLinkageOperationsError(f"source item_id={source_item_id} not found")
    return dict(row)


def _rollback_payload_from_source(source_item: dict[str, Any]) -> dict[str, Any]:
    payload = _normalize_json_dict(source_item.get("rollback_payload"))
    if not payload:
        raise UserLinkageOperationsError(
            f"source item_id={source_item['item_id']} has no rollback_payload"
        )
    user_id = payload.get("user_id")
    if user_id is None or int(user_id) != int(source_item["user_id"]):
        raise UserLinkageOperationsError("rollback_payload user_id mismatch")
    return payload


def _rollback_already_applied(conn: Connection, source_item_id: int) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM public.identity_reconciliation_runs r
            JOIN public.user_linkage_execute_items i ON i.run_id = r.run_id
            WHERE r.phase = :phase
              AND r.operation = :operation
              AND r.summary->>'source_item_id' = :source_item_id
              AND i.action = :action
              AND i.status = :status
            LIMIT 1
            """
        ),
        {
            "phase": PHASE_R2,
            "operation": OPERATION_ROLLBACK_ITEM,
            "source_item_id": str(int(source_item_id)),
            "action": ACTION_ROLLBACK_LINK,
            "status": STATUS_APPLIED,
        },
    ).first()
    return row is not None


def _expected_current_employee_id(
    source_action: str,
    payload: dict[str, Any],
) -> Optional[int]:
    if source_action in LINK_SOURCE_ACTIONS:
        employee_id = payload.get("employee_id")
        if employee_id is None:
            raise UserLinkageOperationsError("rollback_payload employee_id missing")
        return int(employee_id)
    if source_action == ACTION_MANUAL_UNLINK:
        return None
    raise UserLinkageOperationsError(f"unsupported rollback source action: {source_action}")


def _restore_target_employee_id(payload: dict[str, Any]) -> Optional[int]:
    previous = payload.get("previous_employee_id")
    return int(previous) if previous is not None else None


def _inverse_rollback_payload(
    *,
    user_id: int,
    before_employee_id: Optional[int],
    after_employee_id: Optional[int],
    source_item_id: int,
) -> dict[str, Any]:
    return {
        "user_id": int(user_id),
        "previous_employee_id": int(before_employee_id)
        if before_employee_id is not None
        else None,
        "employee_id": int(after_employee_id) if after_employee_id is not None else None,
        "decision_id": None,
        "source_item_id": int(source_item_id),
    }


def _finalize_rollback_result(
    conn: Connection,
    *,
    run_id: int,
    operator_reason: str,
    source_item_id: int,
    source_action: str,
    target_user_id: int,
    item_id: int,
    action: str,
    status: str,
    applied: bool,
    audit_created: bool,
    audit_id: Optional[int],
    before_snapshot: dict[str, Any],
    after_snapshot: dict[str, Any],
    rollback_payload: dict[str, Any],
    reason_codes: list[str],
    run_status: str,
    applied_count: int,
    noop_count: int,
    failed_count: int,
    restored_employee_id: Optional[int],
) -> dict[str, Any]:
    run_summary = {
        "reason": operator_reason,
        "trigger": "ROLLBACK",
        "source_item_id": int(source_item_id),
        "source_action": source_action,
        "applied": applied_count,
        "noop": noop_count,
        "failed": failed_count,
        "audit_records_created": 1 if audit_created else 0,
    }
    _finalize_operations_run(
        conn,
        run_id=run_id,
        status=run_status,
        summary=run_summary,
    )
    return _operations_result(
        run_id=run_id,
        run_status=run_status,
        operation=OPERATION_ROLLBACK_ITEM,
        item_id=item_id,
        user_id=target_user_id,
        employee_id=after_snapshot.get("employee_id"),
        action=action,
        status=status,
        applied=applied,
        audit_created=audit_created,
        audit_id=audit_id,
        source_item_id=source_item_id,
        source_action=source_action,
        restored_employee_id=restored_employee_id,
        before_user_snapshot=before_snapshot,
        after_user_snapshot=after_snapshot,
        rollback_payload=rollback_payload,
    )


def rollback_linkage_item(
    conn: Connection,
    *,
    actor_user_id: int,
    source_item_id: int,
    reason: str,
) -> dict[str, Any]:
    """Reverse one applied linkage item using immutable rollback_payload."""
    from app.services.security_audit_service import write_security_event

    _require_operations_schema(conn)
    actor_id = _validate_actor_user_id(actor_user_id)
    operator_reason = _validate_reason(reason)
    source_id = int(source_item_id)

    source_item = _load_rollback_source_item(conn, source_id)
    source_action = str(source_item.get("action") or "")
    source_status = str(source_item.get("status") or "")

    if source_action not in ROLLBACKABLE_SOURCE_ACTIONS:
        raise UserLinkageOperationsError(
            f"source item_id={source_id} action={source_action} is not rollbackable"
        )
    if source_status != STATUS_APPLIED:
        raise UserLinkageOperationsError(
            f"source item_id={source_id} status must be APPLIED, got {source_status}"
        )

    payload = _rollback_payload_from_source(source_item)
    target_user_id = int(source_item["user_id"])
    expected_current = _expected_current_employee_id(source_action, payload)
    restore_target = _restore_target_employee_id(payload)

    user_row = _load_user_row_for_update(conn, target_user_id)
    if user_row is None:
        raise UserLinkageOperationsError(f"user_id={target_user_id} not found")

    before_snapshot = _user_snapshot(user_row)
    live_employee_id = user_row.get("employee_id")
    live_employee_id_int = (
        int(live_employee_id) if live_employee_id is not None else None
    )

    run_id = _create_operations_run(
        conn,
        actor_user_id=actor_id,
        operation=OPERATION_ROLLBACK_ITEM,
        reason=operator_reason,
        trigger="ROLLBACK",
        source_item_id=source_id,
    )

    if live_employee_id_int == restore_target:
        item_id = _insert_operations_item(
            conn,
            run_id=run_id,
            user_id=target_user_id,
            proposed_employee_id=restore_target,
            action=ACTION_ROLLBACK_LINK,
            status=STATUS_NOOP_ALREADY_ROLLED_BACK,
            reason_codes=[REASON_ROLLBACK_ALREADY_APPLIED],
            before_user_snapshot=before_snapshot,
            after_user_snapshot=before_snapshot,
            rollback_payload=_inverse_rollback_payload(
                user_id=target_user_id,
                before_employee_id=live_employee_id_int,
                after_employee_id=restore_target,
                source_item_id=source_id,
            ),
        )
        return _finalize_rollback_result(
            conn,
            run_id=run_id,
            operator_reason=operator_reason,
            source_item_id=source_id,
            source_action=source_action,
            target_user_id=target_user_id,
            item_id=item_id,
            action=ACTION_ROLLBACK_LINK,
            status=STATUS_NOOP_ALREADY_ROLLED_BACK,
            applied=False,
            audit_created=False,
            audit_id=None,
            before_snapshot=before_snapshot,
            after_snapshot=before_snapshot,
            rollback_payload=payload,
            reason_codes=[REASON_ROLLBACK_ALREADY_APPLIED],
            run_status=RUN_STATUS_COMPLETED,
            applied_count=0,
            noop_count=1,
            failed_count=0,
            restored_employee_id=restore_target,
        )

    if _rollback_already_applied(conn, source_id):
        item_id = _insert_operations_item(
            conn,
            run_id=run_id,
            user_id=target_user_id,
            proposed_employee_id=restore_target,
            action=ACTION_ROLLBACK_LINK,
            status=STATUS_NOOP_ALREADY_ROLLED_BACK,
            reason_codes=[REASON_ROLLBACK_ALREADY_APPLIED],
            before_user_snapshot=before_snapshot,
            after_user_snapshot=before_snapshot,
            rollback_payload=_inverse_rollback_payload(
                user_id=target_user_id,
                before_employee_id=live_employee_id_int,
                after_employee_id=restore_target,
                source_item_id=source_id,
            ),
        )
        return _finalize_rollback_result(
            conn,
            run_id=run_id,
            operator_reason=operator_reason,
            source_item_id=source_id,
            source_action=source_action,
            target_user_id=target_user_id,
            item_id=item_id,
            action=ACTION_ROLLBACK_LINK,
            status=STATUS_NOOP_ALREADY_ROLLED_BACK,
            applied=False,
            audit_created=False,
            audit_id=None,
            before_snapshot=before_snapshot,
            after_snapshot=before_snapshot,
            rollback_payload=payload,
            reason_codes=[REASON_ROLLBACK_ALREADY_APPLIED],
            run_status=RUN_STATUS_COMPLETED,
            applied_count=0,
            noop_count=1,
            failed_count=0,
            restored_employee_id=restore_target,
        )

    if live_employee_id_int != expected_current:
        item_id = _insert_operations_item(
            conn,
            run_id=run_id,
            user_id=target_user_id,
            proposed_employee_id=restore_target,
            action=ACTION_ROLLBACK_LINK,
            status=STATUS_FAILED,
            reason_codes=[REASON_ROLLBACK_TARGET_CHANGED],
            before_user_snapshot=before_snapshot,
            after_user_snapshot=before_snapshot,
        )
        return _finalize_rollback_result(
            conn,
            run_id=run_id,
            operator_reason=operator_reason,
            source_item_id=source_id,
            source_action=source_action,
            target_user_id=target_user_id,
            item_id=item_id,
            action=ACTION_ROLLBACK_LINK,
            status=STATUS_FAILED,
            applied=False,
            audit_created=False,
            audit_id=None,
            before_snapshot=before_snapshot,
            after_snapshot=before_snapshot,
            rollback_payload={},
            reason_codes=[REASON_ROLLBACK_TARGET_CHANGED],
            run_status=RUN_STATUS_FAILED,
            applied_count=0,
            noop_count=0,
            failed_count=1,
            restored_employee_id=restore_target,
        )

    if restore_target is not None:
        employee_row = _load_employee_row(conn, int(restore_target))
        if employee_row is None or str(employee_row.get("operational_status") or "") not in (
            OPERATIONAL_EMPLOYEE_STATUSES
        ):
            item_id = _insert_operations_item(
                conn,
                run_id=run_id,
                user_id=target_user_id,
                proposed_employee_id=restore_target,
                action=ACTION_ROLLBACK_LINK,
                status=STATUS_FAILED,
                reason_codes=[REASON_ROLLBACK_TARGET_CHANGED],
                before_user_snapshot=before_snapshot,
                after_user_snapshot=before_snapshot,
            )
            return _finalize_rollback_result(
                conn,
                run_id=run_id,
                operator_reason=operator_reason,
                source_item_id=source_id,
                source_action=source_action,
                target_user_id=target_user_id,
                item_id=item_id,
                action=ACTION_ROLLBACK_LINK,
                status=STATUS_FAILED,
                applied=False,
                audit_created=False,
                audit_id=None,
                before_snapshot=before_snapshot,
                after_snapshot=before_snapshot,
                rollback_payload={},
                reason_codes=[REASON_ROLLBACK_TARGET_CHANGED],
                run_status=RUN_STATUS_FAILED,
                applied_count=0,
                noop_count=0,
                failed_count=1,
                restored_employee_id=restore_target,
            )
        if _employee_linked_to_other_user(
            conn,
            employee_id=int(restore_target),
            exclude_user_id=target_user_id,
        ):
            item_id = _insert_operations_item(
                conn,
                run_id=run_id,
                user_id=target_user_id,
                proposed_employee_id=restore_target,
                action=ACTION_ROLLBACK_LINK,
                status=STATUS_FAILED,
                reason_codes=[REASON_LINK_TARGET_CONFLICT],
                before_user_snapshot=before_snapshot,
                after_user_snapshot=before_snapshot,
            )
            return _finalize_rollback_result(
                conn,
                run_id=run_id,
                operator_reason=operator_reason,
                source_item_id=source_id,
                source_action=source_action,
                target_user_id=target_user_id,
                item_id=item_id,
                action=ACTION_ROLLBACK_LINK,
                status=STATUS_FAILED,
                applied=False,
                audit_created=False,
                audit_id=None,
                before_snapshot=before_snapshot,
                after_snapshot=before_snapshot,
                rollback_payload={},
                reason_codes=[REASON_LINK_TARGET_CONFLICT],
                run_status=RUN_STATUS_FAILED,
                applied_count=0,
                noop_count=0,
                failed_count=1,
                restored_employee_id=restore_target,
            )
        conn.execute(
            text(
                """
                UPDATE public.users
                SET employee_id = :employee_id
                WHERE user_id = :user_id
                  AND employee_id IS NULL
                """
            ),
            {
                "employee_id": int(restore_target),
                "user_id": target_user_id,
            },
        )
    else:
        conn.execute(
            text(
                """
                UPDATE public.users
                SET employee_id = NULL
                WHERE user_id = :user_id
                  AND employee_id = :employee_id
                """
            ),
            {
                "user_id": target_user_id,
                "employee_id": int(expected_current),
            },
        )

    after_row = _load_user_row(conn, target_user_id) or user_row
    after_snapshot = _user_snapshot(after_row)
    inverse_payload = _inverse_rollback_payload(
        user_id=target_user_id,
        before_employee_id=live_employee_id_int,
        after_employee_id=restore_target,
        source_item_id=source_id,
    )
    item_id = _insert_operations_item(
        conn,
        run_id=run_id,
        user_id=target_user_id,
        proposed_employee_id=restore_target,
        action=ACTION_ROLLBACK_LINK,
        status=STATUS_APPLIED,
        reason_codes=[REASON_ROLLBACK_PAYLOAD_APPLIED, REASON_MANUAL_OPERATOR_DECISION],
        before_user_snapshot=before_snapshot,
        after_user_snapshot=after_snapshot,
        rollback_payload=inverse_payload,
    )
    audit_id = write_security_event(
        event_type=EVENT_USER_EMPLOYEE_LINK_ROLLED_BACK,
        actor_user_id=actor_id,
        target_user_id=target_user_id,
        target_employee_id=restore_target if restore_target is not None else expected_current,
        metadata={
            "user_id": target_user_id,
            "source_item_id": source_id,
            "source_action": source_action,
            "source_operation": source_item.get("source_operation"),
            "previous_employee_id": live_employee_id_int,
            "restored_employee_id": restore_target,
            "expected_employee_id": expected_current,
            "run_id": int(run_id),
            "operation": OPERATION_ROLLBACK_ITEM,
            "reason": operator_reason,
        },
        conn=conn,
    )
    return _finalize_rollback_result(
        conn,
        run_id=run_id,
        operator_reason=operator_reason,
        source_item_id=source_id,
        source_action=source_action,
        target_user_id=target_user_id,
        item_id=item_id,
        action=ACTION_ROLLBACK_LINK,
        status=STATUS_APPLIED,
        applied=True,
        audit_created=audit_id is not None,
        audit_id=audit_id,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        rollback_payload=inverse_payload,
        reason_codes=[REASON_ROLLBACK_PAYLOAD_APPLIED],
        run_status=RUN_STATUS_COMPLETED,
        applied_count=1,
        noop_count=0,
        failed_count=0,
        restored_employee_id=restore_target,
    )


def rollback_linkage_item_for_user(
    *,
    actor_user_id: int,
    source_item_id: int,
    reason: str,
) -> dict[str, Any]:
    """Atomic rollback — user update, journal, and audit in one transaction."""
    from app.db.engine import engine

    validated_actor = _validate_actor_user_id(actor_user_id)
    with engine.begin() as conn:
        return rollback_linkage_item(
            conn,
            actor_user_id=validated_actor,
            source_item_id=int(source_item_id),
            reason=reason,
        )


def manual_link_user(
    *,
    actor_user_id: int,
    user_id: int,
    employee_id: int,
    reason: str,
) -> dict[str, Any]:
    """Atomic manual link — user update, journal, and audit in one transaction."""
    from app.db.engine import engine

    validated_actor = _validate_actor_user_id(actor_user_id)
    with engine.begin() as conn:
        return manual_link_user_employee(
            conn,
            actor_user_id=validated_actor,
            user_id=int(user_id),
            employee_id=int(employee_id),
            reason=reason,
        )


def manual_unlink_user(
    *,
    actor_user_id: int,
    user_id: int,
    reason: str,
) -> dict[str, Any]:
    """Atomic manual unlink — user update, journal, and audit in one transaction."""
    from app.db.engine import engine

    validated_actor = _validate_actor_user_id(actor_user_id)
    with engine.begin() as conn:
        return manual_unlink_user_employee(
            conn,
            actor_user_id=validated_actor,
            user_id=int(user_id),
            reason=reason,
        )


def _validate_repair_target(
    *,
    user_id: Optional[int],
    employee_id: Optional[int],
) -> None:
    has_user = user_id is not None
    has_employee = employee_id is not None
    if has_user and has_employee:
        raise UserLinkageOperationsError(
            "provide either user_id or employee_id, not both"
        )
    if not has_user and not has_employee:
        raise UserLinkageOperationsError("user_id or employee_id is required")


def _user_row_to_preview_user(user_row: dict[str, Any]) -> _UserRow:
    return _UserRow(
        user_id=int(user_row["user_id"]),
        login=user_row.get("login"),
        full_name=str(user_row.get("full_name") or ""),
        role_id=int(user_row.get("role_id") or 0),
        google_login=user_row.get("google_login"),
        normalized_name=normalize_fio(user_row.get("full_name")),
    )


def _classify_user_for_repair(conn: Connection, user_id: int) -> dict[str, Any]:
    user_row = _load_user_row(conn, int(user_id))
    if user_row is None:
        return {}
    preview_user = _user_row_to_preview_user(user_row)
    employees = list(_load_employees_for_lookup(conn).values())
    ctx = _build_context([preview_user], employees)
    return _classify_user(ctx, preview_user)


def _load_user_id_for_employee(conn: Connection, employee_id: int) -> Optional[int]:
    value = conn.execute(
        text(
            """
            SELECT user_id
            FROM public.users
            WHERE employee_id = :employee_id
              AND COALESCE(is_active, TRUE) = TRUE
            ORDER BY user_id
            LIMIT 1
            """
        ),
        {"employee_id": int(employee_id)},
    ).scalar_one_or_none()
    return int(value) if value is not None else None


def _preview_candidates_for_employee(
    conn: Connection,
    employee_id: int,
) -> list[dict[str, Any]]:
    preview_report = run_user_linkage_preview(conn)
    return [
        dict(candidate)
        for candidate in preview_report.get("candidates") or []
        if candidate.get("proposed_employee_id") is not None
        and int(candidate["proposed_employee_id"]) == int(employee_id)
    ]


def _employee_state(employee_row: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if employee_row is None:
        return None
    return {
        "employee_id": int(employee_row["employee_id"]),
        "full_name": employee_row.get("full_name"),
        "operational_status": employee_row.get("operational_status"),
    }


def _linkage_state(user_row: dict[str, Any]) -> dict[str, Any]:
    employee_id = user_row.get("employee_id")
    return {
        "user_id": int(user_row["user_id"]),
        "employee_id": int(employee_id) if employee_id is not None else None,
        "linked": employee_id is not None,
    }


def _candidate_linkage(preview_candidate: dict[str, Any]) -> Optional[dict[str, Any]]:
    proposed = preview_candidate.get("proposed_employee_id")
    if proposed is None:
        return None
    return {
        "proposed_employee_id": int(proposed),
        "employee_name": preview_candidate.get("employee_name"),
        "classification": preview_candidate.get("classification"),
        "match_strategy": preview_candidate.get("match_strategy"),
        "reason_codes": list(preview_candidate.get("reason_codes") or []),
    }


def _recommended_action(
    diagnosis_code: str,
    *,
    execute_action: str,
) -> str:
    if diagnosis_code == DIAG_LINK_OK:
        return "NO_ACTION"
    if diagnosis_code == DIAG_SERVICE_ACCOUNT_EXCLUDED:
        return "NO_ACTION"
    if diagnosis_code == DIAG_USER_UNLINKED_EMPLOYEE_MATCH_FOUND:
        return "RE_EXECUTE" if execute_action == ACTION_LINK else "RE_REVIEW"
    if diagnosis_code == DIAG_REVIEW_REQUIRED:
        return "RE_REVIEW"
    if diagnosis_code in {
        DIAG_USER_LINKED_TO_DIFFERENT_EMPLOYEE,
        DIAG_EMPLOYEE_LINKED_TO_DIFFERENT_USER,
        DIAG_CONFLICT_REQUIRES_MANUAL_DECISION,
        DIAG_INACTIVE_EMPLOYEE_TARGET,
        DIAG_NO_CANDIDATE_FOUND,
    }:
        return "MANUAL_DECISION"
    return "MANUAL_DECISION"


def _build_repair_diagnosis(
    conn: Connection,
    *,
    user_row: dict[str, Any],
    employee_row: Optional[dict[str, Any]],
    preview_candidate: dict[str, Any],
    execute_action: str,
    target_employee_id: Optional[int] = None,
    preview_candidate_count: int = 1,
) -> str:
    if is_service_account(user_row):
        return DIAG_SERVICE_ACCOUNT_EXCLUDED

    if employee_row is not None:
        status = str(employee_row.get("operational_status") or "")
        if status not in OPERATIONAL_EMPLOYEE_STATUSES:
            return DIAG_INACTIVE_EMPLOYEE_TARGET

    if target_employee_id is not None:
        linked_user_id = _load_user_id_for_employee(conn, int(target_employee_id))
        if linked_user_id is not None and int(linked_user_id) != int(user_row["user_id"]):
            return DIAG_EMPLOYEE_LINKED_TO_DIFFERENT_USER

    classification = str(preview_candidate.get("classification") or "")
    current_employee_id = user_row.get("employee_id")
    candidate_employee_id = preview_candidate.get("proposed_employee_id")

    if preview_candidate_count > 1 or classification == CLASSIFICATION_AMBIGUOUS:
        return DIAG_CONFLICT_REQUIRES_MANUAL_DECISION

    if current_employee_id is not None:
        if candidate_employee_id is not None and int(current_employee_id) == int(
            candidate_employee_id
        ):
            return DIAG_LINK_OK
        return DIAG_USER_LINKED_TO_DIFFERENT_EMPLOYEE

    if candidate_employee_id is None or classification == CLASSIFICATION_IMPOSSIBLE:
        return DIAG_NO_CANDIDATE_FOUND

    if classification == CLASSIFICATION_EXCLUDED:
        return DIAG_SERVICE_ACCOUNT_EXCLUDED

    if _employee_linked_to_other_user(
        conn,
        employee_id=int(candidate_employee_id),
        exclude_user_id=int(user_row["user_id"]),
    ):
        return DIAG_EMPLOYEE_LINKED_TO_DIFFERENT_USER

    return DIAG_USER_UNLINKED_EMPLOYEE_MATCH_FOUND


def _resolve_repair_scope(
    conn: Connection,
    *,
    user_id: Optional[int],
    employee_id: Optional[int],
) -> tuple[str, dict[str, Any], Optional[dict[str, Any]], int]:
    if user_id is not None:
        user_row = _load_user_row(conn, int(user_id))
        if user_row is None:
            raise UserLinkageOperationsError(f"user_id={int(user_id)} not found")
        employee_row = None
        if user_row.get("employee_id") is not None:
            employee_row = _load_employee_row(conn, int(user_row["employee_id"]))
        return "user", user_row, employee_row, 1

    assert employee_id is not None
    employee_row = _load_employee_row(conn, int(employee_id))
    if employee_row is None:
        raise UserLinkageOperationsError(f"employee_id={int(employee_id)} not found")

    linked_user_id = _load_user_id_for_employee(conn, int(employee_id))
    if linked_user_id is not None:
        user_row = _load_user_row(conn, int(linked_user_id))
        if user_row is None:
            raise UserLinkageOperationsError(f"user_id={linked_user_id} not found")
        return "employee", user_row, employee_row, 1

    preview_matches = _preview_candidates_for_employee(conn, int(employee_id))
    if not preview_matches:
        raise UserLinkageOperationsError(
            f"no user candidate found for employee_id={int(employee_id)} repair"
        )
    diagnostic_user_id = int(preview_matches[0]["user_id"])
    user_row = _load_user_row(conn, diagnostic_user_id)
    if user_row is None:
        raise UserLinkageOperationsError(f"user_id={diagnostic_user_id} not found")
    return "employee", user_row, employee_row, len(preview_matches)


def repair_linkage_preview(
    conn: Connection,
    *,
    actor_user_id: int,
    reason: str,
    user_id: Optional[int] = None,
    employee_id: Optional[int] = None,
) -> dict[str, Any]:
    """Targeted read-only linkage repair diagnostic with journal row."""
    _require_operations_schema(conn)
    validated_actor = _validate_actor_user_id(actor_user_id)
    operator_reason = _validate_reason(reason)
    _validate_repair_target(user_id=user_id, employee_id=employee_id)

    target_kind, user_row, employee_row, candidate_count = _resolve_repair_scope(
        conn,
        user_id=user_id,
        employee_id=employee_id,
    )
    diagnostic_user_id = int(user_row["user_id"])
    preview_candidate = _classify_user_for_repair(conn, diagnostic_user_id)
    latest_decisions = _load_latest_decisions(conn)
    decision = latest_decisions.get(diagnostic_user_id)
    decision_snapshot = _decision_snapshot(decision)
    execute_action, execute_reason_codes, proposed_employee_id = _evaluate_candidate(
        conn,
        user_id=diagnostic_user_id,
        user_row=user_row,
        decision=decision,
        preview=preview_candidate or None,
    )
    diagnosis_code = _build_repair_diagnosis(
        conn,
        user_row=user_row,
        employee_row=employee_row,
        preview_candidate=preview_candidate,
        execute_action=execute_action,
        target_employee_id=int(employee_id) if employee_id is not None else None,
        preview_candidate_count=candidate_count,
    )
    recommended_action = _recommended_action(
        diagnosis_code,
        execute_action=execute_action,
    )
    before_snapshot = _user_snapshot(user_row)
    generated_at = datetime.now(timezone.utc).isoformat()

    run_id = _create_operations_run(
        conn,
        actor_user_id=validated_actor,
        operation=OPERATION_REPAIR_PREVIEW,
        reason=operator_reason,
        trigger="REPAIR",
        dry_run=True,
        extra_summary={
            "target_kind": target_kind,
            "target_user_id": int(user_id) if user_id is not None else None,
            "target_employee_id": int(employee_id) if employee_id is not None else None,
            "diagnosis_code": diagnosis_code,
            "recommended_action": recommended_action,
        },
    )
    source_decision_id = (
        int(decision["decision_id"]) if decision and decision.get("decision_id") else None
    )
    item_id = _insert_operations_item(
        conn,
        run_id=run_id,
        user_id=diagnostic_user_id,
        proposed_employee_id=proposed_employee_id
        or preview_candidate.get("proposed_employee_id"),
        source_decision_id=source_decision_id,
        action=ACTION_REPAIR_PREVIEW,
        status=STATUS_APPLIED,
        reason_codes=[diagnosis_code, *execute_reason_codes],
        preview_snapshot=preview_candidate,
        decision_snapshot=decision_snapshot,
        before_user_snapshot=before_snapshot,
        after_user_snapshot=before_snapshot,
    )
    run_summary = {
        "reason": operator_reason,
        "trigger": "REPAIR",
        "target_kind": target_kind,
        "target_user_id": int(user_id) if user_id is not None else None,
        "target_employee_id": int(employee_id) if employee_id is not None else None,
        "diagnosis_code": diagnosis_code,
        "recommended_action": recommended_action,
        "execute_ready": execute_action == ACTION_LINK,
        "execute_action": execute_action,
        "item_id": int(item_id),
        "applied": 1,
        "failed": 0,
    }
    _finalize_operations_run(
        conn,
        run_id=run_id,
        status=RUN_STATUS_COMPLETED,
        summary=run_summary,
    )

    review_payload = {
        "latest_decision": decision_snapshot.get("decision"),
        "decision_id": decision_snapshot.get("decision_id"),
        "proposed_employee_id": decision_snapshot.get("proposed_employee_id"),
        "decision_at": decision_snapshot.get("decision_at"),
    }

    return {
        "phase": PHASE_R2,
        "operation": OPERATION_REPAIR_PREVIEW,
        "run_id": int(run_id),
        "item_id": int(item_id),
        "dry_run": True,
        "target": {
            "kind": target_kind,
            "user_id": int(user_id) if user_id is not None else None,
            "employee_id": int(employee_id) if employee_id is not None else None,
            "diagnostic_user_id": diagnostic_user_id,
        },
        "current_user": _user_snapshot(user_row),
        "current_employee": _employee_state(employee_row),
        "current_linkage": _linkage_state(user_row),
        "candidate_linkage": _candidate_linkage(preview_candidate),
        "diagnosis_code": diagnosis_code,
        "recommended_action": recommended_action,
        "execute_ready": execute_action == ACTION_LINK,
        "execute_action": execute_action,
        "preview": preview_candidate,
        "review": review_payload,
        "generated_at": generated_at,
    }


def repair_linkage_preview_for_user(
    *,
    actor_user_id: int,
    reason: str,
    user_id: Optional[int] = None,
    employee_id: Optional[int] = None,
) -> dict[str, Any]:
    """Atomic repair preview diagnostic with journal row."""
    from app.db.engine import engine

    validated_actor = _validate_actor_user_id(actor_user_id)
    with engine.begin() as conn:
        return repair_linkage_preview(
            conn,
            actor_user_id=validated_actor,
            reason=reason,
            user_id=user_id,
            employee_id=employee_id,
        )


def _rerun_item_status(execute_item: dict[str, Any]) -> str:
    if execute_item.get("applied"):
        return STATUS_APPLIED
    action = str(execute_item.get("action") or "")
    if action == ACTION_NOOP_ALREADY_LINKED:
        return STATUS_NOOP_ALREADY_LINKED
    return STATUS_SKIPPED


def rerun_user_linkage_execute(
    *,
    actor_user_id: int,
    source_preview_run_id: int,
    confirm_token: str,
    reason: str,
) -> dict[str, Any]:
    """Controlled re-run execute using existing R2.4 validation and apply path."""
    validated_actor = _validate_actor_user_id(actor_user_id)
    operator_reason = _validate_reason(reason)

    execute_result = execute_user_linkage_from_preview(
        actor_user_id=validated_actor,
        preview_run_id=int(source_preview_run_id),
        confirm_token=str(confirm_token),
    )

    from app.db.engine import engine

    generated_at = datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        _require_operations_schema(conn)
        rerun_run_id = _create_operations_run(
            conn,
            actor_user_id=validated_actor,
            operation=OPERATION_RERUN_EXECUTE,
            reason=operator_reason,
            trigger="RE_EXECUTE",
            extra_summary={
                "source_preview_run_id": int(source_preview_run_id),
                "execute_run_id": int(execute_result["run_id"]),
            },
        )
        rerun_items: list[dict[str, Any]] = []
        for execute_item in execute_result.get("items") or []:
            user_id = int(execute_item["user_id"])
            user_row = _load_user_row(conn, user_id)
            if user_row is None:
                continue
            before_snapshot = _user_snapshot(user_row)
            after_employee_id = _employee_id_for_user(conn, user_id)
            after_snapshot = dict(before_snapshot)
            after_snapshot["employee_id"] = after_employee_id
            item_id = _insert_operations_item(
                conn,
                run_id=rerun_run_id,
                user_id=user_id,
                proposed_employee_id=execute_item.get("proposed_employee_id"),
                action=ACTION_RERUN_EXECUTE,
                status=_rerun_item_status(execute_item),
                reason_codes=[operator_reason],
                before_user_snapshot=before_snapshot,
                after_user_snapshot=after_snapshot,
                preview_snapshot={
                    "source_preview_run_id": int(source_preview_run_id),
                    "execute_run_id": int(execute_result["run_id"]),
                    "execute_item_id": int(execute_item.get("item_id") or 0),
                    "execute_action": execute_item.get("action"),
                },
            )
            rerun_items.append(
                {
                    "item_id": int(item_id),
                    "user_id": user_id,
                    "action": ACTION_RERUN_EXECUTE,
                    "status": _rerun_item_status(execute_item),
                    "applied": bool(execute_item.get("applied")),
                }
            )

        run_summary = {
            "reason": operator_reason,
            "trigger": "RE_EXECUTE",
            "source_preview_run_id": int(source_preview_run_id),
            "execute_run_id": int(execute_result["run_id"]),
            "applied": int(execute_result.get("applied") or 0),
            "skipped": int(execute_result.get("skipped") or 0),
            "failed": int(execute_result.get("failed") or 0),
            "audit_records_created": int(execute_result.get("audit_records_created") or 0),
            "items": len(rerun_items),
        }
        _finalize_operations_run(
            conn,
            run_id=rerun_run_id,
            status=RUN_STATUS_COMPLETED,
            summary=run_summary,
        )

    return {
        "phase": PHASE_R2,
        "operation": OPERATION_RERUN_EXECUTE,
        "rerun_run_id": int(rerun_run_id),
        "source_preview_run_id": int(source_preview_run_id),
        "execute_run_id": int(execute_result["run_id"]),
        "run_status": RUN_STATUS_COMPLETED,
        "items": rerun_items,
        "execute": execute_result,
        "generated_at": generated_at,
    }


def _employee_id_for_user(conn: Connection, user_id: int) -> Optional[int]:
    value = conn.execute(
        text("SELECT employee_id FROM public.users WHERE user_id = :user_id"),
        {"user_id": int(user_id)},
    ).scalar_one()
    return int(value) if value is not None else None
