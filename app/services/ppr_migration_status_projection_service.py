"""Transactional, PII-free persisted status projection (WP-PPR-MIG-005B).

It reads source systems only.  The public API deliberately exposes no HTTP route.
"""
from __future__ import annotations
import hashlib, json
from typing import Any, Iterable
from sqlalchemy import text
from sqlalchemy.engine import Connection
from app.db.models.personnel_migration import (
    EDUCATION_KINDS, EXTERNAL_EMPLOYMENT_RECORD_KINDS,
    EXTERNAL_EMPLOYMENT_VERIFICATION_STATUSES, LIFECYCLE_STATUSES,
    MILITARY_RECORD_KIND_NOT_APPLICABLE, MILITARY_RECORD_KINDS,
    MILITARY_LIFECYCLE_STATUSES, RELATIONSHIP_TYPES, SECTION_SOURCE_TYPES,
    TRAINING_KINDS, VERIFICATION_STATUSES,
)

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
CANONICAL_COHORT_POLICY_VERSION = "PPR_STAGE0_CANONICAL_HR_V1"
IMPORT_PROFILE_POLICY_VERSION = "PPR_MIGRATION_STATUS_IMPORT_PROFILE_V1"

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

def ensure_canonical_base_cohort(conn: Connection, *, actor_user_id: int | None = None) -> int:
    """Freeze the current active-primary roster without fabricating import provenance.

    The canonical selection is intentionally the same relation used by the
    personnel report: active employee, active person, and exactly one current
    active PRIMARY assignment.  Re-running against unchanged facts returns the
    same immutable cohort through its fingerprint.
    """
    conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('PPR_STAGE0:CANONICAL_HR'))"))
    rows = [dict(row) for row in conn.execute(text("""
      WITH active_primary AS (
        SELECT pa.person_id, min(pa.org_unit_id) AS org_unit_id
        FROM public.person_assignments pa
        WHERE pa.active_flag IS TRUE AND pa.is_primary IS TRUE
          AND pa.lifecycle_status='active' AND pa.start_date <= CURRENT_DATE
          AND (pa.end_date IS NULL OR pa.end_date >= CURRENT_DATE)
        GROUP BY pa.person_id HAVING count(*)=1
      )
      SELECT e.employee_id,e.person_id,ap.org_unit_id,e.updated_at AS employee_updated_at,
             p.updated_at AS person_updated_at
      FROM public.employees e
      JOIN public.persons p ON p.person_id=e.person_id
      JOIN active_primary ap ON ap.person_id=e.person_id
      WHERE COALESCE(e.is_active,true) IS TRUE AND e.operational_status='active'
        AND (e.date_from IS NULL OR e.date_from <= CURRENT_DATE)
        AND (e.date_to IS NULL OR e.date_to >= CURRENT_DATE)
        AND p.person_status='active' AND p.merged_into_person_id IS NULL
      ORDER BY e.employee_id
    """)).mappings()]
    snapshot_members = [
        {"employee_id": int(row["employee_id"]), "person_id": int(row["person_id"]),
         "org_unit_id": row["org_unit_id"], "employee_updated_at": row["employee_updated_at"],
         "person_updated_at": row["person_updated_at"]}
        for row in rows
    ]
    fingerprint = _hash({"policy_version": CANONICAL_COHORT_POLICY_VERSION, "members": snapshot_members})
    existing = conn.execute(text("SELECT stage0_cohort_run_id FROM public.ppr_stage0_cohort_runs WHERE preview_fingerprint=:fingerprint"), {"fingerprint": fingerprint}).scalar_one_or_none()
    if existing is not None:
        return int(existing)
    actor = actor_user_id or conn.execute(text("SELECT min(user_id) FROM public.users WHERE is_active=true")).scalar_one()
    if actor is None:
        raise ValueError("canonical cohort requires an active actor")
    run_id = conn.execute(text("""
      INSERT INTO public.ppr_stage0_cohort_runs(
        run_kind,supplemental_of_run_id,source_batch_id,source_type,source_batch_status,
        preview_fingerprint,policy_version,source_snapshot,created_by_user_id)
      VALUES('BASE',NULL,NULL,'CANONICAL_HR','CANONICAL',:fingerprint,:policy,
             CAST(:snapshot AS jsonb),:actor)
      RETURNING stage0_cohort_run_id
    """), {"fingerprint": fingerprint, "policy": CANONICAL_COHORT_POLICY_VERSION,
            "snapshot": json.dumps({"selection": "active_employee_exactly_one_active_primary_assignment", "member_count": len(rows)}, default=str),
            "actor": int(actor)}).scalar_one()
    for position, row in enumerate(rows, 1):
        participant_fingerprint = _hash({"employee_id": row["employee_id"], "person_id": row["person_id"],
                                         "org_unit_id": row["org_unit_id"],
                                         "employee_updated_at": row["employee_updated_at"],
                                         "person_updated_at": row["person_updated_at"],
                                         "source_type": "CANONICAL_HR"})
        conn.execute(text("""
          INSERT INTO public.ppr_stage0_cohort_participants(
            stage0_cohort_run_id,position,employee_id,person_id,source_batch_id,source_row_id,
            identity_provenance_record_id,safe_fingerprint,employee_state_version,person_state_version,ppr_lifecycle_version)
          VALUES(:run_id,:position,:employee_id,:person_id,NULL,NULL,NULL,:fingerprint,NULL,NULL,NULL)
        """), {"run_id": run_id, "position": position, "employee_id": row["employee_id"],
                "person_id": row["person_id"], "fingerprint": participant_fingerprint})
    return int(run_id)

