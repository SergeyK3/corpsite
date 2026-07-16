# tests/ppr/test_r5_family_write_path.py
"""R5 application write-path tests for PPR-FAMILY (WP-PR-P4-001-B)."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_migration import RELATIONSHIP_TYPE_MOTHER
from app.ppr.application.authorization import AllowAllAuthorizationPort
from app.ppr.application.command_models import (
    COMMAND_TYPE_ACTIVATE_PPR,
    COMMAND_TYPE_ADD_RELATIVE,
    COMMAND_TYPE_MATERIALIZE_PPR,
    COMMAND_TYPE_SUPERSEDE_RELATIVE,
    COMMAND_TYPE_UPDATE_RELATIVE,
    COMMAND_TYPE_VOID_RELATIVE,
    PprCommandEnvelope,
)
from app.ppr.application.lifecycle_service import PprLifecycleApplicationService
from app.ppr.application.results import RESULT_STATUS_COMMITTED, RESULT_STATUS_IDEMPOTENT_REPLAY
from app.ppr.application.section_service import PprSectionApplicationService
from app.ppr.domain.errors import SectionOptimisticConcurrencyConflictError, SectionValidationError
from tests.conftest import table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_person, ppr_db_available, require_ppr_schema


def _require_r5_schema() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "ppr_command_executions"):
            pytest.skip("ppr_command_executions missing — run: alembic upgrade head")
        if not table_exists(conn, "person_relatives"):
            pytest.skip("person_relatives missing — run: alembic upgrade head")


@pytest.fixture
def family_person_id():
    require_ppr_schema()
    _require_r5_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"PPR Family R5 {suffix}")
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


def _add_relative_envelope(person_id: int, *, command_id: str | None = None) -> PprCommandEnvelope:
    return PprCommandEnvelope(
        command_id=command_id or f"rel-{uuid4().hex}",
        command_type=COMMAND_TYPE_ADD_RELATIVE,
        actor_id="test-actor",
        requested_at=datetime.now(UTC),
        payload={
            "relationship_type": RELATIONSHIP_TYPE_MOTHER,
            "full_name": "Иванова Анна Петровна",
        },
        person_id=person_id,
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_add_relative_commits_with_canonical_event(
    family_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(family_person_id, lifecycle_service)
    result = section_service.add_relative(_add_relative_envelope(family_person_id))
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
        relative_count = conn.execute(
            text("SELECT COUNT(*) FROM public.person_relatives WHERE person_id = :pid"),
            {"pid": family_person_id},
        ).scalar_one()

    assert event[0] == "PPR_SECTION_ADDED"
    assert event[1] == "person_relatives"
    assert event[2] == "PPR-FAMILY"
    assert int(relative_count) == 1


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_add_relative_idempotent_replay(
    family_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(family_person_id, lifecycle_service)
    command_id = f"rel-replay-{uuid4().hex}"
    env = _add_relative_envelope(family_person_id, command_id=command_id)
    first = section_service.add_relative(env)
    second = section_service.add_relative(env)
    assert first.status == RESULT_STATUS_COMMITTED
    assert second.status == RESULT_STATUS_IDEMPOTENT_REPLAY

    with engine.begin() as conn:
        relatives = conn.execute(
            text("SELECT COUNT(*) FROM public.person_relatives WHERE person_id = :pid"),
            {"pid": family_person_id},
        ).scalar_one()
        events = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.personnel_record_events
                WHERE person_id = :pid AND event_type = 'PPR_SECTION_ADDED'
                  AND record_table_name = 'person_relatives'
                """
            ),
            {"pid": family_person_id},
        ).scalar_one()
        cmds = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.ppr_command_executions
                WHERE command_id = :cid AND status = 'completed'
                """
            ),
            {"cid": command_id},
        ).scalar_one()

    assert int(relatives) == 1
    assert int(events) == 1
    assert int(cmds) == 1


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_add_relative_validation_failure_is_atomic(
    family_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(family_person_id, lifecycle_service)
    with pytest.raises(SectionValidationError):
        section_service.add_relative(
            PprCommandEnvelope(
                command_id=f"rel-invalid-{uuid4().hex}",
                command_type=COMMAND_TYPE_ADD_RELATIVE,
                actor_id="test-actor",
                requested_at=datetime.now(UTC),
                payload={
                    "relationship_type": RELATIONSHIP_TYPE_MOTHER,
                    "full_name": "   ",
                },
                person_id=family_person_id,
            )
        )

    with engine.begin() as conn:
        relatives = conn.execute(
            text("SELECT COUNT(*) FROM public.person_relatives WHERE person_id = :pid"),
            {"pid": family_person_id},
        ).scalar_one()
        events = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.personnel_record_events
                WHERE person_id = :pid AND record_table_name = 'person_relatives'
                """
            ),
            {"pid": family_person_id},
        ).scalar_one()
        cmds = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.ppr_command_executions
                WHERE person_id = :pid AND command_type = :op
                """
            ),
            {"pid": family_person_id, "op": COMMAND_TYPE_ADD_RELATIVE},
        ).scalar_one()

    assert int(relatives) == 0
    assert int(events) == 0
    assert int(cmds) == 0


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_void_relative_commits_with_canonical_event(
    family_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(family_person_id, lifecycle_service)
    added = section_service.add_relative(_add_relative_envelope(family_person_id))
    assert added.section_record_id is not None

    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT relative_id, updated_at
                FROM public.person_relatives
                WHERE relative_id = :rid
                """
            ),
            {"rid": added.section_record_id},
        ).one()

    result = section_service.void_relative(
        PprCommandEnvelope(
            command_id=f"rel-void-{uuid4().hex}",
            command_type=COMMAND_TYPE_VOID_RELATIVE,
            actor_id="test-actor",
            requested_at=datetime.now(UTC),
            payload={
                "record_id": int(row[0]),
                "reason": "correction",
                "expected_updated_at": row[1],
            },
            person_id=family_person_id,
        )
    )
    assert result.status == RESULT_STATUS_COMMITTED

    with engine.begin() as conn:
        event_type = conn.execute(
            text("SELECT event_type FROM public.personnel_record_events WHERE event_id = :eid"),
            {"eid": result.event_ids[0]},
        ).scalar_one()
        lifecycle_status = conn.execute(
            text("SELECT lifecycle_status FROM public.person_relatives WHERE relative_id = :rid"),
            {"rid": added.section_record_id},
        ).scalar_one()

    assert event_type == "PPR_SECTION_VOIDED"
    assert lifecycle_status == "voided"


