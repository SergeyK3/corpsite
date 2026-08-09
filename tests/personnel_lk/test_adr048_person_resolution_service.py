"""Authority-level tests for the ADR-048 read-only exact-IIN resolution port."""
from __future__ import annotations

from contextlib import contextmanager
from uuid import uuid4

import pytest
from sqlalchemy import event, text

from app.db.engine import engine
from app.services.adr048_person_resolution_service import (
    resolve_person_create_or_link_exact_iin_tx,
)
from tests.conftest import table_exists
from tests.personnel_applications.conftest import insert_person_with_iin
from tests.personnel_lk.conftest import require_personnel_lk_schema, unique_iin
from tests.ppr.conftest import insert_employee, ppr_db_available


@pytest.fixture(autouse=True)
def _schema() -> None:
    ppr_db_available()
    require_personnel_lk_schema()
    with engine.begin() as conn:
        if not table_exists(conn, "persons"):
            pytest.skip("ADR-048 Person schema is unavailable")


@contextmanager
def _persons(*, statuses: tuple[str, ...]):
    iin = unique_iin("6")
    person_ids: list[int] = []
    employee_ids: list[int] = []
    survivor_ids: list[int] = []
    with engine.begin() as conn:
        for status in statuses:
            person_id = insert_person_with_iin(
                conn,
                full_name=f"ADR048 authority {uuid4().hex[:10]}",
                iin=iin,
                prefix="adr048-authority",
            )
            person_ids.append(person_id)
            if status == "merged":
                survivor_id = insert_person_with_iin(
                    conn,
                    full_name=f"ADR048 survivor {uuid4().hex[:10]}",
                    iin=None,
                    prefix="adr048-survivor",
                )
                survivor_ids.append(survivor_id)
                conn.execute(
                    text(
                        "UPDATE public.persons "
                        "SET person_status='merged', merged_into_person_id=:survivor "
                        "WHERE person_id=:person_id"
                    ),
                    {"survivor": survivor_id, "person_id": person_id},
                )
            elif status != "active":
                conn.execute(
                    text(
                        "UPDATE public.persons SET person_status=:status "
                        "WHERE person_id=:person_id"
                    ),
                    {"status": status, "person_id": person_id},
                )
    try:
        yield {
            "iin": iin,
            "person_ids": person_ids,
            "employee_ids": employee_ids,
            "survivor_ids": survivor_ids,
        }
    finally:
        with engine.begin() as conn:
            if employee_ids:
                conn.execute(
                    text("DELETE FROM public.employees WHERE employee_id=ANY(:ids)"),
                    {"ids": employee_ids},
                )
            if person_ids:
                conn.execute(
                    text("DELETE FROM public.persons WHERE person_id=ANY(:ids)"),
                    {"ids": person_ids},
                )
            if survivor_ids:
                conn.execute(
                    text("DELETE FROM public.persons WHERE person_id=ANY(:ids)"),
                    {"ids": survivor_ids},
                )


def _resolve(iin: str, *, target_employee_id: int | None = None):
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            conn.exec_driver_sql(
                "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
            )
            result = resolve_person_create_or_link_exact_iin_tx(
                conn,
                iin=iin,
                target_employee_id=target_employee_id,
            )
            assert conn.in_transaction()
            return result
        finally:
            transaction.rollback()


def test_no_candidate_returns_p0() -> None:
    result = _resolve(unique_iin("5"))
    assert result.decision == "P0_CREATE"
    assert result.candidates == ()


def test_single_compatible_candidate_returns_p1() -> None:
    with _persons(statuses=("active",)) as state:
        result = _resolve(state["iin"])
        assert result.decision == "P1_ADOPT"
        assert [candidate.person_id for candidate in result.candidates] == state["person_ids"]
        assert result.candidates[0].compatible is True


@pytest.mark.parametrize(
    ("status", "reason"),
    [("inactive", "PERSON_INACTIVE"), ("merged", "PERSON_MERGED")],
)
def test_inactive_and_merged_candidates_are_incompatible(status: str, reason: str) -> None:
    with _persons(statuses=(status,)) as state:
        result = _resolve(state["iin"])
        assert result.decision == "INCOMPATIBLE"
        assert result.candidates[0].incompatibility_reasons == (reason,)


