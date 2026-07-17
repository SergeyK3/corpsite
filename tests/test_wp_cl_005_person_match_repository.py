# tests/test_wp_cl_005_person_match_repository.py
"""PostgreSQL contract tests for SqlAlchemyPersonMatchReadRepository (WP-CL-005)."""
from __future__ import annotations

import inspect
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.control_list_import.domain.person_match_repository import PersonMatchReadPort
from app.control_list_import.infrastructure.person_match_repository import (
    SqlAlchemyPersonMatchReadRepository,
)
from app.control_list_import.matching.keys import person_fio_comparison_key
from app.db.engine import engine
from app.ppr.domain.errors import PprMergeCycleError, PprPersonNotFoundError
from tests.conftest import get_columns, insert_returning_id
from tests.ppr.conftest import cleanup_person_graph, insert_person, ppr_db_available, require_ppr_schema


def _unique_iin() -> str:
    return f"{uuid4().int % 10**12:012d}"


def _insert_match_person(
    conn,
    *,
    full_name: str,
    iin: str | None = None,
    birth_date: date | None = None,
    person_status: str = "active",
    merged_into_person_id: int | None = None,
    prefix: str = "cl-match",
) -> int:
    suffix = uuid4().hex[:12]
    cols = get_columns(conn, "persons")
    values: dict[str, object] = {
        "full_name": full_name,
        "match_key": f"{prefix}:{suffix}",
        "source": "manual",
        "person_status": person_status,
    }
    if iin is not None and "iin" in cols:
        values["iin"] = iin
    if birth_date is not None and "birth_date" in cols:
        values["birth_date"] = birth_date
    if merged_into_person_id is not None and "merged_into_person_id" in cols:
        values["merged_into_person_id"] = merged_into_person_id
    return insert_returning_id(conn, table="persons", id_col="person_id", values=values)


@pytest.fixture
def match_repo_persons():
    require_ppr_schema()
    suffix = uuid4().hex[:8]
    full_name = f"Сейтова Айжан Нурлыбековна {suffix}"
    iin = _unique_iin()
    birth_date = date(1990, 3, 15)
    normalized_fio = person_fio_comparison_key(full_name)
    assert normalized_fio is not None

    with engine.begin() as conn:
        person_id = _insert_match_person(
            conn,
            full_name=full_name,
            iin=iin,
            birth_date=birth_date,
            person_status="active",
        )
    payload = {
        "person_id": person_id,
        "full_name": full_name,
        "iin": iin,
        "birth_date": birth_date,
        "normalized_fio": normalized_fio,
    }
    yield payload
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])


