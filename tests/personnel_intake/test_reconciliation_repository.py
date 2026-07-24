"""Repository contract tests for WP-PPR-CARD-COORDINATION-003."""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.personnel_intake.domain.reconciliation.actions import (
    APPLY_STATUS_APPLIED,
    APPLY_STATUS_BLOCKED,
    APPLY_STATUS_FAILED,
    APPLY_STATUS_PENDING,
    APPLY_STATUS_SKIPPED_MANUAL,
    EVIDENCE_SOURCE_INTAKE_RECONCILIATION,
    RECONCILE_ACTION_ADD,
    RECONCILE_ACTION_KEEP_EXISTING,
    RECONCILE_ACTION_MANUAL_REVIEW,
    RECONCILE_ACTION_UPDATE_VERSION,
)
from app.personnel_intake.domain.reconciliation.errors import (
    ReconciliationConflictError,
    ReconciliationConcurrencyError,
    ReconciliationNotFoundError,
    ReconciliationValidationError,
)
from app.personnel_intake.domain.reconciliation.models import (
    BatchTerminalFinalizationCommand,
    BatchTerminalTransitionItem,
    CreatePendingDecisionCommand,
    TerminalTransitionCommand,
)
from app.personnel_intake.infrastructure.reconciliation_repository import (
    SqlAlchemyReconciliationDecisionRepository,
)
from tests.conftest import insert_returning_id, table_exists
from tests.ppr.conftest import insert_person, ppr_db_available

TABLE = "personnel_intake_reconciliation_decisions"


def _require_schema() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, TABLE):
            pytest.skip(f"{TABLE} missing — run: alembic upgrade head")
        if not table_exists(conn, "personnel_applications"):
            pytest.skip("personnel_applications missing — run: alembic upgrade head")


@pytest.fixture
def db_tx():
    conn = engine.connect()
    tx = conn.begin()
    try:
        yield conn
    finally:
        tx.rollback()
        conn.close()


def _insert_application(conn, *, person_id: int, user_id: int) -> int:
    return insert_returning_id(
        conn,
        table="personnel_applications",
        id_col="application_id",
        values={
            "person_id": person_id,
            "application_received_at": date(2026, 7, 24),
            "registered_by_user_id": user_id,
            "idempotency_key": f"recon-app-{uuid4().hex}",
        },
    )


def _full_evidence(
    *,
    application_id: int,
    section_code: str = "education",
    proposal_index: int = 0,
    proposal_fingerprint: str = "fp-edu-1",
    proposal_payload_digest: str = "digest-a",
    action: str = RECONCILE_ACTION_ADD,
    reason_code: str = "MATCH_NONE_CONFIDENT",
    idempotency_key: str,
    decision_source: str = "system",
    override_token: str | None = None,
    expected_canonical_precondition: str = "none-match:set-v1",
    target_canonical_record_id: int | None = None,
    **overrides,
) -> dict:
    if action == RECONCILE_ACTION_ADD:
        match_kind = "none"
        match_confidence = "high"
        semantically_equal = None
        matched = None
        candidates: list[int] = []
    elif action == RECONCILE_ACTION_KEEP_EXISTING:
        match_kind = "exact_one"
        match_confidence = "high"
        semantically_equal = True
        matched = target_canonical_record_id
        candidates = [target_canonical_record_id] if target_canonical_record_id is not None else []
    elif action == RECONCILE_ACTION_UPDATE_VERSION:
        match_kind = "exact_one"
        match_confidence = "high"
        semantically_equal = False
        matched = target_canonical_record_id
        candidates = [target_canonical_record_id] if target_canonical_record_id is not None else []
    elif action == RECONCILE_ACTION_MANUAL_REVIEW:
        if reason_code == "MATCH_CONFIDENCE_LOW":
            match_kind = "none"
            match_confidence = "low"
            candidates = []
        elif reason_code == "MATCH_STALE_TARGET":
            match_kind = "stale_target"
            match_confidence = "high"
            candidates = []
        else:
            match_kind = "ambiguous"
            match_confidence = "high"
            candidates = [1, 2]
        semantically_equal = None
        matched = None
    else:
        match_kind = "none"
        match_confidence = "high"
        semantically_equal = None
        matched = None
        candidates = []

    base = {
        "source": EVIDENCE_SOURCE_INTAKE_RECONCILIATION,
        "application_id": application_id,
        "section_code": section_code,
        "proposal_index": proposal_index,
        "proposal_fingerprint": proposal_fingerprint,
        "proposal_payload_digest": proposal_payload_digest,
        "digest_algorithm_version": "canon-json-v1",
        "match_kind": match_kind,
        "match_confidence": match_confidence,
        "semantically_equal": semantically_equal,
        "matcher_rule_id": "EDU-FP-v1",
        "matcher_version": "1.0.0",
        "policy_version": "1.0.0",
        "candidate_canonical_record_ids": candidates,
        "matched_canonical_record_id": matched,
        "canonical_payload_digest_at_match": None,
        "expected_canonical_precondition": expected_canonical_precondition,
        "action": action,
        "reason_code": reason_code,
        "decision_source": decision_source,
        "override_token": override_token,
        "before_snapshot_ref": None,
        "after_intent_digest": "after-digest-a",
        "correlation_id": None,
        "idempotency_key": idempotency_key,
    }
    base.update(overrides)
    return base


