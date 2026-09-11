"""WP-PPR-MIG-005F-B targeted, idempotent projection outbox worker.

There is deliberately no scheduler or HTTP entry point here.  A future runtime
invokes ``run_outbox_batch``; the worker only reads authoritative facts and
updates the safe projection/outbox operational state.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.services import ppr_migration_status_projection_service as projection

SAFE_ERROR_INTERNAL = "PROJECTOR_INTERNAL"
SAFE_ERROR_LOCK_TIMEOUT = "LOCK_TIMEOUT"


def recover_expired_processing_jobs(conn: Connection, *, lease_seconds: int) -> int:
    """Return expired leases to RETRY without changing their immutable address."""
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be positive")
    return int(conn.execute(text("""
        UPDATE public.ppr_migration_projection_outbox
        SET state_code='RETRY', next_attempt_at=now(), claimed_at=NULL,
            claimed_by=NULL, last_error_code=:error
        WHERE state_code='PROCESSING'
          AND claimed_at < now() - (:seconds * interval '1 second')
    """), {"seconds": lease_seconds, "error": SAFE_ERROR_LOCK_TIMEOUT}).rowcount)


def claim_ready_jobs(conn: Connection, *, worker_id: str, limit: int) -> list[dict[str, Any]]:
    """Claim ready jobs once, using row locks that competing workers skip."""
    if not worker_id.strip() or limit <= 0:
        raise ValueError("worker_id and positive limit are required")
    rows = conn.execute(text("""
        WITH ready AS (
          SELECT outbox_id
          FROM public.ppr_migration_projection_outbox
          WHERE state_code IN ('PENDING','RETRY') AND next_attempt_at <= now()
          ORDER BY next_attempt_at, outbox_id
          FOR UPDATE SKIP LOCKED
          LIMIT :limit
        )
        UPDATE public.ppr_migration_projection_outbox o
        SET state_code='PROCESSING', attempts=o.attempts+1, claimed_at=now(),
            claimed_by=:worker_id, last_error_code=NULL
        FROM ready
        WHERE o.outbox_id=ready.outbox_id
        RETURNING o.outbox_id,o.event_id,o.universe_id,o.person_id,o.section_code,
                  o.job_kind,o.attempts,o.claimed_at,o.claimed_by
    """), {"worker_id": worker_id, "limit": limit}).mappings().all()
    return [dict(row) for row in rows]


def _fact_for_target(conn: Connection, *, universe_id: int, person_id: int, cohort_run_id: int) -> dict[str, Any] | None:
    row = conn.execute(text("""
      SELECT cp.stage0_cohort_run_id,cp.stage0_participant_id,cp.person_id,cp.employee_id,cp.source_row_id,
             e.org_unit_id,e.person_id employee_person_id,e.is_active,e.operational_status,
             p.person_status,p.merged_into_person_id,p.updated_at person_updated_at,
             e.updated_at employee_updated_at,r.normalized_payload source_payload
      FROM public.ppr_migration_status_universe_cohorts uc
      JOIN public.ppr_stage0_cohort_participants cp
        ON cp.stage0_cohort_run_id=uc.stage0_cohort_run_id
      JOIN public.employees e ON e.employee_id=cp.employee_id
      JOIN public.persons p ON p.person_id=cp.person_id
      JOIN public.hr_import_rows r ON r.row_id=cp.source_row_id
      WHERE uc.universe_id=:universe_id AND cp.person_id=:person_id
        AND cp.stage0_cohort_run_id=:cohort_run_id
      FOR SHARE
    """), {"universe_id": universe_id, "person_id": person_id, "cohort_run_id": cohort_run_id}).mappings().one_or_none()
    return dict(row) if row else None


def _latest_event(conn: Connection, *, universe_id: int, person_id: int, section_code: str) -> dict[str, Any] | None:
    row = conn.execute(text("""
      SELECT * FROM public.ppr_section_manual_correction_events
      WHERE universe_id=:universe_id AND person_id=:person_id AND section_code=:section_code
      ORDER BY recorded_at DESC,event_id DESC LIMIT 1
    """), {"universe_id": universe_id, "person_id": person_id, "section_code": section_code}).mappings().one_or_none()
    return dict(row) if row else None


def _event_status(
    *, base: dict[str, Any], event: dict[str, Any], candidate: dict[str, Any] | None,
) -> dict[str, Any]:
    """Apply the approved WP-005A correction branch after safety facts are read."""
    if base["status_code"] == "BLOCKED":
        return base
    for name, reason in (
        ("source", "FINGERPRINT_SOURCE_CHANGED"),
        ("target", "FINGERPRINT_TARGET_CHANGED"),
        ("binding", "FINGERPRINT_BINDING_CHANGED"),
    ):
        if base[f"{name}_fingerprint"] != event[f"after_{name}_fingerprint"]:
            return {**base, "status_code": "STALE", "reason_code": reason}
    current_policy = base.get("policy_version") or event["policy_version"]
    if current_policy != event["policy_version"]:
        return {**base, "status_code": "STALE", "reason_code": "FINGERPRINT_POLICY_CHANGED"}
    # A participant validation/acceptance completed after correction supersedes
    # the interim correction state and is classified by the normal WP-005A tree.
    candidate_times = ((candidate or {}).get("completed_at"), (candidate or {}).get("accepted_at"))
    recheck_at = max((value for value in candidate_times if value is not None), default=None)
    if recheck_at is not None and recheck_at >= event["occurred_at"]:
        return base
    return {**base, "status_code": "CORRECTED_BY_HR", "reason_code": "MANUAL_CORRECTION_PENDING_RECHECK"}


def _upsert_projection(conn: Connection, *, job: dict[str, Any], fact: dict[str, Any], result: dict[str, Any]) -> None:
    values = {
        "universe_id": job["universe_id"], "person_id": job["person_id"],
        "employee_context_id": fact["employee_id"], "org_unit_id": fact["org_unit_id"],
        "section_code": job["section_code"], "source_cohort_run_id": fact["stage0_cohort_run_id"],
        "source_row_id": fact["source_row_id"], **result,
    }
    conn.execute(text("""
      INSERT INTO public.ppr_migration_section_status_projection(
        universe_id,person_id,employee_context_id,org_unit_id,section_code,status_code,reason_code,
        source_cohort_run_id,source_row_id,stage_run_id,stage1_run_id,stage_participant_id,
        stage1_participant_id,pmf_run_id,evidence_kind,policy_version,source_fingerprint,
        target_fingerprint,binding_fingerprint
      ) VALUES(
        :universe_id,:person_id,:employee_context_id,:org_unit_id,:section_code,:status_code,:reason_code,
        :source_cohort_run_id,:source_row_id,:stage_run_id,:stage1_run_id,:stage_participant_id,
        :stage1_participant_id,:pmf_run_id,:evidence_kind,:policy_version,:source_fingerprint,
        :target_fingerprint,:binding_fingerprint
      ) ON CONFLICT(universe_id,person_id,section_code) DO UPDATE SET
        employee_context_id=EXCLUDED.employee_context_id, org_unit_id=EXCLUDED.org_unit_id,
        status_code=EXCLUDED.status_code, reason_code=EXCLUDED.reason_code,
        source_cohort_run_id=EXCLUDED.source_cohort_run_id, source_row_id=EXCLUDED.source_row_id,
        stage_run_id=EXCLUDED.stage_run_id, stage1_run_id=EXCLUDED.stage1_run_id,
        stage_participant_id=EXCLUDED.stage_participant_id,
        stage1_participant_id=EXCLUDED.stage1_participant_id, pmf_run_id=EXCLUDED.pmf_run_id,
        evidence_kind=EXCLUDED.evidence_kind, policy_version=EXCLUDED.policy_version,
        source_fingerprint=EXCLUDED.source_fingerprint, target_fingerprint=EXCLUDED.target_fingerprint,
        binding_fingerprint=EXCLUDED.binding_fingerprint, calculated_at=now(),
        row_version=public.ppr_migration_section_status_projection.row_version+1
      WHERE ROW(
        public.ppr_migration_section_status_projection.employee_context_id,
        public.ppr_migration_section_status_projection.org_unit_id,
        public.ppr_migration_section_status_projection.status_code,
        public.ppr_migration_section_status_projection.reason_code,
        public.ppr_migration_section_status_projection.source_cohort_run_id,
        public.ppr_migration_section_status_projection.source_row_id,
        public.ppr_migration_section_status_projection.stage_run_id,
        public.ppr_migration_section_status_projection.stage1_run_id,
        public.ppr_migration_section_status_projection.stage_participant_id,
        public.ppr_migration_section_status_projection.stage1_participant_id,
        public.ppr_migration_section_status_projection.pmf_run_id,
        public.ppr_migration_section_status_projection.evidence_kind,
        public.ppr_migration_section_status_projection.policy_version,
        public.ppr_migration_section_status_projection.source_fingerprint,
        public.ppr_migration_section_status_projection.target_fingerprint,
        public.ppr_migration_section_status_projection.binding_fingerprint
      ) IS DISTINCT FROM ROW(
        EXCLUDED.employee_context_id,EXCLUDED.org_unit_id,EXCLUDED.status_code,EXCLUDED.reason_code,
        EXCLUDED.source_cohort_run_id,EXCLUDED.source_row_id,EXCLUDED.stage_run_id,EXCLUDED.stage1_run_id,
        EXCLUDED.stage_participant_id,EXCLUDED.stage1_participant_id,EXCLUDED.pmf_run_id,
        EXCLUDED.evidence_kind,EXCLUDED.policy_version,EXCLUDED.source_fingerprint,
        EXCLUDED.target_fingerprint,EXCLUDED.binding_fingerprint
      )
    """), values)


def project_targeted_cell(conn: Connection, *, job: dict[str, Any]) -> None:
    """Rebuild exactly one addressed cell; a newer correction makes this job stale."""
    event = conn.execute(text("""
      SELECT * FROM public.ppr_section_manual_correction_events WHERE event_id=:event_id FOR SHARE
    """), {"event_id": job["event_id"]}).mappings().one()
    event = dict(event)
    newest = _latest_event(conn, universe_id=job["universe_id"], person_id=job["person_id"], section_code=job["section_code"])
    if newest is not None and newest["event_id"] != event["event_id"]:
        return
    fact = _fact_for_target(conn, universe_id=job["universe_id"], person_id=job["person_id"], cohort_run_id=event["cohort_run_id"])
    if fact is None:
        # Active-universe membership is authoritative: no synthetic cell remains.
        conn.execute(text("""DELETE FROM public.ppr_migration_section_status_projection
          WHERE universe_id=:u AND person_id=:p AND section_code=:s"""),
          {"u": job["universe_id"], "p": job["person_id"], "s": job["section_code"]})
        return
    previous = conn.execute(text("""SELECT status_code,source_fingerprint,target_fingerprint,
      binding_fingerprint,policy_version FROM public.ppr_migration_section_status_projection
      WHERE universe_id=:u AND person_id=:p AND section_code=:s FOR UPDATE"""),
      {"u": job["universe_id"], "p": job["person_id"], "s": job["section_code"]}).mappings().one_or_none()
    candidate = projection._candidate(conn, fact, job["section_code"])
    base = projection._status(conn, fact, job["section_code"], candidate, dict(previous) if previous else None)
    result = _event_status(base=base, event=event, candidate=candidate)
    _upsert_projection(conn, job=job, fact=fact, result=result)


def _complete_or_retry(
    conn: Connection, *, job: dict[str, Any], worker_id: str, error_code: str | None,
    max_attempts: int, retry_delay_seconds: int,
) -> str:
    is_dead = error_code is not None and int(job["attempts"]) >= max_attempts
    if error_code is None:
        state = "COMPLETED"
    elif is_dead:
        state = "DEAD"
    else:
        state = "RETRY"
    conn.execute(text("""
      UPDATE public.ppr_migration_projection_outbox
      SET state_code=:state, processed_at=CASE WHEN :terminal THEN now() ELSE NULL END,
          next_attempt_at=CASE WHEN :terminal THEN next_attempt_at ELSE now() + (:delay * interval '1 second') END,
          claimed_at=CASE WHEN :terminal THEN claimed_at ELSE NULL END,
          claimed_by=CASE WHEN :terminal THEN claimed_by ELSE NULL END,
          last_error_code=:error
      WHERE outbox_id=:outbox_id AND state_code='PROCESSING' AND claimed_by=:worker_id
    """), {"state": state, "terminal": state in ("COMPLETED", "DEAD"), "delay": retry_delay_seconds,
            "error": error_code, "outbox_id": job["outbox_id"], "worker_id": worker_id})
    return state


def run_outbox_batch(
    engine: Engine, *, worker_id: str, limit: int = 50, max_attempts: int = 3,
    lease_seconds: int = 300, retry_delay_seconds: int = 30,
    projector: Callable[[Connection], None] | None = None,
) -> dict[str, int]:
    """Claim and process one finite batch. The caller/scheduler owns repetition."""
    if max_attempts <= 0 or retry_delay_seconds < 0:
        raise ValueError("invalid worker retry configuration")
    with engine.begin() as conn:
        recovered = recover_expired_processing_jobs(conn, lease_seconds=lease_seconds)
        jobs = claim_ready_jobs(conn, worker_id=worker_id, limit=limit)
    counts = {"claimed": len(jobs), "completed": 0, "retry": 0, "dead": 0, "recovered": recovered}
    for job in jobs:
        try:
            with engine.begin() as conn:
                if projector is None:
                    project_targeted_cell(conn, job=job)
                else:
                    projector(conn)
                state = _complete_or_retry(conn, job=job, worker_id=worker_id, error_code=None,
                                           max_attempts=max_attempts, retry_delay_seconds=retry_delay_seconds)
        except Exception:
            with engine.begin() as conn:
                state = _complete_or_retry(conn, job=job, worker_id=worker_id, error_code=SAFE_ERROR_INTERNAL,
                                           max_attempts=max_attempts, retry_delay_seconds=retry_delay_seconds)
        counts[state.lower()] += 1
    return counts
