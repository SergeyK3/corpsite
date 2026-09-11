"""Transactional, PII-free persisted status projection (WP-PPR-MIG-005B).

It reads source systems only.  The public API deliberately exposes no HTTP route.
"""
from __future__ import annotations
import hashlib, json
from typing import Any, Iterable
from sqlalchemy import text
from sqlalchemy.engine import Connection

SECTIONS = (
    "general",
    "education",
    "training",
    "relatives",
    "military",
    "employment_biography",
    "employment_history",
    "foreign_languages",
    "awards",
    "academic_degrees_titles",
)
IMPLEMENTED_SECTIONS = ("general", "education", "training")

def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()

def universe_key(base_cohort_run_id: int, supplemental_cohort_run_ids: Iterable[int] = ()) -> str:
    return _hash({"base": int(base_cohort_run_id), "supplemental": sorted({int(x) for x in supplemental_cohort_run_ids})})

def ensure_universe(conn: Connection, *, base_cohort_run_id: int, supplemental_cohort_run_ids: Iterable[int] = ()) -> int:
    supplements = sorted({int(x) for x in supplemental_cohort_run_ids})
    base = conn.execute(text("SELECT run_kind FROM public.ppr_stage0_cohort_runs WHERE stage0_cohort_run_id=:id FOR SHARE"), {"id": base_cohort_run_id}).scalar_one_or_none()
    if base != "BASE": raise ValueError("base cohort must be a BASE run")
    if supplements:
        rows = conn.execute(text("SELECT stage0_cohort_run_id FROM public.ppr_stage0_cohort_runs WHERE stage0_cohort_run_id=ANY(:ids) AND run_kind='SUPPLEMENTAL' AND supplemental_of_run_id=:base"), {"ids": supplements, "base": base_cohort_run_id}).scalars().all()
        if sorted(map(int, rows)) != supplements: raise ValueError("supplemental cohort is not explicitly attached to base")
    key = universe_key(base_cohort_run_id, supplements)
    uid = conn.execute(text("INSERT INTO public.ppr_migration_status_universes(universe_key,base_cohort_run_id) VALUES(:key,:base) ON CONFLICT(universe_key) DO UPDATE SET universe_key=EXCLUDED.universe_key RETURNING universe_id"), {"key": key,"base":base_cohort_run_id}).scalar_one()
    conn.execute(text("INSERT INTO public.ppr_migration_status_universe_cohorts(universe_id,stage0_cohort_run_id,cohort_role) VALUES(:u,:c,'BASE') ON CONFLICT DO NOTHING"), {"u":uid,"c":base_cohort_run_id})
    for cohort in supplements:
        conn.execute(text("INSERT INTO public.ppr_migration_status_universe_cohorts(universe_id,stage0_cohort_run_id,cohort_role) VALUES(:u,:c,'SUPPLEMENTAL') ON CONFLICT DO NOTHING"), {"u":uid,"c":cohort})
    return int(uid)

def _facts(conn: Connection, universe_id: int) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(text("""
      SELECT cp.stage0_cohort_run_id,cp.stage0_participant_id,cp.person_id,cp.employee_id,cp.source_row_id,
             e.org_unit_id,e.person_id employee_person_id,e.is_active,e.operational_status,p.person_status,p.merged_into_person_id,
             p.updated_at person_updated_at,e.updated_at employee_updated_at,r.normalized_payload source_payload
      FROM ppr_migration_status_universe_cohorts uc
      JOIN ppr_stage0_cohort_participants cp ON cp.stage0_cohort_run_id=uc.stage0_cohort_run_id
      JOIN employees e ON e.employee_id=cp.employee_id JOIN persons p ON p.person_id=cp.person_id
      JOIN hr_import_rows r ON r.row_id=cp.source_row_id WHERE uc.universe_id=:u
    """), {"u":universe_id}).mappings()]

