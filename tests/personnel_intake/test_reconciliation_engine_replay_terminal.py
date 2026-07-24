"""E10b — terminal blocked/failed replay fail-closed."""
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
    APPLY_STATUS_BLOCKED,
    APPLY_STATUS_FAILED,
)
from app.personnel_intake.domain.reconciliation.errors import ReconciliationValidationError
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


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
@pytest.mark.parametrize("to_status", [APPLY_STATUS_BLOCKED, APPLY_STATUS_FAILED])
def test_e10b_terminal_replay_forbidden(seed, db_tx, to_status: str) -> None:
    _require_schema()
    person_id = insert_person(db_tx, full_name=f"Replay {uuid4().hex[:6]}")
    application_id = insert_returning_id(
        db_tx,
        table="personnel_applications",
        id_col="application_id",
        values={
            "person_id": person_id,
            "application_received_at": date(2026, 7, 24),
            "registered_by_user_id": int(seed["initiator_user_id"]),
            "idempotency_key": f"recon-term-{uuid4().hex}",
        },
    )
    plugin = FakeSectionPlugin(
        proposals=[
            proposal(0, content={"slot": "a"}),
            proposal(1, content={"slot": "b"}),
        ],
        default_match=MatchOutcome(match_kind="none", match_confidence="high"),
    )
    registry = SectionReconciliationRegistry()
    registry.register(plugin)
    eng = ReconciliationDecisionEngine(registry)
    cmd = DecideSectionCommand(
        application_id=application_id,
        person_id=person_id,
        section_code="education",
        section_payload={},
        correlation_id="corr-term",
    )
    first = eng.decide_section(db_tx, cmd)
    assert [o.proposal_index for o in first.decisions] == [0, 1]
    by_index = {o.proposal_index: o.decision for o in first.decisions}
    original_index0 = by_index[0]
    terminal_index1 = by_index[1]

    SqlAlchemyReconciliationDecisionRepository(db_tx).transition_to_terminal(
        TerminalTransitionCommand(
            decision_id=terminal_index1.decision_id,
            expected_row_version=terminal_index1.row_version,
            to_status=to_status,
            failure_evidence={"reason": "gate-failed"},
        )
    )

    # Change index-0 payload so a fresh decision would persist before index-1 replay fails.
    plugin.proposals = [
        proposal(0, content={"slot": "a-changed"}),
        proposal(1, content={"slot": "b"}),
    ]
    with pytest.raises(ReconciliationValidationError) as exc:
        eng.decide_section(db_tx, cmd)
    assert exc.value.code == "REDECIDE_TERMINAL_REQUIRES_NEW_INTENT"

    rows = db_tx.execute(
        text(
            f"""
            SELECT proposal_index, decision_id, proposal_payload_digest, apply_status
            FROM {TABLE}
            WHERE application_id = :aid
            ORDER BY proposal_index, decision_id
            """
        ),
        {"aid": application_id},
    ).mappings().all()
    assert len(rows) == 2
    assert [int(row["proposal_index"]) for row in rows] == [0, 1]
    assert int(rows[0]["decision_id"]) == original_index0.decision_id
    assert rows[0]["proposal_payload_digest"] == original_index0.proposal_payload_digest
    assert int(rows[1]["decision_id"]) == terminal_index1.decision_id
    assert rows[1]["apply_status"] == to_status

    # No fresh decision for the changed index-0 payload survived U1 rollback.
    changed_digest_count = db_tx.execute(
        text(
            f"""
            SELECT count(*)
            FROM {TABLE}
            WHERE application_id = :aid
              AND proposal_index = 0
              AND decision_id <> :original_id
            """
        ),
        {"aid": application_id, "original_id": original_index0.decision_id},
    ).scalar_one()
    assert changed_digest_count == 0