def _facts(conn: Connection, universe_id: int) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(text("""
      SELECT cp.stage0_cohort_run_id,cp.stage0_participant_id,cp.person_id,cp.employee_id,cp.source_row_id,
             COALESCE(primary_assignment.org_unit_id,e.org_unit_id) AS org_unit_id,
             cohort.source_type,e.person_id employee_person_id,e.is_active,e.operational_status,p.person_status,p.merged_into_person_id,
             p.updated_at person_updated_at,e.updated_at employee_updated_at,r.normalized_payload source_payload
      FROM ppr_migration_status_universe_cohorts uc
      JOIN ppr_stage0_cohort_runs cohort ON cohort.stage0_cohort_run_id=uc.stage0_cohort_run_id
      JOIN ppr_stage0_cohort_participants cp ON cp.stage0_cohort_run_id=uc.stage0_cohort_run_id
      JOIN employees e ON e.employee_id=cp.employee_id JOIN persons p ON p.person_id=cp.person_id
      LEFT JOIN hr_import_rows r ON r.row_id=cp.source_row_id
      LEFT JOIN LATERAL (
        SELECT pa.org_unit_id FROM public.person_assignments pa
        WHERE pa.person_id=cp.person_id AND pa.active_flag IS TRUE AND pa.is_primary IS TRUE
          AND pa.lifecycle_status='active' AND pa.start_date <= CURRENT_DATE
          AND (pa.end_date IS NULL OR pa.end_date >= CURRENT_DATE)
        ORDER BY pa.start_date DESC,pa.assignment_id DESC LIMIT 1
      ) primary_assignment ON TRUE
      WHERE uc.universe_id=:u
    """), {"u":universe_id}).mappings()]


def _missing(*fields: tuple[str, Any]) -> str | None:
    return next((name for name, value in fields if value is None or not str(value).strip()), None)


