# tests/test_wp_cl_003_mapping_profiles.py
"""Schema, vocabulary, and repository tests for ADR-057 / WP-CL-003 mapping profiles."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.control_list_import.domain.vocabulary import (
    PARSER_CODE_IDENTITY_IIN,
    PARSER_CODE_PERSON_FULL_NAME,
    PARSER_CODES,
    SEMANTIC_FIELD_PERSON_FULL_NAME,
    SEMANTIC_FIELD_PERSON_IIN,
    SEMANTIC_FIELDS,
    is_valid_parser_code,
    is_valid_semantic_field,
)
from app.control_list_import.infrastructure.mapping_profile_repository import (
    SqlAlchemyControlListMappingProfileRepository,
)
from app.db.engine import engine
from app.db.models.control_list_mapping import (
    EMPLOYMENT_MODE_PRIMARY,
    PERSONNEL_CATEGORY_DOCTOR,
    PROFILE_STATUS_ACTIVE,
    PROFILE_STATUS_ARCHIVED,
    PROFILE_STATUS_DRAFT,
    SHEET_PURPOSE_PERSONNEL_CONTROL_LIST,
)
from tests.conftest import get_columns, table_exists

REVISION_ID = "y4z5a6b7c8d9e0"
PREVIOUS_REVISION = "x3y4z5a6b7c8"

WP_CL_003_TABLES = (
    "control_list_mapping_profiles",
    "control_list_mapping_profile_sheets",
    "control_list_mapping_profile_columns",
)

EXPECTED_INDEXES = (
    "uq_control_list_mapping_profiles_active_code",
    "ix_control_list_mapping_profiles_status",
    "ix_control_list_mapping_profiles_created_by",
    "ix_control_list_mapping_profile_sheets_profile",
    "ix_control_list_mapping_profile_columns_sheet",
    "ix_control_list_mapping_profile_columns_semantic_field",
    "uq_control_list_mapping_profiles_code_version",
    "uq_control_list_mapping_profile_sheets_profile_name",
    "uq_control_list_mapping_profile_columns_sheet_column",
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _wp_cl_003_available() -> bool:
    with engine.begin() as conn:
        return all(table_exists(conn, table) for table in WP_CL_003_TABLES)


def _alembic_config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", str(engine.url.render_as_string(hide_password=False)))
    return cfg


def _require_wp_cl_003() -> None:
    if not _wp_cl_003_available():
        pytest.skip(
            f"WP-CL-003 tables missing — run: alembic upgrade head (revision {REVISION_ID})"
        )


def _expect_sql_failure(sql: str, params: dict | None = None) -> None:
    with engine.begin() as conn:
        with pytest.raises(Exception):
            conn.execute(text(sql), params or {})


def _index_exists(conn, index_name: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = :index_name
            LIMIT 1
            """
        ),
        {"index_name": index_name},
    ).first()
    return row is not None


def _current_revision() -> str | None:
    with engine.begin() as conn:
        if not table_exists(conn, "alembic_version"):
            return None
        row = conn.execute(text("SELECT version_num FROM public.alembic_version LIMIT 1")).first()
        return str(row[0]) if row else None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_revision_chain():
    script = ScriptDirectory.from_config(_alembic_config())
    rev = script.get_revision(REVISION_ID)
    assert rev is not None
    assert rev.down_revision == PREVIOUS_REVISION


def test_vocabulary_is_self_consistent():
    assert is_valid_semantic_field(SEMANTIC_FIELD_PERSON_FULL_NAME)
    assert is_valid_semantic_field(SEMANTIC_FIELD_PERSON_IIN)
    assert not is_valid_semantic_field("ppr.person.full_name")
    assert not is_valid_semantic_field("employees.full_name")

    assert is_valid_parser_code(PARSER_CODE_IDENTITY_IIN)
    assert is_valid_parser_code(PARSER_CODE_PERSON_FULL_NAME)
    assert not is_valid_parser_code("ppr.write.person")
    assert len(SEMANTIC_FIELDS) >= 14
    assert len(PARSER_CODES) >= 16


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_wp_cl_003_tables_exist_with_expected_columns():
    _require_wp_cl_003()

    expected = {
        "control_list_mapping_profiles": {
            "profile_id",
            "profile_code",
            "profile_version",
            "profile_name",
            "description",
            "status",
            "created_at",
            "created_by",
            "updated_at",
        },
        "control_list_mapping_profile_sheets": {
            "profile_sheet_id",
            "profile_id",
            "sheet_name",
            "personnel_category",
            "employment_mode",
            "sheet_purpose",
            "header_row_override",
        },
        "control_list_mapping_profile_columns": {
            "profile_column_id",
            "profile_sheet_id",
            "column_index",
            "column_letter",
            "raw_header",
            "semantic_field",
            "parser_code",
            "is_required",
        },
    }

    with engine.begin() as conn:
        for table, cols in expected.items():
            assert table_exists(conn, table), table
            assert cols.issubset(get_columns(conn, table)), table


