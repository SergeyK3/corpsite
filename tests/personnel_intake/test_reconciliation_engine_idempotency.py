"""E10–E12, E10a–E10c, E19, E22 — idempotency / version / correlation."""
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
    APPLY_STATUS_APPLIED,
    APPLY_STATUS_PENDING,
    APPLY_STATUS_SKIPPED_MANUAL,
)
from app.personnel_intake.domain.reconciliation.errors import (
    ReconciliationConflictError,
    ReconciliationValidationError,
)
from app.personnel_intake.domain.reconciliation.models import TerminalTransitionCommand
from app.personnel_intake.infrastructure.reconciliation_repository import (
    SqlAlchemyReconciliationDecisionRepository,
)
from tests.conftest import insert_returning_id, table_exists
from tests.personnel_intake.recon_engine_fakes import FakeSectionPlugin, proposal
from tests.ppr.conftest import insert_person, ppr_db_available

TABLE = "personnel_intake_reconciliation_decisions"


def _require_schema() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, TABLE):
            pytest.skip(f"{TABLE} missing — run: alembic upgrade head")


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
    person_id = insert_person(db_tx, full_name=f"Idem {uuid4().hex[:6]}")
    application_id = insert_returning_id(
        db_tx,
        table="personnel_applications",
        id_col="application_id",
        values={
            "person_id": person_id,
            "application_received_at": date(2026, 7, 24),
            "registered_by_user_id": int(seed["initiator_user_id"]),
            "idempotency_key": f"recon-idem-{uuid4().hex}",
        },
    )
    return person_id, application_id


def _engine_with(plugin: FakeSectionPlugin) -> ReconciliationDecisionEngine:
    registry = SectionReconciliationRegistry()
    registry.register(plugin)
    return ReconciliationDecisionEngine(registry)


