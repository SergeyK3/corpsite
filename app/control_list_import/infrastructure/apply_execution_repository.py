"""SQLAlchemy apply execution journal repository (WP-CL-012)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.control_list_import.apply_execution.errors import ApplyActionTransitionError, ApplyRunTransitionError
from app.control_list_import.apply_execution.models import (
    ApplyActionExecution,
    ApplyActionExecutionStatus,
    ApplyExecutionRun,
    ApplyRunStatus,
    assert_action_transition,
    assert_run_transition,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SqlAlchemyApplyExecutionRepository:
    """Persistent apply execution journal — no canonical PPR/Employment writes."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def get_run_by_fingerprint(self, plan_fingerprint: str) -> Optional[ApplyExecutionRun]:
        row = self._conn.execute(
            text(
                """
                SELECT *
                FROM public.control_list_apply_runs
                WHERE plan_fingerprint = :plan_fingerprint
                """
            ),
            {"plan_fingerprint": plan_fingerprint},
        ).mappings().first()
        if row is None:
            return None
        return self._load_run(int(row["apply_run_id"]))

    def get_action_by_idempotency_key(self, idempotency_key: str) -> Optional[ApplyActionExecution]:
        row = self._conn.execute(
            text(
                """
                SELECT *
                FROM public.control_list_apply_actions
                WHERE idempotency_key = :idempotency_key
                """
            ),
            {"idempotency_key": idempotency_key},
        ).mappings().first()
        if row is None:
            return None
        return self._row_to_action(row)

    def create_run(
        self,
        *,
        import_run_id: int,
        review_run_key: str,
        plan_key: str,
        plan_fingerprint: str,
        plan_snapshot: dict[str, Any],
        requested_by_user_id: Optional[int],
        actions: tuple[ApplyActionExecution, ...],
    ) -> ApplyExecutionRun:
        run_row = self._conn.execute(
            text(
                """
                INSERT INTO public.control_list_apply_runs (
                    import_run_id,
                    review_run_key,
                    plan_key,
                    plan_fingerprint,
                    plan_snapshot,
                    status,
                    requested_by_user_id
                )
                VALUES (
                    :import_run_id,
                    :review_run_key,
                    :plan_key,
                    :plan_fingerprint,
                    CAST(:plan_snapshot AS JSONB),
                    :status,
                    :requested_by_user_id
                )
                RETURNING apply_run_id
                """
            ),
            {
                "import_run_id": import_run_id,
                "review_run_key": review_run_key,
                "plan_key": plan_key,
                "plan_fingerprint": plan_fingerprint,
                "plan_snapshot": json.dumps(plan_snapshot, sort_keys=True, ensure_ascii=False),
                "status": ApplyRunStatus.PENDING.value,
                "requested_by_user_id": requested_by_user_id,
            },
        ).one()
        apply_run_id = int(run_row.apply_run_id)
        for action in actions:
            self._conn.execute(
                text(
                    """
                    INSERT INTO public.control_list_apply_actions (
                        apply_run_id,
                        action_index,
                        action_type,
                        target_aggregate,
                        source_reference,
                        idempotency_key,
                        action_fingerprint,
                        status
                    )
                    VALUES (
                        :apply_run_id,
                        :action_index,
                        :action_type,
                        :target_aggregate,
                        :source_reference,
                        :idempotency_key,
                        :action_fingerprint,
                        :status
                    )
                    """
                ),
                {
                    "apply_run_id": apply_run_id,
                    "action_index": action.action_index,
                    "action_type": action.action_type,
                    "target_aggregate": action.target_aggregate,
                    "source_reference": action.source_reference,
                    "idempotency_key": action.idempotency_key,
                    "action_fingerprint": action.action_fingerprint,
                    "status": ApplyActionExecutionStatus.PENDING.value,
                },
            )
        loaded = self._load_run(apply_run_id)
        assert loaded is not None
        return loaded

    def transition_run_status(
        self,
        apply_run_id: int,
        *,
        expected_status: ApplyRunStatus,
        target_status: ApplyRunStatus,
        failure_code: Optional[str] = None,
        failure_message: Optional[str] = None,
    ) -> ApplyExecutionRun:
        current = self._conn.execute(
            text(
                """
                SELECT status
                FROM public.control_list_apply_runs
                WHERE apply_run_id = :apply_run_id
                FOR UPDATE
                """
            ),
            {"apply_run_id": apply_run_id},
        ).mappings().first()
        if current is None:
            raise ApplyRunTransitionError(f"Apply run {apply_run_id} not found")
        current_status = ApplyRunStatus(current["status"])
        if current_status != expected_status:
            raise ApplyRunTransitionError(
                f"Apply run {apply_run_id} expected {expected_status.value}, got {current_status.value}"
            )
        assert_run_transition(current_status, target_status)

        now = _utcnow()
        params: dict[str, Any] = {
            "apply_run_id": apply_run_id,
            "status": target_status.value,
            "updated_at": now,
        }
        set_parts = ["status = :status", "updated_at = :updated_at"]
        if target_status == ApplyRunStatus.RUNNING:
            set_parts.append("started_at = COALESCE(started_at, :started_at)")
            params["started_at"] = now
        if target_status in {
            ApplyRunStatus.SUCCEEDED,
            ApplyRunStatus.PARTIALLY_SUCCEEDED,
            ApplyRunStatus.FAILED,
            ApplyRunStatus.CANCELLED,
        }:
            set_parts.append("completed_at = :completed_at")
            params["completed_at"] = now
        if target_status == ApplyRunStatus.FAILED:
            set_parts.append("failed_at = :failed_at")
            set_parts.append("failure_code = :failure_code")
            set_parts.append("failure_message = :failure_message")
            params["failed_at"] = now
            params["failure_code"] = failure_code
            params["failure_message"] = failure_message

        self._conn.execute(
            text(
                f"""
                UPDATE public.control_list_apply_runs
                SET {", ".join(set_parts)}
                WHERE apply_run_id = :apply_run_id
                """
            ),
            params,
        )
        loaded = self._load_run(apply_run_id)
        assert loaded is not None
        return loaded

    def transition_action_status(
        self,
        apply_action_execution_id: int,
        *,
        expected_status: ApplyActionExecutionStatus,
        target_status: ApplyActionExecutionStatus,
        result_payload: Optional[dict[str, Any]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> ApplyActionExecution:
        current = self._conn.execute(
            text(
                """
                SELECT *
                FROM public.control_list_apply_actions
                WHERE apply_action_execution_id = :apply_action_execution_id
                FOR UPDATE
                """
            ),
            {"apply_action_execution_id": apply_action_execution_id},
        ).mappings().first()
        if current is None:
            raise ApplyActionTransitionError(
                f"Apply action {apply_action_execution_id} not found"
            )
        current_status = ApplyActionExecutionStatus(current["status"])
        if current_status != expected_status:
            raise ApplyActionTransitionError(
                f"Apply action {apply_action_execution_id} expected {expected_status.value}, "
                f"got {current_status.value}"
            )
        assert_action_transition(current_status, target_status)

        now = _utcnow()
        attempt_increment = 1 if target_status == ApplyActionExecutionStatus.RUNNING else 0
        self._conn.execute(
            text(
                """
                UPDATE public.control_list_apply_actions
                SET
                    status = :status,
                    attempt_count = attempt_count + :attempt_increment,
                    started_at = CASE
                        WHEN :status = 'running' THEN COALESCE(started_at, :now)
                        ELSE started_at
                    END,
                    completed_at = CASE
                        WHEN :status IN ('succeeded', 'skipped', 'deferred', 'failed')
                        THEN :now
                        ELSE completed_at
                    END,
                    result_payload = COALESCE(CAST(:result_payload AS JSONB), result_payload),
                    error_code = :error_code,
                    error_message = :error_message,
                    updated_at = :now
                WHERE apply_action_execution_id = :apply_action_execution_id
                """
            ),
            {
                "apply_action_execution_id": apply_action_execution_id,
                "status": target_status.value,
                "attempt_increment": attempt_increment,
                "now": now,
                "result_payload": json.dumps(result_payload or {}, sort_keys=True, ensure_ascii=False),
                "error_code": error_code,
                "error_message": error_message,
            },
        )
        row = self._conn.execute(
            text(
                """
                SELECT *
                FROM public.control_list_apply_actions
                WHERE apply_action_execution_id = :apply_action_execution_id
                """
            ),
            {"apply_action_execution_id": apply_action_execution_id},
        ).mappings().one()
        return self._row_to_action(row)

    def load_run(self, apply_run_id: int) -> Optional[ApplyExecutionRun]:
        return self._load_run(apply_run_id)

    def _load_run(self, apply_run_id: int) -> Optional[ApplyExecutionRun]:
        run_row = self._conn.execute(
            text(
                """
                SELECT *
                FROM public.control_list_apply_runs
                WHERE apply_run_id = :apply_run_id
                """
            ),
            {"apply_run_id": apply_run_id},
        ).mappings().first()
        if run_row is None:
            return None
        action_rows = self._conn.execute(
            text(
                """
                SELECT *
                FROM public.control_list_apply_actions
                WHERE apply_run_id = :apply_run_id
                ORDER BY action_index ASC
                """
            ),
            {"apply_run_id": apply_run_id},
        ).mappings().all()
        snapshot = run_row["plan_snapshot"]
        if isinstance(snapshot, str):
            snapshot = json.loads(snapshot)
        return ApplyExecutionRun(
            apply_run_id=int(run_row["apply_run_id"]),
            import_run_id=int(run_row["import_run_id"]),
            review_run_key=str(run_row["review_run_key"]),
            plan_key=str(run_row["plan_key"]),
            plan_fingerprint=str(run_row["plan_fingerprint"]),
            plan_snapshot=dict(snapshot or {}),
            status=ApplyRunStatus(run_row["status"]),
            requested_by_user_id=run_row["requested_by_user_id"],
            started_at=run_row["started_at"],
            completed_at=run_row["completed_at"],
            failed_at=run_row["failed_at"],
            failure_code=run_row["failure_code"],
            failure_message=run_row["failure_message"],
            actions=tuple(self._row_to_action(row) for row in action_rows),
        )

    def _row_to_action(self, row: Any) -> ApplyActionExecution:
        payload = row["result_payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return ApplyActionExecution(
            apply_action_execution_id=int(row["apply_action_execution_id"]),
            apply_run_id=int(row["apply_run_id"]),
            action_index=int(row["action_index"]),
            action_type=str(row["action_type"]),
            target_aggregate=str(row["target_aggregate"]),
            source_reference=str(row["source_reference"]),
            idempotency_key=str(row["idempotency_key"]),
            action_fingerprint=str(row["action_fingerprint"]),
            status=ApplyActionExecutionStatus(row["status"]),
            attempt_count=int(row["attempt_count"]),
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            error_code=row["error_code"],
            error_message=row["error_message"],
            result_payload=dict(payload or {}),
        )
