# tests/test_org_scope_resolver.py
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.org_scope.resolver import (
    load_department_groups,
    parse_org_group_id,
    parse_org_unit_id,
    resolve_group_id_for_unit,
    resolve_subtree_unit_ids,
    task_effective_owner_unit_sql,
    validate_org_group_exists,
)
from app.services.tasks_router import _task_effective_org_unit_sql


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def test_parse_org_group_id_none_and_invalid():
    assert parse_org_group_id(None) is None
    assert parse_org_group_id(0) is None
    assert parse_org_group_id(-1) is None
    assert parse_org_group_id("abc") is None
    assert parse_org_group_id("") is None


def test_parse_org_group_id_valid():
    assert parse_org_group_id(1) == 1
    assert parse_org_group_id("3") == 3


def test_parse_org_unit_id_matches_group_parser():
    assert parse_org_unit_id(None) is None
    assert parse_org_unit_id(2) == 2


def test_task_effective_owner_unit_sql_matches_tasks_router_helper():
    assert task_effective_owner_unit_sql() == _task_effective_org_unit_sql("t", "rt")
    assert task_effective_owner_unit_sql(task_alias="tx", regular_task_alias="rtx") == (
        _task_effective_org_unit_sql("tx", "rtx")
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_resolve_group_id_for_unit_found():
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT unit_id, group_id
                FROM public.org_units
                WHERE group_id IS NOT NULL
                ORDER BY unit_id
                LIMIT 1
                """
            )
        ).mappings().first()
        if not row:
            pytest.skip("no org_units with group_id in database")

        unit_id = int(row["unit_id"])
        expected = int(row["group_id"])
        assert resolve_group_id_for_unit(conn, unit_id=unit_id) == expected


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_resolve_group_id_for_unit_missing():
    with engine.begin() as conn:
        assert resolve_group_id_for_unit(conn, unit_id=999999999) is None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_resolve_subtree_unit_ids_includes_root_and_children():
    with engine.begin() as conn:
        root = conn.execute(
            text(
                """
                SELECT parent.unit_id AS root_unit_id
                FROM public.org_units parent
                WHERE EXISTS (
                    SELECT 1
                    FROM public.org_units child
                    WHERE child.parent_unit_id = parent.unit_id
                )
                ORDER BY parent.unit_id
                LIMIT 1
                """
            )
        ).mappings().first()
        if not root:
            any_unit = conn.execute(
                text("SELECT unit_id FROM public.org_units ORDER BY unit_id LIMIT 1")
            ).mappings().first()
            if not any_unit:
                pytest.skip("no org_units in database")
            root_unit_id = int(any_unit["unit_id"])
            ids = resolve_subtree_unit_ids(conn, root_unit_id=root_unit_id)
            assert root_unit_id in ids
            return

        root_unit_id = int(root["root_unit_id"])
        ids = resolve_subtree_unit_ids(conn, root_unit_id=root_unit_id)
        assert root_unit_id in ids
        assert len(ids) >= 2


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_resolve_subtree_unit_ids_empty_for_unknown_root():
    with engine.begin() as conn:
        assert resolve_subtree_unit_ids(conn, root_unit_id=999999999) == []


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_load_department_groups_returns_ordered():
    with engine.begin() as conn:
        groups = load_department_groups(conn, limit=50, offset=0)
        if not groups:
            pytest.skip("deps_group is empty")
        ids = [g.group_id for g in groups]
        assert ids == sorted(ids)
        assert all(g.group_name for g in groups)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_validate_org_group_exists():
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT group_id FROM public.deps_group ORDER BY group_id LIMIT 1")
        ).mappings().first()
        if not row:
            pytest.skip("deps_group is empty")
        gid = int(row["group_id"])
        assert validate_org_group_exists(conn, org_group_id=gid) is True
        assert validate_org_group_exists(conn, org_group_id=999999999) is False
