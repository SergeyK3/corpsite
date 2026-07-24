"""Education apply-phase helpers (WP-PPR-CARD-COORDINATION-008 / WP-009)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping

from app.personnel_intake.application.reconciliation.dto import CanonicalRecordRef, ProposalRecordRef
from app.personnel_intake.application.reconciliation.plugins.education import (
    CONTENT_PATCH_FIELDS,
    QUALITY_KEY,
    EducationReconciliationPlugin,
    clearing_fields,
    edu_identity_key,
    is_allowed_auto_delta,
    semantic_equal,
)
from app.personnel_intake.application.reconciliation.precondition import build_add_precondition
from app.personnel_intake.domain.reconciliation.actions import (
    REASON_APPLY_CONCURRENCY_PRECONDITION,
    REASON_APPLY_NO_MATCH_LOST,
    REASON_APPLY_STALE_ROW_VERSION,
    RECONCILE_ACTION_ADD,
    RECONCILE_ACTION_KEEP_EXISTING,
    RECONCILE_ACTION_MANUAL_REVIEW,
    RECONCILE_ACTION_SUPERSEDE,
    RECONCILE_ACTION_UPDATE_VERSION,
)
from app.personnel_intake.domain.reconciliation.digest import DigestBuilder
from app.personnel_intake.domain.reconciliation.errors import ReconciliationValidationError
from app.personnel_intake.domain.reconciliation.models import ReconcileDecisionRecord
from app.ppr.application.command_models import (
    COMMAND_TYPE_ADD_EDUCATION,
    COMMAND_TYPE_UPDATE_EDUCATION,
)


@dataclass(frozen=True, slots=True)
class EducationGateResult:
    outcome: str  # "ok" | "block"
    reason_code: str | None = None
    evidence: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class EducationPprCommandSpec:
    command_type: str
    payload: dict[str, Any]


def _domain_fields(content: Mapping[str, Any]) -> dict[str, Any]:
    from app.personnel_intake.application.reconciliation.plugins.education import SEMANTIC_FIELDS

    return {field: content.get(field) for field in SEMANTIC_FIELDS}


def _proposal_input_quality(proposal: ProposalRecordRef) -> Mapping[str, Any]:
    quality = proposal.normalized_content.get(QUALITY_KEY)
    if isinstance(quality, Mapping):
        return quality
    return {
        "started_at": {"precision": "missing", "raw": None},
        "completed_at": {"precision": "missing", "raw": None},
    }


def _has_incomplete_dates(input_quality: Mapping[str, Any]) -> bool:
    started = input_quality.get("started_at") or {}
    completed = input_quality.get("completed_at") or {}
    return (
        started.get("precision") == "incomplete"
        or completed.get("precision") == "incomplete"
    )


def parse_iso_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ReconciliationValidationError(
            f"Unparsable expected_row_version: {value!r}.",
            code="INVALID_EXPECTED_ROW_VERSION",
        ) from exc


def _date_from_iso(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    return date.fromisoformat(text[:10])


def _block(
    *,
    gate: str,
    reason_code: str,
    decision: ReconcileDecisionRecord,
    detail: Mapping[str, Any] | None = None,
) -> EducationGateResult:
    return EducationGateResult(
        outcome="block",
        reason_code=reason_code,
        evidence={
            "source": "intake_reconciliation_apply",
            "at": datetime.now().astimezone().isoformat(),
            "gate": gate,
            "reason_code": reason_code,
            "detail": dict(detail or {}),
            "decision_id": int(decision.decision_id),
            "idempotency_key": decision.idempotency_key,
        },
    )


def validate_deterministic_executable_intent(
    decision: ReconcileDecisionRecord,
) -> EducationGateResult | None:
    """Return a block-shaped failure descriptor for category C, else None."""
    action = decision.action
    if action == RECONCILE_ACTION_SUPERSEDE:
        return _block(
            gate="deterministic_failed",
            reason_code="SYSTEM_SUPERSEDE_FORBIDDEN",
            decision=decision,
            detail={"detail": "system education apply never executes supersede"},
        )
    if action in {RECONCILE_ACTION_UPDATE_VERSION, RECONCILE_ACTION_KEEP_EXISTING}:
        if decision.target_canonical_record_id is None:
            return _block(
                gate="deterministic_failed",
                reason_code="MISSING_TARGET_FOR_EXACT_ACTION",
                decision=decision,
            )
        token = decision.expected_canonical_precondition
        if not (
            token.startswith("row_version:") or token.startswith("keep:row_version:")
        ):
            return _block(
                gate="deterministic_failed",
                reason_code="INVALID_EXACT_PRECONDITION_TOKEN",
                decision=decision,
                detail={"token": token},
            )
    if action == RECONCILE_ACTION_ADD:
        if not decision.expected_canonical_precondition.startswith("none-match:"):
            return _block(
                gate="deterministic_failed",
                reason_code="INVALID_ADD_PRECONDITION_TOKEN",
                decision=decision,
                detail={"token": decision.expected_canonical_precondition},
            )
    if action == RECONCILE_ACTION_UPDATE_VERSION:
        if not decision.expected_row_version:
            return _block(
                gate="deterministic_failed",
                reason_code="INVALID_EXPECTED_ROW_VERSION",
                decision=decision,
            )
        try:
            parse_iso_datetime(decision.expected_row_version)
        except ReconciliationValidationError:
            return _block(
                gate="deterministic_failed",
                reason_code="INVALID_EXPECTED_ROW_VERSION",
                decision=decision,
                detail={"expected_row_version": decision.expected_row_version},
            )
    return None


def confirm_education_add_precondition(
    decision: ReconcileDecisionRecord,
    proposal: ProposalRecordRef,
    live_canonicals: tuple[CanonicalRecordRef, ...],
    *,
    digest_builder: DigestBuilder,
) -> EducationGateResult:
    identity = edu_identity_key(proposal.normalized_content)
    if not identity[1]:
        return _block(
            gate="add",
            reason_code=REASON_APPLY_CONCURRENCY_PRECONDITION,
            decision=decision,
            detail={"reason": "incomplete_identity"},
        )

    for canonical in live_canonicals:
        if edu_identity_key(canonical.normalized_content) == identity:
            return _block(
                gate="add",
                reason_code=REASON_APPLY_NO_MATCH_LOST,
                decision=decision,
                detail={
                    "live_record_id": int(canonical.record_id),
                    "identity_key": [identity[0], identity[1]],
                },
            )

    live_precondition = build_add_precondition(
        digest_builder=digest_builder,
        canonicals=live_canonicals,
    )
    if live_precondition != decision.expected_canonical_precondition:
        return _block(
            gate="add",
            reason_code=REASON_APPLY_CONCURRENCY_PRECONDITION,
            decision=decision,
            detail={
                "observed_precondition": live_precondition,
                "expected_precondition": decision.expected_canonical_precondition,
            },
        )

    iq = _proposal_input_quality(proposal)
    domain = _domain_fields(proposal.normalized_content)
    if _has_incomplete_dates(iq) or (
        domain.get("started_at") is None and domain.get("completed_at") is None
    ):
        return _block(
            gate="add",
            reason_code=REASON_APPLY_CONCURRENCY_PRECONDITION,
            decision=decision,
            detail={"reason": "not_confident_add_eligible"},
        )

    return EducationGateResult(outcome="ok")


def confirm_education_update_precondition(
    decision: ReconcileDecisionRecord,
    proposal: ProposalRecordRef,
    live_canonicals: tuple[CanonicalRecordRef, ...],
) -> EducationGateResult:
    target_id = decision.target_canonical_record_id
    live_target = next(
        (c for c in live_canonicals if int(c.record_id) == int(target_id or -1)),
        None,
    )
    if live_target is None:
        return _block(
            gate="update_version",
            reason_code=REASON_APPLY_STALE_ROW_VERSION,
            decision=decision,
            detail={"target_canonical_record_id": target_id},
        )
    if str(live_target.row_version) != str(decision.expected_row_version):
        return _block(
            gate="update_version",
            reason_code=REASON_APPLY_STALE_ROW_VERSION,
            decision=decision,
            detail={
                "observed_row_version": live_target.row_version,
                "expected_row_version": decision.expected_row_version,
            },
        )

    proposal_domain = _domain_fields(proposal.normalized_content)
    target_domain = _domain_fields(live_target.normalized_content)
    if edu_identity_key(proposal.normalized_content) != edu_identity_key(
        live_target.normalized_content
    ):
        return _block(
            gate="update_version",
            reason_code=REASON_APPLY_CONCURRENCY_PRECONDITION,
            decision=decision,
            detail={"reason": "identity_mismatch"},
        )

    iq = _proposal_input_quality(proposal)
    clearing = clearing_fields(
        proposal_domain,
        target_domain,
        has_incomplete=_has_incomplete_dates(iq),
        input_quality=iq,
    )
    if clearing:
        return _block(
            gate="update_version",
            reason_code=REASON_APPLY_CONCURRENCY_PRECONDITION,
            decision=decision,
            detail={"clearing_fields": clearing},
        )

    if semantic_equal(proposal_domain, target_domain):
        return _block(
            gate="update_version",
            reason_code=REASON_APPLY_CONCURRENCY_PRECONDITION,
            decision=decision,
            detail={"reason": "semantic_equal_update_drift"},
        )

    for field in CONTENT_PATCH_FIELDS:
        pv = proposal_domain.get(field)
        cv = target_domain.get(field)
        if field in {"started_at", "completed_at"}:
            changed = pv != cv
        else:
            changed = str(pv or "").strip().casefold() != str(cv or "").strip().casefold()
        if not changed:
            continue
        if field not in CONTENT_PATCH_FIELDS:
            return _block(
                gate="update_version",
                reason_code=REASON_APPLY_CONCURRENCY_PRECONDITION,
                decision=decision,
                detail={"field": field},
            )
        if not is_allowed_auto_delta(pv, cv, field=field):
            return _block(
                gate="update_version",
                reason_code=REASON_APPLY_CONCURRENCY_PRECONDITION,
                decision=decision,
                detail={"field": field, "reason": "delta_not_allowed"},
            )

    return EducationGateResult(outcome="ok")


def confirm_education_keep_precondition(
    decision: ReconcileDecisionRecord,
    proposal: ProposalRecordRef,
    live_canonicals: tuple[CanonicalRecordRef, ...],
) -> EducationGateResult:
    target_id = decision.target_canonical_record_id
    live_target = next(
        (c for c in live_canonicals if int(c.record_id) == int(target_id or -1)),
        None,
    )
    if live_target is None:
        return _block(
            gate="keep_existing",
            reason_code=REASON_APPLY_STALE_ROW_VERSION,
            decision=decision,
            detail={"target_canonical_record_id": target_id},
        )
    if edu_identity_key(proposal.normalized_content) != edu_identity_key(
        live_target.normalized_content
    ):
        return _block(
            gate="keep_existing",
            reason_code=REASON_APPLY_CONCURRENCY_PRECONDITION,
            decision=decision,
            detail={"reason": "identity_lost"},
        )
    if str(live_target.row_version) != str(decision.expected_row_version):
        return _block(
            gate="keep_existing",
            reason_code=REASON_APPLY_STALE_ROW_VERSION,
            decision=decision,
            detail={
                "observed_row_version": live_target.row_version,
                "expected_row_version": decision.expected_row_version,
            },
        )
    if not semantic_equal(
        _domain_fields(proposal.normalized_content),
        _domain_fields(live_target.normalized_content),
    ):
        return _block(
            gate="keep_existing",
            reason_code=REASON_APPLY_CONCURRENCY_PRECONDITION,
            decision=decision,
            detail={"reason": "semantic_drift"},
        )
    return EducationGateResult(outcome="ok")


def run_education_apply_gate(
    decision: ReconcileDecisionRecord,
    proposal: ProposalRecordRef,
    live_canonicals: tuple[CanonicalRecordRef, ...],
    *,
    digest_builder: DigestBuilder,
) -> EducationGateResult:
    if decision.action == RECONCILE_ACTION_ADD:
        return confirm_education_add_precondition(
            decision, proposal, live_canonicals, digest_builder=digest_builder
        )
    if decision.action == RECONCILE_ACTION_UPDATE_VERSION:
        return confirm_education_update_precondition(decision, proposal, live_canonicals)
    if decision.action == RECONCILE_ACTION_KEEP_EXISTING:
        return confirm_education_keep_precondition(decision, proposal, live_canonicals)
    if decision.action == RECONCILE_ACTION_MANUAL_REVIEW:
        return EducationGateResult(outcome="ok")
    raise ReconciliationValidationError(
        f"Unsupported education apply action: {decision.action!r}.",
        code="INVALID_EDUCATION_APPLY_ACTION",
    )


def build_education_ppr_command(
    decision: ReconcileDecisionRecord,
    proposal: ProposalRecordRef,
    live_target: CanonicalRecordRef | None,
) -> EducationPprCommandSpec | None:
    content = proposal.normalized_content
    institution = str(content.get("institution_name") or "").strip() or None

    if decision.action == RECONCILE_ACTION_ADD:
        return EducationPprCommandSpec(
            command_type=COMMAND_TYPE_ADD_EDUCATION,
            payload={
                "education_kind": str(content.get("education_kind") or ""),
                "institution_name": institution,
                "specialty": content.get("specialty"),
                "qualification": content.get("qualification"),
                "started_at": _date_from_iso(content.get("started_at")),
                "completed_at": _date_from_iso(content.get("completed_at")),
                "diploma_number": content.get("diploma_number"),
                "document_date": None,
                "metadata": {
                    "source": "personnel_intake_reconciliation",
                    "document_type": content.get("document_type"),
                    "reconciliation_decision_id": int(decision.decision_id),
                },
            },
        )

    if decision.action == RECONCILE_ACTION_UPDATE_VERSION:
        assert decision.target_canonical_record_id is not None
        assert decision.expected_row_version is not None
        assert live_target is not None
        proposal_domain = _domain_fields(content)
        target_domain = _domain_fields(live_target.normalized_content)
        payload: dict[str, Any] = {
            "record_id": int(decision.target_canonical_record_id),
            "expected_updated_at": parse_iso_datetime(decision.expected_row_version),
            "education_kind": None,
            "institution_name": None,
        }
        for field in CONTENT_PATCH_FIELDS:
            if field == "document_type":
                continue
            pv = proposal_domain.get(field)
            cv = target_domain.get(field)
            if field in {"started_at", "completed_at"}:
                if pv != cv:
                    payload[field] = _date_from_iso(pv)
            else:
                if str(pv or "").strip().casefold() != str(cv or "").strip().casefold():
                    payload[field] = pv

        metadata = {
            "document_type": content.get("document_type"),
            "source": "personnel_intake_reconciliation",
            "reconciliation_decision_id": int(decision.decision_id),
        }
        if content.get("document_type") is None and live_target.normalized_content.get(
            "document_type"
        ):
            metadata["document_type"] = live_target.normalized_content.get("document_type")
        payload["metadata"] = metadata
        return EducationPprCommandSpec(
            command_type=COMMAND_TYPE_UPDATE_EDUCATION,
            payload=payload,
        )

    return None


def find_live_target(
    decision: ReconcileDecisionRecord,
    live_canonicals: tuple[CanonicalRecordRef, ...],
) -> CanonicalRecordRef | None:
    if decision.target_canonical_record_id is None:
        return None
    for ref in live_canonicals:
        if int(ref.record_id) == int(decision.target_canonical_record_id):
            return ref
    return None


__all__ = [
    "EducationGateResult",
    "EducationPprCommandSpec",
    "EducationReconciliationPlugin",
    "build_education_ppr_command",
    "confirm_education_add_precondition",
    "confirm_education_keep_precondition",
    "confirm_education_update_precondition",
    "find_live_target",
    "parse_iso_datetime",
    "run_education_apply_gate",
    "validate_deterministic_executable_intent",
]
