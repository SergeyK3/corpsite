"""Schema tests for ADR-050 Phase 2.1 (Position Cabinet foundation tables)."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.db.engine import engine
from tests.conftest import table_exists

DDL_REVISION = "k5l6m7n8o9p0"
PREVIOUS_REVISION = "j9k0l1m2n3o4"

PHASE2_TABLES = (
    "org_unique_position",
    "position_cabinet",
    "permission_template",
    "legacy_position_mapping",
)


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
            f"(revision {DDL_REVISION})"
        )


def _set_local_timeout(conn, *, milliseconds: int = 5000) -> None:
    conn.execute(text("SET LOCAL statement_timeout = :ms"), {"ms": str(milliseconds)})


def _table_column_names(conn, table: str) -> set[str]:
    rows = conn.execute(
        text(
            """
            SELECT a.attname
            FROM pg_attribute a
            JOIN pg_class t ON t.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = 'public'
              AND t.relname = :table
              AND a.attnum > 0
              AND NOT a.attisdropped
            """
        ),
        {"table": table},
    ).fetchall()
    return {str(row[0]) for row in rows}


def _count_unique_on_column(conn, *, table: str, column: str) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE n.nspname = 'public'
                  AND t.relname = :table
                  AND c.contype = 'u'
                  AND pg_get_constraintdef(c.oid) ILIKE :column_pattern
                """
            ),
            {"table": table, "column_pattern": f"%{column}%"},
        ).scalar()
        or 0
    )


def _count_fk_to_table(
    conn,
    *,
    table: str,
    ref_table: str,
    column: str | None = None,
) -> int:
    params: dict[str, str] = {"table": table, "ref_table": ref_table}
    column_filter = ""
    if column is not None:
        column_filter = "AND pg_get_constraintdef(c.oid) ILIKE :column_pattern"
        params["column_pattern"] = f"%{column}%"

    return int(
        conn.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                JOIN pg_class rt ON rt.oid = c.confrelid
                JOIN pg_namespace rn ON rn.oid = rt.relnamespace
                WHERE n.nspname = 'public'
                  AND t.relname = :table
                  AND rn.nspname = 'public'
                  AND rt.relname = :ref_table
                  AND c.contype = 'f'
                  {column_filter}
                """
            ),
            params,
        ).scalar()
        or 0
    )


def _forbidden_fk_tables(conn, *, table: str, forbidden: list[str]) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT rt.relname
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            JOIN pg_class rt ON rt.oid = c.confrelid
            JOIN pg_namespace rn ON rn.oid = rt.relnamespace
            WHERE n.nspname = 'public'
              AND t.relname = :table
              AND rn.nspname = 'public'
              AND c.contype = 'f'
              AND rt.relname = ANY(:forbidden)
            ORDER BY rt.relname
            """
        ),
        {"table": table, "forbidden": forbidden},
    ).fetchall()
    return [str(row[0]) for row in rows]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_revision_chain():
    script = ScriptDirectory.from_config(_alembic_config())
    ddl = script.get_revision(DDL_REVISION)
    assert ddl is not None
    assert ddl.down_revision == PREVIOUS_REVISION


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_phase2_tables_exist():
    _require_phase2()
    with engine.begin() as conn:
        _set_local_timeout(conn)
        for table in PHASE2_TABLES:
            assert table_exists(conn, table), table


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_org_unique_position_columns():
    _require_phase2()
    with engine.begin() as conn:
        _set_local_timeout(conn)
        cols = _table_column_names(conn, "org_unique_position")
    for col in (
        "org_unique_position_id",
        "client_scope_id",
        "org_unit_id",
        "catalog_position_id",
        "lifecycle_status",
        "created_at",
        "updated_at",
    ):
        assert col in cols, col


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_position_cabinet_one_to_one_with_org_unique_position():
    _require_phase2()

    with engine.begin() as conn:
        _set_local_timeout(conn)
        assert table_exists(conn, "position_cabinet")
        cols = _table_column_names(conn, "position_cabinet")
        assert "position_cabinet_id" in cols
        assert "org_unique_position_id" in cols
        assert _count_unique_on_column(
            conn, table="position_cabinet", column="org_unique_position_id"
        ) >= 1
        assert _count_fk_to_table(
            conn,
            table="position_cabinet",
            ref_table="org_unique_position",
            column="org_unique_position_id",
        ) >= 1
        assert _forbidden_fk_tables(
            conn,
            table="position_cabinet",
            forbidden=["users", "persons", "employees", "person_assignments"],
        ) == []


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_permission_template_bound_to_cabinet_only():
    _require_phase2()

    with engine.begin() as conn:
        _set_local_timeout(conn)
        assert table_exists(conn, "permission_template")
        cols = _table_column_names(conn, "permission_template")
        for col in (
            "permission_template_id",
            "position_cabinet_id",
            "role_id",
            "is_active",
            "created_at",
            "updated_at",
        ):
            assert col in cols, col
        assert _count_unique_on_column(
            conn, table="permission_template", column="position_cabinet_id"
        ) >= 1
        assert _count_fk_to_table(
            conn,
            table="permission_template",
            ref_table="position_cabinet",
            column="position_cabinet_id",
        ) >= 1
        assert _count_fk_to_table(
            conn,
            table="permission_template",
            ref_table="roles",
            column="role_id",
        ) >= 1
        assert _forbidden_fk_tables(
            conn,
            table="permission_template",
            forbidden=["users", "persons", "employees", "person_assignments"],
        ) == []


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_legacy_position_mapping_unique_pair():
    _require_phase2()

    with engine.begin() as conn:
        _set_local_timeout(conn)
        assert table_exists(conn, "legacy_position_mapping")
        cols = _table_column_names(conn, "legacy_position_mapping")
        for col in (
            "legacy_position_mapping_id",
            "client_scope_id",
            "org_unit_id",
            "catalog_position_id",
            "org_unique_position_id",
        ):
            assert col in cols, col
        assert _count_unique_on_column(
            conn, table="legacy_position_mapping", column="org_unit_id"
        ) >= 1
        assert _count_unique_on_column(
            conn, table="legacy_position_mapping", column="org_unique_position_id"
        ) >= 1
        assert _count_fk_to_table(
            conn,
            table="legacy_position_mapping",
            ref_table="org_unique_position",
            column="org_unique_position_id",
        ) >= 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_org_unique_position_unique_client_org_catalog():
    _require_phase2()

    with engine.begin() as conn:
        _set_local_timeout(conn)
        assert _count_unique_on_column(
            conn, table="org_unique_position", column="catalog_position_id"
        ) >= 1
        constraint_defs = conn.execute(
            text(
                """
                SELECT pg_get_constraintdef(c.oid)
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE n.nspname = 'public'
                  AND t.relname = 'org_unique_position'
                  AND c.contype = 'u'
                """
            )
        ).fetchall()
        joined = " ".join(str(row[0]).lower() for row in constraint_defs)
        assert "client_scope_id" in joined
        assert "org_unit_id" in joined
        assert "catalog_position_id" in joined
