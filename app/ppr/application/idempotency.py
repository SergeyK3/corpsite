"""Command idempotency orchestration (R5)."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from app.ppr.application.results import PprApplicationResult, RESULT_STATUS_IDEMPOTENT_REPLAY
from app.ppr.domain.command_idempotency_repositories import (
    COMMAND_EXECUTION_COMPLETED,
    COMMAND_EXECUTION_PENDING,
    CommandIdempotencyRepository,
)
from app.ppr.domain.errors import PprCommandIdConflictError, PprCommandInProgressError


def build_request_fingerprint(*, command_type: str, payload: Mapping[str, Any]) -> str:
    normalized = json.dumps(
        {"command_type": command_type, "payload": payload},
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def begin_idempotent_command(
    repo: CommandIdempotencyRepository,
    *,
    command_id: str,
    command_type: str,
    person_id: int,
    request_fingerprint: str,
) -> PprApplicationResult | None:
    """Reserve command_id or return stored idempotent result."""
    reserved = repo.reserve_execution(
        command_id=command_id,
        command_type=command_type,
        person_id=person_id,
        request_fingerprint=request_fingerprint,
    )
    if reserved is not None:
        return None

    existing = repo.load_execution(command_id)
    if existing is None:
        raise PprCommandInProgressError(f"command_id={command_id!r} reservation race")

    if existing.request_fingerprint != request_fingerprint:
        raise PprCommandIdConflictError(
            f"command_id={command_id!r} reused with different payload fingerprint"
        )
    if existing.command_type != command_type:
        raise PprCommandIdConflictError(
            f"command_id={command_id!r} reused with different command_type"
        )
    if existing.status == COMMAND_EXECUTION_PENDING:
        raise PprCommandInProgressError(f"command_id={command_id!r} is in progress")
    if existing.status == COMMAND_EXECUTION_COMPLETED:
        replay = PprApplicationResult.from_completion_payload(
            command_id=command_id,
            command_type=command_type,
            payload=dict(existing.result_payload),
        )
        return PprApplicationResult(
            command_id=replay.command_id,
            command_type=replay.command_type,
            resolved_person_id=replay.resolved_person_id,
            status=RESULT_STATUS_IDEMPOTENT_REPLAY,
            envelope_version=replay.envelope_version,
            section_record_id=replay.section_record_id,
            section_mutation_kind=replay.section_mutation_kind,
            event_ids=replay.event_ids,
            correlation_id=replay.correlation_id,
            extra=replay.extra,
        )
    raise PprCommandInProgressError(f"command_id={command_id!r} has unknown status")


def complete_idempotent_command(
    repo: CommandIdempotencyRepository,
    *,
    command_id: str,
    result: PprApplicationResult,
) -> None:
    repo.complete_execution(command_id, result_payload=result.to_completion_payload())
