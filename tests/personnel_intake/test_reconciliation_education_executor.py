"""Education reconciliation decision executor — practical U2 scenarios (WP-009)."""
from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_migration import EDUCATION_KIND_BASIC, LIFECYCLE_STATUS_ACTIVE
from app.personnel_intake.application.reconciliation.dto import DecideSectionCommand
from app.personnel_intake.application.reconciliation.engine import ReconciliationDecisionEngine
from app.personnel_intake.application.reconciliation.executor import (
    ApplyEducationDecisionCommand,
    EducationReconciliationDecisionExecutor,
)
from app.personnel_intake.application.reconciliation.plugins.education import (
    EducationReconciliationPlugin,
)
from app.personnel_intake.application.reconciliation.registry import SectionReconciliationRegistry
from app.personnel_intake.domain.reconciliation.actions import (
    APPLY_STATUS_APPLIED,
    APPLY_STATUS_BLOCKED,
    APPLY_STATUS_PENDING,
    APPLY_STATUS_SKIPPED_MANUAL,
    REASON_APPLY_STALE_ROW_VERSION,
    RECONCILE_ACTION_ADD,
    RECONCILE_ACTION_KEEP_EXISTING,
    RECONCILE_ACTION_MANUAL_REVIEW,
    RECONCILE_ACTION_UPDATE_VERSION,
)
from app.personnel_intake.domain.reconciliation.errors import ReconciliationValidationError
from app.personnel_intake.infrastructure.reconciliation_repository import (
    SqlAlchemyReconciliationDecisionRepository,
)
from app.ppr.application.authorization import AllowAllAuthorizationPort
from app.ppr.application.command_models import COMMAND_TYPE_MATERIALIZE_PPR, MaterializePprPayload, PprCommandEnvelope
from app.ppr.application.lifecycle_service import PprLifecycleApplicationService
from app.ppr.application.uow_participation import bind_participating_uow
from app.ppr.domain.section_models import EducationRecord
from app.ppr.infrastructure.section_repository import (
    SqlAlchemySectionMutationRepository,
    SqlAlchemySectionReadRepository,
)
from tests.conftest import insert_returning_id, table_exists
from tests.personnel_intake.edu_plugin_helpers import intake_row
from tests.ppr.conftest import cleanup_person_graph, insert_person, ppr_db_available

TABLE = "personnel_intake_reconciliation_decisions"


def _require_schema() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, TABLE):
            pytest.skip(f"{TABLE} missing — run: alembic upgrade head")
        if not table_exists(conn, "person_education"):
            pytest.skip("person_education missing — run: alembic upgrade head")
        if not table_exists(conn, "personnel_record_metadata"):
            pytest.skip("personnel_record_metadata missing — run: alembic upgrade head")


@pytest.fixture
def db_tx():
    conn = engine.connect()
    tx = conn.begin()
    try:
        yield conn
    finally:
        tx.rollback()
        conn.close()


def _seed(db_tx, seed):
    person_id = insert_person(db_tx, full_name=f"Edu Exec {uuid4().hex[:6]}")
    application_id = insert_returning_id(
        db_tx,
        table="personnel_applications",
        id_col="application_id",
        values={
            "person_id": person_id,
            "application_received_at": date(2026, 7, 24),
            "registered_by_user_id": int(seed["initiator_user_id"]),
            "idempotency_key": f"edu-exec-{uuid4().hex}",
        },
    )
    return person_id, application_id


def _engine() -> ReconciliationDecisionEngine:
    registry = SectionReconciliationRegistry()
    registry.register(EducationReconciliationPlugin())
    return ReconciliationDecisionEngine(registry)


def _executor() -> EducationReconciliationDecisionExecutor:
    return EducationReconciliationDecisionExecutor()


def _decide_cmd(application_id: int, person_id: int, records: list[dict], **overrides):
    data = dict(
        application_id=application_id,
        person_id=person_id,
        section_code="education",
        section_payload={"records": records},
        decision_source="system",
        correlation_id="edu-exec-corr",
        digest_algorithm_version="canon-json-v1",
    )
    data.update(overrides)
    return DecideSectionCommand(**data)


def _apply_cmd(decision_id: int, records: list[dict], **overrides) -> ApplyEducationDecisionCommand:
    data = dict(
        decision_id=decision_id,
        section_payload={"records": records},
        actor_id="test-recon-apply",
        correlation_id="edu-exec-corr",
        digest_algorithm_version="canon-json-v1",
    )
    data.update(overrides)
    return ApplyEducationDecisionCommand(**data)


