"""ADR-044 R2.4 — User → Employee linkage execute preview and apply engine."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.user_linkage_preview_service import (
    CLASSIFICATION_AMBIGUOUS,
    CLASSIFICATION_EXCLUDED,
    CLASSIFICATION_IMPOSSIBLE,
    CLASSIFICATION_REVIEW_REQUIRED,
    PHASE_R2,
    run_user_linkage_preview,
)
from app.services.user_linkage_review_service import (
    DECISION_APPROVE,
    review_decisions_available,
)

OPERATION_EXECUTE_PREVIEW = "USER_LINKAGE_EXECUTE_PREVIEW"
OPERATION_EXECUTE = "USER_LINKAGE_EXECUTE"

RUN_STATUS_RUNNING = "running"
RUN_STATUS_COMPLETED = "completed"
RUN_STATUS_FAILED = "failed"

ACTION_LINK = "LINK"
ACTION_NOOP_ALREADY_LINKED = "NOOP_ALREADY_LINKED"
ACTION_SKIP_NOT_APPROVED = "SKIP_NOT_APPROVED"
ACTION_SKIP_PREVIEW_DRIFT = "SKIP_PREVIEW_DRIFT"
ACTION_SKIP_CLASSIFICATION_REGRESSION = "SKIP_CLASSIFICATION_REGRESSION"
ACTION_SKIP_EXCLUDED = "SKIP_EXCLUDED"
ACTION_FAIL_ALREADY_LINKED_DIFFERENT = "FAIL_ALREADY_LINKED_DIFFERENT"
ACTION_FAIL_EMPLOYEE_CONFLICT = "FAIL_EMPLOYEE_CONFLICT"

STATUS_PLANNED = "PLANNED"
STATUS_APPLIED = "APPLIED"
STATUS_SKIPPED = "SKIPPED"
STATUS_FAILED = "FAILED"

OPERATIONAL_EMPLOYEE_STATUSES = frozenset({"draft", "active", "suspended"})

EXECUTABLE_CLASSIFICATIONS = frozenset(
    {CLASSIFICATION_REVIEW_REQUIRED, CLASSIFICATION_AMBIGUOUS}
)
EXCLUDED_CLASSIFICATIONS = frozenset(
    {CLASSIFICATION_EXCLUDED, CLASSIFICATION_IMPOSSIBLE}
)

REASON_NOT_APPROVED = "NOT_APPROVED"
REASON_PREVIEW_DRIFT = "PREVIEW_DRIFT"
REASON_CLASSIFICATION_REGRESSION = "CLASSIFICATION_REGRESSION"
REASON_ALREADY_LINKED_DIFFERENT = "ALREADY_LINKED_DIFFERENT"
REASON_EMPLOYEE_CONFLICT = "EMPLOYEE_CONFLICT"


class UserLinkageExecuteError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


@dataclass
class ExecutePreviewResult:
    run_id: int
    phase: str
    dry_run: bool
    operation: str
    status: str
    summary: dict[str, Any]
    items: list[dict[str, Any]]
    generated_at: str


def execute_items_available(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'user_linkage_execute_items'
            LIMIT 1
            """
        )
    ).first()
    if row is None:
        return False
    cols = conn.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'identity_reconciliation_runs'
            """
        )
    ).scalars().all()
    return "operation" in cols


def _load_latest_decisions(conn: Connection) -> dict[int, dict[str, Any]]:
    if not review_decisions_available(conn):
        return {}
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT ON (user_id)
                decision_id,
                reviewer_user_id,
                user_id,
                proposed_employee_id,
                classification,
                match_strategy,
                decision,
                reason,
                created_at
            FROM public.user_linkage_review_decisions
            ORDER BY user_id, created_at DESC, decision_id DESC
            """
        )
    ).mappings().all()
    return {int(row["user_id"]): dict(row) for row in rows}


