"""Education SectionReconciliationPlugin (WP-PPR-CARD-COORDINATION-006 / WP-007)."""
from __future__ import annotations

from copy import copy
from datetime import date, datetime
from typing import Any, Mapping

from sqlalchemy.engine import Connection

from app.personnel_intake.application.reconciliation.dto import (
    CanonicalRecordRef,
    MatchOutcome,
    ProposalRecordRef,
)
from app.personnel_intake.application.reconciliation.engine import SECTION_APPLY_MODE_PER_RECORD
from app.personnel_intake.application.reconciliation.registry import SectionReconciliationRegistry
from app.personnel_intake.domain.date_validation import (
    ISO_DATE_RE,
    RU_DATE_RE,
    is_incomplete_intake_period_date,
    is_valid_intake_full_date_iso,
)
from app.personnel_intake.domain.education_type import resolve_intake_education_kind
from app.personnel_intake.domain.reconciliation.actions import (
    MATCH_CONFIDENCE_HIGH,
    MATCH_CONFIDENCE_LOW,
    MATCH_KIND_AMBIGUOUS,
    MATCH_KIND_EXACT_ONE,
    MATCH_KIND_NONE,
    RECONCILE_ACTION_UPDATE_VERSION,
    SECTION_CODE_EDUCATION,
)
from app.personnel_intake.domain.reconciliation.errors import ReconciliationValidationError
from app.ppr.domain.section_models import (
    SECTION_CODE_PPR_EDUCATION,
    EducationRecord,
)
from app.ppr.infrastructure.section_repository import SqlAlchemySectionReadRepository

EDU_MATCHER_RULE_ID = "EDU-MATCH-v1"
EDU_MATCHER_VERSION = "1.0.0"
EDU_POLICY_VERSION = "1.0.0"

SEMANTIC_FIELDS: tuple[str, ...] = (
    "education_kind",
    "institution_name",
    "specialty",
    "qualification",
    "started_at",
    "completed_at",
    "diploma_number",
    "document_type",
)

CONTENT_PATCH_FIELDS: frozenset[str] = frozenset(
    {
        "specialty",
        "qualification",
        "diploma_number",
        "document_type",
        "started_at",
        "completed_at",
    }
)

QUALITY_KEY = "reconciliation_input_quality"
PRECISION_MISSING = "missing"
PRECISION_DAY = "day"
PRECISION_INCOMPLETE = "incomplete"

REASON_INCOMPLETE_IDENTITY = "INCOMPLETE_IDENTITY"
REASON_HR_Q3_AMBIGUOUS_IDENTITY = "HR_Q3_AMBIGUOUS_IDENTITY"
REASON_INCOMPLETE_OR_YEAR_ONLY_DATE = "INCOMPLETE_OR_YEAR_ONLY_DATE"
REASON_BOTH_DATES_MISSING = "BOTH_DATES_MISSING"
REASON_CANONICAL_VALUE_CLEARING_FORBIDDEN = "CANONICAL_VALUE_CLEARING_FORBIDDEN"


def _strip_text(value: Any) -> str:
    return str(value or "").strip()


def _optional_stripped(value: Any) -> str | None:
    text = _strip_text(value)
    return text if text else None


def _isoformat_utc_or_naive(value: datetime) -> str:
    return value.isoformat()


