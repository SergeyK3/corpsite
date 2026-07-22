# tests/personnel_intake/test_telegram_binding_repository.py
"""Repository tests for Person-level Telegram identity."""
from __future__ import annotations

import time
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.person_telegram import BOT_CODE_INTAKE_PPR, BOT_CODE_OPERATIONAL_TASKS
from app.personnel_intake.domain.errors import PersonnelIntakeConflictError
from app.personnel_intake.infrastructure.telegram_binding_repository import (
    SqlAlchemyPersonTelegramRepository,
)
from tests.conftest import table_exists
from tests.ppr.conftest import insert_person, ppr_db_available


def _unique_telegram_user_id() -> int:
    return 1_000_000_000 + (uuid4().int % 899_999_999)


@pytest.fixture
def db_ready():
    if not ppr_db_available():
        pytest.skip("PostgreSQL not available")
    with engine.begin() as conn:
        if not table_exists(conn, "person_telegram_bindings"):
            pytest.skip("person_telegram_bindings missing — run: alembic upgrade head")
        if not table_exists(conn, "person_telegram_bot_activations"):
            pytest.skip("person_telegram_bot_activations missing — run: alembic upgrade head")


@pytest.fixture
def repo(db_ready):
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name="Telegram Binding Person", prefix="person-tg")
        yield conn, SqlAlchemyPersonTelegramRepository(conn), person_id
        conn.execute(
            text(
                """
                DELETE FROM public.person_telegram_bot_activations
                WHERE person_id = :person_id
                """
            ),
            {"person_id": person_id},
        )
        conn.execute(
            text(
                """
                DELETE FROM public.person_telegram_bindings
                WHERE person_id = :person_id
                """
            ),
            {"person_id": person_id},
        )
        conn.execute(
            text("DELETE FROM public.persons WHERE person_id = :person_id"),
            {"person_id": person_id},
        )


def test_create_binding_success(repo) -> None:
    conn, repository, person_id = repo
    telegram_user_id = _unique_telegram_user_id()

    created = repository.create_binding(
        person_id,
        telegram_user_id,
        "intake_test_user",
    )

    assert created.binding_id > 0
    assert created.person_id == person_id
    assert created.telegram_user_id == telegram_user_id
    assert created.telegram_username == "intake_test_user"
    assert created.revoked_at is None

    row = conn.execute(
        text(
            """
            SELECT COUNT(*) AS cnt
            FROM public.person_telegram_bindings
            WHERE binding_id = :binding_id
            """
        ),
        {"binding_id": created.binding_id},
    ).scalar_one()
    assert int(row) == 1


def test_get_active_by_person_id(repo) -> None:
    _, repository, person_id = repo
    telegram_user_id = _unique_telegram_user_id()
    created = repository.create_binding(person_id, telegram_user_id, None)

    found = repository.get_active_by_person_id(person_id)

    assert found is not None
    assert found.binding_id == created.binding_id
    assert found.telegram_user_id == telegram_user_id


def test_get_active_by_telegram_user_id(repo) -> None:
    _, repository, person_id = repo
    telegram_user_id = _unique_telegram_user_id()
    created = repository.create_binding(person_id, telegram_user_id, "lookup_user")

    found = repository.get_active_by_telegram_user_id(telegram_user_id)

    assert found is not None
    assert found.binding_id == created.binding_id
    assert found.person_id == person_id
    assert found.telegram_username == "lookup_user"


def test_create_second_active_binding_for_same_person_is_rejected(repo) -> None:
    _, repository, person_id = repo
    repository.create_binding(person_id, _unique_telegram_user_id(), None)

    with pytest.raises(PersonnelIntakeConflictError, match="person"):
        repository.create_binding(person_id, _unique_telegram_user_id(), None)


def test_create_second_active_binding_for_same_telegram_user_is_rejected(db_ready) -> None:
    telegram_user_id = _unique_telegram_user_id()
    with engine.begin() as conn:
        person_a = insert_person(conn, full_name="Telegram Person A", prefix="person-tg-a")
        person_b = insert_person(conn, full_name="Telegram Person B", prefix="person-tg-b")
        repository = SqlAlchemyPersonTelegramRepository(conn)
        repository.create_binding(person_a, telegram_user_id, None)

        with pytest.raises(PersonnelIntakeConflictError, match="Telegram user"):
            repository.create_binding(person_b, telegram_user_id, None)

        conn.execute(
            text(
                """
                DELETE FROM public.person_telegram_bindings
                WHERE telegram_user_id = :telegram_user_id
                """
            ),
            {"telegram_user_id": telegram_user_id},
        )
        conn.execute(
            text("DELETE FROM public.persons WHERE person_id IN (:person_a, :person_b)"),
            {"person_a": person_a, "person_b": person_b},
        )


def test_after_revoke_can_create_new_active_binding(repo) -> None:
    conn, repository, person_id = repo
    first_telegram_user_id = _unique_telegram_user_id()
    first = repository.create_binding(person_id, first_telegram_user_id, "first_user")

    revoked = repository.revoke_binding(first.binding_id)
    assert revoked.revoked_at is not None
    assert revoked.updated_at == revoked.revoked_at
    assert repository.get_active_by_person_id(person_id) is None
    assert repository.get_active_by_telegram_user_id(first_telegram_user_id) is None

    second_telegram_user_id = _unique_telegram_user_id()
    second = repository.create_binding(person_id, second_telegram_user_id, "second_user")

    assert second.binding_id != first.binding_id
    assert second.revoked_at is None
    assert repository.get_active_by_person_id(person_id) is not None

    history_count = conn.execute(
        text(
            """
            SELECT COUNT(*) AS cnt
            FROM public.person_telegram_bindings
            WHERE person_id = :person_id
            """
        ),
        {"person_id": person_id},
    ).scalar_one()
    assert int(history_count) == 2


def test_upsert_activation_creates_first_record(repo) -> None:
    _, repository, person_id = repo

    activation = repository.upsert_activation(person_id, BOT_CODE_INTAKE_PPR)

    assert activation.activation_id > 0
    assert activation.person_id == person_id
    assert activation.bot_code == BOT_CODE_INTAKE_PPR
    assert activation.first_activated_at == activation.last_activated_at


def test_upsert_activation_updates_only_last_activated_at(repo) -> None:
    _, repository, person_id = repo

    first = repository.upsert_activation(person_id, BOT_CODE_OPERATIONAL_TASKS)
    time.sleep(0.01)
    second = repository.upsert_activation(person_id, BOT_CODE_OPERATIONAL_TASKS)

    assert second.activation_id == first.activation_id
    assert second.first_activated_at == first.first_activated_at
    assert second.last_activated_at >= first.last_activated_at


def test_upsert_activation_allows_distinct_bot_codes(repo) -> None:
    _, repository, person_id = repo

    intake = repository.upsert_activation(person_id, BOT_CODE_INTAKE_PPR)
    operational = repository.upsert_activation(person_id, BOT_CODE_OPERATIONAL_TASKS)

    assert intake.activation_id != operational.activation_id
    assert intake.bot_code == BOT_CODE_INTAKE_PPR
    assert operational.bot_code == BOT_CODE_OPERATIONAL_TASKS


def test_upsert_activation_rejects_unknown_bot_code(repo) -> None:
    _, repository, person_id = repo

    with pytest.raises(ValueError, match="Unsupported bot_code"):
        repository.upsert_activation(person_id, "unknown_bot")
