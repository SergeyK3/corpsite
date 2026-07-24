# tests/ppr/test_r5_external_employment_write_path.py
"""R5 application write-path tests for PPR-EMPLOYMENT-BIOGRAPHY (WP-PR-014)."""
from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_migration import (
    EXTERNAL_EMPLOYMENT_RECORD_KIND_ATTESTATION_NONE,
    EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
    EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY,
)
from app.db.models.personnel_verification import CONTROL_POINT_EMPLOYMENT_EPISODE
from app.personnel_verification.infrastructure.repository import PersonnelVerificationRepository
from app.ppr.application.authorization import AllowAllAuthorizationPort
from app.ppr.application.command_models import (
    COMMAND_TYPE_ACTIVATE_PPR,
    COMMAND_TYPE_ADD_EXTERNAL_EMPLOYMENT,
    COMMAND_TYPE_MATERIALIZE_PPR,
    COMMAND_TYPE_SUPERSEDE_EXTERNAL_EMPLOYMENT,
    COMMAND_TYPE_VOID_EXTERNAL_EMPLOYMENT,
    PprCommandEnvelope,
)
from app.ppr.application.lifecycle_service import PprLifecycleApplicationService
from app.ppr.application.results import RESULT_STATUS_COMMITTED, RESULT_STATUS_IDEMPOTENT_REPLAY
from app.ppr.application.section_service import PprSectionApplicationService
from app.ppr.domain.errors import (
    SectionOptimisticConcurrencyConflictError,
    SectionRecordNotFoundError,
    SectionValidationError,
)
from app.ppr.infrastructure.ppr_event_repository import SqlAlchemyPprEventRepository
from tests.conftest import table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_person, ppr_db_available, require_ppr_schema


def _require_r5_schema() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "ppr_command_executions"):
            pytest.skip("ppr_command_executions missing — run: alembic upgrade head")
        if not table_exists(conn, "person_external_employment"):
            pytest.skip("person_external_employment missing — run: alembic upgrade head")
        if not table_exists(conn, "verification_policies"):
            pytest.skip("verification_policies missing — run: alembic upgrade head")


def _ensure_employment_policy(*, user_id: int) -> None:
    """Publish active employment_episode policy required by WP-VER-005A supersede."""
    with engine.begin() as conn:
        repo = PersonnelVerificationRepository(conn)
        active = repo.get_active_policy(CONTROL_POINT_EMPLOYMENT_EPISODE)
        if active is not None:
            return
        draft = repo.create_policy_draft(
            control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
            effective_from=date(2026, 1, 1),
            decision_basis=f"WP-VER-005A test policy {uuid4().hex[:8]}",
            created_by_user_id=user_id,
        )
        repo.publish_policy(policy_id=draft.policy_id, published_by_user_id=user_id)


@pytest.fixture
def employment_person_id():
    require_ppr_schema()
    _require_r5_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"PPR Employment R5 {suffix}")
    yield person_id
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])


@pytest.fixture
def other_person_id():
    require_ppr_schema()
    _require_r5_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"PPR Employment Other {suffix}")
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


def _add_episode_envelope(
    person_id: int,
    *,
    command_id: str | None = None,
) -> PprCommandEnvelope:
    return PprCommandEnvelope(
        command_id=command_id or f"emp-{uuid4().hex}",
        command_type=COMMAND_TYPE_ADD_EXTERNAL_EMPLOYMENT,
        actor_id="test-actor",
        requested_at=datetime.now(UTC),
        payload={
            "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
            "employer_name": "ТОО «Внешний работодатель»",
            "position_title": "Инженер",
            "started_at": date(2018, 1, 1),
        },
        person_id=person_id,
    )


