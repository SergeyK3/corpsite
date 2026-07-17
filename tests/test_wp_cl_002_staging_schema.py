# tests/test_wp_cl_002_staging_schema.py
"""Schema and repository tests for ADR-057 / WP-CL-002 staging layer."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.control_list_import.infrastructure.repository import SqlAlchemyControlListImportStagingRepository
from app.db.engine import engine
from app.db.models.control_list_import import (
    EMPLOYMENT_MODE_PRIMARY,
    INFERRED_TYPE_IIN_CANDIDATE,
    PERSONNEL_CATEGORY_DOCTOR,
    ROW_KIND_DATA,
    RUN_STATUS_STAGED,
    SHEET_PURPOSE_PERSONNEL_CONTROL_LIST,
    SHEET_STATUS_ANALYZED,
)
from tests.conftest import get_columns, table_exists

REVISION_ID = "x3y4z5a6b7c8"
PREVIOUS_REVISION = "w2x3y4z5a6b7"

WP_CL_002_TABLES = (
    "control_list_import_runs",
    "control_list_import_sheets",
    "control_list_import_rows",
    "control_list_import_cells",
)

EXPECTED_INDEXES = (
    "ix_control_list_import_runs_status",
    "ix_control_list_import_runs_source_sha256",
    "ix_control_list_import_runs_imported_by",
    "ix_control_list_import_sheets_run",
    "ix_control_list_import_sheets_run_status",
    "ix_control_list_import_rows_sheet",
    "ix_control_list_import_rows_sheet_kind",
    "ix_control_list_import_cells_row",
    "ix_control_list_import_cells_semantic_hint",
    "uq_control_list_import_sheets_run_index",
    "uq_control_list_import_sheets_run_name",
    "uq_control_list_import_rows_sheet_row",
    "uq_control_list_import_cells_row_column",
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _wp_cl_002_available() -> bool:
    with engine.begin() as conn:
        return all(table_exists(conn, table) for table in WP_CL_002_TABLES)


def _alembic_config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", str(engine.url.render_as_string(hide_password=False)))
    return cfg


def _require_wp_cl_002() -> None:
    if not _wp_cl_002_available():
        pytest.skip(
            f"WP-CL-002 tables missing — run: alembic upgrade head (revision {REVISION_ID})"
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


def _sample_sha256() -> str:
    return "a" * 64


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_revision_chain():
    script = ScriptDirectory.from_config(_alembic_config())
    rev = script.get_revision(REVISION_ID)
    assert rev is not None
    assert rev.down_revision == PREVIOUS_REVISION


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_wp_cl_002_tables_exist_with_expected_columns():
    _require_wp_cl_002()

    expected = {
        "control_list_import_runs": {
            "import_run_id",
            "source_filename",
            "source_sha256",
            "imported_at",
            "imported_by",
            "profiler_version",
            "status",
        },
        "control_list_import_sheets": {
            "sheet_id",
            "import_run_id",
            "sheet_name",
            "sheet_index",
            "personnel_category",
            "employment_mode",
            "sheet_purpose",
            "status",
        },
        "control_list_import_rows": {
            "row_id",
            "sheet_id",
            "excel_row_number",
            "row_kind",
            "section_key",
            "section_caption",
        },
        "control_list_import_cells": {
            "cell_id",
            "row_id",
            "column_letter",
            "column_index",
            "raw_header",
            "raw_value",
            "normalized_text",
            "inferred_type",
            "issue_codes",
            "semantic_hint",
            "is_composite",
        },
    }

    with engine.begin() as conn:
        for table, cols in expected.items():
            assert table_exists(conn, table), table
            assert cols.issubset(get_columns(conn, table)), table


@pytest.mark.parametrize("index_name", EXPECTED_INDEXES)
@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_wp_cl_002_indexes_exist(index_name):
    _require_wp_cl_002()
    with engine.begin() as conn:
        assert _index_exists(conn, index_name), f"missing index: {index_name}"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_wp_cl_002_foreign_keys_and_checks(seed):
    _require_wp_cl_002()

    suffix = uuid4().hex[:8]

    _expect_sql_failure(
        """
        INSERT INTO public.control_list_import_runs (
            source_filename, source_sha256, imported_by, profiler_version, status
        )
        VALUES ('bad.xlsx', 'not-a-sha256', :imported_by, '1', 'staged')
        """,
        {"imported_by": int(seed["initiator_user_id"])},
    )

    _expect_sql_failure(
        """
        INSERT INTO public.control_list_import_runs (
            source_filename, source_sha256, imported_by, profiler_version, status
        )
        VALUES ('bad.xlsx', :sha256, -999999, '1', 'staged')
        """,
        {"sha256": _sample_sha256()},
    )

    with engine.begin() as conn:
        run_id = conn.execute(
            text(
                """
                INSERT INTO public.control_list_import_runs (
                    source_filename, source_sha256, imported_by, profiler_version, status
                )
                VALUES (:filename, :sha256, :imported_by, '1', 'staged')
                RETURNING import_run_id
                """
            ),
            {
                "filename": f"pytest_{suffix}.xlsx",
                "sha256": _sample_sha256(),
                "imported_by": int(seed["initiator_user_id"]),
            },
        ).scalar_one()

        sheet_id = conn.execute(
            text(
                """
                INSERT INTO public.control_list_import_sheets (
                    import_run_id, sheet_name, sheet_index,
                    personnel_category, employment_mode, sheet_purpose, status
                )
                VALUES (
                    :run_id, 'врачи', 0,
                    'doctor', 'primary', 'personnel_control_list', 'analyzed'
                )
                RETURNING sheet_id
                """
            ),
            {"run_id": run_id},
        ).scalar_one()

    _expect_sql_failure(
        """
        INSERT INTO public.control_list_import_sheets (
            import_run_id, sheet_name, sheet_index,
            personnel_category, employment_mode, sheet_purpose, status
        )
        VALUES (
            :run_id, 'врачи', 0,
            'doctor', 'primary', 'personnel_control_list', 'analyzed'
        )
        """,
        {"run_id": run_id},
    )

    _expect_sql_failure(
        """
        INSERT INTO public.control_list_import_rows (
            sheet_id, excel_row_number, row_kind
        )
        VALUES (-999999, 5, 'data')
        """
    )

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.control_list_import_runs WHERE import_run_id = :id"),
            {"id": run_id},
        )
        assert not conn.execute(
            text("SELECT 1 FROM public.control_list_import_sheets WHERE sheet_id = :id"),
            {"id": sheet_id},
        ).first()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_wp_cl_002_repository_create_chain(seed):
    _require_wp_cl_002()

    suffix = uuid4().hex[:8]

    with engine.begin() as conn:
        repo = SqlAlchemyControlListImportStagingRepository(conn)
        run_id = repo.create_run(
            source_filename=f"pytest_repo_{suffix}.xlsx",
            source_sha256=_sample_sha256(),
            imported_by=int(seed["initiator_user_id"]),
            profiler_version="1",
            status=RUN_STATUS_STAGED,
        )
        sheet_id = repo.create_sheet(
            import_run_id=run_id,
            sheet_name="врачи",
            sheet_index=0,
            personnel_category=PERSONNEL_CATEGORY_DOCTOR,
            employment_mode=EMPLOYMENT_MODE_PRIMARY,
            sheet_purpose=SHEET_PURPOSE_PERSONNEL_CONTROL_LIST,
            status=SHEET_STATUS_ANALYZED,
        )
        row_id = repo.create_row(
            sheet_id=sheet_id,
            excel_row_number=5,
            row_kind=ROW_KIND_DATA,
            section_key="dept_1",
            section_caption="Терапевтическое отделение",
        )
        cell_id = repo.create_cell(
            row_id=row_id,
            column_letter="C",
            column_index=3,
            raw_header="ИИН",
            raw_value="900101300123",
            normalized_text="900101300123",
            inferred_type=INFERRED_TYPE_IIN_CANDIDATE,
            issue_codes=["iin_stored_as_number"],
            semantic_hint="person.iin",
            is_composite=False,
        )

        assert run_id > 0
        assert sheet_id > 0
        assert row_id > 0
        assert cell_id > 0

        cell_row = conn.execute(
            text(
                """
                SELECT issue_codes, semantic_hint, inferred_type
                FROM public.control_list_import_cells
                WHERE cell_id = :cell_id
                """
            ),
            {"cell_id": cell_id},
        ).one()
        assert cell_row.issue_codes == ["iin_stored_as_number"]
        assert cell_row.semantic_hint == "person.iin"
        assert cell_row.inferred_type == INFERRED_TYPE_IIN_CANDIDATE

        conn.execute(
            text("DELETE FROM public.control_list_import_runs WHERE import_run_id = :id"),
            {"id": run_id},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_wp_cl_002_cascade_row_to_cells(seed):
    _require_wp_cl_002()

    suffix = uuid4().hex[:8]

    with engine.begin() as conn:
        repo = SqlAlchemyControlListImportStagingRepository(conn)
        run_id = repo.create_run(
            source_filename=f"pytest_cascade_{suffix}.xlsx",
            source_sha256=_sample_sha256(),
            imported_by=int(seed["initiator_user_id"]),
            profiler_version="1",
        )
        sheet_id = repo.create_sheet(
            import_run_id=run_id,
            sheet_name="медсестры",
            sheet_index=1,
        )
        row_id = repo.create_row(sheet_id=sheet_id, excel_row_number=10)
        cell_id = repo.create_cell(
            row_id=row_id,
            column_letter="A",
            column_index=1,
            raw_value="Test",
        )

        conn.execute(
            text("DELETE FROM public.control_list_import_rows WHERE row_id = :id"),
            {"id": row_id},
        )
        assert not conn.execute(
            text("SELECT 1 FROM public.control_list_import_cells WHERE cell_id = :id"),
            {"id": cell_id},
        ).first()

        conn.execute(
            text("DELETE FROM public.control_list_import_runs WHERE import_run_id = :id"),
            {"id": run_id},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_downgrade_and_upgrade_roundtrip():
    current = _current_revision()
    if current != REVISION_ID:
        pytest.skip(f"DB at {current!r}, not {REVISION_ID!r} — run alembic upgrade head first")

    cfg = _alembic_config()
    try:
        command.downgrade(cfg, PREVIOUS_REVISION)
        with engine.begin() as conn:
            for table in WP_CL_002_TABLES:
                assert not table_exists(conn, table), table

        command.upgrade(cfg, REVISION_ID)
        with engine.begin() as conn:
            for table in WP_CL_002_TABLES:
                assert table_exists(conn, table), table
    finally:
        if _current_revision() != REVISION_ID:
            command.upgrade(cfg, REVISION_ID)
