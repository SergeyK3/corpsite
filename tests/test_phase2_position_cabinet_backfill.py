"""Backfill tests for ADR-050 Phase 2.2 (legacy staffing → Position + Cabinet + mapping)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import get_columns, insert_returning_id, table_exists

DDL_REVISION = "k5l6m7n8o9p0"
BACKFILL_REVISION = "l6m7n8o9p0q1"

PHASE2_TABLES = (
    "org_unique_position",
    "position_cabinet",
    "permission_template",
    "legacy_position_mapping",
)

_INVENTORY_SQL = """
    SELECT COUNT(*) AS pair_count
    FROM (
        SELECT DISTINCT pairs.org_unit_id, pairs.catalog_position_id
        FROM (
            SELECT e.org_unit_id, e.position_id AS catalog_position_id
            FROM public.employees e
            WHERE e.org_unit_id IS NOT NULL
              AND e.position_id IS NOT NULL
            UNION
            SELECT pa.org_unit_id, pa.position_id AS catalog_position_id
            FROM public.person_assignments pa
            WHERE pa.org_unit_id IS NOT NULL
              AND pa.position_id IS NOT NULL
        ) pairs
        INNER JOIN public.org_units ou ON ou.unit_id = pairs.org_unit_id
        INNER JOIN public.positions pos ON pos.position_id = pairs.catalog_position_id
    ) inv
"""

_BACKFILL_COUNT_SQL = """
    SELECT
        (SELECT COUNT(*) FROM public.org_unique_position) AS org_unique_positions,
        (SELECT COUNT(*) FROM public.position_cabinet) AS position_cabinets,
        (SELECT COUNT(*) FROM public.permission_template) AS permission_templates,
        (SELECT COUNT(*) FROM public.legacy_position_mapping) AS legacy_mappings
