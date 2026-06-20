# tests/test_adr043_phase_c1_effective_monthly_diff.py
"""Tests for ADR-043 Phase C1 effective monthly diff and personnel events."""
from __future__ import annotations

import json
from contextlib import contextmanager
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.hr_effective_monthly_diff_service import (
    EVENT_DEPARTMENT_CHANGED,
    EVENT_FIELD_CHANGED,
    EVENT_NEW_ASSIGNMENT,
    EVENT_NEW_PERSON,
    EVENT_OVERRIDE_APPLIED,
    EVENT_POSITION_CHANGED,
    EVENT_TERMINATED_PERSON,
    EVENT_TRANSFER,
    compare_effective_snapshots,
    compute_personnel_event_hash,
    ensure_effective_cache_for_snapshots,
    enqueue_personnel_events_for_review,
    run_effective_monthly_diff,
)
from app.services.hr_snapshot_comparison_service import materialize_snapshot_change_events
from tests.conftest import insert_returning_id, table_exists

PHASE_C1_TABLES = (
    "hr_snapshot_effective_entries",
    "hr_personnel_change_events",
    "hr_canonical_snapshots",
    "hr_canonical_snapshot_entries",
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_c1() -> None:
    with engine.begin() as conn:
        if not all(table_exists(conn, table) for table in PHASE_C1_TABLES):
            pytest.skip("ADR-043 Phase C1 tables missing — run: alembic upgrade head")


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
        {"file_name": f"c1_{uuid4().hex[:8]}.xlsx", "uid": user_id},
    ).scalar_one()


def _insert_snapshot(
    conn,
    *,
    user_id: int,
    version: int,
    status: str,
) -> tuple[int, int]:
    batch_id = _insert_batch(conn, user_id)
    snapshot_id = insert_returning_id(
        conn,
        table="hr_canonical_snapshots",
        id_col="snapshot_id",
        values={
            "source_batch_id": batch_id,
            "source_type": "HR_CONTROL_LIST",
            "version": version,
            "status": status,
            "entry_count": 0,
            "promoted_by": user_id,
        },
    )
    return int(snapshot_id), int(batch_id)


def _insert_roster_entry(
    conn,
    *,
    snapshot_id: int,
    match_key: str,
    payload: dict,
) -> int:
    return insert_returning_id(
        conn,
        table="hr_canonical_snapshot_entries",
        id_col="entry_id",
        values={
            "snapshot_id": snapshot_id,
            "entity_scope": match_key,
            "record_kind": "roster",
            "match_key": match_key,
            "canonical_hash": "c1" + uuid4().hex,
            "payload": json.dumps(payload),
        },
    )


def _setup_pair(
    conn,
    *,
    user_id: int,
    prior_entries: dict[str, dict],
    new_entries: dict[str, dict],
) -> tuple[int, int]:
    base_version = 900_000 + int(uuid4().hex[:3], 16)
    prior_id, _ = _insert_snapshot(conn, user_id=user_id, version=base_version, status="superseded")
    new_id, _ = _insert_snapshot(conn, user_id=user_id, version=base_version + 1, status="superseded")
    for match_key, payload in prior_entries.items():
        _insert_roster_entry(conn, snapshot_id=prior_id, match_key=match_key, payload=payload)
    for match_key, payload in new_entries.items():
        _insert_roster_entry(conn, snapshot_id=new_id, match_key=match_key, payload=payload)
    ensure_effective_cache_for_snapshots(conn, previous_snapshot_id=prior_id, snapshot_id=new_id)
    return prior_id, new_id