@pytest.fixture
def match_repo_merge_chain():
    require_ppr_schema()
    suffix = uuid4().hex[:8]
    full_name = f"Иванов Иван Иванович {suffix}"
    iin = _unique_iin()
    birth_date = date(1988, 7, 20)
    normalized_fio = person_fio_comparison_key(full_name)
    assert normalized_fio is not None

    with engine.begin() as conn:
        survivor_id = _insert_match_person(
            conn,
            full_name=full_name,
            iin=iin,
            birth_date=birth_date,
            person_status="inactive",
        )
        loser_id = _insert_match_person(
            conn,
            full_name=f"Merged Loser {suffix}",
            iin=None,
            birth_date=birth_date,
            person_status="merged",
            merged_into_person_id=survivor_id,
        )
    payload = {
        "survivor_id": survivor_id,
        "loser_id": loser_id,
        "full_name": full_name,
        "iin": iin,
        "birth_date": birth_date,
        "normalized_fio": normalized_fio,
    }
    yield payload
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[loser_id, survivor_id], employee_ids=[])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_find_by_iin_returns_active_or_inactive_person(match_repo_persons: dict) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPersonMatchReadRepository(conn)
        hits = repo.find_by_iin(match_repo_persons["iin"])

    assert len(hits) == 1
    assert hits[0].person_id == match_repo_persons["person_id"]
    assert hits[0].iin == match_repo_persons["iin"]


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_find_by_fio_and_birth_date(match_repo_persons: dict) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPersonMatchReadRepository(conn)
        hits = repo.find_by_fio_and_birth_date(
            normalized_fio_key=match_repo_persons["normalized_fio"],
            birth_date=match_repo_persons["birth_date"],
        )

    assert len(hits) == 1
    assert hits[0].person_id == match_repo_persons["person_id"]
    assert hits[0].birth_date == match_repo_persons["birth_date"]


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_find_by_normalized_fio(match_repo_persons: dict) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPersonMatchReadRepository(conn)
        hits = repo.find_by_normalized_fio(match_repo_persons["normalized_fio"])

    assert len(hits) == 1
    assert hits[0].person_id == match_repo_persons["person_id"]


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_inactive_merged_loser_resolves_to_survivor(match_repo_merge_chain: dict) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPersonMatchReadRepository(conn)
        assert repo.resolve_survivor(match_repo_merge_chain["loser_id"]) == match_repo_merge_chain["survivor_id"]
        survivor = repo.load_person(match_repo_merge_chain["survivor_id"])
        assert survivor is not None
        assert survivor.person_status == "inactive"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_loser_and_survivor_resolve_to_same_person_id(match_repo_merge_chain: dict) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPersonMatchReadRepository(conn)
        from_loser = repo.resolve_survivor(match_repo_merge_chain["loser_id"])
        from_survivor = repo.resolve_survivor(match_repo_merge_chain["survivor_id"])

    assert from_loser == from_survivor == match_repo_merge_chain["survivor_id"]


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_find_by_iin_dedupes_to_single_survivor(match_repo_merge_chain: dict) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPersonMatchReadRepository(conn)
        hits = repo.find_by_iin(match_repo_merge_chain["iin"])

    assert len(hits) == 1
    assert hits[0].person_id == match_repo_merge_chain["survivor_id"]
    assert hits[0].person_status == "inactive"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_find_by_fio_and_birth_date_dedupes_loser_and_survivor_to_one_result(
    match_repo_merge_chain: dict,
) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPersonMatchReadRepository(conn)
        hits = repo.find_by_fio_and_birth_date(
            normalized_fio_key=match_repo_merge_chain["normalized_fio"],
            birth_date=match_repo_merge_chain["birth_date"],
        )

    assert len(hits) == 1
    assert hits[0].person_id == match_repo_merge_chain["survivor_id"]


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_resolve_survivor_missing_person_fails_closed() -> None:
    require_ppr_schema()
    with engine.begin() as conn:
        repo = SqlAlchemyPersonMatchReadRepository(conn)
        with pytest.raises(PprPersonNotFoundError):
            repo.resolve_survivor(9_999_999_999)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_resolve_survivor_merge_cycle_fails_closed() -> None:
    require_ppr_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        anchor_id = _insert_match_person(conn, full_name=f"Cycle Anchor {suffix}", person_status="active")
        first_id = _insert_match_person(
            conn,
            full_name=f"Cycle A {suffix}",
            person_status="merged",
            merged_into_person_id=anchor_id,
        )
        second_id = _insert_match_person(
            conn,
            full_name=f"Cycle B {suffix}",
            person_status="merged",
            merged_into_person_id=first_id,
        )
        conn.execute(
            text(
                """
                UPDATE public.persons
                SET person_status = 'merged', merged_into_person_id = :second_id
                WHERE person_id = :first_id
                """
            ),
            {"first_id": first_id, "second_id": second_id},
        )
        conn.execute(
            text(
                """
                UPDATE public.persons
                SET merged_into_person_id = :first_id
                WHERE person_id = :second_id
                """
            ),
            {"first_id": first_id, "second_id": second_id},
        )
        repo = SqlAlchemyPersonMatchReadRepository(conn)
        with pytest.raises(PprMergeCycleError):
            repo.resolve_survivor(first_id)
        cleanup_person_graph(conn, person_ids=[first_id, second_id, anchor_id], employee_ids=[])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_repository_is_read_only(match_repo_persons: dict) -> None:
    person_id = match_repo_persons["person_id"]
    with engine.begin() as conn:
        before = conn.execute(
            text(
                """
                SELECT full_name, iin, birth_date, person_status, merged_into_person_id
                FROM public.persons
                WHERE person_id = :pid
                """
            ),
            {"pid": person_id},
        ).mappings().one()
        repo = SqlAlchemyPersonMatchReadRepository(conn)
        repo.find_by_iin(match_repo_persons["iin"])
        repo.find_by_fio_and_birth_date(
            normalized_fio_key=match_repo_persons["normalized_fio"],
            birth_date=match_repo_persons["birth_date"],
        )
        repo.find_by_normalized_fio(match_repo_persons["normalized_fio"])
        repo.resolve_survivor(person_id)
        repo.load_person(person_id)
        after = conn.execute(
            text(
                """
                SELECT full_name, iin, birth_date, person_status, merged_into_person_id
                FROM public.persons
                WHERE person_id = :pid
                """
            ),
            {"pid": person_id},
        ).mappings().one()
    assert dict(before) == dict(after)


def test_repository_has_no_mutation_or_employee_methods() -> None:
    public_methods = {
        name
        for name, member in inspect.getmembers(SqlAlchemyPersonMatchReadRepository, predicate=inspect.isfunction)
        if not name.startswith("_")
    }
    assert public_methods == {
        "find_by_iin",
        "find_by_fio_and_birth_date",
        "find_by_normalized_fio",
        "resolve_survivor",
        "load_person",
    }
    source = inspect.getsource(SqlAlchemyPersonMatchReadRepository)
    assert "employee_id" not in source
    assert "INSERT INTO" not in source.upper()
    assert "UPDATE public.persons" not in source
    assert "DELETE FROM" not in source.upper()


def test_repository_implements_read_port_protocol() -> None:
    assert hasattr(PersonMatchReadPort, "find_by_iin")
    assert hasattr(PersonMatchReadPort, "find_by_fio_and_birth_date")
    assert hasattr(PersonMatchReadPort, "find_by_normalized_fio")
    assert hasattr(PersonMatchReadPort, "resolve_survivor")
    assert hasattr(PersonMatchReadPort, "load_person")
