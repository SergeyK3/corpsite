# tests/ppr/test_r6_composite_query.py
"""Integration and parity tests for PPR R6 composite query layer."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_migration import EDUCATION_KIND_BASIC, RELATIONSHIP_TYPE_MOTHER, TRAINING_KIND_COURSE
from app.ppr.application.authorization import AllowAllAuthorizationPort
from app.ppr.application.command_models import (
    COMMAND_TYPE_ADD_RELATIVE,
    COMMAND_TYPE_MATERIALIZE_PPR,
    MaterializePprPayload,
    PprCommandEnvelope,
)
from app.ppr.application.lifecycle_service import PprLifecycleApplicationService
from app.ppr.application.section_service import PprSectionApplicationService
from app.ppr.domain.errors import (
    PprEmployeeNotFoundError,
    PprPersonNotFoundError,
)
from app.ppr.domain.identity_models import INPUT_KIND_EMPLOYEE_ID, INPUT_KIND_PERSON_ID, RESULT_MERGE_REDIRECTED
from app.ppr.domain.models import HR_RELATIONSHIP_CANDIDATE, HR_RELATIONSHIP_EMPLOYED, PPR_LIFECYCLE_CREATED, PPR_LIFECYCLE_NOT_MATERIALIZED
from app.ppr.domain.section_models import EducationRecord, SECTION_CODE_PPR_EDUCATION, SECTION_CODE_PPR_FAMILY, SECTION_CODE_PPR_TRAINING
from app.ppr.infrastructure.section_repository import SqlAlchemySectionMutationRepository
from app.ppr.read import PprCompositeReadModel, PprQueryApplicationService
from app.ppr.read import models as read_models
from tests.conftest import table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_employee, insert_person, ppr_db_available, require_ppr_schema


def _require_r6_schema() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_record_metadata"):
            pytest.skip("personnel_record_metadata missing — run: alembic upgrade head")


@pytest.fixture
def query_service() -> PprQueryApplicationService:
    return PprQueryApplicationService()


@pytest.fixture
def lifecycle_service() -> PprLifecycleApplicationService:
    return PprLifecycleApplicationService(
        authorization=AllowAllAuthorizationPort(),
    )


@pytest.fixture
def section_service() -> PprSectionApplicationService:
    return PprSectionApplicationService(authorization=AllowAllAuthorizationPort())


def _materialize(person_id: int, lifecycle_service: PprLifecycleApplicationService) -> None:
    lifecycle_service.materialize_ppr(
        PprCommandEnvelope(
            command_id=f"mat-{uuid4().hex}",
            command_type=COMMAND_TYPE_MATERIALIZE_PPR,
            actor_id="r6-test",
            requested_at=datetime.now(UTC),
            payload=MaterializePprPayload(),
            person_id=person_id,
        )
    )


@pytest.fixture
def bare_person_id():
    require_ppr_schema()
    _require_r6_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"R6 Bare {suffix}")
    yield person_id
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])


@pytest.fixture
def materialized_person_id(bare_person_id: int, lifecycle_service: PprLifecycleApplicationService):
    _materialize(bare_person_id, lifecycle_service)
    return bare_person_id


@pytest.fixture
def employee_linked_person():
    require_ppr_schema()
    _require_r6_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"R6 Employee Person {suffix}")
        employee_id = insert_employee(conn, full_name=f"R6 Employee {suffix}", person_id=person_id)
    yield {"person_id": person_id, "employee_id": employee_id}
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[employee_id])


@pytest.fixture
def merge_survivor_chain():
    require_ppr_schema()
    _require_r6_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        survivor_id = insert_person(conn, full_name=f"R6 Survivor {suffix}")
        mid_id = insert_person(
            conn,
            full_name=f"R6 Mid {suffix}",
            person_status="merged",
            merged_into_person_id=survivor_id,
        )
        loser_id = insert_person(
            conn,
            full_name=f"R6 Loser {suffix}",
            person_status="merged",
            merged_into_person_id=mid_id,
        )
    yield {"survivor": survivor_id, "mid": mid_id, "loser": loser_id}
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[loser_id, mid_id, survivor_id], employee_ids=[])


def _insert_education(person_id: int, institution: str) -> int:
    with engine.begin() as conn:
        repo = SqlAlchemySectionMutationRepository(conn)
        record = repo.insert_record(
            EducationRecord(
                person_id=person_id,
                education_kind=EDUCATION_KIND_BASIC,
                institution_name=institution,
            )
        )
        return int(record.record_id or 0)


def _ensure_hr_context(person_id: int, hr_context: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO public.personnel_record_metadata (
                    person_id, ppr_lifecycle_state, hr_relationship_context, version
                )
                VALUES (:person_id, :state, :ctx, 1)
                ON CONFLICT (person_id) DO UPDATE
                SET hr_relationship_context = EXCLUDED.hr_relationship_context,
                    updated_at = now()
                """
            ),
            {"person_id": person_id, "state": PPR_LIFECYCLE_CREATED, "ctx": hr_context},
        )


