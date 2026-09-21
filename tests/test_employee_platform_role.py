"""Security contract for the neutral EMPLOYEE Platform Role."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.security.admin_permissions import (
    has_any_admin_api_permission,
    has_any_personnel_read_permission,
    has_hr_governance_permission,
)
from app.security.directory_scope import is_privileged
from tests.ppr.conftest import ppr_db_available


EMPLOYEE_ROLE_CODE = "EMPLOYEE"


def _employee_role(conn) -> dict:
    row = conn.execute(
        text("SELECT role_id, code, name, is_active FROM public.roles WHERE code = :code"),
        {"code": EMPLOYEE_ROLE_CODE},
    ).mappings().one_or_none()
    if row is None:
        pytest.fail("EMPLOYEE Platform Role migration has not been applied")
    return dict(row)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_employee_role_is_active_neutral_and_not_privileged(monkeypatch) -> None:
    monkeypatch.delenv("DIRECTORY_PRIVILEGED_USER_IDS", raising=False)
    monkeypatch.delenv("DIRECTORY_PRIVILEGED_IDS", raising=False)
    with engine.connect() as conn:
        role = _employee_role(conn)
        active_role_grants = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.access_grants
                    WHERE target_type = 'ROLE'
                      AND target_id = :role_id
                      AND active_flag = TRUE
                      AND revoked_at IS NULL
                    """
                ),
                {"role_id": int(role["role_id"])},
            ).scalar_one()
        )

    assert role == {
        "role_id": int(role["role_id"]),
        "code": EMPLOYEE_ROLE_CODE,
        "name": "Сотрудник",
        "is_active": True,
    }
    assert active_role_grants == 0
    assert not is_privileged({"user_id": -999999, "role_id": role["role_id"]})
    assert not has_any_admin_api_permission(-999999)
    assert not has_any_personnel_read_permission(-999999)
    assert not has_hr_governance_permission(-999999)
