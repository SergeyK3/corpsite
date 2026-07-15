"""SQLAlchemy adapter for command_id idempotency (ppr_command_executions)."""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from app.ppr.domain.command_idempotency_repositories import (
    COMMAND_EXECUTION_COMPLETED,
    COMMAND_EXECUTION_PENDING,
    CommandExecutionRecord,
)


def _row_to_record(row: RowMapping) -> CommandExecutionRecord:
    payload = row["result_payload"] or {}
    if not isinstance(payload, dict):
        payload = dict(payload)
    return CommandExecutionRecord(
        command_id=str(row["command_id"]),
        command_type=str(row["command_type"]),
        person_id=int(row["person_id"]),
        request_fingerprint=str(row["request_fingerprint"]),
        status=str(row["status"]),
        result_payload=dict(payload),
        created_at=row["created_at"],
        completed_at=row.get("completed_at"),
    )


class SqlAlchemyCommandIdempotencyRepository:
    """Command idempotency store — does not commit."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def reserve_execution(
        self,
        *,
        command_id: str,
        command_type: str,
        person_id: int,
        request_fingerprint: str,
    ) -> CommandExecutionRecord | None:
        row = self._conn.execute(
            text(
                """
                INSERT INTO public.ppr_command_executions (
                    command_id,
                    command_type,
                    person_id,
                    request_fingerprint,
                    status,
                    result_payload
                )
                VALUES (
                    :command_id,
                    :command_type,
                    :person_id,
                    :request_fingerprint,
                    :status,
                    CAST(:result_payload AS jsonb)
                )
                ON CONFLICT (command_id) DO NOTHING
                RETURNING
                    command_id,
                    command_type,
                    person_id,
                    request_fingerprint,
                    status,
                    result_payload,
                    created_at,
                    completed_at
                """
            ),
            {
                "command_id": command_id,
                "command_type": command_type,
                "person_id": int(person_id),
                "request_fingerprint": request_fingerprint,
                "status": COMMAND_EXECUTION_PENDING,
                "result_payload": json.dumps({}, ensure_ascii=False),
            },
        ).mappings().one_or_none()
        if row is None:
            return None
        return _row_to_record(row)

    def load_execution(self, command_id: str) -> CommandExecutionRecord | None:
        row = self._conn.execute(
            text(
                """
                SELECT
                    command_id,
                    command_type,
                    person_id,
                    request_fingerprint,
                    status,
                    result_payload,
                    created_at,
                    completed_at
                FROM public.ppr_command_executions
                WHERE command_id = :command_id
                """
            ),
            {"command_id": command_id},
        ).mappings().one_or_none()
        if row is None:
            return None
        return _row_to_record(row)

    def complete_execution(
        self,
        command_id: str,
        *,
        result_payload: Mapping[str, Any],
    ) -> CommandExecutionRecord:
        row = self._conn.execute(
            text(
                """
                UPDATE public.ppr_command_executions
                SET status = :status,
                    result_payload = CAST(:result_payload AS jsonb),
                    completed_at = now()
                WHERE command_id = :command_id
                  AND status = :pending_status
                RETURNING
                    command_id,
                    command_type,
                    person_id,
                    request_fingerprint,
                    status,
                    result_payload,
                    created_at,
                    completed_at
                """
            ),
            {
                "command_id": command_id,
                "status": COMMAND_EXECUTION_COMPLETED,
                "pending_status": COMMAND_EXECUTION_PENDING,
                "result_payload": json.dumps(dict(result_payload), ensure_ascii=False),
            },
        ).mappings().one_or_none()
        if row is None:
            existing = self.load_execution(command_id)
            if existing is not None and existing.status == COMMAND_EXECUTION_COMPLETED:
                return existing
            raise RuntimeError(f"Failed to complete command execution: {command_id!r}")
        return _row_to_record(row)

    def delete_execution(self, command_id: str) -> None:
        self._conn.execute(
            text(
                """
                DELETE FROM public.ppr_command_executions
                WHERE command_id = :command_id
                  AND status = :pending_status
                """
            ),
            {"command_id": command_id, "pending_status": COMMAND_EXECUTION_PENDING},
        )
