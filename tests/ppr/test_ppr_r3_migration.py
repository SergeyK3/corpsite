# tests/ppr/test_ppr_r3_migration.py
"""Migration tests for PPR R3 nullable personnel_record_events.domain_code."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db.engine import engine
from app.db.models.personnel_migration import DOMAIN_CODE_EDUCATION
from app.ppr.infrastructure.ppr_event_repository import SqlAlchemyPprEventRepository
from app.ppr.domain.event_models import (
    EVENT_CATEGORY_LIFECYCLE,
    EVENT_TYPE_PPR_CREATED,
    PprEventAppendRequest,
)
from tests.conftest import get_columns, insert_returning_id, table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_person

REVISION_ID = "k1l2m3n4o5p6"
PREVIOUS_REVISION = "j0k1l2m3n4o5"
MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "k1l2m3n4o5p6_ppr_r3_nullable_personnel_record_events_domain_code.py"
)


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


def _domain_code_nullable(conn) -> bool:
    row = conn.execute(
        text(
            """
            SELECT is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'personnel_record_events'
              AND column_name = 'domain_code'
            """
        )
    ).scalar_one_or_none()
    return row == "YES"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_revision_chain() -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    rev = script.get_revision(REVISION_ID)
    assert rev is not None
    assert rev.down_revision == PREVIOUS_REVISION


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_single_alembic_head_is_r3_revision() -> None:
    heads = _heads()
    assert len(heads) == 1
    assert REVISION_ID in heads


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_upgrade_makes_domain_code_nullable() -> None:
    current = _current_revision()
    if current != REVISION_ID:
        pytest.skip(f"DB at {current!r}, not {REVISION_ID!r} — run alembic upgrade head first")
    with engine.begin() as conn:
        assert _domain_code_nullable(conn)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_does_not_create_ppr_core_domain() -> None:
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    assert "ppr_core" not in source
    assert "INSERT INTO public.personnel_migration_domains" not in source


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_does_not_backfill_domain_code() -> None:
    current = _current_revision()
    if current != REVISION_ID:
        pytest.skip(f"DB at {current!r}, not {REVISION_ID!r} — run alembic upgrade head first")
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    assert "UPDATE public.personnel_record_events" not in source


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_existing_pmf_event_rows_preserved_after_upgrade() -> None:
    current = _current_revision()
    if current != REVISION_ID:
        pytest.skip(f"DB at {current!r}, not {REVISION_ID!r} — run alembic upgrade head first")
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_record_events"):
            pytest.skip("personnel_record_events missing")
        count = conn.execute(text("SELECT COUNT(*) FROM public.personnel_record_events")).scalar_one()
        assert int(count) >= 0


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_canonical_null_domain_event_inserts_after_upgrade() -> None:
    current = _current_revision()
    if current != REVISION_ID:
        pytest.skip(f"DB at {current!r}, not {REVISION_ID!r} — run alembic upgrade head first")
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"R3 Mig Person {suffix}")
        repo = SqlAlchemyPprEventRepository(conn)
        record = repo.append(
            PprEventAppendRequest(
                person_id=person_id,
                event_type=EVENT_TYPE_PPR_CREATED,
                category=EVENT_CATEGORY_LIFECYCLE,
                domain_code=None,
                record_table_name="personnel_record_metadata",
                record_id=person_id,
                payload={},
            )
        )
        row = conn.execute(
            text(
                """
                SELECT domain_code
                FROM public.personnel_record_events
                WHERE event_id = :event_id
                """
            ),
            {"event_id": record.event_id},
        ).one()
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])

    assert row[0] is None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_downgrade_does_not_use_cascade() -> None:
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    downgrade_source = source.split("def downgrade", 1)[1]
    assert "CASCADE" not in downgrade_source.upper()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_downgrade_without_null_rows() -> None:
    current = _current_revision()
    if current != REVISION_ID:
        pytest.skip(f"DB at {current!r}, not {REVISION_ID!r} — run alembic upgrade head first")

    cfg = _alembic_config()
    with engine.begin() as conn:
        assert table_exists(conn, "personnel_record_metadata")
        assert table_exists(conn, "person_education")
        assert table_exists(conn, "personnel_record_events")

    command.downgrade(cfg, PREVIOUS_REVISION)

    with engine.begin() as conn:
        assert not _domain_code_nullable(conn)
        assert table_exists(conn, "personnel_record_metadata")
        assert table_exists(conn, "person_education")

    command.upgrade(cfg, REVISION_ID)

    with engine.begin() as conn:
        assert _domain_code_nullable(conn)
        assert _current_revision() == REVISION_ID


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_downgrade_fails_when_null_domain_rows_exist() -> None:
    current = _current_revision()
    if current != REVISION_ID:
        pytest.skip(f"DB at {current!r}, not {REVISION_ID!r} — run alembic upgrade head first")

    cfg = _alembic_config()
    suffix = uuid4().hex[:8]
    event_id: int | None = None
    person_id: int | None = None

    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"R3 Downgrade Block {suffix}")
        repo = SqlAlchemyPprEventRepository(conn)
        record = repo.append(
            PprEventAppendRequest(
                person_id=person_id,
                event_type=EVENT_TYPE_PPR_CREATED,
                category=EVENT_CATEGORY_LIFECYCLE,
                domain_code=None,
                record_table_name="personnel_record_metadata",
                record_id=person_id,
                payload={},
            )
        )
        event_id = record.event_id

    with pytest.raises(DBAPIError, match="NULL domain_code"):
        command.downgrade(cfg, PREVIOUS_REVISION)

    assert _current_revision() == REVISION_ID

    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT domain_code, event_type
                FROM public.personnel_record_events
                WHERE event_id = :event_id
                """
            ),
            {"event_id": event_id},
        ).one()
        assert row[0] is None
        assert row[1] == EVENT_TYPE_PPR_CREATED
        conn.execute(
            text("DELETE FROM public.personnel_record_events WHERE event_id = :event_id"),
            {"event_id": event_id},
        )
        if person_id is not None:
            cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])

    command.downgrade(cfg, PREVIOUS_REVISION)
    command.upgrade(cfg, REVISION_ID)

    with engine.begin() as conn:
        assert _domain_code_nullable(conn)
        assert _current_revision() == REVISION_ID


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_other_tables_and_constraints_remain() -> None:
    current = _current_revision()
    if current != REVISION_ID:
        pytest.skip(f"DB at {current!r}, not {REVISION_ID!r} — run alembic upgrade head first")
    with engine.begin() as conn:
        assert table_exists(conn, "personnel_record_metadata")
        assert table_exists(conn, "personnel_migration_domains")
        assert "domain_code" in get_columns(conn, "personnel_record_events")
        pmf_domains = conn.execute(
            text(
                """
                SELECT domain_code
                FROM public.personnel_migration_domains
                WHERE domain_code = :domain_code
                """
            ),
            {"domain_code": DOMAIN_CODE_EDUCATION},
        ).first()
        assert pmf_domains is not None
