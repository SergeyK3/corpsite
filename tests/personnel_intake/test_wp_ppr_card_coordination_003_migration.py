"""Migration tests for WP-PPR-CARD-COORDINATION-003."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import get_columns, table_exists
from tests.ppr.conftest import ppr_db_available

REVISION_ID = "q8r9s0t1u2v3"
TABLE = "personnel_intake_reconciliation_decisions"

EXPECTED_COLUMNS = {
    "decision_id",
    "application_id",
    "person_id",
    "section_code",
    "proposal_index",
    "proposal_fingerprint",
    "proposal_payload_digest",
    "action",
    "reason_code",
    "evidence",
    "target_canonical_record_id",
    "expected_row_version",
    "expected_canonical_precondition",
    "decision_source",
    "override_token",
    "matcher_rule_id",
    "matcher_version",
    "policy_version",
    "digest_algorithm_version",
    "idempotency_key",
    "intent_fingerprint",
    "apply_status",
    "failure_evidence",
    "row_version",
    "created_at",
    "updated_at",
}


@pytest.fixture
def db_ready():
    if not ppr_db_available():
        pytest.skip("PostgreSQL not available")
    with engine.begin() as conn:
        if not table_exists(conn, TABLE):
            pytest.skip(f"{TABLE} missing — run: alembic upgrade head ({REVISION_ID})")


def test_reconciliation_decisions_table_columns(db_ready) -> None:
    with engine.connect() as conn:
        cols = get_columns(conn, TABLE)
    assert EXPECTED_COLUMNS.issubset(cols)


def test_idempotency_key_unique_constraint(db_ready) -> None:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_pird_idempotency_key'
                """
            )
        ).first()
    assert row is not None


def test_apply_status_check_excludes_replayed(db_ready) -> None:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT pg_get_constraintdef(oid) AS def
                FROM pg_constraint
                WHERE conname = 'chk_pird_apply_status'
                """
            )
        ).first()
    assert row is not None
    definition = row[0]
    assert "pending" in definition
    assert "applied" in definition
    assert "skipped_manual" in definition
    assert "blocked" in definition
    assert "failed" in definition
    assert "replayed" not in definition


def test_action_check_excludes_blocked(db_ready) -> None:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT pg_get_constraintdef(oid) AS def
                FROM pg_constraint
                WHERE conname = 'chk_pird_action'
                """
            )
        ).first()
    assert row is not None
    definition = row[0]
    for action in ("add", "keep_existing", "update_version", "supersede", "manual_review"):
        assert action in definition
    assert "'blocked'" not in definition
