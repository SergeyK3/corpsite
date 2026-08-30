from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import Barrier
from typing import Iterator

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from openpyxl import Workbook
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.db.engine import engine
from app.db.models.operational_order_archive_import import (
    OperationalOrderImportBatch,
    OperationalOrderImportRow,
)
from app.operational_orders.archive_import import REQUIRED_COLUMNS, run_dry_run
from app.operational_orders.archive_import.models import DryRunReport, ValidationIssue
from app.operational_orders.archive_import.persistence import (
    ARCHIVE_IMPORT_FORMAT_VERSION,
    ArchiveImportPersistenceError,
    PersistedArchiveImportBatch,
    calculate_batch_fingerprint,
    persist_archive_import_batch,
)
from tests.alembic_test_helpers import (
    alembic_config,
    exclusive_migration_cycle,
    get_alembic_heads,
)
from tests.conftest import table_exists


MIGRATION_REVISION = "u4v5w6x7y8z"
PREVIOUS_REVISION = "t3u4v5w6x7y"
MIGRATION_FILE = "u4v5w6x7y8z_wp_po_002_stage_2a_archive_import_staging.py"
INITIAL_STATE_BY_STATUS = {
    "Найден": "REQUISITES_PRECONFIRMED",
    "Не найден": "NEEDS_REQUISITES",
    "Требует проверки": "NEEDS_DOCUMENT_TYPE",
    "Не является приказом": "POSSIBLE_NON_ORDER",
}


