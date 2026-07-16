"""Shared helpers for demo PPR section rollback via application layer."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.ppr.application.command_models import PprCommandEnvelope

DEMO_ROLLBACK_REASON = "demo pipeline rollback"


@dataclass(frozen=True, slots=True)
class DemoSectionRecordRef:
    person_id: int
    record_id: int
    demo_record_key: str
    updated_at: datetime


def load_active_demo_record(
    conn: Connection,
    *,
    table: str,
    id_column: str,
    person_id: int,
    demo_suite: str,
    demo_record_key: str,
) -> DemoSectionRecordRef | None:
    row = conn.execute(
        text(
            f"""
            SELECT
                person_id,
                {id_column} AS record_id,
                metadata->>'demo_record_key' AS demo_record_key,
                updated_at
            FROM public.{table}
            WHERE person_id = :person_id
              AND lifecycle_status = 'active'
              AND metadata->>'demo_suite' = :demo_suite
              AND metadata->>'demo_record_key' = :demo_record_key
            LIMIT 1
            """
        ),
        {
            "person_id": person_id,
            "demo_suite": demo_suite,
            "demo_record_key": demo_record_key,
        },
    ).mappings().first()
    if row is None:
        return None
    return DemoSectionRecordRef(
        person_id=int(row["person_id"]),
        record_id=int(row["record_id"]),
        demo_record_key=str(row["demo_record_key"]),
        updated_at=row["updated_at"],
    )


def build_void_envelope(
    *,
    command_type: str,
    actor_id: str,
    person_id: int,
    record_id: int,
    expected_updated_at: datetime,
    command_prefix: str,
) -> PprCommandEnvelope:
    return PprCommandEnvelope(
        command_id=f"{command_prefix}-{uuid4().hex}",
        command_type=command_type,
        actor_id=actor_id,
        requested_at=datetime.now(UTC),
        payload={
            "record_id": record_id,
            "reason": DEMO_ROLLBACK_REASON,
            "expected_updated_at": expected_updated_at,
        },
        person_id=person_id,
        correlation_id=f"{command_prefix}-{uuid4().hex[:12]}",
    )


def void_record_via_service(
    *,
    void_fn: Callable[[PprCommandEnvelope], Any],
    command_type: str,
    actor_id: str,
    record: DemoSectionRecordRef,
    command_prefix: str,
) -> str:
    envelope = build_void_envelope(
        command_type=command_type,
        actor_id=actor_id,
        person_id=record.person_id,
        record_id=record.record_id,
        expected_updated_at=record.updated_at,
        command_prefix=command_prefix,
    )
    result = void_fn(envelope)
    return str(result.status)
