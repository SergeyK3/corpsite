# tests/operational_orders/conftest.py
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.operational_orders.repository import OO_TABLES, operational_orders_available
from tests.conftest import auth_headers, get_columns, insert_returning_id, table_exists

DDL_REVISION = "x8y9z0a1b2c3"


def _schema_available() -> bool:
    return operational_orders_available()


def _require_schema() -> None:
    if not _schema_available():
        pytest.skip(
            f"OO schema missing — run: alembic upgrade head (revision {DDL_REVISION})"
        )


@pytest.fixture(scope="session")
def _require_oo_schema_fixture():
    _require_schema()


def revoke_user_access_grants(conn, user_id: int) -> None:
    """Remove grants created by OO tests before seed teardown deletes users."""
    conn.execute(
        text(
            """
            DELETE FROM public.access_grants
            WHERE (target_type = 'USER' AND target_id = :user_id)
               OR granted_by_user_id = :user_id
            """
        ),
        {"user_id": int(user_id)},
    )


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
    user_id = int(seed["executor_user_id"])
    with engine.begin() as conn:
        _grant_user_permission(conn, user_id, "OPERATIONAL_ORDERS_INTAKE_CREATE")
        _grant_user_permission(conn, user_id, "OPERATIONAL_ORDERS_INTAKE_READ")
        _grant_user_permission(conn, user_id, "OPERATIONAL_ORDERS_INTAKE_OPERATE")
    try:
        yield auth_headers(user_id)
    finally:
        with engine.begin() as conn:
            revoke_user_access_grants(conn, user_id)


@pytest.fixture
def oo_editorial_headers(seed):
    user_id = int(seed["executor_user_id"])
    perms = (
        "OPERATIONAL_ORDERS_INTAKE_CREATE",
        "OPERATIONAL_ORDERS_INTAKE_READ",
        "OPERATIONAL_ORDERS_INTAKE_OPERATE",
        "OPERATIONAL_ORDERS_TRANSLATION_ASSIGN",
        "OPERATIONAL_ORDERS_TRANSLATION_WORK",
        "OPERATIONAL_ORDERS_CONTENT_CONFIRM",
        "OPERATIONAL_ORDERS_RECONCILE",
        "OPERATIONAL_ORDERS_EDITORIAL_READY",
    )
    with engine.begin() as conn:
        for perm in perms:
            _grant_user_permission(conn, user_id, perm)
    try:
        yield auth_headers(user_id)
    finally:
        with engine.begin() as conn:
            revoke_user_access_grants(conn, user_id)


# Child tables first — safe DELETE ... WHERE workspace_id (see OO FK graph).
OO_CLEANUP_TABLES = (
    "operational_order_bilingual_reconciliations",
    "operational_order_content_confirmations",
    "operational_order_translation_assignments",
    "operational_order_draft_audit",
    "operational_order_clarifications",
    "operational_order_text_provenance",
    "operational_order_draft_blocks",
    "operational_order_draft_workspaces",
)


def cleanup_workspace(conn, workspace_id: int) -> None:
    for table in OO_CLEANUP_TABLES:
        if table_exists(conn, table):
            conn.execute(
                text(f"DELETE FROM public.{table} WHERE workspace_id = :workspace_id"),
                {"workspace_id": int(workspace_id)},
            )