def _event_types(events: list[dict]) -> set[str]:
    return {str(e["event_type"]) for e in events}


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_effective_cache_refresh_used_before_diff(seed):
    _require_c1()
    user_id = seed["executor_user_id"]
    suffix = uuid4().hex[:8]
    person_key = f"name:c1-cache-{suffix}"
    payload = {"full_name": "Cache Person", "iin": "123456789012", "department": "A", "position_raw": "Doc"}

    with _isolated_conn() as conn:
        prior_id, new_id = _setup_pair(
            conn,
            user_id=user_id,
            prior_entries={person_key: payload},
            new_entries={person_key: payload},
        )
        row = conn.execute(
            text(
                """
                SELECT COUNT(*) AS cnt
                FROM public.hr_snapshot_effective_entries
                WHERE snapshot_id = ANY(:ids)
                """
            ),
            {"ids": [prior_id, new_id]},
        ).mappings().one()
        assert int(row["cnt"]) >= 2

        report = run_effective_monthly_diff(
            conn,
            previous_snapshot_id=prior_id,
            snapshot_id=new_id,
            dry_run=True,
            refresh_cache=False,
        )
        assert report["cache_refreshed"] is False


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_detects_new_person(seed):
    _require_c1()
    user_id = seed["executor_user_id"]
    suffix = uuid4().hex[:8]
    existing = f"name:c1-existing-{suffix}"
    newcomer = f"name:c1-new-{suffix}"
    base = {"full_name": "Existing", "department": "A", "position_raw": "Doc"}

    with _isolated_conn() as conn:
        prior_id, new_id = _setup_pair(
            conn,
            user_id=user_id,
            prior_entries={existing: base},
            new_entries={
                existing: base,
                newcomer: {"full_name": "New Person", "department": "B", "position_raw": "Nurse"},
            },
        )
        events = compare_effective_snapshots(conn, previous_snapshot_id=prior_id, snapshot_id=new_id)
        assert EVENT_NEW_PERSON in _event_types(events)
        assert EVENT_NEW_ASSIGNMENT in _event_types(events)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_detects_terminated_person(seed):
    _require_c1()
    user_id = seed["executor_user_id"]
    suffix = uuid4().hex[:8]
    gone = f"name:c1-gone-{suffix}"
    payload = {"full_name": "Leaving", "department": "A", "position_raw": "Doc"}

    with _isolated_conn() as conn:
        prior_id, new_id = _setup_pair(
            conn,
            user_id=user_id,
            prior_entries={gone: payload},
            new_entries={},
        )
        events = compare_effective_snapshots(conn, previous_snapshot_id=prior_id, snapshot_id=new_id)
        assert EVENT_TERMINATED_PERSON in _event_types(events)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_detects_department_and_position_changes(seed):
    _require_c1()
    user_id = seed["executor_user_id"]
    suffix = uuid4().hex[:8]
    person = f"name:c1-dept-pos-{suffix}"

    with _isolated_conn() as conn:
        prior_id, new_id = _setup_pair(
            conn,
            user_id=user_id,
            prior_entries={
                person: {"full_name": "Worker", "department": "Dept A", "org_unit_id": 1, "position_raw": "Doctor"},
            },
            new_entries={
                person: {"full_name": "Worker", "department": "Dept B", "org_unit_id": 2, "position_raw": "Doctor"},
            },
        )
        events = compare_effective_snapshots(conn, previous_snapshot_id=prior_id, snapshot_id=new_id)
        assert EVENT_DEPARTMENT_CHANGED in _event_types(events)

        prior_id2, new_id2 = _setup_pair(
            conn,
            user_id=user_id,
            prior_entries={
                person + "b": {"full_name": "Worker B", "department": "Dept A", "position_raw": "Doctor"},
            },
            new_entries={
                person + "b": {"full_name": "Worker B", "department": "Dept A", "position_raw": "Chief Doctor"},
            },
        )
        events2 = compare_effective_snapshots(conn, previous_snapshot_id=prior_id2, snapshot_id=new_id2)
        assert EVENT_POSITION_CHANGED in _event_types(events2)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_detects_transfer_when_org_and_position_change(seed):
    _require_c1()
    user_id = seed["executor_user_id"]
    person = f"name:c1-transfer-{uuid4().hex[:8]}"

    with _isolated_conn() as conn:
        prior_id, new_id = _setup_pair(
            conn,
            user_id=user_id,
            prior_entries={
                person: {"full_name": "Mover", "department": "A", "org_unit_id": 1, "position_raw": "Doctor"},
            },
            new_entries={
                person: {"full_name": "Mover", "department": "B", "org_unit_id": 2, "position_raw": "Head Doctor"},
            },
        )
        events = compare_effective_snapshots(conn, previous_snapshot_id=prior_id, snapshot_id=new_id)
        assert EVENT_TRANSFER in _event_types(events)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_detects_override_applied(seed):
    _require_c1()
    user_id = seed["executor_user_id"]
    person = f"name:c1-override-{uuid4().hex[:8]}"
    base = {"full_name": "Canonical Name", "department": "A", "position_raw": "Doc"}

    with _isolated_conn() as conn:
        prior_id, new_id = _setup_pair(
            conn,
            user_id=user_id,
            prior_entries={person: base},
            new_entries={person: base},
        )
        conn.execute(
            text(
                """
                UPDATE public.hr_snapshot_effective_entries
                SET effective_payload = effective_payload || CAST(:extra AS jsonb),
                    override_ids = CAST(:oids AS jsonb)
                WHERE snapshot_id = :sid AND match_key = :mk
                """
            ),
            {
                "sid": new_id,
                "mk": person,
                "extra": json.dumps(
                    {"full_name": "Effective Name", "_override_fields": ["identity.full_name"]}
                ),
                "oids": json.dumps([999]),
            },
        )
        events = compare_effective_snapshots(conn, previous_snapshot_id=prior_id, snapshot_id=new_id)
        assert EVENT_OVERRIDE_APPLIED in _event_types(events)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_idempotent_rerun_no_duplicate_events(seed):
    _require_c1()
    user_id = seed["executor_user_id"]
    person = f"name:c1-idem-{uuid4().hex[:8]}"

    with _isolated_conn() as conn:
        prior_id, new_id = _setup_pair(
            conn,
            user_id=user_id,
            prior_entries={},
            new_entries={person: {"full_name": "Once", "department": "A", "position_raw": "Doc"}},
        )
        first = run_effective_monthly_diff(
            conn,
            previous_snapshot_id=prior_id,
            snapshot_id=new_id,
            dry_run=False,
            refresh_cache=False,
        )
        second = run_effective_monthly_diff(
            conn,
            previous_snapshot_id=prior_id,
            snapshot_id=new_id,
            dry_run=False,
            refresh_cache=False,
        )
        assert first["events_created"] > 0
        assert second["events_created"] == 0
        assert second["events_existing"] >= first["events_created"]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_enrollment_auto_created_for_actionable_events(seed):
    _require_c1()
    user_id = seed["executor_user_id"]
    person = f"name:c1-enroll-{uuid4().hex[:8]}"

    with _isolated_conn() as conn:
        if not table_exists(conn, "enrollment_queue"):
            pytest.skip("enrollment_queue missing")

        prior_id, new_id = _setup_pair(
            conn,
            user_id=user_id,
            prior_entries={},
            new_entries={person: {"full_name": "Enroll Me", "department": "A", "position_raw": "Doc"}},
        )
        report = run_effective_monthly_diff(
            conn,
            previous_snapshot_id=prior_id,
            snapshot_id=new_id,
            dry_run=False,
            enqueue=True,
            refresh_cache=False,
        )
        assert report["enrollment_items_created"] >= 1

        second = run_effective_monthly_diff(
            conn,
            previous_snapshot_id=prior_id,
            snapshot_id=new_id,
            dry_run=False,
            enqueue=True,
            refresh_cache=False,
        )
        assert second["enrollment_items_existing"] >= 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_enrollment_not_created_for_note_field_change(seed):
    _require_c1()
    user_id = seed["executor_user_id"]
    person = f"name:c1-note-{uuid4().hex[:8]}"

    with _isolated_conn() as conn:
        if not table_exists(conn, "enrollment_queue"):
            pytest.skip("enrollment_queue missing")

        prior_id, new_id = _setup_pair(
            conn,
            user_id=user_id,
            prior_entries={person: {"full_name": "Note Person", "note_raw": "old note", "department": "A"}},
            new_entries={person: {"full_name": "Note Person", "note_raw": "new note", "department": "A"}},
        )
        report = run_effective_monthly_diff(
            conn,
            previous_snapshot_id=prior_id,
            snapshot_id=new_id,
            dry_run=True,
            enqueue=True,
            refresh_cache=False,
        )
        assert EVENT_FIELD_CHANGED in _event_types(report["planned_events"])
        assert report["enrollment_items_created"] == 0


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_old_hr_change_events_still_work(seed):
    _require_c1()
    user_id = seed["executor_user_id"]
    person = f"name:c1-legacy-{uuid4().hex[:8]}"

    with _isolated_conn() as conn:
        if not table_exists(conn, "hr_change_events"):
            pytest.skip("hr_change_events missing")

        prior_id, new_id = _setup_pair(
            conn,
            user_id=user_id,
            prior_entries={person: {"full_name": "Legacy", "department": "A", "position_raw": "Old"}},
            new_entries={person: {"full_name": "Legacy", "department": "B", "position_raw": "Old"}},
        )
        legacy = materialize_snapshot_change_events(
            conn,
            prior_snapshot_id=prior_id,
            new_snapshot_id=new_id,
        )
        assert legacy["event_count"] >= 1
        assert "DEPARTMENT_CHANGED" in legacy.get("summary", {})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_event_hash_stable():
    h1 = compute_personnel_event_hash(
        previous_snapshot_id=1,
        snapshot_id=2,
        person_key="iin:123",
        assignment_key="iin:123|a|doc|primary",
        event_type=EVENT_NEW_PERSON,
        field_path=None,
        effective_old_value=None,
        effective_new_value={"full_name": "A"},
    )
    h2 = compute_personnel_event_hash(
        previous_snapshot_id=1,
        snapshot_id=2,
        person_key="iin:123",
        assignment_key="iin:123|a|doc|primary",
        event_type=EVENT_NEW_PERSON,
        field_path=None,
        effective_old_value=None,
        effective_new_value={"full_name": "A"},
    )
    assert h1 == h2
    assert len(h1) == 64
