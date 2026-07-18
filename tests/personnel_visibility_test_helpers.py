"""Test helpers for ADR-042 personnel visibility + dept-scoped RBAC."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.access_grant_service import grant_access
from tests.conftest import table_exists

ACCESS_MANAGER_CODE = "ACCESS_MANAGER"


def require_access_registry() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "access_roles"):
            pytest.skip("access_roles missing")
        row = conn.execute(
            text(
                """
                SELECT access_role_id
                FROM public.access_roles
                WHERE code = :code
                LIMIT 1
                """
            ),
            {"code": ACCESS_MANAGER_CODE},
        ).first()
        if not row:
            pytest.skip(f"{ACCESS_MANAGER_CODE} access role missing")


def grant_dept_manager_visibility(
    user_id: int,
    *,
    granted_by_user_id: int,
) -> None:
    """Implicit MANAGER visibility (dept-scoped under DIRECTORY_RBAC_MODE=dept)."""
    require_access_registry()
    with engine.begin() as conn:
        role_id = conn.execute(
            text(
                """
                SELECT access_role_id
                FROM public.access_roles
                WHERE code = :code
                LIMIT 1
                """
            ),
            {"code": ACCESS_MANAGER_CODE},
        ).scalar_one()
    grant_access(
        access_role_id=int(role_id),
        target_type="USER",
        target_id=int(user_id),
        granted_by_user_id=int(granted_by_user_id),
    )


def revoke_user_access_grants(user_id: int) -> None:
    with engine.begin() as conn:
        if table_exists(conn, "access_grants"):
            conn.execute(
                text(
                    """
                    DELETE FROM public.access_grants
                    WHERE target_type = 'USER' AND target_id = :uid
                    """
                ),
                {"uid": int(user_id)},
            )
