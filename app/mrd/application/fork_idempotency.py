"""Shared idempotency helpers for MRD fork commands."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from app.mrd.domain.errors import MrdCommandConflictError
from app.mrd.domain.types import MRD_COMMAND_EXECUTION_COMPLETED
from app.mrd.infrastructure.command_idempotency_repository import (
    MrdCommandExecutionRecord,
    SqlAlchemyMrdCommandIdempotencyRepository,
)


def build_request_fingerprint(payload: Mapping[str, Any]) -> str:
    normalized = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def begin_idempotent_command(
    idempotency: SqlAlchemyMrdCommandIdempotencyRepository,
    *,
    command_id: str,
    command_type: str,
    performed_by: int,
    request_fingerprint: str,
) -> MrdCommandExecutionRecord | None:
    """Reserve command_id or return completed record for replay."""
    existing = idempotency.load_execution(command_id)
    if existing is not None:
        if existing.request_fingerprint != request_fingerprint:
            raise MrdCommandConflictError(
                f"command_id {command_id!r} reused with different request fingerprint"
            )
        if existing.status == MRD_COMMAND_EXECUTION_COMPLETED:
            return existing
        raise MrdCommandConflictError(
            f"command_id {command_id!r} is already in progress"
        )

    reserved = idempotency.reserve_execution(
        command_id=command_id,
        command_type=command_type,
        performed_by=performed_by,
        request_fingerprint=request_fingerprint,
    )
    if reserved is None:
        existing = idempotency.load_execution(command_id)
        if existing is None:
            raise MrdCommandConflictError(f"Failed to reserve command_id {command_id!r}")
        if existing.request_fingerprint != request_fingerprint:
            raise MrdCommandConflictError(
                f"command_id {command_id!r} reused with different request fingerprint"
            )
        if existing.status == MRD_COMMAND_EXECUTION_COMPLETED:
            return existing
        raise MrdCommandConflictError(
            f"command_id {command_id!r} is already in progress"
        )
    return None
