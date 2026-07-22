# tests/personnel_intake/test_person_telegram_bindings_orm.py
"""ORM/schema parity tests for person_telegram_bindings."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.person_telegram import PersonTelegramBinding
from tests.conftest import get_columns, table_exists
from tests.ppr.conftest import ppr_db_available

TABLE_NAME = "person_telegram_bindings"

EXPECTED_COLUMNS = {
    "binding_id",
    "person_id",
    "telegram_user_id",
    "telegram_username",
    "revoked_at",
    "created_at",
    "updated_at",
}

EXPECTED_INDEXES = (
    "uq_person_telegram_bindings_telegram_user_id_active",
    "uq_person_telegram_bindings_person_id_active",
    "ix_person_telegram_bindings_person_id_history",
)

CHECK_CONSTRAINT = "chk_person_telegram_bindings_telegram_user_id_positive"


@pytest.fixture
def db_ready():
    if not ppr_db_available():
        pytest.skip("PostgreSQL not available")


def test_orm_model_maps_to_expected_table_and_columns() -> None:
    assert PersonTelegramBinding.__tablename__ == TABLE_NAME
    orm_columns = {column.name for column in PersonTelegramBinding.__table__.columns}
    assert orm_columns == EXPECTED_COLUMNS


def test_orm_person_id_foreign_key_points_to_persons() -> None:
    person_id_column = PersonTelegramBinding.__table__.c.person_id
    foreign_keys = list(person_id_column.foreign_keys)
    assert len(foreign_keys) == 1
    fk = foreign_keys[0]
    assert str(fk.target_fullname) == "public.persons.person_id"
    assert fk.ondelete == "RESTRICT"


def test_orm_declares_check_and_indexes() -> None:
    table = PersonTelegramBinding.__table__
    check_names = {constraint.name for constraint in table.constraints if constraint.name}
    assert CHECK_CONSTRAINT in check_names

    index_names = {index.name for index in table.indexes}
    assert set(EXPECTED_INDEXES).issubset(index_names)

    telegram_active = next(
        index
        for index in table.indexes
        if index.name == "uq_person_telegram_bindings_telegram_user_id_active"
    )
    assert telegram_active.unique is True
    assert "revoked_at IS NULL" in str(telegram_active.kwargs["postgresql_where"])

    person_active = next(
        index
        for index in table.indexes
        if index.name == "uq_person_telegram_bindings_person_id_active"
    )
    assert person_active.unique is True
    assert "revoked_at IS NULL" in str(person_active.kwargs["postgresql_where"])

    history = next(
        index
        for index in table.indexes
        if index.name == "ix_person_telegram_bindings_person_id_history"
    )
    assert history.kwargs["postgresql_ops"] == {"created_at": "DESC"}


def test_database_schema_matches_orm_model(db_ready) -> None:
    with engine.connect() as conn:
        if not table_exists(conn, TABLE_NAME):
            pytest.skip(f"{TABLE_NAME} missing — run: alembic upgrade head")
        db_columns = get_columns(conn, TABLE_NAME)
        assert db_columns == EXPECTED_COLUMNS

        fk_rows = conn.execute(
            text(
                """
                SELECT ccu.table_name AS referenced_table
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON kcu.constraint_name = tc.constraint_name
                 AND kcu.constraint_schema = tc.constraint_schema
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name
                 AND ccu.constraint_schema = tc.constraint_schema
                WHERE tc.table_schema = 'public'
                  AND tc.table_name = :table_name
                  AND tc.constraint_type = 'FOREIGN KEY'
                  AND kcu.column_name = 'person_id'
                """
            ),
            {"table_name": TABLE_NAME},
        ).mappings().all()
        assert {row["referenced_table"] for row in fk_rows} == {"persons"}

        check_row = conn.execute(
            text(
                """
                SELECT 1
                FROM pg_constraint
                WHERE conname = :constraint_name
                """
            ),
            {"constraint_name": CHECK_CONSTRAINT},
        ).scalar_one_or_none()
        assert check_row == 1

        index_rows = conn.execute(
            text(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = :table_name
                """
            ),
            {"table_name": TABLE_NAME},
        ).mappings().all()
        index_by_name = {row["indexname"]: str(row["indexdef"]).lower() for row in index_rows}

    for expected_index in EXPECTED_INDEXES:
        assert expected_index in index_by_name

    assert "unique" in index_by_name["uq_person_telegram_bindings_telegram_user_id_active"]
    assert "where (revoked_at is null)" in index_by_name[
        "uq_person_telegram_bindings_telegram_user_id_active"
    ]
    assert "unique" in index_by_name["uq_person_telegram_bindings_person_id_active"]
    assert "where (revoked_at is null)" in index_by_name[
        "uq_person_telegram_bindings_person_id_active"
    ]
    assert "created_at desc" in index_by_name["ix_person_telegram_bindings_person_id_history"]