def _date_to_iso_day(value: date | datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = _strip_text(value)
    return text[:10] if text else None


def _quality_entry(*, precision: str, raw: str | None) -> dict[str, Any]:
    return {"precision": precision, "raw": raw}


def _parse_full_day_iso(value: Any) -> str | None:
    text = _strip_text(value)
    if not text:
        return None
    if ISO_DATE_RE.match(text):
        iso = text[:10]
    else:
        ru_match = RU_DATE_RE.match(text)
        if not ru_match:
            return None
        day, month, year = ru_match.groups()
        iso = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    if not is_valid_intake_full_date_iso(iso):
        return None
    return iso


def _normalize_proposal_date(raw: Any) -> tuple[str | None, dict[str, Any]]:
    text = _strip_text(raw)
    if not text:
        return None, _quality_entry(precision=PRECISION_MISSING, raw=None)
    if is_incomplete_intake_period_date(text):
        return None, _quality_entry(precision=PRECISION_INCOMPLETE, raw=text)
    iso = _parse_full_day_iso(text)
    if iso is None:
        return None, _quality_entry(precision=PRECISION_INCOMPLETE, raw=text)
    return iso, _quality_entry(precision=PRECISION_DAY, raw=text)


def _canonical_date_quality(iso_day: str | None) -> dict[str, Any]:
    if iso_day is None:
        return _quality_entry(precision=PRECISION_MISSING, raw=None)
    return _quality_entry(precision=PRECISION_DAY, raw=iso_day)


def edu_identity_key(content: Mapping[str, Any]) -> tuple[str, str]:
    kind = str(content.get("education_kind") or "")
    institution = _strip_text(content.get("institution_name")).casefold()
    return kind, institution


def education_identity_fingerprint(content: Mapping[str, Any]) -> str:
    kind, institution = edu_identity_key(content)
    return f"edu:{kind}|{institution}"


def _domain_fields(content: Mapping[str, Any]) -> dict[str, Any]:
    return {field: content.get(field) for field in SEMANTIC_FIELDS}


def _is_non_empty_domain(field: str, value: Any) -> bool:
    if value is None:
        return False
    if field == "institution_name":
        return bool(_strip_text(value))
    if field in {"started_at", "completed_at"}:
        return True
    return bool(_strip_text(value))


def _is_empty_domain(field: str, value: Any) -> bool:
    return not _is_non_empty_domain(field, value)


def _text_compare_equal(left: Any, right: Any) -> bool:
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    return _strip_text(left).casefold() == _strip_text(right).casefold()


def semantic_equal(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    for field in SEMANTIC_FIELDS:
        lv = left.get(field)
        rv = right.get(field)
        if field in {"started_at", "completed_at"}:
            if lv != rv:
                return False
            continue
        if field == "education_kind":
            if str(lv or "") != str(rv or ""):
                return False
            continue
        if not _text_compare_equal(lv, rv):
            return False
    return True


def differing_fields(left: Mapping[str, Any], right: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    for field in SEMANTIC_FIELDS:
        lv = left.get(field)
        rv = right.get(field)
        if field in {"started_at", "completed_at"}:
            if lv != rv:
                out.append(field)
            continue
        if field == "education_kind":
            if str(lv or "") != str(rv or ""):
                out.append(field)
            continue
        if not _text_compare_equal(lv, rv):
            out.append(field)
    return out


def clearing_fields(
    proposal: Mapping[str, Any],
    target: Mapping[str, Any],
    *,
    has_incomplete: bool,
    input_quality: Mapping[str, Any],
) -> list[str]:
    fields: list[str] = []
    for field in SEMANTIC_FIELDS:
        if _is_non_empty_domain(field, target.get(field)) and _is_empty_domain(
            field, proposal.get(field)
        ):
            fields.append(field)

    if has_incomplete:
        started_q = input_quality.get("started_at") or {}
        completed_q = input_quality.get("completed_at") or {}
        if (
            started_q.get("precision") == PRECISION_INCOMPLETE
            and _is_non_empty_domain("started_at", target.get("started_at"))
            and "started_at" not in fields
        ):
            fields.append("started_at")
        if (
            completed_q.get("precision") == PRECISION_INCOMPLETE
            and _is_non_empty_domain("completed_at", target.get("completed_at"))
            and "completed_at" not in fields
        ):
            fields.append("completed_at")
    return fields


def is_allowed_auto_delta(proposal_value: Any, canonical_value: Any, *, field: str) -> bool:
    if _is_empty_domain(field, canonical_value) and _is_non_empty_domain(field, proposal_value):
        return True
    if (
        _is_non_empty_domain(field, canonical_value)
        and _is_non_empty_domain(field, proposal_value)
        and not (
            (field in {"started_at", "completed_at"} and proposal_value == canonical_value)
            or (
                field not in {"started_at", "completed_at"}
                and _text_compare_equal(proposal_value, canonical_value)
            )
        )
    ):
        return True
    return False


def _extract_education_list(section_payload: Mapping[str, object]) -> list[Any]:
    has_records = "records" in section_payload
    has_education = "education" in section_payload
    if has_records and has_education:
        raise ReconciliationValidationError(
            "education section payload must not include both 'records' and 'education'.",
            code="INVALID_EDUCATION_PAYLOAD",
        )
    if has_records:
        records = section_payload.get("records")
        if not isinstance(records, list):
            raise ReconciliationValidationError(
                "education section payload 'records' must be a list.",
                code="INVALID_EDUCATION_PAYLOAD",
            )
        return records
    if has_education:
        education = section_payload.get("education")
        if not isinstance(education, list):
            raise ReconciliationValidationError(
                "education section payload 'education' must be a list.",
                code="INVALID_EDUCATION_PAYLOAD",
            )
        return education
    raise ReconciliationValidationError(
        "education section payload must include 'records' or 'education' list.",
        code="INVALID_EDUCATION_PAYLOAD",
    )


def _normalize_intake_record(item: Mapping[str, Any]) -> dict[str, Any]:
    try:
        education_kind = resolve_intake_education_kind(item.get("education_type"))
    except ValueError as exc:
        raise ReconciliationValidationError(
            f"Unknown education_type: {item.get('education_type')!r}.",
            code="INVALID_EDUCATION_TYPE",
        ) from exc

    institution_name = _strip_text(item.get("institution"))
    started_at, started_q = _normalize_proposal_date(item.get("year_from"))
    completed_at, completed_q = _normalize_proposal_date(item.get("year_to"))
    return {
        "education_kind": education_kind,
        "institution_name": institution_name,
        "specialty": _optional_stripped(item.get("specialty")),
        "qualification": _optional_stripped(item.get("qualification")),
        "started_at": started_at,
        "completed_at": completed_at,
        "diploma_number": _optional_stripped(item.get("diploma_number")),
        "document_type": _optional_stripped(item.get("document_type")),
        QUALITY_KEY: {
            "started_at": started_q,
            "completed_at": completed_q,
        },
    }


def _normalize_canonical_record(record: EducationRecord) -> dict[str, Any]:
    started_at = _date_to_iso_day(record.started_at)
    completed_at = _date_to_iso_day(record.completed_at)
    metadata = dict(record.metadata or {})
    document_type = _optional_stripped(metadata.get("document_type"))
    return {
        "education_kind": str(record.education_kind),
        "institution_name": _strip_text(record.institution_name),
        "specialty": _optional_stripped(record.specialty),
        "qualification": _optional_stripped(record.qualification),
        "started_at": started_at,
        "completed_at": completed_at,
        "diploma_number": _optional_stripped(record.diploma_number),
        "document_type": document_type,
        QUALITY_KEY: {
            "started_at": _canonical_date_quality(started_at),
            "completed_at": _canonical_date_quality(completed_at),
        },
    }


def _proposal_input_quality(proposal: ProposalRecordRef) -> Mapping[str, Any]:
    quality = proposal.normalized_content.get(QUALITY_KEY)
    if isinstance(quality, Mapping):
        return quality
    return {
        "started_at": _quality_entry(precision=PRECISION_MISSING, raw=None),
        "completed_at": _quality_entry(precision=PRECISION_MISSING, raw=None),
    }


def _has_incomplete_dates(input_quality: Mapping[str, Any]) -> bool:
    started = input_quality.get("started_at") or {}
    completed = input_quality.get("completed_at") or {}
    return (
        started.get("precision") == PRECISION_INCOMPLETE
        or completed.get("precision") == PRECISION_INCOMPLETE
    )


class EducationReconciliationPlugin:
    """Decide-phase education plugin — no PPR mutations."""

    section_code: str = SECTION_CODE_EDUCATION
    section_apply_mode: str = SECTION_APPLY_MODE_PER_RECORD
    policy_version: str = EDU_POLICY_VERSION
    matcher_rule_id: str = EDU_MATCHER_RULE_ID
    matcher_version: str = EDU_MATCHER_VERSION

    def build_proposal_refs(
        self,
        section_payload: Mapping[str, object],
        digest_algorithm_version: str,
    ) -> tuple[ProposalRecordRef, ...]:
        del digest_algorithm_version
        items = _extract_education_list(section_payload)
        refs: list[ProposalRecordRef] = []
        for index, item in enumerate(items):
            if not isinstance(item, Mapping):
                raise ReconciliationValidationError(
                    f"education[{index}] must be an object.",
                    code="INVALID_EDUCATION_PAYLOAD",
                )
            normalized = _normalize_intake_record(item)
            refs.append(
                ProposalRecordRef(
                    proposal_index=index,
                    proposal_fingerprint=education_identity_fingerprint(normalized),
                    normalized_content=normalized,
                    raw_payload=dict(copy(item)),
                    claimed_payload_digest=None,
                    payload_digest=None,
                )
            )
        return tuple(refs)

    def load_canonical_refs(
        self,
        conn: Connection,
        person_id: int,
        digest_algorithm_version: str,
    ) -> tuple[CanonicalRecordRef, ...]:
        del digest_algorithm_version
        repo = SqlAlchemySectionReadRepository(conn)
        records = repo.load_active_records(int(person_id), SECTION_CODE_PPR_EDUCATION)
        refs: list[CanonicalRecordRef] = []
        for record in records:
            if not isinstance(record, EducationRecord):
                raise ReconciliationValidationError(
                    "Active PPR-EDUCATION row must be EducationRecord; "
                    f"got {type(record).__name__}.",
                    code="INVALID_CANONICAL_RECORD",
                )
            if record.record_id is None:
                raise ReconciliationValidationError(
                    "Active education record is missing record_id.",
                    code="INVALID_CANONICAL_RECORD",
                )
            if record.updated_at is None:
                raise ReconciliationValidationError(
                    f"Active education record_id={record.record_id} missing updated_at.",
                    code="INVALID_CANONICAL_ROW_VERSION",
                )
            normalized = _normalize_canonical_record(record)
            refs.append(
                CanonicalRecordRef(
                    record_id=int(record.record_id),
                    lifecycle_status="active",
                    row_version=_isoformat_utc_or_naive(record.updated_at),
                    record_fingerprint=education_identity_fingerprint(normalized),
                    normalized_content=normalized,
                    claimed_payload_digest=None,
                    payload_digest=None,
                )
            )
        return tuple(refs)

    def match(
        self,
        proposal: ProposalRecordRef,
        canonicals: tuple[CanonicalRecordRef, ...],
    ) -> MatchOutcome:
        iq = dict(_proposal_input_quality(proposal))
        has_incomplete = _has_incomplete_dates(iq)
        proposal_domain = _domain_fields(proposal.normalized_content)
        identity = edu_identity_key(proposal.normalized_content)

        if not identity[1]:
            return MatchOutcome(
                match_kind=MATCH_KIND_NONE,
                match_confidence=MATCH_CONFIDENCE_LOW,
                semantically_equal=None,
                candidate_canonical_record_ids=(),
                detail={
                    "reason": REASON_INCOMPLETE_IDENTITY,
                    QUALITY_KEY: iq,
                },
            )

        candidates = [
            c
            for c in canonicals
            if edu_identity_key(c.normalized_content) == identity
        ]

        if len(candidates) >= 2:
            ids = tuple(sorted(int(c.record_id) for c in candidates))
            return MatchOutcome(
                match_kind=MATCH_KIND_AMBIGUOUS,
                match_confidence=MATCH_CONFIDENCE_HIGH,
                matched_canonical_record_id=None,
                candidate_canonical_record_ids=ids,
                semantically_equal=None,
                detail={
                    "reason": REASON_HR_Q3_AMBIGUOUS_IDENTITY,
                    "identity_key": [identity[0], identity[1]],
                    QUALITY_KEY: iq,
                },
            )

        if len(candidates) == 1:
            target = candidates[0]
            target_domain = _domain_fields(target.normalized_content)
            equal = semantic_equal(proposal_domain, target_domain)
            clearing = clearing_fields(
                proposal_domain,
                target_domain,
                has_incomplete=has_incomplete,
                input_quality=iq,
            )
            diffs = differing_fields(proposal_domain, target_domain) if not equal else []
            target_id = int(target.record_id)

            if has_incomplete:
                return MatchOutcome(
                    match_kind=MATCH_KIND_EXACT_ONE,
                    match_confidence=MATCH_CONFIDENCE_LOW,
                    matched_canonical_record_id=target_id,
                    candidate_canonical_record_ids=(target_id,),
                    semantically_equal=equal,
                    detail={
                        "reason": REASON_INCOMPLETE_OR_YEAR_ONLY_DATE,
                        QUALITY_KEY: iq,
                        "clearing_fields": clearing,
                        "differing_fields": diffs,
                    },
                )

            if clearing:
                return MatchOutcome(
                    match_kind=MATCH_KIND_EXACT_ONE,
                    match_confidence=MATCH_CONFIDENCE_LOW,
                    matched_canonical_record_id=target_id,
                    candidate_canonical_record_ids=(target_id,),
                    semantically_equal=False,
                    detail={
                        "reason": REASON_CANONICAL_VALUE_CLEARING_FORBIDDEN,
                        QUALITY_KEY: iq,
                        "clearing_fields": clearing,
                        "differing_fields": diffs,
                    },
                )

            return MatchOutcome(
                match_kind=MATCH_KIND_EXACT_ONE,
                match_confidence=MATCH_CONFIDENCE_HIGH,
                matched_canonical_record_id=target_id,
                candidate_canonical_record_ids=(target_id,),
                semantically_equal=equal,
                detail={
                    QUALITY_KEY: iq,
                    "differing_fields": diffs,
                },
            )

        if has_incomplete:
            return MatchOutcome(
                match_kind=MATCH_KIND_NONE,
                match_confidence=MATCH_CONFIDENCE_LOW,
                semantically_equal=None,
                candidate_canonical_record_ids=(),
                detail={
                    "reason": REASON_INCOMPLETE_OR_YEAR_ONLY_DATE,
                    QUALITY_KEY: iq,
                },
            )

        if proposal_domain.get("started_at") is None and proposal_domain.get("completed_at") is None:
            return MatchOutcome(
                match_kind=MATCH_KIND_NONE,
                match_confidence=MATCH_CONFIDENCE_LOW,
                semantically_equal=None,
                candidate_canonical_record_ids=(),
                detail={
                    "reason": REASON_BOTH_DATES_MISSING,
                    QUALITY_KEY: iq,
                },
            )

        return MatchOutcome(
            match_kind=MATCH_KIND_NONE,
            match_confidence=MATCH_CONFIDENCE_HIGH,
            semantically_equal=None,
            candidate_canonical_record_ids=(),
            detail={QUALITY_KEY: iq},
        )

    def choose_exact_action(
        self,
        match: MatchOutcome,
        proposal: ProposalRecordRef,
        target: CanonicalRecordRef,
    ) -> str:
        if match.match_kind != MATCH_KIND_EXACT_ONE or match.match_confidence != MATCH_CONFIDENCE_HIGH:
            raise ReconciliationValidationError(
                "choose_exact_action requires exact_one + high.",
                code="INVALID_CHOOSE_EXACT_ACTION",
            )
        if match.semantically_equal is not False:
            raise ReconciliationValidationError(
                "choose_exact_action requires semantically_equal=false.",
                code="INVALID_CHOOSE_EXACT_ACTION",
            )

        proposal_domain = _domain_fields(proposal.normalized_content)
        target_domain = _domain_fields(target.normalized_content)
        iq = _proposal_input_quality(proposal)
        clearing = clearing_fields(
            proposal_domain,
            target_domain,
            has_incomplete=False,
            input_quality=iq,
        )
        if clearing:
            raise ReconciliationValidationError(
                "choose_exact_action forbids canonical value clearing.",
                code="INVALID_CHOOSE_EXACT_ACTION",
            )

        diffs = differing_fields(proposal_domain, target_domain)
        for field in diffs:
            if field not in CONTENT_PATCH_FIELDS:
                raise ReconciliationValidationError(
                    f"Field {field!r} is not an allowed auto content patch.",
                    code="INVALID_CHOOSE_EXACT_ACTION",
                )
            if not is_allowed_auto_delta(
                proposal_domain.get(field),
                target_domain.get(field),
                field=field,
            ):
                raise ReconciliationValidationError(
                    f"Field {field!r} delta is not allowed on system auto path.",
                    code="INVALID_CHOOSE_EXACT_ACTION",
                )

        return RECONCILE_ACTION_UPDATE_VERSION


def register_education_plugin(
    registry: SectionReconciliationRegistry,
    *,
    plugin: EducationReconciliationPlugin | None = None,
) -> EducationReconciliationPlugin:
    """Register the education decide-phase plugin on a registry."""
    instance = plugin or EducationReconciliationPlugin()
    registry.register(instance)
    return instance


__all__ = [
    "CONTENT_PATCH_FIELDS",
    "EDU_MATCHER_RULE_ID",
    "EDU_MATCHER_VERSION",
    "EDU_POLICY_VERSION",
    "EducationReconciliationPlugin",
    "QUALITY_KEY",
    "SEMANTIC_FIELDS",
    "clearing_fields",
    "edu_identity_key",
    "education_identity_fingerprint",
    "register_education_plugin",
    "semantic_equal",
]
