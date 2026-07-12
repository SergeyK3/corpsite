# tests/operational_orders/conftest.py
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.operational_orders.repository import OO_TABLES, operational_orders_available
from tests.conftest import auth_headers, get_columns, insert_returning_id, table_exists

DDL_REVISION = "w7x8y9z0a1b2"


def _schema_available() -> bool:
    return operational_orders_available()


def _require_schema() -> None:
    if not _schema_available():
        pytest.skip(
            f"OO-IMP-001 schema missing — run: alembic upgrade head (revision {DDL_REVISION})"
        )


@pytest.fixture(scope="session")
def _require_oo_schema_fixture():
    _require_schema()


def _grant_user_permission(conn, user_id: int, permission_code: str) -> None:
    role_row = conn.execute(
        text(
            """
            SELECT access_role_id
            FROM public.access_roles
            WHERE code = :code
            LIMIT 1
            """
        ),
        {"code": permission_code},
    ).fetchone()
    if not role_row:
        return
    conn.execute(
        text(
            """
            INSERT INTO public.access_grants (
                access_role_id, target_type, target_id, granted_by_user_id, reason
            )
            SELECT :access_role_id, 'USER', :user_id, :user_id, :reason
            WHERE NOT EXISTS (
                SELECT 1
                FROM public.access_grants g
                WHERE g.active_flag = TRUE
                  AND g.access_role_id = :access_role_id
                  AND g.target_type = 'USER'
                  AND g.target_id = :user_id
            )
            """
        ),
        {
            "access_role_id": int(role_row[0]),
            "user_id": int(user_id),
            "reason": f"OO test grant {permission_code}",
        },
    )


@pytest.fixture
def oo_intake_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def oo_regular_headers(seed):
    with engine.begin() as conn:
        _grant_user_permission(conn, int(seed["executor_user_id"]), "OPERATIONAL_ORDERS_INTAKE_CREATE")
        _grant_user_permission(conn, int(seed["executor_user_id"]), "OPERATIONAL_ORDERS_INTAKE_READ")
        _grant_user_permission(conn, int(seed["executor_user_id"]), "OPERATIONAL_ORDERS_INTAKE_OPERATE")
    return auth_headers(seed["executor_user_id"])


def cleanup_workspace(conn, workspace_id: int) -> None:
    for table in reversed(OO_TABLES):
        if table_exists(conn, table):
            conn.execute(
                text(f"DELETE FROM public.{table} WHERE workspace_id = :workspace_id"),
                {"workspace_id": int(workspace_id)},
            )
