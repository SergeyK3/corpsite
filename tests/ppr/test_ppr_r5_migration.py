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


def _revision_is_ancestor_of_head(revision_id: str, head_revision_id: str) -> bool:
    script = ScriptDirectory.from_config(_alembic_config())
    current = script.get_revision(head_revision_id)
    seen: set[str] = set()
    while current is not None:
        if current.revision == revision_id:
            return True
        if current.revision in seen:
            break
        seen.add(current.revision)
        current = script.get_revision(current.down_revision) if current.down_revision else None
    return False


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_migration_revision_chain() -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    rev = script.get_revision(REVISION_ID)
    assert rev is not None
    assert rev.down_revision == PREVIOUS_REVISION


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_r5_revision_is_ancestor_of_current_head() -> None:
    heads = _heads()
    assert len(heads) == 1
    head_revision_id = next(iter(heads))
    script = ScriptDirectory.from_config(_alembic_config())
    assert script.get_revision(REVISION_ID) is not None
    assert _revision_is_ancestor_of_head(REVISION_ID, head_revision_id), (
        f"{REVISION_ID} is not an ancestor of head {head_revision_id!r}"
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_repository_has_single_alembic_head() -> None:
    assert len(_heads()) == 1


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_current_alembic_head_is_single_repository_revision() -> None:
    heads = _heads()
    assert len(heads) == 1
    head_revision_id = next(iter(heads))
    script = ScriptDirectory.from_config(_alembic_config())
    assert script.get_revision(head_revision_id) is not None
    assert _revision_is_ancestor_of_head(REVISION_ID, head_revision_id)


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
