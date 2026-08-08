"""Narrow API tests for the permission-guarded manual assignment command."""
from __future__ import annotations

from sqlalchemy import text

from app.db.engine import engine
from app.services import manual_assignment_change_service
from tests.conftest import auth_headers
from tests.test_manual_assignment_change_service import _setup_employee


def _grant_hr_enrollment_manager(user_id: int) -> int:
    with engine.begin() as conn:
        return int(
            conn.execute(
                text(
                    """
                    INSERT INTO public.access_grants (
                        access_role_id, target_type, target_id,
                        granted_by_user_id, reason
                    )
                    SELECT access_role_id, 'USER', :user_id, :user_id,
                           'pytest manual assignment API'
                    FROM public.access_roles
                    WHERE code='HR_ENROLLMENT_MANAGER'
                    RETURNING grant_id
                    """
                ),
                {"user_id": int(user_id)},
            ).scalar_one()
        )


def _create_fixture(seed) -> dict:
    with engine.begin() as conn:
        return _setup_employee(conn, seed)


def _cleanup(data: dict, grant_id: int | None) -> None:
    with engine.begin() as conn:
        if data:
            conn.execute(
                text("DELETE FROM security_audit_log WHERE target_employee_id=:employee_id"),
                {"employee_id": data["employee_id"]},
            )
            conn.execute(
                text("DELETE FROM employee_events WHERE employee_id=:employee_id"),
                {"employee_id": data["employee_id"]},
            )
            conn.execute(
                text("DELETE FROM employee_assignment_links WHERE employee_id=:employee_id"),
                {"employee_id": data["employee_id"]},
            )
            conn.execute(
                text("DELETE FROM person_assignments WHERE person_id=:person_id"),
                {"person_id": data["person_id"]},
            )
            conn.execute(
                text("DELETE FROM employees WHERE employee_id=:employee_id"),
                {"employee_id": data["employee_id"]},
            )
            conn.execute(
                text("DELETE FROM persons WHERE person_id=:person_id"),
                {"person_id": data["person_id"]},
            )
        if grant_id is not None:
            conn.execute(
                text("DELETE FROM access_grants WHERE grant_id=:grant_id"),
                {"grant_id": int(grant_id)},
            )


def _payload(data: dict, *, expected_assignment_id: int | None = None) -> dict:
    return {
        "expected_assignment_id": (
            data["assignment_id"]
            if expected_assignment_id is None
            else expected_assignment_id
        ),
        "org_unit_id": data["unit_id"],
        "position_id": data["target_position_id"],
        "start_date": data["start_date"].isoformat(),
        "idempotency_key": data["idempotency_key"],
        "comment": "pytest API assignment change",
    }


def test_authorized_permission_changes_assignment(client, seed):
    data: dict = {}
    grant_id = None
    try:
        data = _create_fixture(seed)
        actor_id = int(seed["executor_user_id"])
        grant_id = _grant_hr_enrollment_manager(actor_id)
        response = client.post(
            f"/directory/employees/{data['employee_id']}/assignment-change",
            json=_payload(data),
            headers=auth_headers(actor_id),
        )
        assert response.status_code == 200, response.text
        result = response.json()["result"]
        assert result["predecessor_assignment_id"] == data["assignment_id"]
        assert result["already_applied"] is False
        with engine.connect() as conn:
            active = conn.execute(
                text(
                    """
                    SELECT assignment_id, org_unit_id, position_id
                    FROM person_assignments
                    WHERE person_id=:person_id AND active_flag IS TRUE
                      AND lifecycle_status='active'
                    """
                ),
                {"person_id": data["person_id"]},
            ).mappings().all()
        assert len(active) == 1
        assert active[0]["assignment_id"] == result["successor_assignment_id"]
        assert active[0]["position_id"] == data["target_position_id"]
    finally:
        _cleanup(data, grant_id)


def test_view_only_user_gets_403(client, seed):
    data: dict = {}
    try:
        data = _create_fixture(seed)
        response = client.post(
            f"/directory/employees/{data['employee_id']}/assignment-change",
            json=_payload(data),
            headers=auth_headers(int(seed["initiator_user_id"])),
        )
        assert response.status_code == 403
        assert "HR_ENROLLMENT_MANAGER" in str(response.json()["detail"])
    finally:
        _cleanup(data, None)


def test_stale_expected_assignment_returns_conflict_without_changes(client, seed):
    data: dict = {}
    grant_id = None
    try:
        data = _create_fixture(seed)
        actor_id = int(seed["executor_user_id"])
        grant_id = _grant_hr_enrollment_manager(actor_id)
        response = client.post(
            f"/directory/employees/{data['employee_id']}/assignment-change",
            json=_payload(data, expected_assignment_id=data["assignment_id"] + 999_999),
            headers=auth_headers(actor_id),
        )
        assert response.status_code == 409, response.text
        assert response.json()["detail"]["code"] == "ACTIVE_ASSIGNMENT_STALE"
        with engine.connect() as conn:
            assignments = conn.execute(
                text(
                    """
                    SELECT assignment_id, active_flag, lifecycle_status
                    FROM person_assignments WHERE person_id=:person_id
                    """
                ),
                {"person_id": data["person_id"]},
            ).mappings().all()
            event_count = conn.execute(
                text("SELECT count(*) FROM employee_events WHERE employee_id=:employee_id"),
                {"employee_id": data["employee_id"]},
            ).scalar_one()
        assert len(assignments) == 1
        assert assignments[0]["active_flag"] is True
        assert assignments[0]["lifecycle_status"] == "active"
        assert event_count == 0
    finally:
        _cleanup(data, grant_id)


def test_service_error_is_controlled_and_transaction_rolls_back(client, seed, monkeypatch):
    data: dict = {}
    grant_id = None
    try:
        data = _create_fixture(seed)
        actor_id = int(seed["executor_user_id"])
        grant_id = _grant_hr_enrollment_manager(actor_id)
        monkeypatch.setattr(
            manual_assignment_change_service,
            "write_security_event",
            lambda **kwargs: None,
        )
        response = client.post(
            f"/directory/employees/{data['employee_id']}/assignment-change",
            json=_payload(data),
            headers=auth_headers(actor_id),
        )
        assert response.status_code == 409, response.text
        assert response.json()["detail"]["code"] == "ASSIGNMENT_AUDIT_WRITE_FAILED"
        with engine.connect() as conn:
            assignments = conn.execute(
                text(
                    """
                    SELECT assignment_id, active_flag, lifecycle_status
                    FROM person_assignments WHERE person_id=:person_id
                    """
                ),
                {"person_id": data["person_id"]},
            ).mappings().all()
            employee = conn.execute(
                text("SELECT position_id FROM employees WHERE employee_id=:employee_id"),
                {"employee_id": data["employee_id"]},
            ).scalar_one()
            event_count = conn.execute(
                text("SELECT count(*) FROM employee_events WHERE employee_id=:employee_id"),
                {"employee_id": data["employee_id"]},
            ).scalar_one()
        assert len(assignments) == 1
        assert assignments[0]["assignment_id"] == data["assignment_id"]
        assert assignments[0]["active_flag"] is True
        assert assignments[0]["lifecycle_status"] == "active"
        assert employee == data["old_position_id"]
        assert event_count == 0
    finally:
        _cleanup(data, grant_id)
