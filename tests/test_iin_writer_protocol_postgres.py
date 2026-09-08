"""PostgreSQL integration tests for the shared transaction IIN writer protocol."""
from __future__ import annotations

import logging
import threading
import time
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.iin_writer_protocol import (
    IinWriterProtocolError,
    ensure_employee_iin_identity_tx,
    lock_and_recheck_iin_tx,
)
from tests.ppr.conftest import cleanup_person_graph, insert_employee, insert_person


def _available() -> bool:
    try:
        with engine.connect() as conn:
            return str(conn.execute(text("SELECT current_database()")).scalar_one()).lower() == "corpsite_test"
    except Exception:
        return False


def _iin(seed: int) -> str:
    return f"{700_000_000_000 + seed:012d}"


@pytest.fixture
def people():
    person_ids: list[int] = []
    employee_ids: list[int] = []
    with engine.begin() as conn:
        for index in range(2):
            person_id = insert_person(conn, full_name=f"IIN Protocol {uuid4().hex[:10]} {index}")
            employee_id = insert_employee(conn, full_name=f"IIN Protocol {index}", person_id=person_id)
            person_ids.append(person_id)
            employee_ids.append(employee_id)
    try:
        yield person_ids, employee_ids
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)


@pytest.mark.skipif(not _available(), reason="corpsite_test PostgreSQL not available")
def test_same_iin_lock_serializes_and_different_iin_does_not(people):
    same = _iin(uuid4().int % 100_000_000)
    other = _iin((uuid4().int % 100_000_000) + 100_000_000)
    held = threading.Event()
    release = threading.Event()
    acquired = threading.Event()

    def holder():
        with engine.connect() as conn:
            tx = conn.begin()
            try:
                lock_and_recheck_iin_tx(conn, iin=same)
                held.set()
                assert release.wait(5)
                tx.commit()
            finally:
                if tx.is_active:
                    tx.rollback()

    def waiter():
        assert held.wait(5)
        with engine.connect() as conn:
            tx = conn.begin()
            try:
                lock_and_recheck_iin_tx(conn, iin=same)
                acquired.set()
                tx.commit()
            finally:
                if tx.is_active:
                    tx.rollback()

    first = threading.Thread(target=holder)
    second = threading.Thread(target=waiter)
    first.start(); assert held.wait(5)
    with engine.connect() as conn:
        tx = conn.begin()
        lock_and_recheck_iin_tx(conn, iin=other)
        tx.commit()
    second.start()
    assert not acquired.wait(0.25)
    release.set()
    first.join(5); second.join(5)
    assert acquired.is_set()


@pytest.mark.skipif(not _available(), reason="corpsite_test PostgreSQL not available")
def test_concurrent_claim_is_one_write_one_safe_conflict_and_consistent(people, caplog):
    person_ids, employee_ids = people
    value = _iin(uuid4().int % 100_000_000)
    barrier = threading.Barrier(2)
    results: list[str] = []
    results_lock = threading.Lock()

    def claim(person_id: int, employee_id: int):
        with engine.connect() as conn:
            tx = conn.begin()
            try:
                barrier.wait(5)
                state = lock_and_recheck_iin_tx(conn, iin=value)
                if state.person_ids and person_id not in state.person_ids:
                    outcome = "IIN_PERSON_CONFLICT"
                    tx.rollback()
                else:
                    conn.execute(
                        text("UPDATE public.persons SET iin=:iin WHERE person_id=:person_id AND iin IS NULL"),
                        {"iin": value, "person_id": person_id},
                    )
                    ensure_employee_iin_identity_tx(
                        conn, employee_id=employee_id, iin=value, created_by=1
                    )
                    tx.commit()
                    outcome = "APPLIED"
                with results_lock:
                    results.append(outcome)
            except Exception:
                if tx.is_active:
                    tx.rollback()
                raise

    with caplog.at_level(logging.INFO):
        threads = [threading.Thread(target=claim, args=pair) for pair in zip(person_ids, employee_ids)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(8)
    assert sorted(results) == ["APPLIED", "IIN_PERSON_CONFLICT"]
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT person_id FROM public.persons WHERE iin=:iin ORDER BY person_id"), {"iin": value}
        ).scalars().all()
        identities = conn.execute(
            text("SELECT employee_id FROM public.employee_identities WHERE identity_type='IIN' AND identity_value=:iin AND valid_to IS NULL"),
            {"iin": value},
        ).scalars().all()
    assert len(rows) == len(identities) == 1
    assert value not in caplog.text


@pytest.mark.skipif(not _available(), reason="corpsite_test PostgreSQL not available")
def test_rollback_releases_lock_and_leaves_no_partial_identity(people):
    person_id, employee_id = people[0][0], people[1][0]
    value = _iin(uuid4().int % 100_000_000)
    with engine.connect() as conn:
        tx = conn.begin()
        lock_and_recheck_iin_tx(conn, iin=value)
        conn.execute(text("UPDATE public.persons SET iin=:iin WHERE person_id=:person_id"), {"iin": value, "person_id": person_id})
        ensure_employee_iin_identity_tx(conn, employee_id=employee_id, iin=value, created_by=1)
        tx.rollback()
    with engine.begin() as conn:
        state = lock_and_recheck_iin_tx(conn, iin=value)
        assert state.person_ids == ()
        assert state.active_identity_ids == ()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT iin FROM public.persons WHERE person_id=:id"), {"id": person_id}).scalar_one() is None


def test_protocol_error_never_contains_full_iin():
    value = _iin(1)
    with pytest.raises(IinWriterProtocolError) as exc:
        # No connection needed: input validation occurs before SQL.
        from app.services.iin_writer_protocol import acquire_iin_advisory_locks_tx
        acquire_iin_advisory_locks_tx(None, ["invalid"])  # type: ignore[arg-type]
    assert value not in str(exc.value)
