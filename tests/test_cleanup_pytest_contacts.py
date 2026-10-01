from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from io import StringIO
from typing import Any

import pytest

from scripts.cleanup_pytest_contacts import CONFIRMATION_PHRASE, run_cleanup


@dataclass
class Row:
    contact_id: int
    full_name: str
    is_deleted: bool = False


class FakeMappings:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def all(self) -> list[dict[str, Any]]:
        return self.rows

    def one(self) -> dict[str, Any]:
        assert len(self.rows) == 1
        return self.rows[0]


class FakeResult:
    def __init__(self, rows: list[dict[str, Any]] | None = None, scalar: int | None = None) -> None:
        self.rows = rows or []
        self.scalar = scalar

    def mappings(self) -> FakeMappings:
        return FakeMappings(self.rows)

    def scalar_one(self) -> int:
        assert self.scalar is not None
        return self.scalar


class FakeConnection:
    def __init__(self, engine: "FakeEngine") -> None:
        self.engine = engine

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> FakeResult:
        sql = str(statement)
        params = params or {}
        if "cleanup:identity" in sql:
            return FakeResult(
                [
                    {
                        "database_name": self.engine.database_name,
                        "server_address": self.engine.server_address,
                    }
                ]
            )
        if "cleanup:find" in sql:
            matches = [
                {"contact_id": row.contact_id, "full_name": row.full_name}
                for row in self.engine.rows
                if not row.is_deleted and row.full_name.startswith("Pytest")
            ]
            return FakeResult(matches)
        if "cleanup:soft-delete" in sql:
            ids = set(params["contact_ids"])
            deleted: list[dict[str, Any]] = []
            for row in self.engine.rows:
                if row.contact_id in ids and not row.is_deleted and row.full_name.startswith("Pytest"):
                    row.is_deleted = True
                    deleted.append({"contact_id": row.contact_id, "full_name": row.full_name})
                    if self.engine.fail_during_delete:
                        raise RuntimeError("synthetic delete failure")
            return FakeResult(deleted)
        if "cleanup:count" in sql:
            count = sum(
                not row.is_deleted and row.full_name.startswith("Pytest")
                for row in self.engine.rows
            )
            return FakeResult(scalar=count)
        if "cleanup:referencing-fks" in sql:
            return FakeResult([])
        raise AssertionError(f"Unexpected SQL: {sql}")


class FakeContext(AbstractContextManager[FakeConnection]):
    def __init__(self, engine: "FakeEngine", transactional: bool) -> None:
        self.engine = engine
        self.transactional = transactional
        self.snapshot: list[bool] = []

    def __enter__(self) -> FakeConnection:
        self.snapshot = [row.is_deleted for row in self.engine.rows]
        return FakeConnection(self.engine)

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        if self.transactional and exc_type is not None:
            for row, was_deleted in zip(self.engine.rows, self.snapshot):
                row.is_deleted = was_deleted
        return False


class FakeEngine:
    def __init__(
        self,
        rows: list[Row],
        *,
        fail_during_delete: bool = False,
        server_address: str | None = "127.0.0.1",
    ) -> None:
        self.rows = rows
        self.fail_during_delete = fail_during_delete
        self.database_name = "corpsite_test"
        self.server_address = server_address
        self.connection_attempts = 0

    def connect(self) -> FakeContext:
        self.connection_attempts += 1
        return FakeContext(self, transactional=False)

    def begin(self) -> FakeContext:
        self.connection_attempts += 1
        return FakeContext(self, transactional=True)


def names(engine: FakeEngine, *, deleted: bool) -> list[str]:
    return [row.full_name for row in engine.rows if row.is_deleted is deleted]


@pytest.fixture
def sample_engine() -> FakeEngine:
    return FakeEngine(
        [
            Row(1, "Pytest Contact"),
            Row(2, "Pytest"),
            Row(3, "Pytest123"),
            Row(4, "pytest Contact"),
            Row(5, "PYTEST Contact"),
            Row(6, "Test Pytest Contact"),
        ]
    )


@pytest.mark.parametrize(
    ("full_name", "is_found"),
    [
        ("Pytest Contact", True),
        ("Pytest", True),
        ("Pytest123", True),
        ("pytest Contact", False),
        ("PYTEST Contact", False),
        ("Test Pytest Contact", False),
    ],
)
def test_exact_case_sensitive_prefix_matching(full_name: str, is_found: bool) -> None:
    engine = FakeEngine([Row(1, full_name)])
    output = StringIO()

    result = run_cleanup(
        engine,
        "postgresql://user:secret@localhost/corpsite_test",
        apply=False,
        expected_database_name="corpsite_test",
        output=output,
    )

    assert result == 0
    assert (f"1\t{full_name}" in output.getvalue()) is is_found
    assert f"Найдено записей: {int(is_found)}" in output.getvalue()