def _db_available() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _schema_available() -> bool:
    if not _db_available():
        return False
    with engine.connect() as connection:
        found = set(
            connection.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name IN (
                          'operational_order_import_batches',
                          'operational_order_import_rows'
                      )
                    """
                )
            ).scalars()
        )
    return found == {
        "operational_order_import_batches",
        "operational_order_import_rows",
    }


def _require_schema() -> None:
    if not _schema_available():
        pytest.skip(f"Stage 2A schema missing — run: alembic upgrade {MIGRATION_REVISION}")


@pytest.fixture
def pass_report(tmp_path: Path) -> tuple[DryRunReport, Path, str]:
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    statuses = tuple(INITIAL_STATE_BY_STATUS)
    rows: list[dict[str, object]] = []
    for index, status in enumerate(statuses, start=1):
        filename = f"Приказ-{index}.docx"
        relative_path = f"[Раздел {index}]\\{filename}"
        file_path = archive_root / f"[Раздел {index}]" / filename
        file_path.parent.mkdir(parents=True)
        file_path.write_bytes(f"document-{index}".encode())
        rows.append(
            {
                "№ п/п": str(index),
                "Имя файла (Word/PDF)": filename,
                "Тип документа": "Приказ",
                "Статус": status,
                "Тип события / предмет приказа": f"Событие {index}",
                "Номер приказа": "001-A" if index == 1 else "",
                "Дата приказа": "01.02.2026" if index == 1 else "",
                "Примечание": f"Примечание {index}",
                "Исходная папка": "Производственные приказы",
                "Раздел архива": f"[Раздел {index}]",
                "Относительный путь к файлу": relative_path,
            }
        )

    xlsx = tmp_path / "manifest.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Производственные приказы"
    worksheet.append(list(REQUIRED_COLUMNS))
    for row in rows:
        worksheet.append([row[column] for column in REQUIRED_COLUMNS])
    workbook.save(xlsx)
    workbook.close()

    report = run_dry_run(
        xlsx_path=xlsx,
        archive_root=archive_root,
        expected_rows=len(rows),
    )
    assert report.outcome == "PASS"
    manifest_sha256 = hashlib.sha256(xlsx.read_bytes()).hexdigest()
    return report, xlsx, manifest_sha256


@pytest.fixture
def archive_actor_user_id() -> int:
    with engine.connect() as connection:
        actor_user_id = connection.execute(
            text("SELECT user_id FROM public.users ORDER BY user_id LIMIT 1")
        ).scalar_one_or_none()
    if actor_user_id is None:
        pytest.skip("Stage 2A PostgreSQL tests require one existing user in the disposable DB")
    return int(actor_user_id)


@contextmanager
def _persisted_batch(
    report: DryRunReport,
    xlsx: Path,
    manifest_sha256: str,
    actor_user_id: int,
) -> Iterator[PersistedArchiveImportBatch]:
    result = persist_archive_import_batch(
        report=report,
        source_manifest_name=xlsx.name,
        source_manifest_sha256=manifest_sha256,
        actor_user_id=actor_user_id,
    )
    try:
        yield result
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM public.operational_order_import_batches WHERE id = :batch_id"),
                {"batch_id": result.batch_id},
            )


def _official_counts(connection) -> tuple[int, int, int]:
    return tuple(
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


def _migration_module():
    path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / MIGRATION_FILE
    spec = spec_from_file_location("wp_po_002_stage_2a_migration", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load migration from {path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_models_are_registered_with_required_constraints() -> None:
    assert OperationalOrderImportBatch.__tablename__ == "operational_order_import_batches"
    assert OperationalOrderImportRow.__tablename__ == "operational_order_import_rows"
    batch_constraints = {constraint.name for constraint in OperationalOrderImportBatch.__table__.constraints}
    row_constraints = {constraint.name for constraint in OperationalOrderImportRow.__table__.constraints}
    assert "uq_oo_import_batches_fingerprint" in batch_constraints
    assert "uq_oo_import_rows_batch_source_row" in row_constraints
    assert "uq_oo_import_rows_batch_relative_path" in row_constraints
    assert {index.name for index in OperationalOrderImportRow.__table__.indexes} >= {
        "ix_oo_import_rows_file_sha256"
    }


def test_fingerprint_is_deterministic_and_row_order_independent(pass_report) -> None:
    report, _, manifest_sha256 = pass_report
    reordered = replace(report, rows=tuple(reversed(report.rows)))

    first = calculate_batch_fingerprint(
        report,
        source_manifest_sha256=manifest_sha256,
    )
    second = calculate_batch_fingerprint(
        reordered,
        source_manifest_sha256=manifest_sha256,
    )

    assert first == second
    assert len(first) == 64


def test_rejects_invalid_hashes_empty_paths_negative_sizes_and_summary_drift(pass_report) -> None:
    report, xlsx, manifest_sha256 = pass_report
    invalid_reports = (
        replace(
            report,
            rows=(replace(report.rows[0], file_size_bytes=-1), *report.rows[1:]),
        ),
        replace(
            report,
            rows=(
                replace(
                    report.rows[0],
                    source=replace(report.rows[0].source, relative_path="   "),
                ),
                *report.rows[1:],
            ),
        ),
        replace(report, summary=replace(report.summary, existing_files=3)),
    )

    for invalid_report in invalid_reports:
        with pytest.raises(ArchiveImportPersistenceError):
            persist_archive_import_batch(
                report=invalid_report,
                source_manifest_name=xlsx.name,
                source_manifest_sha256=manifest_sha256,
                actor_user_id=1,
            )
    with pytest.raises(ArchiveImportPersistenceError, match="SHA-256"):
        calculate_batch_fingerprint(report, source_manifest_sha256="not-a-sha256")
    with pytest.raises(ArchiveImportPersistenceError, match="SHA-256"):
        persist_archive_import_batch(
            report=replace(
                report,
                rows=(replace(report.rows[0], sha256="bad"), *report.rows[1:]),
            ),
            source_manifest_name=xlsx.name,
            source_manifest_sha256=manifest_sha256,
            actor_user_id=1,
        )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_persists_exact_batch_rows_states_and_no_official_records(
    pass_report, archive_actor_user_id
) -> None:
    _require_schema()
    report, xlsx, manifest_sha256 = pass_report
    actor_user_id = archive_actor_user_id
    with engine.connect() as connection:
        official_before = _official_counts(connection)

    with _persisted_batch(report, xlsx, manifest_sha256, actor_user_id) as result:
        assert result.created is True
        assert result.row_count == 4
        with engine.connect() as connection:
            batch = connection.execute(
                text("SELECT * FROM public.operational_order_import_batches WHERE id = :id"),
                {"id": result.batch_id},
            ).mappings().one()
            rows = connection.execute(
                text(
                    """
                    SELECT * FROM public.operational_order_import_rows
                    WHERE batch_id = :batch_id
                    ORDER BY source_row_number
                    """
                ),
                {"batch_id": result.batch_id},
            ).mappings().all()
            official_after = _official_counts(connection)

        assert batch["source_manifest_name"] == xlsx.name
        assert batch["source_manifest_sha256"] == manifest_sha256
        assert batch["format_version"] == ARCHIVE_IMPORT_FORMAT_VERSION
        assert batch["source_root_name"] == "archive"
        assert str(xlsx.parent) not in batch["source_root_name"]
        assert batch["status"] == "IMPORTED"
        assert (batch["total_rows"], batch["valid_rows"], batch["error_rows"]) == (4, 4, 0)
        assert batch["file_count"] == 4
        assert batch["archive_section_count"] == 4
        assert batch["created_by_user_id"] == actor_user_id
        assert batch["completed_at"] is None
        assert len(rows) == 4
        assert {row["source_status"]: row["initial_review_state"] for row in rows} == (
            INITIAL_STATE_BY_STATUS
        )
        assert rows[0]["source_order_number"] == "001-A"
        assert rows[0]["source_order_date"].isoformat() == "2026-02-01"
        assert all(row["confirmed_document_type"] is None for row in rows)
        assert all(row["official_document_id"] is None for row in rows)
        assert all(row["version"] == 1 for row in rows)
        assert official_after == official_before


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_rejects_fail_and_inconsistent_pass_without_writes(
    pass_report, archive_actor_user_id
) -> None:
    _require_schema()
    report, xlsx, manifest_sha256 = pass_report
    actor_user_id = archive_actor_user_id
    failure = ValidationIssue(code="TEST", severity="ERROR", message="test")
    fail_report = replace(report, errors=(failure,))
    inconsistent_pass = replace(
        report,
        summary=replace(report.summary, valid_rows=3, error_rows=1),
    )
    with engine.connect() as connection:
        before = int(
            connection.execute(
                text("SELECT count(*) FROM public.operational_order_import_batches")
            ).scalar_one()
        )

    for rejected in (fail_report, inconsistent_pass):
        with pytest.raises(ArchiveImportPersistenceError):
            persist_archive_import_batch(
                report=rejected,
                source_manifest_name=xlsx.name,
                source_manifest_sha256=manifest_sha256,
                actor_user_id=actor_user_id,
            )

    with engine.connect() as connection:
        after = int(
            connection.execute(
                text("SELECT count(*) FROM public.operational_order_import_batches")
            ).scalar_one()
        )
    assert after == before


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_idempotent_repeat_returns_existing_batch(pass_report, archive_actor_user_id) -> None:
    _require_schema()
    report, xlsx, manifest_sha256 = pass_report
    actor_user_id = archive_actor_user_id
    with _persisted_batch(report, xlsx, manifest_sha256, actor_user_id) as first:
        second = persist_archive_import_batch(
            report=report,
            source_manifest_name=xlsx.name,
            source_manifest_sha256=manifest_sha256,
            actor_user_id=actor_user_id,
        )
        assert second.created is False
        assert second.batch_id == first.batch_id
        with engine.connect() as connection:
            batch_count = connection.execute(
                text(
                    """
                    SELECT count(*) FROM public.operational_order_import_batches
                    WHERE batch_fingerprint = :fingerprint
                    """
                ),
                {"fingerprint": first.batch_fingerprint},
            ).scalar_one()
            row_count = connection.execute(
                text(
                    "SELECT count(*) FROM public.operational_order_import_rows WHERE batch_id = :id"
                ),
                {"id": first.batch_id},
            ).scalar_one()
        assert batch_count == 1
        assert row_count == 4


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_idempotent_repeat_rejects_different_metadata(
    pass_report, archive_actor_user_id
) -> None:
    _require_schema()
    report, xlsx, manifest_sha256 = pass_report
    actor_user_id = archive_actor_user_id
    with _persisted_batch(report, xlsx, manifest_sha256, actor_user_id):
        with pytest.raises(ArchiveImportPersistenceError, match="different metadata"):
            persist_archive_import_batch(
                report=report,
                source_manifest_name="renamed-manifest.xlsx",
                source_manifest_sha256=manifest_sha256,
                actor_user_id=actor_user_id,
            )
        changed_source = replace(report.rows[0].source, document_type="Распоряжение")
        changed_report = replace(
            report,
            rows=(replace(report.rows[0], source=changed_source), *report.rows[1:]),
        )
        with pytest.raises(ArchiveImportPersistenceError, match="row metadata"):
            persist_archive_import_batch(
                report=changed_report,
                source_manifest_name=xlsx.name,
                source_manifest_sha256=manifest_sha256,
                actor_user_id=actor_user_id,
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_parallel_repeat_creates_one_batch(pass_report, archive_actor_user_id) -> None:
    _require_schema()
    report, xlsx, manifest_sha256 = pass_report
    actor_user_id = archive_actor_user_id

    ready = Barrier(2)

    def persist_once():
        with engine.connect() as connection:
            transaction = connection.begin()
            backend_pid = int(connection.execute(text("SELECT pg_backend_pid()" )).scalar_one())
            ready.wait(timeout=10)
            result = persist_archive_import_batch(
                report=report,
                source_manifest_name=xlsx.name,
                source_manifest_sha256=manifest_sha256,
                actor_user_id=actor_user_id,
                connection=connection,
            )
            transaction.commit()
            return backend_pid, result

    with ThreadPoolExecutor(max_workers=2) as executor:
        attempts = list(executor.map(lambda _: persist_once(), range(2)))
    results = [result for _, result in attempts]
    try:
        assert len({backend_pid for backend_pid, _ in attempts}) == 2
        assert len({result.batch_id for result in results}) == 1
        assert sorted(result.created for result in results) == [False, True]
        batch_id = results[0].batch_id
        with engine.connect() as connection:
            assert connection.execute(
                text(
                    "SELECT count(*) FROM public.operational_order_import_rows WHERE batch_id = :id"
                ),
                {"id": batch_id},
            ).scalar_one() == 4
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM public.operational_order_import_batches WHERE id = :id"),
                {"id": results[0].batch_id},
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
@pytest.mark.parametrize("duplicate", ["source_row_number", "relative_path"])
def test_database_blocks_duplicate_row_identity(
    pass_report, archive_actor_user_id, duplicate: str
) -> None:
    _require_schema()
    report, xlsx, manifest_sha256 = pass_report
    actor_user_id = archive_actor_user_id
    with _persisted_batch(report, xlsx, manifest_sha256, actor_user_id) as persisted:
        values = {
            "batch_id": persisted.batch_id,
            "source_row_number": "1" if duplicate == "source_row_number" else "999",
            "relative_path": (
                "[Другой]\\Другой.docx"
                if duplicate == "source_row_number"
                else report.rows[0].source.relative_path
            ),
            "sha256": "f" * 64,
        }
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        INSERT INTO public.operational_order_import_rows (
                            batch_id, source_row_number, source_filename,
                            source_document_type, source_status, source_event_type,
                            source_folder, archive_section, relative_path,
                            file_extension, file_size, file_sha256, initial_review_state
                        ) VALUES (
                            :batch_id, :source_row_number, 'Другой.docx',
                            'Приказ', 'Найден', 'Тест',
                            'Производственные приказы', '[Другой]', :relative_path,
                            '.docx', 1, :sha256, 'REQUISITES_PRECONFIRMED'
                        )
                        """
                    ),
                    values,
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_mid_insert_failure_rolls_back_batch(
    pass_report, archive_actor_user_id, monkeypatch
) -> None:
    _require_schema()
    report, xlsx, manifest_sha256 = pass_report
    actor_user_id = archive_actor_user_id
    fingerprint = calculate_batch_fingerprint(
        report,
        source_manifest_sha256=manifest_sha256,
    )
    from app.operational_orders.archive_import import persistence

    monkeypatch.setitem(
        persistence._INITIAL_REVIEW_BY_SOURCE_STATUS,
        "Не найден",
        "INVALID_REVIEW_STATE",
    )
    with pytest.raises(IntegrityError):
        persist_archive_import_batch(
            report=report,
            source_manifest_name=xlsx.name,
            source_manifest_sha256=manifest_sha256,
            actor_user_id=actor_user_id,
        )

    with engine.connect() as connection:
        assert connection.execute(
            text(
                """
                SELECT count(*) FROM public.operational_order_import_batches
                WHERE batch_fingerprint = :fingerprint
                """
            ),
            {"fingerprint": fingerprint},
        ).scalar_one() == 0


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_source_fields_are_immutable_but_review_fields_can_change(
    pass_report, archive_actor_user_id
) -> None:
    _require_schema()
    report, xlsx, manifest_sha256 = pass_report
    actor_user_id = archive_actor_user_id
    with _persisted_batch(report, xlsx, manifest_sha256, actor_user_id) as persisted:
        with pytest.raises(DBAPIError, match="source fields are immutable"):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        UPDATE public.operational_order_import_rows
                        SET source_filename = 'changed.docx'
                        WHERE batch_id = :batch_id
                        """
                    ),
                    {"batch_id": persisted.batch_id},
                )
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE public.operational_order_import_rows
                    SET review_outcome = 'CONFIRMED',
                        reviewed_at = now(),
                        created_at = created_at + interval '1 second',
                        version = version + 1
                    WHERE batch_id = :batch_id
                    """
                ),
                {"batch_id": persisted.batch_id},
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_caller_owned_transaction_is_not_committed(
    pass_report, archive_actor_user_id
) -> None:
    _require_schema()
    report, xlsx, manifest_sha256 = pass_report
    actor_user_id = archive_actor_user_id
    fingerprint = calculate_batch_fingerprint(
        report,
        source_manifest_sha256=manifest_sha256,
    )
    with engine.connect() as connection:
        transaction = connection.begin()
        persisted = persist_archive_import_batch(
            report=report,
            source_manifest_name=xlsx.name,
            source_manifest_sha256=manifest_sha256,
            actor_user_id=actor_user_id,
            connection=connection,
        )
        assert persisted.created is True
        transaction.rollback()
    with engine.connect() as connection:
        assert connection.execute(
            text(
                """
                SELECT count(*) FROM public.operational_order_import_batches
                WHERE batch_fingerprint = :fingerprint
                """
            ),
            {"fingerprint": fingerprint},
        ).scalar_one() == 0


def test_migration_is_single_head_with_exact_parent() -> None:
    assert get_alembic_heads(alembic_config()) == {MIGRATION_REVISION}
    module = _migration_module()
    assert module.revision == MIGRATION_REVISION
    assert module.down_revision == PREVIOUS_REVISION


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_downgrade_upgrade_cycle() -> None:
    _require_schema()
    module = _migration_module()
    with exclusive_migration_cycle() as connection:
        transaction = connection.begin()
        try:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                module.downgrade()
                assert not table_exists(connection, "operational_order_import_rows")
                assert not table_exists(connection, "operational_order_import_batches")
                module.upgrade()
                assert table_exists(connection, "operational_order_import_batches")
                assert table_exists(connection, "operational_order_import_rows")
        finally:
            transaction.rollback()
