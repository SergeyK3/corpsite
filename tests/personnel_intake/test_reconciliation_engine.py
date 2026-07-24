"""E01–E09, E13–E15, E18, E23 — ReconciliationDecisionEngine core paths."""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.personnel_intake.application.reconciliation.dto import (
    DecideSectionCommand,
    MatchOutcome,
)
from app.personnel_intake.application.reconciliation.engine import ReconciliationDecisionEngine
from app.personnel_intake.application.reconciliation.registry import SectionReconciliationRegistry
from app.personnel_intake.domain.reconciliation.actions import (
    APPLY_STATUS_PENDING,
    EVIDENCE_SOURCE_INTAKE_RECONCILIATION,
    REASON_MATCH_AMBIGUOUS,
    REASON_MATCH_CONFIDENCE_LOW,
    REASON_MATCH_EXACT_KEEP,
    REASON_MATCH_EXACT_SUPERSEDE,
    REASON_MATCH_EXACT_UPDATE,
    REASON_MATCH_NONE_CONFIDENT,
    REASON_MATCH_STALE_TARGET,
    RECONCILE_ACTION_ADD,
    RECONCILE_ACTION_KEEP_EXISTING,
    RECONCILE_ACTION_MANUAL_REVIEW,
    RECONCILE_ACTION_SUPERSEDE,
    RECONCILE_ACTION_UPDATE_VERSION,
)
from app.personnel_intake.domain.reconciliation.errors import ReconciliationValidationError
from tests.conftest import insert_returning_id, table_exists
from tests.personnel_intake.recon_engine_fakes import FakeSectionPlugin, canonical, proposal
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
            "idempotency_key": f"recon-eng-{uuid4().hex}",
        },
    )


def _seed_app(db_tx, seed):
    person_id = insert_person(db_tx, full_name=f"Eng Person {uuid4().hex[:6]}")
    application_id = _insert_application(
        db_tx, person_id=person_id, user_id=int(seed["initiator_user_id"])
    )
    return person_id, application_id


def _engine_with(plugin: FakeSectionPlugin) -> ReconciliationDecisionEngine:
    registry = SectionReconciliationRegistry()
    registry.register(plugin)
    return ReconciliationDecisionEngine(registry)


