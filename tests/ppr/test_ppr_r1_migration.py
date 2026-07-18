# tests/ppr/test_ppr_r1_migration.py
"""Migration tests for PPR R1 personnel_record_metadata."""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.db.engine import engine
from tests.conftest import get_columns, table_exists

REVISION_ID = "j0k1l2m3n4o5"
PREVIOUS_REVISION = "i9j0k1l2m3n4"
MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "j0k1l2m3n4o5_ppr_r1_personnel_record_metadata.py"
)

EXPECTED_COLUMNS = {
    "person_id",
    "ppr_lifecycle_state",
    "hr_relationship_context",
    "version",
    "created_at",
    "updated_at",
}


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _alembic_config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", str(engine.url.render_as_string(hide_password=False)))
    return cfg


def _current_revision() -> str | None:
    with engine.begin() as conn:
        if not table_exists(conn, "alembic_version"):
            return None
        row = conn.execute(text("SELECT version_num FROM public.alembic_version LIMIT 1")).first()
        return str(row[0]) if row else None


def _heads() -> set[str]:
    script = ScriptDirectory.from_config(_alembic_config())
    return set(script.get_heads())


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_revision_chain() -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    rev = script.get_revision(REVISION_ID)
    assert rev is not None
    assert rev.down_revision == PREVIOUS_REVISION


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_single_alembic_head() -> None:
    heads = _heads()
    assert len(heads) == 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_revision_is_ancestor_of_current_head() -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    heads = _heads()
    assert len(heads) == 1
    head_revision = heads.pop()
    walk = script.get_revision(head_revision)
    found = False
    while walk is not None:
        if walk.revision == REVISION_ID:
            found = True
            break
        walk = script.get_revision(walk.down_revision) if walk.down_revision else None
    assert found, f"{REVISION_ID} is not an ancestor of head {head_revision}"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_personnel_record_metadata_table_columns() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_record_metadata"):
            pytest.skip(
                f"personnel_record_metadata missing — run: alembic upgrade head ({REVISION_ID})"
            )
        cols = get_columns(conn, "personnel_record_metadata")
        assert EXPECTED_COLUMNS.issubset(cols)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_does_not_backfill_envelopes() -> None:
    upgrade_source = MIGRATION_FILE.read_text(encoding="utf-8").split("def upgrade", 1)[1]
    upgrade_source = upgrade_source.split("def downgrade", 1)[0].upper()
    assert "INSERT INTO PUBLIC.PERSONNEL_RECORD_METADATA" not in upgrade_source
    assert "INSERT INTO PERSONNEL_RECORD_METADATA" not in upgrade_source


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_downgrade_does_not_use_cascade() -> None:
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    downgrade_source = source.split("def downgrade", 1)[1]
    assert "CASCADE" not in downgrade_source.upper()
    assert 'op.drop_table("personnel_record_metadata")' in downgrade_source


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_downgrade_removes_table_only() -> None:
    current = _current_revision()
    if current != REVISION_ID:
        pytest.skip(f"DB at {current!r}, not {REVISION_ID!r} — run alembic upgrade head first")

    cfg = _alembic_config()
    with engine.begin() as conn:
        assert table_exists(conn, "persons")
        assert table_exists(conn, "person_education")
        assert table_exists(conn, "person_training")
        assert table_exists(conn, "personnel_record_metadata")

    command.downgrade(cfg, PREVIOUS_REVISION)

    with engine.begin() as conn:
        assert not table_exists(conn, "personnel_record_metadata")
        assert table_exists(conn, "persons")
        assert table_exists(conn, "person_education")
        assert table_exists(conn, "person_training")

    command.upgrade(cfg, REVISION_ID)

    with engine.begin() as conn:
        assert table_exists(conn, "personnel_record_metadata")
        assert _current_revision() == REVISION_ID
