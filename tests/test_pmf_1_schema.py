# tests/test_pmf_1_schema.py
"""Schema tests for PMF-1 personnel migration framework foundation."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.db.engine import engine
from app.db.models.personnel_migration import (
    DOMAIN_CODE_EDUCATION,
    EDUCATION_KIND_BASIC,
    EVENT_TYPE_EDUCATION_MIGRATED,
    LIFECYCLE_STATUS_ACTIVE,
    RUN_STATUS_DRAFT,
    TRAINING_KIND_COURSE,
)
from tests.conftest import get_columns, insert_returning_id, table_exists

DDL_REVISION = "q1r2s3t4u5w6"
PREVIOUS_REVISION = "p0q1r2s3t4u5"

PMF_TABLES = (
    "personnel_migration_domains",
    "personnel_migration_runs",
    "personnel_migration_items",
    "personnel_record_events",
    "person_education",
    "person_training",
)

FORBIDDEN_TABLES = (
    "personnel_migration_events",
    "employee_education",
    "employee_training",
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _schema_available() -> bool:
    with engine.begin() as conn:
        return all(table_exists(conn, table) for table in PMF_TABLES)


def _alembic_config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", str(engine.url.render_as_string(hide_password=False)))
    return cfg


def _require_schema() -> None:
    if not _schema_available():
        pytest.skip(
            f"PMF-1 schema missing — run: alembic upgrade head (revision {DDL_REVISION})"
        )


def _insert_returning(conn, sql: str, params: dict[str, Any] | None = None) -> int:
    row = conn.execute(text(sql), params or {}).one()
    return int(row[0])


def _expect_sql_failure(sql: str, params: dict[str, Any] | None = None) -> None:
    with engine.begin() as conn:
        with pytest.raises(Exception):
            conn.execute(text(sql), params or {})


def _insert_person(conn, *, full_name: str) -> int:
    suffix = uuid4().hex[:12]
    match_key = f"pmf-test:{suffix}"
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


def _insert_employee(conn, *, full_name: str, person_id: int | None = None) -> int:
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


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_revision_chain() -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    rev = script.get_revision(DDL_REVISION)
    assert rev is not None
    assert rev.down_revision == PREVIOUS_REVISION


def test_pmf_tables_exist() -> None:
    _require_schema()


def test_forbidden_tables_not_created() -> None:
    if not _db_available():
        pytest.skip("PostgreSQL not available")
    with engine.begin() as conn:
        for table in FORBIDDEN_TABLES:
            assert not table_exists(conn, table), f"forbidden table exists: {table}"


def test_education_domain_seed() -> None:
    _require_schema()
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT domain_code, display_name, is_enabled,
                       target_table_names, control_list_columns
                FROM public.personnel_migration_domains
                WHERE domain_code = :domain_code
                """
            ),
            {"domain_code": DOMAIN_CODE_EDUCATION},
        ).mappings().one()

    assert row["display_name"] == "Образование"
    assert row["is_enabled"] is False
    assert row["target_table_names"] == ["person_education", "person_training"]
    assert row["control_list_columns"] == ["H", "I", "K", "M"]


def test_person_education_requires_person_id() -> None:
    _require_schema()
    _expect_sql_failure(
        """
        INSERT INTO public.person_education (
            person_id,
            education_kind
        )
        VALUES (
            :person_id,
            :education_kind
        )
        """,
        {"person_id": 999999999, "education_kind": EDUCATION_KIND_BASIC},
    )