def _materialize(db_tx, person_id: int) -> None:
    uow = bind_participating_uow(db_tx)
    lifecycle = PprLifecycleApplicationService(authorization=AllowAllAuthorizationPort())
    lifecycle.materialize_ppr_participating(
        uow,
        PprCommandEnvelope(
            command_id=f"mat-edu-exec-{uuid4().hex}",
            command_type=COMMAND_TYPE_MATERIALIZE_PPR,
            actor_id="test-actor",
            requested_at=datetime.now(UTC),
            payload=MaterializePprPayload(),
            person_id=person_id,
        ),
    )


def _insert_education(
    conn,
    *,
    person_id: int,
    institution_name: str = "МГУ",
    education_kind: str = EDUCATION_KIND_BASIC,
    specialty: str | None = "Математика",
    qualification: str | None = "Бакалавр",
    started_at: date | None = date(2015, 9, 1),
    completed_at: date | None = date(2019, 6, 30),
    diploma_number: str | None = "D-1",
    document_type: str | None = "diploma",
) -> EducationRecord:
    mutation = SqlAlchemySectionMutationRepository(conn)
    metadata = {"document_type": document_type} if document_type is not None else {}
    inserted = mutation.insert_record(
        EducationRecord(
            person_id=person_id,
            education_kind=education_kind,
            institution_name=institution_name,
            specialty=specialty,
            qualification=qualification,
            started_at=started_at,
            completed_at=completed_at,
            diploma_number=diploma_number,
            metadata=metadata or None,
            lifecycle_status=LIFECYCLE_STATUS_ACTIVE,
        )
    )
    assert inserted.record_id is not None
    assert inserted.updated_at is not None
    return inserted


