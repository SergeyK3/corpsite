# tests/ppr/test_r5_military_write_path.py
"""R5 application write-path tests for PPR-MILITARY (WP-PR-029)."""
from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.engine import engine
from app.db.models.personnel_migration import (
    MILITARY_RECORD_KIND_NOT_APPLICABLE,
    MILITARY_RECORD_KIND_REGISTRATION,
    SECTION_SOURCE_TYPE_ENTERED,
)
from app.ppr.application.authorization import AllowAllAuthorizationPort
from app.ppr.application.command_models import (
    COMMAND_TYPE_ACTIVATE_PPR,
    COMMAND_TYPE_CREATE_MILITARY_SERVICE,
    COMMAND_TYPE_MATERIALIZE_PPR,
    COMMAND_TYPE_SUPERSEDE_MILITARY_SERVICE,
    COMMAND_TYPE_VOID_MILITARY_SERVICE,
    PprCommandEnvelope,
)
from app.ppr.application.lifecycle_service import PprLifecycleApplicationService
from app.ppr.application.results import RESULT_STATUS_COMMITTED, RESULT_STATUS_IDEMPOTENT_REPLAY
from app.ppr.application.section_service import PprSectionApplicationService
from app.ppr.domain.errors import (
    SectionOptimisticConcurrencyConflictError,
    SectionRecordNotFoundError,
)
from app.ppr.domain.section_models import SECTION_CODE_PPR_MILITARY
from tests.conftest import table_exists
from tests.ppr.conftest import (
    cleanup_person_graph,
    insert_employee,
    insert_person,
    ppr_db_available,
    require_ppr_schema,
)


def _require_schema() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "ppr_command_executions"):
            pytest.skip("ppr_command_executions missing — run: alembic upgrade head")
        if not table_exists(conn, "person_military_service"):
            pytest.skip("person_military_service missing — run: alembic upgrade head")


@pytest.fixture
def military_person_id():
    require_ppr_schema()
    _require_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"PPR Military R5 {suffix}")
    yield person_id
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])


@pytest.fixture
def other_person_id():
    require_ppr_schema()
    _require_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"PPR Military Other {suffix}")
    yield person_id
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])


@pytest.fixture
def lifecycle_service():
    return PprLifecycleApplicationService(authorization=AllowAllAuthorizationPort())


@pytest.fixture
def section_service():
    return PprSectionApplicationService(authorization=AllowAllAuthorizationPort())


def _materialize_and_activate(person_id: int, lifecycle_service: PprLifecycleApplicationService) -> None:
    lifecycle_service.materialize_ppr(
        PprCommandEnvelope(
            command_id=f"mat-{uuid4().hex}",
            command_type=COMMAND_TYPE_MATERIALIZE_PPR,
            actor_id="test-actor",
            requested_at=datetime.now(UTC),
            payload={},
            person_id=person_id,
        )
    )
    lifecycle_service.activate_ppr(
        PprCommandEnvelope(
            command_id=f"act-{uuid4().hex}",
            command_type=COMMAND_TYPE_ACTIVATE_PPR,
            actor_id="test-actor",
            requested_at=datetime.now(UTC),
            payload={},
            person_id=person_id,
        )
    )


def _registration_payload(**overrides) -> dict:
    base = {
        "record_kind": MILITARY_RECORD_KIND_REGISTRATION,
        "obligation_status": "liable",
        "registration_category": "II",
        "military_rank": "рядовой",
        "registration_status": "registered",
        "source_type": SECTION_SOURCE_TYPE_ENTERED,
    }
    base.update(overrides)
    return base


def _create_envelope(person_id: int, *, command_id: str | None = None, **payload_overrides) -> PprCommandEnvelope:
    return PprCommandEnvelope(
        command_id=command_id or f"mil-{uuid4().hex}",
        command_type=COMMAND_TYPE_CREATE_MILITARY_SERVICE,
        actor_id="test-actor",
        requested_at=datetime.now(UTC),
        payload=_registration_payload(**payload_overrides),
        person_id=person_id,
    )


