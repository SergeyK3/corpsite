# tests/personnel_intake/test_person_telegram_bot_activations_orm.py
"""ORM/schema parity tests for person_telegram_bot_activations."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.person_telegram import PersonTelegramBotActivation
from tests.conftest import get_columns, table_exists
from tests.ppr.conftest import ppr_db_available

TABLE_NAME = "person_telegram_bot_activations"

EXPECTED_COLUMNS = {
    "activation_id",
    "person_id",
    "bot_code",
    "first_activated_at",
    "last_activated_at",
}

UNIQUE_CONSTRAINT = "uq_person_telegram_bot_activations_person_bot"
CHECK_CONSTRAINT = "chk_person_telegram_bot_activations_bot_code"


@pytest.fixture
def db_ready():
    if not ppr_db_available():
        pytest.skip("PostgreSQL not available")


def test_orm_model_maps_to_expected_table_and_columns() -> None:
    assert PersonTelegramBotActivation.__tablename__ == TABLE_NAME
    orm_columns = {column.name for column in PersonTelegramBotActivation.__table__.columns}
    assert orm_columns == EXPECTED_COLUMNS


def test_orm_person_id_foreign_key_points_to_persons() -> None:
    person_id_column = PersonTelegramBotActivation.__table__.c.person_id
    foreign_keys = list(person_id_column.foreign_keys)
    assert len(foreign_keys) == 1
    fk = foreign_keys[0]
    assert str(fk.target_fullname) == "public.persons.person_id"
    assert fk.ondelete == "RESTRICT"


def test_orm_declares_unique_and_check_constraints() -> None:
    table = PersonTelegramBotActivation.__table__
    constraint_names = {constraint.name for constraint in table.constraints if constraint.name}
    assert UNIQUE_CONSTRAINT in constraint_names
    assert CHECK_CONSTRAINT in constraint_names


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

        constraint_rows = conn.execute(
            text(
                """
                SELECT conname
                FROM pg_constraint
                WHERE conname IN (:unique_name, :check_name)
                """
            ),
            {"unique_name": UNIQUE_CONSTRAINT, "check_name": CHECK_CONSTRAINT},
        ).scalars().all()
        assert set(constraint_rows) == {UNIQUE_CONSTRAINT, CHECK_CONSTRAINT}
