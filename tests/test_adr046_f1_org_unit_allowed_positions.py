"""Schema and API tests for ADR-046 F1 — org_unit_allowed_positions."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers, get_columns, insert_returning_id, table_exists

DDL_REVISION = "i9j0k1l2m3n4"
PREVIOUS_REVISION = "h8i9j0k1l2m3"
TABLE_NAME = "org_unit_allowed_positions"


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


def _list_positions(client, privileged_headers, **params):
    return client.get(
        "/directory/positions",
        params=params,
        headers=privileged_headers,
    )


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _alembic_config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", str(engine.url.render_as_string(hide_password=False)))
    return cfg


def _table_available() -> bool:
    with engine.begin() as conn:
        return table_exists(conn, TABLE_NAME)


def _create_unit(conn, *, name: str, group_id: int = 1) -> int:
    cols = get_columns(conn, "org_units")
    values: Dict[str, Any] = {"name": name}
    if "code" in cols:
        values["code"] = name
    if "group_id" in cols:
        values["group_id"] = group_id
    if "is_active" in cols:
        values["is_active"] = True
    return insert_returning_id(conn, table="org_units", id_col="unit_id", values=values)


def _create_position(conn, *, name: str) -> int:
    cols = get_columns(conn, "positions")
    values: Dict[str, Any] = {"name": name}
    if "category" in cols:
        values["category"] = "admin"
    return insert_returning_id(conn, table="positions", id_col="position_id", values=values)


def _insert_allowed_link(
    conn,
    *,
    org_unit_id: int,
    position_id: int,
    sort_order: Optional[int] = None,
    is_active: bool = True,
) -> int:
    return insert_returning_id(
        conn,
        table=TABLE_NAME,
        id_col="org_unit_allowed_position_id",
        values={
            "org_unit_id": int(org_unit_id),
            "position_id": int(position_id),
            "sort_order": sort_order,
            "is_active": bool(is_active),
        },
    )


def _cleanup_allowed_links(link_ids: List[int]) -> None:
    if not link_ids:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                f"DELETE FROM public.{TABLE_NAME} WHERE org_unit_allowed_position_id = ANY(:ids)"
            ),
            {"ids": [int(x) for x in link_ids]},
        )


def _cleanup_positions(position_ids: List[int]) -> None:
    if not position_ids:
        return
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.positions WHERE position_id = ANY(:ids)"),
            {"ids": [int(x) for x in position_ids]},
        )


def _cleanup_units(unit_ids: List[int]) -> None:
    if not unit_ids:
        return
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.org_units WHERE unit_id = ANY(:ids)"),
            {"ids": [int(x) for x in unit_ids]},
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_adr046_f1_table_exists_with_constraints():
    if not _table_available():
        pytest.skip(f"{TABLE_NAME} missing — run alembic upgrade head ({DDL_REVISION})")

    with engine.begin() as conn:
        cols = {row[0] for row in conn.execute(
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
            {"table": TABLE_NAME},
        ).fetchall()}

    for col in (
        "org_unit_allowed_position_id",
        "org_unit_id",
        "position_id",
        "sort_order",
        "is_active",
        "created_at",
        "updated_at",
    ):
        assert col in cols, col

    with engine.begin() as conn:
        unique_pairs = int(
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
                      AND pg_get_constraintdef(c.oid) ILIKE '%org_unit_id%'
                      AND pg_get_constraintdef(c.oid) ILIKE '%position_id%'
                    """
                ),
                {"table": TABLE_NAME},
            ).scalar()
            or 0
        )
        fk_org = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM pg_constraint c
                    JOIN pg_class t ON t.oid = c.conrelid
                    JOIN pg_namespace n ON n.oid = t.relnamespace
                    JOIN pg_class rt ON rt.oid = c.confrelid
                    WHERE n.nspname = 'public'
                      AND t.relname = :table
                      AND rt.relname = 'org_units'
                      AND c.contype = 'f'
                      AND pg_get_constraintdef(c.oid) ILIKE '%ON DELETE RESTRICT%'
                    """
                ),
                {"table": TABLE_NAME},
            ).scalar()
            or 0
        )
        fk_pos = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM pg_constraint c
                    JOIN pg_class t ON t.oid = c.conrelid
                    JOIN pg_namespace n ON n.oid = t.relnamespace
                    JOIN pg_class rt ON rt.oid = c.confrelid
                    WHERE n.nspname = 'public'
                      AND t.relname = :table
                      AND rt.relname = 'positions'
                      AND c.contype = 'f'
                      AND pg_get_constraintdef(c.oid) ILIKE '%ON DELETE RESTRICT%'
                    """
                ),
                {"table": TABLE_NAME},
            ).scalar()
            or 0
        )

    assert unique_pairs >= 1
    assert fk_org >= 1
    assert fk_pos >= 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_adr046_f1_migration_downgrade_upgrade_cycle():
    if not _table_available():
        pytest.skip(f"{TABLE_NAME} missing — run alembic upgrade head ({DDL_REVISION})")

    cfg = _alembic_config()
    command.downgrade(cfg, PREVIOUS_REVISION)
    with engine.begin() as conn:
        assert not table_exists(conn, TABLE_NAME)

    command.upgrade(cfg, DDL_REVISION)
    with engine.begin() as conn:
        assert table_exists(conn, TABLE_NAME)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_positions_scope_allowed_returns_unoccupied_allowed_links(client, privileged_headers):
    if not _table_available():
        pytest.skip(f"{TABLE_NAME} missing — run alembic upgrade head ({DDL_REVISION})")

    unique_allowed = "PytestAdr046AllowedOnly"
    unique_used = "PytestAdr046UsedOnly"
    created_links: List[int] = []
    created_positions: List[int] = []
    created_units: List[int] = []
    created_employee_names: List[str] = []

    try:
        with engine.begin() as conn:
            unit_id = _create_unit(conn, name="pytest_adr046_allowed_unit")
            created_units.append(unit_id)
            allowed_pos = _create_position(conn, name=unique_allowed)
            used_pos = _create_position(conn, name=unique_used)
            created_positions.extend([allowed_pos, used_pos])
            created_links.append(
                _insert_allowed_link(
                    conn,
                    org_unit_id=unit_id,
                    position_id=allowed_pos,
                    sort_order=10,
                )
            )
            created_links.append(
                _insert_allowed_link(
                    conn,
                    org_unit_id=unit_id,
                    position_id=used_pos,
                    sort_order=20,
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO public.employees (full_name, org_unit_id, position_id, is_active)
                    VALUES (:full_name, :org_unit_id, :position_id, TRUE)
                    """
                ),
                {
                    "full_name": "PytestAdr046UsedEmp",
                    "org_unit_id": unit_id,
                    "position_id": used_pos,
                },
            )
            created_employee_names.append("PytestAdr046UsedEmp")

        allowed_resp = _list_positions(
            client,
            privileged_headers,
            org_unit_id=unit_id,
            scope="allowed",
            q="PytestAdr046",
        )
        assert allowed_resp.status_code == 200, allowed_resp.text
        allowed_names = {row["name"] for row in allowed_resp.json()["items"]}
        assert unique_allowed in allowed_names
        assert unique_used in allowed_names

        used_resp = _list_positions(
            client,
            privileged_headers,
            org_unit_id=unit_id,
            scope="used",
            q="PytestAdr046",
        )
        assert used_resp.status_code == 200, used_resp.text
        used_names = {row["name"] for row in used_resp.json()["items"]}
        assert unique_used in used_names
        assert unique_allowed not in used_names

        default_resp = _list_positions(
            client,
            privileged_headers,
            org_unit_id=unit_id,
            q="PytestAdr046",
        )
        assert default_resp.status_code == 200, default_resp.text
        assert default_resp.json()["items"] == used_resp.json()["items"]
    finally:
        if created_employee_names:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM public.employees WHERE full_name = ANY(:names)"),
                    {"names": created_employee_names},
                )
        _cleanup_allowed_links(created_links)
        _cleanup_positions(created_positions)
        _cleanup_units(created_units)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_positions_scope_allowed_honors_sort_order(client, privileged_headers):
    if not _table_available():
        pytest.skip(f"{TABLE_NAME} missing — run alembic upgrade head ({DDL_REVISION})")

    prefix = "PytestAdr046Sort"
    created_links: List[int] = []
    created_positions: List[int] = []
    created_units: List[int] = []

    try:
        with engine.begin() as conn:
            unit_id = _create_unit(conn, name="pytest_adr046_sort_unit")
            created_units.append(unit_id)
            pos_b = _create_position(conn, name=f"{prefix}B")
            pos_a = _create_position(conn, name=f"{prefix}A")
            created_positions.extend([pos_a, pos_b])
            created_links.append(
                _insert_allowed_link(conn, org_unit_id=unit_id, position_id=pos_b, sort_order=20)
            )
            created_links.append(
                _insert_allowed_link(conn, org_unit_id=unit_id, position_id=pos_a, sort_order=10)
            )

        resp = _list_positions(
            client,
            privileged_headers,
            org_unit_id=unit_id,
            scope="allowed",
            q=prefix,
        )
        assert resp.status_code == 200, resp.text
        names = [row["name"] for row in resp.json()["items"]]
        assert names.index(f"{prefix}A") < names.index(f"{prefix}B")
    finally:
        _cleanup_allowed_links(created_links)
        _cleanup_positions(created_positions)
        _cleanup_units(created_units)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_positions_scope_allowed_excludes_inactive_links(client, privileged_headers):
    if not _table_available():
        pytest.skip(f"{TABLE_NAME} missing — run alembic upgrade head ({DDL_REVISION})")

    unique = "PytestAdr046Inactive"
    created_links: List[int] = []
    created_positions: List[int] = []
    created_units: List[int] = []

    try:
        with engine.begin() as conn:
            unit_id = _create_unit(conn, name="pytest_adr046_inactive_unit")
            created_units.append(unit_id)
            position_id = _create_position(conn, name=unique)
            created_positions.append(position_id)
            created_links.append(
                _insert_allowed_link(
                    conn,
                    org_unit_id=unit_id,
                    position_id=position_id,
                    sort_order=10,
                    is_active=False,
                )
            )

        resp = _list_positions(
            client,
            privileged_headers,
            org_unit_id=unit_id,
            scope="allowed",
            q=unique,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["total"] == 0
    finally:
        _cleanup_allowed_links(created_links)
        _cleanup_positions(created_positions)
        _cleanup_units(created_units)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_positions_scope_allowed_does_not_inherit_child_unit_links(client, privileged_headers):
    if not _table_available():
        pytest.skip(f"{TABLE_NAME} missing — run alembic upgrade head ({DDL_REVISION})")

    unique_child = "PytestAdr046AllowedChildOnly"
    created_links: List[int] = []
    created_positions: List[int] = []
    created_units: List[int] = []

    try:
        with engine.begin() as conn:
            cols = get_columns(conn, "org_units")
            if "parent_unit_id" not in cols:
                pytest.skip("org_units.parent_unit_id not available")

            parent_unit = _create_unit(conn, name="pytest_adr046_allowed_parent")
            child_unit = _create_unit(
                conn,
                name="pytest_adr046_allowed_child",
                group_id=1,
            )
            conn.execute(
                text(
                    """
                    UPDATE public.org_units
                    SET parent_unit_id = :parent_unit_id
                    WHERE unit_id = :child_unit_id
                    """
                ),
                {"parent_unit_id": parent_unit, "child_unit_id": child_unit},
            )
            created_units.extend([parent_unit, child_unit])

            position_id = _create_position(conn, name=unique_child)
            created_positions.append(position_id)
            created_links.append(
                _insert_allowed_link(
                    conn,
                    org_unit_id=child_unit,
                    position_id=position_id,
                    sort_order=10,
                )
            )

        parent_resp = _list_positions(
            client,
            privileged_headers,
            org_unit_id=parent_unit,
            scope="allowed",
            q=unique_child,
        )
        assert parent_resp.status_code == 200, parent_resp.text
        assert parent_resp.json()["total"] == 0

        child_resp = _list_positions(
            client,
            privileged_headers,
            org_unit_id=child_unit,
            scope="allowed",
            q=unique_child,
        )
        assert child_resp.status_code == 200, child_resp.text
        assert child_resp.json()["total"] == 1
    finally:
        _cleanup_allowed_links(created_links)
        _cleanup_positions(created_positions)
        _cleanup_units(created_units)


def test_list_positions_rejects_unknown_scope(client, privileged_headers):
    resp = _list_positions(
        client,
        privileged_headers,
        org_unit_id=1,
        scope="typical",
    )
    assert resp.status_code == 422


def test_list_positions_scope_allowed_requires_org_filter(client, privileged_headers):
    resp = _list_positions(client, privileged_headers, scope="allowed")
    assert resp.status_code == 422
