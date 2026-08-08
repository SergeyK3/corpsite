"""Narrow integration tests for the manual assignment successor command."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.manual_assignment_change_service import (
    ManualAssignmentChangeError,
    change_employee_assignment,
)
from tests.conftest import get_columns, insert_returning_id, table_exists


REQUIRED_TABLES = (
    "persons",
    "employees",
    "person_assignments",
    "employee_assignment_links",
    "employee_events",
    "security_audit_log",
)


@contextmanager
def _isolated_conn():
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            yield conn
        finally:
            transaction.rollback()


def _require_schema(conn) -> None:
    if not all(table_exists(conn, table) for table in REQUIRED_TABLES):
        pytest.skip("manual assignment change schema is not available")


def _setup_employee(conn, seed) -> dict:
    _require_schema(conn)
    positions = conn.execute(
        text("SELECT position_id FROM public.positions ORDER BY position_id LIMIT 2")
    ).scalars().all()
    if len(positions) < 2:
        pytest.skip("two positions are required")
    suffix = uuid4().hex[:10]
    person_id = insert_returning_id(
        conn,
        table="persons",
        id_col="person_id",
        values={
            "full_name": f"Manual Assignment {suffix}",
            "match_key": f"manual-assignment-test:{suffix}",
            "source": "manual",
            "person_status": "active",
        },
    )
    employee_values = {
        "full_name": f"Manual Assignment {suffix}",
        "person_id": person_id,
        "org_unit_id": int(seed["unit_id"]),
        "position_id": int(positions[0]),
        "date_from": date(2026, 1, 1),
        "is_active": True,
        "operational_status": "active",
        "enrollment_source": "manual_emergency",
    }
    if "employment_rate" in get_columns(conn, "employees"):
        employee_values["employment_rate"] = 1.0
    employee_id = insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values=employee_values,
    )
    assignment_id = insert_returning_id(
        conn,
        table="person_assignments",
        id_col="assignment_id",
        values={
            "person_id": person_id,
            "org_unit_id": int(seed["unit_id"]),
            "position_id": int(positions[0]),
            "employment_type": "primary",
            "rate": 1.0,
            "start_date": date(2026, 1, 1),
            "active_flag": True,
            "is_primary": True,
            "lifecycle_status": "active",
            "assignment_key": f"manual-assignment-predecessor:{suffix}",
            "source": "manual",
        },
    )
    insert_returning_id(
        conn,
        table="employee_assignment_links",
        id_col="link_id",
        values={
            "employee_id": employee_id,
            "assignment_id": assignment_id,
            "link_status": "active",
            "enrolled_by_user_id": int(seed["executor_user_id"]),
        },
    )
    return {
        "person_id": int(person_id),
        "employee_id": int(employee_id),
        "assignment_id": int(assignment_id),
        "old_position_id": int(positions[0]),
        "target_position_id": int(positions[1]),
        "unit_id": int(seed["unit_id"]),
        "actor_user_id": int(seed["executor_user_id"]),
        "idempotency_key": f"manual-change-{suffix}",
        "start_date": date(2026, 2, 1),
    }


def _call(conn, data):
    return change_employee_assignment(
        conn=conn,
        employee_id=data["employee_id"],
        expected_assignment_id=data["assignment_id"],
        org_unit_id=data["unit_id"],
        position_id=data["target_position_id"],
        start_date=data["start_date"],
        actor_user_id=data["actor_user_id"],
        idempotency_key=data["idempotency_key"],
        comment="pytest manual position change",
    )


def test_change_closes_predecessor_creates_successor_projection_event_and_audit(seed):
    with _isolated_conn() as conn:
        data = _setup_employee(conn, seed)
        result = _call(conn, data)

        rows = conn.execute(
            text(
                """
                SELECT assignment_id, position_id, start_date, end_date,
                       active_flag, lifecycle_status
                FROM public.person_assignments
                WHERE person_id=:person_id ORDER BY assignment_id
                """
            ),
            {"person_id": data["person_id"]},
        ).mappings().all()
        assert len(rows) == 2
        assert rows[0]["assignment_id"] == data["assignment_id"]
        assert rows[0]["lifecycle_status"] == "closed"
        assert rows[0]["active_flag"] is False
        assert rows[0]["end_date"] == date(2026, 1, 31)
        assert rows[1]["assignment_id"] == result.successor_assignment_id
        assert rows[1]["position_id"] == data["target_position_id"]
        assert rows[1]["start_date"] == data["start_date"]
        assert rows[1]["active_flag"] is True
        assert sum(1 for row in rows if row["active_flag"]) == 1

        employee = conn.execute(
            text(
                """
                SELECT org_unit_id, position_id, employment_rate, date_from, is_active
                FROM public.employees WHERE employee_id=:employee_id
                """
            ),
            {"employee_id": data["employee_id"]},
        ).mappings().one()
        assert employee["org_unit_id"] == data["unit_id"]
        assert employee["position_id"] == data["target_position_id"]
        assert employee["date_from"] == data["start_date"]
        assert employee["is_active"] is True

        event = conn.execute(
            text("SELECT event_type, metadata FROM employee_events WHERE event_id=:event_id"),
            {"event_id": result.event_id},
        ).mappings().one()
        assert event["event_type"] == "POSITION_CHANGE"
        assert event["metadata"]["predecessor_assignment_id"] == data["assignment_id"]
        assert event["metadata"]["successor_assignment_id"] == result.successor_assignment_id
        audit = conn.execute(
            text("SELECT metadata FROM security_audit_log WHERE audit_id=:audit_id"),
            {"audit_id": result.audit_id},
        ).scalar_one()
        assert audit["action"] == "manual_assignment_changed"


def test_identical_retry_returns_original_successor_without_duplicates(seed):
    with _isolated_conn() as conn:
        data = _setup_employee(conn, seed)
        first = _call(conn, data)
        second = _call(conn, data)
        assert second.already_applied is True
        assert second.successor_assignment_id == first.successor_assignment_id
        assert second.event_id == first.event_id
        assert conn.execute(
            text("SELECT count(*) FROM person_assignments WHERE person_id=:person_id"),
            {"person_id": data["person_id"]},
        ).scalar_one() == 2
        assert conn.execute(
            text("SELECT count(*) FROM employee_events WHERE employee_id=:employee_id"),
            {"employee_id": data["employee_id"]},
        ).scalar_one() == 1


@pytest.mark.parametrize("active_count", [0, 2])
def test_invalid_active_assignment_cardinality_has_no_partial_changes(seed, active_count):
    with _isolated_conn() as conn:
        data = _setup_employee(conn, seed)
        if active_count == 0:
            conn.execute(
                text(
                    """
                    UPDATE person_assignments
                    SET active_flag=FALSE, lifecycle_status='closed',
                        end_date=start_date
                    WHERE assignment_id=:assignment_id
                    """
                ),
                {"assignment_id": data["assignment_id"]},
            )
        else:
            insert_returning_id(
                conn,
                table="person_assignments",
                id_col="assignment_id",
                values={
                    "person_id": data["person_id"],
                    "org_unit_id": data["unit_id"],
                    "position_id": data["target_position_id"],
                    "employment_type": "part_time",
                    "rate": 0.5,
                    "start_date": date(2026, 1, 2),
                    "active_flag": True,
                    "is_primary": False,
                    "lifecycle_status": "active",
                    "assignment_key": f"extra-active:{uuid4().hex}",
                    "source": "manual",
                },
            )
        before = {
            "assignments": conn.execute(
                text("SELECT count(*) FROM person_assignments WHERE person_id=:person_id"),
                {"person_id": data["person_id"]},
            ).scalar_one(),
            "events": conn.execute(
                text("SELECT count(*) FROM employee_events WHERE employee_id=:employee_id"),
                {"employee_id": data["employee_id"]},
            ).scalar_one(),
            "position": conn.execute(
                text("SELECT position_id FROM employees WHERE employee_id=:employee_id"),
                {"employee_id": data["employee_id"]},
            ).scalar_one(),
        }
        with pytest.raises(ManualAssignmentChangeError) as exc:
            _call(conn, data)
        assert exc.value.code == "ACTIVE_ASSIGNMENT_CARDINALITY_INVALID"
        assert conn.execute(
            text("SELECT count(*) FROM person_assignments WHERE person_id=:person_id"),
            {"person_id": data["person_id"]},
        ).scalar_one() == before["assignments"]
        assert conn.execute(
            text("SELECT count(*) FROM employee_events WHERE employee_id=:employee_id"),
            {"employee_id": data["employee_id"]},
        ).scalar_one() == before["events"]
        assert conn.execute(
            text("SELECT position_id FROM employees WHERE employee_id=:employee_id"),
            {"employee_id": data["employee_id"]},
        ).scalar_one() == before["position"]
