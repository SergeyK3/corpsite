# tests/test_adr043_phase_c2_person_assignment_sync.py
"""Tests for ADR-043 Phase C2 person & assignment sync engine."""
from __future__ import annotations

import json
from contextlib import contextmanager
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.hr_effective_monthly_diff_service import (
    EVENT_CLOSED_ASSIGNMENT,
    EVENT_DEPARTMENT_CHANGED,
    EVENT_FIELD_CHANGED,
    EVENT_NEW_ASSIGNMENT,
    EVENT_NEW_PERSON,
    EVENT_POSITION_CHANGED,
    EVENT_RATE_CHANGED,
    EVENT_TERMINATED_PERSON,
    compute_assignment_key,
    compute_personnel_event_hash,
)
from app.services.hr_person_assignment_sync_service import sync_personnel_events
from tests.conftest import get_columns, insert_returning_id, table_exists

PHASE_C2_TABLES = (
    "hr_personnel_change_events",
    "persons",
    "person_assignments",
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_c2() -> None:
    with engine.begin() as conn:
        if not all(table_exists(conn, table) for table in PHASE_C2_TABLES):
            pytest.skip("ADR-043 Phase C2 tables missing — run: alembic upgrade head")


@contextmanager
def _isolated_conn():
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            yield conn
        finally:
            trans.rollback()


def _insert_batch(conn, user_id: int) -> int:
    return conn.execute(
        text(
            """
            INSERT INTO public.hr_import_batches (
                source_type, file_name, imported_by, status,
                total_rows, valid_rows, error_rows
            )
            VALUES ('HR_CONTROL_LIST', :file_name, :uid, 'PARSED', 1, 1, 0)
            RETURNING batch_id
            """
        ),
        {"file_name": f"c2_{uuid4().hex[:8]}.xlsx", "uid": user_id},
    ).scalar_one()


def _insert_snapshot_pair(conn, user_id: int) -> tuple[int, int]:
    base_version = 910_000 + int(uuid4().hex[:3], 16)
    prior_id = insert_returning_id(
        conn,
        table="hr_canonical_snapshots",
        id_col="snapshot_id",
        values={
            "source_batch_id": _insert_batch(conn, user_id),
            "source_type": "HR_CONTROL_LIST",
            "version": base_version,
            "status": "superseded",
            "entry_count": 0,
            "promoted_by": user_id,
        },
    )
    new_id = insert_returning_id(
        conn,
        table="hr_canonical_snapshots",
        id_col="snapshot_id",
        values={
            "source_batch_id": _insert_batch(conn, user_id),
            "source_type": "HR_CONTROL_LIST",
            "version": base_version + 1,
            "status": "superseded",
            "entry_count": 0,
            "promoted_by": user_id,
        },
    )
    return int(prior_id), int(new_id)


def _insert_personnel_event(
    conn,
    *,
    prior_id: int,
    new_id: int,
    person_key: str,
    event_type: str,
    assignment_key: str | None = None,
    field_path: str | None = None,
    effective_old_value=None,
    effective_new_value=None,
    metadata: dict | None = None,
) -> int:
    event_hash = compute_personnel_event_hash(
        previous_snapshot_id=prior_id,
        snapshot_id=new_id,
        person_key=person_key,
        assignment_key=assignment_key,
        event_type=event_type,
        field_path=field_path,
        effective_old_value=effective_old_value,
        effective_new_value=effective_new_value,
    )
    return insert_returning_id(
        conn,
        table="hr_personnel_change_events",
        id_col="personnel_event_id",
        values={
            "previous_snapshot_id": prior_id,
            "snapshot_id": new_id,
            "person_key": person_key,
            "assignment_key": assignment_key,
            "event_type": event_type,
            "field_path": field_path,
            "effective_old_value": json.dumps(effective_old_value) if effective_old_value is not None else None,
            "effective_new_value": json.dumps(effective_new_value) if effective_new_value is not None else None,
            "event_hash": event_hash,
            "status": "detected",
            "metadata": json.dumps(metadata or {}),
        },
    )


def _count_persons(conn, person_key: str) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.persons
                WHERE match_key = :mk AND person_status IN ('active', 'inactive')
                """
            ),
            {"mk": person_key},
        ).scalar_one()
    )


def _count_active_assignments(conn, person_id: int, assignment_key: str) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.person_assignments
                WHERE person_id = :pid
                  AND lower(assignment_key) = lower(:ak)
                  AND lifecycle_status = 'active'
                """
            ),
            {"pid": person_id, "ak": assignment_key},
        ).scalar_one()
    )


