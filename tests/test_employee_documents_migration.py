# tests/test_employee_documents_migration.py
from __future__ import annotations

import pytest
from sqlalchemy import text

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.db.engine import engine
from tests.conftest import table_exists

REVISION_ID = "d9e8f71a2b05"
PREVIOUS_REVISION = "c7f3d92a1e04"


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


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_revision_chain():
    script = ScriptDirectory.from_config(_alembic_config())
    rev = script.get_revision(REVISION_ID)
    assert rev is not None
    assert rev.down_revision == PREVIOUS_REVISION


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_phase_1a_tables_and_seed_present():
    with engine.begin() as conn:
        for table in (
            "medical_specialty_groups",
            "medical_specialties",
            "document_types",
            "document_kinds",
            "employee_documents",
        ):
            if not table_exists(conn, table):
                pytest.skip(
                    f"{table} missing — run: alembic upgrade head "
                    f"(revision {REVISION_ID})"
                )

        groups = conn.execute(
            text("SELECT COUNT(*) FROM public.medical_specialty_groups")
        ).scalar()
        specialties = conn.execute(
            text("SELECT COUNT(*) FROM public.medical_specialties")
        ).scalar()
        doc_types = conn.execute(text("SELECT COUNT(*) FROM public.document_types")).scalar()
        doc_kinds = conn.execute(text("SELECT COUNT(*) FROM public.document_kinds")).scalar()

        assert int(groups) >= 2
        assert int(specialties) >= 6
        assert int(doc_types) >= 7
        assert int(doc_kinds) == 6


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_employee_documents_fk_and_check_constraints():
    with engine.begin() as conn:
        if not table_exists(conn, "employee_documents"):
            pytest.skip("employee_documents missing — run alembic upgrade head")

        with pytest.raises(Exception):
            conn.execute(
                text(
                    """
                    INSERT INTO public.employee_documents (
                        employee_id, document_type_id, lifecycle_status, created_by
                    )
                    VALUES (-999999, -999999, 'ACTIVE', -999999)
                    """
                )
            )

        with pytest.raises(Exception):
            conn.execute(
                text(
                    """
                    INSERT INTO public.employee_documents (
                        employee_id, document_type_id, lifecycle_status, created_by
                    )
                    VALUES (1, 1, 'INVALID_STATUS', 1)
                    """
                )
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_downgrade_and_upgrade_roundtrip():
    current = _current_revision()
    if current != REVISION_ID:
        pytest.skip(f"DB at {current!r}, not {REVISION_ID!r} — run alembic upgrade head first")

    cfg = _alembic_config()
    try:
        command.downgrade(cfg, PREVIOUS_REVISION)
        with engine.begin() as conn:
            assert not table_exists(conn, "employee_documents")
            assert not table_exists(conn, "document_kinds")
            assert not table_exists(conn, "document_types")
            assert not table_exists(conn, "medical_specialties")
            assert not table_exists(conn, "medical_specialty_groups")

        command.upgrade(cfg, REVISION_ID)
        with engine.begin() as conn:
            assert table_exists(conn, "employee_documents")
            assert table_exists(conn, "document_kinds")
            assert table_exists(conn, "document_types")
    finally:
        if _current_revision() != REVISION_ID:
            command.upgrade(cfg, REVISION_ID)
