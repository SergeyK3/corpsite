# tests/ppr/test_person_repository_contract.py
"""Contract tests for SqlAlchemyPersonRepository (PPR R2 read-only)."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.ppr.domain.errors import PprPersonNotFoundError
from app.ppr.domain.person_models import (
    AUDIT_READ_FIELDS,
    IDENTITY_READ_FIELD_IIN,
    IDENTITY_READ_FIELDS,
    PPR_CADRE_READ_FIELDS,
    PPR_WRITABLE_FIELD_NAMES,
    PersonGeneralReadSnapshot,
)
from app.ppr.domain.person_repositories import PersonRepository
from app.ppr.infrastructure.person_repository import SqlAlchemyPersonRepository
from tests.conftest import get_columns, insert_returning_id
from tests.ppr.conftest import (
    cleanup_person_graph,
    insert_person,
    ppr_db_available,
    require_ppr_schema,
)


@pytest.fixture
def cadre_person_id():
    require_ppr_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"PPR Read Person {suffix}")
    yield person_id
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_load_general_read_snapshot_for_existing_person(cadre_person_id: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPersonRepository(conn)
        snapshot = repo.load_general_read_snapshot(cadre_person_id)

    assert isinstance(snapshot, PersonGeneralReadSnapshot)
    assert snapshot.person_id == cadre_person_id
    assert snapshot.full_name.startswith("PPR Read Person")
    assert snapshot.created_at is not None
    assert snapshot.updated_at is not None


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_load_general_read_snapshot_missing_person() -> None:
    require_ppr_schema()
    with engine.begin() as conn:
        repo = SqlAlchemyPersonRepository(conn)
        with pytest.raises(PprPersonNotFoundError):
            repo.load_general_read_snapshot(9_999_999_999)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_snapshot_is_domain_shaped_not_orm_row(cadre_person_id: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPersonRepository(conn)
        snapshot = repo.load_general_read_snapshot(cadre_person_id)
    assert type(snapshot).__name__ == "PersonGeneralReadSnapshot"
    assert not hasattr(snapshot, "_sa_instance_state")


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_iin_readable_as_identity_sourced_field() -> None:
    require_ppr_schema()
    suffix = uuid4().hex[:8]
    iin = "800115300290"
    with engine.begin() as conn:
        cols = get_columns(conn, "persons")
        values: dict[str, object] = {
            "full_name": f"PPR IIN Read {suffix}",
            "match_key": f"ppr-iin:{suffix}",
            "source": "manual",
            "person_status": "active",
            "iin": iin,
        }
        values = {k: v for k, v in values.items() if k in cols}
        person_id = insert_returning_id(
            conn, table="persons", id_col="person_id", values=values
        )
        repo = SqlAlchemyPersonRepository(conn)
        snapshot = repo.load_general_read_snapshot(person_id)
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])

    assert snapshot.iin == iin


def test_iin_not_classified_as_ppr_writable() -> None:
    assert IDENTITY_READ_FIELD_IIN in IDENTITY_READ_FIELDS
    assert IDENTITY_READ_FIELD_IIN not in PPR_CADRE_READ_FIELDS
    assert IDENTITY_READ_FIELD_IIN not in PPR_WRITABLE_FIELD_NAMES


def test_person_repository_protocol_has_no_update_method() -> None:
    assert hasattr(PersonRepository, "load_general_read_snapshot")
    assert not hasattr(PersonRepository, "update_cadre_fields")
    assert not hasattr(PersonRepository, "update_general_read_snapshot")


def test_sqlalchemy_person_repository_has_no_update_method() -> None:
    assert hasattr(SqlAlchemyPersonRepository, "load_general_read_snapshot")
    assert not hasattr(SqlAlchemyPersonRepository, "update_cadre_fields")


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_repository_does_not_modify_persons(cadre_person_id: int) -> None:
    with engine.begin() as conn:
        before = conn.execute(
            text("SELECT full_name, iin FROM public.persons WHERE person_id = :pid"),
            {"pid": cadre_person_id},
        ).mappings().one()
        repo = SqlAlchemyPersonRepository(conn)
        repo.load_general_read_snapshot(cadre_person_id)
        after = conn.execute(
            text("SELECT full_name, iin FROM public.persons WHERE person_id = :pid"),
            {"pid": cadre_person_id},
        ).mappings().one()
    assert dict(before) == dict(after)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_full_name_and_name_parts_are_read_only_snapshot_data(cadre_person_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE public.persons
                SET last_name = 'Ivanov', first_name = 'Ivan', middle_name = 'Ivanovich'
                WHERE person_id = :pid
                """
            ),
            {"pid": cadre_person_id},
        )
        repo = SqlAlchemyPersonRepository(conn)
        snapshot = repo.load_general_read_snapshot(cadre_person_id)

    assert snapshot.full_name is not None
    assert snapshot.last_name == "Ivanov"
    assert snapshot.first_name == "Ivan"
    assert snapshot.middle_name == "Ivanovich"


def test_field_classifications_are_separate() -> None:
    assert PPR_CADRE_READ_FIELDS.isdisjoint(IDENTITY_READ_FIELDS)
    assert PPR_CADRE_READ_FIELDS.isdisjoint(AUDIT_READ_FIELDS)
    assert IDENTITY_READ_FIELDS.isdisjoint(AUDIT_READ_FIELDS)
    assert PPR_WRITABLE_FIELD_NAMES == frozenset()


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_repository_does_not_create_envelope(cadre_person_id: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPersonRepository(conn)
        repo.load_general_read_snapshot(cadre_person_id)
        count = conn.execute(
            text("SELECT COUNT(*) FROM public.personnel_record_metadata WHERE person_id = :pid"),
            {"pid": cadre_person_id},
        ).scalar_one()
    assert int(count) == 0


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_repository_does_not_create_events(cadre_person_id: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPersonRepository(conn)
        repo.load_general_read_snapshot(cadre_person_id)
        count = conn.execute(
            text("SELECT COUNT(*) FROM public.personnel_record_events WHERE person_id = :pid"),
            {"pid": cadre_person_id},
        ).scalar_one()
    assert int(count) == 0


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_repository_does_not_modify_employees(cadre_person_id: int) -> None:
    suffix = uuid4().hex[:6]
    with engine.begin() as conn:
        from tests.ppr.conftest import insert_employee

        employee_id = insert_employee(
            conn,
            full_name=f"PPR Emp {suffix}",
            person_id=cadre_person_id,
        )
        before = conn.execute(
            text("SELECT full_name FROM public.employees WHERE employee_id = :eid"),
            {"eid": employee_id},
        ).scalar_one()
        repo = SqlAlchemyPersonRepository(conn)
        repo.load_general_read_snapshot(cadre_person_id)
        after = conn.execute(
            text("SELECT full_name FROM public.employees WHERE employee_id = :eid"),
            {"eid": employee_id},
        ).scalar_one()
        cleanup_person_graph(conn, person_ids=[], employee_ids=[employee_id])
    assert before == after