def _active_education_count(conn, person_id: int) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT count(*)
                FROM public.person_education
                WHERE person_id = :person_id AND lifecycle_status = 'active'
                """
            ),
            {"person_id": person_id},
        ).scalar_one()
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_ex01_add_applies_successfully(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    _materialize(db_tx, person_id)
    records = [intake_row(institution="New Apply Uni")]
    decided = _engine().decide_section(db_tx, _decide_cmd(application_id, person_id, records))
    decision = decided.decisions[0].decision
    assert decision.action == RECONCILE_ACTION_ADD
    assert _active_education_count(db_tx, person_id) == 0

    result = _executor().apply_decision(db_tx, _apply_cmd(decision.decision_id, records))
    assert result.result_status == "applied"
    assert result.decision.apply_status == APPLY_STATUS_APPLIED
    assert result.section_record_id is not None
    assert _active_education_count(db_tx, person_id) == 1

    loaded = SqlAlchemySectionReadRepository(db_tx).load_record(
        person_id, "PPR-EDUCATION", int(result.section_record_id)
    )
    assert isinstance(loaded, EducationRecord)
    assert loaded.institution_name == "New Apply Uni"
    assert (loaded.metadata or {}).get("reconciliation_decision_id") == decision.decision_id


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_ex03_update_version_applies_successfully(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    _materialize(db_tx, person_id)
    row = _insert_education(db_tx, person_id=person_id, specialty=None)
    records = [intake_row(specialty="Физика")]
    decided = _engine().decide_section(db_tx, _decide_cmd(application_id, person_id, records))
    decision = decided.decisions[0].decision
    assert decision.action == RECONCILE_ACTION_UPDATE_VERSION
    assert decision.target_canonical_record_id == row.record_id

    result = _executor().apply_decision(db_tx, _apply_cmd(decision.decision_id, records))
    assert result.result_status == "applied"
    assert result.decision.apply_status == APPLY_STATUS_APPLIED
    assert _active_education_count(db_tx, person_id) == 1

    loaded = SqlAlchemySectionReadRepository(db_tx).load_record(
        person_id, "PPR-EDUCATION", int(row.record_id)
    )
    assert isinstance(loaded, EducationRecord)
    assert loaded.specialty == "Физика"
    assert (loaded.metadata or {}).get("reconciliation_decision_id") == decision.decision_id


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_ex02_ex04_keep_and_manual_do_not_mutate_ppr(seed, db_tx) -> None:
    _require_schema()

    # keep_existing
    person_id, application_id = _seed(db_tx, seed)
    _materialize(db_tx, person_id)
    keep_row = _insert_education(db_tx, person_id=person_id, institution_name="KeepU")
    keep_records = [intake_row(institution="KeepU")]
    keep_decision = _engine().decide_section(
        db_tx, _decide_cmd(application_id, person_id, keep_records)
    ).decisions[0].decision
    assert keep_decision.action == RECONCILE_ACTION_KEEP_EXISTING
    before_keep = _active_education_count(db_tx, person_id)

    keep_result = _executor().apply_decision(
        db_tx, _apply_cmd(keep_decision.decision_id, keep_records)
    )
    assert keep_result.result_status == "applied"
    assert keep_result.decision.apply_status == APPLY_STATUS_APPLIED
    assert keep_result.section_record_id is None
    assert _active_education_count(db_tx, person_id) == before_keep
    reloaded = SqlAlchemySectionReadRepository(db_tx).load_record(
        person_id, "PPR-EDUCATION", int(keep_row.record_id)
    )
    assert isinstance(reloaded, EducationRecord)
    assert reloaded.updated_at == keep_row.updated_at

    # manual_review (ambiguous identity)
    person_id2, application_id2 = _seed(db_tx, seed)
    _materialize(db_tx, person_id2)
    _insert_education(db_tx, person_id=person_id2, institution_name="DupApply")
    db_tx.execute(
        text(
            """
            INSERT INTO public.person_education (
                person_id, education_kind, institution_name, specialty,
                started_at, completed_at, lifecycle_status, verification_status
            ) VALUES (
                :person_id, :kind, :inst, 'X',
                DATE '2010-01-02', DATE '2014-01-02', 'active', 'pending'
            )
            """
        ),
        {"person_id": person_id2, "kind": EDUCATION_KIND_BASIC, "inst": "DupApply"},
    )
    manual_records = [
        intake_row(institution="DupApply", year_from="2010-01-02", year_to="2014-01-02")
    ]
    before_manual = _active_education_count(db_tx, person_id2)
    manual_decision = _engine().decide_section(
        db_tx, _decide_cmd(application_id2, person_id2, manual_records)
    ).decisions[0].decision
    assert manual_decision.action == RECONCILE_ACTION_MANUAL_REVIEW

    manual_result = _executor().apply_decision(
        db_tx, _apply_cmd(manual_decision.decision_id, manual_records)
    )
    assert manual_result.result_status == "skipped_manual"
    assert manual_result.decision.apply_status == APPLY_STATUS_SKIPPED_MANUAL
    assert _active_education_count(db_tx, person_id2) == before_manual


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_ex09_terminal_replay_does_not_repeat_mutation(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    _materialize(db_tx, person_id)
    records = [intake_row(institution="Replay Uni")]
    decided = _engine().decide_section(db_tx, _decide_cmd(application_id, person_id, records))
    decision_id = decided.decisions[0].decision.decision_id

    first = _executor().apply_decision(db_tx, _apply_cmd(decision_id, records))
    assert first.result_status == "applied"
    assert _active_education_count(db_tx, person_id) == 1

    second = _executor().apply_decision(db_tx, _apply_cmd(decision_id, records))
    assert second.idempotent_replay is True
    assert second.result_status == "idempotent_replay"
    assert second.decision.apply_status == APPLY_STATUS_APPLIED
    assert _active_education_count(db_tx, person_id) == 1


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_ex14_digest_mismatch_leaves_pending_without_writes(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    _materialize(db_tx, person_id)
    records = [intake_row(institution="Digest Uni")]
    decided = _engine().decide_section(db_tx, _decide_cmd(application_id, person_id, records))
    decision = decided.decisions[0].decision

    wrong = [intake_row(institution="Other Uni")]
    with pytest.raises(ReconciliationValidationError) as exc_info:
        _executor().apply_decision(db_tx, _apply_cmd(decision.decision_id, wrong))
    assert exc_info.value.code == "PROPOSAL_DIGEST_MISMATCH"

    reloaded = SqlAlchemyReconciliationDecisionRepository(db_tx).require_by_id(
        decision.decision_id
    )
    assert reloaded.apply_status == APPLY_STATUS_PENDING
    assert reloaded.failure_evidence is None
    assert _active_education_count(db_tx, person_id) == 0


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_ex07_stale_canonical_blocks_without_ppr_mutation(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    _materialize(db_tx, person_id)
    row = _insert_education(db_tx, person_id=person_id, specialty=None)
    records = [intake_row(specialty="Химия")]
    decided = _engine().decide_section(db_tx, _decide_cmd(application_id, person_id, records))
    decision = decided.decisions[0].decision
    assert decision.action == RECONCILE_ACTION_UPDATE_VERSION

    # Live canonical changes after decide → stale expected_row_version.
    # Use clock_timestamp(): transaction-scoped now() does not advance inside db_tx.
    db_tx.execute(
        text(
            """
            UPDATE public.person_education
            SET specialty = 'Биология',
                updated_at = clock_timestamp()
            WHERE education_id = :record_id
              AND person_id = :person_id
            """
        ),
        {"record_id": int(row.record_id), "person_id": person_id},
    )
    mutated = SqlAlchemySectionReadRepository(db_tx).load_record(
        person_id, "PPR-EDUCATION", int(row.record_id)
    )
    assert isinstance(mutated, EducationRecord)
    assert mutated.updated_at != row.updated_at

    result = _executor().apply_decision(db_tx, _apply_cmd(decision.decision_id, records))
    assert result.result_status == "blocked_new_decide_required"
    assert result.decision.apply_status == APPLY_STATUS_BLOCKED
    assert result.decision.reason_code == REASON_APPLY_STALE_ROW_VERSION
    assert result.redecide_required is True

    loaded = SqlAlchemySectionReadRepository(db_tx).load_record(
        person_id, "PPR-EDUCATION", int(row.record_id)
    )
    assert isinstance(loaded, EducationRecord)
    assert loaded.specialty == "Биология"
    assert (loaded.metadata or {}).get("reconciliation_decision_id") is None


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_ex12b_error_after_ppr_mutation_rolls_back_ppr_and_status(
    seed, db_tx, monkeypatch
) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    _materialize(db_tx, person_id)
    records = [intake_row(institution="Rollback Uni")]
    decided = _engine().decide_section(db_tx, _decide_cmd(application_id, person_id, records))
    decision = decided.decisions[0].decision

    original = SqlAlchemyReconciliationDecisionRepository.transition_to_terminal

    def _boom(self, command):  # noqa: ANN001
        if command.to_status == APPLY_STATUS_APPLIED:
            raise RuntimeError("injected post-ppr terminal failure")
        return original(self, command)

    monkeypatch.setattr(
        SqlAlchemyReconciliationDecisionRepository,
        "transition_to_terminal",
        _boom,
    )

    with pytest.raises(RuntimeError, match="injected post-ppr terminal failure"):
        _executor().apply_decision(db_tx, _apply_cmd(decision.decision_id, records))

    reloaded = SqlAlchemyReconciliationDecisionRepository(db_tx).require_by_id(
        decision.decision_id
    )
    assert reloaded.apply_status == APPLY_STATUS_PENDING
    assert reloaded.failure_evidence is None
    assert _active_education_count(db_tx, person_id) == 0


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_ex_u2_owned_transaction_commits_add_visibly(seed) -> None:
    """Executor owns a full U2 txn on a clean Connection; commit is visible after close."""
    _require_schema()
    records = [intake_row(institution="Owned Tx Uni")]

    with engine.begin() as setup:
        person_id, application_id = _seed(setup, seed)
        _materialize(setup, person_id)
        decided = _engine().decide_section(
            setup, _decide_cmd(application_id, person_id, records)
        )
        decision_id = int(decided.decisions[0].decision.decision_id)

    apply_conn = engine.connect()
    try:
        assert apply_conn.in_transaction() is False
        result = _executor().apply_decision(
            apply_conn, _apply_cmd(decision_id, records)
        )
        assert result.result_status == "applied"
        assert result.decision.apply_status == APPLY_STATUS_APPLIED
        assert result.section_record_id is not None
        assert apply_conn.in_transaction() is False
        section_record_id = int(result.section_record_id)
    finally:
        apply_conn.close()

    verify_conn = engine.connect()
    try:
        decision = SqlAlchemyReconciliationDecisionRepository(verify_conn).require_by_id(
            decision_id
        )
        assert decision.apply_status == APPLY_STATUS_APPLIED
        assert _active_education_count(verify_conn, person_id) == 1
        loaded = SqlAlchemySectionReadRepository(verify_conn).load_record(
            person_id, "PPR-EDUCATION", section_record_id
        )
        assert isinstance(loaded, EducationRecord)
        assert loaded.institution_name == "Owned Tx Uni"
        assert (loaded.metadata or {}).get("reconciliation_decision_id") == decision_id
    finally:
        verify_conn.rollback()
        verify_conn.close()

    # Committed fixture data must be removed so session-scoped seed teardown can succeed.
    with engine.begin() as cleanup:
        cleanup.execute(
            text(
                """
                DELETE FROM public.personnel_intake_reconciliation_decisions
                WHERE decision_id = :decision_id
                """
            ),
            {"decision_id": decision_id},
        )
        cleanup_person_graph(cleanup, person_ids=[person_id], employee_ids=[])