def _load_employment_row(record_id: int) -> tuple[int, datetime, str]:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT employment_id, updated_at, lifecycle_status
                FROM public.person_external_employment
                WHERE employment_id = :rid
                """
            ),
            {"rid": record_id},
        ).one()
    return int(row[0]), row[1], str(row[2])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_create_episode_commits_with_canonical_event(
    employment_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(employment_person_id, lifecycle_service)
    result = section_service.add_external_employment(_add_episode_envelope(employment_person_id))
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
        row_count = conn.execute(
            text("SELECT COUNT(*) FROM public.person_external_employment WHERE person_id = :pid"),
            {"pid": employment_person_id},
        ).scalar_one()

    assert event[0] == "PPR_SECTION_ADDED"
    assert event[1] == "person_external_employment"
    assert event[2] == "PPR-EMPLOYMENT-BIOGRAPHY"
    assert int(row_count) == 1


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_create_narrative_summary_commits_with_canonical_event(
    employment_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(employment_person_id, lifecycle_service)
    result = section_service.add_external_employment(
        PprCommandEnvelope(
            command_id=f"nar-{uuid4().hex}",
            command_type=COMMAND_TYPE_ADD_EXTERNAL_EMPLOYMENT,
            actor_id="test-actor",
            requested_at=datetime.now(UTC),
            payload={
                "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY,
                "notes": "Сводный стаж 22 года 3 месяца",
            },
            person_id=employment_person_id,
        )
    )
    assert result.status == RESULT_STATUS_COMMITTED

    with engine.begin() as conn:
        notes = conn.execute(
            text("SELECT notes FROM public.person_external_employment WHERE employment_id = :rid"),
            {"rid": result.section_record_id},
        ).scalar_one()
        event_type = conn.execute(
            text("SELECT event_type FROM public.personnel_record_events WHERE event_id = :eid"),
            {"eid": result.event_ids[0]},
        ).scalar_one()

    assert notes == "Сводный стаж 22 года 3 месяца"
    assert event_type == "PPR_SECTION_ADDED"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_create_attestation_none_commits_with_canonical_event(
    employment_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(employment_person_id, lifecycle_service)
    result = section_service.add_external_employment(
        PprCommandEnvelope(
            command_id=f"att-{uuid4().hex}",
            command_type=COMMAND_TYPE_ADD_EXTERNAL_EMPLOYMENT,
            actor_id="test-actor",
            requested_at=datetime.now(UTC),
            payload={
                "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_ATTESTATION_NONE,
                "notes": "Стаж отсутствует",
            },
            person_id=employment_person_id,
        )
    )
    assert result.status == RESULT_STATUS_COMMITTED

    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT record_kind, employer_name, position_title, started_at, ended_at
                FROM public.person_external_employment
                WHERE employment_id = :rid
                """
            ),
            {"rid": result.section_record_id},
        ).one()

    assert row[0] == EXTERNAL_EMPLOYMENT_RECORD_KIND_ATTESTATION_NONE
    assert row[1] is None
    assert row[2] is None
    assert row[3] is None
    assert row[4] is None


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
@pytest.mark.parametrize(
    "payload,match",
    [
        (
            {
                "record_kind": "unknown_kind",
                "employer_name": "X",
                "position_title": "Y",
                "started_at": date(2020, 1, 1),
            },
            "record_kind must be one of",
        ),
        (
            {
                "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
                "position_title": "Role",
                "started_at": date(2020, 1, 1),
            },
            "employer_name is required",
        ),
        (
            {
                "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY,
            },
            "notes is required",
        ),
        (
            {
                "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_ATTESTATION_NONE,
                "notes": "Стаж отсутствует",
                "employer_name": "Should not be set",
            },
            "attestation_none must not include employer_name",
        ),
    ],
)
def test_invalid_command_validation_is_atomic(
    employment_person_id: int,
    lifecycle_service,
    section_service,
    payload: dict,
    match: str,
) -> None:
    _materialize_and_activate(employment_person_id, lifecycle_service)
    with pytest.raises(SectionValidationError, match=match):
        section_service.add_external_employment(
            PprCommandEnvelope(
                command_id=f"invalid-{uuid4().hex}",
                command_type=COMMAND_TYPE_ADD_EXTERNAL_EMPLOYMENT,
                actor_id="test-actor",
                requested_at=datetime.now(UTC),
                payload=payload,
                person_id=employment_person_id,
            )
        )

    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT COUNT(*) FROM public.person_external_employment WHERE person_id = :pid"),
            {"pid": employment_person_id},
        ).scalar_one()
        events = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.personnel_record_events
                WHERE person_id = :pid AND record_table_name = 'person_external_employment'
                """
            ),
            {"pid": employment_person_id},
        ).scalar_one()
        cmds = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.ppr_command_executions
                WHERE person_id = :pid AND command_type = :op
                """
            ),
            {"pid": employment_person_id, "op": COMMAND_TYPE_ADD_EXTERNAL_EMPLOYMENT},
        ).scalar_one()

    assert int(rows) == 0
    assert int(events) == 0
    assert int(cmds) == 0


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
@pytest.mark.parametrize(
    "forbidden_field,forbidden_value",
    [
        ("record_id", 999),
        ("lifecycle_status", "voided"),
        ("verification_status", "verified"),
        ("created_at", datetime.now(UTC)),
        ("updated_at", datetime.now(UTC)),
    ],
)
def test_add_rejects_forbidden_payload_fields(
    employment_person_id: int,
    lifecycle_service,
    section_service,
    forbidden_field: str,
    forbidden_value,
) -> None:
    _materialize_and_activate(employment_person_id, lifecycle_service)
    payload = {
        "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
        "employer_name": "ТОО «Внешний работодатель»",
        "position_title": "Инженер",
        "started_at": date(2018, 1, 1),
        forbidden_field: forbidden_value,
    }
    with pytest.raises(TypeError):
        section_service.add_external_employment(
            PprCommandEnvelope(
                command_id=f"emp-forbidden-{uuid4().hex}",
                command_type=COMMAND_TYPE_ADD_EXTERNAL_EMPLOYMENT,
                actor_id="test-actor",
                requested_at=datetime.now(UTC),
                payload=payload,
                person_id=employment_person_id,
            )
        )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_void_stale_expected_updated_at_raises_and_rolls_back(
    employment_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(employment_person_id, lifecycle_service)
    added = section_service.add_external_employment(_add_episode_envelope(employment_person_id))
    assert added.section_record_id is not None
    _, updated_at, original_status = _load_employment_row(added.section_record_id)

    with engine.begin() as conn:
        events_before = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.personnel_record_events
                WHERE person_id = :pid AND record_table_name = 'person_external_employment'
                """
            ),
            {"pid": employment_person_id},
        ).scalar_one()

    with pytest.raises(SectionOptimisticConcurrencyConflictError):
        section_service.void_external_employment(
            PprCommandEnvelope(
                command_id=f"emp-void-stale-{uuid4().hex}",
                command_type=COMMAND_TYPE_VOID_EXTERNAL_EMPLOYMENT,
                actor_id="test-actor",
                requested_at=datetime.now(UTC),
                payload={
                    "record_id": added.section_record_id,
                    "reason": "should fail",
                    "expected_updated_at": updated_at.replace(year=2000),
                },
                person_id=employment_person_id,
            )
        )

    _, _, current_status = _load_employment_row(added.section_record_id)
    with engine.begin() as conn:
        events_after = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.personnel_record_events
                WHERE person_id = :pid AND record_table_name = 'person_external_employment'
                """
            ),
            {"pid": employment_person_id},
        ).scalar_one()
        cmds = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.ppr_command_executions
                WHERE person_id = :pid AND command_type = :op
                """
            ),
            {"pid": employment_person_id, "op": COMMAND_TYPE_VOID_EXTERNAL_EMPLOYMENT},
        ).scalar_one()

    assert current_status == original_status
    assert int(events_after) == int(events_before)
    assert int(cmds) == 0


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_supersede_stale_expected_updated_at_raises_and_rolls_back(
    employment_person_id: int,
    lifecycle_service,
    section_service,
    seed,
) -> None:
    _ensure_employment_policy(user_id=int(seed["initiator_user_id"]))
    _materialize_and_activate(employment_person_id, lifecycle_service)
    added = section_service.add_external_employment(_add_episode_envelope(employment_person_id))
    assert added.section_record_id is not None
    _, updated_at, original_status = _load_employment_row(added.section_record_id)

    with engine.begin() as conn:
        rows_before = conn.execute(
            text("SELECT COUNT(*) FROM public.person_external_employment WHERE person_id = :pid"),
            {"pid": employment_person_id},
        ).scalar_one()

    with pytest.raises(SectionOptimisticConcurrencyConflictError):
        section_service.supersede_external_employment(
            PprCommandEnvelope(
                command_id=f"emp-sup-stale-{uuid4().hex}",
                command_type=COMMAND_TYPE_SUPERSEDE_EXTERNAL_EMPLOYMENT,
                actor_id="test-actor",
                requested_at=datetime.now(UTC),
                payload={
                    "record_id": added.section_record_id,
                    "expected_updated_at": updated_at.replace(year=2000),
                    "replacement": {
                        "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
                        "employer_name": "Should Not Persist",
                        "position_title": "Role",
                        "started_at": date(2020, 1, 1),
                    },
                },
                person_id=employment_person_id,
            )
        )

    _, _, current_status = _load_employment_row(added.section_record_id)
    with engine.begin() as conn:
        rows_after = conn.execute(
            text("SELECT COUNT(*) FROM public.person_external_employment WHERE person_id = :pid"),
            {"pid": employment_person_id},
        ).scalar_one()
        cmds = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.ppr_command_executions
                WHERE person_id = :pid AND command_type = :op
                """
            ),
            {"pid": employment_person_id, "op": COMMAND_TYPE_SUPERSEDE_EXTERNAL_EMPLOYMENT},
        ).scalar_one()

    assert current_status == original_status
    assert int(rows_after) == int(rows_before)
    assert int(cmds) == 0


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_add_external_employment_idempotent_replay(
    employment_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(employment_person_id, lifecycle_service)
    command_id = f"emp-replay-{uuid4().hex}"
    env = _add_episode_envelope(employment_person_id, command_id=command_id)
    first = section_service.add_external_employment(env)
    second = section_service.add_external_employment(env)
    assert first.status == RESULT_STATUS_COMMITTED
    assert second.status == RESULT_STATUS_IDEMPOTENT_REPLAY

    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT COUNT(*) FROM public.person_external_employment WHERE person_id = :pid"),
            {"pid": employment_person_id},
        ).scalar_one()
        events = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.personnel_record_events
                WHERE person_id = :pid AND event_type = 'PPR_SECTION_ADDED'
                  AND record_table_name = 'person_external_employment'
                """
            ),
            {"pid": employment_person_id},
        ).scalar_one()

    assert int(rows) == 1
    assert int(events) == 1


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_supersede_active_record_commits_with_canonical_event(
    employment_person_id: int,
    lifecycle_service,
    section_service,
    seed,
) -> None:
    _ensure_employment_policy(user_id=int(seed["initiator_user_id"]))
    _materialize_and_activate(employment_person_id, lifecycle_service)
    added = section_service.add_external_employment(_add_episode_envelope(employment_person_id))
    assert added.section_record_id is not None
    _, updated_at, _ = _load_employment_row(added.section_record_id)

    result = section_service.supersede_external_employment(
        PprCommandEnvelope(
            command_id=f"emp-supersede-{uuid4().hex}",
            command_type=COMMAND_TYPE_SUPERSEDE_EXTERNAL_EMPLOYMENT,
            actor_id="test-actor",
            requested_at=datetime.now(UTC),
            payload={
                "record_id": added.section_record_id,
                "expected_updated_at": updated_at,
                "replacement": {
                    "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
                    "employer_name": "ТОО «Новый работодатель»",
                    "position_title": "Старший инженер",
                    "started_at": date(2019, 6, 1),
                },
            },
            person_id=employment_person_id,
        )
    )
    assert result.status == RESULT_STATUS_COMMITTED
    assert result.section_record_id != added.section_record_id

    with engine.begin() as conn:
        event = conn.execute(
            text(
                """
                SELECT person_id,
                       record_table_name,
                       record_id,
                       event_type,
                       event_payload->>'person_id' AS payload_person_id,
                       event_payload->>'section_code' AS section_code,
                       event_payload->>'record_id' AS payload_record_id,
                       event_payload->>'prior_record_id' AS prior_record_id
                FROM public.personnel_record_events
                WHERE event_id = :eid
                """
            ),
            {"eid": result.event_ids[0]},
        ).one()
        old_status = conn.execute(
            text(
                "SELECT lifecycle_status FROM public.person_external_employment WHERE employment_id = :rid"
            ),
            {"rid": added.section_record_id},
        ).scalar_one()
        task_count = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.verification_tasks
                WHERE object_version_id = :revision_id AND status = 'pending'
                """
            ),
            {"revision_id": result.section_record_id},
        ).scalar_one()

    assert event[3] == "PPR_SECTION_SUPERSEDED"
    assert int(event[0]) == employment_person_id
    assert event[1] == "person_external_employment"
    assert int(event[2]) == result.section_record_id
    assert int(event[4]) == employment_person_id
    assert event[5] == "PPR-EMPLOYMENT-BIOGRAPHY"
    assert int(event[6]) == result.section_record_id
    assert int(event[7]) == added.section_record_id
    # WP-VER-005A: prior stays active until confirm; revision is pending.
    assert old_status == "active"
    assert int(task_count) == 1


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_supersede_idempotent_replay(
    employment_person_id: int,
    lifecycle_service,
    section_service,
    seed,
) -> None:
    _ensure_employment_policy(user_id=int(seed["initiator_user_id"]))
    _materialize_and_activate(employment_person_id, lifecycle_service)
    added = section_service.add_external_employment(_add_episode_envelope(employment_person_id))
    assert added.section_record_id is not None
    _, updated_at, _ = _load_employment_row(added.section_record_id)

    command_id = f"emp-sup-replay-{uuid4().hex}"
    env = PprCommandEnvelope(
        command_id=command_id,
        command_type=COMMAND_TYPE_SUPERSEDE_EXTERNAL_EMPLOYMENT,
        actor_id="test-actor",
        requested_at=datetime.now(UTC),
        payload={
            "record_id": added.section_record_id,
            "expected_updated_at": updated_at,
            "replacement": {
                "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
                "employer_name": "Replacement Employer",
                "position_title": "Lead",
                "started_at": date(2021, 1, 1),
            },
        },
        person_id=employment_person_id,
    )
    first = section_service.supersede_external_employment(env)
    second = section_service.supersede_external_employment(env)
    assert first.status == RESULT_STATUS_COMMITTED
    assert second.status == RESULT_STATUS_IDEMPOTENT_REPLAY

    with engine.begin() as conn:
        active_count = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.person_external_employment
                WHERE person_id = :pid AND lifecycle_status = 'active'
                """
            ),
            {"pid": employment_person_id},
        ).scalar_one()
        supersede_events = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.personnel_record_events
                WHERE person_id = :pid AND event_type = 'PPR_SECTION_SUPERSEDED'
                  AND record_table_name = 'person_external_employment'
                """
            ),
            {"pid": employment_person_id},
        ).scalar_one()

    # Prior + pending revision both lifecycle=active until confirm.
    assert int(active_count) == 2
    assert int(supersede_events) == 1


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_supersede_foreign_person_record_rejected(
    employment_person_id: int,
    other_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(employment_person_id, lifecycle_service)
    _materialize_and_activate(other_person_id, lifecycle_service)
    added = section_service.add_external_employment(_add_episode_envelope(employment_person_id))
    assert added.section_record_id is not None
    _, updated_at, _ = _load_employment_row(added.section_record_id)

    with pytest.raises(SectionRecordNotFoundError):
        section_service.supersede_external_employment(
            PprCommandEnvelope(
                command_id=f"emp-foreign-{uuid4().hex}",
                command_type=COMMAND_TYPE_SUPERSEDE_EXTERNAL_EMPLOYMENT,
                actor_id="test-actor",
                requested_at=datetime.now(UTC),
                payload={
                    "record_id": added.section_record_id,
                    "expected_updated_at": updated_at,
                    "replacement": {
                        "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
                        "employer_name": "Foreign attempt",
                        "position_title": "Role",
                        "started_at": date(2020, 1, 1),
                    },
                },
                person_id=other_person_id,
            )
        )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_supersede_non_active_record_rejected(
    employment_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(employment_person_id, lifecycle_service)
    added = section_service.add_external_employment(_add_episode_envelope(employment_person_id))
    assert added.section_record_id is not None
    _, updated_at, _ = _load_employment_row(added.section_record_id)

    section_service.void_external_employment(
        PprCommandEnvelope(
            command_id=f"emp-void-for-sup-{uuid4().hex}",
            command_type=COMMAND_TYPE_VOID_EXTERNAL_EMPLOYMENT,
            actor_id="test-actor",
            requested_at=datetime.now(UTC),
            payload={
                "record_id": added.section_record_id,
                "reason": "prepare supersede rejection",
                "expected_updated_at": updated_at,
            },
            person_id=employment_person_id,
        )
    )

    with pytest.raises(SectionValidationError, match="is not active"):
        section_service.supersede_external_employment(
            PprCommandEnvelope(
                command_id=f"emp-sup-inactive-{uuid4().hex}",
                command_type=COMMAND_TYPE_SUPERSEDE_EXTERNAL_EMPLOYMENT,
                actor_id="test-actor",
                requested_at=datetime.now(UTC),
                payload={
                    "record_id": added.section_record_id,
                    "expected_updated_at": updated_at,
                    "replacement": {
                        "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
                        "employer_name": "Should fail",
                        "position_title": "Role",
                        "started_at": date(2020, 1, 1),
                    },
                },
                person_id=employment_person_id,
            )
        )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_void_active_record_commits_with_canonical_event(
    employment_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(employment_person_id, lifecycle_service)
    added = section_service.add_external_employment(_add_episode_envelope(employment_person_id))
    assert added.section_record_id is not None
    _, updated_at, _ = _load_employment_row(added.section_record_id)

    result = section_service.void_external_employment(
        PprCommandEnvelope(
            command_id=f"emp-void-{uuid4().hex}",
            command_type=COMMAND_TYPE_VOID_EXTERNAL_EMPLOYMENT,
            actor_id="test-actor",
            requested_at=datetime.now(UTC),
            payload={
                "record_id": added.section_record_id,
                "reason": "correction",
                "expected_updated_at": updated_at,
            },
            person_id=employment_person_id,
        )
    )
    assert result.status == RESULT_STATUS_COMMITTED

    with engine.begin() as conn:
        event_type = conn.execute(
            text("SELECT event_type FROM public.personnel_record_events WHERE event_id = :eid"),
            {"eid": result.event_ids[0]},
        ).scalar_one()
        lifecycle_status = conn.execute(
            text(
                "SELECT lifecycle_status FROM public.person_external_employment WHERE employment_id = :rid"
            ),
            {"rid": added.section_record_id},
        ).scalar_one()

    assert event_type == "PPR_SECTION_VOIDED"
    assert lifecycle_status == "voided"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_repeated_void_idempotent_replay_and_rejects_new_command(
    employment_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(employment_person_id, lifecycle_service)
    added = section_service.add_external_employment(_add_episode_envelope(employment_person_id))
    assert added.section_record_id is not None
    _, updated_at, _ = _load_employment_row(added.section_record_id)

    command_id = f"emp-void-replay-{uuid4().hex}"
    void_env = PprCommandEnvelope(
        command_id=command_id,
        command_type=COMMAND_TYPE_VOID_EXTERNAL_EMPLOYMENT,
        actor_id="test-actor",
        requested_at=datetime.now(UTC),
        payload={
            "record_id": added.section_record_id,
            "reason": "correction",
            "expected_updated_at": updated_at,
        },
        person_id=employment_person_id,
    )
    first = section_service.void_external_employment(void_env)
    replay = section_service.void_external_employment(void_env)
    assert first.status == RESULT_STATUS_COMMITTED
    assert replay.status == RESULT_STATUS_IDEMPOTENT_REPLAY

    with pytest.raises(SectionValidationError, match="is not active"):
        section_service.void_external_employment(
            PprCommandEnvelope(
                command_id=f"emp-void-again-{uuid4().hex}",
                command_type=COMMAND_TYPE_VOID_EXTERNAL_EMPLOYMENT,
                actor_id="test-actor",
                requested_at=datetime.now(UTC),
                payload={
                    "record_id": added.section_record_id,
                    "reason": "second void",
                    "expected_updated_at": updated_at,
                },
                person_id=employment_person_id,
            )
        )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_add_external_employment_rolls_back_when_event_append_fails(
    employment_person_id: int,
    lifecycle_service,
    section_service,
    monkeypatch,
) -> None:
    _materialize_and_activate(employment_person_id, lifecycle_service)

    def _failing_append(self, request):
        del self, request
        raise RuntimeError("event append failed")

    monkeypatch.setattr(SqlAlchemyPprEventRepository, "append", _failing_append)

    with pytest.raises(RuntimeError, match="event append failed"):
        section_service.add_external_employment(_add_episode_envelope(employment_person_id))

    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT COUNT(*) FROM public.person_external_employment WHERE person_id = :pid"),
            {"pid": employment_person_id},
        ).scalar_one()
        events = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.personnel_record_events
                WHERE person_id = :pid AND record_table_name = 'person_external_employment'
                """
            ),
            {"pid": employment_person_id},
        ).scalar_one()
        cmds = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.ppr_command_executions
                WHERE person_id = :pid AND command_type = :op
                """
            ),
            {"pid": employment_person_id, "op": COMMAND_TYPE_ADD_EXTERNAL_EMPLOYMENT},
        ).scalar_one()

    assert int(rows) == 0
    assert int(events) == 0
    assert int(cmds) == 0


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_create_with_employee_context_id_audit_field(
    employment_person_id: int,
    lifecycle_service,
    section_service,
) -> None:
    _materialize_and_activate(employment_person_id, lifecycle_service)
    result = section_service.add_external_employment(
        PprCommandEnvelope(
            command_id=f"emp-ctx-{uuid4().hex}",
            command_type=COMMAND_TYPE_ADD_EXTERNAL_EMPLOYMENT,
            actor_id="test-actor",
            requested_at=datetime.now(UTC),
            payload={
                "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
                "employer_name": "ТОО «Внешний работодатель»",
                "position_title": "Инженер",
                "started_at": date(2018, 1, 1),
                "employee_context_id": 42_001,
            },
            person_id=employment_person_id,
        )
    )
    assert result.status == RESULT_STATUS_COMMITTED

    with engine.begin() as conn:
        employee_context_id = conn.execute(
            text(
                """
                SELECT employee_context_id
                FROM public.person_external_employment
                WHERE employment_id = :rid
                """
            ),
            {"rid": result.section_record_id},
        ).scalar_one()

    assert employee_context_id == 42_001
