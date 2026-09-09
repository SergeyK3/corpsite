"""Stage 2 education envelope over PMF drafts.

The envelope deliberately persists only technical anchors and hashes.  Fragment payload
lives in existing normalized records until execution, then in PMF draft items.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.ppr_migration.education_kind_policy import POLICY_VERSION, REVIEW_REQUIRED, classify_education_kind
from app.ppr.application.config import ppr_pmf_bridge_enabled
from app.services.personnel_migration_commit_service import add_draft_item, commit_run, create_draft_run


class Stage2Error(RuntimeError):
    code = "STAGE2_ERROR"
class Stage2NotFoundError(Stage2Error):
    code = "STAGE2_RUN_NOT_FOUND"
class Stage2ConflictError(Stage2Error):
    code = "STAGE2_CONFLICT"
class Stage2ValidationError(Stage2Error):
    code = "STAGE2_VALIDATION"


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _key(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _safe_error(exc: Exception) -> tuple[str, str]:
    code = getattr(exc, "code", "STAGE2_EXECUTION_ERROR")
    return str(code)[:120], _hash({"code": str(code), "type": type(exc).__name__})


def _normalize(value: Any) -> str | None:
    result = " ".join(str(value or "").strip().split())
    return result or None


def _run(conn: Connection, run_id: int, *, lock: bool = False) -> dict[str, Any]:
    row = conn.execute(text(f"SELECT * FROM public.ppr_stage_runs WHERE stage_run_id=:id{' FOR UPDATE' if lock else ''}"), {"id": run_id}).mappings().one_or_none()
    if row is None:
        raise Stage2NotFoundError("STAGE2_RUN_NOT_FOUND")
    return dict(row)


def _participant_rows(conn: Connection, run_id: int, *, lock: bool = False) -> list[dict[str, Any]]:
    return [dict(x) for x in conn.execute(text(f"SELECT * FROM public.ppr_stage_run_participants WHERE stage_run_id=:id ORDER BY position{' FOR UPDATE' if lock else ''}"), {"id": run_id}).mappings()]


def _fragments(conn: Connection, participant: dict[str, Any], *, lock: bool = False) -> list[dict[str, Any]]:
    # ``hr_import_rows`` is a nullable outer-join side.  PostgreSQL forbids a
    # blanket FOR UPDATE there; the normalized source rows are the lock target.
    suffix = " FOR UPDATE OF nr" if lock else ""
    rows = conn.execute(text(f"""
        SELECT nr.normalized_record_id,nr.batch_id,nr.row_id,nr.employee_id,nr.fragment_index,
               nr.source_field,nr.source_record_key,nr.record_kind,nr.title,nr.source_text,
               nr.specialty_text,nr.document_number,nr.start_date,nr.end_date,nr.issue_date,
               nr.parse_method,nr.confidence,nr.review_status,nr.promoted_document_id,nr.updated_at,
               r.source_row_number
          FROM public.ppr_stage0_cohort_participants s
          JOIN public.hr_import_normalized_records nr ON nr.row_id=s.source_row_id
         LEFT JOIN public.hr_import_rows r ON r.row_id=nr.row_id
         WHERE s.stage0_participant_id=:stage0
           AND nr.employee_id=:employee AND nr.record_kind='education'
         ORDER BY nr.normalized_record_id{suffix}
    """), {"stage0": participant["stage0_participant_id"], "employee": participant["employee_id"]}).mappings().all()
    return [dict(x) for x in rows]


def _canonical(conn: Connection, person_id: int, *, lock: bool = False) -> list[dict[str, Any]]:
    return [dict(x) for x in conn.execute(text(f"""
        SELECT education_id,education_kind,institution_name,specialty,qualification,completed_at,
               diploma_number,import_batch_id,import_row_id,metadata,updated_at
          FROM public.person_education
         WHERE person_id=:person AND lifecycle_status='active'
         ORDER BY education_id{' FOR UPDATE' if lock else ''}
    """), {"person": person_id}).mappings()]


def _fragment_view(fragment: dict[str, Any], canon: list[dict[str, Any]], *, stage_run_id: int, participant_id: int, version: int) -> dict[str, Any]:
    title = _normalize(fragment.get("title")) or _normalize(fragment.get("source_text"))
    classification = classify_education_kind(title, fragment.get("source_text"), fragment.get("specialty_text"))
    proposal = {
        "education_kind": classification.kind,
        "institution_name": title,
        "specialty": _normalize(fragment.get("specialty_text")),
        "qualification": None,
        "completed_at": str(fragment["end_date"] or fragment["issue_date"] or "") or None,
        "diploma_number": _normalize(fragment.get("document_number")),
    }
    source_key = str(fragment["source_record_key"])
    item_key = _key(f"stage2-pmf-item:v1:{stage_run_id}:{participant_id}:{version}:{source_key}:{fragment['fragment_index']}")
    source = {"source_row_number": fragment.get("source_row_number"), "fragment_index": int(fragment["fragment_index"]), "institution_name": title, "specialty": proposal["specialty"], "completed_at": proposal["completed_at"]}
    current: dict[str, Any] | None = None
    outcome, reason = classification.outcome, classification.reason_code
    identity = (classification.kind, (title or "").casefold())
    matches = [x for x in canon if (x["education_kind"], (_normalize(x["institution_name"]) or "").casefold()) == identity]
    if classification.outcome != REVIEW_REQUIRED and fragment["review_status"] not in {"approved", "promoted"}:
        outcome, reason = REVIEW_REQUIRED, "STAGE2_SOURCE_REVIEW_STATUS"
    elif classification.outcome != REVIEW_REQUIRED and len(matches) > 1:
        outcome, reason = "CANONICAL_CONFLICT", "STAGE2_AMBIGUOUS_CANONICAL_MATCH"
    elif classification.outcome != REVIEW_REQUIRED and len(matches) == 1:
        current = {k: matches[0].get(k) for k in ("education_kind","institution_name","specialty","qualification","completed_at","diploma_number")}
        meta = dict(matches[0].get("metadata") or {}).get("stage2") or {}
        same = all((_normalize(current.get(k)) or None) == (_normalize(proposal.get(k)) or None) for k in proposal)
        provenance = (matches[0].get("import_batch_id") == fragment.get("batch_id") and matches[0].get("import_row_id") == fragment.get("row_id") and meta.get("source_record_key") == source_key and meta.get("fragment_index") == int(fragment["fragment_index"]) and meta.get("policy_version") == POLICY_VERSION and meta.get("item_key") == item_key)
        if same and provenance:
            outcome, reason = "ALREADY_APPLIED", "STAGE2_EXACT_PROVENANCE_MATCH"
        else:
            outcome, reason = "CANONICAL_CONFLICT", "STAGE2_CANONICAL_VALUE_CONFLICT"
    if fragment.get("promoted_document_id") and outcome != "ALREADY_APPLIED":
        outcome, reason = REVIEW_REQUIRED, "STAGE2_PROMOTED_MATCH_NOT_EXACT"
    return {"normalized_record_id": int(fragment["normalized_record_id"]), "import_batch_id": int(fragment["batch_id"]), "import_row_id": int(fragment["row_id"]), "source_record_key": source_key, "fragment_index": int(fragment["fragment_index"]), "source": source, "current": current or {}, "proposal": proposal, "outcome": outcome, "reason_code": reason, "item_key": item_key, "source_fingerprint": _hash({"id":fragment["normalized_record_id"],"updated":fragment["updated_at"],"outcome":outcome,"proposal":proposal})}


def _derive(conn: Connection, participant: dict[str, Any], *, stage_run_id: int, lock: bool = False) -> dict[str, Any]:
    state = conn.execute(text(f"""
      SELECT e.employee_id,e.person_id employee_person_id,e.is_active,e.operational_status,
             p.person_id,p.updated_at person_updated_at
        FROM public.employees e JOIN public.persons p ON p.person_id=:person
       WHERE e.employee_id=:employee{' FOR UPDATE' if lock else ''}
    """), {"employee": participant["employee_id"], "person": participant["person_id"]}).mappings().one_or_none()
    if state is None or not state["is_active"] or state["operational_status"] != "active" or int(state["employee_person_id"]) != int(participant["person_id"]):
        raise Stage2ConflictError("STAGE2_EMPLOYEE_PERSON_LINK_STALE")
    fragments = _fragments(conn, participant, lock=lock)
    canon = _canonical(conn, int(participant["person_id"]), lock=lock)
    views = [_fragment_view(x, canon, stage_run_id=stage_run_id, participant_id=int(participant.get("stage_run_participant_id") or 0), version=int(participant.get("participant_snapshot_version") or 1)) for x in fragments]
    if not views:
        views = [{"outcome": REVIEW_REQUIRED, "reason_code": "STAGE2_EDUCATION_SOURCE_MISSING", "source": {}, "current": {}, "proposal": {}, "source_fingerprint": _hash({"missing":True}), "fragment_index": 0, "source_record_key": "", "normalized_record_id": 0, "item_key": ""}]
    fpr = _hash({"employee":participant["employee_id"],"person":participant["person_id"],"fragments":[{"id":x["normalized_record_id"],"f":x["source_fingerprint"]} for x in views], "person_updated":state["person_updated_at"],"policy":POLICY_VERSION})
    return {"fragments": views, "fingerprint": fpr}


def _view_run(conn: Connection, run_id: int) -> dict[str, Any]:
    run = _run(conn, run_id)
    participants = _participant_rows(conn, run_id)
    for p in participants:
        d = _derive(conn, p, stage_run_id=run_id)
        p["fragments"] = d["fragments"]
    return {"run": run, "participants": participants, "counts": dict(Counter(x["status"] for x in participants))}


def compute_preview_stage2(conn: Connection, *, stage0_cohort_run_id: int) -> dict[str, Any]:
    """Read-only half of PREVIEW.

    The caller owns a REPEATABLE READ, READ ONLY transaction.  This function
    deliberately does not touch envelope or PMF tables.
    """
    cohort = [dict(x) for x in conn.execute(text("SELECT * FROM public.ppr_stage0_cohort_participants WHERE stage0_cohort_run_id=:id ORDER BY position"), {"id":stage0_cohort_run_id}).mappings()]
    if not cohort:
        raise Stage2ValidationError("STAGE2_COHORT_EMPTY_OR_NOT_FOUND")
    provisional = [{"stage0_participant_id":p["stage0_participant_id"],"employee_id":p["employee_id"],"person_id":p["person_id"],"participant_snapshot_version":1} for p in cohort]
    fingerprint = _hash({"cohort":stage0_cohort_run_id,"policy":POLICY_VERSION,"participants":[{"id":p["stage0_participant_id"],"fingerprint":_derive(conn,p,stage_run_id=0)["fingerprint"]} for p in provisional]})
    return {"stage0_cohort_run_id": stage0_cohort_run_id, "preview_fingerprint": fingerprint, "participant_count": len(cohort)}


def persist_preview_stage2(conn: Connection, *, stage0_cohort_run_id: int, actor_user_id: int, expected_preview_fingerprint: str) -> dict[str, Any]:
    """Short serializable write half of PREVIEW.

    The advisory lock serialises competing freezes of the same Stage 0 cohort;
    recalculation under that lock makes a stale browser preview fail closed.
    """
    conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key":f"PPR_STAGE2:{stage0_cohort_run_id}"})
    try:
        computed = compute_preview_stage2(conn, stage0_cohort_run_id=stage0_cohort_run_id)
    except Stage2ConflictError as exc:
        raise Stage2ConflictError("STAGE2_PREVIEW_STALE") from exc
    fingerprint = computed["preview_fingerprint"]
    if fingerprint != expected_preview_fingerprint:
        raise Stage2ConflictError("STAGE2_PREVIEW_STALE")
    cohort = [dict(x) for x in conn.execute(text("SELECT * FROM public.ppr_stage0_cohort_participants WHERE stage0_cohort_run_id=:id ORDER BY position FOR UPDATE"), {"id":stage0_cohort_run_id}).mappings()]
    existing = conn.execute(text("SELECT stage_run_id FROM public.ppr_stage_runs WHERE stage_code='education' AND stage0_cohort_run_id=:cohort AND preview_fingerprint=:f"), {"cohort":stage0_cohort_run_id,"f":fingerprint}).scalar_one_or_none()
    if existing:
        return _view_run(conn, int(existing))
    run_id = conn.execute(text("""INSERT INTO public.ppr_stage_runs(stage_code,stage0_cohort_run_id,status,preview_fingerprint,policy_version,current_position,safe_snapshot,created_by_user_id)
      VALUES('education',:cohort,'DRY_RUN_COMPLETED',:fingerprint,:policy,1,'{}'::jsonb,:actor) RETURNING stage_run_id"""), {"cohort":stage0_cohort_run_id,"fingerprint":fingerprint,"policy":POLICY_VERSION,"actor":actor_user_id}).scalar_one()
    for p in cohort:
        d = _derive(conn,{**p,"participant_snapshot_version":1},stage_run_id=int(run_id))
        conn.execute(text("""INSERT INTO public.ppr_stage_run_participants(stage_run_id,stage0_participant_id,position,employee_id,person_id,participant_snapshot_version,safe_fingerprint,status)
          VALUES(:run,:stage0,:position,:employee,:person,1,:fingerprint,'PENDING')"""), {"run":run_id,"stage0":p["stage0_participant_id"],"position":p["position"],"employee":p["employee_id"],"person":p["person_id"],"fingerprint":d["fingerprint"]})
    return _view_run(conn, int(run_id))


def preview_stage2(conn: Connection, *, stage0_cohort_run_id: int, actor_user_id: int) -> dict[str, Any]:
    """Compatibility entry point for service callers already in a write UoW."""
    preview = compute_preview_stage2(conn, stage0_cohort_run_id=stage0_cohort_run_id)
    return persist_preview_stage2(conn, stage0_cohort_run_id=stage0_cohort_run_id, actor_user_id=actor_user_id, expected_preview_fingerprint=preview["preview_fingerprint"])


def approve_stage2(conn: Connection, *, run_id: int, actor_user_id: int) -> dict[str, Any]:
    run = _run(conn, run_id, lock=True)
    if run["status"] == "APPROVED":
        return _view_run(conn, run_id)
    if run["status"] != "DRY_RUN_COMPLETED":
        raise Stage2ConflictError("STAGE2_INVALID_STATE")
    blocked = []
    for p in _participant_rows(conn, run_id, lock=True):
        if p["status"] == "SKIPPED_BY_DECISION":
            continue
        d = _derive(conn,p,stage_run_id=run_id,lock=True)
        if d["fingerprint"] != p["safe_fingerprint"] or any(f["outcome"] in {REVIEW_REQUIRED,"CANONICAL_CONFLICT"} for f in d["fragments"]):
            blocked.append(p["stage_run_participant_id"])
    if blocked:
        raise Stage2ConflictError("STAGE2_APPROVAL_BLOCKED")
    conn.execute(text("UPDATE public.ppr_stage_runs SET status='APPROVED',approved_by_user_id=:actor,approved_at=now() WHERE stage_run_id=:id"), {"id":run_id,"actor":actor_user_id})
    return _view_run(conn, run_id)


def _pause_execution(conn: Connection, run_id: int, participant_id: int, exc: Exception) -> None:
    code, ref = _safe_error(exc)
    conn.execute(text("""UPDATE public.ppr_stage_run_participants SET status='ERROR',error_code=:code,error_reference=:ref,errored_at=now(),completed_at=NULL WHERE stage_run_participant_id=:p AND status IN ('PENDING','ERROR')"""), {"p":participant_id,"code":code,"ref":ref})
    conn.execute(text("""UPDATE public.ppr_stage_runs SET status='PAUSED_ON_ERROR',paused_operation='PARTICIPANT_EXECUTION',stopped_participant_id=:p,paused_at=now(),last_error_code=:code,last_error_reference=:ref WHERE stage_run_id=:id AND status IN ('APPROVED','RUNNING')"""), {"id":run_id,"p":participant_id,"code":code,"ref":ref})


def execute_next_stage2(conn: Connection, *, run_id: int, actor_user_id: int, resume: bool = False) -> dict[str, Any]:
    run = _run(conn, run_id, lock=True)
    if resume:
        if run["status"] != "PAUSED_ON_ERROR" or run["paused_operation"] != "PARTICIPANT_EXECUTION":
            raise Stage2ConflictError("STAGE2_RUN_NOT_RESUMABLE")
        position = conn.execute(text("SELECT position FROM public.ppr_stage_run_participants WHERE stage_run_participant_id=:id FOR UPDATE"),{"id":run["stopped_participant_id"]}).scalar_one()
        conn.execute(text("UPDATE public.ppr_stage_runs SET status='RUNNING',paused_operation=NULL,stopped_participant_id=NULL,paused_at=NULL,last_error_code=NULL,last_error_reference=NULL WHERE stage_run_id=:id"),{"id":run_id})
    elif run["status"] in {"APPROVED","RUNNING"}:
        position = run["current_position"]
    else:
        raise Stage2ConflictError("STAGE2_RUN_PAUSED" if run["status"]=="PAUSED_ON_ERROR" else "STAGE2_INVALID_STATE")
    p = conn.execute(text("""SELECT * FROM public.ppr_stage_run_participants WHERE stage_run_id=:run AND position>=:pos AND status IN ('PENDING','ERROR') ORDER BY position LIMIT 1 FOR UPDATE"""),{"run":run_id,"pos":position}).mappings().one_or_none()
    if p is None:
        conn.execute(text("UPDATE public.ppr_stage_runs SET status='COMPLETED_PENDING_REVIEW' WHERE stage_run_id=:id"),{"id":run_id})
        return _view_run(conn,run_id)
    p=dict(p)
    try:
        d=_derive(conn,p,stage_run_id=run_id,lock=True)
        if d["fingerprint"] != p["safe_fingerprint"]:
            raise Stage2ConflictError("STAGE2_RESUME_STALE")
        if any(f["outcome"] in {REVIEW_REQUIRED,"CANONICAL_CONFLICT"} for f in d["fragments"]):
            raise Stage2ConflictError("STAGE2_FRAGMENT_REVIEW_REQUIRED")
        ready=[f for f in d["fragments"] if f["outcome"]=="READY_TO_ADD"]
        pmf_id=p.get("pmf_run_id")
        if ready and not pmf_id:
            run_key=_key(f"stage2-pmf-run:v1:{run_id}:{p['stage_run_participant_id']}:{p['participant_snapshot_version']}")
            pmf=create_draft_run(conn,domain_code="education",employee_context_id=int(p["employee_id"]),actor_id=str(actor_user_id),metadata={"stage2":{"envelope_run_id":run_id,"participant_id":p["stage_run_participant_id"],"participant_snapshot_version":p["participant_snapshot_version"],"policy_version":POLICY_VERSION,"deterministic_run_key":run_key}})
            pmf_id=int(pmf["run_id"])
            for f in ready:
                payload={**f["proposal"],"employee_context_id":int(p["employee_id"]),"source_field":"education_raw","source_text":None,"parse_method":"stage2_v1","confidence":None,"metadata":{"stage2":{"envelope_run_id":run_id,"participant_id":p["stage_run_participant_id"],"participant_snapshot_version":p["participant_snapshot_version"],"source_record_key":f["source_record_key"],"fragment_index":f["fragment_index"],"policy_version":POLICY_VERSION,"item_key":f["item_key"]}}}
                add_draft_item(conn,run_id=pmf_id,source_kind="stage2_control_list_fragment",source_record_id=f["item_key"],import_batch_id=f["import_batch_id"],import_row_id=f["import_row_id"],record_kind="education",draft_payload=payload,source_payload={"stage2":{"source_record_key":f["source_record_key"],"fragment_index":f["fragment_index"],"item_key":f["item_key"],"classification_outcome":f["outcome"],"policy_version":POLICY_VERSION,"source_snapshot_fingerprint":f["source_fingerprint"]}})
        conn.execute(text("""UPDATE public.ppr_stage_run_participants SET status='COMPLETED',pmf_run_id=COALESCE(pmf_run_id,:pmf),completed_at=now(),error_code=NULL,error_reference=NULL,errored_at=NULL WHERE stage_run_participant_id=:id"""),{"id":p["stage_run_participant_id"],"pmf":pmf_id})
        conn.execute(text("UPDATE public.ppr_stage_runs SET status='RUNNING',current_position=:next WHERE stage_run_id=:id"),{"id":run_id,"next":int(p["position"])+1})
    except Exception as exc:
        _pause_execution(conn,run_id,int(p["stage_run_participant_id"]),exc)
    return _view_run(conn,run_id)


def skip_stage2_participant(conn: Connection, *, run_id: int, participant_id: int, actor_user_id: int, reason: str) -> dict[str, Any]:
    run=_run(conn,run_id,lock=True); p=conn.execute(text("SELECT * FROM public.ppr_stage_run_participants WHERE stage_run_participant_id=:id AND stage_run_id=:run FOR UPDATE"),{"id":participant_id,"run":run_id}).mappings().one_or_none()
    if p is None or p["status"] not in {"PENDING","ERROR"} or not str(reason).strip() or run["status"] not in {"DRY_RUN_COMPLETED","PAUSED_ON_ERROR"} or (run["status"]=="PAUSED_ON_ERROR" and (run["paused_operation"]!="PARTICIPANT_EXECUTION" or run["stopped_participant_id"]!=participant_id)):
        raise Stage2ConflictError("STAGE2_SKIP_NOT_ALLOWED")
    conn.execute(text("UPDATE public.ppr_stage_run_participants SET status='SKIPPED_BY_DECISION',skipped_by_user_id=:actor,skipped_at=now(),skip_reason=:reason,error_code=NULL,error_reference=NULL,errored_at=NULL WHERE stage_run_participant_id=:id"),{"id":participant_id,"actor":actor_user_id,"reason":str(reason).strip()})
    if run["status"]=="PAUSED_ON_ERROR":
        conn.execute(text("UPDATE public.ppr_stage_runs SET status='APPROVED',current_position=(SELECT position+1 FROM public.ppr_stage_run_participants WHERE stage_run_participant_id=:p),paused_operation=NULL,stopped_participant_id=NULL,paused_at=NULL,last_error_code=NULL,last_error_reference=NULL WHERE stage_run_id=:id"),{"id":run_id,"p":participant_id})
    return _view_run(conn,run_id)


def cancel_stage2(conn: Connection, *, run_id:int, actor_user_id:int, reason:str)->dict[str,Any]:
    run=_run(conn,run_id,lock=True)
    if run["status"]=="CANCELLED": return _view_run(conn,run_id)
    if run["status"] not in {"DRY_RUN_COMPLETED","APPROVED","RUNNING","PAUSED_ON_ERROR","COMPLETED_PENDING_REVIEW"} or not str(reason).strip(): raise Stage2ConflictError("STAGE2_INVALID_STATE")
    conn.execute(text("UPDATE public.ppr_stage_runs SET status='CANCELLED',cancelled_by_user_id=:actor,cancelled_at=now(),cancel_reason=:reason,paused_operation=NULL,stopped_participant_id=NULL,paused_at=NULL,last_error_code=NULL,last_error_reference=NULL WHERE stage_run_id=:id"),{"id":run_id,"actor":actor_user_id,"reason":str(reason).strip()})
    return _view_run(conn,run_id)


def acceptance_summary(conn:Connection,*,run_id:int)->dict[str,Any]:
    run=_run(conn,run_id); parts=_participant_rows(conn,run_id)
    fragments=[f for p in parts for f in _derive(conn,p,stage_run_id=run_id)["fragments"]]
    counts=Counter(f["proposal"].get("education_kind") or "review" for f in fragments if f["outcome"]=="READY_TO_ADD")
    fingerprint=_hash({"run":run_id,"preview":run["preview_fingerprint"],"parts":[p["safe_fingerprint"] for p in parts],"records":dict(counts)})
    return {"stage_run_id":run_id,"employee_count":len(parts),"records_by_kind":dict(counts),"skipped_count":sum(p["status"]=="SKIPPED_BY_DECISION" for p in parts),"acceptance_fingerprint":fingerprint}


def pause_acceptance_after_rollback(conn: Connection, *, run_id: int, exc: Exception) -> bool:
    """Best-effort, conditional operational pause in a new transaction.

    This must be called only after the canonical/PMF transaction rolled back.
    It intentionally cannot overwrite ACCEPTED or CANCELLED.
    """
    code, reference = _safe_error(exc)
    row = conn.execute(text("SELECT status FROM public.ppr_stage_runs WHERE stage_run_id=:id FOR UPDATE"), {"id": run_id}).mappings().one_or_none()
    if row is None or row["status"] not in {"COMPLETED_PENDING_REVIEW", "PAUSED_ON_ERROR"}:
        return False
    conn.execute(text("""UPDATE public.ppr_stage_runs
        SET status='PAUSED_ON_ERROR',paused_operation='ACCEPTANCE',stopped_participant_id=NULL,
            paused_at=now(),last_error_code=:code,last_error_reference=:reference
        WHERE stage_run_id=:id AND status IN ('COMPLETED_PENDING_REVIEW','PAUSED_ON_ERROR')"""),
        {"id": run_id, "code": code, "reference": reference})
    return True


def accept_stage2(conn:Connection,*,run_id:int,actor_user_id:int,acceptance_fingerprint:str|None=None)->dict[str,Any]:
    run=_run(conn,run_id,lock=True)
    if run["status"]=="ACCEPTED": return _view_run(conn,run_id)
    if run["status"] not in {"COMPLETED_PENDING_REVIEW","PAUSED_ON_ERROR"} or (run["status"]=="PAUSED_ON_ERROR" and run["paused_operation"]!="ACCEPTANCE"): raise Stage2ConflictError("STAGE2_ACCEPTANCE_NOT_READY")
    summary=acceptance_summary(conn,run_id=run_id)
    if acceptance_fingerprint and acceptance_fingerprint!=summary["acceptance_fingerprint"]: raise Stage2ConflictError("STAGE2_ACCEPTANCE_STALE")
    parts=_participant_rows(conn,run_id,lock=True)
    if any(p["status"] not in {"COMPLETED","SKIPPED_BY_DECISION"} for p in parts): raise Stage2ConflictError("STAGE2_ACCEPTANCE_NOT_READY")
    if not ppr_pmf_bridge_enabled(): raise Stage2ValidationError("STAGE2_PPR_PMF_BRIDGE_REQUIRED")
    for p in parts:
        if p.get("pmf_run_id"): commit_run(conn,run_id=int(p["pmf_run_id"]),actor_id=str(actor_user_id))
    conn.execute(text("""UPDATE public.ppr_stage_runs SET status='ACCEPTED',accepted_by_user_id=:actor,accepted_at=now(),accepted_precondition_fingerprint=:f,acceptance_outcome=CAST(:o AS jsonb),paused_operation=NULL,stopped_participant_id=NULL,paused_at=NULL,last_error_code=NULL,last_error_reference=NULL WHERE stage_run_id=:id"""),{"id":run_id,"actor":actor_user_id,"f":summary["acceptance_fingerprint"],"o":json.dumps(summary)})
    return _view_run(conn,run_id)
