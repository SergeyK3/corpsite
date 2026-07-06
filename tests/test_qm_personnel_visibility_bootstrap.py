# tests/test_qm_personnel_visibility_bootstrap.py
"""QM pilot ADR-042 E1 visibility bootstrap — idempotency."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from scripts.pilot.qm_personnel_visibility_bootstrap import (
    QM_PILOT_VISIBILITY_UNIT_ID,
    count_active_qm_pilot_visibility_assignments,
    ensure_qm_pilot_personnel_visibility,
    find_active_qm_pilot_visibility_assignment,
)
from tests.conftest import table_exists


def _require_e1_and_qm_unit() -> None:
    with engine.connect() as conn:
        if not table_exists(conn, "personnel_visibility_assignments"):
            pytest.skip("ADR-042 E1 table missing: personnel_visibility_assignments")
        unit_ok = conn.execute(
            text("SELECT 1 FROM public.org_units WHERE unit_id = :id LIMIT 1"),
            {"id": int(QM_PILOT_VISIBILITY_UNIT_ID)},
        ).first()
        if not unit_ok:
            pytest.skip(f"QM org unit {QM_PILOT_VISIBILITY_UNIT_ID} missing")


def test_qm_pilot_visibility_bootstrap_is_idempotent(seed):
    _require_e1_and_qm_unit()

    first = ensure_qm_pilot_personnel_visibility(created_by_user_id=int(seed["initiator_user_id"]))
    second = ensure_qm_pilot_personnel_visibility(created_by_user_id=int(seed["initiator_user_id"]))

    assert first["assignment_id"] is not None
    assert second["created"] is False
    assert second["assignment_id"] == first["assignment_id"]

    with engine.connect() as conn:
        assert count_active_qm_pilot_visibility_assignments(conn) == 1
        row = find_active_qm_pilot_visibility_assignment(conn)
        assert row is not None
        assert int(row["target_department_id"]) == QM_PILOT_VISIBILITY_UNIT_ID
        assert int(row["scope_department_id"]) == QM_PILOT_VISIBILITY_UNIT_ID
        assert row["can_view_personnel"] is True
        assert row["can_view_tasks"] is True