def _load_military_row(record_id: int) -> tuple[int, datetime, str]:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT military_id, updated_at, lifecycle_status
                FROM public.person_military_service
                WHERE military_id = :rid
                """
            ),
            {"rid": record_id},
        ).one()
    return int(row[0]), row[1], str(row[2])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_create_registration_commits_with_canonical_event(
    military_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(military_person_id, lifecycle_service)
    result = section_service.create_military_service(_create_envelope(military_person_id))
    assert result.status == RESULT_STATUS_COMMITTED
    assert result.section_record_id is not None
    assert len(result.event_ids) == 1

    with engine.begin() as conn:
        event = conn.execute(
            text(
                """
                SELECT event_type, record_table_name, event_payload->>'section_code' AS section_code
                FROM public.personnel_record_events
                WHERE event_id = :event_id
                """
            ),
            {"event_id": result.event_ids[0]},
        ).one()
        rank = conn.execute(
            text("SELECT military_rank FROM public.person_military_service WHERE military_id = :rid"),
            {"rid": result.section_record_id},
        ).scalar_one()

    assert event[0] == "PPR_SECTION_ADDED"
    assert event[1] == "person_military_service"
    assert event[2] == SECTION_CODE_PPR_MILITARY
    assert rank == "рядовой"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_create_not_applicable_commits(
    military_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(military_person_id, lifecycle_service)
    result = section_service.create_military_service(
        PprCommandEnvelope(
            command_id=f"na-{uuid4().hex}",
            command_type=COMMAND_TYPE_CREATE_MILITARY_SERVICE,
            actor_id="test-actor",
            requested_at=datetime.now(UTC),
            payload={
                "record_kind": MILITARY_RECORD_KIND_NOT_APPLICABLE,
                "notes": "Не подлежит воинскому учёту",
                "source_type": SECTION_SOURCE_TYPE_ENTERED,
            },
            person_id=military_person_id,
        )
    )
    assert result.status == RESULT_STATUS_COMMITTED

    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT record_kind, obligation_status, military_rank
                FROM public.person_military_service
                WHERE military_id = :rid
                """
            ),
            {"rid": result.section_record_id},
        ).one()

    assert row[0] == MILITARY_RECORD_KIND_NOT_APPLICABLE
    assert row[1] is None
    assert row[2] is None


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_supersede_pair(
    military_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(military_person_id, lifecycle_service)
    added = section_service.create_military_service(_create_envelope(military_person_id))
    assert added.section_record_id is not None
    _, updated_at, _ = _load_military_row(added.section_record_id)

    result = section_service.supersede_military_service(
        PprCommandEnvelope(
            command_id=f"sup-{uuid4().hex}",
            command_type=COMMAND_TYPE_SUPERSEDE_MILITARY_SERVICE,
            actor_id="test-actor",
            requested_at=datetime.now(UTC),
            payload={
                "record_id": added.section_record_id,
                "expected_updated_at": updated_at,
                "replacement": _registration_payload(military_rank="лейтенант"),
            },
            person_id=military_person_id,
        )
    )
    assert result.status == RESULT_STATUS_COMMITTED

    with engine.begin() as conn:
        old_status = conn.execute(
            text(
                "SELECT lifecycle_status FROM public.person_military_service WHERE military_id = :rid"
            ),
            {"rid": added.section_record_id},
        ).scalar_one()
        new_rank = conn.execute(
            text(
                "SELECT military_rank FROM public.person_military_service WHERE military_id = :rid"
            ),
            {"rid": result.section_record_id},
        ).scalar_one()

    assert old_status == "superseded"
    assert new_rank == "лейтенант"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_void_record(
    military_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(military_person_id, lifecycle_service)
    added = section_service.create_military_service(_create_envelope(military_person_id))
    assert added.section_record_id is not None
    _, updated_at, _ = _load_military_row(added.section_record_id)

    result = section_service.void_military_service(
        PprCommandEnvelope(
            command_id=f"void-{uuid4().hex}",
            command_type=COMMAND_TYPE_VOID_MILITARY_SERVICE,
            actor_id="test-actor",
            requested_at=datetime.now(UTC),
            payload={
                "record_id": added.section_record_id,
                "reason": "Ошибочная запись",
                "expected_updated_at": updated_at,
            },
            person_id=military_person_id,
        )
    )
    assert result.status == RESULT_STATUS_COMMITTED

    with engine.begin() as conn:
        status = conn.execute(
            text(
                """
                SELECT lifecycle_status FROM public.person_military_service
                WHERE military_id = :rid
                """
            ),
            {"rid": added.section_record_id},
        ).scalar_one()
        active_count = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.person_military_service
                WHERE person_id = :pid AND lifecycle_status = 'active'
                """
            ),
            {"pid": military_person_id},
        ).scalar_one()

    assert status == "voided"
    assert int(active_count) == 0


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_stale_void_raises(
    military_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(military_person_id, lifecycle_service)
    added = section_service.create_military_service(_create_envelope(military_person_id))
    assert added.section_record_id is not None
    _, updated_at, _ = _load_military_row(added.section_record_id)

    with pytest.raises(SectionOptimisticConcurrencyConflictError):
        section_service.void_military_service(
            PprCommandEnvelope(
                command_id=f"void-stale-{uuid4().hex}",
                command_type=COMMAND_TYPE_VOID_MILITARY_SERVICE,
                actor_id="test-actor",
                requested_at=datetime.now(UTC),
                payload={
                    "record_id": added.section_record_id,
                    "reason": "fail",
                    "expected_updated_at": updated_at.replace(year=2000),
                },
                person_id=military_person_id,
            )
        )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_second_active_conflict(
    military_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(military_person_id, lifecycle_service)
    section_service.create_military_service(_create_envelope(military_person_id))
    with pytest.raises(IntegrityError):
        section_service.create_military_service(
            _create_envelope(military_person_id, military_rank="conflict")
        )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_create_idempotent_replay(
    military_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(military_person_id, lifecycle_service)
    command_id = f"idempotent-{uuid4().hex}"
    first = section_service.create_military_service(
        _create_envelope(military_person_id, command_id=command_id)
    )
    second = section_service.create_military_service(
        _create_envelope(military_person_id, command_id=command_id)
    )
    assert first.status == RESULT_STATUS_COMMITTED
    assert second.status == RESULT_STATUS_IDEMPOTENT_REPLAY
    assert second.section_record_id == first.section_record_id


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_void_idempotent_replay(
    military_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(military_person_id, lifecycle_service)
    added = section_service.create_military_service(_create_envelope(military_person_id))
    assert added.section_record_id is not None
    _, updated_at, _ = _load_military_row(added.section_record_id)
    command_id = f"void-idem-{uuid4().hex}"
    payload = {
        "record_id": added.section_record_id,
        "reason": "Ошибочная запись",
        "expected_updated_at": updated_at,
    }
    first = section_service.void_military_service(
        PprCommandEnvelope(
            command_id=command_id,
            command_type=COMMAND_TYPE_VOID_MILITARY_SERVICE,
            actor_id="test-actor",
            requested_at=datetime.now(UTC),
            payload=payload,
            person_id=military_person_id,
        )
    )
    second = section_service.void_military_service(
        PprCommandEnvelope(
            command_id=command_id,
            command_type=COMMAND_TYPE_VOID_MILITARY_SERVICE,
            actor_id="test-actor",
            requested_at=datetime.now(UTC),
            payload=payload,
            person_id=military_person_id,
        )
    )
    assert first.status == RESULT_STATUS_COMMITTED
    assert second.status == RESULT_STATUS_IDEMPOTENT_REPLAY


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_stale_supersede_raises(
    military_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(military_person_id, lifecycle_service)
    added = section_service.create_military_service(_create_envelope(military_person_id))
    assert added.section_record_id is not None
    _, updated_at, _ = _load_military_row(added.section_record_id)

    with pytest.raises(SectionOptimisticConcurrencyConflictError):
        section_service.supersede_military_service(
            PprCommandEnvelope(
                command_id=f"sup-stale-{uuid4().hex}",
                command_type=COMMAND_TYPE_SUPERSEDE_MILITARY_SERVICE,
                actor_id="test-actor",
                requested_at=datetime.now(UTC),
                payload={
                    "record_id": added.section_record_id,
                    "expected_updated_at": updated_at.replace(year=2000),
                    "replacement": _registration_payload(military_rank="fail"),
                },
                person_id=military_person_id,
            )
        )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_supersede_idempotent_replay(
    military_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(military_person_id, lifecycle_service)
    added = section_service.create_military_service(_create_envelope(military_person_id))
    assert added.section_record_id is not None
    _, updated_at, _ = _load_military_row(added.section_record_id)
    command_id = f"sup-idem-{uuid4().hex}"
    payload = {
        "record_id": added.section_record_id,
        "expected_updated_at": updated_at,
        "replacement": _registration_payload(military_rank="капитан"),
    }
    first = section_service.supersede_military_service(
        PprCommandEnvelope(
            command_id=command_id,
            command_type=COMMAND_TYPE_SUPERSEDE_MILITARY_SERVICE,
            actor_id="test-actor",
            requested_at=datetime.now(UTC),
            payload=payload,
            person_id=military_person_id,
        )
    )
    second = section_service.supersede_military_service(
        PprCommandEnvelope(
            command_id=command_id,
            command_type=COMMAND_TYPE_SUPERSEDE_MILITARY_SERVICE,
            actor_id="test-actor",
            requested_at=datetime.now(UTC),
            payload=payload,
            person_id=military_person_id,
        )
    )
    assert first.status == RESULT_STATUS_COMMITTED
    assert second.status == RESULT_STATUS_IDEMPOTENT_REPLAY
    assert second.section_record_id == first.section_record_id


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_employee_route_resolves_person_for_create(
    lifecycle_service,
    section_service,
) -> None:
    require_ppr_schema()
    _require_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"PPR Military Emp {suffix}")
        employee_id = insert_employee(conn, full_name=f"PPR Military Emp {suffix}", person_id=person_id)
    try:
        _materialize_and_activate(person_id, lifecycle_service)
        result = section_service.create_military_service(_create_envelope(person_id))
        assert result.status == RESULT_STATUS_COMMITTED
        with engine.begin() as conn:
            stored_person = conn.execute(
                text("SELECT person_id FROM public.person_military_service WHERE military_id = :rid"),
                {"rid": result.section_record_id},
            ).scalar_one()
        assert int(stored_person) == person_id
        assert employee_id != person_id
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[employee_id])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_foreign_person_void_not_found(
    military_person_id: int,
    other_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(military_person_id, lifecycle_service)
    _materialize_and_activate(other_person_id, lifecycle_service)
    added = section_service.create_military_service(_create_envelope(military_person_id))
    assert added.section_record_id is not None
    _, updated_at, _ = _load_military_row(added.section_record_id)

    with pytest.raises(SectionRecordNotFoundError):
        section_service.void_military_service(
            PprCommandEnvelope(
                command_id=f"foreign-{uuid4().hex}",
                command_type=COMMAND_TYPE_VOID_MILITARY_SERVICE,
                actor_id="test-actor",
                requested_at=datetime.now(UTC),
                payload={
                    "record_id": added.section_record_id,
                    "reason": "wrong person",
                    "expected_updated_at": updated_at,
                },
                person_id=other_person_id,
            )
        )
