"""Controlled CLI for importing a validated Operational Orders archive into staging."""
from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.engine import engine  # noqa: E402
from app.operational_orders.archive_import import (  # noqa: E402
    DEFAULT_SHEET_NAME,
    DryRunReport,
    DryRunTechnicalError,
    run_dry_run,
)
from app.operational_orders.archive_import.persistence import (  # noqa: E402
    ArchiveImportPersistenceError,
    PersistedArchiveImportBatch,
    persist_archive_import_batch,
)
from scripts.dry_run_operational_orders_archive_import import print_report  # noqa: E402


CONFIRM_FLAG = "--confirm-staging-import"


class StagingImportRefusedError(ValueError):
    """The archive was checked but is not eligible for a staging write."""

    def __init__(self, message: str, *, report: DryRunReport) -> None:
        super().__init__(message)
        self.report = report


@dataclass(frozen=True, slots=True)
class StagingImportExecution:
    report: DryRunReport
    persisted: PersistedArchiveImportBatch


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and import an Operational Orders archive into staging tables."
    )
    parser.add_argument("--xlsx", required=True, help="Path to the XLSX manifest")
    parser.add_argument("--archive-root", required=True, help="Archive root directory")
    parser.add_argument("--actor-user-id", required=True, type=_positive_int)
    parser.add_argument("--sheet", default=DEFAULT_SHEET_NAME, help="Manifest sheet name")
    parser.add_argument("--expected-rows", required=True, type=_positive_int)
    parser.add_argument(
        CONFIRM_FLAG,
        action="store_true",
        help="Explicitly allow the real staging database write",
    )
    return parser.parse_args(argv)


def run_staging_import(
    *,
    xlsx_path: str | Path,
    archive_root: str | Path,
    actor_user_id: int,
    confirm_staging_import: bool,
    sheet_name: str = DEFAULT_SHEET_NAME,
    expected_rows: int,
) -> StagingImportExecution:
    """Run the existing dry-run and persist its PASS result in one transaction."""
    xlsx = Path(xlsx_path)
    manifest_sha256 = _stable_sha256_file(xlsx)[0]
    report = run_dry_run(
        xlsx_path=xlsx,
        archive_root=archive_root,
        sheet_name=sheet_name,
        expected_rows=expected_rows,
    )
    if not _report_is_persistable(report):
        raise StagingImportRefusedError(
            "Dry-run result is not a row-clean PASS; staging was not changed",
            report=report,
        )
    if not confirm_staging_import:
        raise StagingImportRefusedError(
            f"Real staging write requires explicit {CONFIRM_FLAG}",
            report=report,
        )

    with engine.begin() as connection:
        _assert_source_snapshot_unchanged(
            report=report,
            xlsx=xlsx,
            manifest_sha256=manifest_sha256,
        )
        persisted = persist_archive_import_batch(
            report=report,
            source_manifest_name=xlsx.name,
            source_manifest_sha256=manifest_sha256,
            actor_user_id=actor_user_id,
            connection=connection,
        )
    return StagingImportExecution(report=report, persisted=persisted)


def main(argv: Sequence[str] | None = None) -> int:
    _configure_console_encoding()
    args = parse_args(argv)
    try:
        execution = run_staging_import(
            xlsx_path=args.xlsx,
            archive_root=args.archive_root,
            actor_user_id=args.actor_user_id,
            confirm_staging_import=args.confirm_staging_import,
            sheet_name=args.sheet,
            expected_rows=args.expected_rows,
        )
        print_report(execution.report)
        persisted = execution.persisted
        print(
            "Staging batch: "
            f"id={persisted.batch_id} "
            f"fingerprint={persisted.batch_fingerprint} "
            f"created={str(persisted.created).lower()} "
            f"rows={persisted.row_count}"
        )
        return 0
    except StagingImportRefusedError as exc:
        print_report(exc.report)
        print(f"STAGING IMPORT REFUSED: {exc}", file=sys.stderr)
        return 1
    except DryRunTechnicalError as exc:
        print(f"TECHNICAL ERROR [{exc.code}]: {exc}", file=sys.stderr)
        return 2
    except ArchiveImportPersistenceError as exc:
        print(f"STAGING PERSISTENCE ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception:
        print(
            "TECHNICAL ERROR [UNEXPECTED]: staging import failed; "
            "no database changes were committed",
            file=sys.stderr,
        )
        return 2


def _report_is_persistable(report: DryRunReport) -> bool:
    return (
        report.outcome == "PASS"
        and not report.errors
        and report.summary.error_rows == 0
        and report.summary.valid_rows == report.summary.total_rows
        and report.summary.total_rows == len(report.rows)
        and all(row.is_valid for row in report.rows)
    )


def _assert_source_snapshot_unchanged(
    *,
    report: DryRunReport,
    xlsx: Path,
    manifest_sha256: str,
) -> None:
    current_manifest_sha256, _ = _stable_sha256_file(xlsx)
    if current_manifest_sha256 != manifest_sha256:
        raise StagingImportRefusedError(
            "Manifest changed after validation; staging was not changed",
            report=report,
        )
    for row in report.rows:
        if not row.resolved_path or row.file_size_bytes is None or not row.sha256:
            raise StagingImportRefusedError(
                f"Validated file snapshot is incomplete at Excel row {row.source.excel_row}",
                report=report,
            )
        current_sha256, current_size = _stable_sha256_file(Path(row.resolved_path))
        if current_size != row.file_size_bytes or current_sha256 != row.sha256:
            raise StagingImportRefusedError(
                f"Validated file changed at Excel row {row.source.excel_row}; "
                "staging was not changed",
                report=report,
            )


def _stable_sha256_file(path: Path) -> tuple[str, int]:
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError("Source file changed while it was being hashed")
    return digest.hexdigest(), after.st_size


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
