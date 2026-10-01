from __future__ import annotations

import sys
from pathlib import Path

import pytest

from scripts import cleanup_local_test_databases as cleanup


class FakeCursor:
    def __init__(self, events: list[object]) -> None:
        self.events = events

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False

    def execute(self, statement, params=None) -> None:
        self.events.append((str(statement), params))


class FakeMaintenanceConnection:
    def __init__(self, events: list[object]) -> None:
        self.events = events
        self.autocommit = False
        self.closed = False

    def cursor(self) -> FakeCursor:
        return FakeCursor(self.events)

    def close(self) -> None:
        self.closed = True


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://user@127.0.0.1:5432/corpsite_test",
        "postgresql+psycopg2://user@localhost/corpsite_test",
    ],
)
def test_validated_url_accepts_loopback_postgres(url: str) -> None:
    assert cleanup._validated_url(url).database == "corpsite_test"


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://user@db.example/corpsite_test",
        "sqlite:///corpsite_test.sqlite",
        "postgresql://user@localhost/",
    ],
)
def test_validated_url_rejects_remote_non_postgres_and_missing_database(url: str) -> None:
    with pytest.raises(cleanup.SafetyError):
        cleanup._validated_url(url)


@pytest.mark.parametrize("name", ["corpsite", "postgres", "template0", "template1"])
def test_validate_targets_rejects_protected_databases(name: str) -> None:
    with pytest.raises(cleanup.SafetyError, match="Protected"):
        cleanup._validate_targets([name])


@pytest.mark.parametrize("name", ["corpsite_*", "corpsite?test", "not_a_test_database"])
def test_validate_targets_rejects_wildcards_and_non_test_names(name: str) -> None:
    with pytest.raises(cleanup.SafetyError):
        cleanup._validate_targets([name])


def test_validate_targets_accepts_exact_test_database() -> None:
    assert cleanup._validate_targets(["corpsite_test"]) == ["corpsite_test"]


def _argv(*extra: str) -> list[str]:
    return [
        "cleanup_local_test_databases.py",
        "--database",
        "corpsite_test",
        "--database-url",
        "postgresql://user@127.0.0.1:5432/corpsite_test",
        *extra,
    ]


def test_dry_run_is_non_mutating(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    events: list[object] = []
    connection = FakeMaintenanceConnection(events)
    monkeypatch.setattr(cleanup, "_connect", lambda url, database: connection)
    monkeypatch.setattr(cleanup, "_listed_databases", lambda conn: {"corpsite_test"})
    monkeypatch.setattr(sys, "argv", _argv())

    assert cleanup.main() == 0
    assert connection.autocommit is True
    assert connection.closed is True
    assert events == []
    assert '"mode": "dry-run"' in capsys.readouterr().out


def test_execute_requires_exact_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeMaintenanceConnection([])
    monkeypatch.setattr(cleanup, "_connect", lambda url, database: connection)
    monkeypatch.setattr(cleanup, "_listed_databases", lambda conn: {"corpsite_test"})
    monkeypatch.setattr(sys, "argv", _argv("--execute", "--confirm", "wrong"))

    with pytest.raises(cleanup.SafetyError, match="confirm"):
        cleanup.main()
    assert connection.closed is True


def test_execute_requires_backup_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeMaintenanceConnection([])
    monkeypatch.setattr(cleanup, "_connect", lambda url, database: connection)
    monkeypatch.setattr(cleanup, "_listed_databases", lambda conn: {"corpsite_test"})
    monkeypatch.setattr(
        sys,
        "argv",
        _argv("--execute", "--confirm", cleanup.CONFIRMATION),
    )

    with pytest.raises(cleanup.SafetyError, match="backup-dir"):
        cleanup.main()
    assert connection.closed is True


def test_confirmed_execute_backs_up_before_drop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[object] = []
    connection = FakeMaintenanceConnection(events)
    order: list[str] = []
    monkeypatch.setattr(cleanup, "_connect", lambda url, database: connection)
    monkeypatch.setattr(cleanup, "_listed_databases", lambda conn: {"corpsite_test"})
    monkeypatch.setattr(
        cleanup,
        "_backup_all",
        lambda args, url, targets, backup_dir: order.append("backup") or [
            {"database": "corpsite_test", "backup": str(backup_dir / "corpsite_test.dump"), "bytes": 1}
        ],
    )
    monkeypatch.setattr(cleanup, "_outside_repository", lambda path: None)
    monkeypatch.setattr(cleanup, "_write_json", lambda path, value: None)
    monkeypatch.setattr(
        sys,
        "argv",
        _argv(
            "--execute",
            "--confirm",
            cleanup.CONFIRMATION,
            "--backup-dir",
            str(Path.cwd()),
        ),
    )

    assert cleanup.main() == 0
    assert order == ["backup"]
    assert any("DROP DATABASE" in statement for statement, _ in events)
    assert connection.closed is True