def _load_relative_row(record_id: int) -> tuple[int, datetime, str]:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT relative_id, updated_at, full_name
                FROM public.person_relatives
                WHERE relative_id = :rid
                """
            ),
            {"rid": record_id},
        ).one()
    return int(row[0]), row[1], str(row[2])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_update_relative_commits_with_canonical_event(
    family_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(family_person_id, lifecycle_service)
    added = section_service.add_relative(_add_relative_envelope(family_person_id))
    assert added.section_record_id is not None
    _, updated_at, _ = _load_relative_row(added.section_record_id)

    result = section_service.update_relative(
        PprCommandEnvelope(
            command_id=f"rel-update-{uuid4().hex}",
            command_type=COMMAND_TYPE_UPDATE_RELATIVE,
            actor_id="test-actor",
            requested_at=datetime.now(UTC),
            payload={
                "record_id": added.section_record_id,
                "expected_updated_at": updated_at,
                "full_name": "Иванова Анна Сергеевна",
            },
            person_id=family_person_id,
        )
    )
    assert result.status == RESULT_STATUS_COMMITTED

    with engine.begin() as conn:
        event_type = conn.execute(
            text("SELECT event_type FROM public.personnel_record_events WHERE event_id = :eid"),
            {"eid": result.event_ids[0]},
        ).scalar_one()
        full_name = conn.execute(
            text("SELECT full_name FROM public.person_relatives WHERE relative_id = :rid"),
            {"rid": added.section_record_id},
        ).scalar_one()

    assert event_type == "PPR_SECTION_UPDATED"
    assert full_name == "Иванова Анна Сергеевна"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_supersede_relative_commits_with_canonical_event(
    family_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(family_person_id, lifecycle_service)
    added = section_service.add_relative(_add_relative_envelope(family_person_id))
    assert added.section_record_id is not None
    _, updated_at, _ = _load_relative_row(added.section_record_id)

    result = section_service.supersede_relative(
        PprCommandEnvelope(
            command_id=f"rel-supersede-{uuid4().hex}",
            command_type=COMMAND_TYPE_SUPERSEDE_RELATIVE,
            actor_id="test-actor",
            requested_at=datetime.now(UTC),
            payload={
                "record_id": added.section_record_id,
                "expected_updated_at": updated_at,
                "replacement": {
                    "relationship_type": RELATIONSHIP_TYPE_MOTHER,
                    "full_name": "Иванова Анна Петровна (исправлено)",
                },
            },
            person_id=family_person_id,
        )
    )
    assert result.status == RESULT_STATUS_COMMITTED
    assert result.section_record_id is not None
    assert result.section_record_id != added.section_record_id

    with engine.begin() as conn:
        event_type = conn.execute(
            text("SELECT event_type FROM public.personnel_record_events WHERE event_id = :eid"),
            {"eid": result.event_ids[0]},
        ).scalar_one()
        old_status = conn.execute(
            text("SELECT lifecycle_status FROM public.person_relatives WHERE relative_id = :rid"),
            {"rid": added.section_record_id},
        ).scalar_one()
        new_name = conn.execute(
            text("SELECT full_name FROM public.person_relatives WHERE relative_id = :rid"),
            {"rid": result.section_record_id},
        ).scalar_one()

    assert event_type == "PPR_SECTION_SUPERSEDED"
    assert old_status == "superseded"
    assert new_name == "Иванова Анна Петровна (исправлено)"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_update_relative_stale_token_raises_and_rolls_back(
    family_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(family_person_id, lifecycle_service)
    added = section_service.add_relative(_add_relative_envelope(family_person_id))
    assert added.section_record_id is not None
    _, updated_at, original_name = _load_relative_row(added.section_record_id)

    with engine.begin() as conn:
        events_before = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.personnel_record_events
                WHERE person_id = :pid AND record_table_name = 'person_relatives'
                """
            ),
            {"pid": family_person_id},
        ).scalar_one()

    with pytest.raises(SectionOptimisticConcurrencyConflictError):
        section_service.update_relative(
            PprCommandEnvelope(
                command_id=f"rel-stale-{uuid4().hex}",
                command_type=COMMAND_TYPE_UPDATE_RELATIVE,
                actor_id="test-actor",
                requested_at=datetime.now(UTC),
                payload={
                    "record_id": added.section_record_id,
                    "expected_updated_at": updated_at.replace(year=2000),
                    "full_name": "Should Not Persist",
                },
                person_id=family_person_id,
            )
        )

    _, _, current_name = _load_relative_row(added.section_record_id)
    with engine.begin() as conn:
        events_after = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.personnel_record_events
                WHERE person_id = :pid AND record_table_name = 'person_relatives'
                """
            ),
            {"pid": family_person_id},
        ).scalar_one()
        cmds = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.ppr_command_executions
                WHERE person_id = :pid AND command_type = :op
                """
            ),
            {"pid": family_person_id, "op": COMMAND_TYPE_UPDATE_RELATIVE},
        ).scalar_one()

    assert current_name == original_name
    assert int(events_after) == int(events_before)
    assert int(cmds) == 0
