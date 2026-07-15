# tests/ppr/test_r5_application_write_path.py
"""Integration tests for PPR R5 application write path."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_migration import EDUCATION_KIND_BASIC, TRAINING_KIND_COURSE
from app.ppr.application.authorization import AllowAllAuthorizationPort
from app.ppr.application.command_models import (
    COMMAND_TYPE_ACTIVATE_PPR,
    COMMAND_TYPE_MATERIALIZE_PPR,
    COMMAND_TYPE_START_COLLECTION,
    MaterializePprPayload,
    PprCommandEnvelope,
)
from app.ppr.application.lifecycle_service import PprLifecycleApplicationService
from app.ppr.application.post_commit import LoggingPostCommitHookRunner
from app.ppr.application.results import (
    RESULT_STATUS_ALREADY_MATERIALIZED,
    RESULT_STATUS_COMMITTED,
    RESULT_STATUS_IDEMPOTENT_REPLAY,
    RESULT_STATUS_NO_OP,
)
from app.ppr.application.section_service import PprSectionApplicationService
from app.ppr.domain.errors import (
    PprAuthorizationDeniedError,
    PprCommandIdConflictError,
    PprNotMaterializedError,
    PprOptimisticConcurrencyConflictError,
)
from app.ppr.domain.models import PPR_LIFECYCLE_ACTIVE, PPR_LIFECYCLE_COLLECTING, PPR_LIFECYCLE_CREATED
from tests.conftest import table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_person, ppr_db_available, require_ppr_schema


def _require_r5_schema() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "ppr_command_executions"):
            pytest.skip("ppr_command_executions missing — run: alembic upgrade head")


@pytest.fixture
def r5_person_id():
    require_ppr_schema()
    _require_r5_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"PPR R5 Person {suffix}")
    yield person_id
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])


def _now_envelope(command_id: str, command_type: str, person_id: int, **kwargs) -> PprCommandEnvelope:
    return PprCommandEnvelope(
        command_id=command_id,
        command_type=command_type,
        actor_id="test-actor",
        requested_at=datetime.now(UTC),
        payload=kwargs.pop("payload", MaterializePprPayload()),
        person_id=person_id,
        **kwargs,
    )


@pytest.fixture
def lifecycle_service():
    return PprLifecycleApplicationService(
        authorization=AllowAllAuthorizationPort(),
        post_commit=LoggingPostCommitHookRunner(),
    )


@pytest.fixture
def section_service():
    return PprSectionApplicationService(authorization=AllowAllAuthorizationPort())


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_materialize_ppr_creates_envelope_and_event(r5_person_id: int, lifecycle_service) -> None:
    command_id = f"mat-{uuid4().hex}"
    result = lifecycle_service.materialize_ppr(
        _now_envelope(command_id, COMMAND_TYPE_MATERIALIZE_PPR, r5_person_id)
    )
    assert result.status == RESULT_STATUS_COMMITTED
    assert result.envelope_version == 1
    assert len(result.event_ids) == 1

    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT ppr_lifecycle_state, version
                FROM public.personnel_record_metadata
                WHERE person_id = :person_id
                """
            ),
            {"person_id": r5_person_id},
        ).one()
        event = conn.execute(
            text(
                """
                SELECT event_type, domain_code
                FROM public.personnel_record_events
                WHERE event_id = :event_id
                """
            ),
            {"event_id": result.event_ids[0]},
        ).one()
    assert row[0] == PPR_LIFECYCLE_CREATED
    assert int(row[1]) == 1
    assert event[0] == "PPR_CREATED"
    assert event[1] is None


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_materialize_same_command_id_replay(r5_person_id: int, lifecycle_service) -> None:
    command_id = f"mat-replay-{uuid4().hex}"
    env = _now_envelope(command_id, COMMAND_TYPE_MATERIALIZE_PPR, r5_person_id)
    first = lifecycle_service.materialize_ppr(env)
    second = lifecycle_service.materialize_ppr(env)
    assert first.status == RESULT_STATUS_COMMITTED
    assert second.status == RESULT_STATUS_IDEMPOTENT_REPLAY
    with engine.begin() as conn:
        count = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.personnel_record_metadata WHERE person_id = :person_id
                """
            ),
            {"person_id": r5_person_id},
        ).scalar_one()
        events = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.personnel_record_events
                WHERE person_id = :person_id AND event_type = 'PPR_CREATED'
                """
            ),
            {"person_id": r5_person_id},
        ).scalar_one()
    assert int(count) == 1
    assert int(events) == 1


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_materialize_different_command_id_already_materialized(r5_person_id: int, lifecycle_service) -> None:
    lifecycle_service.materialize_ppr(
        _now_envelope(f"mat-a-{uuid4().hex}", COMMAND_TYPE_MATERIALIZE_PPR, r5_person_id)
    )
    result = lifecycle_service.materialize_ppr(
        _now_envelope(f"mat-b-{uuid4().hex}", COMMAND_TYPE_MATERIALIZE_PPR, r5_person_id)
    )
    assert result.status == RESULT_STATUS_ALREADY_MATERIALIZED


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_start_collection_and_activate(r5_person_id: int, lifecycle_service) -> None:
    lifecycle_service.materialize_ppr(
        _now_envelope(f"mat-{uuid4().hex}", COMMAND_TYPE_MATERIALIZE_PPR, r5_person_id)
    )
    started = lifecycle_service.start_collection(
        _now_envelope(f"start-{uuid4().hex}", COMMAND_TYPE_START_COLLECTION, r5_person_id)
    )
    assert started.status == RESULT_STATUS_COMMITTED
    activated = lifecycle_service.activate_ppr(
        _now_envelope(f"act-{uuid4().hex}", COMMAND_TYPE_ACTIVATE_PPR, r5_person_id)
    )
    assert activated.status == RESULT_STATUS_COMMITTED
    with engine.begin() as conn:
        state = conn.execute(
            text(
                "SELECT ppr_lifecycle_state FROM public.personnel_record_metadata WHERE person_id = :pid"
            ),
            {"pid": r5_person_id},
        ).scalar_one()
    assert state == PPR_LIFECYCLE_ACTIVE


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_activate_no_op_when_already_active(r5_person_id: int, lifecycle_service) -> None:
    lifecycle_service.materialize_ppr(
        _now_envelope(f"mat-{uuid4().hex}", COMMAND_TYPE_MATERIALIZE_PPR, r5_person_id)
    )
    lifecycle_service.activate_ppr(
        _now_envelope(f"act1-{uuid4().hex}", COMMAND_TYPE_ACTIVATE_PPR, r5_person_id)
    )
    again = lifecycle_service.activate_ppr(
        _now_envelope(f"act2-{uuid4().hex}", COMMAND_TYPE_ACTIVATE_PPR, r5_person_id)
    )
    assert again.status == RESULT_STATUS_NO_OP


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_section_add_requires_materialized_envelope(r5_person_id: int, section_service) -> None:
    with pytest.raises(PprNotMaterializedError):
        section_service.add_education(
            PprCommandEnvelope(
                command_id=f"edu-{uuid4().hex}",
                command_type="AddEducationRecord",
                actor_id="test-actor",
                requested_at=datetime.now(UTC),
                payload={
                    "education_kind": EDUCATION_KIND_BASIC,
                    "institution_name": "R5 University",
                },
                person_id=r5_person_id,
            )
        )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_section_add_commits_with_canonical_event(
    r5_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    lifecycle_service.materialize_ppr(
        _now_envelope(f"mat-{uuid4().hex}", COMMAND_TYPE_MATERIALIZE_PPR, r5_person_id)
    )
    lifecycle_service.activate_ppr(
        _now_envelope(f"act-{uuid4().hex}", COMMAND_TYPE_ACTIVATE_PPR, r5_person_id)
    )
    result = section_service.add_education(
        PprCommandEnvelope(
            command_id=f"edu-{uuid4().hex}",
            command_type="AddEducationRecord",
            actor_id="test-actor",
            requested_at=datetime.now(UTC),
            payload={
                "education_kind": EDUCATION_KIND_BASIC,
                "institution_name": "R5 University",
            },
            person_id=r5_person_id,
        )
    )
    assert result.status == RESULT_STATUS_COMMITTED
    assert result.section_record_id is not None
    assert len(result.event_ids) == 1
    with engine.begin() as conn:
        event_type = conn.execute(
            text("SELECT event_type FROM public.personnel_record_events WHERE event_id = :eid"),
            {"eid": result.event_ids[0]},
        ).scalar_one()
    assert event_type == "PPR_SECTION_ADDED"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_command_id_conflict_on_payload_mismatch(r5_person_id: int, lifecycle_service) -> None:
    command_id = f"conflict-{uuid4().hex}"
    lifecycle_service.materialize_ppr(
        PprCommandEnvelope(
            command_id=command_id,
            command_type=COMMAND_TYPE_MATERIALIZE_PPR,
            actor_id="test-actor",
            requested_at=datetime.now(UTC),
            payload=MaterializePprPayload(hr_relationship_context="UNKNOWN"),
            person_id=r5_person_id,
        )
    )
    with pytest.raises(PprCommandIdConflictError):
        lifecycle_service.materialize_ppr(
            PprCommandEnvelope(
                command_id=command_id,
                command_type=COMMAND_TYPE_MATERIALIZE_PPR,
                actor_id="test-actor",
                requested_at=datetime.now(UTC),
                payload=MaterializePprPayload(hr_relationship_context="EMPLOYED"),
                person_id=r5_person_id,
            )
        )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_authorization_denied_before_mutation(r5_person_id: int) -> None:
    from app.ppr.application.authorization import AuthorizationPort

    class DenyPort(AuthorizationPort):
        def authorize_mutation(self, **kwargs) -> None:
            del kwargs
            raise PprAuthorizationDeniedError("denied")

    service = PprLifecycleApplicationService(authorization=DenyPort())
    with pytest.raises(PprAuthorizationDeniedError):
        service.materialize_ppr(
            _now_envelope(f"mat-{uuid4().hex}", COMMAND_TYPE_MATERIALIZE_PPR, r5_person_id)
        )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_post_commit_warning_does_not_rollback(r5_person_id: int) -> None:
    class WarningHook:
        def run(self, actions):
            del actions
            return ("hook failed",)

    service = PprLifecycleApplicationService(
        authorization=AllowAllAuthorizationPort(),
        post_commit=WarningHook(),
    )
    result = service.materialize_ppr(
        _now_envelope(f"mat-{uuid4().hex}", COMMAND_TYPE_MATERIALIZE_PPR, r5_person_id)
    )
    assert result.post_commit_warnings == ("hook failed",)
    with engine.begin() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM public.personnel_record_metadata WHERE person_id = :pid"),
            {"pid": r5_person_id},
        ).first()
    assert exists is not None
