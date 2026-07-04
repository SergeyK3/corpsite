# tests/test_adr042_phase_b2_schema.py
"""Schema tests for ADR-042 Phase B2 (persons, assignments, enrollment, access)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import text

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.db.engine import engine
from tests.conftest import get_columns, insert_returning_id, table_exists

DDL_REVISION = "u3v4w5x6y7z8"
BACKFILL_REVISION = "v4w5x6y7z8a9"
PREVIOUS_REVISION = "t2u3v4w5x6y7"

PHASE_B2_TABLES = (
    "persons",
    "person_assignments",
    "employee_assignment_links",
    "enrollment_queue",
    "enrollment_history",
    "access_roles",
    "access_grants",
    "security_audit_log",
)

ACCESS_ROLE_CODES = (
    "ACCESS_NONE",
    "ACCESS_OBSERVER",
    "ACCESS_MANAGER",
    "ACCESS_ADMIN",
    "SYSADMIN_CABINET",
    "HR_ENROLLMENT_MANAGER",
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
            f"ADR-042 Phase B2 tables missing — run: alembic upgrade head "
            f"(revisions {DDL_REVISION}, {BACKFILL_REVISION})"
        )


def _expect_sql_failure(sql: str, params: dict | None = None) -> None:
    with engine.begin() as conn:
        with pytest.raises(Exception):
            conn.execute(text(sql), params or {})


def _backfill_migration_module():
    """Load ADR-042 B2.3 backfill revision module without Alembic chain traversal."""
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/v4w5x6y7z8a9_adr042_phase_b2_3_backfill.py"
    )
    spec = importlib.util.spec_from_file_location("_adr042_backfill_mod", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load backfill migration from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _clear_backfill_downgrade_blockers(conn) -> None:
    """Drop head-era FK rows that block B2.3 backfill downgrade on a live DB.

    identity_reconciliation_items (ADR-044 B2) post-dates the backfill revision and
    holds ON DELETE RESTRICT on person_id. Clearing those rows is test-only scaffolding
    so we can exercise backfill downgrade/upgrade without broad Alembic rollback.
    """
    if table_exists(conn, "identity_reconciliation_items"):
        conn.execute(
            text(
                """
                DELETE FROM public.identity_reconciliation_items i
                USING public.persons p
                WHERE i.person_id = p.person_id
                  AND p.source = 'migration'
                """
            )
        )


def _run_backfill_downgrade_upgrade(conn) -> None:
    """Invoke v4w5x6y7z8a9 downgrade()+upgrade() in an Alembic Operations context.

    Direct invocation exercises only the B2.3 backfill revision. It does not run
    Alembic chain rollback (e.g. ADR-039 h7i8j9 chk_employee_events_event_type),
    which is intentionally out of scope for this ADR-042 test.
    """
    ctx = MigrationContext.configure(conn)
    mod = _backfill_migration_module()
    with Operations.context(ctx):
        mod.downgrade()
        mod.upgrade()


_BACKFILL_COUNT_SQL = """
    SELECT
        (SELECT COUNT(*) FROM public.persons WHERE source = 'migration') AS persons,
        (SELECT COUNT(*) FROM public.person_assignments WHERE source = 'migration') AS assignments,
        (SELECT COUNT(*) FROM public.employees WHERE person_id IS NOT NULL) AS linked_employees,
        (SELECT COUNT(*) FROM public.employee_assignment_links) AS links
