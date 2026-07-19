"""Command idempotency store for MRD fork operations (WP-MRD-003)."""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from app.mrd.domain.errors import MrdCommandConflictError
from app.mrd.domain.types import MRD_COMMAND_EXECUTION_COMPLETED, MRD_COMMAND_EXECUTION_PENDING


@dataclass(frozen=True, slots=True)
class MrdCommandExecutionRecord:
    command_id: str
    command_type: str
    performed_by: int
    request_fingerprint: str
    status: str
    result_payload: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None


def _row_to_record(row: RowMapping) -> MrdCommandExecutionRecord:
    payload = row["result_payload"] or {}
    if not isinstance(payload, dict):
        payload = dict(payload)
    return MrdCommandExecutionRecord(
        command_id=str(row["command_id"]),
        command_type=str(row["command_type"]),
        performed_by=int(row["performed_by"]),
        request_fingerprint=str(row["request_fingerprint"]),
        status=str(row["status"]),
        result_payload=dict(payload),
        created_at=row["created_at"],
        completed_at=row.get("completed_at"),
    )


class SqlAlchemyMrdCommandIdempotencyRepository:
    """MRD command idempotency — caller owns transaction boundaries."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def table_available(self) -> bool:
        row = self._conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'hr_mrd_command_executions'
                LIMIT 1
                """
            )
        ).first()
        return row is not None

    def reserve_execution(
        self,
        *,
        command_id: str,
        command_type: str,
        performed_by: int,
        request_fingerprint: str,
    ) -> MrdCommandExecutionRecord | None:
        row = self._conn.execute(
            text(
                """
                INSERT INTO public.hr_mrd_command_executions (
                    command_id,
                    command_type,
                    performed_by,
                    request_fingerprint,
                    status,
                    result_payload
                )
                VALUES (
                    :command_id,
                    :command_type,
                    :performed_by,
                    :request_fingerprint,
                    :status,
                    CAST(:result_payload AS jsonb)
                )
                ON CONFLICT (command_id) DO NOTHING
                RETURNING
                    command_id,
                    command_type,
                    performed_by,
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
                "performed_by": int(performed_by),
                "request_fingerprint": request_fingerprint,
                "status": MRD_COMMAND_EXECUTION_PENDING,
                "result_payload": json.dumps({}, ensure_ascii=False),
            },
        ).mappings().one_or_none()
        if row is None:
            return None
        return _row_to_record(row)

    def load_execution(self, command_id: str) -> MrdCommandExecutionRecord | None:
        row = self._conn.execute(
            text(
                """
                SELECT
                    command_id,
                    command_type,
                    performed_by,
                    request_fingerprint,
                    status,
                    result_payload,
                    created_at,
                    completed_at
                FROM public.hr_mrd_command_executions
                WHERE command_id = :command_id
                """
            ),
            {"command_id": command_id},
        ).mappings().one_or_none()
        if row is None:
            return None
        return _row_to_record(row)

    def assert_same_fingerprint(
        self,
        existing: MrdCommandExecutionRecord,
        *,
        request_fingerprint: str,
    ) -> None:
        if existing.request_fingerprint != request_fingerprint:
            raise MrdCommandConflictError(
                f"command_id {existing.command_id!r} reused with different request fingerprint"
            )

    def complete_execution(
        self,
        command_id: str,
        *,
        result_payload: Mapping[str, Any],
    ) -> MrdCommandExecutionRecord:
        row = self._conn.execute(
            text(
                """
                UPDATE public.hr_mrd_command_executions
                SET status = :status,
                    result_payload = CAST(:result_payload AS jsonb),
                    completed_at = NOW()
                WHERE command_id = :command_id
                  AND status = :pending_status
                RETURNING
                    command_id,
                    command_type,
                    performed_by,
                    request_fingerprint,
                    status,
                    result_payload,
                    created_at,
                    completed_at
                """
            ),
            {
                "command_id": command_id,
                "status": MRD_COMMAND_EXECUTION_COMPLETED,
                "pending_status": MRD_COMMAND_EXECUTION_PENDING,
                "result_payload": json.dumps(dict(result_payload), ensure_ascii=False, default=str),
            },
        ).mappings().one_or_none()
        if row is None:
            existing = self.load_execution(command_id)
            if existing is not None and existing.status == MRD_COMMAND_EXECUTION_COMPLETED:
                return existing
            raise RuntimeError(f"Failed to complete MRD command execution: {command_id!r}")
        return _row_to_record(row)

    def delete_execution(self, command_id: str) -> None:
        self._conn.execute(
            text(
                """
                DELETE FROM public.hr_mrd_command_executions
                WHERE command_id = :command_id
                  AND status = :pending_status
                """
            ),
            {"command_id": command_id, "pending_status": MRD_COMMAND_EXECUTION_PENDING},
        )
