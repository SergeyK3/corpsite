from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from types import SimpleNamespace

import pytest
from openpyxl import Workbook
from sqlalchemy import text

from app.db.engine import engine as database_engine
from app.operational_orders.archive_import import REQUIRED_COLUMNS
from app.operational_orders.archive_import.persistence import (
    ArchiveImportPersistenceError,
    PersistedArchiveImportBatch,
)
from scripts import import_operational_orders_archive_staging as cli


class _Transaction(AbstractContextManager):
    def __init__(self) -> None:
        self.connection = object()
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        self.committed = exc_type is None
        self.rolled_back = exc_type is not None
        return False


class _Engine:
    def __init__(self) -> None:
        self.transactions: list[_Transaction] = []

    def begin(self) -> _Transaction:
        transaction = _Transaction()
        self.transactions.append(transaction)
        return transaction


def _report(*, passed: bool = True):
    rows = tuple(
        SimpleNamespace(
            is_valid=passed,
            resolved_path=None,
            file_size_bytes=8,
            sha256="f" * 64,
            source=SimpleNamespace(excel_row=index + 2),
        )
        for index in range(2)
    )
    return SimpleNamespace(
        outcome="PASS" if passed else "FAIL",
        errors=() if passed else (SimpleNamespace(severity="ERROR"),),
        rows=rows,
        summary=SimpleNamespace(
            total_rows=2,
            valid_rows=2 if passed else 1,
            error_rows=0 if passed else 1,
        ),
    )


@pytest.fixture
def xlsx(tmp_path: Path) -> Path:
    path = tmp_path / "manifest.xlsx"
    path.write_bytes(b"manifest")
    return path


def _install_pass_dependencies(monkeypatch: pytest.MonkeyPatch):
    report = _report()
    fake_engine = _Engine()
    monkeypatch.setattr(cli, "run_dry_run", lambda **kwargs: report)
    monkeypatch.setattr(cli, "engine", fake_engine)
    monkeypatch.setattr(cli, "_assert_source_snapshot_unchanged", lambda **kwargs: None)
    return report, fake_engine


