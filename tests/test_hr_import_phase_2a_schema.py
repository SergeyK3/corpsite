# tests/test_hr_import_phase_2a_schema.py
"""Schema tests for ADR-038 Phase 2A (identity + HR import staging)."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.db.engine import engine
from tests.conftest import get_columns, insert_returning_id, table_exists

REVISION_ID = "c1a8f92e4b03"
PREVIOUS_REVISION = "f2b3c4d5e6a7"

PHASE_2A_TABLES = (
    "employee_identities",
    "hr_import_batches",
    "hr_import_rows",
    "hr_import_document_candidates",
    "org_unit_aliases",
    "position_aliases",
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _phase_2a_available() -> bool:
    with engine.begin() as conn:
        return all(table_exists(conn, table) for table in PHASE_2A_TABLES)


def _alembic_config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", str(engine.url.render_as_string(hide_password=False)))
    return cfg


def _require_phase_2a() -> None:
    if not _phase_2a_available():
        pytest.skip(
            f"Phase 2A tables missing — run: alembic upgrade head (revision {REVISION_ID})"
        )


def _expect_sql_failure(sql: str, params: dict | None = None) -> None:
    with engine.begin() as conn:
        with pytest.raises(Exception):
            conn.execute(text(sql), params or {})


def _insert_employee(conn, *, full_name: str, org_unit_id: int) -> int:
    values = {
        "full_name": full_name,
        "org_unit_id": org_unit_id,
        "is_active": True,
    }
    cols = get_columns(conn, "employees")
    if "employment_rate" in cols:
        values["employment_rate"] = 1.00
    return insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values=values,
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_revision_chain():
    script = ScriptDirectory.from_config(_alembic_config())
    rev = script.get_revision(REVISION_ID)
    assert rev is not None
    assert rev.down_revision == PREVIOUS_REVISION


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_phase_2a_tables_exist_with_expected_columns():
    _require_phase_2a()

    expected = {
        "employee_identities": {
            "identity_id",
            "employee_id",
            "identity_type",
            "identity_value",
            "valid_from",
            "valid_to",
            "is_primary",
            "created_at",
            "created_by",
        },
        "hr_import_batches": {
            "batch_id",
            "source_type",
            "file_name",
            "imported_by",
            "imported_at",
            "status",
            "total_rows",
            "valid_rows",
            "error_rows",
        },
        "hr_import_rows": {
            "row_id",
            "batch_id",
            "source_sheet",
            "source_row_number",
            "raw_payload",
            "normalized_payload",
            "match_status",
            "review_status",
            "error_codes",
            "employee_id",
        },
        "hr_import_document_candidates": {
            "candidate_id",
            "row_id",
            "employee_id",
            "proposed_document_type",
            "parsed_hours",
            "parsed_valid_until",
            "confidence_score",
            "review_status",
            "created_document_id",
        },
        "org_unit_aliases": {
            "alias_id",
            "org_unit_id",
            "alias_text",
            "normalized_alias",
        },
        "position_aliases": {
            "alias_id",
            "position_id",
            "alias_text",
            "normalized_alias",
        },
    }

    with engine.begin() as conn:
        for table, cols in expected.items():
            assert table_exists(conn, table), table
            assert cols.issubset(get_columns(conn, table)), table


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_employee_identities_fk_and_unique_iin(seed):
    _require_phase_2a()

    suffix = uuid4().hex[:8]
    iin_value = f"9{suffix}012345"[:12]

    with engine.begin() as conn:
        employee_id = _insert_employee(
            conn,
            full_name=f"Phase2A Identity {suffix}",
            org_unit_id=int(seed["unit_id"]),
        )

        identity_id = insert_returning_id(
            conn,
            table="employee_identities",
            id_col="identity_id",
            values={
                "employee_id": employee_id,
                "identity_type": "IIN",
                "identity_value": iin_value,
                "is_primary": True,
                "created_by": int(seed["initiator_user_id"]),
            },
        )
        assert identity_id > 0

    _expect_sql_failure(
        """
        INSERT INTO public.employee_identities (
            employee_id, identity_type, identity_value, is_primary
        )
        VALUES (:employee_id, 'IIN', :iin_value, FALSE)
        """,
        {"employee_id": employee_id, "iin_value": iin_value},
    )
    _expect_sql_failure(
        """
        INSERT INTO public.employee_identities (
            employee_id, identity_type, identity_value
        )
        VALUES (-999999, 'IIN', '000000000001')
        """
    )

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.employee_identities WHERE identity_id = :id"),
            {"id": identity_id},
        )
        conn.execute(
            text("DELETE FROM public.employees WHERE employee_id = :id"),
            {"id": employee_id},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_hr_import_staging_fk_and_source_unique(seed):
    _require_phase_2a()

    suffix = uuid4().hex[:8]

    with engine.begin() as conn:
        batch_id = insert_returning_id(
            conn,
            table="hr_import_batches",
            id_col="batch_id",
            values={
                "source_type": "HR_CONTROL_LIST",
                "file_name": f"pytest_{suffix}.xlsx",
                "imported_by": int(seed["initiator_user_id"]),
                "status": "PARSED",
                "total_rows": 1,
                "valid_rows": 1,
                "error_rows": 0,
            },
        )

        row_id = int(
            conn.execute(
                text(
                    """
                    INSERT INTO public.hr_import_rows (
                        batch_id, source_sheet, source_row_number,
                        raw_payload, normalized_payload,
                        match_status, review_status, error_codes
                    )
                    VALUES (
                        :batch_id, 'doctors', 42,
                        '{"full_name": "Test"}'::jsonb,
                        '{"full_name": "Test"}'::jsonb,
                        'REVIEW_REQUIRED', 'PENDING',
                        ARRAY['missing_department']::text[]
                    )
                    RETURNING row_id
                    """
                ),
                {"batch_id": batch_id},
            ).scalar_one()
        )

        candidate_values: dict = {
            "row_id": row_id,
            "proposed_document_type": "QUAL_UPGRADE",
            "parsed_hours": 54,
            "confidence_score": 0.75,
            "review_status": "PENDING",
        }
        if "batch_id" in get_columns(conn, "hr_import_document_candidates"):
            candidate_values["batch_id"] = batch_id
            candidate_values["raw_text"] = "2024 курс ПК"
        candidate_id = insert_returning_id(
            conn,
            table="hr_import_document_candidates",
            id_col="candidate_id",
            values=candidate_values,
        )
        assert candidate_id > 0

    _expect_sql_failure(
        """
        INSERT INTO public.hr_import_rows (
            batch_id, source_sheet, source_row_number,
            raw_payload, normalized_payload, match_status
        )
        VALUES (
            :batch_id, 'doctors', 42,
            '{}'::jsonb, '{}'::jsonb, 'REVIEW_REQUIRED'
        )
        """,
        {"batch_id": batch_id},
    )
    _expect_sql_failure(
        """
        INSERT INTO public.hr_import_document_candidates (row_id)
        VALUES (-999999)
        """
    )

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.hr_import_document_candidates WHERE candidate_id = :id"),
            {"id": candidate_id},
        )
        conn.execute(
            text("DELETE FROM public.hr_import_rows WHERE row_id = :id"),
            {"id": row_id},
        )
        conn.execute(
            text("DELETE FROM public.hr_import_batches WHERE batch_id = :id"),
            {"id": batch_id},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_alias_unique_constraints(seed):
    _require_phase_2a()

    suffix = uuid4().hex[:8]
    normalized = f"pytest alias {suffix}"

    with engine.begin() as conn:
        org_unit_id = int(seed["unit_id"])

        position_id = insert_returning_id(
            conn,
            table="positions",
            id_col="position_id",
            values={"name": f"Pytest Position {suffix}"},
        )

        org_alias_id = insert_returning_id(
            conn,
            table="org_unit_aliases",
            id_col="alias_id",
            values={
                "org_unit_id": org_unit_id,
                "alias_text": f"ОТДЕЛЕНИЕ {suffix}",
                "normalized_alias": normalized,
            },
        )

        pos_alias_id = insert_returning_id(
            conn,
            table="position_aliases",
            id_col="alias_id",
            values={
                "position_id": position_id,
                "alias_text": f"Врач {suffix}",
                "normalized_alias": f"position {normalized}",
            },
        )

    _expect_sql_failure(
        """
        INSERT INTO public.org_unit_aliases (
            org_unit_id, alias_text, normalized_alias
        )
        VALUES (:org_unit_id, 'duplicate', :normalized_alias)
        """,
        {"org_unit_id": org_unit_id, "normalized_alias": normalized},
    )
    _expect_sql_failure(
        """
        INSERT INTO public.position_aliases (
            position_id, alias_text, normalized_alias
        )
        VALUES (:position_id, 'duplicate', :normalized_alias)
        """,
        {
            "position_id": position_id,
            "normalized_alias": f"position {normalized}",
        },
    )

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.position_aliases WHERE alias_id = :id"),
            {"id": pos_alias_id},
        )
        conn.execute(
            text("DELETE FROM public.org_unit_aliases WHERE alias_id = :id"),
            {"id": org_alias_id},
        )
        conn.execute(
            text("DELETE FROM public.positions WHERE position_id = :id"),
            {"id": position_id},
        )
