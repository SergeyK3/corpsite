# tests/test_wp_cl_012_apply_execution_schema.py
"""Schema tests for WP-CL-012 apply execution journal."""
from __future__ import annotations

import hashlib
from uuid import uuid4

import pytest
from sqlalchemy import text

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.db.engine import engine
from app.control_list_import.infrastructure.apply_execution_repository import SqlAlchemyApplyExecutionRepository
from tests.conftest import get_columns, table_exists

REVISION_ID = "z5a6b7c8d9e0f1"
PREVIOUS_REVISION = "y4z5a6b7c8d9e0"

WP_CL_012_TABLES = (
    "control_list_apply_runs",
    "control_list_apply_actions",
)

EXPECTED_INDEXES = (
    "uq_control_list_apply_runs_plan_fingerprint",
    "ix_control_list_apply_runs_import_run",
    "ix_control_list_apply_runs_status",
    "uq_control_list_apply_actions_run_index",
    "uq_control_list_apply_actions_idempotency_key",
    "ix_control_list_apply_actions_run",
    "ix_control_list_apply_actions_status",
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _wp_cl_012_available() -> bool:
    with engine.begin() as conn:
        return all(table_exists(conn, table) for table in WP_CL_012_TABLES)


def _alembic_config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", str(engine.url.render_as_string(hide_password=False)))
    return cfg


def _require_wp_cl_012() -> None:
    if not _wp_cl_012_available():
        pytest.skip(
            f"WP-CL-012 tables missing — run: alembic upgrade head (revision {REVISION_ID})"
        )


@pytest.mark.skipif(not _db_available(), reason="Database unavailable")
def test_migration_revision_chain():
    script = ScriptDirectory.from_config(_alembic_config())
    revision = script.get_revision(REVISION_ID)
    assert revision is not None
    assert revision.down_revision == PREVIOUS_REVISION


def _sample_sha256() -> str:
    return hashlib.sha256(uuid4().bytes).hexdigest()


@pytest.mark.skipif(not _db_available(), reason="Database unavailable")
def test_apply_runs_columns():
    _require_wp_cl_012()
    with engine.begin() as conn:
        columns = get_columns(conn, "control_list_apply_runs")
    for name in (
        "apply_run_id",
        "import_run_id",
        "review_run_key",
        "plan_key",
        "plan_fingerprint",
        "plan_snapshot",
        "status",
        "requested_by_user_id",
        "started_at",
        "completed_at",
        "failed_at",
        "failure_code",
        "failure_message",
        "created_at",
        "updated_at",
    ):
        assert name in columns


@pytest.mark.skipif(not _db_available(), reason="Database unavailable")
def test_apply_actions_columns():
    _require_wp_cl_012()
    with engine.begin() as conn:
        columns = get_columns(conn, "control_list_apply_actions")
    for name in (
        "apply_action_execution_id",
        "apply_run_id",
        "action_index",
        "action_type",
        "target_aggregate",
        "source_reference",
        "idempotency_key",
        "action_fingerprint",
        "status",
        "attempt_count",
        "result_payload",
    ):
        assert name in columns


@pytest.mark.skipif(not _db_available(), reason="Database unavailable")
def test_unique_identity_constraints_fail_closed(seed):
    _require_wp_cl_012()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        import_run_id = conn.execute(
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
                "filename": f"pytest_wp_cl_012_{suffix}.xlsx",
                "sha256": _sample_sha256(),
                "imported_by": int(seed["initiator_user_id"]),
            },
        ).scalar_one()
        run_id = conn.execute(
            text(
                """
                INSERT INTO public.control_list_apply_runs (
                    import_run_id,
                    review_run_key,
                    plan_key,
                    plan_fingerprint,
                    plan_snapshot,
                    status
                )
                VALUES (
                    :import_run_id,
                    'review:test:1',
                    'cl-plan:test:1:abc',
                    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                    '{"review_run_key":"review:test:1","actions":[]}'::jsonb,
                    'pending'
                )
                RETURNING apply_run_id
                """
            ),
            {"import_run_id": import_run_id},
        ).scalar_one()
        conn.execute(text("SAVEPOINT duplicate_plan_fingerprint"))
        with pytest.raises(Exception):
            conn.execute(
                text(
                    """
                    INSERT INTO public.control_list_apply_runs (
                        import_run_id,
                        review_run_key,
                        plan_key,
                        plan_fingerprint,
                        plan_snapshot,
                        status
                    )
                    VALUES (
                        :import_run_id,
                        'review:test:2',
                        'cl-plan:test:2:abc',
                        'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                        '{"review_run_key":"review:test:2","actions":[]}'::jsonb,
                        'pending'
                    )
                    """
                ),
                {"import_run_id": import_run_id},
            )
        conn.execute(text("ROLLBACK TO SAVEPOINT duplicate_plan_fingerprint"))
        conn.execute(
            text(
                """
                INSERT INTO public.control_list_apply_actions (
                    apply_run_id,
                    action_index,
                    action_type,
                    target_aggregate,
                    source_reference,
                    idempotency_key,
                    action_fingerprint,
                    status
                )
                VALUES (
                    :apply_run_id,
                    0,
                    'skip',
                    'person',
                    'row:1',
                    'cl-apply:test-identity-key',
                    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
                    'pending'
                )
                """
            ),
            {"apply_run_id": run_id},
        )
        conn.execute(text("SAVEPOINT duplicate_idempotency_key"))
        with pytest.raises(Exception):
            conn.execute(
                text(
                    """
                    INSERT INTO public.control_list_apply_actions (
                        apply_run_id,
                        action_index,
                        action_type,
                        target_aggregate,
                        source_reference,
                        idempotency_key,
                        action_fingerprint,
                        status
                    )
                    VALUES (
                        :apply_run_id,
                        1,
                        'skip',
                        'person',
                        'row:2',
                        'cl-apply:test-identity-key',
                        'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
                        'pending'
                    )
                    """
                ),
                {"apply_run_id": run_id},
            )
        conn.execute(text("ROLLBACK TO SAVEPOINT duplicate_idempotency_key"))
        conn.execute(
            text("DELETE FROM public.control_list_apply_runs WHERE import_run_id = :id"),
            {"id": import_run_id},
        )
        conn.execute(
            text("DELETE FROM public.control_list_import_runs WHERE import_run_id = :id"),
            {"id": import_run_id},
        )
    assert not hasattr(SqlAlchemyApplyExecutionRepository, "reset_failed_run_for_retry")


@pytest.mark.skipif(not _db_available(), reason="Database unavailable")
def test_indexes_exist():
    _require_wp_cl_012()
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename IN ('control_list_apply_runs', 'control_list_apply_actions')
                """
            )
        ).all()
    index_names = {row.indexname for row in rows}
    for expected in EXPECTED_INDEXES:
        assert expected in index_names
