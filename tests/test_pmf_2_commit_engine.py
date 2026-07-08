# tests/test_pmf_2_commit_engine.py
"""Service integration tests for PMF-2 Commit Engine."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_migration import (
    DOMAIN_CODE_EDUCATION,
    EDUCATION_KIND_BASIC,
    EVENT_TYPE_EDUCATION_MIGRATED,
    EVENT_TYPE_EDUCATION_SUPERSEDED,
    EVENT_TYPE_EDUCATION_VOIDED,
    ITEM_STATUS_COMMITTED,
    ITEM_STATUS_DRAFT,
    ITEM_STATUS_VOIDED,
    LIFECYCLE_STATUS_ACTIVE,
    LIFECYCLE_STATUS_SUPERSEDED,
    LIFECYCLE_STATUS_VOIDED,
    RUN_STATUS_COMMITTED,
    RUN_STATUS_DRAFT,
    RUN_STATUS_VOIDED,
    TRAINING_KIND_COURSE,
)
from app.services.education_migration_plugin import RECORD_KIND_EDUCATION, RECORD_KIND_TRAINING
from app.services.personnel_migration_commit_service import (
    add_draft_item_tx,
    commit_run_tx,
    create_draft_run_tx,
    supersede_record_tx,
    void_run_tx,
)
from app.services.personnel_migration_types import (
    PersonnelMigrationConflictError,
    PersonnelMigrationValidationError,
)
from tests.conftest import get_columns, insert_returning_id, table_exists
from tests.test_pmf_1_schema import FORBIDDEN_TABLES, PMF_TABLES, _require_schema

ACTOR_ID = "pmf-test-actor"


def _insert_person(conn, *, full_name: str) -> int:
    suffix = uuid4().hex[:12]
    match_key = f"pmf2-test:{suffix}"
    cols = get_columns(conn, "persons")
    values: dict[str, Any] = {"full_name": full_name}
    if "match_key" in cols:
        values["match_key"] = match_key
    if "source" in cols:
        values["source"] = "manual"
    if "person_status" in cols:
        values["person_status"] = "active"
    return insert_returning_id(
        conn,
        table="persons",
        id_col="person_id",
        values=values,
    )


def _insert_employee(
    conn,
    *,
    full_name: str,
    person_id: int | None = None,
) -> int:
    values: dict[str, Any] = {"full_name": full_name, "is_active": True}
    cols = get_columns(conn, "employees")
    if "employment_rate" in cols:
        values["employment_rate"] = 1.00
    if person_id is not None and "person_id" in cols:
        values["person_id"] = person_id
    return insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values=values,
    )


def _count_rows(conn, table: str, where_sql: str, params: dict[str, Any]) -> int:
    return int(
        conn.execute(
            text(f"SELECT COUNT(*) FROM public.{table} WHERE {where_sql}"),
            params,
        ).scalar_one()
    )


@pytest.fixture
def pmf_employee_with_person():
    _require_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = _insert_person(conn, full_name=f"PMF2 Person {suffix}")
        employee_id = _insert_employee(
            conn,
            full_name=f"PMF2 Employee {suffix}",
            person_id=person_id,
        )
    yield {"person_id": person_id, "employee_id": employee_id}
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                DELETE FROM public.personnel_record_events
                WHERE person_id = :person_id
                """
            ),
            {"person_id": person_id},
        )
        conn.execute(
            text(
                """
                DELETE FROM public.personnel_migration_items
                WHERE run_id IN (
                    SELECT run_id FROM public.personnel_migration_runs
                    WHERE person_id = :person_id
                )
                """
            ),
            {"person_id": person_id},
        )
        conn.execute(
            text(
                "DELETE FROM public.personnel_migration_runs WHERE person_id = :person_id"
            ),
            {"person_id": person_id},
        )
        conn.execute(
            text("DELETE FROM public.person_education WHERE person_id = :person_id"),
            {"person_id": person_id},
        )
        conn.execute(
            text("DELETE FROM public.person_training WHERE person_id = :person_id"),
            {"person_id": person_id},
        )
        conn.execute(
            text("DELETE FROM public.employees WHERE employee_id = :employee_id"),
            {"employee_id": employee_id},
        )
        conn.execute(
            text("DELETE FROM public.persons WHERE person_id = :person_id"),
            {"person_id": person_id},
        )


