"""Command idempotency repository contract (R5)."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

COMMAND_EXECUTION_PENDING = "pending"
COMMAND_EXECUTION_COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class CommandExecutionRecord:
    command_id: str
    command_type: str
    person_id: int
    request_fingerprint: str
    status: str
    result_payload: Mapping[str, Any]
    created_at: datetime
    completed_at: datetime | None = None


class CommandIdempotencyRepository(Protocol):
    """DB-enforced command_id idempotency — caller owns transaction."""

    def reserve_execution(
        self,
        *,
        command_id: str,
        command_type: str,
        person_id: int,
        request_fingerprint: str,
    ) -> CommandExecutionRecord | None:
        """Insert pending row; return None if command_id already exists."""
        ...

    def load_execution(self, command_id: str) -> CommandExecutionRecord | None:
        ...

    def complete_execution(
        self,
        command_id: str,
        *,
        result_payload: Mapping[str, Any],
    ) -> CommandExecutionRecord:
        ...

    def delete_execution(self, command_id: str) -> None:
        """Remove pending row on rollback cleanup (optional)."""
        ...