def _candidate(conn: Connection, f: dict[str, Any], section: str) -> dict[str, Any] | None:
    if section == "general":
        sql = """SELECT r.stage1_run_id run_id,p.stage1_participant_id participant_id,r.status run_status,p.status participant_status,p.source_fingerprint,p.person_updated_at,p.completed_at,r.accepted_at,r.policy_version,NULL::bigint pmf_run_id FROM ppr_stage1_general_runs r JOIN ppr_stage1_general_participants p ON p.stage1_run_id=r.stage1_run_id WHERE r.stage0_cohort_run_id=:c AND p.person_id=:p AND r.status<>'CANCELLED' ORDER BY COALESCE(r.accepted_at,p.completed_at,r.created_at) DESC,r.stage1_run_id DESC LIMIT 1"""
    else:
        sql = """SELECT r.stage_run_id run_id,p.stage_run_participant_id participant_id,r.status run_status,p.status participant_status,p.safe_fingerprint source_fingerprint,NULL::timestamptz person_updated_at,p.completed_at,r.accepted_at,r.policy_version,p.pmf_run_id FROM ppr_stage_runs r JOIN ppr_stage_run_participants p ON p.stage_run_id=r.stage_run_id WHERE r.stage0_cohort_run_id=:c AND r.stage_code=:s AND p.person_id=:p AND r.status<>'CANCELLED' ORDER BY COALESCE(r.accepted_at,p.completed_at,r.created_at) DESC,r.stage_run_id DESC LIMIT 1"""
    args={"c":f["stage0_cohort_run_id"],"p":f["person_id"],"s":section}
    row=conn.execute(text(sql),args).mappings().one_or_none(); return dict(row) if row else None

def _accepted_evidence(conn: Connection | None, *, section: str, person_id: int, candidate: dict[str, Any]) -> bool:
    """Require existing participant-level evidence; never infer an accepted empty section."""
    if "_accepted_evidence" in candidate:
        return bool(candidate["_accepted_evidence"])
    if conn is None:  # unit-tree tests exercise classification only, not persistence evidence.
        return section != "general" and candidate.get("pmf_run_id") is not None
    if section == "general":
        return conn.execute(text("SELECT 1 FROM public.personnel_record_events WHERE person_id=:p AND event_type='PPR_STAGE1_GENERAL_ACCEPTED' AND event_payload->>'stage1_run_id'=:run LIMIT 1"), {"p":person_id,"run":str(candidate["run_id"])}).scalar_one_or_none() is not None
    pmf = candidate.get("pmf_run_id")
    if pmf is None: return False
    # An item is mandatory evidence in current PMF. A zero-item accepted run has no
    # explicit absence attestation in existing facts, so conservatively is not ACCEPTED.
    return conn.execute(text("SELECT 1 FROM public.personnel_migration_runs r WHERE r.run_id=:id AND r.run_status='committed' AND EXISTS (SELECT 1 FROM public.personnel_migration_items i WHERE i.run_id=r.run_id)"), {"id":pmf}).scalar_one_or_none() is not None