def _load_user_row(conn: Connection, user_id: int) -> Optional[dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT user_id, login, full_name, employee_id, is_active, role_id
            FROM public.users
            WHERE user_id = :user_id
            """
        ),
        {"user_id": int(user_id)},
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


def _action_to_status(action: str) -> str:
    if action == ACTION_LINK:
        return STATUS_PLANNED
    if action == ACTION_NOOP_ALREADY_LINKED:
        return STATUS_SKIPPED
    if action.startswith("SKIP_"):
        return STATUS_SKIPPED
    if action.startswith("FAIL_"):
        return STATUS_FAILED
    return STATUS_SKIPPED


def _decision_snapshot(decision: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not decision:
        return {}
    created_at = decision.get("created_at")
    return {
        "decision_id": int(decision["decision_id"]),
        "reviewer_user_id": int(decision["reviewer_user_id"]),
        "user_id": int(decision["user_id"]),
        "proposed_employee_id": decision.get("proposed_employee_id"),
        "classification": str(decision.get("classification") or ""),
        "match_strategy": decision.get("match_strategy"),
        "decision": str(decision.get("decision") or ""),
        "reason": decision.get("reason"),
        "created_at": created_at.isoformat() if created_at else None,
    }


def _before_user_snapshot(user_row: dict[str, Any]) -> dict[str, Any]:
    employee_id = user_row.get("employee_id")
    return {
        "user_id": int(user_row["user_id"]),
        "login": user_row.get("login"),
        "full_name": user_row.get("full_name"),
        "employee_id": int(employee_id) if employee_id is not None else None,
        "is_active": user_row.get("is_active"),
        "role_id": user_row.get("role_id"),
    }


def _evaluate_candidate(
    conn: Connection,
    *,
    user_id: int,
    user_row: dict[str, Any],
    decision: Optional[dict[str, Any]],
    preview: Optional[dict[str, Any]],
) -> tuple[str, list[str], Optional[int]]:
    """Return (action, reason_codes, proposed_employee_id)."""
    if decision is None or str(decision.get("decision") or "") != DECISION_APPROVE:
        return ACTION_SKIP_NOT_APPROVED, [REASON_NOT_APPROVED], None

    approved_employee_id = decision.get("proposed_employee_id")
    current_employee_id = user_row.get("employee_id")
    if current_employee_id is not None:
        if approved_employee_id is not None and int(current_employee_id) == int(
            approved_employee_id
        ):
            return ACTION_NOOP_ALREADY_LINKED, [], int(approved_employee_id)
        return (
            ACTION_FAIL_ALREADY_LINKED_DIFFERENT,
            [REASON_ALREADY_LINKED_DIFFERENT],
            int(approved_employee_id) if approved_employee_id is not None else None,
        )

    if preview is None:
        return (
            ACTION_SKIP_CLASSIFICATION_REGRESSION,
            [REASON_CLASSIFICATION_REGRESSION],
            int(approved_employee_id) if approved_employee_id is not None else None,
        )

    classification = str(preview.get("classification") or "")
    fresh_proposed = preview.get("proposed_employee_id")

    if classification in EXCLUDED_CLASSIFICATIONS:
        return ACTION_SKIP_EXCLUDED, list(preview.get("reason_codes") or []), fresh_proposed

    if classification not in EXECUTABLE_CLASSIFICATIONS:
        return (
            ACTION_SKIP_CLASSIFICATION_REGRESSION,
            [REASON_CLASSIFICATION_REGRESSION, *list(preview.get("reason_codes") or [])],
            fresh_proposed,
        )

    if approved_employee_id is None or fresh_proposed is None:
        return ACTION_SKIP_PREVIEW_DRIFT, [REASON_PREVIEW_DRIFT], fresh_proposed

    if int(fresh_proposed) != int(approved_employee_id):
        return ACTION_SKIP_PREVIEW_DRIFT, [REASON_PREVIEW_DRIFT], int(fresh_proposed)

    if _employee_linked_to_other_user(
        conn,
        employee_id=int(fresh_proposed),
        exclude_user_id=int(user_id),
    ):
        return (
            ACTION_FAIL_EMPLOYEE_CONFLICT,
            [REASON_EMPLOYEE_CONFLICT],
            int(fresh_proposed),
        )

    return ACTION_LINK, list(preview.get("reason_codes") or []), int(fresh_proposed)


def _create_execute_run(
    conn: Connection,
    *,
    actor_user_id: int,
    operation: str,
    dry_run: bool,
) -> int:
    row = conn.execute(
        text(
            """
            INSERT INTO public.identity_reconciliation_runs (
                phase, operation, dry_run, actor_user_id, status
            )
            VALUES (:phase, :operation, :dry_run, :actor_user_id, :status)
            RETURNING run_id
            """
        ),
        {
            "phase": PHASE_R2,
            "operation": operation,
            "dry_run": dry_run,
            "actor_user_id": int(actor_user_id),
            "status": RUN_STATUS_RUNNING,
        },
    ).mappings().one()
    return int(row["run_id"])


def _insert_execute_item(
    conn: Connection,
    *,
    run_id: int,
    user_id: int,
    proposed_employee_id: Optional[int],
    source_decision_id: Optional[int],
    action: str,
    status: str,
    reason_codes: list[str],
    preview_snapshot: dict[str, Any],
    decision_snapshot: dict[str, Any],
    before_user_snapshot: dict[str, Any],
    after_user_snapshot: Optional[dict[str, Any]] = None,
    rollback_payload: Optional[dict[str, Any]] = None,
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
            "preview_snapshot": json.dumps(preview_snapshot),
            "decision_snapshot": json.dumps(decision_snapshot),
            "before_user_snapshot": json.dumps(before_user_snapshot),
            "after_user_snapshot": json.dumps(after_user_snapshot),
            "rollback_payload": json.dumps(rollback_payload),
        },
    ).mappings().one()
    return int(row["item_id"])


def _load_user_row_for_update(conn: Connection, user_id: int) -> Optional[dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT user_id, login, full_name, employee_id, is_active, role_id
            FROM public.users
            WHERE user_id = :user_id
            FOR UPDATE
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


def _load_preview_run(conn: Connection, preview_run_id: int) -> Optional[dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT run_id, phase, operation, dry_run, actor_user_id, status, summary
            FROM public.identity_reconciliation_runs
            WHERE run_id = :run_id
            """
        ),
        {"run_id": int(preview_run_id)},
    ).mappings().first()
    return dict(row) if row else None


