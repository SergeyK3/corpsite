# tests/test_wp_mrd_001_schema.py
"""Schema tests for WP-MRD-001 Monthly Reference Dataset foundation."""
from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.db.engine import engine
from app.mrd.domain.types import ORIGIN_IMPORT_COMPARE, SEED_DIFFERENCE_ORIGIN_CODES
from tests.conftest import get_columns, table_exists

REVISION_ID = "e6f7a8b9c0d1"
PREVIOUS_REVISION = "d5e6f7a8b9c0"

WP_MRD_001_TABLES = (
    "hr_monthly_references",
    "hr_monthly_reference_entries",
    "hr_difference_origin_types",
    "hr_detected_differences",
    "hr_confirmed_changes",
    "hr_comparison_runs",
    "hr_reference_version_events",
)

EXPECTED_INDEXES = (
    "uq_hmr_one_active_per_period",
    "uq_hmr_report_period_version",
    "ix_hmr_report_period_status",
    "ix_hcr_batch_started",
    "ix_hcr_mrd_started",
    "uq_hdd_one_open_detected_per_logical_key",
    "ix_hdd_queue_detected",
    "ix_hdd_origin",
    "ix_hdd_supersedes",
    "uq_hcc_one_event_per_difference",
    "ix_hcc_report_period_confirmed_at",
    "ix_hcc_mrd_confirmed_at",
    "uq_hmre_mrd_match_key",
    "ix_hmre_mrd_id",
    "ix_hmre_canonical_hash",
    "ix_hmre_employee_id",
    "ix_hrve_mrd_performed_at",
    "ix_hrve_report_period_performed_at",
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _wp_mrd_001_available() -> bool:
    with engine.begin() as conn:
        return all(table_exists(conn, table) for table in WP_MRD_001_TABLES)


def _alembic_config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", str(engine.url.render_as_string(hide_password=False)))
    return cfg


def _require_wp_mrd_001() -> None:
    if not _wp_mrd_001_available():
        pytest.skip(
            f"WP-MRD-001 tables missing — run: alembic upgrade head (revision {REVISION_ID})"
        )


def _expect_sql_failure(conn, sql: str, params: dict | None = None) -> None:
    nested = conn.begin_nested()
    with pytest.raises(Exception):
        conn.execute(text(sql), params or {})
    nested.rollback()


def _report_period() -> date:
    suffix = uuid4().hex
    year = 2090 + int(suffix[:2], 16) % 10
    month = int(suffix[2:4], 16) % 12 + 1
    return date(year, month, 1)


@pytest.fixture
def db_tx():
    conn = engine.connect()
    tx = conn.begin()
    try:
        yield conn
    finally:
        tx.rollback()
        conn.close()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_revision_chain() -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    revision = script.get_revision(REVISION_ID)
    assert revision is not None
    assert revision.down_revision == PREVIOUS_REVISION


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_wp_mrd_001_tables_exist_with_expected_columns() -> None:
    _require_wp_mrd_001()

    expected = {
        "hr_difference_origin_types": {
            "origin_code",
            "label",
            "description",
            "is_active",
            "created_at",
        },
        "hr_monthly_references": {
            "mrd_id",
            "report_period",
            "version",
            "status",
            "source_type",
            "forked_from_reference_id",
            "entry_count",
            "created_by",
            "created_at",
            "closed_at",
            "closed_by",
            "notes",
            "row_version",
        },
        "hr_monthly_reference_entries": {
            "entry_id",
            "mrd_id",
            "entity_scope",
            "record_kind",
            "match_key",
            "canonical_hash",
            "employee_id",
            "iin",
            "effective_payload",
            "source_row_id",
            "source_normalized_record_id",
            "last_confirmed_change_id",
            "created_at",
            "updated_at",
            "row_version",
        },
        "hr_detected_differences": {
            "difference_id",
            "report_period",
            "mrd_id",
            "logical_key",
            "entity_scope",
            "record_kind",
            "attribute",
            "business_type",
            "lifecycle_status",
            "technical_diff_class",
            "difference_origin_code",
            "origin_context",
            "old_value",
            "new_value",
            "supersedes_difference_id",
            "last_comparison_run_id",
            "detected_at",
            "confirmed_at",
            "confirmed_by",
            "rejected_at",
            "rejected_by",
            "reject_basis",
            "row_version",
        },
        "hr_confirmed_changes": {
            "confirmed_change_id",
            "detected_difference_id",
            "report_period",
            "mrd_id",
            "entity_scope",
            "attribute",
            "old_value",
            "new_value",
            "confirmed_by",
            "confirmed_at",
            "basis",
            "difference_origin_code",
            "origin_context",
            "source_batch_id",
            "created_at",
        },
        "hr_comparison_runs": {
            "comparison_run_id",
            "batch_id",
            "mrd_id",
            "report_period",
            "status",
            "started_at",
            "completed_at",
            "started_by",
            "stats",
        },
        "hr_reference_version_events": {
            "event_id",
            "event_type",
            "report_period",
            "mrd_id",
            "source_mrd_id",
            "performed_by",
            "performed_at",
            "event_context",
        },
    }

    with engine.begin() as conn:
        for table, cols in expected.items():
            assert table_exists(conn, table), table
            assert cols.issubset(get_columns(conn, table)), table


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_expected_indexes_exist() -> None:
    _require_wp_mrd_001()
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = ANY(:names)
                """
            ),
            {"names": list(EXPECTED_INDEXES)},
        ).fetchall()
    found = {row[0] for row in rows}
    assert found == set(EXPECTED_INDEXES)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_seed_difference_origin_types() -> None:
    _require_wp_mrd_001()
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT origin_code, is_active
                FROM public.hr_difference_origin_types
                ORDER BY origin_code
                """
            )
        ).fetchall()
    codes = {row[0] for row in rows}
    assert SEED_DIFFERENCE_ORIGIN_CODES.issubset(codes)
    assert all(bool(row[1]) for row in rows if row[0] in SEED_DIFFERENCE_ORIGIN_CODES)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_inv_mrd_01_only_one_active_mrd_per_period(seed, db_tx) -> None:
    _require_wp_mrd_001()
    period = _report_period()
    user_id = int(seed["initiator_user_id"])

    db_tx.execute(
        text(
            """
            INSERT INTO public.hr_monthly_references (
                report_period, version, status, created_by
            )
            VALUES (:period, 1, 'ACTIVE', :user_id)
            """
        ),
        {"period": period, "user_id": user_id},
    )

    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.hr_monthly_references (
            report_period, version, status, created_by
        )
        VALUES (:period, 2, 'ACTIVE', :user_id)
        """,
        {"period": period, "user_id": user_id},
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_unique_version_within_period(seed, db_tx) -> None:
    _require_wp_mrd_001()
    period = _report_period()
    user_id = int(seed["initiator_user_id"])

    db_tx.execute(
        text(
            """
            INSERT INTO public.hr_monthly_references (
                report_period, version, status, created_by
            )
            VALUES (:period, 1, 'ACTIVE', :user_id)
            """
        ),
        {"period": period, "user_id": user_id},
    )

    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.hr_monthly_references (
            report_period, version, status, created_by, closed_at, closed_by
        )
        VALUES (:period, 1, 'CLOSED', :user_id, NOW(), :user_id)
        """,
        {"period": period, "user_id": user_id},
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_inv_dd_05_one_open_detected_per_logical_key(seed, db_tx) -> None:
    _require_wp_mrd_001()
    period = _report_period()
    user_id = int(seed["initiator_user_id"])
    logical_key = f"pytest:{uuid4().hex}"

    mrd_id = db_tx.execute(
        text(
            """
            INSERT INTO public.hr_monthly_references (
                report_period, version, status, created_by
            )
            VALUES (:period, 1, 'ACTIVE', :user_id)
            RETURNING mrd_id
            """
        ),
        {"period": period, "user_id": user_id},
    ).scalar_one()

    db_tx.execute(
        text(
            """
            INSERT INTO public.hr_detected_differences (
                report_period, mrd_id, logical_key, entity_scope, attribute,
                business_type, lifecycle_status, difference_origin_code, origin_context
            )
            VALUES (
                :period, :mrd_id, :logical_key, 'employee:1', 'position',
                'PERIOD_CHANGED', 'DETECTED', :origin, '{}'::jsonb
            )
            """
        ),
        {
            "period": period,
            "mrd_id": mrd_id,
            "logical_key": logical_key,
            "origin": ORIGIN_IMPORT_COMPARE,
        },
    )

    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.hr_detected_differences (
            report_period, mrd_id, logical_key, entity_scope, attribute,
            business_type, lifecycle_status, difference_origin_code, origin_context
        )
        VALUES (
            :period, :mrd_id, :logical_key, 'employee:1', 'position',
            'PERIOD_CHANGED', 'DETECTED', :origin, '{}'::jsonb
        )
        """,
        {
            "period": period,
            "mrd_id": mrd_id,
            "logical_key": logical_key,
            "origin": ORIGIN_IMPORT_COMPARE,
        },
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_inv_dd_02_detected_difference_delete_forbidden(seed, db_tx) -> None:
    _require_wp_mrd_001()
    period = _report_period()
    user_id = int(seed["initiator_user_id"])

    mrd_id = db_tx.execute(
        text(
            """
            INSERT INTO public.hr_monthly_references (
                report_period, version, status, created_by
            )
            VALUES (:period, 1, 'ACTIVE', :user_id)
            RETURNING mrd_id
            """
        ),
        {"period": period, "user_id": user_id},
    ).scalar_one()
    difference_id = db_tx.execute(
        text(
            """
            INSERT INTO public.hr_detected_differences (
                report_period, mrd_id, logical_key, entity_scope, attribute,
                business_type, lifecycle_status, difference_origin_code, origin_context
            )
            VALUES (
                :period, :mrd_id, :logical_key, 'employee:1', 'position',
                'PERIOD_CHANGED', 'DETECTED', :origin, '{}'::jsonb
            )
            RETURNING difference_id
            """
        ),
        {
            "period": period,
            "mrd_id": mrd_id,
            "logical_key": f"pytest:{uuid4().hex}",
            "origin": ORIGIN_IMPORT_COMPARE,
        },
    ).scalar_one()

    _expect_sql_failure(
        db_tx,
        "DELETE FROM public.hr_detected_differences WHERE difference_id = :difference_id",
        {"difference_id": difference_id},
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_inv_cc_02_confirmed_change_append_only(seed, db_tx) -> None:
    _require_wp_mrd_001()
    period = _report_period()
    user_id = int(seed["initiator_user_id"])

    mrd_id = db_tx.execute(
        text(
            """
            INSERT INTO public.hr_monthly_references (
                report_period, version, status, created_by
            )
            VALUES (:period, 1, 'ACTIVE', :user_id)
            RETURNING mrd_id
            """
        ),
        {"period": period, "user_id": user_id},
    ).scalar_one()
    difference_id = db_tx.execute(
        text(
            """
            INSERT INTO public.hr_detected_differences (
                report_period, mrd_id, logical_key, entity_scope, attribute,
                business_type, lifecycle_status, difference_origin_code, origin_context
            )
            VALUES (
                :period, :mrd_id, :logical_key, 'employee:1', 'position',
                'PERIOD_CHANGED', 'DETECTED', :origin, '{"batch_id": 1}'::jsonb
            )
            RETURNING difference_id
            """
        ),
        {
            "period": period,
            "mrd_id": mrd_id,
            "logical_key": f"pytest:{uuid4().hex}",
            "origin": ORIGIN_IMPORT_COMPARE,
        },
    ).scalar_one()
    confirmed_change_id = db_tx.execute(
        text(
            """
            INSERT INTO public.hr_confirmed_changes (
                detected_difference_id, report_period, mrd_id, entity_scope, attribute,
                old_value, new_value, confirmed_by, difference_origin_code, origin_context
            )
            VALUES (
                :difference_id, :period, :mrd_id, 'employee:1', 'position',
                '"nurse"'::jsonb, '"senior nurse"'::jsonb, :user_id, :origin,
                '{"batch_id": 1}'::jsonb
            )
            RETURNING confirmed_change_id
            """
        ),
        {
            "difference_id": difference_id,
            "period": period,
            "mrd_id": mrd_id,
            "user_id": user_id,
            "origin": ORIGIN_IMPORT_COMPARE,
        },
    ).scalar_one()

    _expect_sql_failure(
        db_tx,
        """
        UPDATE public.hr_confirmed_changes
        SET basis = 'changed'
        WHERE confirmed_change_id = :confirmed_change_id
        """,
        {"confirmed_change_id": confirmed_change_id},
    )
    _expect_sql_failure(
        db_tx,
        """
        DELETE FROM public.hr_confirmed_changes
        WHERE confirmed_change_id = :confirmed_change_id
        """,
        {"confirmed_change_id": confirmed_change_id},
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_inv_mrd_04_closed_mrd_entry_mutation_forbidden(seed, db_tx) -> None:
    _require_wp_mrd_001()
    period = _report_period()
    user_id = int(seed["initiator_user_id"])
    closed_at = datetime.now(timezone.utc)

    mrd_id = db_tx.execute(
        text(
            """
            INSERT INTO public.hr_monthly_references (
                report_period, version, status, created_by, closed_at, closed_by
            )
            VALUES (:period, 1, 'CLOSED', :user_id, :closed_at, :user_id)
            RETURNING mrd_id
            """
        ),
        {"period": period, "user_id": user_id, "closed_at": closed_at},
    ).scalar_one()

    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.hr_monthly_reference_entries (
            mrd_id, entity_scope, record_kind, match_key, canonical_hash, effective_payload
        )
        VALUES (
            :mrd_id, 'employee:1', 'roster', :match_key, 'hash-1', '{}'::jsonb
        )
        """,
        {"mrd_id": mrd_id, "match_key": f"mk:{uuid4().hex}"},
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_inv_org_01_missing_origin_rejected(seed, db_tx) -> None:
    _require_wp_mrd_001()
    period = _report_period()
    user_id = int(seed["initiator_user_id"])

    mrd_id = db_tx.execute(
        text(
            """
            INSERT INTO public.hr_monthly_references (
                report_period, version, status, created_by
            )
            VALUES (:period, 1, 'ACTIVE', :user_id)
            RETURNING mrd_id
            """
        ),
        {"period": period, "user_id": user_id},
    ).scalar_one()

    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.hr_detected_differences (
            report_period, mrd_id, logical_key, entity_scope, attribute,
            business_type, lifecycle_status, difference_origin_code, origin_context
        )
        VALUES (
            :period, :mrd_id, :logical_key, 'employee:1', 'position',
            'PERIOD_CHANGED', 'DETECTED', 'UNKNOWN_ORIGIN', '{}'::jsonb
        )
        """,
        {
            "period": period,
            "mrd_id": mrd_id,
            "logical_key": f"pytest:{uuid4().hex}",
        },
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_inv_org_02_inactive_origin_rejected(seed, db_tx) -> None:
    _require_wp_mrd_001()
    period = _report_period()
    user_id = int(seed["initiator_user_id"])
    origin_code = f"PYTEST_INACTIVE_{uuid4().hex[:8].upper()}"

    mrd_id = db_tx.execute(
        text(
            """
            INSERT INTO public.hr_monthly_references (
                report_period, version, status, created_by
            )
            VALUES (:period, 1, 'ACTIVE', :user_id)
            RETURNING mrd_id
            """
        ),
        {"period": period, "user_id": user_id},
    ).scalar_one()
    db_tx.execute(
        text(
            """
            INSERT INTO public.hr_difference_origin_types (
                origin_code, label, is_active
            )
            VALUES (:origin_code, 'Inactive test origin', FALSE)
            """
        ),
        {"origin_code": origin_code},
    )

    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.hr_detected_differences (
            report_period, mrd_id, logical_key, entity_scope, attribute,
            business_type, lifecycle_status, difference_origin_code, origin_context
        )
        VALUES (
            :period, :mrd_id, :logical_key, 'employee:1', 'position',
            'PERIOD_CHANGED', 'DETECTED', :origin_code, '{}'::jsonb
        )
        """,
        {
            "period": period,
            "mrd_id": mrd_id,
            "logical_key": f"pytest:{uuid4().hex}",
            "origin_code": origin_code,
        },
    )