def _cmd(
    *,
    application_id: int,
    person_id: int,
    action: str = RECONCILE_ACTION_ADD,
    reason_code: str = "MATCH_NONE_CONFIDENT",
    idempotency_key: str | None = None,
    proposal_index: int = 0,
    proposal_payload_digest: str = "digest-a",
    decision_source: str = "system",
    override_token: str | None = None,
    expected_canonical_precondition: str = "none-match:set-v1",
    target_canonical_record_id: int | None = None,
    expected_row_version: str | None = None,
    evidence: dict | None = None,
) -> CreatePendingDecisionCommand:
    key = idempotency_key or f"recon:{application_id}:education:{proposal_index}:{action}:{uuid4().hex[:8]}"
    return CreatePendingDecisionCommand(
        application_id=application_id,
        person_id=person_id,
        section_code="education",
        proposal_index=proposal_index,
        proposal_fingerprint="fp-edu-1",
        proposal_payload_digest=proposal_payload_digest,
        action=action,
        reason_code=reason_code,
        evidence=evidence
        or _full_evidence(
            application_id=application_id,
            proposal_index=proposal_index,
            proposal_payload_digest=proposal_payload_digest,
            action=action,
            reason_code=reason_code,
            idempotency_key=key,
            decision_source=decision_source,
            override_token=override_token,
            expected_canonical_precondition=expected_canonical_precondition,
            target_canonical_record_id=target_canonical_record_id,
        ),
        expected_canonical_precondition=expected_canonical_precondition,
        matcher_rule_id="EDU-FP-v1",
        matcher_version="1.0.0",
        policy_version="1.0.0",
        digest_algorithm_version="canon-json-v1",
        idempotency_key=key,
        decision_source=decision_source,
        override_token=override_token,
        target_canonical_record_id=target_canonical_record_id,
        expected_row_version=expected_row_version,
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_create_pending_and_getters(seed, db_tx) -> None:
    _require_schema()
    repo = SqlAlchemyReconciliationDecisionRepository(db_tx)
    person_id = insert_person(db_tx, full_name=f"Recon Person {uuid4().hex[:6]}")
    application_id = _insert_application(
        db_tx, person_id=person_id, user_id=int(seed["initiator_user_id"])
    )

    result = repo.create_pending(
        _cmd(application_id=application_id, person_id=person_id, idempotency_key="k-create-1")
    )
    assert result.idempotent_replay is False
    assert result.decision.apply_status == APPLY_STATUS_PENDING
    assert result.decision.row_version == 1

    by_id = repo.get_by_id(result.decision.decision_id)
    by_key = repo.get_by_idempotency_key("k-create-1")
    assert by_id is not None and by_key is not None
    assert by_id.decision_id == by_key.decision_id == result.decision.decision_id
    assert by_id.evidence["source"] == EVIDENCE_SOURCE_INTAKE_RECONCILIATION
    assert by_id.evidence["after_intent_digest"] == "after-digest-a"
    assert by_id.expected_canonical_precondition == "none-match:set-v1"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_incomplete_evidence_rejected_on_create(seed, db_tx) -> None:
    _require_schema()
    repo = SqlAlchemyReconciliationDecisionRepository(db_tx)
    person_id = insert_person(db_tx, full_name=f"Recon Ev {uuid4().hex[:6]}")
    application_id = _insert_application(
        db_tx, person_id=person_id, user_id=int(seed["initiator_user_id"])
    )
    with pytest.raises(ReconciliationValidationError, match="missing required fields"):
        repo.create_pending(
            _cmd(
                application_id=application_id,
                person_id=person_id,
                evidence={"source": EVIDENCE_SOURCE_INTAKE_RECONCILIATION},
                idempotency_key="k-ev-incomplete",
            )
        )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_application_person_mismatch_rejected(seed, db_tx) -> None:
    _require_schema()
    repo = SqlAlchemyReconciliationDecisionRepository(db_tx)
    person_a = insert_person(db_tx, full_name=f"Recon A {uuid4().hex[:6]}")
    person_b = insert_person(db_tx, full_name=f"Recon B {uuid4().hex[:6]}")
    application_id = _insert_application(
        db_tx, person_id=person_a, user_id=int(seed["initiator_user_id"])
    )
    with pytest.raises(ReconciliationValidationError, match="does not belong"):
        repo.create_pending(
            _cmd(
                application_id=application_id,
                person_id=person_b,
                idempotency_key="k-person-mismatch",
            )
        )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_idempotent_replay_same_intent(seed, db_tx) -> None:
    _require_schema()
    repo = SqlAlchemyReconciliationDecisionRepository(db_tx)
    person_id = insert_person(db_tx, full_name=f"Recon Replay {uuid4().hex[:6]}")
    application_id = _insert_application(
        db_tx, person_id=person_id, user_id=int(seed["initiator_user_id"])
    )
    cmd = _cmd(application_id=application_id, person_id=person_id, idempotency_key="k-replay-1")

    first = repo.create_pending(cmd)
    second = repo.create_pending(cmd)
    assert first.idempotent_replay is False
    assert second.idempotent_replay is True
    assert first.decision.decision_id == second.decision.decision_id

    count = db_tx.execute(
        text(f"SELECT COUNT(*) FROM public.{TABLE} WHERE idempotency_key = :k"),
        {"k": "k-replay-1"},
    ).scalar_one()
    assert int(count) == 1


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_conflicting_payload_same_key_rejected(seed, db_tx) -> None:
    _require_schema()
    repo = SqlAlchemyReconciliationDecisionRepository(db_tx)
    person_id = insert_person(db_tx, full_name=f"Recon Conflict {uuid4().hex[:6]}")
    application_id = _insert_application(
        db_tx, person_id=person_id, user_id=int(seed["initiator_user_id"])
    )
    key = "k-conflict-1"
    repo.create_pending(
        _cmd(
            application_id=application_id,
            person_id=person_id,
            idempotency_key=key,
            proposal_payload_digest="digest-a",
        )
    )
    with pytest.raises(ReconciliationConflictError):
        repo.create_pending(
            _cmd(
                application_id=application_id,
                person_id=person_id,
                idempotency_key=key,
                proposal_payload_digest="digest-b",
            )
        )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
@pytest.mark.parametrize(
    ("action", "reason", "to_status", "target", "expected_rv", "failure"),
    [
        (RECONCILE_ACTION_ADD, "MATCH_NONE_CONFIDENT", APPLY_STATUS_APPLIED, None, None, None),
        (
            RECONCILE_ACTION_KEEP_EXISTING,
            "MATCH_EXACT_KEEP",
            APPLY_STATUS_APPLIED,
            42,
            "1",
            None,
        ),
        (
            RECONCILE_ACTION_UPDATE_VERSION,
            "MATCH_EXACT_UPDATE",
            APPLY_STATUS_APPLIED,
            42,
            "3",
            None,
        ),
        (
            RECONCILE_ACTION_MANUAL_REVIEW,
            "MATCH_AMBIGUOUS",
            APPLY_STATUS_SKIPPED_MANUAL,
            None,
            None,
            None,
        ),
        (
            RECONCILE_ACTION_ADD,
            "MATCH_NONE_CONFIDENT",
            APPLY_STATUS_BLOCKED,
            None,
            None,
            {"reason": "APPLY_NO_MATCH_LOST"},
        ),
        (
            RECONCILE_ACTION_ADD,
            "MATCH_NONE_CONFIDENT",
            APPLY_STATUS_FAILED,
            None,
            None,
            {"reason": "db_error", "detail": "rollback"},
        ),
    ],
)
def test_terminal_transitions(
    seed,
    db_tx,
    action,
    reason,
    to_status,
    target,
    expected_rv,
    failure,
) -> None:
    _require_schema()
    repo = SqlAlchemyReconciliationDecisionRepository(db_tx)
    person_id = insert_person(db_tx, full_name=f"Recon Term {uuid4().hex[:6]}")
    application_id = _insert_application(
        db_tx, person_id=person_id, user_id=int(seed["initiator_user_id"])
    )
    created = repo.create_pending(
        _cmd(
            application_id=application_id,
            person_id=person_id,
            action=action,
            reason_code=reason,
            target_canonical_record_id=target,
            expected_row_version=expected_rv,
            idempotency_key=f"k-term-{uuid4().hex[:10]}",
        )
    )
    updated = repo.transition_to_terminal(
        TerminalTransitionCommand(
            decision_id=created.decision.decision_id,
            expected_row_version=created.decision.row_version,
            to_status=to_status,
            failure_evidence=failure,
        )
    )
    assert updated.apply_status == to_status
    assert updated.apply_status != APPLY_STATUS_PENDING
    assert updated.row_version == created.decision.row_version + 1
    if failure is not None:
        assert updated.failure_evidence == failure
    else:
        assert updated.failure_evidence is None


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_invalid_terminal_reason_code_rejected(seed, db_tx) -> None:
    _require_schema()
    repo = SqlAlchemyReconciliationDecisionRepository(db_tx)
    person_id = insert_person(db_tx, full_name=f"Recon Reason {uuid4().hex[:6]}")
    application_id = _insert_application(
        db_tx, person_id=person_id, user_id=int(seed["initiator_user_id"])
    )
    created = repo.create_pending(
        _cmd(application_id=application_id, person_id=person_id, idempotency_key="k-bad-reason")
    )
    with pytest.raises(ReconciliationValidationError, match="Unknown reason_code"):
        repo.transition_to_terminal(
            TerminalTransitionCommand(
                decision_id=created.decision.decision_id,
                expected_row_version=created.decision.row_version,
                to_status=APPLY_STATUS_BLOCKED,
                failure_evidence={"reason": "stale"},
                reason_code="NOT_A_REAL_REASON",
            )
        )
    assert repo.require_by_id(created.decision.decision_id).apply_status == APPLY_STATUS_PENDING


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_stale_row_version_rejected(seed, db_tx) -> None:
    _require_schema()
    repo = SqlAlchemyReconciliationDecisionRepository(db_tx)
    person_id = insert_person(db_tx, full_name=f"Recon Stale {uuid4().hex[:6]}")
    application_id = _insert_application(
        db_tx, person_id=person_id, user_id=int(seed["initiator_user_id"])
    )
    created = repo.create_pending(
        _cmd(application_id=application_id, person_id=person_id, idempotency_key="k-stale-1")
    )
    with pytest.raises(ReconciliationConcurrencyError):
        repo.transition_to_terminal(
            TerminalTransitionCommand(
                decision_id=created.decision.decision_id,
                expected_row_version=created.decision.row_version + 99,
                to_status=APPLY_STATUS_APPLIED,
            )
        )
    still = repo.require_by_id(created.decision.decision_id)
    assert still.apply_status == APPLY_STATUS_PENDING
    assert still.row_version == 1


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_illegal_transition_rejected_and_stays_pending(seed, db_tx) -> None:
    _require_schema()
    repo = SqlAlchemyReconciliationDecisionRepository(db_tx)
    person_id = insert_person(db_tx, full_name=f"Recon Illegal {uuid4().hex[:6]}")
    application_id = _insert_application(
        db_tx, person_id=person_id, user_id=int(seed["initiator_user_id"])
    )
    created = repo.create_pending(
        _cmd(
            application_id=application_id,
            person_id=person_id,
            action=RECONCILE_ACTION_ADD,
            idempotency_key="k-illegal-1",
        )
    )
    with pytest.raises(ReconciliationValidationError):
        repo.transition_to_terminal(
            TerminalTransitionCommand(
                decision_id=created.decision.decision_id,
                expected_row_version=created.decision.row_version,
                to_status=APPLY_STATUS_SKIPPED_MANUAL,
            )
        )
    assert repo.require_by_id(created.decision.decision_id).apply_status == APPLY_STATUS_PENDING


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_blocked_requires_failure_evidence(seed, db_tx) -> None:
    _require_schema()
    repo = SqlAlchemyReconciliationDecisionRepository(db_tx)
    person_id = insert_person(db_tx, full_name=f"Recon FailEv {uuid4().hex[:6]}")
    application_id = _insert_application(
        db_tx, person_id=person_id, user_id=int(seed["initiator_user_id"])
    )
    created = repo.create_pending(
        _cmd(application_id=application_id, person_id=person_id, idempotency_key="k-fail-ev-1")
    )
    with pytest.raises(ReconciliationValidationError, match="failure_evidence"):
        repo.transition_to_terminal(
            TerminalTransitionCommand(
                decision_id=created.decision.decision_id,
                expected_row_version=created.decision.row_version,
                to_status=APPLY_STATUS_BLOCKED,
                failure_evidence=None,
            )
        )
    assert repo.require_by_id(created.decision.decision_id).apply_status == APPLY_STATUS_PENDING


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_blocked_empty_failure_evidence_rejected(seed, db_tx) -> None:
    _require_schema()
    repo = SqlAlchemyReconciliationDecisionRepository(db_tx)
    person_id = insert_person(db_tx, full_name=f"Recon Empty FailEv {uuid4().hex[:6]}")
    application_id = _insert_application(
        db_tx, person_id=person_id, user_id=int(seed["initiator_user_id"])
    )
    created = repo.create_pending(
        _cmd(application_id=application_id, person_id=person_id, idempotency_key="k-empty-fail-ev")
    )
    with pytest.raises(ReconciliationValidationError, match="non-empty failure_evidence"):
        repo.transition_to_terminal(
            TerminalTransitionCommand(
                decision_id=created.decision.decision_id,
                expected_row_version=created.decision.row_version,
                to_status=APPLY_STATUS_BLOCKED,
                failure_evidence={},
            )
        )
    assert repo.require_by_id(created.decision.decision_id).apply_status == APPLY_STATUS_PENDING


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_finalize_batch_empty_failure_evidence_rejected(seed, db_tx) -> None:
    _require_schema()
    repo = SqlAlchemyReconciliationDecisionRepository(db_tx)
    person_id = insert_person(db_tx, full_name=f"Recon Batch Empty FailEv {uuid4().hex[:6]}")
    application_id = _insert_application(
        db_tx, person_id=person_id, user_id=int(seed["initiator_user_id"])
    )
    created = repo.create_pending(
        _cmd(application_id=application_id, person_id=person_id, idempotency_key="k-batch-empty-fail")
    )
    with pytest.raises(ReconciliationValidationError, match="non-empty failure_evidence"):
        repo.finalize_batch_terminal(
            BatchTerminalFinalizationCommand(
                transitions=(
                    BatchTerminalTransitionItem(
                        decision_id=created.decision.decision_id,
                        expected_row_version=created.decision.row_version,
                        to_status=APPLY_STATUS_BLOCKED,
                        failure_evidence={},
                    ),
                )
            )
        )
    assert repo.require_by_id(created.decision.decision_id).apply_status == APPLY_STATUS_PENDING


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_finalize_batch_rollback_after_partial_update(seed, db_tx, monkeypatch) -> None:
    _require_schema()
    repo = SqlAlchemyReconciliationDecisionRepository(db_tx)
    person_id = insert_person(db_tx, full_name=f"Recon Batch Rollback {uuid4().hex[:6]}")
    application_id = _insert_application(
        db_tx, person_id=person_id, user_id=int(seed["initiator_user_id"])
    )
    first = repo.create_pending(
        _cmd(
            application_id=application_id,
            person_id=person_id,
            proposal_index=0,
            idempotency_key="k-batch-rollback-a",
        )
    )
    second = repo.create_pending(
        _cmd(
            application_id=application_id,
            person_id=person_id,
            proposal_index=1,
            idempotency_key="k-batch-rollback-b",
        )
    )

    original_apply = repo._apply_terminal_transition
    calls = {"count": 0}

    def flaky_apply(current, item):
        record = original_apply(current, item)
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("forced after first update")
        return record

    monkeypatch.setattr(repo, "_apply_terminal_transition", flaky_apply)

    with pytest.raises(RuntimeError, match="forced after first update"):
        repo.finalize_batch_terminal(
            BatchTerminalFinalizationCommand(
                transitions=(
                    BatchTerminalTransitionItem(
                        decision_id=first.decision.decision_id,
                        expected_row_version=first.decision.row_version,
                        to_status=APPLY_STATUS_APPLIED,
                    ),
                    BatchTerminalTransitionItem(
                        decision_id=second.decision.decision_id,
                        expected_row_version=second.decision.row_version,
                        to_status=APPLY_STATUS_APPLIED,
                    ),
                )
            )
        )

    assert repo.require_by_id(first.decision.decision_id).apply_status == APPLY_STATUS_PENDING
    assert repo.require_by_id(second.decision.decision_id).apply_status == APPLY_STATUS_PENDING


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_unique_idempotency_at_db_level(seed, db_tx) -> None:
    _require_schema()
    repo = SqlAlchemyReconciliationDecisionRepository(db_tx)
    person_id = insert_person(db_tx, full_name=f"Recon UQ {uuid4().hex[:6]}")
    application_id = _insert_application(
        db_tx, person_id=person_id, user_id=int(seed["initiator_user_id"])
    )
    key = "k-uq-db-1"
    repo.create_pending(
        _cmd(application_id=application_id, person_id=person_id, idempotency_key=key)
    )
    nested = db_tx.begin_nested()
    try:
        with pytest.raises(Exception):
            db_tx.execute(
                text(
                    f"""
                    INSERT INTO public.{TABLE} (
                        application_id, person_id, section_code, proposal_index,
                        proposal_fingerprint, proposal_payload_digest, action, reason_code,
                        evidence, expected_canonical_precondition, decision_source,
                        matcher_rule_id, matcher_version, policy_version,
                        digest_algorithm_version, idempotency_key, intent_fingerprint
                    ) VALUES (
                        :application_id, :person_id, 'education', 1,
                        'fp', 'd', 'add', 'MATCH_NONE_CONFIDENT',
                        '{{}}'::jsonb, 'none', 'system',
                        'r', '1', '1',
                        'canon-json-v1', :key, 'different-fingerprint'
                    )
                    """
                ),
                {
                    "application_id": application_id,
                    "person_id": person_id,
                    "key": key,
                },
            )
            db_tx.execute(text("SELECT 1"))
    finally:
        if nested.is_active:
            nested.rollback()

    assert repo.get_by_idempotency_key(key) is not None


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_finalize_batch_terminal_atomicity_hold(seed, db_tx) -> None:
    _require_schema()
    repo = SqlAlchemyReconciliationDecisionRepository(db_tx)
    person_id = insert_person(db_tx, full_name=f"Recon Batch {uuid4().hex[:6]}")
    application_id = _insert_application(
        db_tx, person_id=person_id, user_id=int(seed["initiator_user_id"])
    )

    manual = repo.create_pending(
        _cmd(
            application_id=application_id,
            person_id=person_id,
            proposal_index=0,
            action=RECONCILE_ACTION_MANUAL_REVIEW,
            reason_code="MATCH_AMBIGUOUS",
            idempotency_key="k-batch-manual",
        )
    )
    blocked = repo.create_pending(
        _cmd(
            application_id=application_id,
            person_id=person_id,
            proposal_index=1,
            action=RECONCILE_ACTION_ADD,
            idempotency_key="k-batch-add",
        )
    )

    result = repo.finalize_batch_terminal(
        BatchTerminalFinalizationCommand(
            transitions=(
                BatchTerminalTransitionItem(
                    decision_id=manual.decision.decision_id,
                    expected_row_version=manual.decision.row_version,
                    to_status=APPLY_STATUS_SKIPPED_MANUAL,
                ),
                BatchTerminalTransitionItem(
                    decision_id=blocked.decision.decision_id,
                    expected_row_version=blocked.decision.row_version,
                    to_status=APPLY_STATUS_BLOCKED,
                    reason_code="SECTION_ATOMICITY_HOLD",
                    failure_evidence={"reason": "SECTION_ATOMICITY_HOLD"},
                ),
            )
        )
    )
    assert len(result.decisions) == 2
    statuses = {d.decision_id: d.apply_status for d in result.decisions}
    assert statuses[manual.decision.decision_id] == APPLY_STATUS_SKIPPED_MANUAL
    assert statuses[blocked.decision.decision_id] == APPLY_STATUS_BLOCKED
    assert all(d.apply_status != APPLY_STATUS_PENDING for d in result.decisions)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_finalize_batch_stale_one_rejects_all(seed, db_tx) -> None:
    _require_schema()
    repo = SqlAlchemyReconciliationDecisionRepository(db_tx)
    person_id = insert_person(db_tx, full_name=f"Recon Batch Stale {uuid4().hex[:6]}")
    application_id = _insert_application(
        db_tx, person_id=person_id, user_id=int(seed["initiator_user_id"])
    )
    first = repo.create_pending(
        _cmd(
            application_id=application_id,
            person_id=person_id,
            proposal_index=0,
            idempotency_key="k-batch-a",
        )
    )
    second = repo.create_pending(
        _cmd(
            application_id=application_id,
            person_id=person_id,
            proposal_index=1,
            idempotency_key="k-batch-b",
        )
    )

    with pytest.raises(ReconciliationConcurrencyError):
        repo.finalize_batch_terminal(
            BatchTerminalFinalizationCommand(
                transitions=(
                    BatchTerminalTransitionItem(
                        decision_id=first.decision.decision_id,
                        expected_row_version=first.decision.row_version,
                        to_status=APPLY_STATUS_APPLIED,
                    ),
                    BatchTerminalTransitionItem(
                        decision_id=second.decision.decision_id,
                        expected_row_version=second.decision.row_version + 99,
                        to_status=APPLY_STATUS_APPLIED,
                    ),
                )
            )
        )

    assert repo.require_by_id(first.decision.decision_id).apply_status == APPLY_STATUS_PENDING
    assert repo.require_by_id(second.decision.decision_id).apply_status == APPLY_STATUS_PENDING


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_finalize_batch_missing_id_rejected(seed, db_tx) -> None:
    _require_schema()
    repo = SqlAlchemyReconciliationDecisionRepository(db_tx)
    with pytest.raises(ReconciliationNotFoundError):
        repo.finalize_batch_terminal(
            BatchTerminalFinalizationCommand(
                transitions=(
                    BatchTerminalTransitionItem(
                        decision_id=999_999_999,
                        expected_row_version=1,
                        to_status=APPLY_STATUS_BLOCKED,
                        failure_evidence={"reason": "missing"},
                    ),
                )
            )
        )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_finalize_batch_duplicate_id_rejected(seed, db_tx) -> None:
    _require_schema()
    repo = SqlAlchemyReconciliationDecisionRepository(db_tx)
    person_id = insert_person(db_tx, full_name=f"Recon Batch Dup {uuid4().hex[:6]}")
    application_id = _insert_application(
        db_tx, person_id=person_id, user_id=int(seed["initiator_user_id"])
    )
    created = repo.create_pending(
        _cmd(application_id=application_id, person_id=person_id, idempotency_key="k-batch-dup")
    )
    item = BatchTerminalTransitionItem(
        decision_id=created.decision.decision_id,
        expected_row_version=created.decision.row_version,
        to_status=APPLY_STATUS_APPLIED,
    )
    with pytest.raises(ReconciliationValidationError, match="unique decision_id"):
        repo.finalize_batch_terminal(
            BatchTerminalFinalizationCommand(transitions=(item, item))
        )
    assert repo.require_by_id(created.decision.decision_id).apply_status == APPLY_STATUS_PENDING