def _status(conn: Connection | None, f: dict[str, Any], section: str, candidate: dict[str, Any] | None = None, previous: dict[str, Any] | None = None) -> dict[str, Any]:
    binding=_hash({k:str(f.get(k)) for k in ("stage0_cohort_run_id","stage0_participant_id","person_id","employee_id","source_row_id","employee_person_id","is_active","operational_status","person_status","merged_into_person_id")})
    target=_hash({"person":f["person_id"],"person_updated":f["person_updated_at"]})
    blocked = (not f["is_active"] or f["operational_status"] != "active" or f["employee_person_id"] != f["person_id"] or f["person_status"] != "active" or f["merged_into_person_id"] is not None)
    source=_hash({"row":f["source_row_id"],"payload":f.get("source_payload") or {},"section":section})
    base={"stage_run_id":None,"stage1_run_id":None,"stage_participant_id":None,"stage1_participant_id":None,"pmf_run_id":None,"evidence_kind":None,"policy_version":None}
    if blocked: return {**base,"status_code":"BLOCKED","reason_code":"BINDING_EMPLOYEE_LINK_STALE","source_fingerprint":source,"target_fingerprint":target,"binding_fingerprint":binding}
    # The seven catalog-only sections deliberately have no source/run lookup
    # until their individual migration processors are approved.  This preserves
    # the full persisted matrix without fabricating evidence or adding N+1 reads.
    if section not in IMPLEMENTED_SECTIONS:
        return {**base,"status_code":"NOT_STARTED","reason_code":"SECTION_PROCESSING_NOT_CONNECTED","source_fingerprint":source,"target_fingerprint":target,"binding_fingerprint":binding}
    cand=candidate if candidate is not None else _candidate(conn,f,section)
    if previous and previous["status_code"] in ("ACCEPTED","AUTO_READY","CORRECTED_BY_HR") and previous["source_fingerprint"] != source:
        return {**base,"status_code":"STALE","reason_code":"FINGERPRINT_SOURCE_CHANGED","source_fingerprint":source,"target_fingerprint":target,"binding_fingerprint":binding}
    if not cand: return {**base,"status_code":"NOT_STARTED","reason_code":"RUN_NO_SECTION_RESULT","source_fingerprint":source,"target_fingerprint":target,"binding_fingerprint":binding}
    base.update({"policy_version":cand["policy_version"],"pmf_run_id":cand["pmf_run_id"]})
    if previous and previous["status_code"] in ("ACCEPTED","AUTO_READY","CORRECTED_BY_HR") and previous.get("policy_version") != cand["policy_version"]:
        return {**base,"status_code":"STALE","reason_code":"FINGERPRINT_POLICY_CHANGED","source_fingerprint":source,"target_fingerprint":target,"binding_fingerprint":binding}
    if section == "general": base.update(stage1_run_id=cand["run_id"],stage1_participant_id=cand["participant_id"])
    else: base.update(stage_run_id=cand["run_id"],stage_participant_id=cand["participant_id"])
    # Existing snapshots are stale if a source/canonical fact changed after participant completion.
    if cand["completed_at"] and f["person_updated_at"] > cand["completed_at"]:
        return {**base,"status_code":"STALE","reason_code":"FINGERPRINT_SOURCE_CHANGED","source_fingerprint":source,"target_fingerprint":target,"binding_fingerprint":binding}
    if cand["participant_status"] == "ERROR" or cand["run_status"] == "PAUSED_ON_ERROR": code,reason="ERROR","RUN_PARTICIPANT_ERROR"
    elif cand["run_status"] == "ACCEPTED" and cand["participant_status"] == "COMPLETED" and _accepted_evidence(conn,section=section,person_id=f["person_id"],candidate=cand): code,reason="ACCEPTED","RUN_PARTICIPANT_ACCEPTED"; base["evidence_kind"]="PARTICIPANT_ACCEPTED"
    elif cand["participant_status"] == "COMPLETED" or cand["run_status"] == "COMPLETED_PENDING_REVIEW": code,reason="AUTO_READY","RUN_COMPLETED_PENDING_REVIEW"
    elif cand["run_status"] in ("APPROVED","RUNNING"): code,reason="PROCESSING",("RUN_RUNNING" if cand["run_status"] == "RUNNING" else "RUN_APPROVED")
    else: code,reason="AUTO_READY","RUN_PREVIEW_READY"
    return {**base,"status_code":code,"reason_code":reason,"source_fingerprint":source,"target_fingerprint":target,"binding_fingerprint":binding}

def _candidate_cache(conn: Connection, universe_id: int) -> dict[tuple[int, int, str], dict[str, Any]]:
    """Three set queries; selection is ordered once per section, never per person."""
    cache: dict[tuple[int, int, str], dict[str, Any]] = {}
    queries = [
      ("general", """SELECT r.stage0_cohort_run_id cohort,p.person_id,r.stage1_run_id run_id,p.stage1_participant_id participant_id,r.status run_status,p.status participant_status,p.source_fingerprint,p.completed_at,r.accepted_at,r.policy_version,NULL::bigint pmf_run_id FROM ppr_migration_status_universe_cohorts uc JOIN ppr_stage1_general_runs r ON r.stage0_cohort_run_id=uc.stage0_cohort_run_id JOIN ppr_stage1_general_participants p ON p.stage1_run_id=r.stage1_run_id WHERE uc.universe_id=:u AND r.status<>'CANCELLED' ORDER BY p.person_id,r.stage0_cohort_run_id,COALESCE(r.accepted_at,p.completed_at,r.created_at) DESC,r.stage1_run_id DESC"""),
      ("education", """SELECT r.stage0_cohort_run_id cohort,p.person_id,r.stage_run_id run_id,p.stage_run_participant_id participant_id,r.status run_status,p.status participant_status,p.safe_fingerprint,p.completed_at,r.accepted_at,r.policy_version,p.pmf_run_id FROM ppr_migration_status_universe_cohorts uc JOIN ppr_stage_runs r ON r.stage0_cohort_run_id=uc.stage0_cohort_run_id AND r.stage_code='education' JOIN ppr_stage_run_participants p ON p.stage_run_id=r.stage_run_id WHERE uc.universe_id=:u AND r.status<>'CANCELLED' ORDER BY p.person_id,r.stage0_cohort_run_id,COALESCE(r.accepted_at,p.completed_at,r.created_at) DESC,r.stage_run_id DESC"""),
      ("training", """SELECT r.stage0_cohort_run_id cohort,p.person_id,r.stage_run_id run_id,p.stage_run_participant_id participant_id,r.status run_status,p.status participant_status,p.safe_fingerprint,p.completed_at,r.accepted_at,r.policy_version,p.pmf_run_id FROM ppr_migration_status_universe_cohorts uc JOIN ppr_stage_runs r ON r.stage0_cohort_run_id=uc.stage0_cohort_run_id AND r.stage_code='training' JOIN ppr_stage_run_participants p ON p.stage_run_id=r.stage_run_id WHERE uc.universe_id=:u AND r.status<>'CANCELLED' ORDER BY p.person_id,r.stage0_cohort_run_id,COALESCE(r.accepted_at,p.completed_at,r.created_at) DESC,r.stage_run_id DESC"""),
    ]
    for section, sql in queries:
        for row in conn.execute(text(sql), {"u": universe_id}).mappings():
            key=(int(row["cohort"]),int(row["person_id"]),section)
            if key not in cache: cache[key]=dict(row)
    general_pairs={(v["person_id"], v["run_id"]) for k,v in cache.items() if k[2]=="general" and v["run_status"]=="ACCEPTED"}
    events={(int(r["person_id"]),int(r["run_id"])) for r in conn.execute(text("SELECT person_id,(event_payload->>'stage1_run_id')::bigint run_id FROM personnel_record_events WHERE event_type='PPR_STAGE1_GENERAL_ACCEPTED' AND event_payload ? 'stage1_run_id'")).mappings()}
    pmf_ids=[int(v["pmf_run_id"]) for k,v in cache.items() if k[2] != "general" and v.get("pmf_run_id") is not None]
    committed=set()
    if pmf_ids:
        committed={int(x) for x in conn.execute(text("SELECT r.run_id FROM personnel_migration_runs r WHERE r.run_id=ANY(:ids) AND r.run_status='committed' AND EXISTS (SELECT 1 FROM personnel_migration_items i WHERE i.run_id=r.run_id)"),{"ids":pmf_ids}).scalars()}
    for key, value in cache.items():
        value["_accepted_evidence"] = ((value["person_id"],value["run_id"]) in events) if key[2]=="general" else value.get("pmf_run_id") in committed
    return cache