@pytest.mark.parametrize("index_name", EXPECTED_INDEXES)
@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_wp_cl_003_indexes_exist(index_name):
    _require_wp_cl_003()
    with engine.begin() as conn:
        assert _index_exists(conn, index_name), f"missing index: {index_name}"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_vocabulary_aligns_with_schema_enums():
    _require_wp_cl_003()
    for semantic_field in SEMANTIC_FIELDS:
        assert is_valid_semantic_field(semantic_field)
    for parser_code in PARSER_CODES:
        assert is_valid_parser_code(parser_code)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_wp_cl_003_constraints_and_versioning(seed):
    _require_wp_cl_003()

    suffix = uuid4().hex[:8]
    profile_code = f"pytest_cl003_{suffix}"

    with engine.begin() as conn:
        profile_id_v1 = conn.execute(
            text(
                """
                INSERT INTO public.control_list_mapping_profiles (
                    profile_code, profile_version, profile_name, status, created_by
                )
                VALUES (:code, 1, 'Test v1', 'active', :created_by)
                RETURNING profile_id
                """
            ),
            {"code": profile_code, "created_by": int(seed["initiator_user_id"])},
        ).scalar_one()

    _expect_sql_failure(
        """
        INSERT INTO public.control_list_mapping_profiles (
            profile_code, profile_version, profile_name, status, created_by
        )
        VALUES (:code, 1, 'Duplicate version', 'draft', :created_by)
        """,
        {"code": profile_code, "created_by": int(seed["initiator_user_id"])},
    )

    _expect_sql_failure(
        """
        INSERT INTO public.control_list_mapping_profiles (
            profile_code, profile_version, profile_name, status, created_by
        )
        VALUES (:code, 2, 'Second active', 'active', :created_by)
        """,
        {"code": profile_code, "created_by": int(seed["initiator_user_id"])},
    )

    with engine.begin() as conn:
        profile_id_v2 = conn.execute(
            text(
                """
                INSERT INTO public.control_list_mapping_profiles (
                    profile_code, profile_version, profile_name, status, created_by
                )
                VALUES (:code, 2, 'Test v2', 'draft', :created_by)
                RETURNING profile_id
                """
            ),
            {"code": profile_code, "created_by": int(seed["initiator_user_id"])},
        ).scalar_one()

        sheet_id = conn.execute(
            text(
                """
                INSERT INTO public.control_list_mapping_profile_sheets (
                    profile_id, sheet_name, personnel_category, employment_mode, sheet_purpose
                )
                VALUES (:profile_id, 'врачи', 'doctor', 'primary', 'personnel_control_list')
                RETURNING profile_sheet_id
                """
            ),
            {"profile_id": profile_id_v2},
        ).scalar_one()

    _expect_sql_failure(
        """
        INSERT INTO public.control_list_mapping_profile_columns (
            profile_sheet_id, column_index, semantic_field, parser_code
        )
        VALUES (:sheet_id, 2, 'not.a.valid.field', 'identity.iin')
        """,
        {"sheet_id": sheet_id},
    )

    _expect_sql_failure(
        """
        INSERT INTO public.control_list_mapping_profile_columns (
            profile_sheet_id, column_index, semantic_field, parser_code
        )
        VALUES (:sheet_id, 2, 'person.iin', 'not.a.valid.parser')
        """,
        {"sheet_id": sheet_id},
    )

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.control_list_mapping_profiles WHERE profile_id = :id"),
            {"id": profile_id_v1},
        )
        conn.execute(
            text("DELETE FROM public.control_list_mapping_profiles WHERE profile_id = :id"),
            {"id": profile_id_v2},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_wp_cl_003_repository_create_get_and_list_active(seed):
    _require_wp_cl_003()

    suffix = uuid4().hex[:8]
    profile_code = f"repo_cl003_{suffix}"

    with engine.begin() as conn:
        repo = SqlAlchemyControlListMappingProfileRepository(conn)
        profile_id = repo.create_profile(
            profile_code=profile_code,
            profile_version=1,
            profile_name="Doctors primary",
            created_by=int(seed["initiator_user_id"]),
            description="Pytest mapping profile",
            status=PROFILE_STATUS_ACTIVE,
        )
        sheet_id = repo.create_profile_sheet(
            profile_id=profile_id,
            sheet_name="врачи",
            personnel_category=PERSONNEL_CATEGORY_DOCTOR,
            employment_mode=EMPLOYMENT_MODE_PRIMARY,
            sheet_purpose=SHEET_PURPOSE_PERSONNEL_CONTROL_LIST,
            header_row_override=3,
        )
        col_name_id = repo.create_profile_column(
            profile_sheet_id=sheet_id,
            column_index=2,
            column_letter="B",
            raw_header="ФИО",
            semantic_field=SEMANTIC_FIELD_PERSON_FULL_NAME,
            parser_code=PARSER_CODE_PERSON_FULL_NAME,
            is_required=True,
        )
        col_iin_id = repo.create_profile_column(
            profile_sheet_id=sheet_id,
            column_index=3,
            column_letter="C",
            raw_header="ИИН",
            semantic_field=SEMANTIC_FIELD_PERSON_IIN,
            parser_code=PARSER_CODE_IDENTITY_IIN,
            is_required=True,
        )

        snapshot = repo.get_profile(profile_id=profile_id)
        assert snapshot is not None
        assert snapshot.profile_code == profile_code
        assert snapshot.profile_version == 1
        assert snapshot.status == PROFILE_STATUS_ACTIVE
        assert len(snapshot.sheets) == 1
        assert snapshot.sheets[0].sheet_name == "врачи"
        assert len(snapshot.sheets[0].columns) == 2
        assert snapshot.sheets[0].columns[0].profile_column_id == col_name_id
        assert snapshot.sheets[0].columns[1].profile_column_id == col_iin_id

        by_code = repo.get_profile(profile_code=profile_code, profile_version=1)
        assert by_code is not None
        assert by_code.profile_id == profile_id

        active = repo.list_active_profiles()
        assert any(item.profile_id == profile_id for item in active)

        conn.execute(
            text("DELETE FROM public.control_list_mapping_profiles WHERE profile_id = :id"),
            {"id": profile_id},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_wp_cl_003_cascade_profile_to_columns(seed):
    _require_wp_cl_003()

    suffix = uuid4().hex[:8]

    with engine.begin() as conn:
        repo = SqlAlchemyControlListMappingProfileRepository(conn)
        profile_id = repo.create_profile(
            profile_code=f"cascade_cl003_{suffix}",
            profile_version=1,
            profile_name="Cascade test",
            created_by=int(seed["initiator_user_id"]),
            status=PROFILE_STATUS_DRAFT,
        )
        sheet_id = repo.create_profile_sheet(profile_id=profile_id, sheet_name="медсестры")
        column_id = repo.create_profile_column(
            profile_sheet_id=sheet_id,
            column_index=1,
            semantic_field=SEMANTIC_FIELD_PERSON_FULL_NAME,
            parser_code=PARSER_CODE_PERSON_FULL_NAME,
        )

        conn.execute(
            text("DELETE FROM public.control_list_mapping_profiles WHERE profile_id = :id"),
            {"id": profile_id},
        )
        assert not conn.execute(
            text(
                "SELECT 1 FROM public.control_list_mapping_profile_sheets WHERE profile_sheet_id = :id"
            ),
            {"id": sheet_id},
        ).first()
        assert not conn.execute(
            text(
                "SELECT 1 FROM public.control_list_mapping_profile_columns WHERE profile_column_id = :id"
            ),
            {"id": column_id},
        ).first()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_downgrade_and_upgrade_roundtrip():
    current = _current_revision()
    if current != REVISION_ID:
        pytest.skip(f"DB at {current!r}, not {REVISION_ID!r} — run alembic upgrade head first")

    cfg = _alembic_config()
    try:
        command.downgrade(cfg, PREVIOUS_REVISION)
        with engine.begin() as conn:
            for table in WP_CL_003_TABLES:
                assert not table_exists(conn, table), table

        command.upgrade(cfg, REVISION_ID)
        with engine.begin() as conn:
            for table in WP_CL_003_TABLES:
                assert table_exists(conn, table), table
    finally:
        if _current_revision() != REVISION_ID:
            command.upgrade(cfg, REVISION_ID)