def test_person_education_person_owned_roundtrip() -> None:
    _require_schema()

    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = _insert_person(conn, full_name=f"PMF Edu {suffix}")
        employee_id = _insert_employee(
            conn,
            full_name=f"PMF Emp {suffix}",
            person_id=person_id,
        )

        education_id = _insert_returning(
            conn,
            """
            INSERT INTO public.person_education (
                person_id,
                employee_context_id,
                education_kind,
                institution_name
            )
            VALUES (
                :person_id,
                :employee_context_id,
                :education_kind,
                :institution_name
            )
            RETURNING education_id
            """,
            {
                "person_id": person_id,
                "employee_context_id": employee_id,
                "education_kind": EDUCATION_KIND_BASIC,
                "institution_name": "Test University",
            },
        )

        training_id = _insert_returning(
            conn,
            """
            INSERT INTO public.person_training (
                person_id,
                training_kind,
                title
            )
            VALUES (
                :person_id,
                :training_kind,
                :title
            )
            RETURNING training_id
            """,
            {
                "person_id": person_id,
                "training_kind": TRAINING_KIND_COURSE,
                "title": "PMF test course",
            },
        )

        run_id = _insert_returning(
            conn,
            """
            INSERT INTO public.personnel_migration_runs (
                domain_code,
                employee_context_id,
                person_id,
                run_status
            )
            VALUES (
                :domain_code,
                :employee_context_id,
                :person_id,
                :run_status
            )
            RETURNING run_id
            """,
            {
                "domain_code": DOMAIN_CODE_EDUCATION,
                "employee_context_id": employee_id,
                "person_id": person_id,
                "run_status": RUN_STATUS_DRAFT,
            },
        )

        item_id = _insert_returning(
            conn,
            """
            INSERT INTO public.personnel_migration_items (
                run_id,
                domain_code,
                source_kind,
                target_table_name,
                target_record_id,
                item_status
            )
            VALUES (
                :run_id,
                :domain_code,
                :source_kind,
                :target_table_name,
                :target_record_id,
                :item_status
            )
            RETURNING item_id
            """,
            {
                "run_id": run_id,
                "domain_code": DOMAIN_CODE_EDUCATION,
                "source_kind": "import_row_field",
                "target_table_name": "person_education",
                "target_record_id": education_id,
                "item_status": "draft",
            },
        )

        event_id = _insert_returning(
            conn,
            """
            INSERT INTO public.personnel_record_events (
                person_id,
                employee_context_id,
                domain_code,
                record_table_name,
                record_id,
                event_type,
                migration_run_id,
                migration_item_id
            )
            VALUES (
                :person_id,
                :employee_context_id,
                :domain_code,
                :record_table_name,
                :record_id,
                :event_type,
                :migration_run_id,
                :migration_item_id
            )
            RETURNING event_id
            """,
            {
                "person_id": person_id,
                "employee_context_id": employee_id,
                "domain_code": DOMAIN_CODE_EDUCATION,
                "record_table_name": "person_education",
                "record_id": education_id,
                "event_type": EVENT_TYPE_EDUCATION_MIGRATED,
                "migration_run_id": run_id,
                "migration_item_id": item_id,
            },
        )

        assert education_id > 0
        assert training_id > 0
        assert run_id > 0
        assert item_id > 0
        assert event_id > 0

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
        assert lifecycle == LIFECYCLE_STATUS_ACTIVE

        conn.execute(
            text("DELETE FROM public.personnel_record_events WHERE event_id = :event_id"),
            {"event_id": event_id},
        )
        conn.execute(
            text("DELETE FROM public.personnel_migration_items WHERE item_id = :item_id"),
            {"item_id": item_id},
        )
        conn.execute(
            text("DELETE FROM public.personnel_migration_runs WHERE run_id = :run_id"),
            {"run_id": run_id},
        )
        conn.execute(
            text("DELETE FROM public.person_training WHERE training_id = :training_id"),
            {"training_id": training_id},
        )
        conn.execute(
            text("DELETE FROM public.person_education WHERE education_id = :education_id"),
            {"education_id": education_id},
        )
        conn.execute(
            text("DELETE FROM public.employees WHERE employee_id = :employee_id"),
            {"employee_id": employee_id},
        )
        conn.execute(
            text("DELETE FROM public.persons WHERE person_id = :person_id"),
            {"person_id": person_id},
        )


def test_person_education_rejects_invalid_lifecycle_status() -> None:
    _require_schema()

    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = _insert_person(conn, full_name=f"PMF Bad {suffix}")

    _expect_sql_failure(
        """
        INSERT INTO public.person_education (
            person_id,
            education_kind,
            lifecycle_status
        )
        VALUES (
            :person_id,
            :education_kind,
            :lifecycle_status
        )
        """,
        {
            "person_id": person_id,
            "education_kind": EDUCATION_KIND_BASIC,
            "lifecycle_status": "deleted",
        },
    )

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.persons WHERE person_id = :person_id"),
            {"person_id": person_id},
        )


def test_orm_models_map_to_tables() -> None:
    from app.db.models.personnel_migration import (
        PersonEducation,
        PersonnelMigrationDomain,
        PersonnelMigrationItem,
        PersonnelMigrationRun,
        PersonnelRecordEvent,
        PersonTraining,
    )

    assert PersonnelMigrationDomain.__tablename__ == "personnel_migration_domains"
    assert PersonnelMigrationRun.__tablename__ == "personnel_migration_runs"
    assert PersonnelMigrationItem.__tablename__ == "personnel_migration_items"
    assert PersonnelRecordEvent.__tablename__ == "personnel_record_events"
    assert PersonEducation.__tablename__ == "person_education"
    assert PersonTraining.__tablename__ == "person_training"
