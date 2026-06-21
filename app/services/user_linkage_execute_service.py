"""ADR-044 R2.4b — User → Employee linkage execute preview (dry-run plan, no writes)."""
from __future__ import annotations

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
STATUS_SKIPPED = "SKIPPED"
STATUS_FAILED = "FAILED"

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
            "after_user_snapshot": json.dumps(None),
            "rollback_payload": json.dumps(None),
        },
    ).mappings().one()
    return int(row["item_id"])


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
    user_id: Optional[int],
) -> list[int]:
    user_ids: set[int] = {int(c["user_id"]) for c in preview_candidates}
    for uid, decision in latest_decisions.items():
        if str(decision.get("decision") or "") == DECISION_APPROVE:
            user_ids.add(int(uid))
    ordered = sorted(user_ids)
    if user_id is not None:
        target = int(user_id)
        if target not in ordered:
            return []
        return [target]
    return ordered


def _build_user_linkage_execute_preview(
    conn: Connection,
    *,
    actor_user_id: int,
    limit: Optional[int] = None,
    user_id: Optional[int] = None,
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
) -> ExecutePreviewResult:
    """Build dry-run execute plan using a dedicated DB transaction."""
    from app.db.engine import engine

    with engine.begin() as conn:
        return _build_user_linkage_execute_preview(
            conn,
            actor_user_id=actor_user_id,
            limit=limit,
            user_id=user_id,
        )
