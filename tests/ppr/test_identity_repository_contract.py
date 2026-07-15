# tests/ppr/test_identity_repository_contract.py
"""Contract tests for SqlAlchemyIdentityRepository (PPR R2)."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.ppr.domain.errors import (
    PprEmployeeNotFoundError,
    PprEmployeePersonLinkMissingError,
    PprPersonNotFoundError,
)
from app.ppr.domain.identity_models import (
    INPUT_KIND_EMPLOYEE_ID,
    INPUT_KIND_PERSON_ID,
    RESULT_DIRECT,
    RESULT_MERGE_REDIRECTED,
)
from app.ppr.infrastructure.identity_repository import SqlAlchemyIdentityRepository
from tests.ppr.conftest import (
    cleanup_person_graph,
    insert_employee,
    insert_person,
    ppr_db_available,
    require_ppr_schema,
)


@pytest.fixture
def identity_person():
    require_ppr_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"PPR Identity Active {suffix}")
    yield person_id
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])


@pytest.fixture
def identity_merge_chain():
    require_ppr_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        survivor_id = insert_person(conn, full_name=f"PPR Survivor {suffix}")
        mid_id = insert_person(
            conn,
            full_name=f"PPR Mid {suffix}",
            person_status="merged",
            merged_into_person_id=survivor_id,
        )
        loser_id = insert_person(
            conn,
            full_name=f"PPR Loser {suffix}",
            person_status="merged",
            merged_into_person_id=mid_id,
        )
    yield {"survivor": survivor_id, "mid": mid_id, "loser": loser_id}
    with engine.begin() as conn:
        cleanup_person_graph(
            conn,
            person_ids=[loser_id, mid_id, survivor_id],
            employee_ids=[],
        )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_resolve_active_person_id(identity_person: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyIdentityRepository(conn)
        result = repo.resolve_person_id(identity_person)

    assert result.input_kind == INPUT_KIND_PERSON_ID
    assert result.input_id == identity_person
    assert result.employee_id is None
    assert result.source_person_id == identity_person
    assert result.resolved_person_id == identity_person
    assert result.merge_redirected is False
    assert result.result_code == RESULT_DIRECT
    assert result.merge_chain == (identity_person,)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_resolve_employee_id_with_linked_person(identity_person: int) -> None:
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        employee_id = insert_employee(
            conn,
            full_name=f"PPR Emp Linked {suffix}",
            person_id=identity_person,
        )
        repo = SqlAlchemyIdentityRepository(conn)
        result = repo.resolve_employee_id(employee_id)

    assert result.input_kind == INPUT_KIND_EMPLOYEE_ID
    assert result.employee_id == employee_id
    assert result.resolved_person_id == identity_person
    assert result.merge_redirected is False

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[], employee_ids=[employee_id])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_employee_not_found() -> None:
    require_ppr_schema()
    with engine.begin() as conn:
        repo = SqlAlchemyIdentityRepository(conn)
        with pytest.raises(PprEmployeeNotFoundError):
            repo.resolve_employee_id(9_999_999_999)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_employee_without_person_id_fails_closed() -> None:
    require_ppr_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        employee_id = insert_employee(conn, full_name=f"PPR Orphan Emp {suffix}", person_id=None)
        repo = SqlAlchemyIdentityRepository(conn)
        with pytest.raises(PprEmployeePersonLinkMissingError):
            repo.resolve_employee_id(employee_id)
        cleanup_person_graph(conn, person_ids=[], employee_ids=[employee_id])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_person_not_found() -> None:
    require_ppr_schema()
    with engine.begin() as conn:
        repo = SqlAlchemyIdentityRepository(conn)
        with pytest.raises(PprPersonNotFoundError):
            repo.resolve_person_id(9_999_999_999)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_merged_loser_resolves_to_survivor(identity_merge_chain: dict[str, int]) -> None:
    loser_id = identity_merge_chain["loser"]
    survivor_id = identity_merge_chain["survivor"]
    with engine.begin() as conn:
        repo = SqlAlchemyIdentityRepository(conn)
        result = repo.resolve_person_id(loser_id)

    assert result.source_person_id == loser_id
    assert result.resolved_person_id == survivor_id
    assert result.merge_redirected is True
    assert result.result_code == RESULT_MERGE_REDIRECTED
    assert result.merge_chain == (loser_id, identity_merge_chain["mid"], survivor_id)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_merge_chain_preserves_source_person_id(identity_merge_chain: dict[str, int]) -> None:
    loser_id = identity_merge_chain["loser"]
    with engine.begin() as conn:
        employee_id = insert_employee(
            conn,
            full_name=f"PPR Emp Loser {uuid4().hex[:6]}",
            person_id=loser_id,
        )
        repo = SqlAlchemyIdentityRepository(conn)
        result = repo.resolve_employee_id(employee_id)

    assert result.source_person_id == loser_id
    assert result.resolved_person_id == identity_merge_chain["survivor"]

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[], employee_ids=[employee_id])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_two_employees_same_person_resolve_identically(identity_person: int) -> None:
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        emp_active = insert_employee(
            conn,
            full_name=f"PPR Active Emp {suffix}",
            person_id=identity_person,
            operational_status="active",
        )
        emp_terminated = insert_employee(
            conn,
            full_name=f"PPR Term Emp {suffix}",
            person_id=identity_person,
            is_active=False,
            operational_status="terminated",
        )
        repo = SqlAlchemyIdentityRepository(conn)
        res_a = repo.resolve_employee_id(emp_active)
        res_b = repo.resolve_employee_id(emp_terminated)

    assert res_a.resolved_person_id == identity_person
    assert res_b.resolved_person_id == identity_person
    assert res_a.resolved_person_id == res_b.resolved_person_id

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[], employee_ids=[emp_active, emp_terminated])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_inactive_employee_still_resolvable(identity_person: int) -> None:
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        employee_id = insert_employee(
            conn,
            full_name=f"PPR Inactive Emp {suffix}",
            person_id=identity_person,
            is_active=False,
            operational_status="terminated",
        )
        repo = SqlAlchemyIdentityRepository(conn)
        result = repo.resolve_employee_id(employee_id)
        cleanup_person_graph(conn, person_ids=[], employee_ids=[employee_id])

    assert result.resolved_person_id == identity_person


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_resolve_survivor_stable(identity_merge_chain: dict[str, int]) -> None:
    survivor_id = identity_merge_chain["survivor"]
    with engine.begin() as conn:
        repo = SqlAlchemyIdentityRepository(conn)
        assert repo.resolve_survivor(survivor_id) == survivor_id
        assert repo.resolve_survivor(identity_merge_chain["loser"]) == survivor_id


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_repeated_resolution_deterministic(identity_merge_chain: dict[str, int]) -> None:
    loser_id = identity_merge_chain["loser"]
    with engine.begin() as conn:
        repo = SqlAlchemyIdentityRepository(conn)
        first = repo.resolve_person_id(loser_id)
        second = repo.resolve_person_id(loser_id)
    assert first == second


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_resolver_does_not_write_persons(identity_person: int) -> None:
    with engine.begin() as conn:
        before = conn.execute(
            text("SELECT person_status, merged_into_person_id FROM public.persons WHERE person_id = :pid"),
            {"pid": identity_person},
        ).mappings().one()
        repo = SqlAlchemyIdentityRepository(conn)
        repo.resolve_person_id(identity_person)
        after = conn.execute(
            text("SELECT person_status, merged_into_person_id FROM public.persons WHERE person_id = :pid"),
            {"pid": identity_person},
        ).mappings().one()
    assert dict(before) == dict(after)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_resolver_does_not_create_envelope(identity_person: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyIdentityRepository(conn)
        repo.resolve_person_id(identity_person)
        count = conn.execute(
            text(
                "SELECT COUNT(*) FROM public.personnel_record_metadata WHERE person_id = :pid"
            ),
            {"pid": identity_person},
        ).scalar_one()
    assert int(count) == 0


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_resolver_does_not_create_events(identity_person: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyIdentityRepository(conn)
        repo.resolve_person_id(identity_person)
        count = conn.execute(
            text("SELECT COUNT(*) FROM public.personnel_record_events WHERE person_id = :pid"),
            {"pid": identity_person},
        ).scalar_one()
    assert int(count) == 0


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_load_identity_returns_direct_row(identity_merge_chain: dict[str, int]) -> None:
    loser_id = identity_merge_chain["loser"]
    with engine.begin() as conn:
        repo = SqlAlchemyIdentityRepository(conn)
        identity = repo.load_identity(loser_id)
    assert identity.person_id == loser_id
    assert identity.person_status == "merged"
    assert identity.merged_into_person_id == identity_merge_chain["mid"]