def _canonical_section_evidence(conn: Connection, facts: list[dict[str, Any]]) -> dict[int, dict[str, list[dict[str, Any]]]]:
    """Read all canonical section sources in bounded set queries.

    These are the same person-owned tables exposed by the PPR card.  No import
    row is consulted for a CANONICAL_HR cohort.
    """
    person_ids = sorted({int(f["person_id"]) for f in facts})
    result = {person_id: {section: [] for section in SECTIONS} for person_id in person_ids}
    if not person_ids:
        return result
    sources = {
        "education": "SELECT * FROM public.person_education WHERE person_id=ANY(:ids) AND lifecycle_status='active'",
        "training": "SELECT * FROM public.person_training WHERE person_id=ANY(:ids) AND lifecycle_status='active'",
        "relatives": "SELECT * FROM public.person_relatives WHERE person_id=ANY(:ids) AND lifecycle_status='active'",
        "military": "SELECT * FROM public.person_military_service WHERE person_id=ANY(:ids) AND lifecycle_status='active'",
        "employment_biography": "SELECT * FROM public.person_external_employment WHERE person_id=ANY(:ids) AND lifecycle_status='active'",
        "employment_history": """
          SELECT person_id,org_unit_id,position_id,start_date,end_date,active_flag,is_primary,lifecycle_status
          FROM public.person_assignments WHERE person_id=ANY(:ids) AND active_flag IS TRUE
            AND is_primary IS TRUE AND lifecycle_status='active' AND start_date<=CURRENT_DATE
            AND (end_date IS NULL OR end_date>=CURRENT_DATE)
        """,
        "general": "SELECT person_id,full_name,last_name,first_name,middle_name,birth_date,iin,updated_at FROM public.persons WHERE person_id=ANY(:ids)",
        "additional": "SELECT person_id,additional_profile,updated_at FROM public.personnel_record_metadata WHERE person_id=ANY(:ids)",
    }
    for section, sql in sources.items():
        for row in conn.execute(text(sql), {"ids": person_ids}).mappings():
            person_id = int(row["person_id"])
            if section == "additional":
                profile = row.get("additional_profile") or {}
                if isinstance(profile, str):
                    try: profile = json.loads(profile)
                    except json.JSONDecodeError: profile = {}
                for target in ("foreign_languages", "awards", "academic_degrees_titles"):
                    result[person_id][target].append({"profile": profile, "updated_at": row.get("updated_at")})
            else:
                result[person_id][section].append(dict(row))
    return result


