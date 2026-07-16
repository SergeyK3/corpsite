# tests/ppr/test_section_repository_contract.py
"""Contract tests for section read/mutation repositories (PPR R4)."""
from __future__ import annotations

from uuid import uuid4

from datetime import UTC, datetime, date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.db.engine import engine
from app.db.models.personnel_migration import (
    EDUCATION_KIND_BASIC,
    EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
    EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY,
    LIFECYCLE_STATUS_ACTIVE,
    LIFECYCLE_STATUS_SUPERSEDED,
    LIFECYCLE_STATUS_VOIDED,
    MILITARY_RECORD_KIND_NOT_APPLICABLE,
    MILITARY_RECORD_KIND_REGISTRATION,
    RELATIONSHIP_TYPE_MOTHER,
    SECTION_SOURCE_TYPE_ENTERED,
    TRAINING_KIND_COURSE,
)
from app.ppr.domain.errors import (
    SectionOptimisticConcurrencyConflictError,
    SectionRecordNotFoundError,
    UnknownSectionTypeError,
)
from app.ppr.domain.section_models import (
    SECTION_CODE_PPR_EDUCATION,
    SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY,
    SECTION_CODE_PPR_FAMILY,
    SECTION_CODE_PPR_MILITARY,
    SECTION_CODE_PPR_TRAINING,
    SECTION_OPTIMISTIC_TOKEN_FIELD,
    SUPPORTED_SECTION_CODES,
    EducationRecord,
    ExternalEmploymentRecord,
    MilitaryServiceRecord,
    RelativeRecord,
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
        if not table_exists(conn, "person_relatives"):
            pytest.skip("person_relatives missing — run: alembic upgrade head")
        if not table_exists(conn, "person_external_employment"):
            pytest.skip("person_external_employment missing — run: alembic upgrade head")
        if not table_exists(conn, "person_military_service"):
            pytest.skip("person_military_service missing — run: alembic upgrade head")


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
    assert inserted.updated_at is not None
    voided = mutation_repo.void_record(
        section_person_id,
        SECTION_CODE_PPR_EDUCATION,
        inserted.record_id or 0,
        expected_updated_at=inserted.updated_at,
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
        expected_updated_at=old.updated_at,
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
        mutation_repo.void_record(
            section_person_id,
            SECTION_CODE_PPR_EDUCATION,
            9_999_999,
            expected_updated_at=datetime(2000, 1, 1, tzinfo=UTC),
        )


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
                expected_updated_at=old.updated_at,
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


def test_supported_section_codes_include_family() -> None:
    assert SECTION_CODE_PPR_FAMILY in SUPPORTED_SECTION_CODES


def test_supported_section_codes_include_employment_biography() -> None:
    assert SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY in SUPPORTED_SECTION_CODES


def test_supported_section_codes_include_military() -> None:
    assert SECTION_CODE_PPR_MILITARY in SUPPORTED_SECTION_CODES


def _registration_record(person_id: int, **overrides) -> MilitaryServiceRecord:
    base = {
        "person_id": person_id,
        "record_kind": MILITARY_RECORD_KIND_REGISTRATION,
        "obligation_status": "liable",
        "registration_category": "II",
        "military_rank": "рядовой",
        "registration_status": "registered",
        "source_type": SECTION_SOURCE_TYPE_ENTERED,
    }
    base.update(overrides)
    return MilitaryServiceRecord(**base)


def _full_registration_record(person_id: int, **overrides) -> MilitaryServiceRecord:
    base = {
        "person_id": person_id,
        "record_kind": MILITARY_RECORD_KIND_REGISTRATION,
        "obligation_status": "liable",
        "registration_category": "II",
        "military_rank": "рядовой",
        "military_specialty_code": "123456",
        "personnel_composition": "soldiers",
        "fitness_category": "A",
        "registration_status": "registered",
        "commissariat_name": "Военкомат №1",
        "registered_at": date(2015, 3, 1),
        "deregistered_at": date(2017, 6, 30),
        "military_id_book_series": "АА",
        "military_id_book_number": "1234567",
        "registration_certificate_series": "ББ",
        "registration_certificate_number": "987654",
        "notes": "Round-trip notes",
        "source_type": SECTION_SOURCE_TYPE_ENTERED,
        "provenance": {"import_batch": "test-batch"},
        "employee_context_id": 42,
        "metadata": {"restricted_flag": True},
    }
    base.update(overrides)
    return MilitaryServiceRecord(**base)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_insert_and_load_military_registration_record(section_repos, section_person_id: int) -> None:
    read_repo, mutation_repo = section_repos
    inserted = mutation_repo.insert_record(
        _registration_record(
            section_person_id,
            military_rank="лейтенант",
            commissariat_name="Военкомат города",
        )
    )
    loaded = read_repo.load_record(
        section_person_id,
        SECTION_CODE_PPR_MILITARY,
        inserted.record_id or 0,
    )

    assert inserted.record_id is not None
    assert loaded is not None
    assert isinstance(loaded, MilitaryServiceRecord)
    assert loaded.person_id == section_person_id
    assert loaded.record_kind == MILITARY_RECORD_KIND_REGISTRATION
    assert loaded.military_rank == "лейтенант"
    assert loaded.commissariat_name == "Военкомат города"
    assert loaded.lifecycle_status == LIFECYCLE_STATUS_ACTIVE
    assert not hasattr(loaded, "_sa_instance_state")


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_insert_and_load_military_not_applicable_record(section_repos, section_person_id: int) -> None:
    read_repo, mutation_repo = section_repos
    inserted = mutation_repo.insert_record(
        MilitaryServiceRecord(
            person_id=section_person_id,
            record_kind=MILITARY_RECORD_KIND_NOT_APPLICABLE,
            notes="Не подлежит воинскому учёту",
            source_type=SECTION_SOURCE_TYPE_ENTERED,
        )
    )
    loaded = read_repo.load_record(
        section_person_id,
        SECTION_CODE_PPR_MILITARY,
        inserted.record_id or 0,
    )

    assert inserted.record_id is not None
    assert loaded is not None
    assert isinstance(loaded, MilitaryServiceRecord)
    assert loaded.record_kind == MILITARY_RECORD_KIND_NOT_APPLICABLE
    assert loaded.notes == "Не подлежит воинскому учёту"
    assert loaded.obligation_status is None
    assert loaded.military_rank is None
    assert loaded.lifecycle_status == LIFECYCLE_STATUS_ACTIVE


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_military_load_active_records(section_repos, section_person_id: int) -> None:
    read_repo, mutation_repo = section_repos
    inserted = mutation_repo.insert_record(_registration_record(section_person_id))
    active_rows = read_repo.load_active_records(section_person_id, SECTION_CODE_PPR_MILITARY)

    assert len(active_rows) == 1
    assert active_rows[0].record_id == inserted.record_id
    assert active_rows[0].lifecycle_status == LIFECYCLE_STATUS_ACTIVE


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_military_lifecycle_buckets(section_repos, section_person_id: int) -> None:
    read_repo, mutation_repo = section_repos
    first = mutation_repo.insert_record(
        _registration_record(section_person_id, military_rank="первый")
    )
    assert first.updated_at is not None
    old_record, replacement = mutation_repo.supersede_pair(
        section_person_id,
        SECTION_CODE_PPR_MILITARY,
        first.record_id or 0,
        _registration_record(section_person_id, military_rank="второй"),
        expected_updated_at=first.updated_at,
    )
    assert replacement.updated_at is not None
    voided = mutation_repo.void_record(
        section_person_id,
        SECTION_CODE_PPR_MILITARY,
        replacement.record_id or 0,
        expected_updated_at=replacement.updated_at,
    )
    current = mutation_repo.insert_record(
        _registration_record(section_person_id, military_rank="третий")
    )

    active_rows = read_repo.load_active_records(section_person_id, SECTION_CODE_PPR_MILITARY)
    loaded_superseded = read_repo.load_record(
        section_person_id,
        SECTION_CODE_PPR_MILITARY,
        first.record_id or 0,
    )
    loaded_voided = read_repo.load_record(
        section_person_id,
        SECTION_CODE_PPR_MILITARY,
        replacement.record_id or 0,
    )

    assert old_record.lifecycle_status == LIFECYCLE_STATUS_SUPERSEDED
    assert voided.lifecycle_status == LIFECYCLE_STATUS_VOIDED
    assert current.lifecycle_status == LIFECYCLE_STATUS_ACTIVE
    assert len(active_rows) == 1
    assert active_rows[0].record_id == current.record_id
    assert loaded_superseded is not None
    assert loaded_superseded.lifecycle_status == LIFECYCLE_STATUS_SUPERSEDED
    assert loaded_voided is not None
    assert loaded_voided.lifecycle_status == LIFECYCLE_STATUS_VOIDED


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_military_supersede_pair(section_repos, section_person_id: int) -> None:
    read_repo, mutation_repo = section_repos
    old = mutation_repo.insert_record(
        _registration_record(section_person_id, military_rank="до замены")
    )
    old_record, new_record = mutation_repo.supersede_pair(
        section_person_id,
        SECTION_CODE_PPR_MILITARY,
        old.record_id or 0,
        _registration_record(section_person_id, military_rank="после замены"),
        expected_updated_at=old.updated_at,
    )
    active = read_repo.load_active_records(section_person_id, SECTION_CODE_PPR_MILITARY)

    assert old_record.lifecycle_status == LIFECYCLE_STATUS_SUPERSEDED
    assert new_record.lifecycle_status == LIFECYCLE_STATUS_ACTIVE
    assert new_record.military_rank == "после замены"
    assert len(active) == 1
    assert active[0].record_id == new_record.record_id


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_military_void_record(section_repos, section_person_id: int) -> None:
    read_repo, mutation_repo = section_repos
    inserted = mutation_repo.insert_record(_registration_record(section_person_id))
    assert inserted.updated_at is not None
    voided = mutation_repo.void_record(
        section_person_id,
        SECTION_CODE_PPR_MILITARY,
        inserted.record_id or 0,
        expected_updated_at=inserted.updated_at,
    )
    active = read_repo.load_active_records(section_person_id, SECTION_CODE_PPR_MILITARY)

    assert voided.lifecycle_status == LIFECYCLE_STATUS_VOIDED
    assert len(active) == 0


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_military_load_wrong_person_id_returns_none(section_repos, section_person_id: int) -> None:
    read_repo, mutation_repo = section_repos
    inserted = mutation_repo.insert_record(_registration_record(section_person_id))
    wrong_person_id = section_person_id + 99_999
    loaded = read_repo.load_record(
        wrong_person_id,
        SECTION_CODE_PPR_MILITARY,
        inserted.record_id or 0,
    )

    assert loaded is None


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_military_stale_void_raises_concurrency_conflict(section_repos, section_person_id: int) -> None:
    _, mutation_repo = section_repos
    inserted = mutation_repo.insert_record(_registration_record(section_person_id))
    assert inserted.updated_at is not None
    with pytest.raises(SectionOptimisticConcurrencyConflictError):
        mutation_repo.void_record(
            section_person_id,
            SECTION_CODE_PPR_MILITARY,
            inserted.record_id or 0,
            expected_updated_at=inserted.updated_at.replace(year=2000),
        )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_military_stale_supersede_raises_concurrency_conflict(section_repos, section_person_id: int) -> None:
    _, mutation_repo = section_repos
    inserted = mutation_repo.insert_record(_registration_record(section_person_id))
    assert inserted.updated_at is not None
    with pytest.raises(SectionOptimisticConcurrencyConflictError):
        mutation_repo.supersede_pair(
            section_person_id,
            SECTION_CODE_PPR_MILITARY,
            inserted.record_id or 0,
            _registration_record(section_person_id, military_rank="replacement"),
            expected_updated_at=inserted.updated_at.replace(year=2000),
        )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_military_second_active_insert_raises(section_repos, section_person_id: int) -> None:
    _, mutation_repo = section_repos
    mutation_repo.insert_record(_registration_record(section_person_id))
    with pytest.raises(IntegrityError) as exc_info:
        mutation_repo.insert_record(
            _registration_record(section_person_id, military_rank="conflict")
        )
    orig = getattr(exc_info.value, "orig", None)
    assert getattr(orig, "pgcode", None) == "23505"
    diag = getattr(orig, "diag", None)
    constraint_name = getattr(diag, "constraint_name", None) if diag is not None else None
    if constraint_name is not None:
        assert constraint_name == "uq_person_military_service_one_active_per_person"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_military_round_trip_all_fields(section_repos, section_person_id: int) -> None:
    read_repo, mutation_repo = section_repos
    source = _full_registration_record(section_person_id)
    inserted = mutation_repo.insert_record(source)
    loaded = read_repo.load_record(
        section_person_id,
        SECTION_CODE_PPR_MILITARY,
        inserted.record_id or 0,
    )

    assert loaded is not None
    assert isinstance(loaded, MilitaryServiceRecord)
    assert loaded.record_kind == source.record_kind
    assert loaded.obligation_status == source.obligation_status
    assert loaded.registration_category == source.registration_category
    assert loaded.military_rank == source.military_rank
    assert loaded.military_specialty_code == source.military_specialty_code
    assert loaded.personnel_composition == source.personnel_composition
    assert loaded.fitness_category == source.fitness_category
    assert loaded.registration_status == source.registration_status
    assert loaded.commissariat_name == source.commissariat_name
    assert loaded.registered_at == source.registered_at
    assert loaded.deregistered_at == source.deregistered_at
    assert loaded.military_id_book_series == source.military_id_book_series
    assert loaded.military_id_book_number == source.military_id_book_number
    assert loaded.registration_certificate_series == source.registration_certificate_series
    assert loaded.registration_certificate_number == source.registration_certificate_number
    assert loaded.notes == source.notes
    assert loaded.source_type == source.source_type
    assert loaded.provenance == source.provenance
    assert loaded.employee_context_id == source.employee_context_id
    assert loaded.metadata == source.metadata
    assert loaded.lifecycle_status == LIFECYCLE_STATUS_ACTIVE


def _episode_record(person_id: int, **overrides) -> ExternalEmploymentRecord:
    base = {
        "person_id": person_id,
        "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
        "employer_name": "Employer",
        "position_title": "Role",
        "started_at": date(2020, 1, 1),
    }
    base.update(overrides)
    return ExternalEmploymentRecord(**base)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_insert_and_load_relative_record(section_repos, section_person_id: int) -> None:
    read_repo, mutation_repo = section_repos
    inserted = mutation_repo.insert_record(
        RelativeRecord(
            person_id=section_person_id,
            relationship_type=RELATIONSHIP_TYPE_MOTHER,
            full_name="Петрова Мария Сергеевна",
        )
    )
    loaded = read_repo.load_record(
        section_person_id,
        SECTION_CODE_PPR_FAMILY,
        inserted.record_id or 0,
    )

    assert inserted.record_id is not None
    assert loaded is not None
    assert isinstance(loaded, RelativeRecord)
    assert loaded.person_id == section_person_id
    assert loaded.full_name == "Петрова Мария Сергеевна"
    assert loaded.lifecycle_status == LIFECYCLE_STATUS_ACTIVE
    assert not hasattr(loaded, "_sa_instance_state")


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_relative_lifecycle_buckets(section_repos, section_person_id: int) -> None:
    read_repo, mutation_repo = section_repos
    active_row = mutation_repo.insert_record(
        RelativeRecord(
            person_id=section_person_id,
            relationship_type=RELATIONSHIP_TYPE_MOTHER,
            full_name="Active Relative",
        )
    )
    void_candidate = mutation_repo.insert_record(
        RelativeRecord(
            person_id=section_person_id,
            relationship_type=RELATIONSHIP_TYPE_MOTHER,
            full_name="Void Relative",
        )
    )
    supersede_candidate = mutation_repo.insert_record(
        RelativeRecord(
            person_id=section_person_id,
            relationship_type=RELATIONSHIP_TYPE_MOTHER,
            full_name="Supersede Relative",
        )
    )

    assert void_candidate.updated_at is not None
    voided = mutation_repo.void_record(
        section_person_id,
        SECTION_CODE_PPR_FAMILY,
        void_candidate.record_id or 0,
        expected_updated_at=void_candidate.updated_at,
    )
    assert supersede_candidate.updated_at is not None
    old_record, new_record = mutation_repo.supersede_pair(
        section_person_id,
        SECTION_CODE_PPR_FAMILY,
        supersede_candidate.record_id or 0,
        RelativeRecord(
            person_id=section_person_id,
            relationship_type=RELATIONSHIP_TYPE_MOTHER,
            full_name="Supersede Replacement",
        ),
        expected_updated_at=supersede_candidate.updated_at,
    )

    active_rows = read_repo.load_active_records(section_person_id, SECTION_CODE_PPR_FAMILY)
    loaded_voided = read_repo.load_record(
        section_person_id,
        SECTION_CODE_PPR_FAMILY,
        void_candidate.record_id or 0,
    )
    loaded_superseded = read_repo.load_record(
        section_person_id,
        SECTION_CODE_PPR_FAMILY,
        supersede_candidate.record_id or 0,
    )

    assert voided.lifecycle_status == LIFECYCLE_STATUS_VOIDED
    assert old_record.lifecycle_status == LIFECYCLE_STATUS_SUPERSEDED
    assert new_record.lifecycle_status == LIFECYCLE_STATUS_ACTIVE
    assert len(active_rows) == 2
    active_ids = {row.record_id for row in active_rows}
    assert active_row.record_id in active_ids
    assert new_record.record_id in active_ids
    assert void_candidate.record_id not in active_ids
    assert supersede_candidate.record_id not in active_ids
    assert loaded_voided is not None
    assert loaded_voided.lifecycle_status == LIFECYCLE_STATUS_VOIDED
    assert loaded_superseded is not None
    assert loaded_superseded.lifecycle_status == LIFECYCLE_STATUS_SUPERSEDED


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_relative_update_with_expected_updated_at(section_repos, section_person_id: int) -> None:
    _, mutation_repo = section_repos
    inserted = mutation_repo.insert_record(
        RelativeRecord(
            person_id=section_person_id,
            relationship_type=RELATIONSHIP_TYPE_MOTHER,
            full_name="Before Update",
        )
    )
    assert inserted.updated_at is not None
    updated = mutation_repo.update_record(
        RelativeRecord(
            record_id=inserted.record_id,
            person_id=section_person_id,
            relationship_type=RELATIONSHIP_TYPE_MOTHER,
            full_name="After Update",
            updated_at=inserted.updated_at,
        ),
        expected_updated_at=inserted.updated_at,
    )

    assert updated.full_name == "After Update"
    assert SECTION_OPTIMISTIC_TOKEN_FIELD == "updated_at"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_relative_stale_update_raises_concurrency_conflict(section_repos, section_person_id: int) -> None:
    _, mutation_repo = section_repos
    inserted = mutation_repo.insert_record(
        RelativeRecord(
            person_id=section_person_id,
            relationship_type=RELATIONSHIP_TYPE_MOTHER,
            full_name="Stale Test",
        )
    )
    assert inserted.updated_at is not None
    with pytest.raises(SectionOptimisticConcurrencyConflictError):
        mutation_repo.update_record(
            RelativeRecord(
                record_id=inserted.record_id,
                person_id=section_person_id,
                relationship_type=RELATIONSHIP_TYPE_MOTHER,
                full_name="Should Fail",
            ),
            expected_updated_at=inserted.updated_at.replace(year=2000),
        )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_relative_load_wrong_person_id_returns_none(section_repos, section_person_id: int) -> None:
    read_repo, mutation_repo = section_repos
    inserted = mutation_repo.insert_record(
        RelativeRecord(
            person_id=section_person_id,
            relationship_type=RELATIONSHIP_TYPE_MOTHER,
            full_name="Ownership Test",
        )
    )
    wrong_person_id = section_person_id + 99_999
    loaded = read_repo.load_record(
        wrong_person_id,
        SECTION_CODE_PPR_FAMILY,
        inserted.record_id or 0,
    )

    assert loaded is None


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_mutation_repository_has_no_delete_method() -> None:
    assert not hasattr(SqlAlchemySectionMutationRepository, "delete_record")
    assert not hasattr(SqlAlchemySectionMutationRepository, "delete")


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_insert_and_load_external_employment_record(section_repos, section_person_id: int) -> None:
    read_repo, mutation_repo = section_repos
    inserted = mutation_repo.insert_record(
        _episode_record(
            section_person_id,
            employer_name="ТОО «Внешний работодатель»",
            position_title="Бухгалтер",
        )
    )
    loaded = read_repo.load_record(
        section_person_id,
        SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY,
        inserted.record_id or 0,
    )

    assert inserted.record_id is not None
    assert loaded is not None
    assert isinstance(loaded, ExternalEmploymentRecord)
    assert loaded.person_id == section_person_id
    assert loaded.employer_name == "ТОО «Внешний работодатель»"
    assert loaded.lifecycle_status == LIFECYCLE_STATUS_ACTIVE
    assert not hasattr(loaded, "_sa_instance_state")


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_external_employment_lifecycle_buckets(section_repos, section_person_id: int) -> None:
    read_repo, mutation_repo = section_repos
    active_row = mutation_repo.insert_record(
        _episode_record(section_person_id, employer_name="Active Employer", position_title="Engineer")
    )
    void_candidate = mutation_repo.insert_record(
        _episode_record(section_person_id, employer_name="Void Employer", position_title="Clerk")
    )
    supersede_candidate = mutation_repo.insert_record(
        _episode_record(section_person_id, employer_name="Supersede Employer", position_title="Manager")
    )

    assert void_candidate.updated_at is not None
    voided = mutation_repo.void_record(
        section_person_id,
        SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY,
        void_candidate.record_id or 0,
        expected_updated_at=void_candidate.updated_at,
    )
    assert supersede_candidate.updated_at is not None
    old_record, new_record = mutation_repo.supersede_pair(
        section_person_id,
        SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY,
        supersede_candidate.record_id or 0,
        ExternalEmploymentRecord(
            person_id=section_person_id,
            record_kind=EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
            employer_name="Replacement Employer",
            position_title="Lead",
            started_at=date(2021, 1, 1),
        ),
        expected_updated_at=supersede_candidate.updated_at,
    )

    active_rows = read_repo.load_active_records(
        section_person_id,
        SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY,
    )
    loaded_voided = read_repo.load_record(
        section_person_id,
        SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY,
        void_candidate.record_id or 0,
    )
    loaded_superseded = read_repo.load_record(
        section_person_id,
        SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY,
        supersede_candidate.record_id or 0,
    )

    assert voided.lifecycle_status == LIFECYCLE_STATUS_VOIDED
    assert old_record.lifecycle_status == LIFECYCLE_STATUS_SUPERSEDED
    assert new_record.lifecycle_status == LIFECYCLE_STATUS_ACTIVE
    assert len(active_rows) == 2
    active_ids = {row.record_id for row in active_rows}
    assert active_row.record_id in active_ids
    assert new_record.record_id in active_ids
    assert void_candidate.record_id not in active_ids
    assert supersede_candidate.record_id not in active_ids
    assert loaded_voided is not None
    assert loaded_voided.lifecycle_status == LIFECYCLE_STATUS_VOIDED
    assert loaded_superseded is not None
    assert loaded_superseded.lifecycle_status == LIFECYCLE_STATUS_SUPERSEDED


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_external_employment_update_with_expected_updated_at(section_repos, section_person_id: int) -> None:
    _, mutation_repo = section_repos
    inserted = mutation_repo.insert_record(
        _episode_record(section_person_id, employer_name="Before Update", position_title="Role A")
    )
    assert inserted.updated_at is not None
    updated = mutation_repo.update_record(
        ExternalEmploymentRecord(
            record_id=inserted.record_id,
            person_id=section_person_id,
            record_kind=EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
            employer_name="After Update",
            position_title="Role B",
            started_at=date(2020, 1, 1),
            updated_at=inserted.updated_at,
        ),
        expected_updated_at=inserted.updated_at,
    )

    assert updated.employer_name == "After Update"
    assert SECTION_OPTIMISTIC_TOKEN_FIELD == "updated_at"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_external_employment_stale_update_raises_concurrency_conflict(
    section_repos,
    section_person_id: int,
) -> None:
    _, mutation_repo = section_repos
    inserted = mutation_repo.insert_record(
        _episode_record(section_person_id, employer_name="Stale Test", position_title="Role")
    )
    assert inserted.updated_at is not None
    with pytest.raises(SectionOptimisticConcurrencyConflictError):
        mutation_repo.update_record(
            ExternalEmploymentRecord(
                record_id=inserted.record_id,
                person_id=section_person_id,
                record_kind=EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
                employer_name="Should Fail",
                position_title="Role",
                started_at=date(2020, 1, 1),
            ),
            expected_updated_at=inserted.updated_at.replace(year=2000),
        )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_external_employment_active_order_by_started_at_desc(section_repos, section_person_id: int) -> None:
    read_repo, mutation_repo = section_repos
    oldest = mutation_repo.insert_record(
        _episode_record(section_person_id, employer_name="Oldest", started_at=date(2010, 1, 1))
    )
    newest = mutation_repo.insert_record(
        _episode_record(section_person_id, employer_name="Newest", started_at=date(2022, 6, 1))
    )
    middle = mutation_repo.insert_record(
        _episode_record(section_person_id, employer_name="Middle", started_at=date(2018, 3, 15))
    )

    active_rows = read_repo.load_active_records(section_person_id, SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY)
    assert [row.record_id for row in active_rows] == [
        newest.record_id,
        middle.record_id,
        oldest.record_id,
    ]


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_external_employment_active_order_null_started_at_last(section_repos, section_person_id: int) -> None:
    read_repo, mutation_repo = section_repos
    dated = mutation_repo.insert_record(
        _episode_record(section_person_id, employer_name="Dated", started_at=date(2018, 1, 1))
    )
    null_started = mutation_repo.insert_record(
        ExternalEmploymentRecord(
            person_id=section_person_id,
            record_kind=EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY,
            notes="No episode dates",
        )
    )

    active_rows = read_repo.load_active_records(section_person_id, SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY)
    assert active_rows[0].record_id == dated.record_id
    assert active_rows[-1].record_id == null_started.record_id
    assert active_rows[-1].started_at is None


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_external_employment_active_order_tie_breakers(section_repos, section_person_id: int) -> None:
    read_repo, mutation_repo = section_repos
    later_end = mutation_repo.insert_record(
        _episode_record(
            section_person_id,
            employer_name="Later end",
            started_at=date(2020, 1, 1),
            ended_at=date(2022, 12, 31),
        )
    )
    earlier_end = mutation_repo.insert_record(
        _episode_record(
            section_person_id,
            employer_name="Earlier end",
            started_at=date(2020, 1, 1),
            ended_at=date(2021, 6, 30),
        )
    )
    first_tie = mutation_repo.insert_record(
        _episode_record(
            section_person_id,
            employer_name="First tie",
            started_at=date(2020, 1, 1),
            ended_at=date(2021, 6, 30),
        )
    )
    second_tie = mutation_repo.insert_record(
        _episode_record(
            section_person_id,
            employer_name="Second tie",
            started_at=date(2020, 1, 1),
            ended_at=date(2021, 6, 30),
        )
    )

    active_rows = read_repo.load_active_records(section_person_id, SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY)
    assert [row.record_id for row in active_rows] == [
        later_end.record_id,
        second_tie.record_id,
        first_tie.record_id,
        earlier_end.record_id,
    ]


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_external_employment_load_wrong_person_id_returns_none(
    section_repos,
    section_person_id: int,
) -> None:
    read_repo, mutation_repo = section_repos
    inserted = mutation_repo.insert_record(
        _episode_record(section_person_id, employer_name="Ownership Test", position_title="Role")
    )
    wrong_person_id = section_person_id + 99_999
    loaded = read_repo.load_record(
        wrong_person_id,
        SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY,
        inserted.record_id or 0,
    )

    assert loaded is None
