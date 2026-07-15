"""Application-layer mutation results (R5)."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

RESULT_STATUS_COMMITTED = "committed"
RESULT_STATUS_IDEMPOTENT_REPLAY = "idempotent_replay"
RESULT_STATUS_ALREADY_MATERIALIZED = "already_materialized"
RESULT_STATUS_NO_OP = "no_op"


@dataclass(frozen=True, slots=True)
class PprApplicationResult:
    command_id: str
    command_type: str
    resolved_person_id: int
    status: str
    envelope_version: int | None = None
    section_record_id: int | None = None
    section_mutation_kind: str | None = None
    event_ids: tuple[int, ...] = ()
    post_commit_warnings: tuple[str, ...] = ()
    correlation_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_completion_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "resolved_person_id": self.resolved_person_id,
            "envelope_version": self.envelope_version,
            "section_record_id": self.section_record_id,
            "section_mutation_kind": self.section_mutation_kind,
            "event_ids": list(self.event_ids),
            "correlation_id": self.correlation_id,
            "extra": dict(self.extra),
        }

    @classmethod
    def from_completion_payload(
        cls,
        *,
        command_id: str,
        command_type: str,
        payload: dict[str, Any],
    ) -> PprApplicationResult:
        event_ids_raw = payload.get("event_ids") or []
        return cls(
            command_id=command_id,
            command_type=command_type,
            resolved_person_id=int(payload["resolved_person_id"]),
            status=str(payload["status"]),
            envelope_version=payload.get("envelope_version"),
            section_record_id=payload.get("section_record_id"),
            section_mutation_kind=payload.get("section_mutation_kind"),
            event_ids=tuple(int(x) for x in event_ids_raw),
            correlation_id=payload.get("correlation_id"),
            extra=dict(payload.get("extra") or {}),
        )


def merge_warnings(
    result: PprApplicationResult,
    warnings: Sequence[str],
) -> PprApplicationResult:
    if not warnings:
        return result
    return PprApplicationResult(
        command_id=result.command_id,
        command_type=result.command_type,
        resolved_person_id=result.resolved_person_id,
        status=result.status,
        envelope_version=result.envelope_version,
        section_record_id=result.section_record_id,
        section_mutation_kind=result.section_mutation_kind,
        event_ids=result.event_ids,
        post_commit_warnings=tuple(result.post_commit_warnings) + tuple(warnings),
        correlation_id=result.correlation_id,
        extra=result.extra,
    )