@pytest.fixture
def pmf_employee_without_person():
    _require_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        employee_id = _insert_employee(conn, full_name=f"PMF2 Orphan {suffix}")
    yield {"employee_id": employee_id}
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.employees WHERE employee_id = :employee_id"),
            {"employee_id": employee_id},
        )


def test_create_draft_run_fails_without_person_id(pmf_employee_without_person) -> None:
    with pytest.raises(PersonnelMigrationValidationError, match="person_id"):
        create_draft_run_tx(
            domain_code=DOMAIN_CODE_EDUCATION,
            employee_context_id=pmf_employee_without_person["employee_id"],
            actor_id=ACTOR_ID,
            allow_disabled_domain=True,
        )


def test_create_draft_run_succeeds_with_person_id(pmf_employee_with_person) -> None:
    run = create_draft_run_tx(
        domain_code=DOMAIN_CODE_EDUCATION,
        employee_context_id=pmf_employee_with_person["employee_id"],
        actor_id=ACTOR_ID,
        allow_disabled_domain=True,
    )
    assert run["run_status"] == RUN_STATUS_DRAFT
    assert run["person_id"] == pmf_employee_with_person["person_id"]
    assert run["employee_context_id"] == pmf_employee_with_person["employee_id"]


def test_commit_education_item_creates_person_education(pmf_employee_with_person) -> None:
    run = create_draft_run_tx(
        domain_code=DOMAIN_CODE_EDUCATION,
        employee_context_id=pmf_employee_with_person["employee_id"],
        actor_id=ACTOR_ID,
        allow_disabled_domain=True,
    )
    add_draft_item_tx(
        run_id=int(run["run_id"]),
        source_kind="import_row_field",
        record_kind=RECORD_KIND_EDUCATION,
        draft_payload={
            "education_kind": EDUCATION_KIND_BASIC,
            "institution_name": "Test University",
            "specialty": "Medicine",
        },
    )
    result = commit_run_tx(run_id=int(run["run_id"]), actor_id=ACTOR_ID)

    education_id = result["committed_items"][0]["target_record_id"]
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT person_id, education_kind, institution_name, lifecycle_status
                FROM public.person_education
                WHERE education_id = :education_id
                """
            ),
            {"education_id": education_id},
        ).mappings().one()
    assert row["person_id"] == pmf_employee_with_person["person_id"]
    assert row["education_kind"] == EDUCATION_KIND_BASIC
    assert row["lifecycle_status"] == LIFECYCLE_STATUS_ACTIVE


def test_commit_training_item_creates_person_training(pmf_employee_with_person) -> None:
    run = create_draft_run_tx(
        domain_code=DOMAIN_CODE_EDUCATION,
        employee_context_id=pmf_employee_with_person["employee_id"],
        actor_id=ACTOR_ID,
        allow_disabled_domain=True,
    )
    add_draft_item_tx(
        run_id=int(run["run_id"]),
        source_kind="import_row_field",
        record_kind=RECORD_KIND_TRAINING,
        draft_payload={
            "training_kind": TRAINING_KIND_COURSE,
            "title": "Advanced PMF",
            "hours": 24,
        },
    )
    result = commit_run_tx(run_id=int(run["run_id"]), actor_id=ACTOR_ID)

    training_id = result["committed_items"][0]["target_record_id"]
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT person_id, training_kind, title, lifecycle_status
                FROM public.person_training
                WHERE training_id = :training_id
                """
            ),
            {"training_id": training_id},
        ).mappings().one()
    assert row["person_id"] == pmf_employee_with_person["person_id"]
    assert row["training_kind"] == TRAINING_KIND_COURSE
    assert row["lifecycle_status"] == LIFECYCLE_STATUS_ACTIVE