def _canonical_cell(f: dict[str, Any], section: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify one canonical card section; absence is a real result, never a placeholder."""
    source = _hash({"section": section, "source_type": "CANONICAL_HR", "records": records})
    target = _hash({"person": f["person_id"], "person_updated": f["person_updated_at"]})
    binding = _hash({key: str(f.get(key)) for key in ("stage0_cohort_run_id", "stage0_participant_id", "person_id", "employee_id", "org_unit_id", "employee_person_id", "is_active", "operational_status", "person_status", "merged_into_person_id")})
    base = {"stage_run_id": None, "stage1_run_id": None, "stage_participant_id": None,
            "stage1_participant_id": None, "pmf_run_id": None, "evidence_kind": "CANONICAL_CARD",
            "policy_version": CANONICAL_COHORT_POLICY_VERSION, "source_fingerprint": source,
            "target_fingerprint": target, "binding_fingerprint": binding}
    if not records:
        return {**base, "status_code": "NO_SOURCE_DATA", "reason_code": f"CANONICAL_{section.upper()}_ABSENT"}
    if section == "general":
        row = records[0]
        missing = _missing(("full_name", row.get("full_name")), ("last_name", row.get("last_name")),
                           ("first_name", row.get("first_name")), ("birth_date", row.get("birth_date")))
        if missing: return {**base, "status_code": "REVIEW_REQUIRED", "reason_code": f"GENERAL_MISSING_{missing.upper()}"}
        iin = str(row.get("iin") or "")
        if not iin or not iin.isdigit() or len(iin) != 12:
            return {**base, "status_code": "REVIEW_REQUIRED", "reason_code": "GENERAL_IIN_MISSING_OR_INVALID"}
    elif section == "education":
        invalid = next((r for r in records if r.get("education_kind") not in EDUCATION_KINDS), None)
        if invalid: return {**base, "status_code": "REVIEW_REQUIRED", "reason_code": "EDUCATION_INVALID_OR_MISSING_KIND"}
    elif section == "training":
        invalid = next((r for r in records if r.get("training_kind") not in TRAINING_KINDS), None)
        if invalid: return {**base, "status_code": "REVIEW_REQUIRED", "reason_code": "TRAINING_INVALID_OR_MISSING_KIND"}
    elif section == "relatives":
        invalid = next((r for r in records if r.get("relationship_type") not in RELATIONSHIP_TYPES or not str(r.get("full_name") or "").strip() or r.get("verification_status") not in VERIFICATION_STATUSES or r.get("source_type") not in SECTION_SOURCE_TYPES), None)
        if invalid: return {**base, "status_code": "REVIEW_REQUIRED", "reason_code": "RELATIVES_REQUIRED_FIELD_OR_ENUM_INVALID"}
    elif section == "military":
        invalid = next((r for r in records if r.get("record_kind") not in MILITARY_RECORD_KINDS or r.get("verification_status") not in VERIFICATION_STATUSES or r.get("lifecycle_status") not in MILITARY_LIFECYCLE_STATUSES or r.get("source_type") not in SECTION_SOURCE_TYPES), None)
        if invalid: return {**base, "status_code": "REVIEW_REQUIRED", "reason_code": "MILITARY_REQUIRED_FIELD_OR_ENUM_INVALID"}
        registration = [r for r in records if r.get("record_kind") != MILITARY_RECORD_KIND_NOT_APPLICABLE]
        if registration and not any(any(str(r.get(key) or "").strip() for key in ("obligation_status", "registration_category", "military_rank", "registration_status")) for r in registration):
            return {**base, "status_code": "REVIEW_REQUIRED", "reason_code": "MILITARY_REGISTRATION_STRUCTURED_FIELD_MISSING"}
    elif section == "employment_biography":
        invalid = next((r for r in records if r.get("record_kind") not in EXTERNAL_EMPLOYMENT_RECORD_KINDS or r.get("verification_status") not in EXTERNAL_EMPLOYMENT_VERIFICATION_STATUSES or r.get("lifecycle_status") not in LIFECYCLE_STATUSES), None)
        if invalid: return {**base, "status_code": "REVIEW_REQUIRED", "reason_code": "EMPLOYMENT_BIOGRAPHY_REQUIRED_FIELD_OR_ENUM_INVALID"}
        episode = next((r for r in records if r.get("record_kind") == "episode" and (not str(r.get("employer_name") or "").strip() or not str(r.get("position_title") or "").strip())), None)
        if episode: return {**base, "status_code": "REVIEW_REQUIRED", "reason_code": "EMPLOYMENT_BIOGRAPHY_EPISODE_EMPLOYER_OR_POSITION_MISSING"}
    elif section == "employment_history":
        if len(records) != 1: return {**base, "status_code": "REVIEW_REQUIRED", "reason_code": "EMPLOYMENT_HISTORY_PRIMARY_ASSIGNMENT_AMBIGUOUS"}
        missing = _missing(("org_unit_id", records[0].get("org_unit_id")), ("position_id", records[0].get("position_id")), ("start_date", records[0].get("start_date")))
        if missing: return {**base, "status_code": "REVIEW_REQUIRED", "reason_code": f"EMPLOYMENT_HISTORY_MISSING_{missing.upper()}"}
    else:
        profile = records[0].get("profile") if records else {}
        if not isinstance(profile, dict): return {**base, "status_code": "REVIEW_REQUIRED", "reason_code": "ADDITIONAL_PROFILE_INVALID"}
        if section == "foreign_languages":
            entries, none = profile.get("foreign_languages") or [], profile.get("foreign_languages_none") is True
            invalid = any(not str(x.get("language") or "").strip() or not str(x.get("proficiency") or "").strip() for x in entries if isinstance(x, dict))
        elif section == "awards":
            entries, none = profile.get("awards") or [], profile.get("awards_none") is True
            invalid = any(not (str(x.get("category") or "").strip() or str(x.get("name") or x.get("title") or "").strip()) for x in entries if isinstance(x, dict))
        else:
            entries = list(profile.get("academic_degrees") or []) + list(profile.get("academic_titles") or [])
            none = profile.get("academic_degrees_none") is True or profile.get("academic_titles_none") is True
            invalid = any(not (str(x.get("degree") or x.get("degree_other") or x.get("academic_title") or x.get("academic_title_other") or "").strip()) for x in entries if isinstance(x, dict))
        if not entries:
            return {**base, "status_code": "NO_SOURCE_DATA", "reason_code": f"CANONICAL_{section.upper()}_{'EXPLICIT_NONE' if none else 'ABSENT'}"}
        if invalid or any(not isinstance(x, dict) for x in entries):
            return {**base, "status_code": "REVIEW_REQUIRED", "reason_code": f"{section.upper()}_REQUIRED_FIELD_MISSING"}
    return {**base, "status_code": "AUTO_READY", "reason_code": "CANONICAL_REQUIRED_FIELDS_VALID"}


def _import_override_origin(conn: Connection, employee_id: int, row_id: int) -> str:
    """Return only the storage origin of an effective override, never its data."""
    from app.services.employee_import_profile_override_service import load_employee_override

    if load_employee_override(conn, employee_id) is not None:
        return "employee_import_profile_overrides"
    value = conn.execute(text("SELECT profile_override FROM public.hr_import_rows WHERE row_id=:row_id"),
                         {"row_id": row_id}).scalar_one_or_none()
    return "hr_import_rows.profile_override" if value else "none"


def _profile_validation_error(section: str, profile: dict[str, Any]) -> bool:
    """Use the dossier's existing profile override validation unchanged."""
    from app.services.hr_import_profile_override_service import (
        extract_editable_sections_override,
        validate_profile_override,
    )

    try:
        override = extract_editable_sections_override(profile)
        override_section = {"academic_degrees_titles": "degree"}.get(section, section)
        validate_profile_override({override_section: override.get(override_section, [])})
    except (TypeError, ValueError):
        return True
    return False


def _first_import_profile_problem(section: str, records: list[dict[str, Any]], profile: dict[str, Any]) -> str | None:
    """Return a non-PII, actionable first problem in dossier display order."""
    if section == "education":
        fields = (("institution", "EDUCATION_IMPORT_MISSING_INSTITUTION"),
                  ("specialty", "EDUCATION_IMPORT_MISSING_SPECIALTY"),
                  ("completed_at", "EDUCATION_IMPORT_MISSING_COMPLETED_AT"))
    elif section == "training":
        fields = (("title", "TRAINING_IMPORT_MISSING_TITLE"),
                  ("completed_at", "TRAINING_IMPORT_MISSING_COMPLETED_AT"),
                  ("hours", "TRAINING_IMPORT_MISSING_HOURS"))
    elif section == "awards":
        fields = (("title", "AWARDS_IMPORT_MISSING_TITLE"),
                  ("date", "AWARDS_IMPORT_MISSING_DATE"))
    else:
        fields = (("label", "ACADEMIC_DEGREES_TITLES_IMPORT_MISSING_LABEL"),
                  ("completed_at", "ACADEMIC_DEGREES_TITLES_IMPORT_MISSING_COMPLETED_AT"))
    for record in records:
        for field, reason in fields:
            value = record.get(field)
            if value is None or not str(value).strip():
                return reason
        if section == "training":
            try:
                float(record.get("hours"))
            except (TypeError, ValueError):
                return "TRAINING_IMPORT_HOURS_INVALID"
    if _profile_validation_error(section, profile):
        return f"{section.upper()}_IMPORT_DATE_OR_VALUE_INVALID"
    return None


def _selected_row_review_statuses(conn: Connection, *, row_id: int, section: str) -> set[str]:
    rows = conn.execute(text("""
        SELECT review_status
        FROM public.hr_import_normalized_records
        WHERE row_id=:row_id AND record_kind=:section AND review_status <> 'superseded'
    """), {"row_id": row_id, "section": section}).scalars().all()
    return {str(value) for value in rows if value}


def _import_profile_cell(conn: Connection, f: dict[str, Any], section: str,
                         card_cache: dict[int, dict[str, Any] | None] | None = None) -> dict[str, Any]:
    """Evaluate education/training from the exact legacy import-card profile.

    The cohort remains canonical.  This merely reuses the deterministic dossier
    read model as migration evidence and persists its row/batch/override origin.
    """
    from app.services.hr_import_employee_card_service import (
        EmployeeImportCardNotFoundError,
        get_employee_import_card,
    )

    base = {
        "stage_run_id": None, "stage1_run_id": None, "stage_participant_id": None,
        "stage1_participant_id": None, "pmf_run_id": None,
        "evidence_kind": "IMPORT_PROFILE", "policy_version": IMPORT_PROFILE_POLICY_VERSION,
    }
    profile_records_key = {
        "education": "education_records",
        "training": "training_records",
        "awards": "award_records",
    }.get(section)
    employee_id = int(f["employee_id"])
    if card_cache is not None and employee_id in card_cache:
        card = card_cache[employee_id]
    else:
        try:
            card = get_employee_import_card(conn, employee_id)
        except EmployeeImportCardNotFoundError:
            card = None
        if card_cache is not None:
            card_cache[employee_id] = card
    if card is None:
        source = _hash({"section": section, "employee_id": f["employee_id"], "import_card": None})
        return {**base, "status_code": "NO_SOURCE_DATA", "reason_code": f"{section.upper()}_IMPORT_PROFILE_ABSENT",
                "source_fingerprint": source, "target_fingerprint": _hash({"person": f["person_id"], "person_updated": f["person_updated_at"]}),
                "binding_fingerprint": _hash({"person": f["person_id"], "employee": f["employee_id"]}),
                "source_row_id": None, "source_batch_id": None,
                "import_profile_provenance": {"profile_source": "none"}}
    profile = card.get("profile") or {}
    records = (list(profile.get(profile_records_key) or []) if profile_records_key
               else list((profile.get("degrees") or {}).get("records") or []))
    row_id, batch_id = int(card["row_id"]), int(card["batch_id"])
    origin = _import_override_origin(conn, employee_id, row_id)
    provenance = {"batch_id": batch_id, "row_id": row_id, "override_origin": origin}
    source = _hash({"section": section, "profile": profile, "provenance": provenance})
    common = {**base, "source_fingerprint": source,
              "target_fingerprint": _hash({"person": f["person_id"], "person_updated": f["person_updated_at"]}),
              "binding_fingerprint": _hash({"person": f["person_id"], "employee": f["employee_id"]}),
              "source_row_id": row_id, "source_batch_id": batch_id,
              "import_profile_provenance": provenance}
    if not records:
        return {**common, "status_code": "NO_SOURCE_DATA", "reason_code": f"{section.upper()}_IMPORT_PROFILE_ABSENT"}
    problem = _first_import_profile_problem(section, records, profile)
    if problem:
        return {**common, "status_code": "REVIEW_REQUIRED", "reason_code": problem}
    review_statuses = (_selected_row_review_statuses(conn, row_id=row_id, section=section)
                       if section in {"education", "training"} else set())
    if "rejected" in review_statuses:
        return {**common, "status_code": "REJECTED", "reason_code": f"{section.upper()}_IMPORT_REVIEW_REJECTED"}
    if "pending" in review_statuses:
        # Match the established normalized-record policy: pending review alone
        # does not negate a fully parsed, currently valid record.  The pending
        # fact stays visible in the reason/provenance and in the fingerprint.
        return {**common, "status_code": "AUTO_READY", "reason_code": f"{section.upper()}_IMPORT_REVIEW_PENDING_AUTO_READY"}
    if review_statuses and review_statuses <= {"approved", "promoted"}:
        return {**common, "status_code": "ACCEPTED", "reason_code": f"{section.upper()}_IMPORT_REVIEW_APPROVED"}
    return {**common, "status_code": "AUTO_READY", "reason_code": f"{section.upper()}_IMPORT_REQUIRED_FIELDS_VALID"}

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
    facts = _facts(conn, universe_id)
    rows=[]; candidates=_candidate_cache(conn,universe_id)
    import_card_cache: dict[int, dict[str, Any] | None] = {}
    canonical_evidence = _canonical_section_evidence(conn, facts) if any(f.get("source_type") == "CANONICAL_HR" for f in facts) else {}
    previous={(int(x["person_id"]),str(x["section_code"])):dict(x) for x in conn.execute(text("SELECT person_id,section_code,status_code,source_fingerprint,policy_version FROM ppr_migration_section_status_projection WHERE universe_id=:u FOR UPDATE"),{"u":universe_id}).mappings()}
    for fact in facts:
        for section in SECTIONS:
            if fact.get("source_type") == "CANONICAL_HR":
                status = (_import_profile_cell(conn, fact, section, import_card_cache)
                          if section in {"education", "training", "awards", "academic_degrees_titles"}
                          else _canonical_cell(fact, section, canonical_evidence[int(fact["person_id"])][section]))
            else:
                candidate=candidates.get((int(fact["stage0_cohort_run_id"]),int(fact["person_id"]),section))
                status = _status(conn,fact,section,candidate,previous.get((int(fact["person_id"]),section)))
            rows.append({**fact,"section":section,**status})
    conn.execute(text("DELETE FROM public.ppr_migration_section_status_projection WHERE universe_id=:u"),{"u":universe_id})
    for r in rows:
        conn.execute(text("""INSERT INTO public.ppr_migration_section_status_projection(universe_id,person_id,employee_context_id,org_unit_id,section_code,status_code,reason_code,source_cohort_run_id,source_batch_id,source_row_id,import_profile_provenance,stage_run_id,stage1_run_id,stage_participant_id,stage1_participant_id,pmf_run_id,evidence_kind,policy_version,source_fingerprint,target_fingerprint,binding_fingerprint) VALUES(:u,:person_id,:employee_id,:org_unit_id,:section,:status_code,:reason_code,:stage0_cohort_run_id,:source_batch_id,:source_row_id,CAST(:import_profile_provenance AS jsonb),:stage_run_id,:stage1_run_id,:stage_participant_id,:stage1_participant_id,:pmf_run_id,:evidence_kind,:policy_version,:source_fingerprint,:target_fingerprint,:binding_fingerprint)"""),{
            **r, "u": universe_id,
            "source_batch_id": r.get("source_batch_id"),
            "import_profile_provenance": json.dumps(r.get("import_profile_provenance")) if r.get("import_profile_provenance") is not None else None,
        })
    return len(rows)

def list_projection_for_scope(conn: Connection, *, universe_id: int, org_unit_ids: list[int] | None) -> list[dict[str, Any]]:
    where="universe_id=:u" if org_unit_ids is None else "universe_id=:u AND org_unit_id=ANY(:units)"
    return [dict(r) for r in conn.execute(text(f"SELECT * FROM public.ppr_migration_section_status_projection WHERE {where} ORDER BY person_id,section_code"),{"u":universe_id,"units":org_unit_ids}).mappings()]