def test_successful_pass_import_uses_one_transaction_and_leaf_manifest_name(
    tmp_path: Path,
    xlsx: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report, fake_engine = _install_pass_dependencies(monkeypatch)
    captured: dict[str, object] = {}
    expected = PersistedArchiveImportBatch(17, "a" * 64, True, 2)

    def persist(**kwargs):
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(cli, "persist_archive_import_batch", persist)
    result = cli.run_staging_import(
        xlsx_path=xlsx.resolve(),
        archive_root=tmp_path.resolve(),
        actor_user_id=9,
        confirm_staging_import=True,
        expected_rows=2,
    )

    assert result.report is report
    assert result.persisted == expected
    assert captured["source_manifest_name"] == "manifest.xlsx"
    assert not Path(str(captured["source_manifest_name"])).is_absolute()
    assert captured["actor_user_id"] == 9
    assert captured["connection"] is fake_engine.transactions[0].connection
    assert fake_engine.transactions[0].committed is True
    assert fake_engine.transactions[0].rolled_back is False


def test_refuses_without_explicit_confirmation_after_dry_run(
    xlsx: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, fake_engine = _install_pass_dependencies(monkeypatch)
    persisted = False

    def persist(**kwargs):
        nonlocal persisted
        persisted = True

    monkeypatch.setattr(cli, "persist_archive_import_batch", persist)
    with pytest.raises(cli.StagingImportRefusedError, match=cli.CONFIRM_FLAG):
        cli.run_staging_import(
            xlsx_path=xlsx,
            archive_root=xlsx.parent,
            actor_user_id=9,
            confirm_staging_import=False,
            expected_rows=2,
        )

    assert persisted is False
    assert fake_engine.transactions == []


def test_refuses_dry_run_error_without_opening_transaction(
    xlsx: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_engine = _Engine()
    monkeypatch.setattr(cli, "run_dry_run", lambda **kwargs: _report(passed=False))
    monkeypatch.setattr(cli, "engine", fake_engine)

    with pytest.raises(cli.StagingImportRefusedError, match="not a row-clean PASS"):
        cli.run_staging_import(
            xlsx_path=xlsx,
            archive_root=xlsx.parent,
            actor_user_id=9,
            confirm_staging_import=True,
            expected_rows=2,
        )

    assert fake_engine.transactions == []


def test_persistence_error_rolls_back_transaction(
    xlsx: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, fake_engine = _install_pass_dependencies(monkeypatch)

    def fail(**kwargs):
        raise ArchiveImportPersistenceError("forced failure")

    monkeypatch.setattr(cli, "persist_archive_import_batch", fail)
    with pytest.raises(ArchiveImportPersistenceError, match="forced failure"):
        cli.run_staging_import(
            xlsx_path=xlsx,
            archive_root=xlsx.parent,
            actor_user_id=9,
            confirm_staging_import=True,
            expected_rows=2,
        )

    assert fake_engine.transactions[0].committed is False
    assert fake_engine.transactions[0].rolled_back is True


def test_repeat_returns_same_idempotent_batch_without_duplicate_rows(
    xlsx: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, fake_engine = _install_pass_dependencies(monkeypatch)
    results = iter(
        (
            PersistedArchiveImportBatch(17, "a" * 64, True, 2),
            PersistedArchiveImportBatch(17, "a" * 64, False, 2),
        )
    )
    monkeypatch.setattr(cli, "persist_archive_import_batch", lambda **kwargs: next(results))

    calls = [
        cli.run_staging_import(
            xlsx_path=xlsx,
            archive_root=xlsx.parent,
            actor_user_id=9,
            confirm_staging_import=True,
            expected_rows=2,
        ).persisted
        for _ in range(2)
    ]

    assert [result.batch_id for result in calls] == [17, 17]
    assert [result.created for result in calls] == [True, False]
    assert [result.row_count for result in calls] == [2, 2]
    assert all(transaction.committed for transaction in fake_engine.transactions)


def test_metadata_mismatch_is_not_accepted_as_idempotent_repeat(
    xlsx: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, fake_engine = _install_pass_dependencies(monkeypatch)
    outcomes = iter(
        (
            PersistedArchiveImportBatch(17, "a" * 64, True, 2),
            ArchiveImportPersistenceError("Existing batch fingerprint has different metadata"),
        )
    )

    def persist(**kwargs):
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(cli, "persist_archive_import_batch", persist)
    cli.run_staging_import(
        xlsx_path=xlsx,
        archive_root=xlsx.parent,
        actor_user_id=9,
        confirm_staging_import=True,
        expected_rows=2,
    )
    with pytest.raises(ArchiveImportPersistenceError, match="different metadata"):
        cli.run_staging_import(
            xlsx_path=xlsx,
            archive_root=xlsx.parent,
            actor_user_id=9,
            confirm_staging_import=True,
            expected_rows=2,
        )

    assert fake_engine.transactions[0].committed is True
    assert fake_engine.transactions[1].rolled_back is True


def test_snapshot_change_refuses_persistence_and_rolls_back(
    xlsx: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report, fake_engine = _install_pass_dependencies(monkeypatch)
    persisted = False

    def snapshot_changed(**kwargs):
        raise cli.StagingImportRefusedError("snapshot changed", report=report)

    def persist(**kwargs):
        nonlocal persisted
        persisted = True

    monkeypatch.setattr(cli, "_assert_source_snapshot_unchanged", snapshot_changed)
    monkeypatch.setattr(cli, "persist_archive_import_batch", persist)
    with pytest.raises(cli.StagingImportRefusedError, match="snapshot changed"):
        cli.run_staging_import(
            xlsx_path=xlsx,
            archive_root=xlsx.parent,
            actor_user_id=9,
            confirm_staging_import=True,
            expected_rows=2,
        )

    assert persisted is False
    assert fake_engine.transactions[0].rolled_back is True


def test_expected_rows_is_required_by_cli_parser() -> None:
    with pytest.raises(SystemExit):
        cli.parse_args(
            [
                "--xlsx",
                "manifest.xlsx",
                "--archive-root",
                "archive",
                "--actor-user-id",
                "9",
                cli.CONFIRM_FLAG,
            ]
        )


def test_cli_has_no_official_document_write_service_dependency() -> None:
    source = Path(cli.__file__).read_text(encoding="utf-8")
    forbidden = (
        "operational_order_documents",
        "operational_order_document_versions",
        "operational_order_draft_workspaces",
        "operational_order_attachments",
        "draft_intake_service",
        "promotion_service",
        "signing_service",
    )
    assert all(token not in source for token in forbidden)


def _database_available() -> bool:
    try:
        with database_engine.connect() as connection:
            return bool(
                connection.execute(
                    text(
                        """
                        SELECT to_regclass('public.operational_order_import_batches')
                               IS NOT NULL
                           AND to_regclass('public.operational_order_import_rows')
                               IS NOT NULL
                        """
                    )
                ).scalar_one()
            )
    except Exception:
        return False


@pytest.mark.skipif(not _database_available(), reason="Stage 2A PostgreSQL schema unavailable")
def test_database_import_is_idempotent_relative_only_and_officially_isolated(
    tmp_path: Path,
) -> None:
    archive_root = tmp_path / "archive"
    section = archive_root / "Раздел"
    section.mkdir(parents=True)
    document = section / "Приказ.docx"
    document.write_bytes(b"document")
    xlsx = tmp_path / "manifest.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Производственные приказы"
    worksheet.append(list(REQUIRED_COLUMNS))
    worksheet.append(
        [
            "1",
            document.name,
            "Приказ",
            "Найден",
            "Тестовый предмет",
            "001",
            "01.02.2026",
            "",
            "Производственные приказы",
            "Раздел",
            "Раздел\\Приказ.docx",
        ]
    )
    workbook.save(xlsx)
    workbook.close()

    with database_engine.connect() as connection:
        actor_user_id = int(
            connection.execute(text("SELECT user_id FROM users ORDER BY user_id LIMIT 1"))
            .scalars()
            .one()
        )
        official_before = tuple(
            int(
                connection.execute(
                    text(f"SELECT count(*) FROM public.{table_name}")
                ).scalar_one()
            )
            for table_name in (
                "operational_order_draft_workspaces",
                "operational_order_documents",
                "operational_order_document_versions",
            )
        )

    first = cli.run_staging_import(
        xlsx_path=xlsx,
        archive_root=archive_root,
        actor_user_id=actor_user_id,
        confirm_staging_import=True,
        expected_rows=1,
    ).persisted
    try:
        second = cli.run_staging_import(
            xlsx_path=xlsx,
            archive_root=archive_root,
            actor_user_id=actor_user_id,
            confirm_staging_import=True,
            expected_rows=1,
        ).persisted
        renamed_xlsx = tmp_path / "renamed.xlsx"
        renamed_xlsx.write_bytes(xlsx.read_bytes())
        with pytest.raises(ArchiveImportPersistenceError, match="different metadata"):
            cli.run_staging_import(
                xlsx_path=renamed_xlsx,
                archive_root=archive_root,
                actor_user_id=actor_user_id,
                confirm_staging_import=True,
                expected_rows=1,
            )

        with database_engine.connect() as connection:
            batch = connection.execute(
                text(
                    """
                    SELECT source_manifest_name, source_root_name
                    FROM operational_order_import_batches
                    WHERE id = :batch_id
                    """
                ),
                {"batch_id": first.batch_id},
            ).mappings().one()
            row = connection.execute(
                text(
                    """
                    SELECT relative_path, official_document_id
                    FROM operational_order_import_rows
                    WHERE batch_id = :batch_id
                    """
                ),
                {"batch_id": first.batch_id},
            ).mappings().one()
            official_after = tuple(
                int(
                    connection.execute(
                        text(f"SELECT count(*) FROM public.{table_name}")
                    ).scalar_one()
                )
                for table_name in (
                    "operational_order_draft_workspaces",
                    "operational_order_documents",
                    "operational_order_document_versions",
                )
            )

        assert first.created is True
        assert second.created is False
        assert second.batch_id == first.batch_id
        assert dict(batch) == {
            "source_manifest_name": "manifest.xlsx",
            "source_root_name": "archive",
        }
        assert row["relative_path"] == "Раздел\\Приказ.docx"
        assert not Path(row["relative_path"]).is_absolute()
        assert row["official_document_id"] is None
        assert official_after == official_before
    finally:
        with database_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM operational_order_import_batches WHERE id = :batch_id"),
                {"batch_id": first.batch_id},
            )
