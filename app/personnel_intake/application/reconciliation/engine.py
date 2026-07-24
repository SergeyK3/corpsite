"""Reconciliation Decision Engine — U1 Decide (WP-PPR-CARD-COORDINATION-004)."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from sqlalchemy.engine import Connection

from app.personnel_intake.application.reconciliation.dto import (
    CanonicalRecordRef,
    DecideDecisionOutcome,
    DecideSectionCommand,
    DecideSectionResult,
    DecideSectionSummary,
    MatchOutcome,
    ProposalRecordRef,
)
from app.personnel_intake.application.reconciliation.idempotency import build_idempotency_key
from app.personnel_intake.application.reconciliation.normalizer import normalize_match_outcome
from app.personnel_intake.application.reconciliation.plugin import SectionReconciliationPlugin
from app.personnel_intake.application.reconciliation.precondition import (
    build_add_precondition,
    build_keep_precondition,
    build_manual_precondition,
    build_row_version_precondition,
)
from app.personnel_intake.application.reconciliation.registry import SectionReconciliationRegistry
from app.personnel_intake.domain.reconciliation.actions import (
    APPLY_STATUS_APPLIED,
    APPLY_STATUS_BLOCKED,
    APPLY_STATUS_FAILED,
    APPLY_STATUS_PENDING,
    APPLY_STATUS_SKIPPED_MANUAL,
    DECISION_SOURCE_SYSTEM,
    EVIDENCE_SOURCE_INTAKE_RECONCILIATION,
    MATCH_CONFIDENCE_HIGH,
    MATCH_KIND_AMBIGUOUS,
    MATCH_KIND_EXACT_ONE,
    REASON_MATCH_EXACT_SUPERSEDE,
    REASON_MATCH_EXACT_UPDATE,
    RECONCILE_ACTION_ADD,
    RECONCILE_ACTION_KEEP_EXISTING,
    RECONCILE_ACTION_MANUAL_REVIEW,
    RECONCILE_ACTION_SUPERSEDE,
    RECONCILE_ACTION_UPDATE_VERSION,
    SECTION_CODE_MILITARY,
)
from app.personnel_intake.domain.reconciliation.digest import (
    DEFAULT_DIGEST_BUILDER_REGISTRY,
    DigestBuilder,
    DigestBuilderRegistry,
)
from app.personnel_intake.domain.reconciliation.errors import ReconciliationValidationError
from app.personnel_intake.domain.reconciliation.models import CreatePendingDecisionCommand
from app.personnel_intake.infrastructure.reconciliation_repository import (
    SqlAlchemyReconciliationDecisionRepository,
)

# SECTION_APPLY_MODE constants are engine-local (not in WP-003 actions).
SECTION_APPLY_MODE_PER_RECORD = "per_record"
SECTION_APPLY_MODE_ALL_OR_NOTHING = "all_or_nothing"


def _assert_complete_coverage(proposals: tuple[ProposalRecordRef, ...]) -> None:
    if not proposals:
        raise ReconciliationValidationError(
            "Section decide requires at least one proposal.",
            code="INCOMPLETE_PROPOSAL_COVERAGE",
        )
    indices = [int(ref.proposal_index) for ref in proposals]
    if len(indices) != len(set(indices)):
        raise ReconciliationValidationError(
            "Duplicate proposal_index values in build_proposal_refs.",
            code="INVALID_PROPOSAL_INDEX_SET",
        )
    expected = list(range(len(proposals)))
    if sorted(indices) != expected:
        raise ReconciliationValidationError(
            "proposal_index set must be contiguous 0..N-1.",
            code="INVALID_PROPOSAL_INDEX_SET",
        )


def _validate_match_outcome(match: MatchOutcome) -> None:
    if not str(match.match_kind or "").strip():
        raise ReconciliationValidationError(
            "MatchOutcome.match_kind is required.",
            code="INVALID_MATCH_OUTCOME",
        )
    if not str(match.match_confidence or "").strip():
        raise ReconciliationValidationError(
            "MatchOutcome.match_confidence is required.",
            code="INVALID_MATCH_OUTCOME",
        )
    candidates = match.candidate_canonical_record_ids
    if not isinstance(candidates, (list, tuple)):
        raise ReconciliationValidationError(
            "MatchOutcome.candidate_canonical_record_ids must be a sequence of int.",
            code="INVALID_MATCH_OUTCOME",
        )
    for index, candidate_id in enumerate(candidates):
        if isinstance(candidate_id, bool) or not isinstance(candidate_id, int):
            raise ReconciliationValidationError(
                f"candidate_canonical_record_ids[{index}] must be int.",
                code="INVALID_MATCH_OUTCOME",
            )
    if match.match_kind == MATCH_KIND_AMBIGUOUS and len(candidates) == 0:
        raise ReconciliationValidationError(
            "ambiguous match requires non-empty candidate_canonical_record_ids.",
            code="INVALID_MATCH_OUTCOME",
        )
    matched = match.matched_canonical_record_id
    if matched is not None and (isinstance(matched, bool) or not isinstance(matched, int)):
        raise ReconciliationValidationError(
            "matched_canonical_record_id must be int or null.",
            code="INVALID_MATCH_OUTCOME",
        )
    if match.semantically_equal is not None and not isinstance(match.semantically_equal, bool):
        raise ReconciliationValidationError(
            "semantically_equal must be bool or null.",
            code="INVALID_MATCH_OUTCOME",
        )
    if (
        match.match_kind == MATCH_KIND_EXACT_ONE
        and match.match_confidence == MATCH_CONFIDENCE_HIGH
        and not isinstance(match.semantically_equal, bool)
    ):
        raise ReconciliationValidationError(
            "exact_one + high requires semantically_equal to be a strict bool.",
            code="INVALID_MATCH_OUTCOME",
        )


def _assert_replay_allowed(decision) -> None:
    status = decision.apply_status
    if status in {
        APPLY_STATUS_PENDING,
        APPLY_STATUS_APPLIED,
        APPLY_STATUS_SKIPPED_MANUAL,
    }:
        return
    if status in {APPLY_STATUS_BLOCKED, APPLY_STATUS_FAILED}:
        raise ReconciliationValidationError(
            f"Re-decide of terminal apply_status={status!r} requires a new execution intent.",
            code="REDECIDE_TERMINAL_REQUIRES_NEW_INTENT",
        )
    raise ReconciliationValidationError(
        f"Unexpected apply_status on replay: {status!r}.",
        code="INVALID_REPLAY_APPLY_STATUS",
    )


def _canonical_by_id(
    canonicals: tuple[CanonicalRecordRef, ...],
    record_id: int,
) -> CanonicalRecordRef:
    for ref in canonicals:
        if int(ref.record_id) == int(record_id):
            return ref
    raise ReconciliationValidationError(
        f"Matched canonical record_id={record_id} not found in loaded canonicals.",
        code="INVALID_MATCH_OUTCOME",
    )


def _resolve_action_and_target(
    *,
    plugin: SectionReconciliationPlugin,
    match: MatchOutcome,
    proposal: ProposalRecordRef,
    canonicals: tuple[CanonicalRecordRef, ...],
    section_code: str,
) -> tuple[str, str, int | None, str | None, CanonicalRecordRef | None]:
    normalized = normalize_match_outcome(match, section_code=section_code)
    if normalized.needs_choose_exact_action:
        if match.matched_canonical_record_id is None:
            raise ReconciliationValidationError(
                "exact_one non-equal match requires matched_canonical_record_id.",
                code="INVALID_MATCH_OUTCOME",
            )
        target = _canonical_by_id(canonicals, match.matched_canonical_record_id)
        chosen = plugin.choose_exact_action(match, proposal, target)
        if chosen == RECONCILE_ACTION_UPDATE_VERSION:
            return (
                RECONCILE_ACTION_UPDATE_VERSION,
                REASON_MATCH_EXACT_UPDATE,
                int(target.record_id),
                str(target.row_version),
                target,
            )
        if chosen == RECONCILE_ACTION_SUPERSEDE:
            return (
                RECONCILE_ACTION_SUPERSEDE,
                REASON_MATCH_EXACT_SUPERSEDE,
                int(target.record_id),
                str(target.row_version),
                target,
            )
        raise ReconciliationValidationError(
            f"choose_exact_action returned illegal action {chosen!r}.",
            code="ILLEGAL_ACTION_REASON",
        )

    if normalized.action is None or normalized.reason_code is None:
        raise ReconciliationValidationError(
            "Normalizer did not produce action/reason.",
            code="ILLEGAL_ACTION_REASON",
        )

    action = normalized.action
    reason_code = normalized.reason_code
    target: CanonicalRecordRef | None = None
    target_id: int | None = None
    expected_row_version: str | None = None

    if action in {
        RECONCILE_ACTION_KEEP_EXISTING,
        RECONCILE_ACTION_UPDATE_VERSION,
        RECONCILE_ACTION_SUPERSEDE,
    }:
        if match.matched_canonical_record_id is None:
            raise ReconciliationValidationError(
                f"action={action!r} requires matched_canonical_record_id.",
                code="INVALID_MATCH_OUTCOME",
            )
        target = _canonical_by_id(canonicals, match.matched_canonical_record_id)
        target_id = int(target.record_id)
        expected_row_version = str(target.row_version)

    return action, reason_code, target_id, expected_row_version, target


def _build_precondition(
    *,
    digest_builder: DigestBuilder,
    action: str,
    reason_code: str,
    target: CanonicalRecordRef | None,
    canonicals: tuple[CanonicalRecordRef, ...],
) -> str:
    if action == RECONCILE_ACTION_ADD:
        return build_add_precondition(digest_builder=digest_builder, canonicals=canonicals)
    if action == RECONCILE_ACTION_KEEP_EXISTING:
        assert target is not None
        return build_keep_precondition(row_version=str(target.row_version))
    if action in {RECONCILE_ACTION_UPDATE_VERSION, RECONCILE_ACTION_SUPERSEDE}:
        assert target is not None
        return build_row_version_precondition(row_version=str(target.row_version))
    if action == RECONCILE_ACTION_MANUAL_REVIEW:
        return build_manual_precondition(reason_code=reason_code)
    raise ReconciliationValidationError(
        f"Unsupported action for precondition: {action!r}.",
        code="ILLEGAL_ACTION_REASON",
    )


def _build_after_intent_digest(
    *,
    action: str,
    proposal: ProposalRecordRef,
    target: CanonicalRecordRef | None,
) -> str:
    if action == RECONCILE_ACTION_KEEP_EXISTING:
        assert target is not None and target.payload_digest
        return str(target.payload_digest)
    assert proposal.payload_digest
    return str(proposal.payload_digest)


def _build_evidence(
    *,
    command: DecideSectionCommand,
    proposal: ProposalRecordRef,
    match: MatchOutcome,
    action: str,
    reason_code: str,
    policy_version: str,
    matcher_rule_id: str,
    matcher_version: str,
    expected_canonical_precondition: str,
    idempotency_key: str,
    target: CanonicalRecordRef | None,
) -> dict[str, Any]:
    canonical_digest = target.payload_digest if target is not None else None
    before_snapshot_ref: str | None = None
    if target is not None and target.payload_digest:
        before_snapshot_ref = f"canonical:{target.record_id}:{target.payload_digest}"

    return {
        "source": EVIDENCE_SOURCE_INTAKE_RECONCILIATION,
        "application_id": int(command.application_id),
        "section_code": command.section_code,
        "proposal_index": int(proposal.proposal_index),
        "proposal_fingerprint": proposal.proposal_fingerprint,
        "proposal_payload_digest": proposal.payload_digest,
        "digest_algorithm_version": command.digest_algorithm_version,
        "match_kind": match.match_kind,
        "match_confidence": match.match_confidence,
        "semantically_equal": match.semantically_equal,
        "matcher_rule_id": matcher_rule_id,
        "matcher_version": matcher_version,
        "policy_version": policy_version,
        "candidate_canonical_record_ids": list(match.candidate_canonical_record_ids),
        "matched_canonical_record_id": match.matched_canonical_record_id,
        "canonical_payload_digest_at_match": canonical_digest,
        "expected_canonical_precondition": expected_canonical_precondition,
        "action": action,
        "reason_code": reason_code,
        "decision_source": command.decision_source,
        "override_token": command.override_token,
        "before_snapshot_ref": before_snapshot_ref,
        "after_intent_digest": _build_after_intent_digest(
            action=action, proposal=proposal, target=target
        ),
        "correlation_id": command.correlation_id,
        "idempotency_key": idempotency_key,
    }


def _build_summary(outcomes: tuple[DecideDecisionOutcome, ...]) -> DecideSectionSummary:
    counts = {
        RECONCILE_ACTION_ADD: 0,
        RECONCILE_ACTION_UPDATE_VERSION: 0,
        RECONCILE_ACTION_SUPERSEDE: 0,
        RECONCILE_ACTION_KEEP_EXISTING: 0,
        RECONCILE_ACTION_MANUAL_REVIEW: 0,
    }
    pending = 0
    applied = 0
    skipped_manual = 0
    for outcome in outcomes:
        counts[outcome.action] = counts.get(outcome.action, 0) + 1
        status = outcome.decision.apply_status
        if status == APPLY_STATUS_PENDING:
            pending += 1
        elif status == APPLY_STATUS_APPLIED:
            applied += 1
        elif status == APPLY_STATUS_SKIPPED_MANUAL:
            skipped_manual += 1
    return DecideSectionSummary(
        add=counts[RECONCILE_ACTION_ADD],
        update_version=counts[RECONCILE_ACTION_UPDATE_VERSION],
        supersede=counts[RECONCILE_ACTION_SUPERSEDE],
        keep_existing=counts[RECONCILE_ACTION_KEEP_EXISTING],
        manual_review=counts[RECONCILE_ACTION_MANUAL_REVIEW],
        pending=pending,
        applied=applied,
        skipped_manual=skipped_manual,
    )


def _result_status(outcomes: tuple[DecideDecisionOutcome, ...]) -> str:
    if not outcomes:
        raise ReconciliationValidationError(
            "DecideSectionResult requires at least one decision.",
            code="INCOMPLETE_PROPOSAL_COVERAGE",
        )
    replays = [outcome.idempotent_replay for outcome in outcomes]
    if all(replays):
        return "idempotent_replay"
    if not any(replays):
        return "fresh"
    return "mixed"


class ReconciliationDecisionEngine:
    """Application-layer U1 Decide engine (no PPR / transfer mutations)."""

    def __init__(
        self,
        registry: SectionReconciliationRegistry,
        *,
        digest_registry: DigestBuilderRegistry | None = None,
    ) -> None:
        self._registry = registry
        self._digest_registry = digest_registry or DEFAULT_DIGEST_BUILDER_REGISTRY

    def decide_section(
        self,
        conn: Connection,
        command: DecideSectionCommand,
    ) -> DecideSectionResult:
        # --- Before U1 savepoint (no decision rows) ---
        digest_builder = self._digest_registry.resolve(command.digest_algorithm_version)

        if command.decision_source != DECISION_SOURCE_SYSTEM:
            raise ReconciliationValidationError(
                "WP-004 decide path supports decision_source=system only.",
                code="UNSUPPORTED_DECISION_SOURCE",
            )
        if command.override_token is not None:
            raise ReconciliationValidationError(
                "system decide path must not supply override_token.",
                code="INVALID_OVERRIDE_TOKEN",
            )

        plugin = self._registry.require(command.section_code)
        if plugin.section_code == SECTION_CODE_MILITARY:
            if plugin.section_apply_mode != SECTION_APPLY_MODE_ALL_OR_NOTHING:
                raise ReconciliationValidationError(
                    "military plugin must declare section_apply_mode=all_or_nothing.",
                    code="INVALID_SECTION_APPLY_MODE",
                )
        if plugin.section_apply_mode not in {
            SECTION_APPLY_MODE_PER_RECORD,
            SECTION_APPLY_MODE_ALL_OR_NOTHING,
        }:
            raise ReconciliationValidationError(
                f"Unsupported section_apply_mode {plugin.section_apply_mode!r}.",
                code="INVALID_SECTION_APPLY_MODE",
            )

        policy_version = command.policy_version_override or plugin.policy_version

        proposals = plugin.build_proposal_refs(
            command.section_payload,
            command.digest_algorithm_version,
        )
        _assert_complete_coverage(proposals)

        canonicals = plugin.load_canonical_refs(
            conn,
            command.person_id,
            command.digest_algorithm_version,
        )

        repo = SqlAlchemyReconciliationDecisionRepository(conn)

        # --- U1 savepoint: enrichment + loop + persist + replay + result ---
        with conn.begin_nested():
            enriched_proposals: list[ProposalRecordRef] = []
            for ref in proposals:
                digest = digest_builder.verify_or_compute(
                    ref.normalized_content,
                    ref.claimed_payload_digest,
                )
                enriched_proposals.append(replace(ref, payload_digest=digest))

            enriched_canonicals: list[CanonicalRecordRef] = []
            for ref in canonicals:
                digest = digest_builder.verify_or_compute(
                    ref.normalized_content,
                    ref.claimed_payload_digest,
                )
                enriched_canonicals.append(replace(ref, payload_digest=digest))

            proposals_sorted = tuple(
                sorted(enriched_proposals, key=lambda item: int(item.proposal_index))
            )
            canonical_tuple = tuple(enriched_canonicals)

            outcomes: list[DecideDecisionOutcome] = []
            for proposal in proposals_sorted:
                assert proposal.payload_digest
                match = plugin.match(proposal, canonical_tuple)
                _validate_match_outcome(match)

                action, reason_code, target_id, expected_row_version, target = (
                    _resolve_action_and_target(
                        plugin=plugin,
                        match=match,
                        proposal=proposal,
                        canonicals=canonical_tuple,
                        section_code=command.section_code,
                    )
                )

                create_expected_row_version = expected_row_version
                if action in {RECONCILE_ACTION_ADD, RECONCILE_ACTION_MANUAL_REVIEW}:
                    create_expected_row_version = None
                    if action == RECONCILE_ACTION_MANUAL_REVIEW:
                        target_id = None
                        target = None

                precondition = _build_precondition(
                    digest_builder=digest_builder,
                    action=action,
                    reason_code=reason_code,
                    target=target,
                    canonicals=canonical_tuple,
                )
                idempotency_key = build_idempotency_key(
                    digest_builder=digest_builder,
                    application_id=command.application_id,
                    section_code=command.section_code,
                    proposal_index=proposal.proposal_index,
                    action=action,
                    digest_algorithm_version=command.digest_algorithm_version,
                    proposal_payload_digest=str(proposal.payload_digest),
                    target_canonical_record_id=target_id,
                    expected_canonical_precondition=precondition,
                    decision_source=command.decision_source,
                    override_token=command.override_token,
                    matcher_rule_id=plugin.matcher_rule_id,
                    matcher_version=plugin.matcher_version,
                    policy_version=policy_version,
                )
                evidence = _build_evidence(
                    command=command,
                    proposal=proposal,
                    match=match,
                    action=action,
                    reason_code=reason_code,
                    policy_version=policy_version,
                    matcher_rule_id=plugin.matcher_rule_id,
                    matcher_version=plugin.matcher_version,
                    expected_canonical_precondition=precondition,
                    idempotency_key=idempotency_key,
                    target=target,
                )

                create_cmd = CreatePendingDecisionCommand(
                    application_id=int(command.application_id),
                    person_id=int(command.person_id),
                    section_code=command.section_code,
                    proposal_index=int(proposal.proposal_index),
                    proposal_fingerprint=proposal.proposal_fingerprint,
                    proposal_payload_digest=str(proposal.payload_digest),
                    action=action,
                    reason_code=reason_code,
                    evidence=evidence,
                    expected_canonical_precondition=precondition,
                    matcher_rule_id=plugin.matcher_rule_id,
                    matcher_version=plugin.matcher_version,
                    policy_version=policy_version,
                    digest_algorithm_version=command.digest_algorithm_version,
                    idempotency_key=idempotency_key,
                    decision_source=command.decision_source,
                    override_token=command.override_token,
                    target_canonical_record_id=target_id,
                    expected_row_version=create_expected_row_version,
                )

                create_result = repo.create_pending(create_cmd)
                if create_result.idempotent_replay:
                    _assert_replay_allowed(create_result.decision)

                outcomes.append(
                    DecideDecisionOutcome(
                        decision=create_result.decision,
                        idempotent_replay=create_result.idempotent_replay,
                        proposal_index=int(proposal.proposal_index),
                        action=create_result.decision.action,
                        reason_code=create_result.decision.reason_code,
                    )
                )

            outcome_tuple = tuple(outcomes)
            decision_ids = tuple(outcome.decision.decision_id for outcome in outcome_tuple)
            if not decision_ids:
                raise ReconciliationValidationError(
                    "DecideSectionResult.decision_ids must be non-empty.",
                    code="INCOMPLETE_PROPOSAL_COVERAGE",
                )

            return DecideSectionResult(
                application_id=int(command.application_id),
                person_id=int(command.person_id),
                section_code=command.section_code,
                section_apply_mode=plugin.section_apply_mode,
                correlation_id=command.correlation_id,
                digest_algorithm_version=command.digest_algorithm_version,
                policy_version=policy_version,
                decision_ids=decision_ids,
                decisions=outcome_tuple,
                summary=_build_summary(outcome_tuple),
                batch_idempotent_replay=all(
                    outcome.idempotent_replay for outcome in outcome_tuple
                ),
                result_status=_result_status(outcome_tuple),
            )


__all__ = [
    "ReconciliationDecisionEngine",
    "SECTION_APPLY_MODE_ALL_OR_NOTHING",
    "SECTION_APPLY_MODE_PER_RECORD",
]
