"""Security contract for the neutral QM training expert Platform Role."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.security.platform_role_classification import (
    is_approved_leadership_workspace_read_role,
    is_hr_head_platform_role,
    looks_like_leadership_platform_role,
)
from tests.ppr.conftest import ppr_db_available


ROLE_CODE = "QM_TRAINING_EXPERT"
ROLE_NAME = "Эксперт по внутреннему обучению и аттестации"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_qm_training_expert_is_active_neutral_and_nonprivileged() -> None:
    with engine.connect() as conn:
        role = conn.execute(
            text("SELECT role_id, code, name, is_active FROM public.roles WHERE code = :code"),
            {"code": ROLE_CODE},
        ).mappings().one_or_none()
        if role is None:
            pytest.fail("QM_TRAINING_EXPERT Platform Role migration has not been applied")
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

    assert dict(role) == {
        "role_id": int(role["role_id"]),
        "code": ROLE_CODE,
        "name": ROLE_NAME,
        "is_active": True,
    }
    assert active_role_grants == 0
    assert not is_approved_leadership_workspace_read_role(ROLE_CODE)
    assert not is_hr_head_platform_role(ROLE_CODE)
    assert not looks_like_leadership_platform_role(ROLE_CODE)
