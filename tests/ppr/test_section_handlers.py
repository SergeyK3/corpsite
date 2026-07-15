# tests/ppr/test_section_handlers.py
"""Handler tests for PPR R4 domain section commands."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_migration import EDUCATION_KIND_BASIC, TRAINING_KIND_COURSE
from app.ppr.domain.errors import SectionDuplicateRecordError, SectionValidationError
from app.ppr.domain.section_commands import (
    AddEducationRecord,
    AddTrainingRecord,
    UpdateEducationRecord,
    VoidEducationRecord,
)
from app.ppr.domain.section_handlers import (
    handle_add_education_record,
    handle_add_training_record,
    handle_update_education_record,
    handle_void_education_record,
)
from app.ppr.domain.section_models import (
    MUTATION_KIND_INSERT,
    MUTATION_KIND_UPDATE,
    MUTATION_KIND_VOID,
    SECTION_CODE_PPR_TRAINING,
    EducationRecord,
    SectionMutationResult,
)
from app.ppr.infrastructure.unit_of_work import SqlAlchemyUnitOfWork
from tests.conftest import table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_person, ppr_db_available, require_ppr_schema


def _require_section_schema() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "person_education"):
            pytest.skip("person_education missing — run: alembic upgrade head")


@pytest.fixture
def handler_person_id():
    require_ppr_schema()
    _require_section_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"PPR Handler Person {suffix}")
    yield person_id
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_handle_add_education_record_persists_on_commit(handler_person_id: int) -> None:
    record_id: int
    with SqlAlchemyUnitOfWork() as uow:
        result = handle_add_education_record(
            AddEducationRecord(
                person_id=handler_person_id,
                education_kind=EDUCATION_KIND_BASIC,
                institution_name="Handler University",
            ),
            uow,
        )
        assert isinstance(result, SectionMutationResult)
        assert result.mutation_kind == MUTATION_KIND_INSERT
        assert isinstance(result.record, EducationRecord)
        record_id = result.record.record_id or 0
        uow.commit()

    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT institution_name
                FROM public.person_education
                WHERE education_id = :record_id
                """
            ),
            {"record_id": record_id},
        ).one()
    assert row[0] == "Handler University"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_uow_sections_has_no_direct_mutation_methods(handler_person_id: int) -> None:
    with SqlAlchemyUnitOfWork() as uow:
        assert not hasattr(uow.sections, "insert_record")
        assert not hasattr(uow.sections, "void_record")
        assert hasattr(uow, "section_mutations")


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_handler_does_not_commit_without_uow_commit(handler_person_id: int) -> None:
    with SqlAlchemyUnitOfWork() as uow:
        result = handle_add_education_record(
            AddEducationRecord(
                person_id=handler_person_id,
                education_kind=EDUCATION_KIND_BASIC,
                institution_name="Rollback University",
            ),
            uow,
        )
        record_id = result.record.record_id or 0

    with engine.begin() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM public.person_education WHERE education_id = :record_id"),
            {"record_id": record_id},
        ).scalar_one()
    assert int(count) == 0


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_handler_duplicate_education_raises(handler_person_id: int) -> None:
    with SqlAlchemyUnitOfWork() as uow:
        handle_add_education_record(
            AddEducationRecord(
                person_id=handler_person_id,
                education_kind=EDUCATION_KIND_BASIC,
                institution_name="Duplicate U",
            ),
            uow,
        )
        with pytest.raises(SectionDuplicateRecordError):
            handle_add_education_record(
                AddEducationRecord(
                    person_id=handler_person_id,
                    education_kind=EDUCATION_KIND_BASIC,
                    institution_name="Duplicate U",
                ),
                uow,
            )
        uow.rollback()


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_handler_validation_rejects_invalid_kind(handler_person_id: int) -> None:
    with SqlAlchemyUnitOfWork() as uow:
        with pytest.raises(SectionValidationError):
            handle_add_education_record(
                AddEducationRecord(
                    person_id=handler_person_id,
                    education_kind="not-a-real-kind",
                    institution_name="Invalid",
                ),
                uow,
            )
        uow.rollback()


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_handler_update_and_void_education(handler_person_id: int) -> None:
    with SqlAlchemyUnitOfWork() as uow:
        created = handle_add_education_record(
            AddEducationRecord(
                person_id=handler_person_id,
                education_kind=EDUCATION_KIND_BASIC,
                institution_name="Original",
            ),
            uow,
        )
        assert created.record.updated_at is not None
        updated = handle_update_education_record(
            UpdateEducationRecord(
                person_id=handler_person_id,
                record_id=created.record.record_id or 0,
                expected_updated_at=created.record.updated_at,
                institution_name="Updated",
            ),
            uow,
        )
        assert updated.mutation_kind == MUTATION_KIND_UPDATE
        assert updated.record.institution_name == "Updated"
        voided = handle_void_education_record(
            VoidEducationRecord(
                person_id=handler_person_id,
                record_id=updated.record.record_id or 0,
                reason="test void",
                expected_updated_at=updated.record.updated_at,
            ),
            uow,
        )
        assert voided.mutation_kind == MUTATION_KIND_VOID
        assert voided.record.lifecycle_status == "voided"
        uow.commit()


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_handler_does_not_append_events(handler_person_id: int) -> None:
    with SqlAlchemyUnitOfWork() as uow:
        before = uow.connection.execute(
            text("SELECT COUNT(*) FROM public.personnel_record_events WHERE person_id = :person_id"),
            {"person_id": handler_person_id},
        ).scalar_one()
        handle_add_education_record(
            AddEducationRecord(
                person_id=handler_person_id,
                education_kind=EDUCATION_KIND_BASIC,
                institution_name="No Events",
            ),
            uow,
        )
        after = uow.connection.execute(
            text("SELECT COUNT(*) FROM public.personnel_record_events WHERE person_id = :person_id"),
            {"person_id": handler_person_id},
        ).scalar_one()
        uow.rollback()

    assert int(before) == int(after)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_handle_add_training_record(handler_person_id: int) -> None:
    with SqlAlchemyUnitOfWork() as uow:
        result = handle_add_training_record(
            AddTrainingRecord(
                person_id=handler_person_id,
                training_kind=TRAINING_KIND_COURSE,
                title="Domain Handler Course",
            ),
            uow,
        )
        uow.commit()

    assert result.record.record_id is not None
    assert result.record.section_code == SECTION_CODE_PPR_TRAINING