def test_dry_run_deletes_nothing(sample_engine: FakeEngine) -> None:
    output = StringIO()

    result = run_cleanup(
        sample_engine,
        "postgresql://user:secret@localhost/corpsite_test",
        apply=False,
        expected_database_name="corpsite_test",
        output=output,
    )

    assert result == 0
    assert "DRY RUN — записи не удалены" in output.getvalue()
    assert names(sample_engine, deleted=True) == []


@pytest.mark.parametrize("confirmation", ["", "delete pytest contacts", "DELETE PYTEST CONTACT"])
def test_apply_without_exact_confirmation_deletes_nothing(
    sample_engine: FakeEngine, confirmation: str
) -> None:
    output = StringIO()

    result = run_cleanup(
        sample_engine,
        "postgresql://user:secret@127.0.0.1/corpsite_test",
        apply=True,
        expected_database_name="corpsite_test",
        input_fn=lambda _: confirmation,
        output=output,
    )

    assert result == 0
    assert names(sample_engine, deleted=True) == []
    assert "Операция отменена" in output.getvalue()


def test_confirmed_apply_soft_deletes_only_matches_and_recheck_is_zero(
    sample_engine: FakeEngine,
) -> None:
    output = StringIO()

    result = run_cleanup(
        sample_engine,
        "postgresql://user:secret@[::1]/corpsite_test",
        apply=True,
        expected_database_name="corpsite_test",
        input_fn=lambda _: CONFIRMATION_PHRASE,
        output=output,
    )

    assert result == 0
    assert names(sample_engine, deleted=True) == ["Pytest Contact", "Pytest", "Pytest123"]
    assert names(sample_engine, deleted=False) == [
        "pytest Contact",
        "PYTEST Contact",
        "Test Pytest Contact",
    ]
    assert "Удалено записей (soft delete): 3" in output.getvalue()
    assert "Осталось активных записей с префиксом 'Pytest': 0" in output.getvalue()


def test_delete_error_rolls_back_entire_transaction() -> None:
    engine = FakeEngine([Row(1, "Pytest One"), Row(2, "Pytest Two")], fail_during_delete=True)
    output = StringIO()

    result = run_cleanup(
        engine,
        "postgresql://user:secret@localhost/corpsite_test",
        apply=True,
        expected_database_name="corpsite_test",
        input_fn=lambda _: CONFIRMATION_PHRASE,
        output=output,
    )

    assert result == 1
    assert names(engine, deleted=True) == []
    assert "транзакция полностью отменена" in output.getvalue()


def test_apply_is_blocked_for_nonlocal_database(sample_engine: FakeEngine) -> None:
    output = StringIO()

    result = run_cleanup(
        sample_engine,
        "postgresql://user:secret@db.example.com/corpsite_test",
        apply=True,
        expected_database_name="corpsite_test",
        input_fn=lambda _: pytest.fail("confirmation must not be requested"),
        output=output,
    )

    assert result == 1
    assert names(sample_engine, deleted=True) == []
    assert sample_engine.connection_attempts == 0
    assert "не является локальным" in output.getvalue()
    assert "secret" not in output.getvalue()


def test_apply_is_blocked_when_postgres_server_address_is_not_loopback() -> None:
    engine = FakeEngine([Row(1, "Pytest Contact")], server_address="203.0.113.25")
    output = StringIO()

    result = run_cleanup(
        engine,
        "postgresql://user:secret@localhost/corpsite_test",
        apply=True,
        expected_database_name="corpsite_test",
        input_fn=lambda _: pytest.fail("confirmation must not be requested"),
        output=output,
    )

    assert result == 1
    assert names(engine, deleted=True) == []
    assert "server address" in output.getvalue()
    assert "secret" not in output.getvalue()


@pytest.mark.parametrize(
    ("configured_url", "expected_database_name", "message"),
    [
        ("postgresql://user:secret@db.example.com/corpsite_test", "corpsite_test", "не является локальным"),
        ("postgresql://user:secret@localhost/corpsite_prod_test", "corpsite_prod_test", "production-like"),
        ("postgresql://user:secret@localhost/corpsite", "corpsite", "явно test-БД"),
        ("postgresql://user:secret@localhost/corpsite_test", "other_test", "не совпадает"),
    ],
)
def test_preflight_rejects_unsafe_dry_run_without_connection(
    sample_engine: FakeEngine,
    configured_url: str,
    expected_database_name: str,
    message: str,
) -> None:
    output = StringIO()

    result = run_cleanup(
        sample_engine,
        configured_url,
        apply=False,
        expected_database_name=expected_database_name,
        output=output,
    )

    assert result == 1
    assert sample_engine.connection_attempts == 0
    assert message in output.getvalue()
    assert "secret" not in output.getvalue()
