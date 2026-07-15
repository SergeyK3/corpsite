# tests/ppr/test_unit_of_work.py
"""UnitOfWork contract tests (PPR R4)."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_migration import EDUCATION_KIND_BASIC
from app.ppr.domain.section_commands import AddEducationRecord
from app.ppr.domain.section_handlers import handle_add_education_record
from app.ppr.domain.section_models import EducationRecord, SECTION_CODE_PPR_EDUCATION
from app.ppr.domain.unit_of_work import UnitOfWork
from app.ppr.infrastructure.section_repository import SqlAlchemySectionMutationRepository
from app.ppr.infrastructure.unit_of_work import SqlAlchemyUnitOfWork
from tests.conftest import table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_person, ppr_db_available, require_ppr_schema


@pytest.fixture
def uow_person_id():
    require_ppr_schema()
    with engine.begin() as conn:
        if not table_exists(conn, "person_education"):
            pytest.skip("person_education missing — run: alembic upgrade head")
        person_id = insert_person(conn, full_name=f"PPR UoW Person {uuid4().hex[:8]}")
    yield person_id
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_uow_commit_persists_section_mutation(uow_person_id: int) -> None:
    record_id: int
    with SqlAlchemyUnitOfWork() as uow:
        inserted = uow.section_mutations().insert_record(
            EducationRecord(
                person_id=uow_person_id,
                education_kind=EDUCATION_KIND_BASIC,
                institution_name="UoW Commit",
            )
        )
        record_id = inserted.record_id or 0
        uow.commit()

    with engine.begin() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM public.person_education WHERE education_id = :record_id"),
            {"record_id": record_id},
        ).scalar_one()
    assert int(count) == 1


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_uow_rollback_discards_section_mutation(uow_person_id: int) -> None:
    record_id: int
    with SqlAlchemyUnitOfWork() as uow:
        inserted = uow.section_mutations().insert_record(
            EducationRecord(
                person_id=uow_person_id,
                education_kind=EDUCATION_KIND_BASIC,
                institution_name="UoW Rollback",
            )
        )
        record_id = inserted.record_id or 0
        uow.rollback()

    with engine.begin() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM public.person_education WHERE education_id = :record_id"),
            {"record_id": record_id},
        ).scalar_one()
    assert int(count) == 0


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_repositories_share_uow_connection(uow_person_id: int) -> None:
    with SqlAlchemyUnitOfWork() as uow:
        read_a = uow.sections
        read_b = uow.sections
        assert read_a is read_b
        inserted = uow.section_mutations().insert_record(
            EducationRecord(
                person_id=uow_person_id,
                education_kind=EDUCATION_KIND_BASIC,
                institution_name="Shared Conn",
            )
        )
        loaded = read_a.load_record(
            uow_person_id,
            SECTION_CODE_PPR_EDUCATION,
            inserted.record_id or 0,
        )

    assert loaded is not None


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_handler_with_explicit_uow_commit(uow_person_id: int) -> None:
    with SqlAlchemyUnitOfWork() as uow:
        handle_add_education_record(
            AddEducationRecord(
                person_id=uow_person_id,
                education_kind=EDUCATION_KIND_BASIC,
                institution_name="Handler UoW",
            ),
            uow,
        )
        uow.commit()

    with engine.begin() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM public.person_education WHERE person_id = :person_id"),
            {"person_id": uow_person_id},
        ).scalar_one()
    assert int(count) == 1


def test_protocol_surface() -> None:
    assert hasattr(UnitOfWork, "sections")
    assert hasattr(UnitOfWork, "section_mutations")
    assert hasattr(UnitOfWork, "commit")
    assert hasattr(UnitOfWork, "rollback")


def test_mutation_repository_does_not_own_transaction() -> None:
    assert not hasattr(SqlAlchemySectionMutationRepository, "commit")


def test_uow_does_not_expose_mutation_repository_property() -> None:
    assert not hasattr(SqlAlchemyUnitOfWork, "mutation_repository")
    assert "mutation_repo" not in SqlAlchemyUnitOfWork.__dict__


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_uow_closed_section_mutations_raises(uow_person_id: int) -> None:
    del uow_person_id
    uow = SqlAlchemyUnitOfWork()
    with pytest.raises(RuntimeError, match="not started"):
        uow.section_mutations()
    with pytest.raises(RuntimeError, match="not started"):
        _ = uow.sections


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_uow_context_unusable_after_exit(uow_person_id: int) -> None:
    uow = SqlAlchemyUnitOfWork()
    with uow:
        ctx = uow.section_mutations()
        assert ctx is not None
    with pytest.raises(RuntimeError, match="not started"):
        uow.section_mutations()
    with pytest.raises(RuntimeError, match="not started"):
        _ = uow.sections