def _cmd(
    *,
    application_id: int,
    person_id: int,
    section_code: str = "education",
    **overrides,
) -> DecideSectionCommand:
    base = dict(
        application_id=application_id,
        person_id=person_id,
        section_code=section_code,
        section_payload={"items": []},
        decision_source="system",
        correlation_id="corr-1",
        digest_algorithm_version="canon-json-v1",
    )
    base.update(overrides)
    return DecideSectionCommand(**base)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_e01_confident_new_add(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed_app(db_tx, seed)
    plugin = FakeSectionPlugin(
        proposals=[proposal(0, content={"school": "A"})],
        canonicals=[],
        default_match=MatchOutcome(match_kind="none", match_confidence="high"),
    )
    result = _engine_with(plugin).decide_section(
        db_tx, _cmd(application_id=application_id, person_id=person_id)
    )
    assert result.result_status == "fresh"
    assert result.batch_idempotent_replay is False
    assert len(result.decision_ids) == 1
    outcome = result.decisions[0]
    assert outcome.action == RECONCILE_ACTION_ADD
    assert outcome.reason_code == REASON_MATCH_NONE_CONFIDENT
    assert outcome.decision.apply_status == APPLY_STATUS_PENDING
    assert outcome.decision.evidence["source"] == EVIDENCE_SOURCE_INTAKE_RECONCILIATION
    assert outcome.decision.evidence["after_intent_digest"]
    assert outcome.decision.idempotency_key.startswith("recon:v1:")
    assert outcome.decision.expected_canonical_precondition.startswith("none-match:")


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_e02_low_confidence_manual(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed_app(db_tx, seed)
    plugin = FakeSectionPlugin(
        proposals=[proposal(0)],
        default_match=MatchOutcome(match_kind="none", match_confidence="low"),
    )
    result = _engine_with(plugin).decide_section(
        db_tx, _cmd(application_id=application_id, person_id=person_id)
    )
    assert result.decisions[0].action == RECONCILE_ACTION_MANUAL_REVIEW
    assert result.decisions[0].reason_code == REASON_MATCH_CONFIDENCE_LOW


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_e03_ambiguous_manual(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed_app(db_tx, seed)
    plugin = FakeSectionPlugin(
        proposals=[proposal(0)],
        canonicals=[canonical(10), canonical(11)],
        default_match=MatchOutcome(
            match_kind="ambiguous",
            match_confidence="high",
            candidate_canonical_record_ids=(10, 11),
        ),
    )
    result = _engine_with(plugin).decide_section(
        db_tx, _cmd(application_id=application_id, person_id=person_id)
    )
    assert result.decisions[0].action == RECONCILE_ACTION_MANUAL_REVIEW
    assert result.decisions[0].reason_code == REASON_MATCH_AMBIGUOUS
    assert result.decisions[0].decision.evidence["candidate_canonical_record_ids"] == [10, 11]


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_e04_exact_keep(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed_app(db_tx, seed)
    content = {"school": "Same"}
    plugin = FakeSectionPlugin(
        proposals=[proposal(0, content=content)],
        canonicals=[canonical(42, content=content, row_version="7")],
        default_match=MatchOutcome(
            match_kind="exact_one",
            match_confidence="high",
            matched_canonical_record_id=42,
            candidate_canonical_record_ids=(42,),
            semantically_equal=True,
        ),
    )
    result = _engine_with(plugin).decide_section(
        db_tx, _cmd(application_id=application_id, person_id=person_id)
    )
    outcome = result.decisions[0]
    assert outcome.action == RECONCILE_ACTION_KEEP_EXISTING
    assert outcome.reason_code == REASON_MATCH_EXACT_KEEP
    assert outcome.decision.target_canonical_record_id == 42
    assert outcome.decision.evidence["matched_canonical_record_id"] == 42
    assert (
        outcome.decision.evidence["after_intent_digest"]
        == outcome.decision.evidence["canonical_payload_digest_at_match"]
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_e05_exact_update(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed_app(db_tx, seed)
    plugin = FakeSectionPlugin(
        proposals=[proposal(0, content={"school": "New"})],
        canonicals=[canonical(5, content={"school": "Old"}, row_version="3")],
        exact_action="update_version",
        default_match=MatchOutcome(
            match_kind="exact_one",
            match_confidence="high",
            matched_canonical_record_id=5,
            candidate_canonical_record_ids=(5,),
            semantically_equal=False,
        ),
    )
    result = _engine_with(plugin).decide_section(
        db_tx, _cmd(application_id=application_id, person_id=person_id)
    )
    outcome = result.decisions[0]
    assert outcome.action == RECONCILE_ACTION_UPDATE_VERSION
    assert outcome.reason_code == REASON_MATCH_EXACT_UPDATE
    assert outcome.decision.expected_row_version == "3"
    assert outcome.decision.expected_canonical_precondition == "row_version:3"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_e06_exact_supersede(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed_app(db_tx, seed)
    plugin = FakeSectionPlugin(
        proposals=[proposal(0, content={"school": "New"})],
        canonicals=[canonical(5, content={"school": "Old"}, row_version="9")],
        exact_action="supersede",
        default_match=MatchOutcome(
            match_kind="exact_one",
            match_confidence="high",
            matched_canonical_record_id=5,
            candidate_canonical_record_ids=(5,),
            semantically_equal=False,
        ),
    )
    result = _engine_with(plugin).decide_section(
        db_tx, _cmd(application_id=application_id, person_id=person_id)
    )
    outcome = result.decisions[0]
    assert outcome.action == RECONCILE_ACTION_SUPERSEDE
    assert outcome.reason_code == REASON_MATCH_EXACT_SUPERSEDE
    assert outcome.decision.expected_row_version == "9"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_e07_stale_target_manual(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed_app(db_tx, seed)
    plugin = FakeSectionPlugin(
        proposals=[proposal(0)],
        default_match=MatchOutcome(match_kind="stale_target", match_confidence="high"),
    )
    result = _engine_with(plugin).decide_section(
        db_tx, _cmd(application_id=application_id, person_id=person_id)
    )
    assert result.decisions[0].action == RECONCILE_ACTION_MANUAL_REVIEW
    assert result.decisions[0].reason_code == REASON_MATCH_STALE_TARGET


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_e08_missing_plugin(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed_app(db_tx, seed)
    engine_obj = ReconciliationDecisionEngine(SectionReconciliationRegistry())
    with pytest.raises(ReconciliationValidationError) as exc:
        engine_obj.decide_section(
            db_tx, _cmd(application_id=application_id, person_id=person_id)
        )
    assert exc.value.code == "UNKNOWN_SECTION_PLUGIN"
    assert (
        db_tx.execute(
            text(f"SELECT count(*) FROM {TABLE} WHERE application_id = :aid"),
            {"aid": application_id},
        ).scalar_one()
        == 0
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_e09_incomplete_coverage(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed_app(db_tx, seed)
    plugin = FakeSectionPlugin(proposals=[proposal(0), proposal(2)])
    with pytest.raises(ReconciliationValidationError) as exc:
        _engine_with(plugin).decide_section(
            db_tx, _cmd(application_id=application_id, person_id=person_id)
        )
    assert exc.value.code == "INVALID_PROPOSAL_INDEX_SET"
    assert (
        db_tx.execute(
            text(f"SELECT count(*) FROM {TABLE} WHERE application_id = :aid"),
            {"aid": application_id},
        ).scalar_one()
        == 0
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_e13_hr_decide_rejected(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed_app(db_tx, seed)
    plugin = FakeSectionPlugin(proposals=[proposal(0)])
    with pytest.raises(ReconciliationValidationError) as exc:
        _engine_with(plugin).decide_section(
            db_tx,
            _cmd(
                application_id=application_id,
                person_id=person_id,
                decision_source="hr",
                override_token="token",
            ),
        )
    assert exc.value.code == "UNSUPPORTED_DECISION_SOURCE"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_e14_person_mismatch(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed_app(db_tx, seed)
    other_person = insert_person(db_tx, full_name=f"Other {uuid4().hex[:6]}")
    plugin = FakeSectionPlugin(proposals=[proposal(0)])
    with pytest.raises(ReconciliationValidationError) as exc:
        _engine_with(plugin).decide_section(
            db_tx,
            _cmd(application_id=application_id, person_id=other_person),
        )
    assert exc.value.code == "APPLICATION_PERSON_MISMATCH"
    assert (
        db_tx.execute(
            text(f"SELECT count(*) FROM {TABLE} WHERE application_id = :aid"),
            {"aid": application_id},
        ).scalar_one()
        == 0
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_exact_one_high_missing_semantically_equal_rolls_back(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed_app(db_tx, seed)
    plugin = FakeSectionPlugin(
        proposals=[
            proposal(0, content={"ok": True}),
            proposal(1, content={"bad": True}),
        ],
        canonicals=[canonical(9)],
        match_by_index={
            0: MatchOutcome(match_kind="none", match_confidence="high"),
            1: MatchOutcome(
                match_kind="exact_one",
                match_confidence="high",
                matched_canonical_record_id=9,
                candidate_canonical_record_ids=(9,),
                semantically_equal=None,
            ),
        },
    )
    with pytest.raises(ReconciliationValidationError) as exc:
        _engine_with(plugin).decide_section(
            db_tx, _cmd(application_id=application_id, person_id=person_id)
        )
    assert exc.value.code == "INVALID_MATCH_OUTCOME"
    assert (
        db_tx.execute(
            text(f"SELECT count(*) FROM {TABLE} WHERE application_id = :aid"),
            {"aid": application_id},
        ).scalar_one()
        == 0
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_e15_illegal_exact_action_rolls_back(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed_app(db_tx, seed)
    plugin = FakeSectionPlugin(
        proposals=[proposal(0)],
        canonicals=[canonical(1)],
        exact_action="add",
        default_match=MatchOutcome(
            match_kind="exact_one",
            match_confidence="high",
            matched_canonical_record_id=1,
            candidate_canonical_record_ids=(1,),
            semantically_equal=False,
        ),
    )
    with pytest.raises(ReconciliationValidationError) as exc:
        _engine_with(plugin).decide_section(
            db_tx, _cmd(application_id=application_id, person_id=person_id)
        )
    assert exc.value.code == "ILLEGAL_ACTION_REASON"
    assert (
        db_tx.execute(
            text(f"SELECT count(*) FROM {TABLE} WHERE application_id = :aid"),
            {"aid": application_id},
        ).scalar_one()
        == 0
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_e18_military_mode_all_or_nothing(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed_app(db_tx, seed)
    plugin = FakeSectionPlugin(
        section_code="military",
        section_apply_mode="all_or_nothing",
        proposals=[proposal(0)],
        default_match=MatchOutcome(match_kind="none", match_confidence="high"),
    )
    result = _engine_with(plugin).decide_section(
        db_tx,
        _cmd(application_id=application_id, person_id=person_id, section_code="military"),
    )
    assert result.section_apply_mode == "all_or_nothing"

    bad = FakeSectionPlugin(
        section_code="military",
        section_apply_mode="per_record",
        proposals=[proposal(0)],
    )
    with pytest.raises(ReconciliationValidationError) as exc:
        _engine_with(bad).decide_section(
            db_tx,
            _cmd(application_id=application_id, person_id=person_id, section_code="military"),
        )
    assert exc.value.code == "INVALID_SECTION_APPLY_MODE"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_e23_decision_ids_ordered(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed_app(db_tx, seed)
    plugin = FakeSectionPlugin(
        proposals=[proposal(1, content={"i": 1}), proposal(0, content={"i": 0})],
        default_match=MatchOutcome(match_kind="none", match_confidence="high"),
    )
    result = _engine_with(plugin).decide_section(
        db_tx, _cmd(application_id=application_id, person_id=person_id)
    )
    assert len(result.decision_ids) == 2
    assert [d.proposal_index for d in result.decisions] == [0, 1]
    assert result.decision_ids == tuple(d.decision.decision_id for d in result.decisions)