def rebuild_universe(conn: Connection, *, universe_id: int) -> int:
    """Idempotent all-or-nothing rebuild; caller owns a transaction."""
    # Serialize delete-and-replace snapshots for one universe without locking
    # unrelated cohorts.  PostgreSQL releases the advisory xact lock on commit/
    # rollback, preserving all-or-nothing semantics for concurrent rebuilds.
    conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": f"PPR-MIG-005B:{int(universe_id)}"})
    rows=[]; candidates=_candidate_cache(conn,universe_id)
    previous={(int(x["person_id"]),str(x["section_code"])):dict(x) for x in conn.execute(text("SELECT person_id,section_code,status_code,source_fingerprint,policy_version FROM ppr_migration_section_status_projection WHERE universe_id=:u FOR UPDATE"),{"u":universe_id}).mappings()}
    for fact in _facts(conn,universe_id):
        for section in SECTIONS:
            candidate=candidates.get((int(fact["stage0_cohort_run_id"]),int(fact["person_id"]),section))
            rows.append({**fact,"section":section,**_status(conn,fact,section,candidate,previous.get((int(fact["person_id"]),section)))})
    conn.execute(text("DELETE FROM public.ppr_migration_section_status_projection WHERE universe_id=:u"),{"u":universe_id})
    for r in rows:
        conn.execute(text("""INSERT INTO public.ppr_migration_section_status_projection(universe_id,person_id,employee_context_id,org_unit_id,section_code,status_code,reason_code,source_cohort_run_id,source_row_id,stage_run_id,stage1_run_id,stage_participant_id,stage1_participant_id,pmf_run_id,evidence_kind,policy_version,source_fingerprint,target_fingerprint,binding_fingerprint) VALUES(:u,:person_id,:employee_id,:org_unit_id,:section,:status_code,:reason_code,:stage0_cohort_run_id,:source_row_id,:stage_run_id,:stage1_run_id,:stage_participant_id,:stage1_participant_id,:pmf_run_id,:evidence_kind,:policy_version,:source_fingerprint,:target_fingerprint,:binding_fingerprint)"""),{**r,"u":universe_id})
    return len(rows)

def list_projection_for_scope(conn: Connection, *, universe_id: int, org_unit_ids: list[int] | None) -> list[dict[str, Any]]:
    where="universe_id=:u" if org_unit_ids is None else "universe_id=:u AND org_unit_id=ANY(:units)"
    return [dict(r) for r in conn.execute(text(f"SELECT * FROM public.ppr_migration_section_status_projection WHERE {where} ORDER BY person_id,section_code"),{"u":universe_id,"units":org_unit_ids}).mappings()]