def test_commit_creates_personnel_record_events(pmf_employee_with_person) -> None:
    run = create_draft_run_tx(
        domain_code=DOMAIN_CODE_EDUCATION,
        employee_context_id=pmf_employee_with_person["employee_id"],
        actor_id=ACTOR_ID,
        allow_disabled_domain=True,
    )
    add_draft_item_tx(
        run_id=int(run["run_id"]),
        source_kind="manual",
        record_kind=RECORD_KIND_EDUCATION,
        draft_payload={"education_kind": EDUCATION_KIND_BASIC},
    )
    result = commit_run_tx(run_id=int(run["run_id"]), actor_id=ACTOR_ID)
    event_id = result["event_ids"][0]

    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT event_type, migration_run_id, migration_item_id
                FROM public.personnel_record_events
                WHERE event_id = :event_id
                """
            ),
            {"event_id": event_id},
        ).mappings().one()
    assert row["event_type"] == EVENT_TYPE_EDUCATION_MIGRATED
    assert row["migration_run_id"] == int(run["run_id"])


def test_commit_blocked_for_non_draft_run(pmf_employee_with_person) -> None:
    run = create_draft_run_tx(
        domain_code=DOMAIN_CODE_EDUCATION,
        employee_context_id=pmf_employee_with_person["employee_id"],
        actor_id=ACTOR_ID,
        allow_disabled_domain=True,
    )
    add_draft_item_tx(
        run_id=int(run["run_id"]),
        source_kind="manual",
        record_kind=RECORD_KIND_EDUCATION,
        draft_payload={"education_kind": EDUCATION_KIND_BASIC},
    )
    commit_run_tx(run_id=int(run["run_id"]), actor_id=ACTOR_ID)

    with pytest.raises(PersonnelMigrationConflictError, match="not draft"):
        commit_run_tx(run_id=int(run["run_id"]), actor_id=ACTOR_ID)


def test_void_run_requires_void_reason(pmf_employee_with_person) -> None:
    run = create_draft_run_tx(
        domain_code=DOMAIN_CODE_EDUCATION,
        employee_context_id=pmf_employee_with_person["employee_id"],
        actor_id=ACTOR_ID,
        allow_disabled_domain=True,
    )
    add_draft_item_tx(
        run_id=int(run["run_id"]),
        source_kind="manual",
        record_kind=RECORD_KIND_EDUCATION,
        draft_payload={"education_kind": EDUCATION_KIND_BASIC},
    )
    commit_run_tx(run_id=int(run["run_id"]), actor_id=ACTOR_ID)

    with pytest.raises(PersonnelMigrationValidationError, match="void_reason"):
        void_run_tx(run_id=int(run["run_id"]), actor_id=ACTOR_ID, void_reason="   ")


def test_void_run_sets_target_lifecycle_voided(pmf_employee_with_person) -> None:
    run = create_draft_run_tx(
        domain_code=DOMAIN_CODE_EDUCATION,
        employee_context_id=pmf_employee_with_person["employee_id"],
        actor_id=ACTOR_ID,
        allow_disabled_domain=True,
    )
    add_draft_item_tx(
        run_id=int(run["run_id"]),
        source_kind="manual",
        record_kind=RECORD_KIND_EDUCATION,
        draft_payload={"education_kind": EDUCATION_KIND_BASIC},
    )
    committed = commit_run_tx(run_id=int(run["run_id"]), actor_id=ACTOR_ID)
    education_id = committed["committed_items"][0]["target_record_id"]

    void_run_tx(
        run_id=int(run["run_id"]),
        actor_id=ACTOR_ID,
        void_reason="Test rollback",
    )

    with engine.begin() as conn:
        lifecycle = conn.execute(
            text(
                """
                SELECT lifecycle_status
                FROM public.person_education
                WHERE education_id = :education_id
                """
            ),
            {"education_id": education_id},
        ).scalar_one()
        run_status = conn.execute(
            text(
                "SELECT run_status FROM public.personnel_migration_runs WHERE run_id = :run_id"
            ),
            {"run_id": int(run["run_id"])},
        ).scalar_one()
        item_status = conn.execute(
            text(
                """
                SELECT item_status
                FROM public.personnel_migration_items
                WHERE run_id = :run_id
                """
            ),
            {"run_id": int(run["run_id"])},
        ).scalar_one()

    assert lifecycle == LIFECYCLE_STATUS_VOIDED
    assert run_status == RUN_STATUS_VOIDED
    assert item_status == ITEM_STATUS_VOIDED


def test_void_run_creates_education_voided_event(pmf_employee_with_person) -> None:
    run = create_draft_run_tx(
        domain_code=DOMAIN_CODE_EDUCATION,
        employee_context_id=pmf_employee_with_person["employee_id"],
        actor_id=ACTOR_ID,
        allow_disabled_domain=True,
    )
    add_draft_item_tx(
        run_id=int(run["run_id"]),
        source_kind="manual",
        record_kind=RECORD_KIND_EDUCATION,
        draft_payload={"education_kind": EDUCATION_KIND_BASIC},
    )
    commit_run_tx(run_id=int(run["run_id"]), actor_id=ACTOR_ID)

    result = void_run_tx(
        run_id=int(run["run_id"]),
        actor_id=ACTOR_ID,
        void_reason="Rollback test",
    )
    event_id = result["event_ids"][0]

    with engine.begin() as conn:
        event_type = conn.execute(
            text(
                "SELECT event_type FROM public.personnel_record_events WHERE event_id = :event_id"
            ),
            {"event_id": event_id},
        ).scalar_one()
    assert event_type == EVENT_TYPE_EDUCATION_VOIDED


def test_no_physical_delete_on_void(pmf_employee_with_person) -> None:
    run = create_draft_run_tx(
        domain_code=DOMAIN_CODE_EDUCATION,
        employee_context_id=pmf_employee_with_person["employee_id"],
        actor_id=ACTOR_ID,
        allow_disabled_domain=True,
    )
    add_draft_item_tx(
        run_id=int(run["run_id"]),
        source_kind="manual",
        record_kind=RECORD_KIND_EDUCATION,
        draft_payload={"education_kind": EDUCATION_KIND_BASIC},
    )
    committed = commit_run_tx(run_id=int(run["run_id"]), actor_id=ACTOR_ID)
    education_id = committed["committed_items"][0]["target_record_id"]

    void_run_tx(
        run_id=int(run["run_id"]),
        actor_id=ACTOR_ID,
        void_reason="No delete expected",
    )

    with engine.begin() as conn:
        count = _count_rows(
            conn,
            "person_education",
            "education_id = :education_id",
            {"education_id": education_id},
        )
    assert count == 1


def test_personnel_migration_events_table_not_used() -> None:
    _require_schema()
    with engine.begin() as conn:
        for table in FORBIDDEN_TABLES:
            assert not table_exists(conn, table)


def test_supersede_marks_old_superseded_and_creates_replacement(pmf_employee_with_person) -> None:
    run = create_draft_run_tx(
        domain_code=DOMAIN_CODE_EDUCATION,
        employee_context_id=pmf_employee_with_person["employee_id"],
        actor_id=ACTOR_ID,
        allow_disabled_domain=True,
    )
    add_draft_item_tx(
        run_id=int(run["run_id"]),
        source_kind="manual",
        record_kind=RECORD_KIND_EDUCATION,
        draft_payload={
            "education_kind": EDUCATION_KIND_BASIC,
            "institution_name": "Old University",
        },
    )
    committed = commit_run_tx(run_id=int(run["run_id"]), actor_id=ACTOR_ID)
    old_id = committed["committed_items"][0]["target_record_id"]

    result = supersede_record_tx(
        domain_code=DOMAIN_CODE_EDUCATION,
        employee_context_id=pmf_employee_with_person["employee_id"],
        record_table_name="person_education",
        record_id=old_id,
        replacement_payload={
            "education_kind": EDUCATION_KIND_BASIC,
            "institution_name": "New University",
        },
        actor_id=ACTOR_ID,
        allow_disabled_domain=True,
    )
    new_id = result["replacement_record_id"]

    with engine.begin() as conn:
        old_status = conn.execute(
            text(
                """
                SELECT lifecycle_status
                FROM public.person_education
                WHERE education_id = :education_id
                """
            ),
            {"education_id": old_id},
        ).scalar_one()
        new_row = conn.execute(
            text(
                """
                SELECT lifecycle_status, institution_name
                FROM public.person_education
                WHERE education_id = :education_id
                """
            ),
            {"education_id": new_id},
        ).mappings().one()
        event_types = conn.execute(
            text(
                """
                SELECT event_type
                FROM public.personnel_record_events
                WHERE person_id = :person_id
                ORDER BY event_id ASC
                """
            ),
            {"person_id": pmf_employee_with_person["person_id"]},
        ).scalars().all()

    assert old_status == LIFECYCLE_STATUS_SUPERSEDED
    assert new_row["lifecycle_status"] == LIFECYCLE_STATUS_ACTIVE
    assert new_row["institution_name"] == "New University"
    assert EVENT_TYPE_EDUCATION_MIGRATED in event_types
    assert EVENT_TYPE_EDUCATION_SUPERSEDED in event_types


def test_pmf_tables_exist_for_commit_engine() -> None:
    _require_schema()
    with engine.begin() as conn:
        assert all(table_exists(conn, table) for table in PMF_TABLES)


def test_draft_item_status_defaults_to_draft(pmf_employee_with_person) -> None:
    run = create_draft_run_tx(
        domain_code=DOMAIN_CODE_EDUCATION,
        employee_context_id=pmf_employee_with_person["employee_id"],
        actor_id=ACTOR_ID,
        allow_disabled_domain=True,
    )
    item = add_draft_item_tx(
        run_id=int(run["run_id"]),
        source_kind="manual",
        record_kind=RECORD_KIND_EDUCATION,
        draft_payload={"education_kind": EDUCATION_KIND_BASIC},
    )
    assert item["item_status"] == ITEM_STATUS_DRAFT

    with engine.begin() as conn:
        validation_errors = conn.execute(
            text(
                """
                SELECT validation_errors
                FROM public.personnel_migration_items
                WHERE item_id = :item_id
                """
            ),
            {"item_id": int(item["item_id"])},
        ).scalar_one()
    assert validation_errors == []


def test_committed_run_and_items_after_commit(pmf_employee_with_person) -> None:
    run = create_draft_run_tx(
        domain_code=DOMAIN_CODE_EDUCATION,
        employee_context_id=pmf_employee_with_person["employee_id"],
        actor_id=ACTOR_ID,
        allow_disabled_domain=True,
    )
    add_draft_item_tx(
        run_id=int(run["run_id"]),
        source_kind="manual",
        record_kind=RECORD_KIND_EDUCATION,
        draft_payload={"education_kind": EDUCATION_KIND_BASIC},
    )
    commit_run_tx(run_id=int(run["run_id"]), actor_id=ACTOR_ID)

    with engine.begin() as conn:
        run_status = conn.execute(
            text(
                "SELECT run_status FROM public.personnel_migration_runs WHERE run_id = :run_id"
            ),
            {"run_id": int(run["run_id"])},
        ).scalar_one()
        item_status = conn.execute(
            text(
                """
                SELECT item_status, target_table_name, target_record_id
                FROM public.personnel_migration_items
                WHERE run_id = :run_id
                """
            ),
            {"run_id": int(run["run_id"])},
        ).mappings().one()

    assert run_status == RUN_STATUS_COMMITTED
    assert item_status["item_status"] == ITEM_STATUS_COMMITTED
    assert item_status["target_table_name"] == "person_education"
    assert item_status["target_record_id"] is not None
