"""Stage 3 training envelope over PMF drafts.

The envelope deliberately persists only technical anchors and hashes.  Fragment payload
lives in existing normalized records until execution, then in PMF draft items.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.control_list_import.domain.person_candidate import NormalizedPlainText
from app.control_list_import.domain.training_candidate import (
    NormalizedCompletionDate,
    NormalizedCompletionYear,
    NormalizedDurationHours,
    TrainingCandidate,
    TrainingReadinessStatus,
)
from app.control_list_import.training_normalization.records import parse_training_fragment
from app.db.models.personnel_migration import (
    TRAINING_KIND_CONTINUING_EDUCATION,
    TRAINING_KIND_COURSE,
    TRAINING_KIND_MASTER_CLASS,
    TRAINING_KIND_SEMINAR,
)

POLICY_VERSION = "TRAINING-PROPOSAL-v1"
PARSER_VERSION = "training_normalization.records:v1"
REVIEW_REQUIRED = "REVIEW_REQUIRED"


class _TrainingClassification:
    def __init__(self, *, kind: str | None, outcome: str, reason_code: str) -> None:
        self.kind = kind
        self.outcome = outcome
        self.reason_code = reason_code


# These codes are emitted by TrainingNormalizationService.  ``other`` is not a
# fallback: a source value without a one-to-one mapping is a human-review case.
_TRAINING_TYPE_TO_KIND = {
    "QUAL_UPGRADE": TRAINING_KIND_CONTINUING_EDUCATION,
    "COURSE": TRAINING_KIND_COURSE,
    "SEMINAR": TRAINING_KIND_SEMINAR,
    "WORKSHOP": TRAINING_KIND_MASTER_CLASS,
}


def classify_training_kind(training_type: str | None) -> _TrainingClassification:
    normalized = _normalize(training_type)
    if not normalized:
        return _TrainingClassification(kind=None, outcome=REVIEW_REQUIRED, reason_code="STAGE3_TRAINING_TYPE_MISSING")
    kind = _TRAINING_TYPE_TO_KIND.get(normalized.upper())
    if kind is None:
        return _TrainingClassification(kind=None, outcome=REVIEW_REQUIRED, reason_code="STAGE3_TRAINING_TYPE_UNMAPPED")
    return _TrainingClassification(kind=kind, outcome="READY_TO_ADD", reason_code="STAGE3_READY")
from app.ppr.application.config import (
    ppr_pmf_bridge_enabled,
    ppr_stage3_training_accept_enabled,
    ppr_stage3_training_execution_enabled,
    ppr_stage3_training_preview_enabled,
)
from app.security.ppr_stage3_permissions import can_view_training_certificate_details
from app.services.personnel_migration_commit_service import add_draft_item, commit_run, create_draft_run


SAFE_OPERATION_ERROR_CODES = frozenset({
    "STAGE3_RESUME_STALE", "STAGE3_FRAGMENT_REVIEW_REQUIRED",
    "STAGE3_EMPLOYEE_PERSON_LINK_STALE", "STAGE3_EXECUTION_ERROR",
})


class Stage3Error(RuntimeError):
    code = "STAGE3_ERROR"
class Stage3NotFoundError(Stage3Error):
    code = "STAGE3_RUN_NOT_FOUND"
class Stage3ConflictError(Stage3Error):
    code = "STAGE3_CONFLICT"
class Stage3ValidationError(Stage3Error):
    code = "STAGE3_VALIDATION"


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _key(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _safe_error(exc: Exception) -> tuple[str, str]:
    # A message is never promoted blindly to a public/error code.  Stage3
    # operations may carry a precise instance code, but only this finite
    # allowlist can cross the rollback boundary; all other failures collapse
    # to the generic safe code while their text is represented only by a hash.
    candidate = str(exc.args[0]) if isinstance(exc, Stage3Error) and exc.args else ""
    code = candidate if candidate in SAFE_OPERATION_ERROR_CODES else "STAGE3_EXECUTION_ERROR"
    return code, _hash({"code": code, "type": type(exc).__name__})


def _normalize(value: Any) -> str | None:
    result = " ".join(str(value or "").strip().split())
    return result or None


def _certificate_hmac(value: Any) -> str | None:
    value = _normalize(value)
    if not value:
        return None
    secret = os.environ.get("PPR_STAGE3_CERTIFICATE_HMAC_SECRET", "")
    if not secret:
        raise Stage3ValidationError("STAGE3_CERTIFICATE_HMAC_SECRET_REQUIRED")
    return "v1:" + hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def _run(conn: Connection, run_id: int, *, lock: bool = False) -> dict[str, Any]:
    row = conn.execute(text(f"SELECT * FROM public.ppr_stage_runs WHERE stage_run_id=:id AND stage_code='training'{' FOR UPDATE' if lock else ''}"), {"id": run_id}).mappings().one_or_none()
    if row is None:
        raise Stage3NotFoundError("STAGE3_RUN_NOT_FOUND")
    return dict(row)


def _participant_rows(conn: Connection, run_id: int, *, lock: bool = False) -> list[dict[str, Any]]:
    return [dict(x) for x in conn.execute(text(f"SELECT * FROM public.ppr_stage_run_participants WHERE stage_run_id=:id ORDER BY position{' FOR UPDATE' if lock else ''}"), {"id": run_id}).mappings()]


def _fragments(conn: Connection, participant: dict[str, Any], *, lock: bool = False) -> list[dict[str, Any]]:
    # ``hr_import_rows`` is a nullable outer-join side.  PostgreSQL forbids a
    # blanket FOR UPDATE there; the normalized source rows are the lock target.
    suffix = " FOR UPDATE OF nr" if lock else ""
    rows = conn.execute(text(f"""
        SELECT nr.normalized_record_id,nr.batch_id,nr.row_id,nr.employee_id,nr.fragment_index,
               nr.source_field,nr.source_record_key,nr.record_kind,nr.title,nr.provider,nr.hours,
               nr.source_text,nr.specialty_text,nr.document_number,nr.start_date,nr.end_date,nr.issue_date,
               nr.parse_method,nr.confidence,nr.review_status,nr.reviewed_at,nr.reviewed_by,nr.review_notes,
               nr.promoted_document_id,nr.updated_at,
               r.source_row_number
          FROM public.ppr_stage0_cohort_participants s
          JOIN public.hr_import_normalized_records nr ON nr.row_id=s.source_row_id
         LEFT JOIN public.hr_import_rows r ON r.row_id=nr.row_id
         WHERE s.stage0_participant_id=:stage0
           AND nr.employee_id=:employee AND nr.record_kind='training'
         ORDER BY nr.normalized_record_id{suffix}
    """), {"stage0": participant["stage0_participant_id"], "employee": participant["employee_id"]}).mappings().all()
    return [dict(x) for x in rows]


def _canonical(conn: Connection, person_id: int, *, lock: bool = False) -> list[dict[str, Any]]:
    return [dict(x) for x in conn.execute(text(f"""
        SELECT training_id,training_kind,title,organization_name,hours,completed_at,
               certificate_number,import_batch_id,import_row_id,metadata,updated_at
          FROM public.person_training
         WHERE person_id=:person AND lifecycle_status='active'
         ORDER BY training_id{' FOR UPDATE' if lock else ''}
    """), {"person": person_id}).mappings()]


def _plain(raw: Any, value: Any) -> NormalizedPlainText:
    return NormalizedPlainText(raw=str(raw or ""), text=_normalize(value))


def _date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _hours(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _candidate_from_persisted_fragment(fragment: dict[str, Any]) -> TrainingCandidate:
    """Rehydrate the actual TrainingCandidate shape from persisted source values.

    The normalized-record schema predates WP-CL-009 and persists the stable
    projection (title/provider/hours/dates/certificate) rather than a JSON copy
    of the candidate.  Parsing the retained source restores ``training_type``
    and field issues; persisted normalized values then remain authoritative for
    the fields the schema does store.  No generic education payload is used.
    """
    parsed = parse_training_fragment(str(fragment.get("source_text") or ""), fragment_index=int(fragment["fragment_index"]))
    completed = _date(fragment.get("end_date") or fragment.get("issue_date"))
    year = completed.year if completed else parsed.completion_year.value
    persisted_hours = _hours(fragment.get("hours"))
    candidate = TrainingCandidate(
        import_run_id=int(fragment["batch_id"]),
        profile_id=None,
        profile_code=None,
        profile_version=None,
        source_row_id=int(fragment["row_id"]),
        source_sheet_name="",
        source_excel_row_number=int(fragment.get("source_row_number") or 0),
        source_column_index=0,
        source_column_letter="",
        source_fragment_index=int(fragment["fragment_index"]),
        raw_fragment=str(fragment.get("source_text") or ""),
        # The persisted source binds to an employee; _derive validates that
        # employee's current person binding before this projection is frozen.
        matched_person_id=fragment.get("_matched_person_id"),
        training_title=_plain(fragment.get("title"), fragment.get("title") or parsed.training_title.text),
        provider_name=_plain(fragment.get("provider"), fragment.get("provider") or parsed.provider_name.text),
        completion_date=NormalizedCompletionDate(raw=str(completed or parsed.completion_date.raw or ""), value=completed or parsed.completion_date.value, issues=parsed.completion_date.issues if completed is None else ()),
        completion_year=NormalizedCompletionYear(raw=str(year or parsed.completion_year.raw or ""), value=year, issues=parsed.completion_year.issues if year is None else ()),
        certificate_number=_plain(fragment.get("document_number"), fragment.get("document_number") or parsed.certificate_number.text),
        duration_hours=NormalizedDurationHours(raw=str(fragment.get("hours") if fragment.get("hours") is not None else parsed.duration_hours.raw or ""), value=persisted_hours if persisted_hours is not None else parsed.duration_hours.value, issues=parsed.duration_hours.issues if persisted_hours is None else ()),
        training_type=parsed.training_type,
        field_issues=dict(parsed.field_issues),
        readiness_status=TrainingReadinessStatus.NORMALIZATION_READY,
    )
    return candidate


def _candidate_is_deterministic(candidate: TrainingCandidate) -> bool:
    return bool(
        candidate.training_title.text
        and (candidate.completion_date.is_valid or candidate.completion_year.is_valid)
        and not candidate.all_issues
    )


def _temporal_key(completed_at: Any, completion_year: int | None) -> tuple[str, str | int] | None:
    completed = _date(completed_at)
    if completed:
        return ("date", completed.isoformat())
    if completion_year:
        return ("year", completion_year)
    return None


def _candidate_projection(candidate: TrainingCandidate) -> dict[str, Any]:
    """Immutable, structured TrainingCandidate projection; never include raw_fragment."""
    return {
        "training_title": candidate.training_title.text,
        "provider_name": candidate.provider_name.text,
        "completion_date": str(candidate.completion_date.value or "") or None,
        "completion_year": candidate.completion_year.value,
        "certificate_number": candidate.certificate_number.text,
        "duration_hours": str(candidate.duration_hours.value) if candidate.duration_hours.value is not None else None,
        "training_type": candidate.training_type.text,
        "matched_person_id": candidate.matched_person_id,
        "field_issues": candidate.field_issues,
        "readiness_status": candidate.readiness_status.value,
    }


def _candidate_from_projection(value: dict[str, Any]) -> TrainingCandidate:
    completed = _date(value.get("completion_date"))
    duration = _hours(value.get("duration_hours"))
    return TrainingCandidate(
        import_run_id=None, profile_id=None, profile_code=None, profile_version=None,
        source_row_id=None, source_sheet_name="", source_excel_row_number=0,
        source_column_index=0, source_column_letter="", source_fragment_index=0,
        raw_fragment="", matched_person_id=value.get("matched_person_id"),
        training_title=_plain(value.get("training_title"), value.get("training_title")),
        provider_name=_plain(value.get("provider_name"), value.get("provider_name")),
        completion_date=NormalizedCompletionDate(raw=str(value.get("completion_date") or ""), value=completed),
        completion_year=NormalizedCompletionYear(raw=str(value.get("completion_year") or ""), value=value.get("completion_year")),
        certificate_number=_plain(value.get("certificate_number"), value.get("certificate_number")),
        duration_hours=NormalizedDurationHours(raw=str(value.get("duration_hours") or ""), value=duration),
        training_type=_plain(value.get("training_type"), value.get("training_type")),
        field_issues={str(key): tuple(items) for key, items in dict(value.get("field_issues") or {}).items()},
        readiness_status=TrainingReadinessStatus(str(value.get("readiness_status") or TrainingReadinessStatus.REVIEW_REQUIRED)),
    )


def _snapshot_fragment(fragment: dict[str, Any], candidate: TrainingCandidate) -> dict[str, Any]:
    """Persist only anchors/provenance and structured normalized data, never source text."""
    anchors = {key: fragment.get(key) for key in (
        "normalized_record_id", "batch_id", "row_id", "employee_id", "fragment_index",
        "source_field", "source_record_key", "review_status", "reviewed_at", "reviewed_by",
        "review_notes", "promoted_document_id", "updated_at",
    )}
    return {
        "anchor": anchors,
        "source_hash": _hash({"source_text": fragment.get("source_text"), "source_record_key": fragment.get("source_record_key")}),
        "training_candidate": _candidate_projection(candidate),
    }


def _mark_in_run_duplicates(snapshot: dict[str, Any]) -> None:
    """Freeze one deterministic winner per exact proposal identity in a run."""
    seen: set[tuple[Any, ...]] = set()
    participants = dict(snapshot.get("training_candidates") or {})
    for participant_id in sorted(participants, key=lambda value: int(value)):
        participant = dict(participants[participant_id])
        binding = dict(participant.get("person_binding") or {})
        expected_person_id = binding.get("person_id")
        fragments = list(participant.get("fragments") or [])
        for fragment in sorted(fragments, key=lambda value: (int(dict(value.get("anchor") or {}).get("fragment_index") or 0), int(dict(value.get("anchor") or {}).get("normalized_record_id") or 0))):
            candidate = _candidate_from_projection(dict(fragment.get("training_candidate") or {}))
            classification = classify_training_kind(candidate.training_type.text)
            # A run-wide identity is still scoped to the matched person.  A
            # mismatch is fail-closed later in _fragment_view; it must never
            # suppress another person's otherwise independent training.
            if (
                expected_person_id is None
                or candidate.matched_person_id is None
                or int(candidate.matched_person_id) != int(expected_person_id)
                or not _candidate_is_deterministic(candidate)
                or classification.outcome == REVIEW_REQUIRED
            ):
                continue
            identity = (
                int(candidate.matched_person_id),
                candidate.provider_name.text.casefold() if candidate.provider_name.text else None,
                candidate.training_title.text.casefold() if candidate.training_title.text else None,
                _temporal_key(candidate.completion_date.value, candidate.completion_year.value),
                str(candidate.duration_hours.value) if candidate.duration_hours.value is not None else None,
                _certificate_hmac(candidate.certificate_number.text),
            )
            if identity in seen:
                fragment["dedup_outcome"] = "DUPLICATE_IN_RUN"
            else:
                seen.add(identity)


def _fragment_view(fragment: dict[str, Any], canon: list[dict[str, Any]], *, stage_run_id: int, participant_id: int, version: int, candidate: TrainingCandidate | None = None, expected_person_id: int | None = None, forced_outcome: str | None = None) -> dict[str, Any]:
    candidate = candidate or _candidate_from_persisted_fragment(fragment)
    title = candidate.training_title.text
    classification = classify_training_kind(candidate.training_type.text)
    proposal = {
        "training_kind": classification.kind,
        "title": title,
        "organization_name": candidate.provider_name.text,
        "hours": str(candidate.duration_hours.value) if candidate.duration_hours.value is not None else None,
        "completed_at": str(candidate.completion_date.value or "") or None,
        "certificate_number": candidate.certificate_number.text,
    }
    source_key = str(fragment["source_record_key"])
    item_key = _key(f"stage3-pmf-item:v1:{stage_run_id}:{participant_id}:{version}:{source_key}:{fragment['fragment_index']}")
    source = {"source_row_number": fragment.get("source_row_number"), "fragment_index": int(fragment["fragment_index"]), "normalized_record_id": int(fragment["normalized_record_id"]), "provider_name": candidate.provider_name.text, "title": title, "completion_year": candidate.completion_year.value, "duration_hours": proposal["hours"], "training_type": candidate.training_type.text}
    current: dict[str, Any] | None = None
    outcome, reason = classification.outcome, classification.reason_code
    if expected_person_id is not None and candidate.matched_person_id != expected_person_id:
        outcome, reason = REVIEW_REQUIRED, "STAGE3_CANDIDATE_PERSON_MISMATCH"
    elif not _candidate_is_deterministic(candidate):
        outcome, reason = REVIEW_REQUIRED, "STAGE3_TRAINING_CANDIDATE_INCOMPLETE"
    elif classification.outcome != REVIEW_REQUIRED and fragment["review_status"] not in {"approved", "promoted"}:
        outcome, reason = REVIEW_REQUIRED, "STAGE3_SOURCE_REVIEW_STATUS"
    elif classification.outcome != REVIEW_REQUIRED:
        proposal_temporal = _temporal_key(proposal["completed_at"], candidate.completion_year.value)
        proposal_cert = _certificate_hmac(proposal["certificate_number"])
        exact: list[dict[str, Any]] = []
        possible: list[dict[str, Any]] = []
        contradictory: list[dict[str, Any]] = []
        for record in canon:
            same_name = (_normalize(record.get("organization_name")) or "").casefold() == (proposal["organization_name"] or "").casefold() and (_normalize(record.get("title")) or "").casefold() == (title or "").casefold()
            if not same_name:
                continue
            record_temporal = _temporal_key(record.get("completed_at"), None)
            same_temporal = record_temporal == proposal_temporal or (proposal_temporal and proposal_temporal[0] == "year" and _date(record.get("completed_at")) and _date(record.get("completed_at")).year == proposal_temporal[1])
            same_hours = _hours(record.get("hours")) == candidate.duration_hours.value
            same_certificate = _certificate_hmac(record.get("certificate_number")) == proposal_cert
            if same_temporal and same_hours and same_certificate:
                exact.append(record)
            elif same_temporal and (same_hours or same_certificate):
                possible.append(record)
            else:
                contradictory.append(record)
        if len(exact) == 1:
            current = {k: exact[0].get(k) for k in ("training_kind", "title", "organization_name", "hours", "completed_at", "certificate_number")}
            outcome, reason = "ALREADY_APPLIED", "STAGE3_CANONICAL_EXACT_DUPLICATE"
        elif len(exact) > 1:
            outcome, reason = REVIEW_REQUIRED, "STAGE3_CANONICAL_AMBIGUOUS_EXACT_DUPLICATE"
        elif possible:
            current = {k: possible[0].get(k) for k in ("training_kind", "title", "organization_name", "hours", "completed_at", "certificate_number")}
            outcome, reason = REVIEW_REQUIRED, "STAGE3_CANONICAL_POSSIBLE_DUPLICATE"
        elif contradictory:
            current = {k: contradictory[0].get(k) for k in ("training_kind", "title", "organization_name", "hours", "completed_at", "certificate_number")}
            outcome, reason = REVIEW_REQUIRED, "STAGE3_CANONICAL_CONTRADICTORY_RECORD"
    if fragment.get("promoted_document_id") and outcome != "ALREADY_APPLIED":
        outcome, reason = REVIEW_REQUIRED, "STAGE3_PROMOTED_MATCH_NOT_EXACT"
    if forced_outcome == "DUPLICATE_IN_RUN":
        outcome, reason = "DUPLICATE_IN_RUN", "STAGE3_EXACT_DUPLICATE_IN_RUN"
    source_snapshot = {key: fragment.get(key) for key in ("normalized_record_id", "batch_id", "row_id", "employee_id", "fragment_index", "source_field", "source_record_key", "title", "provider", "hours", "source_text", "document_number", "end_date", "issue_date", "parse_method", "review_status", "reviewed_at", "reviewed_by", "review_notes", "promoted_document_id", "updated_at")}
    candidate_snapshot = {"title": candidate.training_title.text, "provider_name": candidate.provider_name.text, "completion_date": str(candidate.completion_date.value or ""), "completion_year": candidate.completion_year.value, "duration_hours": str(candidate.duration_hours.value or ""), "training_type": candidate.training_type.text, "certificate_hmac": _certificate_hmac(candidate.certificate_number.text), "issues": candidate.field_issues, "readiness": candidate.readiness_status.value}
    return {"normalized_record_id": int(fragment["normalized_record_id"]), "import_batch_id": int(fragment["batch_id"]), "import_row_id": int(fragment["row_id"]), "source_record_key": source_key, "fragment_index": int(fragment["fragment_index"]), "source": source, "current": current or {}, "proposal": proposal, "outcome": outcome, "reason_code": reason, "item_key": item_key, "source_fingerprint": _hash({"source_snapshot": source_snapshot, "training_candidate": candidate_snapshot, "policy_version": POLICY_VERSION, "parser_version": PARSER_VERSION, "outcome": outcome, "proposal": proposal}), "snapshot_fragment": _snapshot_fragment(fragment, candidate)}


def _stale_fingerprint(*, participant: dict[str, Any], state: dict[str, Any], views: list[dict[str, Any]], canon: list[dict[str, Any]]) -> str:
    """Hash immutable source/candidate/binding/canonical preconditions only."""
    canonical_projection = [
        {
            "training_id": record["training_id"],
            "training_kind": record["training_kind"],
            "title": _normalize(record.get("title")),
            "provider_name": _normalize(record.get("organization_name")),
            "hours": str(_hours(record.get("hours"))) if _hours(record.get("hours")) is not None else "",
            "completed_at": str(record.get("completed_at") or ""),
            "certificate_hmac": _certificate_hmac(record.get("certificate_number")),
            "updated_at": str(record.get("updated_at") or ""),
        }
        for record in canon
    ]
    return _hash({"employee":participant["employee_id"],"person_binding":{"employee_id":state["employee_id"],"person_id":state["employee_person_id"],"is_active":state["is_active"],"operational_status":state["operational_status"]},"fragments":[{"id":x["normalized_record_id"],"f":x["source_fingerprint"]} for x in views], "canonical_training_projection":canonical_projection,"person_updated":state["person_updated_at"],"policy":POLICY_VERSION,"parser":PARSER_VERSION})


def _approval_decision_fingerprint(parts: list[dict[str, Any]]) -> str:
    """Fingerprint HR decisions separately from immutable participant state.

    Execution transitions (PENDING -> COMPLETED) are deliberately excluded;
    only an explicit skip is an HR decision that requires a fresh approval.
    """
    decisions = []
    for participant in sorted(parts, key=lambda value: int(value["stage_run_participant_id"])):
        skipped = participant.get("status") == "SKIPPED_BY_DECISION"
        decisions.append({
            "participant_id": int(participant["stage_run_participant_id"]),
            "skipped": skipped,
            "skipped_by_user_id": participant.get("skipped_by_user_id") if skipped else None,
            "skipped_at": str(participant.get("skipped_at") or "") if skipped else "",
            "skip_reason": participant.get("skip_reason") if skipped else None,
        })
    return _hash({"version": "stage3-training-approval-decisions:v1", "decisions": decisions})


def _approved_decision_fingerprint(run: dict[str, Any]) -> str | None:
    approval = dict(dict(run.get("safe_snapshot") or {}).get("approval") or {})
    value = approval.get("decision_fingerprint")
    return str(value) if value else None


def _derive(conn: Connection, participant: dict[str, Any], *, stage_run_id: int, lock: bool = False, frozen_fragments: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    state = conn.execute(text(f"""
      SELECT e.employee_id,e.person_id employee_person_id,e.is_active,e.operational_status,
             p.person_id,p.updated_at person_updated_at
        FROM public.employees e JOIN public.persons p ON p.person_id=:person
       WHERE e.employee_id=:employee{' FOR UPDATE' if lock else ''}
    """), {"employee": participant["employee_id"], "person": participant["person_id"]}).mappings().one_or_none()
    if state is None or not state["is_active"] or state["operational_status"] != "active" or int(state["employee_person_id"]) != int(participant["person_id"]):
        raise Stage3ConflictError("STAGE3_EMPLOYEE_PERSON_LINK_STALE")
    fragments = _fragments(conn, participant, lock=lock)
    for fragment in fragments:
        fragment["_matched_person_id"] = int(participant["person_id"])
    canon = _canonical(conn, int(participant["person_id"]), lock=lock)
    if frozen_fragments is None:
        views = [_fragment_view(x, canon, stage_run_id=stage_run_id, participant_id=int(participant.get("stage_run_participant_id") or 0), version=int(participant.get("participant_snapshot_version") or 1), expected_person_id=int(participant["person_id"])) for x in fragments]
    else:
        live_by_id = {int(item["normalized_record_id"]): item for item in fragments}
        views = []
        for frozen in frozen_fragments:
            anchor = dict(frozen.get("anchor") or {})
            record_id = int(anchor.get("normalized_record_id") or 0)
            live = live_by_id.get(record_id)
            if live is None or _hash({"source_text": live.get("source_text"), "source_record_key": live.get("source_record_key")}) != frozen.get("source_hash"):
                views.append({"outcome": REVIEW_REQUIRED, "reason_code": "STAGE3_SOURCE_SNAPSHOT_STALE", "source": {}, "current": {}, "proposal": {}, "source_fingerprint": _hash({"stale": record_id}), "fragment_index": int(anchor.get("fragment_index") or 0), "source_record_key": str(anchor.get("source_record_key") or ""), "normalized_record_id": record_id, "item_key": ""})
                continue
            views.append(_fragment_view(live, canon, stage_run_id=stage_run_id, participant_id=int(participant.get("stage_run_participant_id") or 0), version=int(participant.get("participant_snapshot_version") or 1), candidate=_candidate_from_projection(dict(frozen.get("training_candidate") or {})), expected_person_id=int(participant["person_id"]), forced_outcome=frozen.get("dedup_outcome")))
    if not views:
        views = [{"outcome": REVIEW_REQUIRED, "reason_code": "STAGE3_EDUCATION_SOURCE_MISSING", "source": {}, "current": {}, "proposal": {}, "source_fingerprint": _hash({"missing":True}), "fragment_index": 0, "source_record_key": "", "normalized_record_id": 0, "item_key": ""}]
    fpr = _stale_fingerprint(participant=participant, state=dict(state), views=views, canon=canon)
    return {"fragments": views, "fingerprint": fpr}


def _frozen_fragments(run: dict[str, Any], participant: dict[str, Any]) -> list[dict[str, Any]] | None:
    snapshot = dict(run.get("safe_snapshot") or {})
    if run.get("stage_code") != "training":
        return None
    if run.get("policy_version") != POLICY_VERSION or snapshot.get("policy_version") != POLICY_VERSION or snapshot.get("parser_version") != PARSER_VERSION:
        raise Stage3ConflictError("STAGE3_TRAINING_SNAPSHOT_VERSION_STALE")
    participants = dict(snapshot.get("training_candidates") or {})
    frozen = participants.get(str(participant["stage0_participant_id"]))
    if not isinstance(frozen, dict) or not isinstance(frozen.get("fragments"), list):
        raise Stage3ConflictError("STAGE3_TRAINING_SNAPSHOT_MISSING")
    binding = dict(frozen.get("person_binding") or {})
    if binding.get("employee_id") != participant.get("employee_id") or binding.get("person_id") != participant.get("person_id"):
        raise Stage3ConflictError("STAGE3_TRAINING_SNAPSHOT_PERSON_STALE")
    return list(frozen["fragments"])


def _view_run(conn: Connection, run_id: int) -> dict[str, Any]:
    run = _run(conn, run_id)
    # Snapshot can contain restricted certificate values; it is never an API DTO.
    public_run = {key: value for key, value in run.items() if key != "safe_snapshot"}
    participants = _participant_rows(conn, run_id)
    for p in participants:
        d = _derive(conn, p, stage_run_id=run_id, frozen_fragments=_frozen_fragments(run, p))
        p["fragments"] = d["fragments"]
    return {"run": public_run, "participants": participants, "counts": dict(Counter(x["status"] for x in participants))}


def redacted_view_run_stage3(conn: Connection, *, run_id: int, user: dict) -> dict[str, Any]:
    return redact_stage3_dto(_view_run(conn, run_id), user=user)


def redact_stage3_dto(value: Any, *, user: dict) -> Any:
    """Remove certificate detail from every Stage-3 response shape, fail closed."""
    if can_view_training_certificate_details(user):
        return value
    if isinstance(value, dict):
        return {
            key: redact_stage3_dto(item, user=user)
            for key, item in value.items()
            if key != "certificate_number"
        }
    if isinstance(value, list):
        return [redact_stage3_dto(item, user=user) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_stage3_dto(item, user=user) for item in value)
    return value


def _preview_material_stage3(conn: Connection, *, stage0_cohort_run_id: int) -> dict[str, Any]:
    """Read-only half of PREVIEW.

    The caller owns a REPEATABLE READ, READ ONLY transaction.  This function
    deliberately does not touch envelope or PMF tables.
    """
    if not ppr_stage3_training_preview_enabled():
        raise Stage3ValidationError("STAGE3_PREVIEW_DISABLED")
    cohort = [dict(x) for x in conn.execute(text("SELECT * FROM public.ppr_stage0_cohort_participants WHERE stage0_cohort_run_id=:id ORDER BY position"), {"id":stage0_cohort_run_id}).mappings()]
    if not cohort:
        raise Stage3ValidationError("STAGE3_COHORT_EMPTY_OR_NOT_FOUND")
    provisional = [{"stage0_participant_id":p["stage0_participant_id"],"employee_id":p["employee_id"],"person_id":p["person_id"],"participant_snapshot_version":1} for p in cohort]
    derived = [(p, _derive(conn, p, stage_run_id=0)) for p in provisional]
    fingerprint = _hash({"cohort":stage0_cohort_run_id,"policy":POLICY_VERSION,"parser":PARSER_VERSION,"participants":[{"id":p["stage0_participant_id"],"fingerprint":value["fingerprint"]} for p, value in derived]})
    snapshot = {
        "schema_version": "stage3-training-candidate-snapshot:v1",
        "policy_version": POLICY_VERSION,
        "parser_version": PARSER_VERSION,
        "training_candidates": {
            str(p["stage0_participant_id"]): {
                "person_binding": {"employee_id": p["employee_id"], "person_id": p["person_id"]},
                "fragments": [fragment["snapshot_fragment"] for fragment in value["fragments"] if fragment.get("normalized_record_id")],
            }
            for p, value in derived
        },
    }
    _mark_in_run_duplicates(snapshot)
    return {"stage0_cohort_run_id": stage0_cohort_run_id, "preview_fingerprint": fingerprint, "participant_count": len(cohort), "safe_snapshot": snapshot}


def compute_preview_stage3(conn: Connection, *, stage0_cohort_run_id: int) -> dict[str, Any]:
    material = _preview_material_stage3(conn, stage0_cohort_run_id=stage0_cohort_run_id)
    return {key: value for key, value in material.items() if key != "safe_snapshot"}


def persist_preview_stage3(conn: Connection, *, stage0_cohort_run_id: int, actor_user_id: int, expected_preview_fingerprint: str) -> dict[str, Any]:
    """Short serializable write half of PREVIEW.

    The advisory lock serialises competing freezes of the same Stage 0 cohort;
    recalculation under that lock makes a stale browser preview fail closed.
    """
    conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key":f"PPR_STAGE3:{stage0_cohort_run_id}"})
    try:
        computed = _preview_material_stage3(conn, stage0_cohort_run_id=stage0_cohort_run_id)
    except Stage3ConflictError as exc:
        raise Stage3ConflictError("STAGE3_PREVIEW_STALE") from exc
    fingerprint = computed["preview_fingerprint"]
    if fingerprint != expected_preview_fingerprint:
        raise Stage3ConflictError("STAGE3_PREVIEW_STALE")
    cohort = [dict(x) for x in conn.execute(text("SELECT * FROM public.ppr_stage0_cohort_participants WHERE stage0_cohort_run_id=:id ORDER BY position FOR UPDATE"), {"id":stage0_cohort_run_id}).mappings()]
    existing = conn.execute(text("SELECT stage_run_id FROM public.ppr_stage_runs WHERE stage_code='training' AND stage0_cohort_run_id=:cohort AND preview_fingerprint=:f"), {"cohort":stage0_cohort_run_id,"f":fingerprint}).scalar_one_or_none()
    if existing:
        return _view_run(conn, int(existing))
    run_id = conn.execute(text("""INSERT INTO public.ppr_stage_runs(stage_code,stage0_cohort_run_id,status,preview_fingerprint,policy_version,current_position,safe_snapshot,created_by_user_id)
      VALUES('training',:cohort,'DRY_RUN_COMPLETED',:fingerprint,:policy,1,CAST(:snapshot AS jsonb),:actor) RETURNING stage_run_id"""), {"cohort":stage0_cohort_run_id,"fingerprint":fingerprint,"policy":POLICY_VERSION,"snapshot":json.dumps(computed["safe_snapshot"], default=str),"actor":actor_user_id}).scalar_one()
    for p in cohort:
        frozen = list(computed["safe_snapshot"]["training_candidates"][str(p["stage0_participant_id"])]["fragments"])
        d = _derive(conn,{**p,"participant_snapshot_version":1},stage_run_id=int(run_id), frozen_fragments=frozen)
        conn.execute(text("""INSERT INTO public.ppr_stage_run_participants(stage_run_id,stage0_participant_id,position,employee_id,person_id,participant_snapshot_version,safe_fingerprint,status)
          VALUES(:run,:stage0,:position,:employee,:person,1,:fingerprint,'PENDING')"""), {"run":run_id,"stage0":p["stage0_participant_id"],"position":p["position"],"employee":p["employee_id"],"person":p["person_id"],"fingerprint":d["fingerprint"]})
    return _view_run(conn, int(run_id))


def preview_stage3(conn: Connection, *, stage0_cohort_run_id: int, actor_user_id: int) -> dict[str, Any]:
    """Compatibility entry point for service callers already in a write UoW."""
    preview = compute_preview_stage3(conn, stage0_cohort_run_id=stage0_cohort_run_id)
    return persist_preview_stage3(conn, stage0_cohort_run_id=stage0_cohort_run_id, actor_user_id=actor_user_id, expected_preview_fingerprint=preview["preview_fingerprint"])


def approve_stage3(conn: Connection, *, run_id: int, actor_user_id: int) -> dict[str, Any]:
    run = _run(conn, run_id, lock=True)
    if run["status"] == "APPROVED":
        return _view_run(conn, run_id)
    if run["status"] != "DRY_RUN_COMPLETED":
        raise Stage3ConflictError("STAGE3_INVALID_STATE")
    blocked = []
    parts = _participant_rows(conn, run_id, lock=True)
    for p in parts:
        if p["status"] == "SKIPPED_BY_DECISION":
            continue
        d = _derive(conn,p,stage_run_id=run_id,lock=True,frozen_fragments=_frozen_fragments(run,p))
        if d["fingerprint"] != p["safe_fingerprint"] or any(f["outcome"] in {REVIEW_REQUIRED,"CANONICAL_CONFLICT"} for f in d["fragments"]):
            blocked.append(p["stage_run_participant_id"])
    if blocked:
        raise Stage3ConflictError("STAGE3_APPROVAL_BLOCKED")
    decision_fingerprint = _approval_decision_fingerprint(parts)
    conn.execute(text("""UPDATE public.ppr_stage_runs
        SET status='APPROVED',approved_by_user_id=:actor,approved_at=now(),
            safe_snapshot=jsonb_set(
                COALESCE(safe_snapshot, '{}'::jsonb), '{approval}',
                CAST(:approval AS jsonb), true)
        WHERE stage_run_id=:id"""), {
            "id": run_id,
            "actor": actor_user_id,
            "approval": json.dumps({
                "decision_fingerprint": decision_fingerprint,
                "policy_version": POLICY_VERSION,
            }),
        })
    return _view_run(conn, run_id)


def _pause_execution(conn: Connection, run_id: int, participant_id: int, exc: Exception) -> None:
    code, ref = _safe_error(exc)
    conn.execute(text("""UPDATE public.ppr_stage_run_participants SET status='ERROR',error_code=:code,error_reference=:ref,errored_at=now(),completed_at=NULL WHERE stage_run_participant_id=:p AND status IN ('PENDING','ERROR')"""), {"p":participant_id,"code":code,"ref":ref})
    conn.execute(text("""UPDATE public.ppr_stage_runs SET status='PAUSED_ON_ERROR',paused_operation='PARTICIPANT_EXECUTION',stopped_participant_id=:p,paused_at=now(),last_error_code=:code,last_error_reference=:ref WHERE stage_run_id=:id AND status IN ('APPROVED','RUNNING')"""), {"id":run_id,"p":participant_id,"code":code,"ref":ref})


def execute_next_stage3(conn: Connection, *, run_id: int, actor_user_id: int, resume: bool = False) -> dict[str, Any]:
    if not ppr_stage3_training_execution_enabled():
        raise Stage3ValidationError("STAGE3_EXECUTION_DISABLED")
    run = _run(conn, run_id, lock=True)
    if resume:
        if run["status"] != "PAUSED_ON_ERROR" or run["paused_operation"] != "PARTICIPANT_EXECUTION":
            raise Stage3ConflictError("STAGE3_RUN_NOT_RESUMABLE")
        position = conn.execute(text("SELECT position FROM public.ppr_stage_run_participants WHERE stage_run_participant_id=:id FOR UPDATE"),{"id":run["stopped_participant_id"]}).scalar_one()
        conn.execute(text("UPDATE public.ppr_stage_runs SET status='RUNNING',paused_operation=NULL,stopped_participant_id=NULL,paused_at=NULL,last_error_code=NULL,last_error_reference=NULL WHERE stage_run_id=:id"),{"id":run_id})
    elif run["status"] in {"APPROVED","RUNNING"}:
        position = run["current_position"]
    else:
        raise Stage3ConflictError("STAGE3_RUN_PAUSED" if run["status"]=="PAUSED_ON_ERROR" else "STAGE3_INVALID_STATE")
    p = conn.execute(text("""SELECT * FROM public.ppr_stage_run_participants WHERE stage_run_id=:run AND position>=:pos AND status IN ('PENDING','ERROR') ORDER BY position LIMIT 1 FOR UPDATE"""),{"run":run_id,"pos":position}).mappings().one_or_none()
    if p is None:
        conn.execute(text("UPDATE public.ppr_stage_runs SET status='COMPLETED_PENDING_REVIEW' WHERE stage_run_id=:id"),{"id":run_id})
        return _view_run(conn,run_id)
    p=dict(p)
    try:
        d=_derive(conn,p,stage_run_id=run_id,lock=True,frozen_fragments=_frozen_fragments(run,p))
        if d["fingerprint"] != p["safe_fingerprint"]:
            raise Stage3ConflictError("STAGE3_RESUME_STALE")
        if any(f["outcome"] in {REVIEW_REQUIRED,"CANONICAL_CONFLICT"} for f in d["fragments"]):
            raise Stage3ConflictError("STAGE3_FRAGMENT_REVIEW_REQUIRED")
        ready=[f for f in d["fragments"] if f["outcome"]=="READY_TO_ADD"]
        pmf_id=p.get("pmf_run_id")
        if ready and not pmf_id:
            run_key=_key(f"stage3-pmf-run:v1:{run_id}:{p['stage_run_participant_id']}:{p['participant_snapshot_version']}")
            pmf=create_draft_run(conn,domain_code="education",employee_context_id=int(p["employee_id"]),actor_id=str(actor_user_id),metadata={"stage3":{"envelope_run_id":run_id,"participant_id":p["stage_run_participant_id"],"participant_snapshot_version":p["participant_snapshot_version"],"policy_version":POLICY_VERSION,"deterministic_run_key":run_key}})
            pmf_id=int(pmf["run_id"])
            for f in ready:
                payload={**f["proposal"],"employee_context_id":int(p["employee_id"]),"source_field":"training_raw","source_text":None,"parse_method":"stage3_v1","confidence":None,"metadata":{"stage3":{"envelope_run_id":run_id,"participant_id":p["stage_run_participant_id"],"participant_snapshot_version":p["participant_snapshot_version"],"source_record_key":f["source_record_key"],"fragment_index":f["fragment_index"],"policy_version":POLICY_VERSION,"item_key":f["item_key"]}}}
                add_draft_item(conn,run_id=pmf_id,source_kind="stage3_training_proposal",source_record_id=f["item_key"],import_batch_id=f["import_batch_id"],import_row_id=f["import_row_id"],record_kind="training",draft_payload=payload,source_payload={"stage3":{"source_record_key":f["source_record_key"],"fragment_index":f["fragment_index"],"item_key":f["item_key"],"classification_outcome":f["outcome"],"policy_version":POLICY_VERSION,"source_snapshot_fingerprint":f["source_fingerprint"]}})
        conn.execute(text("""UPDATE public.ppr_stage_run_participants SET status='COMPLETED',pmf_run_id=COALESCE(pmf_run_id,:pmf),completed_at=now(),error_code=NULL,error_reference=NULL,errored_at=NULL WHERE stage_run_participant_id=:id"""),{"id":p["stage_run_participant_id"],"pmf":pmf_id})
        conn.execute(text("UPDATE public.ppr_stage_runs SET status='RUNNING',current_position=:next WHERE stage_run_id=:id"),{"id":run_id,"next":int(p["position"])+1})
    except Exception as exc:
        _pause_execution(conn,run_id,int(p["stage_run_participant_id"]),exc)
    return _view_run(conn,run_id)


def skip_stage3_participant(conn: Connection, *, run_id: int, participant_id: int, actor_user_id: int, reason: str) -> dict[str, Any]:
    run=_run(conn,run_id,lock=True); p=conn.execute(text("SELECT * FROM public.ppr_stage_run_participants WHERE stage_run_participant_id=:id AND stage_run_id=:run FOR UPDATE"),{"id":participant_id,"run":run_id}).mappings().one_or_none()
    if p is None or p["status"] not in {"PENDING","ERROR"} or not str(reason).strip() or run["status"] not in {"DRY_RUN_COMPLETED","APPROVED","PAUSED_ON_ERROR"} or (run["status"]=="PAUSED_ON_ERROR" and (run["paused_operation"]!="PARTICIPANT_EXECUTION" or run["stopped_participant_id"]!=participant_id)):
        raise Stage3ConflictError("STAGE3_SKIP_NOT_ALLOWED")
    conn.execute(text("UPDATE public.ppr_stage_run_participants SET status='SKIPPED_BY_DECISION',skipped_by_user_id=:actor,skipped_at=now(),skip_reason=:reason,error_code=NULL,error_reference=NULL,errored_at=NULL WHERE stage_run_participant_id=:id"),{"id":participant_id,"actor":actor_user_id,"reason":str(reason).strip()})
    if run["status"] != "DRY_RUN_COMPLETED":
        # A decision changed after (or while recovering from) approval.  The
        # old approval cannot authorize the new decision set.
        conn.execute(text("""UPDATE public.ppr_stage_runs
            SET status='DRY_RUN_COMPLETED',approved_by_user_id=NULL,approved_at=NULL,
                paused_operation=NULL,stopped_participant_id=NULL,paused_at=NULL,
                last_error_code=NULL,last_error_reference=NULL,
                safe_snapshot=COALESCE(safe_snapshot, '{}'::jsonb) - 'approval'
            WHERE stage_run_id=:id"""), {"id": run_id})
    return _view_run(conn,run_id)


def cancel_stage3(conn: Connection, *, run_id:int, actor_user_id:int, reason:str)->dict[str,Any]:
    run=_run(conn,run_id,lock=True)
    if run["status"]=="CANCELLED": return _view_run(conn,run_id)
    if run["status"] not in {"DRY_RUN_COMPLETED","APPROVED","RUNNING","PAUSED_ON_ERROR","COMPLETED_PENDING_REVIEW"} or not str(reason).strip(): raise Stage3ConflictError("STAGE3_INVALID_STATE")
    conn.execute(text("UPDATE public.ppr_stage_runs SET status='CANCELLED',cancelled_by_user_id=:actor,cancelled_at=now(),cancel_reason=:reason,paused_operation=NULL,stopped_participant_id=NULL,paused_at=NULL,last_error_code=NULL,last_error_reference=NULL WHERE stage_run_id=:id"),{"id":run_id,"actor":actor_user_id,"reason":str(reason).strip()})
    return _view_run(conn,run_id)


def acceptance_summary(conn:Connection,*,run_id:int)->dict[str,Any]:
    run=_run(conn,run_id); parts=_participant_rows(conn,run_id)
    fragments=[f for p in parts for f in _derive(conn,p,stage_run_id=run_id,frozen_fragments=_frozen_fragments(run,p))["fragments"]]
    counts=Counter(f["proposal"].get("training_kind") or "review" for f in fragments if f["outcome"]=="READY_TO_ADD")
    decision_fingerprint = _approval_decision_fingerprint(parts)
    fingerprint=_hash({"run":run_id,"preview":run["preview_fingerprint"],"parts":[p["safe_fingerprint"] for p in parts],"approval_decisions":decision_fingerprint,"records":dict(counts)})
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


def _revalidate_before_accept(conn: Connection, *, run: dict[str, Any], parts: list[dict[str, Any]]) -> None:
    """Fail closed before canonical commit; never accept a stale frozen proposal."""
    for participant in parts:
        frozen = _frozen_fragments(run, participant)
        derived = _derive(conn, participant, stage_run_id=int(run["stage_run_id"]), lock=True, frozen_fragments=frozen)
        if derived["fingerprint"] != participant["safe_fingerprint"]:
            raise Stage3ConflictError("STAGE3_ACCEPTANCE_STALE")
        if any(fragment["outcome"] in {REVIEW_REQUIRED, "STALE", "CANONICAL_CONFLICT"} for fragment in derived["fragments"]):
            raise Stage3ConflictError("STAGE3_ACCEPTANCE_STALE")
    if _approved_decision_fingerprint(run) != _approval_decision_fingerprint(parts):
        raise Stage3ConflictError("STAGE3_ACCEPTANCE_APPROVAL_STALE")


def accept_stage3(conn:Connection,*,run_id:int,actor_user_id:int,acceptance_fingerprint:str|None=None)->dict[str,Any]:
    if not ppr_stage3_training_accept_enabled():
        raise Stage3ValidationError("STAGE3_ACCEPT_DISABLED")
    run=_run(conn,run_id,lock=True)
    if run["status"]=="ACCEPTED": return _view_run(conn,run_id)
    if run["status"] not in {"COMPLETED_PENDING_REVIEW","PAUSED_ON_ERROR"} or (run["status"]=="PAUSED_ON_ERROR" and run["paused_operation"]!="ACCEPTANCE"): raise Stage3ConflictError("STAGE3_ACCEPTANCE_NOT_READY")
    parts=_participant_rows(conn,run_id,lock=True)
    if any(p["status"] not in {"COMPLETED","SKIPPED_BY_DECISION"} for p in parts): raise Stage3ConflictError("STAGE3_ACCEPTANCE_NOT_READY")
    _revalidate_before_accept(conn, run=run, parts=parts)
    summary=acceptance_summary(conn,run_id=run_id)
    if acceptance_fingerprint and acceptance_fingerprint!=summary["acceptance_fingerprint"]: raise Stage3ConflictError("STAGE3_ACCEPTANCE_STALE")
    if not ppr_pmf_bridge_enabled(): raise Stage3ValidationError("STAGE3_PPR_PMF_BRIDGE_REQUIRED")
    for p in parts:
        if p.get("pmf_run_id"): commit_run(conn,run_id=int(p["pmf_run_id"]),actor_id=str(actor_user_id))
    conn.execute(text("""UPDATE public.ppr_stage_runs SET status='ACCEPTED',accepted_by_user_id=:actor,accepted_at=now(),accepted_precondition_fingerprint=:f,acceptance_outcome=CAST(:o AS jsonb),paused_operation=NULL,stopped_participant_id=NULL,paused_at=NULL,last_error_code=NULL,last_error_reference=NULL WHERE stage_run_id=:id"""),{"id":run_id,"actor":actor_user_id,"f":summary["acceptance_fingerprint"],"o":json.dumps(summary)})
    return _view_run(conn,run_id)
