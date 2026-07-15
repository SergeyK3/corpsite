# tests/ppr/test_ppr_r5_migration.py
"""Migration tests for PPR R5 command idempotency table."""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import table_exists
from tests.ppr.conftest import ppr_db_available

REVISION_ID = "l2m3n4o5p6q7"
PREVIOUS_REVISION = "k1l2m3n4o5p6"
MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "alembic/versions/l2m3n4o5p6q7_ppr_r5_command_idempotency.py"
)


def _alembic_config() -> Config:
    return Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))


def _heads() -> set[str]:
    script = ScriptDirectory.from_config(_alembic_config())
    return set(script.get_heads())


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_migration_revision_chain() -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    rev = script.get_revision(REVISION_ID)
    assert rev is not None
    assert rev.down_revision == PREVIOUS_REVISION


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_single_alembic_head_is_r5_revision() -> None:
    heads = _heads()
    assert len(heads) == 1
    assert REVISION_ID in heads


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_ppr_command_executions_table_exists() -> None:
    with engine.connect() as conn:
        assert table_exists(conn, "ppr_command_executions")


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_command_id_unique_constraint() -> None:
    with engine.connect() as conn:
        cols = conn.execute(
            text(
                """
                SELECT column_name, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'ppr_command_executions'
                ORDER BY ordinal_position
                """
            )
        ).all()
    names = [row[0] for row in cols]
    assert "command_id" in names
    assert "request_fingerprint" in names
    assert "status" in names
