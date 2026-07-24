"""E16 / E21 — U1 savepoint atomicity and digest claim mismatch."""
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
from app.personnel_intake.domain.reconciliation.digest import CanonJsonV1DigestBuilder
from app.personnel_intake.domain.reconciliation.errors import ReconciliationValidationError
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
    person_id = insert_person(db_tx, full_name=f"U1 {uuid4().hex[:6]}")
    application_id = insert_returning_id(
        db_tx,
        table="personnel_applications",
        id_col="application_id",
        values={
            "person_id": person_id,
            "application_received_at": date(2026, 7, 24),
            "registered_by_user_id": int(seed["initiator_user_id"]),
            "idempotency_key": f"recon-u1-{uuid4().hex}",
        },
    )
    return person_id, application_id


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_e16_partial_failure_after_create_pending_rolls_back(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    plugin = FakeSectionPlugin(
        proposals=[proposal(0, content={"i": 0}), proposal(1, content={"i": 1})],
        default_match=MatchOutcome(match_kind="none", match_confidence="high"),
        fail_on_match_index=1,
    )
    registry = SectionReconciliationRegistry()
    registry.register(plugin)
    eng = ReconciliationDecisionEngine(registry)
    cmd = DecideSectionCommand(
        application_id=application_id,
        person_id=person_id,
        section_code="education",
        section_payload={},
    )
    with pytest.raises(RuntimeError, match="injected failure"):
        eng.decide_section(db_tx, cmd)

    assert (
        db_tx.execute(
            text(f"SELECT count(*) FROM {TABLE} WHERE application_id = :aid"),
            {"aid": application_id},
        ).scalar_one()
        == 0
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_e16_caller_catch_still_zero_rows(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    plugin = FakeSectionPlugin(
        proposals=[proposal(0), proposal(1)],
        default_match=MatchOutcome(match_kind="none", match_confidence="high"),
        fail_on_match_index=1,
    )
    registry = SectionReconciliationRegistry()
    registry.register(plugin)
    eng = ReconciliationDecisionEngine(registry)
    cmd = DecideSectionCommand(
        application_id=application_id,
        person_id=person_id,
        section_code="education",
        section_payload={},
    )
    try:
        eng.decide_section(db_tx, cmd)
    except RuntimeError:
        pass

    assert (
        db_tx.execute(
            text(f"SELECT count(*) FROM {TABLE} WHERE application_id = :aid"),
            {"aid": application_id},
        ).scalar_one()
        == 0
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_e16_digest_enrich_failure_before_persist(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    plugin = FakeSectionPlugin(
        proposals=[proposal(0, content={"v": float("nan")})],
        default_match=MatchOutcome(match_kind="none", match_confidence="high"),
    )
    registry = SectionReconciliationRegistry()
    registry.register(plugin)
    eng = ReconciliationDecisionEngine(registry)
    with pytest.raises(ReconciliationValidationError) as exc:
        eng.decide_section(
            db_tx,
            DecideSectionCommand(
                application_id=application_id,
                person_id=person_id,
                section_code="education",
                section_payload={},
            ),
        )
    assert exc.value.code == "INVALID_DIGEST_INPUT"
    assert (
        db_tx.execute(
            text(f"SELECT count(*) FROM {TABLE} WHERE application_id = :aid"),
            {"aid": application_id},
        ).scalar_one()
        == 0
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_e21_plugin_digest_claim_mismatch_rolls_back(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    content = {"school": "X"}
    wrong_claim = "0" * 64
    plugin = FakeSectionPlugin(
        proposals=[
            proposal(0, content=content),
            proposal(1, content={"school": "Y"}, claimed_payload_digest=wrong_claim),
        ],
        default_match=MatchOutcome(match_kind="none", match_confidence="high"),
    )
    registry = SectionReconciliationRegistry()
    registry.register(plugin)
    eng = ReconciliationDecisionEngine(registry)
    with pytest.raises(ReconciliationValidationError) as exc:
        eng.decide_section(
            db_tx,
            DecideSectionCommand(
                application_id=application_id,
                person_id=person_id,
                section_code="education",
                section_payload={},
            ),
        )
    assert exc.value.code == "PLUGIN_DIGEST_MISMATCH"
    assert (
        db_tx.execute(
            text(f"SELECT count(*) FROM {TABLE} WHERE application_id = :aid"),
            {"aid": application_id},
        ).scalar_one()
        == 0
    )
    # Sanity: correct claim would match.
    correct = CanonJsonV1DigestBuilder().payload_digest(content)
    assert wrong_claim != correct
