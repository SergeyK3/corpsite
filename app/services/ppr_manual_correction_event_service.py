"""Transactional writer for WP-PPR-MIG-005F-A event and outbox rows."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

EVENT_TYPE = "PPR_SECTION_MANUAL_CORRECTED"
JOB_KIND_TARGETED_RECALCULATE = "TARGETED_RECALCULATE"


class ManualCorrectionIdempotencyConflictError(ValueError):
    """A reused idempotency key identifies different immutable correction data."""


@dataclass(frozen=True)
class ManualCorrectionAppend:
    idempotency_key: UUID
    actor_user_id: int
    person_id: int
    employee_context_id: int | None
    universe_id: int
    cohort_run_id: int
    section_code: str
    origin_status: str
    origin_reason_code: str
    before_source_fingerprint: str
    before_target_fingerprint: str
    before_binding_fingerprint: str
    after_source_fingerprint: str
    after_target_fingerprint: str
    after_binding_fingerprint: str
    policy_version: str
    optimistic_version: int
    occurred_at: datetime
    stage_run_id: int | None = None
    stage1_run_id: int | None = None
    stage_participant_id: int | None = None
    stage1_participant_id: int | None = None
    pmf_run_id: int | None = None
    pmf_item_id: int | None = None
    evidence_event_id: int | None = None
    job_kind: str = JOB_KIND_TARGETED_RECALCULATE


def _event_comparison(row: dict[str, Any]) -> dict[str, Any]:
    ignored = {"event_id", "event_type", "recorded_at"}
    return {key: value for key, value in row.items() if key not in ignored}


def _request_comparison(request: ManualCorrectionAppend) -> dict[str, Any]:
    value = asdict(request)
    value.pop("job_kind")
    return value


def append_correction_event_and_outbox(conn: Connection, *, request: ManualCorrectionAppend) -> dict[str, int]:
    """Append durable event + job in the caller's transaction; never commits."""
    params = asdict(request)
    inserted = conn.execute(text("""
      INSERT INTO public.ppr_section_manual_correction_events(
        event_type,idempotency_key,actor_user_id,person_id,employee_context_id,universe_id,cohort_run_id,
        section_code,origin_status,origin_reason_code,stage_run_id,stage1_run_id,stage_participant_id,
        stage1_participant_id,pmf_run_id,pmf_item_id,evidence_event_id,before_source_fingerprint,
        before_target_fingerprint,before_binding_fingerprint,after_source_fingerprint,after_target_fingerprint,
        after_binding_fingerprint,policy_version,optimistic_version,occurred_at
      ) VALUES(
        :event_type,:idempotency_key,:actor_user_id,:person_id,:employee_context_id,:universe_id,:cohort_run_id,
        :section_code,:origin_status,:origin_reason_code,:stage_run_id,:stage1_run_id,:stage_participant_id,
        :stage1_participant_id,:pmf_run_id,:pmf_item_id,:evidence_event_id,:before_source_fingerprint,
        :before_target_fingerprint,:before_binding_fingerprint,:after_source_fingerprint,:after_target_fingerprint,
        :after_binding_fingerprint,:policy_version,:optimistic_version,:occurred_at
      ) ON CONFLICT (idempotency_key) DO NOTHING RETURNING event_id
    """), {**params, "event_type": EVENT_TYPE}).scalar_one_or_none()
    if inserted is None:
        existing = conn.execute(text("""
          SELECT event_id,idempotency_key,actor_user_id,person_id,employee_context_id,universe_id,cohort_run_id,
            section_code,origin_status,origin_reason_code,stage_run_id,stage1_run_id,stage_participant_id,
            stage1_participant_id,pmf_run_id,pmf_item_id,evidence_event_id,before_source_fingerprint,
            before_target_fingerprint,before_binding_fingerprint,after_source_fingerprint,after_target_fingerprint,
            after_binding_fingerprint,policy_version,optimistic_version,occurred_at
          FROM public.ppr_section_manual_correction_events WHERE idempotency_key=:id FOR SHARE
        """), {"id": request.idempotency_key}).mappings().one()
        if _event_comparison(dict(existing)) != _request_comparison(request):
            raise ManualCorrectionIdempotencyConflictError("PPR_MANUAL_CORRECTION_IDEMPOTENCY_CONFLICT")
        event_id = int(existing["event_id"])
    else:
        event_id = int(inserted)
    outbox_key = request.idempotency_key
    outbox_id = conn.execute(text("""
      INSERT INTO public.ppr_migration_projection_outbox(
        event_id,idempotency_key,universe_id,person_id,section_code,job_kind
      ) VALUES(:event_id,:idempotency_key,:universe_id,:person_id,:section_code,:job_kind)
      ON CONFLICT (event_id) DO NOTHING RETURNING outbox_id
    """), {"event_id": event_id, "idempotency_key": outbox_key, "universe_id": request.universe_id,
          "person_id": request.person_id, "section_code": request.section_code, "job_kind": request.job_kind}).scalar_one_or_none()
    if outbox_id is None:
        existing_outbox = conn.execute(text("""
          SELECT outbox_id,job_kind FROM public.ppr_migration_projection_outbox
          WHERE event_id=:event_id FOR SHARE
        """), {"event_id": event_id}).mappings().one()
        if existing_outbox["job_kind"] != request.job_kind:
            raise ManualCorrectionIdempotencyConflictError("PPR_MANUAL_CORRECTION_IDEMPOTENCY_CONFLICT")
        outbox_id = existing_outbox["outbox_id"]
    return {"event_id": event_id, "outbox_id": int(outbox_id)}
