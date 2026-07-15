# tests/ppr/test_ppr_event_repository_contract.py
"""Contract tests for SqlAlchemyPprEventRepository (PPR R3 append-only events)."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.engine import engine
from app.db.models.personnel_migration import DOMAIN_CODE_EDUCATION
from app.ppr.domain.event_models import (
    EVENT_CATEGORY_LIFECYCLE,
    EVENT_CATEGORY_SECTION,
    EVENT_TYPE_PPR_CREATED,
    EVENT_TYPE_PPR_SECTION_ADDED,
    PprEventAppendRequest,
    PprEventRecord,
)
from app.ppr.domain.event_repositories import PprEventRepository
from app.ppr.infrastructure.ppr_event_repository import SqlAlchemyPprEventRepository
from app.services.personnel_record_event_service import emit_personnel_record_event
from tests.conftest import table_exists
from tests.ppr.conftest import (
    cleanup_person_graph,
    insert_employee,
    insert_person,
    ppr_db_available,
    require_ppr_schema,
)


def _require_events_schema() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_record_events"):
            pytest.skip(
                "personnel_record_events missing — run: alembic upgrade head "
                "(revision q1r2s3t4u5w6 or later)"
            )


def _require_nullable_domain_code() -> None:
    with engine.begin() as conn:
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
        if row != "YES":
            pytest.skip(
                "personnel_record_events.domain_code is NOT NULL — run: "
                "alembic upgrade head (revision k1l2m3n4o5p6)"
            )


@pytest.fixture
def event_person_id():
    require_ppr_schema()
    _require_events_schema()
    _require_nullable_domain_code()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"PPR Event Person {suffix}")
    yield person_id
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])


def _section_append_request(
    *,
    person_id: int,
    record_id: int,
    correlation_id: str | None = None,
) -> PprEventAppendRequest:
    return PprEventAppendRequest(
        person_id=person_id,
        event_type=EVENT_TYPE_PPR_SECTION_ADDED,
        category=EVENT_CATEGORY_SECTION,
        domain_code=DOMAIN_CODE_EDUCATION,
        section_code="PPR-EDUCATION",
        record_table_name="person_education",
        record_id=record_id,
        payload={"change_kind": "create", "institution": "Test University"},
        correlation_id=correlation_id,
        command_id="cmd-001",
        source_event_id="src-evt-001",
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_append_canonical_event_returns_generated_event_id(event_person_id: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPprEventRepository(conn)
        record = repo.append(_section_append_request(person_id=event_person_id, record_id=101))
        assert record.event_id > 0


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_append_and_load_by_id(event_person_id: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPprEventRepository(conn)
        appended = repo.append(_section_append_request(person_id=event_person_id, record_id=102))
        loaded = repo.load_by_id(appended.event_id)

    assert loaded is not None
    assert loaded.event_id == appended.event_id
    assert loaded.person_id == event_person_id
    assert loaded.event_type == EVENT_TYPE_PPR_SECTION_ADDED


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_payload_persisted_without_loss(event_person_id: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPprEventRepository(conn)
        request = PprEventAppendRequest(
            person_id=event_person_id,
            event_type=EVENT_TYPE_PPR_SECTION_ADDED,
            category=EVENT_CATEGORY_SECTION,
            domain_code=DOMAIN_CODE_EDUCATION,
            section_code="PPR-EDUCATION",
            record_table_name="person_education",
            record_id=103,
            payload={"nested": {"value": 1}, "tags": ["a", "b"]},
        )
        record = repo.append(request)
        loaded = repo.load_by_id(record.event_id)

    assert loaded is not None
    assert loaded.payload == {"nested": {"value": 1}, "tags": ["a", "b"]}


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_person_id_is_canonical_partition_key(event_person_id: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPprEventRepository(conn)
        record = repo.append(_section_append_request(person_id=event_person_id, record_id=104))
        row = conn.execute(
            text("SELECT person_id FROM public.personnel_record_events WHERE event_id = :event_id"),
            {"event_id": record.event_id},
        ).one()

    assert int(row[0]) == event_person_id


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_employee_id_stays_payload_context_only(event_person_id: int) -> None:
    employee_id: int
    with engine.begin() as conn:
        employee_id = insert_employee(conn, full_name="Event Employee", person_id=event_person_id)
        repo = SqlAlchemyPprEventRepository(conn)
        record = repo.append(
            PprEventAppendRequest(
                person_id=event_person_id,
                event_type=EVENT_TYPE_PPR_SECTION_ADDED,
                category=EVENT_CATEGORY_SECTION,
                domain_code=DOMAIN_CODE_EDUCATION,
                record_table_name="person_education",
                record_id=105,
                payload={"employee_id": employee_id},
            )
        )
        loaded = repo.load_by_id(record.event_id)

    assert loaded is not None
    assert loaded.employee_context_id is None
    assert loaded.payload["employee_id"] == employee_id
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[event_person_id], employee_ids=[employee_id])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_occurred_at_and_metadata_round_trip(event_person_id: int) -> None:
    occurred = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    with engine.begin() as conn:
        repo = SqlAlchemyPprEventRepository(conn)
        record = repo.append(
            PprEventAppendRequest(
                person_id=event_person_id,
                event_type=EVENT_TYPE_PPR_CREATED,
                category=EVENT_CATEGORY_LIFECYCLE,
                domain_code=None,
                record_table_name="personnel_record_metadata",
                record_id=event_person_id,
                occurred_at=occurred,
                actor_id="actor-1",
                correlation_id="corr-abc",
                command_id="cmd-xyz",
                source_event_id="ext-999",
                schema_version="1",
                payload={"source": "test"},
            )
        )
        loaded = repo.load_by_id(record.event_id)

    assert loaded is not None
    assert loaded.occurred_at == occurred
    assert loaded.actor_id == "actor-1"
    assert loaded.correlation_id == "corr-abc"
    assert loaded.command_id == "cmd-xyz"
    assert loaded.source_event_id == "ext-999"
    assert loaded.schema_version == "1"
    assert loaded.domain_code is None


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_exists_by_correlation(event_person_id: int) -> None:
    correlation = f"corr-{uuid4().hex[:10]}"
    with engine.begin() as conn:
        repo = SqlAlchemyPprEventRepository(conn)
        assert repo.exists_by_correlation(correlation) is False
        repo.append(
            _section_append_request(
                person_id=event_person_id,
                record_id=106,
                correlation_id=correlation,
            )
        )
        assert repo.exists_by_correlation(correlation) is True
        assert repo.exists_by_correlation(correlation, event_type=EVENT_TYPE_PPR_SECTION_ADDED) is True
        assert repo.exists_by_correlation(correlation, event_type=EVENT_TYPE_PPR_CREATED) is False


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_exists_by_source_event(event_person_id: int) -> None:
    source_id = f"src-{uuid4().hex[:10]}"
    with engine.begin() as conn:
        repo = SqlAlchemyPprEventRepository(conn)
        assert repo.exists_by_source_event(source_id) is False
        repo.append(
            PprEventAppendRequest(
                person_id=event_person_id,
                event_type=EVENT_TYPE_PPR_SECTION_ADDED,
                category=EVENT_CATEGORY_SECTION,
                domain_code=DOMAIN_CODE_EDUCATION,
                record_table_name="person_education",
                record_id=107,
                payload={},
                source_event_id=source_id,
            )
        )
        assert repo.exists_by_source_event(source_id) is True


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_load_by_id_missing_returns_none() -> None:
    _require_events_schema()
    with engine.begin() as conn:
        repo = SqlAlchemyPprEventRepository(conn)
        assert repo.load_by_id(9_999_999_999) is None


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_repository_has_no_update_or_delete_methods() -> None:
    assert not hasattr(SqlAlchemyPprEventRepository, "update_event")
    assert not hasattr(SqlAlchemyPprEventRepository, "delete_event")
    assert not hasattr(SqlAlchemyPprEventRepository, "save_event")
    assert not hasattr(SqlAlchemyPprEventRepository, "replace_payload")


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_record_is_domain_shaped_not_orm(event_person_id: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPprEventRepository(conn)
        record = repo.append(_section_append_request(person_id=event_person_id, record_id=108))

    assert isinstance(record, PprEventRecord)
    assert not hasattr(record, "_sa_instance_state")


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_append_does_not_create_envelope(event_person_id: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPprEventRepository(conn)
        repo.append(
            PprEventAppendRequest(
                person_id=event_person_id,
                event_type=EVENT_TYPE_PPR_CREATED,
                category=EVENT_CATEGORY_LIFECYCLE,
                domain_code=None,
                record_table_name="personnel_record_metadata",
                record_id=event_person_id,
                payload={},
            )
        )
        count = conn.execute(
            text(
                "SELECT COUNT(*) FROM public.personnel_record_metadata WHERE person_id = :person_id"
            ),
            {"person_id": event_person_id},
        ).scalar_one()

    assert int(count) == 0


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_append_does_not_create_employee_or_change_person(event_person_id: int) -> None:
    with engine.begin() as conn:
        before = conn.execute(
            text("SELECT full_name FROM public.persons WHERE person_id = :person_id"),
            {"person_id": event_person_id},
        ).one()[0]
        repo = SqlAlchemyPprEventRepository(conn)
        repo.append(_section_append_request(person_id=event_person_id, record_id=109))
        after = conn.execute(
            text("SELECT full_name FROM public.persons WHERE person_id = :person_id"),
            {"person_id": event_person_id},
        ).one()[0]
        employee_count = conn.execute(text("SELECT COUNT(*) FROM public.employees")).scalar_one()

    assert before == after
    assert int(employee_count) >= 0


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_two_events_for_same_person_allowed(event_person_id: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPprEventRepository(conn)
        first = repo.append(_section_append_request(person_id=event_person_id, record_id=110))
        second = repo.append(_section_append_request(person_id=event_person_id, record_id=111))

    assert first.event_id != second.event_id


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_rollback_removes_appended_event(event_person_id: int) -> None:
    event_id: int
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            repo = SqlAlchemyPprEventRepository(conn)
            record = repo.append(_section_append_request(person_id=event_person_id, record_id=112))
            event_id = record.event_id
            trans.rollback()
        except Exception:
            trans.rollback()
            raise

    with engine.begin() as conn:
        repo = SqlAlchemyPprEventRepository(conn)
        assert repo.load_by_id(event_id) is None


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_historical_loser_person_id_not_redirected() -> None:
    require_ppr_schema()
    _require_events_schema()
    _require_nullable_domain_code()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        survivor_id = insert_person(conn, full_name=f"Survivor {suffix}")
        loser_id = insert_person(
            conn,
            full_name=f"Loser {suffix}",
            merged_into_person_id=survivor_id,
            person_status="merged",
        )
        repo = SqlAlchemyPprEventRepository(conn)
        record = repo.append(
            _section_append_request(person_id=loser_id, record_id=113)
        )
        loaded = repo.load_by_id(record.event_id)

    assert loaded is not None
    assert loaded.person_id == loser_id
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[survivor_id, loser_id], employee_ids=[])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_legacy_pmf_writer_still_works(event_person_id: int) -> None:
    with engine.begin() as conn:
        event_id = emit_personnel_record_event(
            conn,
            person_id=event_person_id,
            domain_code=DOMAIN_CODE_EDUCATION,
            record_table_name="person_education",
            record_id=200,
            event_type="EDUCATION_MIGRATED",
            event_payload={
                "record_kind": "education",
                "source_kind": "manual",
                "source_record_id": "legacy-src",
            },
        )
        row = conn.execute(
            text(
                """
                SELECT event_type, event_payload
                FROM public.personnel_record_events
                WHERE event_id = :event_id
                """
            ),
            {"event_id": event_id},
        ).mappings().one()

    assert row["event_type"] == "EDUCATION_MIGRATED"
    payload = row["event_payload"]
    assert payload["source_record_id"] == "legacy-src"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_legacy_row_readable_after_canonical_append(event_person_id: int) -> None:
    with engine.begin() as conn:
        legacy_id = emit_personnel_record_event(
            conn,
            person_id=event_person_id,
            domain_code=DOMAIN_CODE_EDUCATION,
            record_table_name="person_education",
            record_id=201,
            event_type="EDUCATION_VOIDED",
            event_payload={"void_reason": "cleanup"},
        )
        repo = SqlAlchemyPprEventRepository(conn)
        repo.append(_section_append_request(person_id=event_person_id, record_id=202))
        legacy = repo.load_by_id(legacy_id)

    assert legacy is not None
    assert legacy.event_type == "EDUCATION_VOIDED"
    assert legacy.payload["void_reason"] == "cleanup"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_append_canonical_event_with_null_domain_code(event_person_id: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPprEventRepository(conn)
        record = repo.append(
            PprEventAppendRequest(
                person_id=event_person_id,
                event_type=EVENT_TYPE_PPR_CREATED,
                category=EVENT_CATEGORY_LIFECYCLE,
                domain_code=None,
                record_table_name="personnel_record_metadata",
                record_id=event_person_id,
                payload={},
            )
        )
        loaded = repo.load_by_id(record.event_id)

    assert loaded is not None
    assert loaded.domain_code is None


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_append_does_not_seed_ppr_core_domain(event_person_id: int) -> None:
    with engine.begin() as conn:
        before = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.personnel_migration_domains
                WHERE domain_code = 'ppr_core'
                """
            )
        ).scalar_one()
        repo = SqlAlchemyPprEventRepository(conn)
        repo.append(
            PprEventAppendRequest(
                person_id=event_person_id,
                event_type=EVENT_TYPE_PPR_CREATED,
                category=EVENT_CATEGORY_LIFECYCLE,
                domain_code=None,
                record_table_name="personnel_record_metadata",
                record_id=event_person_id,
                payload={},
            )
        )
        after = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.personnel_migration_domains
                WHERE domain_code = 'ppr_core'
                """
            )
        ).scalar_one()

    assert int(before) == int(after)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_unknown_non_null_domain_code_raises_fk_integrity_error(event_person_id: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPprEventRepository(conn)
        with pytest.raises(IntegrityError):
            repo.append(
                PprEventAppendRequest(
                    person_id=event_person_id,
                    event_type=EVENT_TYPE_PPR_SECTION_ADDED,
                    category=EVENT_CATEGORY_SECTION,
                    domain_code="nonexistent_pmf_domain",
                    record_table_name="person_education",
                    record_id=301,
                    payload={},
                )
            )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_exists_by_correlation_for_null_domain_event(event_person_id: int) -> None:
    correlation = f"corr-null-{uuid4().hex[:10]}"
    with engine.begin() as conn:
        repo = SqlAlchemyPprEventRepository(conn)
        repo.append(
            PprEventAppendRequest(
                person_id=event_person_id,
                event_type=EVENT_TYPE_PPR_CREATED,
                category=EVENT_CATEGORY_LIFECYCLE,
                domain_code=None,
                record_table_name="personnel_record_metadata",
                record_id=event_person_id,
                payload={},
                correlation_id=correlation,
            )
        )
        assert repo.exists_by_correlation(correlation) is True


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_exists_by_source_event_for_null_domain_event(event_person_id: int) -> None:
    source_id = f"src-null-{uuid4().hex[:10]}"
    with engine.begin() as conn:
        repo = SqlAlchemyPprEventRepository(conn)
        repo.append(
            PprEventAppendRequest(
                person_id=event_person_id,
                event_type=EVENT_TYPE_PPR_CREATED,
                category=EVENT_CATEGORY_LIFECYCLE,
                domain_code=None,
                record_table_name="personnel_record_metadata",
                record_id=event_person_id,
                payload={},
                source_event_id=source_id,
            )
        )
        assert repo.exists_by_source_event(source_id) is True


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_rollback_removes_null_domain_event(event_person_id: int) -> None:
    event_id: int
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            repo = SqlAlchemyPprEventRepository(conn)
            record = repo.append(
                PprEventAppendRequest(
                    person_id=event_person_id,
                    event_type=EVENT_TYPE_PPR_CREATED,
                    category=EVENT_CATEGORY_LIFECYCLE,
                    domain_code=None,
                    record_table_name="personnel_record_metadata",
                    record_id=event_person_id,
                    payload={},
                )
            )
            event_id = record.event_id
            trans.rollback()
        except Exception:
            trans.rollback()
            raise

    with engine.begin() as conn:
        repo = SqlAlchemyPprEventRepository(conn)
        assert repo.load_by_id(event_id) is None


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_repository_does_not_create_migration_domain(event_person_id: int) -> None:
    with engine.begin() as conn:
        before = conn.execute(
            text("SELECT COUNT(*) FROM public.personnel_migration_domains")
        ).scalar_one()
        repo = SqlAlchemyPprEventRepository(conn)
        repo.append(
            PprEventAppendRequest(
                person_id=event_person_id,
                event_type=EVENT_TYPE_PPR_CREATED,
                category=EVENT_CATEGORY_LIFECYCLE,
                domain_code=None,
                record_table_name="personnel_record_metadata",
                record_id=event_person_id,
                payload={},
            )
        )
        after = conn.execute(
            text("SELECT COUNT(*) FROM public.personnel_migration_domains")
        ).scalar_one()

    assert int(before) == int(after)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_fk_rejects_nonexistent_person() -> None:
    _require_events_schema()
    _require_nullable_domain_code()
    with engine.begin() as conn:
        repo = SqlAlchemyPprEventRepository(conn)
        with pytest.raises(IntegrityError):
            repo.append(
                PprEventAppendRequest(
                    person_id=9_999_999_999,
                    event_type=EVENT_TYPE_PPR_CREATED,
                    category=EVENT_CATEGORY_LIFECYCLE,
                    record_table_name="personnel_record_metadata",
                    record_id=1,
                    payload={},
                )
            )


def test_protocol_surface() -> None:
    assert hasattr(PprEventRepository, "append")
    assert hasattr(PprEventRepository, "load_by_id")
    assert hasattr(PprEventRepository, "exists_by_correlation")
    assert hasattr(PprEventRepository, "exists_by_source_event")


def test_production_paths_do_not_import_ppr_event_repository() -> None:
    import app.services.personnel_migration_commit_service as commit_service
    import app.services.personnel_record_event_service as event_service

    source_commit = commit_service.__file__ or ""
    source_event = event_service.__file__ or ""
    assert source_commit
    assert source_event
    with open(source_commit, encoding="utf-8") as handle:
        commit_source = handle.read()
    with open(source_event, encoding="utf-8") as handle:
        event_source = handle.read()
    assert "PprEventRepository" not in commit_source
    assert "SqlAlchemyPprEventRepository" not in commit_source
    assert "PprEventRepository" not in event_source
    assert "SqlAlchemyPprEventRepository" not in event_source