"""


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_revision_chain():
    script = ScriptDirectory.from_config(_alembic_config())
    ddl = script.get_revision(DDL_REVISION)
    backfill = script.get_revision(BACKFILL_REVISION)
    assert ddl is not None
    assert ddl.down_revision == PREVIOUS_REVISION
    assert backfill is not None
    assert backfill.down_revision == DDL_REVISION


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_phase_b2_tables_exist():
    _require_phase_b2()
    with engine.begin() as conn:
        for table in PHASE_B2_TABLES:
            assert table_exists(conn, table), table


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_employees_and_users_extension_columns():
    _require_phase_b2()
    with engine.begin() as conn:
        emp_cols = get_columns(conn, "employees")
        user_cols = get_columns(conn, "users")
    for col in (
        "person_id",
        "operational_status",
        "enrolled_at",
        "enrolled_by_user_id",
        "enrollment_source",
        "updated_at",
    ):
        assert col in emp_cols, col
    for col in (
        "must_change_password",
        "password_changed_at",
        "temp_password_expires_at",
        "failed_login_count",
        "locked_at",
        "locked_until",
        "locked_reason",
        "last_login_at",
        "last_failed_login_at",
        "token_version",
    ):
        assert col in user_cols, col


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_access_roles_seed_idempotent():
    _require_phase_b2()
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT code, access_level, level_rank, is_system, is_active
                FROM public.access_roles
                WHERE code = ANY(:codes)
                ORDER BY level_rank
                """
            ),
            {"codes": list(ACCESS_ROLE_CODES)},
        ).mappings().all()
    assert len(rows) == len(ACCESS_ROLE_CODES)
    ranks = {r["code"]: int(r["level_rank"]) for r in rows}
    assert ranks["ACCESS_NONE"] == 0
    assert ranks["ACCESS_OBSERVER"] == 10
    assert ranks["ACCESS_MANAGER"] == 20
    assert ranks["ACCESS_ADMIN"] == 30
    assert all(bool(r["is_system"]) for r in rows)
    assert all(bool(r["is_active"]) for r in rows)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_person_match_key_unique_active(seed):
    _require_phase_b2()
    suffix = uuid4().hex[:8]
    match_key = f"name:pytest person {suffix}"

    with engine.begin() as conn:
        person_id = insert_returning_id(
            conn,
            table="persons",
            id_col="person_id",
            values={
                "full_name": f"Pytest Person {suffix}",
                "match_key": match_key,
                "source": "manual",
                "person_status": "active",
            },
        )
        assert person_id > 0

    _expect_sql_failure(
        """
        INSERT INTO public.persons (full_name, match_key, source, person_status)
        VALUES (:full_name, :match_key, 'manual', 'active')
        """,
        {
            "full_name": f"Duplicate Person {suffix}",
            "match_key": match_key,
        },
    )

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.persons WHERE person_id = :id"),
            {"id": person_id},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_backfill_idempotent_counts_stable(seed):
    _require_phase_b2()

    # Do not use command.downgrade(cfg, BACKFILL_REVISION) from head:
    # Alembic "downgrade to" a revision keeps that revision applied and runs
    # downgrade() on every *later* revision first — not on BACKFILL_REVISION
    # itself. From head that traverses ADR-039 h7i8j9 (employee_events CHECK
    # constraint rollback), which is intentionally out of scope here and fails
    # on valid production rows (e.g. EMPLOYEE_ENROLLED_FROM_IMPORT).
    #
    # Instead, invoke v4w5x6y7z8a9 downgrade()+upgrade() directly via
    # _run_backfill_downgrade_upgrade() so only backfill data is undone and
    # re-applied. Verify two consecutive cycles yield identical counts.
    #
    # The whole test runs in a rolled-back transaction; head-era FK blockers
    # cleared by _clear_backfill_downgrade_blockers() are not persisted.
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            _clear_backfill_downgrade_blockers(conn)
            _run_backfill_downgrade_upgrade(conn)
            before = conn.execute(text(_BACKFILL_COUNT_SQL)).mappings().one()
            _run_backfill_downgrade_upgrade(conn)
            after = conn.execute(text(_BACKFILL_COUNT_SQL)).mappings().one()
            assert dict(before) == dict(after)
        finally:
            trans.rollback()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_validation_sql_runs_clean(seed):
    _require_phase_b2()
    from pathlib import Path

    sql_path = Path("docs/adr/ADR-042-phase-b2-validation.sql")
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