def _cmd(application_id: int, person_id: int, **overrides) -> DecideSectionCommand:
    data = dict(
        application_id=application_id,
        person_id=person_id,
        section_code="education",
        section_payload={},
        decision_source="system",
        correlation_id="corr-stable",
        digest_algorithm_version="canon-json-v1",
    )
    data.update(overrides)
    return DecideSectionCommand(**data)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_e10_idempotent_redecide_pending(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    plugin = FakeSectionPlugin(
        proposals=[proposal(0)],
        default_match=MatchOutcome(match_kind="none", match_confidence="high"),
    )
    eng = _engine_with(plugin)
    first = eng.decide_section(db_tx, _cmd(application_id, person_id))
    second = eng.decide_section(db_tx, _cmd(application_id, person_id))
    assert second.result_status == "idempotent_replay"
    assert second.batch_idempotent_replay is True
    assert second.decisions[0].idempotent_replay is True
    assert second.decisions[0].decision.decision_id == first.decisions[0].decision.decision_id
    assert second.decisions[0].decision.apply_status == APPLY_STATUS_PENDING
    assert (
        db_tx.execute(
            text(f"SELECT count(*) FROM {TABLE} WHERE application_id = :aid"),
            {"aid": application_id},
        ).scalar_one()
        == 1
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
@pytest.mark.parametrize(
    "to_status",
    [APPLY_STATUS_APPLIED, APPLY_STATUS_SKIPPED_MANUAL],
)
def test_e10a_terminal_replay_allowed(seed, db_tx, to_status: str) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    action_match = (
        MatchOutcome(match_kind="none", match_confidence="high")
        if to_status == APPLY_STATUS_APPLIED
        else MatchOutcome(match_kind="ambiguous", match_confidence="high", candidate_canonical_record_ids=(1, 2))
    )
    # skipped_manual requires manual_review action
    if to_status == APPLY_STATUS_SKIPPED_MANUAL:
        plugin = FakeSectionPlugin(
            proposals=[proposal(0)],
            default_match=MatchOutcome(
                match_kind="ambiguous",
                match_confidence="high",
                candidate_canonical_record_ids=(1, 2),
            ),
        )
    else:
        plugin = FakeSectionPlugin(proposals=[proposal(0)], default_match=action_match)

    eng = _engine_with(plugin)
    first = eng.decide_section(db_tx, _cmd(application_id, person_id))
    decision = first.decisions[0].decision
    repo = SqlAlchemyReconciliationDecisionRepository(db_tx)
    repo.transition_to_terminal(
        TerminalTransitionCommand(
            decision_id=decision.decision_id,
            expected_row_version=decision.row_version,
            to_status=to_status,
        )
    )
    second = eng.decide_section(db_tx, _cmd(application_id, person_id))
    assert second.decisions[0].idempotent_replay is True
    assert second.decisions[0].decision.apply_status == to_status
    assert second.decisions[0].decision.decision_id == decision.decision_id
    assert second.result_status == "idempotent_replay"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_e10c_mixed_fresh_and_replay(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    plugin = FakeSectionPlugin(
        proposals=[proposal(0, content={"a": 0})],
        default_match=MatchOutcome(match_kind="none", match_confidence="high"),
    )
    eng = _engine_with(plugin)
    first = eng.decide_section(db_tx, _cmd(application_id, person_id))
    decision = first.decisions[0].decision
    SqlAlchemyReconciliationDecisionRepository(db_tx).transition_to_terminal(
        TerminalTransitionCommand(
            decision_id=decision.decision_id,
            expected_row_version=decision.row_version,
            to_status=APPLY_STATUS_APPLIED,
        )
    )
    # Add second proposal → new intent for index 1; index 0 replays applied.
    plugin.proposals = [proposal(0, content={"a": 0}), proposal(1, content={"a": 1})]
    mixed = eng.decide_section(db_tx, _cmd(application_id, person_id))
    assert mixed.result_status == "mixed"
    assert mixed.batch_idempotent_replay is False
    assert mixed.summary.pending == 1
    assert mixed.summary.applied == 1
    assert sorted(o.idempotent_replay for o in mixed.decisions) == [False, True]


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_e11_matcher_version_bump(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    plugin = FakeSectionPlugin(
        proposals=[proposal(0)],
        matcher_version="1.0.0",
        default_match=MatchOutcome(match_kind="none", match_confidence="high"),
    )
    eng = _engine_with(plugin)
    first = eng.decide_section(db_tx, _cmd(application_id, person_id))
    plugin.matcher_version = "1.0.1"
    second = eng.decide_section(db_tx, _cmd(application_id, person_id))
    assert second.decisions[0].idempotent_replay is False
    assert second.decisions[0].decision.decision_id != first.decisions[0].decision.decision_id
    assert second.decisions[0].decision.idempotency_key.startswith("recon:v1:")
    assert (
        second.decisions[0].decision.idempotency_key
        != first.decisions[0].decision.idempotency_key
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_e12_policy_version_bump(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    plugin = FakeSectionPlugin(
        proposals=[proposal(0)],
        policy_version="1.0.0",
        default_match=MatchOutcome(match_kind="none", match_confidence="high"),
    )
    eng = _engine_with(plugin)
    first = eng.decide_section(db_tx, _cmd(application_id, person_id))
    second = eng.decide_section(
        db_tx,
        _cmd(application_id, person_id, policy_version_override="2.0.0"),
    )
    assert second.decisions[0].idempotent_replay is False
    assert second.decisions[0].decision.decision_id != first.decisions[0].decision.decision_id
    assert second.policy_version == "2.0.0"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_e19_digest_algorithm_version(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    plugin = FakeSectionPlugin(
        proposals=[proposal(0)],
        default_match=MatchOutcome(match_kind="none", match_confidence="high"),
    )
    eng = _engine_with(plugin)
    ok = eng.decide_section(
        db_tx,
        _cmd(application_id, person_id, digest_algorithm_version="canon-json-v1"),
    )
    assert ok.digest_algorithm_version == "canon-json-v1"

    with pytest.raises(ReconciliationValidationError) as exc:
        eng.decide_section(
            db_tx,
            _cmd(application_id, person_id, digest_algorithm_version="canon-json-v2"),
        )
    assert exc.value.code == "UNSUPPORTED_DIGEST_ALGORITHM"
    # Only the successful decide row exists.
    assert (
        db_tx.execute(
            text(f"SELECT count(*) FROM {TABLE} WHERE application_id = :aid"),
            {"aid": application_id},
        ).scalar_one()
        == 1
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_e22_correlation_id_conflict(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    plugin = FakeSectionPlugin(
        proposals=[proposal(0)],
        default_match=MatchOutcome(match_kind="none", match_confidence="high"),
    )
    eng = _engine_with(plugin)
    eng.decide_section(db_tx, _cmd(application_id, person_id, correlation_id="corr-a"))
    with pytest.raises(ReconciliationConflictError):
        eng.decide_section(db_tx, _cmd(application_id, person_id, correlation_id="corr-b"))