def _add_relative(
    person_id: int,
    section_service: PprSectionApplicationService,
    *,
    full_name: str,
    relationship_type: str = RELATIONSHIP_TYPE_MOTHER,
) -> None:
    section_service.add_relative(
        PprCommandEnvelope(
            command_id=f"r6-family-{uuid4().hex}",
            command_type=COMMAND_TYPE_ADD_RELATIVE,
            actor_id="r6-test",
            requested_at=datetime.now(UTC),
            payload={
                "relationship_type": relationship_type,
                "full_name": full_name,
            },
            person_id=person_id,
        )
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_01_load_materialized(
    materialized_person_id: int,
    query_service: PprQueryApplicationService,
) -> None:
    composite = query_service.load_by_person_id(materialized_person_id)
    assert composite.materialized is True
    assert composite.lifecycle_state == PPR_LIFECYCLE_CREATED
    assert composite.person_id == materialized_person_id


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_02_load_not_materialized(
    bare_person_id: int,
    query_service: PprQueryApplicationService,
) -> None:
    composite = query_service.load_by_person_id(bare_person_id)
    assert composite.materialized is False
    assert composite.lifecycle_state == PPR_LIFECYCLE_NOT_MATERIALIZED
    assert composite.hr_relationship_context is None
    assert composite.general.full_name.startswith("R6 Bare")


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_03_load_by_employee(
    employee_linked_person: dict[str, int],
    query_service: PprQueryApplicationService,
) -> None:
    composite = query_service.load_by_employee_id(employee_linked_person["employee_id"])
    assert composite.person_id == employee_linked_person["person_id"]
    assert composite.employee_id == employee_linked_person["employee_id"]
    assert composite.identity_resolution.input_kind == INPUT_KIND_EMPLOYEE_ID


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_04_load_by_person(
    bare_person_id: int,
    query_service: PprQueryApplicationService,
) -> None:
    composite = query_service.load_by_person_id(bare_person_id)
    assert composite.person_id == bare_person_id
    assert composite.identity_resolution.input_kind == INPUT_KIND_PERSON_ID


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_05_merged_redirect(
    merge_survivor_chain: dict[str, int],
    query_service: PprQueryApplicationService,
) -> None:
    composite = query_service.load_by_person_id(merge_survivor_chain["loser"])
    assert composite.person_id == merge_survivor_chain["survivor"]
    assert composite.metadata.merge_redirected is True
    assert composite.identity_resolution.result_code == RESULT_MERGE_REDIRECTED


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_06_missing_employee(query_service: PprQueryApplicationService) -> None:
    with pytest.raises(PprEmployeeNotFoundError):
        query_service.load_by_employee_id(999_999_999)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_07_missing_person(query_service: PprQueryApplicationService) -> None:
    with pytest.raises(PprPersonNotFoundError):
        query_service.load_by_person_id(999_999_999)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_08_no_envelope_still_reads_sections(
    bare_person_id: int,
    query_service: PprQueryApplicationService,
) -> None:
    _insert_education(bare_person_id, "Legacy University")
    composite = query_service.load_by_person_id(bare_person_id)
    assert composite.materialized is False
    assert len(composite.education.active) == 1
    assert composite.education.active[0].institution_name == "Legacy University"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_09_education_aggregation(
    bare_person_id: int,
    query_service: PprQueryApplicationService,
) -> None:
    _insert_education(bare_person_id, "School A")
    _insert_education(bare_person_id, "School B")
    composite = query_service.load_by_person_id(bare_person_id)
    assert composite.education.section_code == SECTION_CODE_PPR_EDUCATION
    assert len(composite.education.active) == 2
    names = {record.institution_name for record in composite.education.active}
    assert names == {"School A", "School B"}


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_10_training_aggregation(
    bare_person_id: int,
    query_service: PprQueryApplicationService,
) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemySectionMutationRepository(conn)
        from app.ppr.domain.section_models import TrainingRecord

        repo.insert_record(
            TrainingRecord(
                person_id=bare_person_id,
                training_kind=TRAINING_KIND_COURSE,
                title="Safety Course",
            )
        )
    composite = query_service.load_by_person_id(bare_person_id)
    assert composite.training.section_code == SECTION_CODE_PPR_TRAINING
    assert len(composite.training.active) == 1
    assert composite.training.active[0].title == "Safety Course"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_11_empty_sections(
    bare_person_id: int,
    query_service: PprQueryApplicationService,
) -> None:
    composite = query_service.load_by_person_id(bare_person_id)
    assert composite.education.active == ()
    assert composite.training.active == ()
    assert composite.family.active == ()
    assert composite.education.superseded == ()
    assert composite.education.voided == ()


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_12_lifecycle_present(
    materialized_person_id: int,
    query_service: PprQueryApplicationService,
) -> None:
    composite = query_service.load_by_person_id(materialized_person_id)
    assert composite.materialized is True
    assert composite.lifecycle_state == PPR_LIFECYCLE_CREATED
    assert composite.envelope_version == 1
    assert composite.envelope_created_at is not None


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_13_lifecycle_absent(
    bare_person_id: int,
    query_service: PprQueryApplicationService,
) -> None:
    composite = query_service.load_by_person_id(bare_person_id)
    assert composite.materialized is False
    assert composite.lifecycle_state == PPR_LIFECYCLE_NOT_MATERIALIZED
    assert composite.envelope_version is None


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_14_events_summary(
    materialized_person_id: int,
    query_service: PprQueryApplicationService,
) -> None:
    composite = query_service.load_by_person_id(materialized_person_id)
    assert composite.events is not None
    assert composite.events.returned_count >= 1
    assert composite.events.recent[0].event_type == "PPR_CREATED"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_15_immutable_dto() -> None:
    dto_names = (
        "PprEnvelopeReadSlice",
        "PprSectionAggregation",
        "PprEventSummaryEntry",
        "PprEventSummary",
        "PprCompositeReadMetadata",
        "PprCompositeReadModel",
        "PprCompositeSummary",
    )
    for name in dto_names:
        obj = getattr(read_models, name)
        assert is_dataclass(obj)
        assert getattr(obj, "__dataclass_params__").frozen is True


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_15_immutable_composite_instance(
    bare_person_id: int,
    query_service: PprQueryApplicationService,
) -> None:
    composite: PprCompositeReadModel = query_service.load_by_person_id(bare_person_id)
    with pytest.raises(FrozenInstanceError):
        composite.materialized = True  # type: ignore[misc]


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_16_repository_isolation_no_query_import_in_repos() -> None:
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    infra_paths = list((repo_root / "app/ppr/infrastructure").rglob("*.py"))
    for path in infra_paths:
        content = path.read_text(encoding="utf-8")
        assert "app.ppr.read" not in content, f"{path.name} imports query layer"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_17_no_writes_from_query(
    bare_person_id: int,
    query_service: PprQueryApplicationService,
) -> None:
    query_service.load_by_person_id(bare_person_id)
    with engine.begin() as conn:
        meta_count = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.personnel_record_metadata
                WHERE person_id = :person_id
                """
            ),
            {"person_id": bare_person_id},
        ).scalar_one()
        event_count = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.personnel_record_events
                WHERE person_id = :person_id
                """
            ),
            {"person_id": bare_person_id},
        ).scalar_one()
    assert int(meta_count) == 0
    assert int(event_count) == 0


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_18_load_summary(
    employee_linked_person: dict[str, int],
    query_service: PprQueryApplicationService,
) -> None:
    summary = query_service.load_summary(person_id=employee_linked_person["person_id"])
    assert summary.person_id == employee_linked_person["person_id"]
    assert summary.full_name.startswith("R6 Employee Person")


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_19_load_identity(
    employee_linked_person: dict[str, int],
    query_service: PprQueryApplicationService,
) -> None:
    snapshot, resolution = query_service.load_identity(
        employee_id=employee_linked_person["employee_id"]
    )
    assert snapshot.person_id == employee_linked_person["person_id"]
    assert resolution.input_kind == INPUT_KIND_EMPLOYEE_ID


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_20_load_sections(
    bare_person_id: int,
    query_service: PprQueryApplicationService,
) -> None:
    _insert_education(bare_person_id, "Section API School")
    sections = query_service.load_sections(bare_person_id)
    assert SECTION_CODE_PPR_EDUCATION in sections
    assert SECTION_CODE_PPR_TRAINING in sections
    assert SECTION_CODE_PPR_FAMILY in sections
    assert len(sections[SECTION_CODE_PPR_EDUCATION].active) == 1


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_employee_without_envelope(
    employee_linked_person: dict[str, int],
    query_service: PprQueryApplicationService,
) -> None:
    composite = query_service.load_by_employee_id(employee_linked_person["employee_id"])
    assert composite.materialized is False
    assert composite.employee_id == employee_linked_person["employee_id"]
    assert composite.general.full_name.startswith("R6 Employee Person")


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_former_employee_without_envelope(
    query_service: PprQueryApplicationService,
) -> None:
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"R6 Former {suffix}")
        employee_id = insert_employee(
            conn,
            full_name=f"R6 Former Emp {suffix}",
            person_id=person_id,
            is_active=False,
            operational_status="terminated",
        )
    try:
        composite = query_service.load_by_employee_id(employee_id)
        assert composite.materialized is False
        assert composite.person_id == person_id
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[employee_id])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_21_family_aggregation_candidate(
    bare_person_id: int,
    lifecycle_service: PprLifecycleApplicationService,
    section_service: PprSectionApplicationService,
    query_service: PprQueryApplicationService,
) -> None:
    _materialize(bare_person_id, lifecycle_service)
    _ensure_hr_context(bare_person_id, HR_RELATIONSHIP_CANDIDATE)
    _add_relative(bare_person_id, section_service, full_name="Иванова Анна Петровна")

    composite = query_service.load_by_person_id(bare_person_id)
    assert composite.hr_relationship_context == HR_RELATIONSHIP_CANDIDATE
    assert composite.family.section_code == SECTION_CODE_PPR_FAMILY
    assert len(composite.family.active) == 1
    assert composite.family.active[0].full_name == "Иванова Анна Петровна"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_22_family_aggregation_employed(
    employee_linked_person: dict[str, int],
    lifecycle_service: PprLifecycleApplicationService,
    section_service: PprSectionApplicationService,
    query_service: PprQueryApplicationService,
) -> None:
    person_id = employee_linked_person["person_id"]
    _materialize(person_id, lifecycle_service)
    _ensure_hr_context(person_id, HR_RELATIONSHIP_EMPLOYED)
    _add_relative(person_id, section_service, full_name="Петров Сергей Иванович")

    composite = query_service.load_by_employee_id(employee_linked_person["employee_id"])
    assert composite.hr_relationship_context == HR_RELATIONSHIP_EMPLOYED
    assert composite.family.section_code == SECTION_CODE_PPR_FAMILY
    assert len(composite.family.active) == 1
    assert composite.family.active[0].full_name == "Петров Сергей Иванович"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_23_summary_family_active_count(
    bare_person_id: int,
    lifecycle_service: PprLifecycleApplicationService,
    section_service: PprSectionApplicationService,
    query_service: PprQueryApplicationService,
) -> None:
    _materialize(bare_person_id, lifecycle_service)
    _add_relative(bare_person_id, section_service, full_name="Сидорова Мария")
    summary = query_service.load_summary(person_id=bare_person_id)
    assert summary.family_active_count == 1
