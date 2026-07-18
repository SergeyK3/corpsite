# tests/test_adr043_phase_b2_schema.py
"""Schema tests for ADR-043 Phase B2 (personnel lifecycle DDL)."""
from __future__ import annotations

import importlib.util
import json
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import text

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.db.engine import engine
from tests.alembic_test_helpers import (
    assert_db_revision_unchanged,
    assert_revision_on_chain,
    exclusive_migration_cycle,
    get_current_db_revision,
)
from tests.conftest import get_columns, insert_returning_id, table_exists

DDL_REVISION = "x6y7z8a9b0c1"
PREVIOUS_REVISION = "w5x6y7z8a9b0"

PHASE_B2_TABLES = (
    "hr_source_files",
    "hr_override_stewardship_rules",
    "hr_review_overrides",
    "hr_review_override_history",
    "hr_personnel_change_events",
    "hr_snapshot_effective_entries",
)

STEWARDSHIP_PATTERNS = (
    "identity.iin",
    "identity.full_name",
    "roster.%",
    "training.%",
    "certificate.%",
    "category.%",
    "education.%",
    "specialty.%",
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _phase_b2_available() -> bool:
    with engine.begin() as conn:
        return all(table_exists(conn, table) for table in PHASE_B2_TABLES)


def _alembic_config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", str(engine.url.render_as_string(hide_password=False)))
    return cfg


def _require_phase_b2() -> None:
    if not _phase_b2_available():
        pytest.skip(
            f"ADR-043 Phase B2 tables missing — run: alembic upgrade head (revision {DDL_REVISION})"
        )


def _adr043_migration_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/x6y7z8a9b0c1_adr043_phase_b2_personnel_lifecycle_schema.py"
    )
    spec = importlib.util.spec_from_file_location("_adr043_phase_b2_mod", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load ADR-043 migration from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _expect_sql_failure(sql: str, params: dict | None = None) -> None:
    with engine.begin() as conn:
        with pytest.raises(Exception):
            conn.execute(text(sql), params or {})


def _expect_sql_failure_conn(conn, sql: str, params: dict | None = None) -> None:
    with pytest.raises(Exception):
        with conn.begin_nested():
            conn.execute(text(sql), params or {})


@contextmanager
def _isolated_conn():
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            yield conn
        finally:
            trans.rollback()


def _insert_override(
    conn,
    *,
    user_id: int,
    scope_key: str,
    field_path: str,
    status: str = "active",
    tier: int = 0,
    supersedes_override_id: int | None = None,
    approved_by_user_id: int | None = None,
    approved_at: str | None = None,
    justification: str | None = None,
) -> int:
    params = {
        "scope_type": scope_key.split(":", 1)[0],
        "scope_key": scope_key,
        "person_key": scope_key.split(":", 2)[1] if ":" in scope_key else None,
        "field_path": field_path,
        "override_value": json.dumps("test-value"),
        "tier": tier,
        "owner_domain": "HR",
        "status": status,
        "persistence_policy": "until_incoming_matches",
        "created_by_user_id": user_id,
        "creation_channel": "review_ui",
        "supersedes_override_id": supersedes_override_id,
        "approved_by_user_id": approved_by_user_id,
        "approved_at": approved_at,
        "justification": justification,
    }
    if tier >= 1 and justification is None:
        params["justification"] = "Pytest justification for override row"
    if approved_by_user_id is not None:
        params["approved_by_user_id"] = approved_by_user_id
    if approved_at is not None:
        params["approved_at"] = approved_at
    return insert_returning_id(
        conn,
        table="hr_review_overrides",
        id_col="override_id",
        values=params,
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_revision_chain():
    script = ScriptDirectory.from_config(_alembic_config())
    rev = script.get_revision(DDL_REVISION)
    assert rev is not None
    assert rev.down_revision == PREVIOUS_REVISION


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_phase_b2_tables_exist():
    _require_phase_b2()
    with engine.begin() as conn:
        for table in PHASE_B2_TABLES:
            assert table_exists(conn, table), table


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_alter_columns_exist():
    _require_phase_b2()
    with engine.begin() as conn:
        batch_cols = get_columns(conn, "hr_import_batches")
        eq_cols = get_columns(conn, "enrollment_queue")
    assert "source_file_id" in batch_cols
    assert "personnel_event_id" in eq_cols


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_stewardship_rules_seed():
    _require_phase_b2()
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT field_path_pattern, owner_domain, required_tier, active_flag
                FROM public.hr_override_stewardship_rules
                WHERE field_path_pattern = ANY(:patterns)
                ORDER BY priority
                """
            ),
            {"patterns": list(STEWARDSHIP_PATTERNS)},
        ).mappings().all()
    patterns_found = {r["field_path_pattern"] for r in rows}
    for pattern in STEWARDSHIP_PATTERNS:
        assert pattern in patterns_found, pattern
    iin = next(r for r in rows if r["field_path_pattern"] == "identity.iin")
    assert iin["owner_domain"] == "HR"
    assert int(iin["required_tier"]) == 2


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_constraint_rejects_invalid_scope_type(seed):
    _require_phase_b2()
    user_id = seed["executor_user_id"]
    with _isolated_conn() as conn:
        _expect_sql_failure_conn(
            conn,
            """
            INSERT INTO public.hr_review_overrides (
                scope_type, scope_key, field_path, override_value, tier, owner_domain,
                status, persistence_policy, created_by_user_id, creation_channel
            ) VALUES (
                'ROSTER_ENTRY', 'PERSON:match:bad', 'identity.iin', '"x"'::jsonb,
                0, 'HR', 'active', 'until_incoming_matches', :uid, 'review_ui'
            )
            """,
            {"uid": user_id},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_constraint_rejects_invalid_status(seed):
    _require_phase_b2()
    user_id = seed["executor_user_id"]
    with _isolated_conn() as conn:
        _expect_sql_failure_conn(
            conn,
            """
            INSERT INTO public.hr_review_overrides (
                scope_type, scope_key, field_path, override_value, tier, owner_domain,
                status, persistence_policy, created_by_user_id, creation_channel
            ) VALUES (
                'PERSON', 'PERSON:match:bad-status', 'note.text', '"x"'::jsonb,
                0, 'HR', 'draft', 'until_incoming_matches', :uid, 'review_ui'
            )
            """,
            {"uid": user_id},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_partial_unique_active_override(seed):
    _require_phase_b2()
    user_id = seed["executor_user_id"]
    suffix = uuid4().hex[:8]
    scope_key = f"PERSON:match:pytest-{suffix}"
    field_path = "note.text"

    with _isolated_conn() as conn:
        oid1 = _insert_override(
            conn,
            user_id=user_id,
            scope_key=scope_key,
            field_path=field_path,
            status="active",
        )
        assert oid1 > 0
        _expect_sql_failure_conn(
            conn,
            """
            INSERT INTO public.hr_review_overrides (
                scope_type, scope_key, field_path, override_value, tier, owner_domain,
                status, persistence_policy, created_by_user_id, creation_channel
            ) VALUES (
                'PERSON', :scope_key, :field_path, '"dup"'::jsonb,
                0, 'HR', 'active', 'until_incoming_matches', :uid, 'review_ui'
            )
            """,
            {"uid": user_id, "scope_key": scope_key, "field_path": field_path},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_pending_replacement_with_supersedes(seed):
    _require_phase_b2()
    user_id = seed["executor_user_id"]
    suffix = uuid4().hex[:8]
    scope_key = f"PERSON:match:pytest-pending-{suffix}"
    field_path = "identity.full_name"

    with _isolated_conn() as conn:
        active_id = _insert_override(
            conn,
            user_id=user_id,
            scope_key=scope_key,
            field_path=field_path,
            status="active",
            tier=1,
        )
        pending_id = _insert_override(
            conn,
            user_id=user_id,
            scope_key=scope_key,
            field_path=field_path,
            status="pending_approval",
            tier=2,
            supersedes_override_id=active_id,
            justification="Pending replacement for tier 2 test",
        )
        assert pending_id > active_id

        row = conn.execute(
            text(
                """
                SELECT status, supersedes_override_id
                FROM public.hr_review_overrides
                WHERE override_id = :id
                """
            ),
            {"id": pending_id},
        ).mappings().one()
        assert row["status"] == "pending_approval"
        assert int(row["supersedes_override_id"]) == active_id


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_tier2_active_requires_different_approver(seed):
    _require_phase_b2()
    user_id = seed["executor_user_id"]
    suffix = uuid4().hex[:8]
    scope_key = f"PERSON:match:pytest-tier2-{suffix}"

    with _isolated_conn() as conn:
        _expect_sql_failure_conn(
            conn,
            """
            INSERT INTO public.hr_review_overrides (
                scope_type, scope_key, field_path, override_value, tier, owner_domain,
                status, persistence_policy, created_by_user_id, creation_channel,
                approved_by_user_id, approved_at, justification, evidence_url
            ) VALUES (
                'PERSON', :scope_key, 'identity.iin', '"123456789012"'::jsonb,
                2, 'HR', 'active', 'manual_only_revoke', :uid, 'review_ui',
                :uid, now(), 'Same approver should fail', 'https://example.com/evidence'
            )
            """,
            {"uid": user_id, "scope_key": scope_key},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_override_history_append_only(seed):
    _require_phase_b2()
    user_id = seed["executor_user_id"]
    suffix = uuid4().hex[:8]
    scope_key = f"PERSON:match:pytest-history-{suffix}"

    with _isolated_conn() as conn:
        override_id = _insert_override(
            conn,
            user_id=user_id,
            scope_key=scope_key,
            field_path="note.text",
        )
        history_id = insert_returning_id(
            conn,
            table="hr_review_override_history",
            id_col="history_id",
            values={
                "override_id": override_id,
                "scope_key": scope_key,
                "event_type": "CREATED",
                "actor_user_id": user_id,
                "from_status": None,
                "to_status": "active",
                "field_path": "note.text",
                "new_value": json.dumps("test-value"),
            },
        )
        assert history_id > 0

        _expect_sql_failure_conn(
            conn,
            "DELETE FROM public.hr_review_override_history WHERE history_id = :id",
            {"id": history_id},
        )
        _expect_sql_failure_conn(
            conn,
            """
            UPDATE public.hr_review_override_history
            SET reason = 'mutated' WHERE history_id = :id
            """,
            {"id": history_id},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_personnel_event_hash_unique(seed):
    _require_phase_b2()
    event_hash = "a" * 64
    with _isolated_conn() as conn:
        snap_rows = conn.execute(
            text(
                """
                SELECT snapshot_id
                FROM public.hr_canonical_snapshots
                WHERE snapshot_id <> (
                    SELECT MIN(snapshot_id) FROM public.hr_canonical_snapshots
                )
                ORDER BY snapshot_id
                LIMIT 1
                """
            )
        ).fetchall()
        prev_row = conn.execute(
            text("SELECT MIN(snapshot_id) AS id FROM public.hr_canonical_snapshots")
        ).mappings().first()
        if not prev_row or prev_row["id"] is None or not snap_rows:
            pytest.skip("Need at least two canonical snapshots for personnel event test")

        prev_id = int(prev_row["id"])
        new_id = int(snap_rows[0][0])
        if prev_id == new_id:
            pytest.skip("Need distinct snapshot ids")

        eid1 = insert_returning_id(
            conn,
            table="hr_personnel_change_events",
            id_col="personnel_event_id",
            values={
                "previous_snapshot_id": prev_id,
                "snapshot_id": new_id,
                "person_key": f"match:pytest-{uuid4().hex[:8]}",
                "event_type": "FIELD_CHANGED",
                "event_hash": event_hash,
            },
        )
        assert eid1 > 0
        _expect_sql_failure_conn(
            conn,
            """
            INSERT INTO public.hr_personnel_change_events (
                previous_snapshot_id, snapshot_id, person_key, event_type, event_hash
            ) VALUES (:prev, :new, 'match:dup', 'FIELD_CHANGED', :hash)
            """,
            {"prev": prev_id, "new": new_id, "hash": event_hash},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_validation_sql_runs_on_empty_db(seed):
    _require_phase_b2()
    from pathlib import Path

    sql_path = Path("docs/adr/ADR-043-phase-b2-validation.sql")
    content = sql_path.read_text(encoding="utf-8")
    statements = [
        s.strip()
        for s in content.split(";")
        if s.strip() and not s.strip().startswith("--")
    ]
    with engine.begin() as conn:
        for stmt in statements:
            if not stmt.upper().startswith("SELECT"):
                continue
            conn.execute(text(stmt))


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_downgrade_upgrade():
    _require_phase_b2()
    assert_revision_on_chain(DDL_REVISION, cfg=_alembic_config())

    revision_before = get_current_db_revision()

    with exclusive_migration_cycle():
        with engine.connect() as conn:
            trans = conn.begin()
            try:
                mod = _adr043_migration_module()
                with Operations.context(MigrationContext.configure(conn)):
                    mod.downgrade()
                assert not table_exists(conn, "hr_review_overrides")
                with Operations.context(MigrationContext.configure(conn)):
                    mod.upgrade()
                for table in PHASE_B2_TABLES:
                    assert table_exists(conn, table), table
            finally:
                trans.rollback()

    revision_after = get_current_db_revision()
    assert_db_revision_unchanged(revision_before, revision_after)
