# tests/ppr/test_section_repository_contract.py
"""Contract tests for section read/mutation repositories (PPR R4)."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db.engine import engine
from app.db.models.personnel_migration import (
    EDUCATION_KIND_BASIC,
    LIFECYCLE_STATUS_ACTIVE,
    LIFECYCLE_STATUS_SUPERSEDED,
    LIFECYCLE_STATUS_VOIDED,
    TRAINING_KIND_COURSE,
)
from app.ppr.domain.errors import (
    SectionOptimisticConcurrencyConflictError,
    SectionRecordNotFoundError,
    UnknownSectionTypeError,
)
from app.ppr.domain.section_models import (
    SECTION_CODE_PPR_EDUCATION,
    SECTION_CODE_PPR_TRAINING,
    SECTION_OPTIMISTIC_TOKEN_FIELD,
    EducationRecord,
    TrainingRecord,
)
from app.ppr.domain.section_repositories import SectionMutationRepository, SectionReadRepository
from app.ppr.infrastructure.section_repository import (
    SqlAlchemySectionMutationRepository,
    SqlAlchemySectionReadRepository,
)
from tests.conftest import table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_person, ppr_db_available, require_ppr_schema


def _require_section_schema() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "person_education"):
            pytest.skip("person_education missing — run: alembic upgrade head")


@pytest.fixture
def section_person_id():
    require_ppr_schema()
    _require_section_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"PPR Section Person {suffix}")
    yield person_id
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])


@pytest.fixture
def section_repos(section_person_id: int):
    del section_person_id
    with engine.begin() as conn:
        yield (
            SqlAlchemySectionReadRepository(conn),
            SqlAlchemySectionMutationRepository(conn),
        )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_insert_and_load_education_record(section_repos, section_person_id: int) -> None:
    read_repo, mutation_repo = section_repos
    inserted = mutation_repo.insert_record(
        EducationRecord(
            person_id=section_person_id,
            education_kind=EDUCATION_KIND_BASIC,
            institution_name="Test University",
        )
    )
    loaded = read_repo.load_record(
        section_person_id,
        SECTION_CODE_PPR_EDUCATION,
        inserted.record_id or 0,
    )

    assert inserted.record_id is not None
    assert loaded is not None
    assert isinstance(loaded, EducationRecord)
    assert loaded.person_id == section_person_id
    assert loaded.institution_name == "Test University"
    assert loaded.lifecycle_status == LIFECYCLE_STATUS_ACTIVE
    assert not hasattr(loaded, "_sa_instance_state")


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_load_active_records(section_repos, section_person_id: int) -> None:
    read_repo, mutation_repo = section_repos
    mutation_repo.insert_record(
        EducationRecord(
            person_id=section_person_id,
            education_kind=EDUCATION_KIND_BASIC,
            institution_name="Alpha University",
        )
    )
    mutation_repo.insert_record(
        TrainingRecord(
            person_id=section_person_id,
            training_kind=TRAINING_KIND_COURSE,
            title="Safety Course",
        )
    )
    education_rows = read_repo.load_active_records(section_person_id, SECTION_CODE_PPR_EDUCATION)
    training_rows = read_repo.load_active_records(section_person_id, SECTION_CODE_PPR_TRAINING)

    assert len(education_rows) == 1
    assert len(training_rows) == 1


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_update_education_with_expected_updated_at(section_repos, section_person_id: int) -> None:
    read_repo, mutation_repo = section_repos
    inserted = mutation_repo.insert_record(
        EducationRecord(
            person_id=section_person_id,
            education_kind=EDUCATION_KIND_BASIC,
            institution_name="Before Update",
        )
    )
    assert inserted.updated_at is not None
    updated = mutation_repo.update_record(
        EducationRecord(
            record_id=inserted.record_id,
            person_id=section_person_id,
            education_kind=EDUCATION_KIND_BASIC,
            institution_name="After Update",
            updated_at=inserted.updated_at,
        ),
        expected_updated_at=inserted.updated_at,
    )

    assert updated.institution_name == "After Update"
    assert SECTION_OPTIMISTIC_TOKEN_FIELD == "updated_at"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_stale_update_raises_concurrency_conflict(section_repos, section_person_id: int) -> None:
    _, mutation_repo = section_repos
    inserted = mutation_repo.insert_record(
        EducationRecord(
            person_id=section_person_id,
            education_kind=EDUCATION_KIND_BASIC,
            institution_name="Stale Test",
        )
    )
    assert inserted.updated_at is not None
    with pytest.raises(SectionOptimisticConcurrencyConflictError):
        mutation_repo.update_record(
            EducationRecord(
                record_id=inserted.record_id,
                person_id=section_person_id,
                education_kind=EDUCATION_KIND_BASIC,
                institution_name="Should Fail",
            ),
            expected_updated_at=inserted.updated_at.replace(year=2000),
        )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_void_education_record(section_repos, section_person_id: int) -> None:
    read_repo, mutation_repo = section_repos
    inserted = mutation_repo.insert_record(
        EducationRecord(
            person_id=section_person_id,
            education_kind=EDUCATION_KIND_BASIC,
            institution_name="Void Me",
        )
    )
    voided = mutation_repo.void_record(
        section_person_id,
        SECTION_CODE_PPR_EDUCATION,
        inserted.record_id or 0,
    )
    active = read_repo.load_active_records(section_person_id, SECTION_CODE_PPR_EDUCATION)

    assert voided.lifecycle_status == LIFECYCLE_STATUS_VOIDED
    assert len(active) == 0


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_supersede_pair(section_repos, section_person_id: int) -> None:
    read_repo, mutation_repo = section_repos
    old = mutation_repo.insert_record(
        EducationRecord(
            person_id=section_person_id,
            education_kind=EDUCATION_KIND_BASIC,
            institution_name="Old School",
        )
    )
    old_record, new_record = mutation_repo.supersede_pair(
        section_person_id,
        SECTION_CODE_PPR_EDUCATION,
        old.record_id or 0,
        EducationRecord(
            person_id=section_person_id,
            education_kind=EDUCATION_KIND_BASIC,
            institution_name="New School",
        ),
    )
    active = read_repo.load_active_records(section_person_id, SECTION_CODE_PPR_EDUCATION)

    assert old_record.lifecycle_status == LIFECYCLE_STATUS_SUPERSEDED
    assert new_record.lifecycle_status == LIFECYCLE_STATUS_ACTIVE
    assert len(active) == 1
    assert active[0].record_id == new_record.record_id


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_load_missing_returns_none(section_repos, section_person_id: int) -> None:
    read_repo, _ = section_repos
    assert read_repo.load_record(section_person_id, SECTION_CODE_PPR_EDUCATION, 9_999_999) is None


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_void_missing_raises_not_found(section_repos, section_person_id: int) -> None:
    _, mutation_repo = section_repos
    with pytest.raises(SectionRecordNotFoundError):
        mutation_repo.void_record(section_person_id, SECTION_CODE_PPR_EDUCATION, 9_999_999)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_unknown_section_code_raises(section_repos, section_person_id: int) -> None:
    read_repo, _ = section_repos
    with pytest.raises(UnknownSectionTypeError):
        read_repo.load_active_records(section_person_id, "PPR-UNKNOWN")


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_read_repository_has_no_mutation_methods() -> None:
    assert not hasattr(SqlAlchemySectionReadRepository, "insert_record")
    assert not hasattr(SqlAlchemySectionReadRepository, "void_record")


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_mutation_repository_has_no_commit_method() -> None:
    assert not hasattr(SqlAlchemySectionMutationRepository, "commit")
    assert not hasattr(SqlAlchemySectionMutationRepository, "rollback")


def test_protocol_surfaces() -> None:
    assert hasattr(SectionReadRepository, "load_active_records")
    assert hasattr(SectionReadRepository, "load_record")
    assert hasattr(SectionMutationRepository, "insert_record")
    assert hasattr(SectionMutationRepository, "void_record")
    assert hasattr(SectionMutationRepository, "supersede_pair")


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_supersede_rollback_restores_old_record_on_insert_failure(section_person_id: int) -> None:
    with engine.begin() as conn:
        mutation_repo = SqlAlchemySectionMutationRepository(conn)
        old = mutation_repo.insert_record(
            EducationRecord(
                person_id=section_person_id,
                education_kind=EDUCATION_KIND_BASIC,
                institution_name="Rollback Supersede Old",
            )
        )
        old_id = old.record_id or 0

    with engine.connect() as conn:
        trans = conn.begin()
        mutation_repo = SqlAlchemySectionMutationRepository(conn)
        with pytest.raises(DBAPIError):
            mutation_repo.supersede_pair(
                section_person_id,
                SECTION_CODE_PPR_EDUCATION,
                old_id,
                EducationRecord(
                    person_id=section_person_id,
                    education_kind="not-a-valid-education-kind",
                    institution_name="Invalid Replacement",
                ),
            )
        trans.rollback()

    with engine.begin() as conn:
        read_repo = SqlAlchemySectionReadRepository(conn)
        loaded = read_repo.load_record(section_person_id, SECTION_CODE_PPR_EDUCATION, old_id)
        active = read_repo.load_active_records(section_person_id, SECTION_CODE_PPR_EDUCATION)

    assert loaded is not None
    assert loaded.lifecycle_status == LIFECYCLE_STATUS_ACTIVE
    assert len(active) == 1
    assert active[0].record_id == old_id
