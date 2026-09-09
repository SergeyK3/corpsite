"""Read-only Stage 0 cohort PREVIEW and metadata-only FREEZE services."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from app.services.hr_import_diff_removal_decision_service import count_pending_diff_removals

POLICY_VERSION = "PPR_STAGE0_COHORT_V1"
ALLOWED_BATCH_STATUSES = {"APPLY_PENDING", "APPLIED", "PARTIALLY_APPLIED"}
ELIGIBLE = "ELIGIBLE"
BLOCKED_NO_PERSON = "BLOCKED_NO_PERSON"
BLOCKED_AMBIGUOUS_PERSON = "BLOCKED_AMBIGUOUS_PERSON"
BLOCKED_PERSON_MERGED_OR_DELETED = "BLOCKED_PERSON_MERGED_OR_DELETED"
BLOCKED_SOURCE_MISSING = "BLOCKED_SOURCE_MISSING"
BLOCKED_SOURCE_AMBIGUOUS = "BLOCKED_SOURCE_AMBIGUOUS"
BLOCKED_SOURCE_STATUS = "BLOCKED_SOURCE_STATUS"
BLOCKED_SOURCE_DELETION_OR_REBINDING = "BLOCKED_SOURCE_DELETION_OR_REBINDING"
BLOCKED_MATERIALIZATION_PATH = "BLOCKED_MATERIALIZATION_PATH"


class Stage0Error(RuntimeError):
    code = "STAGE0_ERROR"


class Stage0NotFoundError(Stage0Error):
    code = "STAGE0_NOT_FOUND"


class Stage0ValidationError(Stage0Error):
    code = "STAGE0_VALIDATION"


class Stage0ConflictError(Stage0Error):
    code = "STAGE0_CONFLICT"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _safe_candidate_key(employee_id: int | None, row_id: int | None) -> str:
    return _hash({"employee_id": employee_id, "row_id": row_id})


def _check_batch(conn: Connection, batch_id: int) -> dict[str, Any]:
    row = conn.execute(text("""
        SELECT batch_id, source_type, status FROM public.hr_import_batches WHERE batch_id=:batch_id
    """), {"batch_id": batch_id}).mappings().one_or_none()
    if row is None:
        raise Stage0NotFoundError("STAGE0_SOURCE_BATCH_NOT_FOUND")
    result = dict(row)
    if result["source_type"] != "HR_CONTROL_LIST":
        raise Stage0ValidationError("STAGE0_SOURCE_TYPE_NOT_ALLOWED")
    if result["status"] not in ALLOWED_BATCH_STATUSES:
        raise Stage0ValidationError("STAGE0_SOURCE_BATCH_STATUS_NOT_ALLOWED")
    return result


def _scope_allows(scope: dict[str, Any] | None, org_unit_id: int | None) -> bool:
    if scope is None or scope.get("privileged") or scope.get("scope_unit_ids") is None:
        return True
    return org_unit_id is not None and int(org_unit_id) in {int(v) for v in scope.get("scope_unit_ids", [])}


def _scan(conn: Connection, *, source_batch_id: int, supplemental_of_run_id: int | None, scope: dict[str, Any] | None, lock: bool = False, include_correction_details: bool = False) -> dict[str, Any]:
    batch = _check_batch(conn, source_batch_id)
    if lock:
        # Lock simple relations separately. PostgreSQL rejects FOR SHARE on the nullable
        # side of the LEFT JOIN used by the classification query below.
        conn.execute(text("SELECT batch_id FROM public.hr_import_batches WHERE batch_id=:batch_id FOR SHARE"), {"batch_id": source_batch_id})
        conn.execute(text("SELECT row_id FROM public.hr_import_rows WHERE batch_id=:batch_id ORDER BY row_id FOR SHARE"), {"batch_id": source_batch_id})
        conn.execute(text("""
            SELECT e.employee_id FROM public.employees e JOIN public.hr_import_rows r ON r.employee_id=e.employee_id
             WHERE r.batch_id=:batch_id ORDER BY e.employee_id FOR SHARE
        """), {"batch_id": source_batch_id})
        conn.execute(text("""
            SELECT p.person_id FROM public.persons p JOIN public.employees e ON e.person_id=p.person_id
              JOIN public.hr_import_rows r ON r.employee_id=e.employee_id
             WHERE r.batch_id=:batch_id ORDER BY p.person_id FOR SHARE
        """), {"batch_id": source_batch_id})
    rows = conn.execute(text(f"""
        SELECT r.row_id, r.source_row_number, r.employee_id AS source_employee_id,
               e.employee_id, e.person_id, e.org_unit_id, e.is_active, e.operational_status, e.updated_at AS employee_updated_at,
               p.person_status, p.merged_into_person_id, p.updated_at AS person_updated_at,
               r.normalized_payload ->> 'full_name' AS source_display_name,
               p.full_name AS person_display_name,
               prm.ppr_lifecycle_state, prm.version AS ppr_version,
               (SELECT min(n.normalized_record_id) FROM public.hr_import_normalized_records n
                 WHERE n.batch_id=r.batch_id AND n.row_id=r.row_id AND n.employee_id=r.employee_id) AS identity_provenance_record_id,
               (SELECT count(*) FROM public.hr_import_rows r2 WHERE r2.batch_id=r.batch_id AND r2.employee_id=r.employee_id) AS source_row_count,
               (SELECT count(*) FROM public.employees other WHERE other.person_id=e.person_id
                 AND other.employee_id<>e.employee_id AND coalesce(other.is_active,true)=true
                 AND other.operational_status IN ('active','suspended','draft')) AS other_operational_employee_count
          FROM public.hr_import_rows r
          LEFT JOIN public.employees e ON e.employee_id=r.employee_id
          LEFT JOIN public.persons p ON p.person_id=e.person_id
          LEFT JOIN public.personnel_record_metadata prm ON prm.person_id=e.person_id
         WHERE r.batch_id=:batch_id
         ORDER BY e.employee_id NULLS LAST, e.person_id NULLS LAST, r.row_id
    """), {"batch_id": source_batch_id}).mappings().all()
    pending_removals = count_pending_diff_removals(conn, source_batch_id)
    outcomes: list[dict[str, Any]] = []
    for raw in rows:
        item = dict(raw)
        if not _scope_allows(scope, item.get("org_unit_id")):
            continue
        employee_id = item.get("employee_id")
        category, reason = ELIGIBLE, "STAGE0_ELIGIBLE"
        if employee_id is None:
            category, reason = BLOCKED_SOURCE_MISSING, "STAGE0_SOURCE_EMPLOYEE_MISSING"
        elif not bool(item.get("is_active")) or item.get("operational_status") != "active":
            category, reason = BLOCKED_SOURCE_MISSING, "STAGE0_EMPLOYEE_NOT_ACTIVE"
        elif item.get("person_id") is None:
            category, reason = BLOCKED_NO_PERSON, "STAGE0_EMPLOYEE_PERSON_MISSING"
        elif item.get("person_status") != "active" or item.get("merged_into_person_id") is not None:
            category, reason = BLOCKED_PERSON_MERGED_OR_DELETED, "STAGE0_PERSON_NOT_ACTIVE"
        elif int(item.get("other_operational_employee_count") or 0) > 0:
            category, reason = BLOCKED_AMBIGUOUS_PERSON, "STAGE0_MULTIPLE_OPERATIONAL_EMPLOYEES"
        elif int(item.get("source_row_count") or 0) != 1:
            category, reason = BLOCKED_SOURCE_AMBIGUOUS, "STAGE0_SOURCE_ANCHOR_NOT_UNIQUE"
        elif pending_removals:
            category, reason = BLOCKED_SOURCE_DELETION_OR_REBINDING, "STAGE0_BATCH_PENDING_REMOVALS"
        elif item.get("ppr_lifecycle_state") in {"ARCHIVED", "MERGED"}:
            category, reason = BLOCKED_MATERIALIZATION_PATH, "STAGE0_PPR_LIFECYCLE_NOT_MATERIALIZABLE"
        snapshot = {
            "employee_id": employee_id, "person_id": item.get("person_id"), "source_batch_id": source_batch_id,
            "source_row_id": item["row_id"], "source_row_number": item.get("source_row_number"),
            "identity_provenance_record_id": item.get("identity_provenance_record_id"),
            "employee_updated_at": item.get("employee_updated_at"), "person_updated_at": item.get("person_updated_at"),
            "ppr_lifecycle_state": item.get("ppr_lifecycle_state") or "NOT_MATERIALIZED", "ppr_lifecycle_version": item.get("ppr_version"),
            "category": category, "reason_code": reason,
        }
        outcome = {**snapshot, "safe_detail": reason, "safe_fingerprint": _hash(snapshot), "candidate_key": _safe_candidate_key(employee_id, item["row_id"])}
        if include_correction_details:
            # Protected HR_HEAD view: source-list FIO plus a row number is the
            # minimum correction context.  Never return IIN or raw payload.
            name = item.get("source_display_name") or item.get("person_display_name")
            if name:
                outcome["display_name"] = str(name)
        outcomes.append(outcome)
    eligible = [outcome for outcome in outcomes if outcome["category"] == ELIGIBLE]
    for position, outcome in enumerate(eligible, 1):
        outcome["position"] = position
    fingerprint_payload = {
        "policy_version": POLICY_VERSION, "source_batch_id": source_batch_id, "source_type": batch["source_type"],
        "source_batch_status": batch["status"], "pending_removal_count": pending_removals,
        # Correction-only display data must never affect a persisted cohort
        # identity.  Otherwise a harmless request projection would make a
        # freshly viewed preview look stale during FREEZE.
        "supplemental_of_run_id": supplemental_of_run_id,
        "outcomes": [{key: value for key, value in outcome.items() if key != "display_name"} for outcome in outcomes],
    }
    return {
        "source_batch_id": source_batch_id, "source_type": batch["source_type"], "source_batch_status": batch["status"],
        "supplemental_of_run_id": supplemental_of_run_id, "pending_removal_count": pending_removals,
        "preview_fingerprint": _hash(fingerprint_payload), "eligible": eligible,
        "blockers": [outcome for outcome in outcomes if outcome["category"] != ELIGIBLE],
        "counts": dict(sorted(Counter(item["category"] for item in outcomes).items())),
    }


def preview_stage0_cohort(conn: Connection, *, source_batch_id: int, supplemental_of_run_id: int | None = None, scope: dict[str, Any] | None = None, include_correction_details: bool = False) -> dict[str, Any]:
    """Scan without DML; caller owns a READ ONLY transaction when required."""
    return _scan(conn, source_batch_id=source_batch_id, supplemental_of_run_id=supplemental_of_run_id, scope=scope, include_correction_details=include_correction_details)


def freeze_stage0_cohort(conn: Connection, *, source_batch_id: int, preview_fingerprint: str, actor_user_id: int, supplemental_of_run_id: int | None = None, scope: dict[str, Any] | None = None) -> dict[str, Any]:
    if supplemental_of_run_id is not None:
        parent = conn.execute(text("SELECT 1 FROM public.ppr_stage0_cohort_runs WHERE stage0_cohort_run_id=:id FOR SHARE"), {"id": supplemental_of_run_id}).scalar_one_or_none()
        if parent is None:
            raise Stage0NotFoundError("STAGE0_SUPPLEMENTAL_PARENT_NOT_FOUND")
    conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": f"PPR_STAGE0:FREEZE:{source_batch_id}:{supplemental_of_run_id or 0}"})
    preview = _scan(conn, source_batch_id=source_batch_id, supplemental_of_run_id=supplemental_of_run_id, scope=scope, lock=True)
    if preview["preview_fingerprint"] != preview_fingerprint:
        raise Stage0ConflictError("STAGE0_PREVIEW_STALE")
    if preview["pending_removal_count"]:
        raise Stage0ValidationError("STAGE0_BATCH_PENDING_REMOVALS")
    existing = conn.execute(text("SELECT stage0_cohort_run_id FROM public.ppr_stage0_cohort_runs WHERE preview_fingerprint=:fingerprint"), {"fingerprint": preview_fingerprint}).scalar_one_or_none()
    if existing is not None:
        return {"stage0_cohort_run_id": int(existing), "replay": True, "counts": preview["counts"]}
    try:
        run_id = conn.execute(text("""
            INSERT INTO public.ppr_stage0_cohort_runs(run_kind,supplemental_of_run_id,source_batch_id,source_type,source_batch_status,preview_fingerprint,policy_version,source_snapshot,created_by_user_id)
            VALUES(:run_kind,:parent,:batch_id,:source_type,:batch_status,:fingerprint,:policy,CAST(:snapshot AS jsonb),:actor)
            RETURNING stage0_cohort_run_id
        """), {"run_kind": "SUPPLEMENTAL" if supplemental_of_run_id else "BASE", "parent": supplemental_of_run_id,
                "batch_id": source_batch_id, "source_type": preview["source_type"], "batch_status": preview["source_batch_status"],
                "fingerprint": preview_fingerprint, "policy": POLICY_VERSION,
                "snapshot": _canonical({"pending_removal_count": preview["pending_removal_count"], "counts": preview["counts"]}), "actor": actor_user_id}).scalar_one()
    except IntegrityError as exc:
        raise Stage0ConflictError("STAGE0_FREEZE_RETRY_REQUIRED") from exc
    for participant in preview["eligible"]:
        conn.execute(text("""
          INSERT INTO public.ppr_stage0_cohort_participants(stage0_cohort_run_id,position,employee_id,person_id,source_batch_id,source_row_id,identity_provenance_record_id,safe_fingerprint,employee_state_version,person_state_version,ppr_lifecycle_version)
          VALUES(:run_id,:position,:employee_id,:person_id,:batch_id,:row_id,:provenance,:fingerprint,NULL,NULL,:ppr_version)
        """), {"run_id": run_id, "position": participant["position"], "employee_id": participant["employee_id"], "person_id": participant["person_id"], "batch_id": source_batch_id, "row_id": participant["source_row_id"], "provenance": participant["identity_provenance_record_id"], "fingerprint": participant["safe_fingerprint"], "ppr_version": participant["ppr_lifecycle_version"]})
    for blocker in preview["blockers"]:
        conn.execute(text("""
          INSERT INTO public.ppr_stage0_cohort_blockers(stage0_cohort_run_id,employee_id,person_id,source_batch_id,source_row_id,identity_provenance_record_id,candidate_key,category,reason_code,safe_detail,safe_fingerprint)
          VALUES(:run_id,:employee_id,:person_id,:batch_id,:row_id,:provenance,:candidate_key,:category,:reason_code,:safe_detail,:fingerprint)
        """), {"run_id": run_id, "employee_id": blocker["employee_id"], "person_id": blocker["person_id"], "batch_id": source_batch_id, "row_id": blocker["source_row_id"], "provenance": blocker["identity_provenance_record_id"], "candidate_key": blocker["candidate_key"], "category": blocker["category"], "reason_code": blocker["reason_code"], "safe_detail": blocker["reason_code"], "fingerprint": blocker["safe_fingerprint"]})
    return {"stage0_cohort_run_id": int(run_id), "replay": False, "counts": preview["counts"]}


def get_stage0_run(conn: Connection, *, run_id: int, scope: dict[str, Any] | None = None, include_correction_details: bool = False) -> dict[str, Any]:
    run = conn.execute(text("SELECT stage0_cohort_run_id,run_kind,supplemental_of_run_id,source_batch_id,source_batch_status,preview_fingerprint,policy_version,frozen_at FROM public.ppr_stage0_cohort_runs WHERE stage0_cohort_run_id=:run_id"), {"run_id": run_id}).mappings().one_or_none()
    if run is None: raise Stage0NotFoundError("STAGE0_RUN_NOT_FOUND")
    participants = [dict(row) for row in conn.execute(text("""
        SELECT p.position,p.employee_id,p.person_id,p.source_batch_id,p.source_row_id,
               p.safe_fingerprint,e.org_unit_id,r.source_row_number,
               r.normalized_payload ->> 'full_name' AS source_display_name,
               person.full_name AS person_display_name
        FROM public.ppr_stage0_cohort_participants p
        JOIN public.employees e ON e.employee_id=p.employee_id
        JOIN public.persons person ON person.person_id=p.person_id
        JOIN public.hr_import_rows r ON r.row_id=p.source_row_id
        WHERE p.stage0_cohort_run_id=:run_id
        ORDER BY p.position
    """), {"run_id": run_id}).mappings()]
    # A changed scope is fail-closed; no partial historical cohort disclosure.
    if any(not _scope_allows(scope, p.pop("org_unit_id", None)) for p in participants):
        raise Stage0ConflictError("STAGE0_RUN_OUT_OF_SCOPE")
    for participant in participants:
        source_name = participant.pop("source_display_name", None)
        person_name = participant.pop("person_display_name", None)
        if include_correction_details and (source_name or person_name):
            participant["display_name"] = str(source_name or person_name)
    return {"run": dict(run), "participants": participants}


def get_stage0_blockers(conn: Connection, *, run_id: int) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(text("""SELECT employee_id,person_id,source_batch_id,source_row_id,category,reason_code,safe_detail,candidate_key FROM public.ppr_stage0_cohort_blockers WHERE stage0_cohort_run_id=:run_id ORDER BY category, employee_id NULLS LAST, source_row_id NULLS LAST"""), {"run_id": run_id}).mappings()]


def list_stage0_source_batches(conn: Connection) -> list[dict[str, Any]]:
    """Safe batch picker data; it intentionally contains neither names nor raw input."""
    return [dict(row) for row in conn.execute(text("""
        SELECT b.batch_id, b.status, b.imported_at, count(r.row_id)::integer AS source_row_count
          FROM public.hr_import_batches b
          LEFT JOIN public.hr_import_rows r ON r.batch_id=b.batch_id
         WHERE b.source_type='HR_CONTROL_LIST'
           AND b.status IN ('APPLY_PENDING','APPLIED','PARTIALLY_APPLIED')
         GROUP BY b.batch_id, b.status, b.imported_at
         ORDER BY b.imported_at DESC, b.batch_id DESC
    """)).mappings()]