def _get_position_id(conn) -> int:
    return int(
        conn.execute(text("SELECT position_id FROM public.positions ORDER BY position_id LIMIT 1")).scalar_one()
    )


def _create_employee_for_person(conn, seed, person_id: int, suffix: str) -> int:
    emp_values = {
        "full_name": f"C2 Employee {suffix}",
        "person_id": person_id,
        "org_unit_id": int(seed["unit_id"]),
        "is_active": True,
        "operational_status": "active",
        "enrollment_source": "manual_emergency",
    }
    cols = get_columns(conn, "employees")
    if "employment_rate" in cols:
        emp_values["employment_rate"] = 1.0
    return insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values=emp_values,
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_new_person_creates_person(seed):
    _require_c2()
    suffix = uuid4().hex[:8]
    person_key = f"name:c2-new-{suffix}"

    with _isolated_conn() as conn:
        prior_id, new_id = _insert_snapshot_pair(conn, seed["executor_user_id"])
        payload = {"full_name": f"New Person {suffix}", "department": "A", "position_raw": "Doc"}
        assignment_key = compute_assignment_key(person_key, payload)
        event_id = _insert_personnel_event(
            conn,
            prior_id=prior_id,
            new_id=new_id,
            person_key=person_key,
            event_type=EVENT_NEW_PERSON,
            assignment_key=assignment_key,
            effective_new_value={"full_name": payload["full_name"], "iin": None, "assignment_key": assignment_key},
        )

        report = sync_personnel_events(
            conn=conn,
            dry_run=False,
            event_ids=[event_id],
            actor_user_id=seed["executor_user_id"],
        )
        assert report["persons_created"] == 1
        assert _count_persons(conn, person_key) == 1

        row = conn.execute(
            text("SELECT status FROM public.hr_personnel_change_events WHERE personnel_event_id = :eid"),
            {"eid": event_id},
        ).scalar_one()
        assert row == "acknowledged"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_rerun_new_person_does_not_duplicate(seed):
    _require_c2()
    suffix = uuid4().hex[:8]
    person_key = f"name:c2-idem-person-{suffix}"

    with _isolated_conn() as conn:
        prior_id, new_id = _insert_snapshot_pair(conn, seed["executor_user_id"])
        insert_returning_id(
            conn,
            table="persons",
            id_col="person_id",
            values={
                "full_name": f"Existing {suffix}",
                "match_key": person_key,
                "source": "manual",
                "person_status": "active",
            },
        )
        payload = {"full_name": f"Existing {suffix}", "department": "A", "position_raw": "Doc"}
        event_id = _insert_personnel_event(
            conn,
            prior_id=prior_id,
            new_id=new_id,
            person_key=person_key,
            event_type=EVENT_NEW_PERSON,
            assignment_key=compute_assignment_key(person_key, payload),
            effective_new_value={"full_name": payload["full_name"]},
        )

        report = sync_personnel_events(
            conn=conn,
            dry_run=False,
            event_ids=[event_id],
            actor_user_id=seed["executor_user_id"],
        )
        assert report["persons_created"] == 0
        assert _count_persons(conn, person_key) == 1
        assert report["events_applied"] == 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_new_assignment_creates_assignment(seed):
    _require_c2()
    suffix = uuid4().hex[:8]
    person_key = f"name:c2-assign-{suffix}"

    with _isolated_conn() as conn:
        prior_id, new_id = _insert_snapshot_pair(conn, seed["executor_user_id"])
        person_id = insert_returning_id(
            conn,
            table="persons",
            id_col="person_id",
            values={
                "full_name": f"Assign Person {suffix}",
                "match_key": person_key,
                "source": "manual",
                "person_status": "active",
            },
        )
        payload = {
            "full_name": f"Assign Person {suffix}",
            "department": "A",
            "org_unit_id": int(seed["unit_id"]),
            "position_raw": "Doctor",
            "rate": 1.0,
        }
        assignment_key = compute_assignment_key(person_key, payload)
        event_id = _insert_personnel_event(
            conn,
            prior_id=prior_id,
            new_id=new_id,
            person_key=person_key,
            event_type=EVENT_NEW_ASSIGNMENT,
            assignment_key=assignment_key,
            effective_new_value={
                "department": payload["department"],
                "org_unit_id": payload["org_unit_id"],
                "position_raw": payload["position_raw"],
            },
            metadata={"canonical_entry_id": None},
        )

        report = sync_personnel_events(
            conn=conn,
            dry_run=False,
            event_ids=[event_id],
            actor_user_id=seed["executor_user_id"],
        )
        assert report["assignments_created"] == 1
        assert _count_active_assignments(conn, person_id, assignment_key) == 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_rerun_new_assignment_does_not_duplicate(seed):
    _require_c2()
    suffix = uuid4().hex[:8]
    person_key = f"name:c2-idem-assign-{suffix}"

    with _isolated_conn() as conn:
        prior_id, new_id = _insert_snapshot_pair(conn, seed["executor_user_id"])
        person_id = insert_returning_id(
            conn,
            table="persons",
            id_col="person_id",
            values={
                "full_name": f"Dup Assign {suffix}",
                "match_key": person_key,
                "source": "manual",
                "person_status": "active",
            },
        )
        pos_id = _get_position_id(conn)
        payload = {
            "org_unit_id": int(seed["unit_id"]),
            "position_raw": "Doctor",
        }
        assignment_key = compute_assignment_key(person_key, payload)
        insert_returning_id(
            conn,
            table="person_assignments",
            id_col="assignment_id",
            values={
                "person_id": person_id,
                "org_unit_id": int(seed["unit_id"]),
                "position_id": pos_id,
                "employment_type": "primary",
                "rate": 1.0,
                "start_date": "2026-01-01",
                "active_flag": True,
                "is_primary": True,
                "lifecycle_status": "active",
                "assignment_key": assignment_key,
                "source": "manual",
            },
        )
        event_id = _insert_personnel_event(
            conn,
            prior_id=prior_id,
            new_id=new_id,
            person_key=person_key,
            event_type=EVENT_NEW_ASSIGNMENT,
            assignment_key=assignment_key,
            effective_new_value=payload,
        )

        report = sync_personnel_events(
            conn=conn,
            dry_run=False,
            event_ids=[event_id],
            actor_user_id=seed["executor_user_id"],
        )
        assert report["assignments_created"] == 0
        assert _count_active_assignments(conn, person_id, assignment_key) == 1
        assert report["events_applied"] == 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_closed_assignment_closes_without_delete(seed):
    _require_c2()
    suffix = uuid4().hex[:8]
    person_key = f"name:c2-close-{suffix}"

    with _isolated_conn() as conn:
        prior_id, new_id = _insert_snapshot_pair(conn, seed["executor_user_id"])
        person_id = insert_returning_id(
            conn,
            table="persons",
            id_col="person_id",
            values={
                "full_name": f"Close Person {suffix}",
                "match_key": person_key,
                "source": "manual",
                "person_status": "active",
            },
        )
        pos_id = _get_position_id(conn)
        payload = {"org_unit_id": int(seed["unit_id"]), "position_raw": "Doctor"}
        assignment_key = compute_assignment_key(person_key, payload)
        assignment_id = insert_returning_id(
            conn,
            table="person_assignments",
            id_col="assignment_id",
            values={
                "person_id": person_id,
                "org_unit_id": int(seed["unit_id"]),
                "position_id": pos_id,
                "employment_type": "primary",
                "rate": 1.0,
                "start_date": "2026-01-01",
                "active_flag": True,
                "is_primary": True,
                "lifecycle_status": "active",
                "assignment_key": assignment_key,
                "source": "manual",
            },
        )
        event_id = _insert_personnel_event(
            conn,
            prior_id=prior_id,
            new_id=new_id,
            person_key=person_key,
            event_type=EVENT_CLOSED_ASSIGNMENT,
            assignment_key=assignment_key,
            effective_old_value=payload,
        )

        report = sync_personnel_events(
            conn=conn,
            dry_run=False,
            event_ids=[event_id],
            actor_user_id=seed["executor_user_id"],
        )
        assert report["assignments_closed"] == 1
        row = conn.execute(
            text("SELECT lifecycle_status FROM public.person_assignments WHERE assignment_id = :aid"),
            {"aid": assignment_id},
        ).scalar_one()
        assert row == "closed"
        assert int(conn.execute(text("SELECT COUNT(*) FROM public.person_assignments")).scalar_one()) >= 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_terminated_person_closes_active_assignments(seed):
    _require_c2()
    suffix = uuid4().hex[:8]
    person_key = f"name:c2-term-{suffix}"

    with _isolated_conn() as conn:
        prior_id, new_id = _insert_snapshot_pair(conn, seed["executor_user_id"])
        person_id = insert_returning_id(
            conn,
            table="persons",
            id_col="person_id",
            values={
                "full_name": f"Term Person {suffix}",
                "match_key": person_key,
                "source": "manual",
                "person_status": "active",
            },
        )
        pos_id = _get_position_id(conn)
        payload = {"org_unit_id": int(seed["unit_id"]), "position_raw": "Doctor"}
        assignment_key = compute_assignment_key(person_key, payload)
        insert_returning_id(
            conn,
            table="person_assignments",
            id_col="assignment_id",
            values={
                "person_id": person_id,
                "org_unit_id": int(seed["unit_id"]),
                "position_id": pos_id,
                "employment_type": "primary",
                "rate": 1.0,
                "start_date": "2026-01-01",
                "active_flag": True,
                "is_primary": True,
                "lifecycle_status": "active",
                "assignment_key": assignment_key,
                "source": "manual",
            },
        )
        event_id = _insert_personnel_event(
            conn,
            prior_id=prior_id,
            new_id=new_id,
            person_key=person_key,
            event_type=EVENT_TERMINATED_PERSON,
            assignment_key=assignment_key,
            effective_old_value={"full_name": f"Term Person {suffix}"},
        )

        report = sync_personnel_events(
            conn=conn,
            dry_run=False,
            event_ids=[event_id],
            actor_user_id=seed["executor_user_id"],
        )
        assert report["assignments_closed"] >= 1
        status = conn.execute(
            text("SELECT person_status FROM public.persons WHERE person_id = :pid"),
            {"pid": person_id},
        ).scalar_one()
        assert status == "inactive"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_department_changed_updates_assignment(seed):
    _require_c2()
    suffix = uuid4().hex[:8]
    person_key = f"name:c2-dept-{suffix}"

    with _isolated_conn() as conn:
        prior_id, new_id = _insert_snapshot_pair(conn, seed["executor_user_id"])
        person_id = insert_returning_id(
            conn,
            table="persons",
            id_col="person_id",
            values={
                "full_name": f"Dept Person {suffix}",
                "match_key": person_key,
                "source": "manual",
                "person_status": "active",
            },
        )
        pos_id = _get_position_id(conn)
        old_payload = {"org_unit_id": int(seed["unit_id"]), "position_raw": "Doctor"}
        assignment_key = compute_assignment_key(person_key, old_payload)
        assignment_id = insert_returning_id(
            conn,
            table="person_assignments",
            id_col="assignment_id",
            values={
                "person_id": person_id,
                "org_unit_id": int(seed["unit_id"]),
                "position_id": pos_id,
                "employment_type": "primary",
                "rate": 1.0,
                "start_date": "2026-01-01",
                "active_flag": True,
                "is_primary": True,
                "lifecycle_status": "active",
                "assignment_key": assignment_key,
                "source": "manual",
            },
        )
        alt_org = conn.execute(
            text(
                """
                SELECT unit_id FROM public.org_units
                WHERE is_active = TRUE AND unit_id <> :uid
                ORDER BY unit_id LIMIT 1
                """
            ),
            {"uid": int(seed["unit_id"])},
        ).scalar_one_or_none()
        if alt_org is None:
            alt_org = int(seed["unit_id"])
        else:
            alt_org = int(alt_org)

        event_id = _insert_personnel_event(
            conn,
            prior_id=prior_id,
            new_id=new_id,
            person_key=person_key,
            event_type=EVENT_DEPARTMENT_CHANGED,
            assignment_key=assignment_key,
            field_path="roster.department",
            effective_old_value="Dept A",
            effective_new_value={"department": "Dept B", "org_unit_id": alt_org},
        )

        report = sync_personnel_events(
            conn=conn,
            dry_run=False,
            event_ids=[event_id],
            actor_user_id=seed["executor_user_id"],
        )
        assert report["assignments_updated"] == 1
        org_unit_id = conn.execute(
            text("SELECT org_unit_id FROM public.person_assignments WHERE assignment_id = :aid"),
            {"aid": assignment_id},
        ).scalar_one()
        assert int(org_unit_id) == alt_org


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_position_changed_updates_assignment(seed):
    _require_c2()
    suffix = uuid4().hex[:8]
    person_key = f"name:c2-pos-{suffix}"

    with _isolated_conn() as conn:
        prior_id, new_id = _insert_snapshot_pair(conn, seed["executor_user_id"])
        person_id = insert_returning_id(
            conn,
            table="persons",
            id_col="person_id",
            values={
                "full_name": f"Pos Person {suffix}",
                "match_key": person_key,
                "source": "manual",
                "person_status": "active",
            },
        )
        pos_id = _get_position_id(conn)
        payload = {"org_unit_id": int(seed["unit_id"]), "position_raw": "Doctor"}
        assignment_key = compute_assignment_key(person_key, payload)
        assignment_id = insert_returning_id(
            conn,
            table="person_assignments",
            id_col="assignment_id",
            values={
                "person_id": person_id,
                "org_unit_id": int(seed["unit_id"]),
                "position_id": pos_id,
                "employment_type": "primary",
                "rate": 1.0,
                "start_date": "2026-01-01",
                "active_flag": True,
                "is_primary": True,
                "lifecycle_status": "active",
                "assignment_key": assignment_key,
                "source": "manual",
            },
        )
        new_position = f"C2 Chief {suffix}"
        event_id = _insert_personnel_event(
            conn,
            prior_id=prior_id,
            new_id=new_id,
            person_key=person_key,
            event_type=EVENT_POSITION_CHANGED,
            assignment_key=assignment_key,
            field_path="roster.position_raw",
            effective_old_value="Doctor",
            effective_new_value={"position_raw": new_position, "org_unit_id": int(seed["unit_id"])},
        )

        report = sync_personnel_events(
            conn=conn,
            dry_run=False,
            event_ids=[event_id],
            actor_user_id=seed["executor_user_id"],
        )
        assert report["assignments_updated"] == 1
        updated_pos = conn.execute(
            text(
                """
                SELECT p.name
                FROM public.person_assignments pa
                JOIN public.positions p ON p.position_id = pa.position_id
                WHERE pa.assignment_id = :aid
                """
            ),
            {"aid": assignment_id},
        ).scalar_one()
        assert updated_pos == new_position


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_rate_changed_updates_assignment(seed):
    _require_c2()
    suffix = uuid4().hex[:8]
    person_key = f"name:c2-rate-{suffix}"

    with _isolated_conn() as conn:
        prior_id, new_id = _insert_snapshot_pair(conn, seed["executor_user_id"])
        person_id = insert_returning_id(
            conn,
            table="persons",
            id_col="person_id",
            values={
                "full_name": f"Rate Person {suffix}",
                "match_key": person_key,
                "source": "manual",
                "person_status": "active",
            },
        )
        pos_id = _get_position_id(conn)
        payload = {"org_unit_id": int(seed["unit_id"]), "position_raw": "Doctor", "rate": 1.0}
        assignment_key = compute_assignment_key(person_key, payload)
        assignment_id = insert_returning_id(
            conn,
            table="person_assignments",
            id_col="assignment_id",
            values={
                "person_id": person_id,
                "org_unit_id": int(seed["unit_id"]),
                "position_id": pos_id,
                "employment_type": "primary",
                "rate": 1.0,
                "start_date": "2026-01-01",
                "active_flag": True,
                "is_primary": True,
                "lifecycle_status": "active",
                "assignment_key": assignment_key,
                "source": "manual",
            },
        )
        event_id = _insert_personnel_event(
            conn,
            prior_id=prior_id,
            new_id=new_id,
            person_key=person_key,
            event_type=EVENT_RATE_CHANGED,
            assignment_key=assignment_key,
            field_path="roster.rate",
            effective_old_value=1.0,
            effective_new_value={"rate": 0.5, "org_unit_id": int(seed["unit_id"]), "position_raw": "Doctor"},
        )

        report = sync_personnel_events(
            conn=conn,
            dry_run=False,
            event_ids=[event_id],
            actor_user_id=seed["executor_user_id"],
        )
        assert report["assignments_updated"] == 1
        rate = conn.execute(
            text("SELECT rate FROM public.person_assignments WHERE assignment_id = :aid"),
            {"aid": assignment_id},
        ).scalar_one()
        assert float(rate) == 0.5


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_field_changed_whitelist_updates_person(seed):
    _require_c2()
    suffix = uuid4().hex[:8]
    person_key = f"name:c2-field-{suffix}"

    with _isolated_conn() as conn:
        prior_id, new_id = _insert_snapshot_pair(conn, seed["executor_user_id"])
        person_id = insert_returning_id(
            conn,
            table="persons",
            id_col="person_id",
            values={
                "full_name": f"Old Name {suffix}",
                "match_key": person_key,
                "source": "manual",
                "person_status": "active",
            },
        )
        payload = {"org_unit_id": int(seed["unit_id"]), "position_raw": "Doctor"}
        assignment_key = compute_assignment_key(person_key, payload)
        insert_returning_id(
            conn,
            table="person_assignments",
            id_col="assignment_id",
            values={
                "person_id": person_id,
                "org_unit_id": int(seed["unit_id"]),
                "position_id": _get_position_id(conn),
                "employment_type": "primary",
                "rate": 1.0,
                "start_date": "2026-01-01",
                "active_flag": True,
                "is_primary": True,
                "lifecycle_status": "active",
                "assignment_key": assignment_key,
                "source": "manual",
            },
        )
        new_name = f"New Name {suffix}"
        event_id = _insert_personnel_event(
            conn,
            prior_id=prior_id,
            new_id=new_id,
            person_key=person_key,
            event_type=EVENT_FIELD_CHANGED,
            assignment_key=assignment_key,
            field_path="identity.full_name",
            effective_old_value="Old",
            effective_new_value=new_name,
        )

        report = sync_personnel_events(
            conn=conn,
            dry_run=False,
            event_ids=[event_id],
            actor_user_id=seed["executor_user_id"],
        )
        assert report["persons_updated"] == 1
        full_name = conn.execute(
            text("SELECT full_name FROM public.persons WHERE person_id = :pid"),
            {"pid": person_id},
        ).scalar_one()
        assert full_name == new_name


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_note_field_ignored(seed):
    _require_c2()
    suffix = uuid4().hex[:8]
    person_key = f"name:c2-note-{suffix}"

    with _isolated_conn() as conn:
        prior_id, new_id = _insert_snapshot_pair(conn, seed["executor_user_id"])
        person_id = insert_returning_id(
            conn,
            table="persons",
            id_col="person_id",
            values={
                "full_name": f"Note Person {suffix}",
                "match_key": person_key,
                "source": "manual",
                "person_status": "active",
            },
        )
        event_id = _insert_personnel_event(
            conn,
            prior_id=prior_id,
            new_id=new_id,
            person_key=person_key,
            event_type=EVENT_FIELD_CHANGED,
            field_path="note.text",
            effective_old_value="old note",
            effective_new_value="new note",
        )

        before_updated = conn.execute(
            text("SELECT updated_at FROM public.persons WHERE person_id = :pid"),
            {"pid": person_id},
        ).scalar_one()
        report = sync_personnel_events(
            conn=conn,
            dry_run=False,
            event_ids=[event_id],
            actor_user_id=seed["executor_user_id"],
        )
        after_updated = conn.execute(
            text("SELECT updated_at FROM public.persons WHERE person_id = :pid"),
            {"pid": person_id},
        ).scalar_one()
        assert report["events_skipped"] == 1
        assert report["persons_updated"] == 0
        assert before_updated == after_updated


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_employee_link_updated_when_employee_exists(seed):
    _require_c2()
    suffix = uuid4().hex[:8]
    person_key = f"name:c2-link-{suffix}"

    with _isolated_conn() as conn:
        if not table_exists(conn, "employee_assignment_links"):
            pytest.skip("employee_assignment_links missing")
        prior_id, new_id = _insert_snapshot_pair(conn, seed["executor_user_id"])
        person_id = insert_returning_id(
            conn,
            table="persons",
            id_col="person_id",
            values={
                "full_name": f"Link Person {suffix}",
                "match_key": person_key,
                "source": "manual",
                "person_status": "active",
            },
        )
        _create_employee_for_person(conn, seed, person_id, suffix)
        payload = {
            "org_unit_id": int(seed["unit_id"]),
            "position_raw": "Doctor",
        }
        assignment_key = compute_assignment_key(person_key, payload)
        event_id = _insert_personnel_event(
            conn,
            prior_id=prior_id,
            new_id=new_id,
            person_key=person_key,
            event_type=EVENT_NEW_ASSIGNMENT,
            assignment_key=assignment_key,
            effective_new_value=payload,
        )

        employees_before = int(conn.execute(text("SELECT COUNT(*) FROM public.employees")).scalar_one())
        report = sync_personnel_events(
            conn=conn,
            dry_run=False,
            event_ids=[event_id],
            actor_user_id=seed["executor_user_id"],
        )
        employees_after = int(conn.execute(text("SELECT COUNT(*) FROM public.employees")).scalar_one())
        assert employees_before == employees_after
        assert report["links_created"] == 1
        status = conn.execute(
            text("SELECT status FROM public.hr_personnel_change_events WHERE personnel_event_id = :eid"),
            {"eid": event_id},
        ).scalar_one()
        assert status == "enrolled"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_no_employee_auto_created_without_enrollment(seed):
    _require_c2()
    suffix = uuid4().hex[:8]
    person_key = f"name:c2-no-emp-{suffix}"

    with _isolated_conn() as conn:
        prior_id, new_id = _insert_snapshot_pair(conn, seed["executor_user_id"])
        insert_returning_id(
            conn,
            table="persons",
            id_col="person_id",
            values={
                "full_name": f"No Emp {suffix}",
                "match_key": person_key,
                "source": "manual",
                "person_status": "active",
            },
        )
        payload = {"org_unit_id": int(seed["unit_id"]), "position_raw": "Doctor"}
        event_id = _insert_personnel_event(
            conn,
            prior_id=prior_id,
            new_id=new_id,
            person_key=person_key,
            event_type=EVENT_NEW_ASSIGNMENT,
            assignment_key=compute_assignment_key(person_key, payload),
            effective_new_value=payload,
        )
        employees_before = int(conn.execute(text("SELECT COUNT(*) FROM public.employees")).scalar_one())
        report = sync_personnel_events(
            conn=conn,
            dry_run=False,
            event_ids=[event_id],
            actor_user_id=seed["executor_user_id"],
        )
        employees_after = int(conn.execute(text("SELECT COUNT(*) FROM public.employees")).scalar_one())
        assert employees_before == employees_after
        assert report["links_created"] == 0


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_dry_run_changes_nothing(seed):
    _require_c2()
    suffix = uuid4().hex[:8]
    person_key = f"name:c2-dry-{suffix}"

    with _isolated_conn() as conn:
        prior_id, new_id = _insert_snapshot_pair(conn, seed["executor_user_id"])
        payload = {"full_name": f"Dry Person {suffix}", "department": "A", "position_raw": "Doc"}
        event_id = _insert_personnel_event(
            conn,
            prior_id=prior_id,
            new_id=new_id,
            person_key=person_key,
            event_type=EVENT_NEW_PERSON,
            assignment_key=compute_assignment_key(person_key, payload),
            effective_new_value={"full_name": payload["full_name"]},
        )
        persons_before = int(conn.execute(text("SELECT COUNT(*) FROM public.persons")).scalar_one())
        report = sync_personnel_events(
            conn=conn,
            dry_run=True,
            event_ids=[event_id],
            actor_user_id=seed["executor_user_id"],
        )
        persons_after = int(conn.execute(text("SELECT COUNT(*) FROM public.persons")).scalar_one())
        assert report["dry_run"] is True
        assert persons_before == persons_after
        status = conn.execute(
            text("SELECT status FROM public.hr_personnel_change_events WHERE personnel_event_id = :eid"),
            {"eid": event_id},
        ).scalar_one()
        assert status == "detected"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_failed_event_remains_retryable(seed):
    _require_c2()
    suffix = uuid4().hex[:8]
    person_key = f"name:c2-fail-{suffix}"

    with _isolated_conn() as conn:
        prior_id, new_id = _insert_snapshot_pair(conn, seed["executor_user_id"])
        payload = {"org_unit_id": int(seed["unit_id"]), "position_raw": "Doctor"}
        assignment_key = compute_assignment_key(person_key, payload)
        event_id = _insert_personnel_event(
            conn,
            prior_id=prior_id,
            new_id=new_id,
            person_key=person_key,
            event_type=EVENT_DEPARTMENT_CHANGED,
            assignment_key=assignment_key,
            field_path="roster.department",
            effective_old_value="A",
            effective_new_value={"department": "B", "org_unit_id": int(seed["unit_id"])},
        )

        report = sync_personnel_events(
            conn=conn,
            dry_run=False,
            event_ids=[event_id],
            actor_user_id=seed["executor_user_id"],
        )
        assert report["errors"]
        status = conn.execute(
            text("SELECT status FROM public.hr_personnel_change_events WHERE personnel_event_id = :eid"),
            {"eid": event_id},
        ).scalar_one()
        assert status == "detected"

        person_id = insert_returning_id(
            conn,
            table="persons",
            id_col="person_id",
            values={
                "full_name": f"Retry Person {suffix}",
                "match_key": person_key,
                "source": "manual",
                "person_status": "active",
            },
        )
        insert_returning_id(
            conn,
            table="person_assignments",
            id_col="assignment_id",
            values={
                "person_id": person_id,
                "org_unit_id": int(seed["unit_id"]),
                "position_id": _get_position_id(conn),
                "employment_type": "primary",
                "rate": 1.0,
                "start_date": "2026-01-01",
                "active_flag": True,
                "is_primary": True,
                "lifecycle_status": "active",
                "assignment_key": assignment_key,
                "source": "manual",
            },
        )
        retry = sync_personnel_events(
            conn=conn,
            dry_run=False,
            event_ids=[event_id],
            actor_user_id=seed["executor_user_id"],
        )
        assert retry["events_applied"] == 1
        status_after = conn.execute(
            text("SELECT status FROM public.hr_personnel_change_events WHERE personnel_event_id = :eid"),
            {"eid": event_id},
        ).scalar_one()
        assert status_after == "acknowledged"