def _load_planned_link_items(conn: Connection, preview_run_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT
                item_id,
                user_id,
                proposed_employee_id,
                source_decision_id,
                action,
                status,
                reason_codes,
                preview_snapshot,
                decision_snapshot,
                before_user_snapshot
            FROM public.user_linkage_execute_items
            WHERE run_id = :run_id
              AND action = :action
              AND status = :status
            ORDER BY user_id, item_id
            """
        ),
        {
            "run_id": int(preview_run_id),
            "action": ACTION_LINK,
            "status": STATUS_PLANNED,
        },
    ).mappings().all()
    return [dict(row) for row in rows]


def _preview_execute_in_progress(conn: Connection, preview_run_id: int) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM public.identity_reconciliation_runs
            WHERE phase = :phase
              AND operation = :operation
              AND status = :status
              AND summary->>'source_preview_run_id' = :preview_run_id
            LIMIT 1
            """
        ),
        {
            "phase": PHASE_R2,
            "operation": OPERATION_EXECUTE,
            "status": RUN_STATUS_RUNNING,
            "preview_run_id": str(int(preview_run_id)),
        },
    ).first()
    return row is not None


def _confirm_token_for_planned_items(
    preview_run_id: int,
    planned_items: list[dict[str, Any]],
) -> str:
    payload = {
        "run_id": int(preview_run_id),
        "operation": OPERATION_EXECUTE_PREVIEW,
        "planned_items": sorted(
            [
                {
                    "user_id": int(item["user_id"]),
                    "proposed_employee_id": item.get("proposed_employee_id"),
                    "source_decision_id": item.get("source_decision_id"),
                }
                for item in planned_items
            ],
            key=lambda row: int(row["user_id"]),
        ),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"sha256:{digest}"


def _blocking_gates_active(blocking_gates: list[dict[str, Any]]) -> bool:
    return any(
        gate.get("blocks_execute") and int(gate.get("count") or 0) > 0
        for gate in blocking_gates
    )


def _validate_execute_request(
    conn: Connection,
    *,
    preview_run_id: int,
    confirm_token: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    preview_run = _load_preview_run(conn, int(preview_run_id))
    if preview_run is None:
        raise UserLinkageExecuteError(f"preview run_id={preview_run_id} not found")

    if str(preview_run.get("phase") or "") != PHASE_R2:
        raise UserLinkageExecuteError("preview run phase must be R2")
    if str(preview_run.get("operation") or "") != OPERATION_EXECUTE_PREVIEW:
        raise UserLinkageExecuteError("preview run operation must be USER_LINKAGE_EXECUTE_PREVIEW")
    if preview_run.get("dry_run") is not True:
        raise UserLinkageExecuteError("preview run must be dry_run=true")
    if str(preview_run.get("status") or "") != RUN_STATUS_COMPLETED:
        raise UserLinkageExecuteError("preview run must be completed")

    planned_items = _load_planned_link_items(conn, int(preview_run_id))
    expected_token = _confirm_token_for_planned_items(int(preview_run_id), planned_items)
    if str(confirm_token or "").strip() != expected_token:
        raise UserLinkageExecuteError("confirm_token mismatch")

    preview_summary = preview_run.get("summary") or {}
    if isinstance(preview_summary, str):
        preview_summary = json.loads(preview_summary)
    planned_link = int(preview_summary.get("planned_link") or 0)
    if planned_link <= 0 and not planned_items:
        raise UserLinkageExecuteError("execute_allowed is false: no planned LINK items")
    if planned_link <= 0 and planned_items:
        planned_link = len(planned_items)

    blocking_gates = _check_r2_execute_blocking_gates(conn)
    if _blocking_gates_active(blocking_gates):
        gate_ids = [
            gate["gate_id"]
            for gate in blocking_gates
            if gate.get("blocks_execute") and int(gate.get("count") or 0) > 0
        ]
        raise UserLinkageExecuteError(
            "blocking gates present: " + ", ".join(gate_ids)
        )

    if _preview_execute_in_progress(conn, int(preview_run_id)):
        raise UserLinkageExecuteError("preview run execute already in progress")

    return preview_run, planned_items


def _rollback_payload_for_link(
    *,
    user_id: int,
    previous_employee_id: Optional[int],
    employee_id: int,
    decision_id: Optional[int],
) -> dict[str, Any]:
    return {
        "user_id": int(user_id),
        "previous_employee_id": int(previous_employee_id)
        if previous_employee_id is not None
        else None,
        "employee_id": int(employee_id),
        "decision_id": int(decision_id) if decision_id is not None else None,
    }


def _apply_planned_link_item(
    conn: Connection,
    *,
    execute_run_id: int,
    actor_user_id: int,
    planned_item: dict[str, Any],
    preview_by_user: dict[int, dict[str, Any]],
    latest_decisions: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    from app.services.security_audit_service import write_security_event

    user_id = int(planned_item["user_id"])
    user_row = _load_user_row_for_update(conn, user_id)
    if user_row is None:
        item_id = _insert_execute_item(
            conn,
            run_id=execute_run_id,
            user_id=user_id,
            proposed_employee_id=planned_item.get("proposed_employee_id"),
            source_decision_id=planned_item.get("source_decision_id"),
            action=ACTION_FAIL_ALREADY_LINKED_DIFFERENT,
            status=STATUS_FAILED,
            reason_codes=[REASON_ALREADY_LINKED_DIFFERENT],
            preview_snapshot=dict(planned_item.get("preview_snapshot") or {}),
            decision_snapshot=dict(planned_item.get("decision_snapshot") or {}),
            before_user_snapshot={},
        )
        return {
            "item_id": item_id,
            "user_id": user_id,
            "action": ACTION_FAIL_ALREADY_LINKED_DIFFERENT,
            "status": STATUS_FAILED,
            "applied": False,
            "audit_created": False,
        }

    decision = latest_decisions.get(user_id)
    preview = preview_by_user.get(user_id)
    action, reason_codes, proposed_employee_id = _evaluate_candidate(
        conn,
        user_id=user_id,
        user_row=user_row,
        decision=decision,
        preview=preview,
    )
    decision_snapshot = _decision_snapshot(decision)
    before_snapshot = _before_user_snapshot(user_row)
    preview_snapshot = dict(preview) if preview else dict(planned_item.get("preview_snapshot") or {})
    source_decision_id = (
        int(decision["decision_id"]) if decision and decision.get("decision_id") else None
    )

    if action == ACTION_LINK and proposed_employee_id is not None:
        employee_row = _load_employee_row(conn, int(proposed_employee_id))
        if employee_row is None or str(employee_row.get("operational_status") or "") not in (
            OPERATIONAL_EMPLOYEE_STATUSES
        ):
            action = ACTION_SKIP_CLASSIFICATION_REGRESSION
            reason_codes = [REASON_CLASSIFICATION_REGRESSION]
            status = STATUS_SKIPPED
        elif _employee_linked_to_other_user(
            conn,
            employee_id=int(proposed_employee_id),
            exclude_user_id=user_id,
        ):
            action = ACTION_FAIL_EMPLOYEE_CONFLICT
            reason_codes = [REASON_EMPLOYEE_CONFLICT]
            status = STATUS_FAILED
        else:
            previous_employee_id = user_row.get("employee_id")
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
                    "employee_id": int(proposed_employee_id),
                    "user_id": user_id,
                },
            )
            after_row = _load_user_row(conn, user_id)
            after_snapshot = _before_user_snapshot(after_row or user_row)
            rollback_payload = _rollback_payload_for_link(
                user_id=user_id,
                previous_employee_id=previous_employee_id,
                employee_id=int(proposed_employee_id),
                decision_id=source_decision_id,
            )
            item_id = _insert_execute_item(
                conn,
                run_id=execute_run_id,
                user_id=user_id,
                proposed_employee_id=int(proposed_employee_id),
                source_decision_id=source_decision_id,
                action=ACTION_LINK,
                status=STATUS_APPLIED,
                reason_codes=reason_codes,
                preview_snapshot=preview_snapshot,
                decision_snapshot=decision_snapshot,
                before_user_snapshot=before_snapshot,
                after_user_snapshot=after_snapshot,
                rollback_payload=rollback_payload,
            )
            audit_id = write_security_event(
                event_type="USER_EMPLOYEE_LINKED",
                actor_user_id=int(actor_user_id),
                target_user_id=user_id,
                target_employee_id=int(proposed_employee_id),
                metadata={
                    "user_id": user_id,
                    "employee_id": int(proposed_employee_id),
                    "previous_employee_id": rollback_payload["previous_employee_id"],
                    "decision_id": source_decision_id,
                    "run_id": int(execute_run_id),
                    "match_strategy": preview_snapshot.get("match_strategy"),
                    "classification": preview_snapshot.get("classification"),
                },
                conn=conn,
            )
            return {
                "item_id": item_id,
                "user_id": user_id,
                "action": ACTION_LINK,
                "status": STATUS_APPLIED,
                "applied": True,
                "audit_created": audit_id is not None,
            }

    status = _action_to_status(action)
    if action == ACTION_NOOP_ALREADY_LINKED:
        status = STATUS_SKIPPED
    item_id = _insert_execute_item(
        conn,
        run_id=execute_run_id,
        user_id=user_id,
        proposed_employee_id=proposed_employee_id,
        source_decision_id=source_decision_id,
        action=action,
        status=status,
        reason_codes=reason_codes,
        preview_snapshot=preview_snapshot,
        decision_snapshot=decision_snapshot,
        before_user_snapshot=before_snapshot,
    )
    return {
        "item_id": item_id,
        "user_id": user_id,
        "action": action,
        "status": status,
        "applied": False,
        "audit_created": False,
    }


def run_user_linkage_execute(
    conn: Connection,
    *,
    actor_user_id: int,
    preview_run_id: int,
    confirm_token: str,
) -> dict[str, Any]:
    """Apply approved user linkage from a completed execute-preview run."""
    if not execute_items_available(conn):
        raise UserLinkageExecuteError(
            "user_linkage_execute_items schema missing — run alembic upgrade head"
        )

    _preview_run, planned_items = _validate_execute_request(
        conn,
        preview_run_id=int(preview_run_id),
        confirm_token=confirm_token,
    )

    execute_run_id = _create_execute_run(
        conn,
        actor_user_id=int(actor_user_id),
        operation=OPERATION_EXECUTE,
        dry_run=False,
    )
    conn.execute(
        text(
            """
            UPDATE public.identity_reconciliation_runs
            SET summary = CAST(:summary AS jsonb)
            WHERE run_id = :run_id
            """
        ),
        {
            "run_id": int(execute_run_id),
            "summary": json.dumps({"source_preview_run_id": int(preview_run_id)}),
        },
    )

    return _execute_planned_items(
        planned_items=planned_items,
        execute_run_id=int(execute_run_id),
        actor_user_id=int(actor_user_id),
        preview_run_id=int(preview_run_id),
    )


def _execute_planned_items(
    *,
    planned_items: list[dict[str, Any]],
    execute_run_id: int,
    actor_user_id: int,
    preview_run_id: int,
) -> dict[str, Any]:
    from app.db.engine import engine

    with engine.connect() as preview_conn:
        preview_report = run_user_linkage_preview(preview_conn)
    preview_by_user = {
        int(c["user_id"]): dict(c) for c in preview_report.get("candidates") or []
    }
    with engine.connect() as decisions_conn:
        latest_decisions = _load_latest_decisions(decisions_conn)

    item_results: list[dict[str, Any]] = []
    applied = 0
    skipped = 0
    failed = 0
    audit_records_created = 0

    for planned_item in planned_items:
        try:
            with engine.begin() as item_conn:
                result = _apply_planned_link_item(
                    item_conn,
                    execute_run_id=int(execute_run_id),
                    actor_user_id=int(actor_user_id),
                    planned_item=planned_item,
                    preview_by_user=preview_by_user,
                    latest_decisions=latest_decisions,
                )
        except Exception as exc:
            user_id = int(planned_item["user_id"])
            with engine.begin() as fail_conn:
                item_id = _insert_execute_item(
                    fail_conn,
                    run_id=int(execute_run_id),
                    user_id=user_id,
                    proposed_employee_id=planned_item.get("proposed_employee_id"),
                    source_decision_id=planned_item.get("source_decision_id"),
                    action=ACTION_FAIL_ALREADY_LINKED_DIFFERENT,
                    status=STATUS_FAILED,
                    reason_codes=[str(exc)],
                    preview_snapshot=dict(planned_item.get("preview_snapshot") or {}),
                    decision_snapshot=dict(planned_item.get("decision_snapshot") or {}),
                    before_user_snapshot=dict(planned_item.get("before_user_snapshot") or {}),
                )
            result = {
                "item_id": item_id,
                "user_id": user_id,
                "action": ACTION_FAIL_ALREADY_LINKED_DIFFERENT,
                "status": STATUS_FAILED,
                "applied": False,
                "audit_created": False,
            }

        item_results.append(result)
        if result.get("status") == STATUS_APPLIED:
            applied += 1
        elif result.get("status") == STATUS_FAILED:
            failed += 1
        else:
            skipped += 1
        if result.get("audit_created"):
            audit_records_created += 1

    execute_summary = {
        "source_preview_run_id": int(preview_run_id),
        "applied": applied,
        "skipped": skipped,
        "failed": failed,
        "audit_records_created": audit_records_created,
        "total_planned": len(planned_items),
    }
    run_status = RUN_STATUS_FAILED if failed and not applied else RUN_STATUS_COMPLETED

    with engine.begin() as final_conn:
        _finalize_execute_run(
            final_conn,
            run_id=int(execute_run_id),
            status=run_status,
            summary=execute_summary,
        )

    return {
        "phase": PHASE_R2,
        "dry_run": False,
        "preview_run_id": int(preview_run_id),
        "run_id": int(execute_run_id),
        "run_status": run_status,
        "operation": OPERATION_EXECUTE,
        "applied": applied,
        "skipped": skipped,
        "failed": failed,
        "audit_records_created": audit_records_created,
        "items": item_results,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def execute_user_linkage_from_preview(
    *,
    actor_user_id: int,
    preview_run_id: int,
    confirm_token: str,
) -> dict[str, Any]:
    """Validate preview run, commit execute journal header, then apply per-item."""
    from app.db.engine import engine

    with engine.begin() as conn:
        if not execute_items_available(conn):
            raise UserLinkageExecuteError(
                "user_linkage_execute_items schema missing — run alembic upgrade head"
            )
        _preview_run, planned_items = _validate_execute_request(
            conn,
            preview_run_id=int(preview_run_id),
            confirm_token=confirm_token,
        )
        execute_run_id = _create_execute_run(
            conn,
            actor_user_id=int(actor_user_id),
            operation=OPERATION_EXECUTE,
            dry_run=False,
        )
        conn.execute(
            text(
                """
                UPDATE public.identity_reconciliation_runs
                SET summary = CAST(:summary AS jsonb)
                WHERE run_id = :run_id
                """
            ),
            {
                "run_id": int(execute_run_id),
                "summary": json.dumps({"source_preview_run_id": int(preview_run_id)}),
            },
        )

    return _execute_planned_items(
        planned_items=planned_items,
        execute_run_id=int(execute_run_id),
        actor_user_id=int(actor_user_id),
        preview_run_id=int(preview_run_id),
    )


def _finalize_execute_run(
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


def _build_candidate_user_ids(
    preview_candidates: list[dict[str, Any]],
    latest_decisions: dict[int, dict[str, Any]],
    *,
    user_id: Optional[int] = None,
    user_ids: Optional[list[int]] = None,
) -> list[int]:
    user_ids_set: set[int] = {int(c["user_id"]) for c in preview_candidates}
    for uid, decision in latest_decisions.items():
        if str(decision.get("decision") or "") == DECISION_APPROVE:
            user_ids_set.add(int(uid))
    ordered = sorted(user_ids_set)
    if user_id is not None:
        target = int(user_id)
        if target not in ordered:
            return []
        return [target]
    if user_ids is not None:
        allowed = {int(uid) for uid in user_ids}
        ordered = [uid for uid in ordered if uid in allowed]
    return ordered


def _check_r2_execute_blocking_gates(conn: Connection) -> list[dict[str, Any]]:
    orphan_count = int(
        conn.execute(
            text(
                """
                SELECT COUNT(*) AS cnt
                FROM public.users u
                LEFT JOIN public.employees e ON e.employee_id = u.employee_id
                WHERE u.employee_id IS NOT NULL
                  AND e.employee_id IS NULL
                """
            )
        ).scalar_one()
    )
    duplicate_count = int(
        conn.execute(
            text(
                """
                SELECT COUNT(*) AS cnt
                FROM (
                    SELECT u.employee_id
                    FROM public.users u
                    WHERE COALESCE(u.is_active, TRUE) = TRUE
                      AND u.employee_id IS NOT NULL
                    GROUP BY u.employee_id
                    HAVING COUNT(*) > 1
                ) dup
                """
            )
        ).scalar_one()
    )
    inactive_target_count = int(
        conn.execute(
            text(
                """
                SELECT COUNT(*) AS cnt
                FROM public.users u
                JOIN public.employees e ON e.employee_id = u.employee_id
                WHERE u.employee_id IS NOT NULL
                  AND e.operational_status NOT IN ('draft', 'active', 'suspended')
                """
            )
        ).scalar_one()
    )
    return [
        {
            "gate_id": "V3a_orphan_users_employee_id",
            "severity": "error",
            "blocks_execute": True,
            "count": orphan_count,
            "passed": orphan_count == 0,
            "message": "users.employee_id must reference an existing employee",
        },
        {
            "gate_id": "V3b_duplicate_user_per_employee",
            "severity": "error",
            "blocks_execute": True,
            "count": duplicate_count,
            "passed": duplicate_count == 0,
            "message": "at most one active user per employee_id",
        },
        {
            "gate_id": "R2_inactive_employee_target",
            "severity": "error",
            "blocks_execute": True,
            "count": inactive_target_count,
            "passed": inactive_target_count == 0,
            "message": "users.employee_id must not point to inactive employees",
        },
    ]


def _build_confirm_token(result: ExecutePreviewResult) -> str:
    return _confirm_token_for_planned_items(
        int(result.run_id),
        [item for item in result.items if item.get("action") == ACTION_LINK],
    )


def _planned_outcome_for_action(action: str) -> tuple[str, Optional[str]]:
    if action == ACTION_LINK:
        return "apply", None
    if action.startswith("FAIL_"):
        return "fail", action
    return "skip", action


def format_execute_preview_report(
    result: ExecutePreviewResult,
    *,
    blocking_gates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Map service result to ADR R2.4 execute-preview API response shape."""
    blocking = any(
        gate.get("blocks_execute") and int(gate.get("count") or 0) > 0
        for gate in blocking_gates
    )
    planned_link = int(result.summary.get("planned_link") or 0)
    skipped_total = (
        int(result.summary.get("skipped_not_approved") or 0)
        + int(result.summary.get("skipped_preview_drift") or 0)
        + int(result.summary.get("skipped_classification_regression") or 0)
        + int(result.summary.get("skipped_excluded") or 0)
        + int(result.summary.get("noop_already_linked") or 0)
    )
    failed_total = (
        int(result.summary.get("failed_already_linked_different") or 0)
        + int(result.summary.get("failed_employee_conflict") or 0)
    )

    items: list[dict[str, Any]] = []
    for raw in result.items:
        preview_snapshot = raw.get("preview_snapshot") or {}
        decision_snapshot = raw.get("decision_snapshot") or {}
        before_snapshot = raw.get("before_user_snapshot") or {}
        action = str(raw.get("action") or "")
        planned_outcome, skip_reason = _planned_outcome_for_action(action)
        items.append(
            {
                "item_id": int(raw["item_id"]),
                "user_id": int(raw["user_id"]),
                "login": preview_snapshot.get("login") or before_snapshot.get("login"),
                "proposed_employee_id": raw.get("proposed_employee_id"),
                "employee_name": preview_snapshot.get("employee_name"),
                "decision_id": decision_snapshot.get("decision_id"),
                "decision_at": decision_snapshot.get("created_at"),
                "classification": preview_snapshot.get("classification")
                or decision_snapshot.get("classification"),
                "match_strategy": preview_snapshot.get("match_strategy")
                or decision_snapshot.get("match_strategy"),
                "action": action,
                "status": str(raw.get("status") or ""),
                "reason_codes": list(raw.get("reason_codes") or []),
                "planned_outcome": planned_outcome,
                "skip_reason": skip_reason,
            }
        )

    return {
        "phase": result.phase,
        "dry_run": result.dry_run,
        "generated_at": result.generated_at,
        "run_id": int(result.run_id),
        "run_status": result.status,
        "operation": result.operation,
        "execute_allowed": planned_link > 0 and not blocking,
        "blocking_gates": blocking_gates,
        "summary": {
            **result.summary,
            "eligible": int(result.summary.get("total_evaluated") or 0),
            "would_apply": planned_link,
            "would_skip": skipped_total,
            "would_fail": failed_total,
            "drift_skipped": int(result.summary.get("skipped_preview_drift") or 0),
        },
        "items": items,
        "confirm_token": _build_confirm_token(result),
    }


def build_user_linkage_execute_preview_report(
    conn: Connection,
    *,
    actor_user_id: int,
    limit: Optional[int] = None,
    user_id: Optional[int] = None,
    user_ids: Optional[list[int]] = None,
) -> dict[str, Any]:
    """Build dry-run execute plan and return API report payload."""
    result = _build_user_linkage_execute_preview(
        conn,
        actor_user_id=int(actor_user_id),
        limit=limit,
        user_id=user_id,
        user_ids=user_ids,
    )
    blocking_gates = _check_r2_execute_blocking_gates(conn)
    return format_execute_preview_report(result, blocking_gates=blocking_gates)


def _build_user_linkage_execute_preview(
    conn: Connection,
    *,
    actor_user_id: int,
    limit: Optional[int] = None,
    user_id: Optional[int] = None,
    user_ids: Optional[list[int]] = None,
) -> ExecutePreviewResult:
    """Build dry-run execute plan and persist run + item journal rows."""
    if not execute_items_available(conn):
        raise UserLinkageExecuteError(
            "user_linkage_execute_items schema missing — run alembic upgrade head"
        )
    if not review_decisions_available(conn):
        raise UserLinkageExecuteError("user_linkage_review_decisions table is not available")

    generated_at = datetime.now(timezone.utc).isoformat()
    preview_report = run_user_linkage_preview(conn)
    preview_by_user = {
        int(c["user_id"]): dict(c) for c in preview_report.get("candidates") or []
    }
    latest_decisions = _load_latest_decisions(conn)

    candidate_user_ids = _build_candidate_user_ids(
        list(preview_by_user.values()),
        latest_decisions,
        user_id=user_id,
        user_ids=user_ids,
    )
    if limit is not None:
        candidate_user_ids = candidate_user_ids[: int(limit)]

    summary_counts = {
        "total_evaluated": 0,
        "planned_link": 0,
        "noop_already_linked": 0,
        "skipped_not_approved": 0,
        "skipped_preview_drift": 0,
        "skipped_classification_regression": 0,
        "skipped_excluded": 0,
        "failed_already_linked_different": 0,
        "failed_employee_conflict": 0,
    }

    run_id = _create_execute_run(
        conn,
        actor_user_id=int(actor_user_id),
        operation=OPERATION_EXECUTE_PREVIEW,
        dry_run=True,
    )

    items: list[dict[str, Any]] = []
    for uid in candidate_user_ids:
        user_row = _load_user_row(conn, uid)
        if user_row is None:
            continue

        decision = latest_decisions.get(uid)
        preview = preview_by_user.get(uid)
        action, reason_codes, proposed_employee_id = _evaluate_candidate(
            conn,
            user_id=uid,
            user_row=user_row,
            decision=decision,
            preview=preview,
        )
        status = _action_to_status(action)
        decision_snapshot = _decision_snapshot(decision)
        before_snapshot = _before_user_snapshot(user_row)
        preview_snapshot = dict(preview) if preview else {}

        source_decision_id = (
            int(decision["decision_id"]) if decision and decision.get("decision_id") else None
        )
        item_id = _insert_execute_item(
            conn,
            run_id=run_id,
            user_id=uid,
            proposed_employee_id=proposed_employee_id,
            source_decision_id=source_decision_id,
            action=action,
            status=status,
            reason_codes=reason_codes,
            preview_snapshot=preview_snapshot,
            decision_snapshot=decision_snapshot,
            before_user_snapshot=before_snapshot,
        )

        summary_counts["total_evaluated"] += 1
        if action == ACTION_LINK:
            summary_counts["planned_link"] += 1
        elif action == ACTION_NOOP_ALREADY_LINKED:
            summary_counts["noop_already_linked"] += 1
        elif action == ACTION_SKIP_NOT_APPROVED:
            summary_counts["skipped_not_approved"] += 1
        elif action == ACTION_SKIP_PREVIEW_DRIFT:
            summary_counts["skipped_preview_drift"] += 1
        elif action == ACTION_SKIP_CLASSIFICATION_REGRESSION:
            summary_counts["skipped_classification_regression"] += 1
        elif action == ACTION_SKIP_EXCLUDED:
            summary_counts["skipped_excluded"] += 1
        elif action == ACTION_FAIL_ALREADY_LINKED_DIFFERENT:
            summary_counts["failed_already_linked_different"] += 1
        elif action == ACTION_FAIL_EMPLOYEE_CONFLICT:
            summary_counts["failed_employee_conflict"] += 1

        items.append(
            {
                "item_id": item_id,
                "user_id": uid,
                "proposed_employee_id": proposed_employee_id,
                "source_decision_id": source_decision_id,
                "action": action,
                "status": status,
                "reason_codes": reason_codes,
                "preview_snapshot": preview_snapshot,
                "decision_snapshot": decision_snapshot,
                "before_user_snapshot": before_snapshot,
            }
        )

    _finalize_execute_run(
        conn,
        run_id=run_id,
        status=RUN_STATUS_COMPLETED,
        summary=summary_counts,
    )

    return ExecutePreviewResult(
        run_id=run_id,
        phase=PHASE_R2,
        dry_run=True,
        operation=OPERATION_EXECUTE_PREVIEW,
        status=RUN_STATUS_COMPLETED,
        summary=summary_counts,
        items=items,
        generated_at=generated_at,
    )


def build_user_linkage_execute_preview(
    *,
    actor_user_id: int,
    limit: Optional[int] = None,
    user_id: Optional[int] = None,
    user_ids: Optional[list[int]] = None,
) -> ExecutePreviewResult:
    """Build dry-run execute plan using a dedicated DB transaction."""
    from app.db.engine import engine

    with engine.begin() as conn:
        return _build_user_linkage_execute_preview(
            conn,
            actor_user_id=actor_user_id,
            limit=limit,
            user_id=user_id,
            user_ids=user_ids,
        )