"""


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _phase2_available() -> bool:
    with engine.begin() as conn:
        return all(table_exists(conn, table) for table in PHASE2_TABLES)


def _alembic_config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", str(engine.url.render_as_string(hide_password=False)))
    return cfg


def _require_phase2() -> None:
    if not _phase2_available():
        pytest.skip(
            f"ADR-050 Phase 2.1 tables missing — run: alembic upgrade head "
            f"(revisions {DDL_REVISION}, {BACKFILL_REVISION})"
        )


def _backfill_migration_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/l6m7n8o9p0q1_adr050_phase2_2_position_cabinet_backfill.py"
    )
    spec = importlib.util.spec_from_file_location("_adr050_backfill_mod", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load backfill migration from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_backfill_downgrade_upgrade(conn) -> None:
    ctx = MigrationContext.configure(conn)
    mod = _backfill_migration_module()
    with Operations.context(ctx):
        mod.downgrade()
        mod.upgrade()


def _insert_position(conn, *, name: str) -> int:
    cols = get_columns(conn, "positions")
    values: dict = {"name": name}
    if "category" in cols:
        values["category"] = "other"
    return insert_returning_id(
        conn,
        table="positions",
        id_col="position_id",
        values=values,
    )


def _insert_employee_with_pair(conn, *, org_unit_id: int, position_id: int, suffix: str) -> int:
    cols = get_columns(conn, "employees")
    values: dict = {
        "full_name": f"Pytest Backfill Employee {suffix}",
        "org_unit_id": org_unit_id,
        "position_id": position_id,
        "is_active": True,
    }
    if "operational_status" in cols:
        values["operational_status"] = "active"
    return insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values=values,
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_backfill_migration_revision_chain():
    script = ScriptDirectory.from_config(_alembic_config())
    ddl = script.get_revision(DDL_REVISION)
    backfill = script.get_revision(BACKFILL_REVISION)
    assert ddl is not None
    assert backfill is not None
    assert backfill.down_revision == DDL_REVISION


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_backfill_creates_expected_rows(seed):
    _require_phase2()

    suffix = uuid4().hex[:8]
    employee_id: int | None = None
    position_id: int | None = None
    unit_id = int(seed["unit_id"])

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            position_id = _insert_position(conn, name=f"pytest_backfill_pos_{suffix}")
            employee_id = _insert_employee_with_pair(
                conn,
                org_unit_id=unit_id,
                position_id=position_id,
                suffix=suffix,
            )

            before = conn.execute(text(_BACKFILL_COUNT_SQL)).mappings().one()
            pair_exists_before = conn.execute(
                text(
                    """
                    SELECT COUNT(*)::bigint
                    FROM public.legacy_position_mapping
                    WHERE org_unit_id = :org_unit_id
                      AND catalog_position_id = :catalog_position_id
                    """
                ),
                {"org_unit_id": unit_id, "catalog_position_id": position_id},
            ).scalar_one()
            assert int(pair_exists_before) == 0

            _run_backfill_downgrade_upgrade(conn)
            after = conn.execute(text(_BACKFILL_COUNT_SQL)).mappings().one()

            pair_exists_after = conn.execute(
                text(
                    """
                    SELECT COUNT(*)::bigint
                    FROM public.legacy_position_mapping
                    WHERE org_unit_id = :org_unit_id
                      AND catalog_position_id = :catalog_position_id
                    """
                ),
                {"org_unit_id": unit_id, "catalog_position_id": position_id},
            ).scalar_one()
            assert int(pair_exists_after) == 1
            assert int(after["org_unique_positions"]) >= int(before["org_unique_positions"]) + 1
            assert int(after["position_cabinets"]) >= int(before["position_cabinets"]) + 1
            assert int(after["permission_templates"]) >= int(before["permission_templates"]) + 1
            assert int(after["legacy_mappings"]) >= int(before["legacy_mappings"]) + 1

            mapping = conn.execute(
                text(
                    """
                    SELECT org_unique_position_id
                    FROM public.legacy_position_mapping
                    WHERE org_unit_id = :org_unit_id
                      AND catalog_position_id = :catalog_position_id
                    """
                ),
                {"org_unit_id": unit_id, "catalog_position_id": position_id},
            ).mappings().one()

            oup = conn.execute(
                text(
                    """
                    SELECT org_unique_position_id
                    FROM public.org_unique_position
                    WHERE org_unit_id = :org_unit_id
                      AND catalog_position_id = :catalog_position_id
                    """
                ),
                {"org_unit_id": unit_id, "catalog_position_id": position_id},
            ).mappings().one()
            assert int(mapping["org_unique_position_id"]) == int(oup["org_unique_position_id"])
        finally:
            trans.rollback()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_backfill_idempotent_no_duplicates(seed):
    _require_phase2()

    suffix = uuid4().hex[:8]
    unit_id = int(seed["unit_id"])

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            position_id = _insert_position(conn, name=f"pytest_idempotent_pos_{suffix}")
            _insert_employee_with_pair(
                conn,
                org_unit_id=unit_id,
                position_id=position_id,
                suffix=suffix,
            )

            _run_backfill_downgrade_upgrade(conn)
            first = conn.execute(text(_BACKFILL_COUNT_SQL)).mappings().one()
            _run_backfill_downgrade_upgrade(conn)
            second = conn.execute(text(_BACKFILL_COUNT_SQL)).mappings().one()

            assert dict(first) == dict(second)
        finally:
            trans.rollback()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_every_org_unique_position_has_exactly_one_cabinet(seed):
    _require_phase2()

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            _run_backfill_downgrade_upgrade(conn)
            orphans = conn.execute(
                text(
                    """
                    SELECT oup.org_unique_position_id
                    FROM public.org_unique_position oup
                    LEFT JOIN public.position_cabinet pc
                      ON pc.org_unique_position_id = oup.org_unique_position_id
                    GROUP BY oup.org_unique_position_id
                    HAVING COUNT(pc.position_cabinet_id) <> 1
                    """
                )
            ).fetchall()
            assert orphans == []
        finally:
            trans.rollback()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_every_cabinet_has_one_permission_template(seed):
    _require_phase2()

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            _run_backfill_downgrade_upgrade(conn)
            violations = conn.execute(
                text(
                    """
                    SELECT pc.position_cabinet_id, COUNT(pt.permission_template_id) AS template_count
                    FROM public.position_cabinet pc
                    LEFT JOIN public.permission_template pt
                      ON pt.position_cabinet_id = pc.position_cabinet_id
                    GROUP BY pc.position_cabinet_id
                    HAVING COUNT(pt.permission_template_id) <> 1
                    """
                )
            ).fetchall()
            assert violations == []

            null_role_only = conn.execute(
                text(
                    """
                    SELECT permission_template_id
                    FROM public.permission_template
                    WHERE role_id IS NOT NULL
                    """
                )
            ).fetchall()
            assert null_role_only == []
        finally:
            trans.rollback()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_legacy_mapping_points_to_existing_org_unique_position(seed):
    _require_phase2()

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            _run_backfill_downgrade_upgrade(conn)
            dangling = conn.execute(
                text(
                    """
                    SELECT lpm.legacy_position_mapping_id
                    FROM public.legacy_position_mapping lpm
                    LEFT JOIN public.org_unique_position oup
                      ON oup.org_unique_position_id = lpm.org_unique_position_id
                    WHERE oup.org_unique_position_id IS NULL
                    """
                )
            ).fetchall()
            assert dangling == []

            mismatched = conn.execute(
                text(
                    """
                    SELECT lpm.legacy_position_mapping_id
                    FROM public.legacy_position_mapping lpm
                    JOIN public.org_unique_position oup
                      ON oup.org_unique_position_id = lpm.org_unique_position_id
                    WHERE lpm.org_unit_id <> oup.org_unit_id
                       OR lpm.catalog_position_id <> oup.catalog_position_id
                       OR lpm.client_scope_id <> oup.client_scope_id
                    """
                )
            ).fetchall()
            assert mismatched == []
        finally:
            trans.rollback()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_backfill_covers_full_inventory(seed):
    _require_phase2()

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            _run_backfill_downgrade_upgrade(conn)
            inventory_count = int(conn.execute(text(_INVENTORY_SQL)).scalar() or 0)
            mapping_count = int(
                conn.execute(text("SELECT COUNT(*) FROM public.legacy_position_mapping")).scalar() or 0
            )
            assert mapping_count >= inventory_count
        finally:
            trans.rollback()