def test_multiple_exact_identity_rows_are_ambiguous() -> None:
    with _persons(statuses=("inactive", "active")) as state:
        result = _resolve(state["iin"])
        assert result.decision == "AMBIGUOUS"
        assert [candidate.person_id for candidate in result.candidates] == sorted(
            state["person_ids"]
        )
        assert result.reason_codes == (
            "PERSON_IDENTITY_AMBIGUOUS",
            "PERSON_CANDIDATE_INCOMPATIBLE",
        )


def test_active_employee_owner_conflict_is_rejected() -> None:
    with _persons(statuses=("active",)) as state:
        with engine.begin() as conn:
            employee_id = insert_employee(
                conn,
                full_name=f"ADR048 conflicting employee {uuid4().hex[:8]}",
                person_id=state["person_ids"][0],
            )
            state["employee_ids"].append(employee_id)
        result = _resolve(state["iin"], target_employee_id=employee_id + 1)
        assert result.decision == "CONFLICT"
        assert result.candidates[0].conflicting_employee_ids == (employee_id,)
        assert result.candidates[0].incompatibility_reasons == (
            "PERSON_ACTIVE_EMPLOYEE_CONFLICT",
        )


def test_target_employee_existing_same_link_is_authority_conflict() -> None:
    with _persons(statuses=("active",)) as state:
        with engine.begin() as conn:
            employee_id = insert_employee(
                conn,
                full_name=f"ADR048 already linked {uuid4().hex[:8]}",
                person_id=state["person_ids"][0],
            )
            state["employee_ids"].append(employee_id)
        result = _resolve(state["iin"], target_employee_id=employee_id)
        assert result.decision == "CONFLICT"
        assert result.reason_codes == ("TARGET_EMPLOYEE_ALREADY_LINKED",)


def test_target_employee_different_person_link_is_authority_conflict() -> None:
    with _persons(statuses=("active",)) as state:
        with engine.begin() as conn:
            other_person_id = insert_person_with_iin(
                conn,
                full_name=f"ADR048 different Person {uuid4().hex[:8]}",
                iin=unique_iin("4"),
                prefix="adr048-different",
            )
            state["person_ids"].append(other_person_id)
            employee_id = insert_employee(
                conn,
                full_name=f"ADR048 mismatched link {uuid4().hex[:8]}",
                person_id=other_person_id,
            )
            state["employee_ids"].append(employee_id)
        result = _resolve(state["iin"], target_employee_id=employee_id)
        assert result.decision == "CONFLICT"
        assert result.reason_codes == ("TARGET_EMPLOYEE_PERSON_IDENTITY_CONFLICT",)


def test_port_uses_caller_owned_read_only_transaction_and_has_no_writes() -> None:
    statements: list[str] = []

    def observe(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.strip().split(maxsplit=1)[0].upper())

    with _persons(statuses=("active",)) as state:
        with engine.connect() as snapshot:
            before = snapshot.execute(
                text(
                    "SELECT person_id, person_status, merged_into_person_id, updated_at "
                    "FROM public.persons WHERE person_id=ANY(:ids) ORDER BY person_id"
                ),
                {"ids": state["person_ids"]},
            ).all()
            sequence_before = snapshot.execute(
                text(
                    "SELECT last_value FROM public.persons_person_id_seq"
                )
            ).scalar_one()
        event.listen(engine, "before_cursor_execute", observe)
        try:
            result = _resolve(state["iin"])
        finally:
            event.remove(engine, "before_cursor_execute", observe)
        with engine.connect() as snapshot:
            after = snapshot.execute(
                text(
                    "SELECT person_id, person_status, merged_into_person_id, updated_at "
                    "FROM public.persons WHERE person_id=ANY(:ids) ORDER BY person_id"
                ),
                {"ids": state["person_ids"]},
            ).all()
            sequence_after = snapshot.execute(
                text(
                    "SELECT last_value FROM public.persons_person_id_seq"
                )
            ).scalar_one()
        assert result.decision == "P1_ADOPT"
        assert after == before
        assert sequence_after == sequence_before
        assert set(statements) <= {"SELECT", "SET"}
