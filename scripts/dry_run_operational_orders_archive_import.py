"""CLI for the read-only Operational Orders archive import dry-run."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.operational_orders.archive_import import (  # noqa: E402
    DEFAULT_SHEET_NAME,
    DryRunTechnicalError,
    run_dry_run,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only validation of an Operational Orders archive XLSX manifest."
    )
    parser.add_argument("--xlsx", required=True, help="Path to the XLSX manifest")
    parser.add_argument("--archive-root", required=True, help="Archive root directory")
    parser.add_argument("--sheet", default=DEFAULT_SHEET_NAME, help="Manifest sheet name")
    parser.add_argument("--json-out", default=None, help="Optional path for the full JSON report")
    parser.add_argument("--expected-rows", type=int, default=None, help="Expected manifest row count")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    _configure_console_encoding()
    args = parse_args(argv)
    try:
        report = run_dry_run(
            xlsx_path=args.xlsx,
            archive_root=args.archive_root,
            sheet_name=args.sheet,
            expected_rows=args.expected_rows,
        )
        if args.json_out:
            output = Path(args.json_out)
            _validate_json_output_path(
                output=output,
                xlsx=Path(args.xlsx),
                archive_root=Path(args.archive_root),
            )
            output.parent.mkdir(parents=True, exist_ok=True)
            try:
                with output.open("x", encoding="utf-8") as destination:
                    json.dump(
                        report.to_dict(),
                        destination,
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
            except FileExistsError as exc:
                raise DryRunTechnicalError(
                    "JSON_OUTPUT_EXISTS",
                    f"JSON output already exists and will not be overwritten: {output}",
                ) from exc
        print_report(report)
        return 0 if report.outcome == "PASS" else 1
    except DryRunTechnicalError as exc:
        print(f"TECHNICAL ERROR [{exc.code}]: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"TECHNICAL ERROR [UNEXPECTED]: {exc}", file=sys.stderr)
        return 2


def _configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def _validate_json_output_path(*, output: Path, xlsx: Path, archive_root: Path) -> None:
    output_resolved = output.resolve(strict=False)
    xlsx_resolved = xlsx.resolve(strict=False)
    archive_resolved = archive_root.resolve(strict=False)
    if os.path.normcase(str(output_resolved)) == os.path.normcase(str(xlsx_resolved)):
        raise DryRunTechnicalError(
            "JSON_OUTPUT_CONFLICT",
            "JSON output must not overwrite the source XLSX.",
        )
    try:
        inside_archive = os.path.normcase(
            os.path.commonpath((str(output_resolved), str(archive_resolved)))
        ) == os.path.normcase(str(archive_resolved))
    except ValueError:
        inside_archive = False
    if inside_archive:
        raise DryRunTechnicalError(
            "JSON_OUTPUT_CONFLICT",
            "JSON output must be outside the archive root.",
        )


def print_report(report) -> None:
    summary = report.summary
    print(f"Excel: {report.xlsx_path}")
    print(f"Archive root: {report.archive_root}")
    print(f"Sheet: {report.sheet_name}")
    print(f"Rows: {summary.total_rows}")
    print(f"Valid rows: {summary.valid_rows}")
    print(f"Error rows: {summary.error_rows}")
    print(f"Existing files: {summary.existing_files}")
    _print_mapping("Extensions", summary.extension_counts)
    _print_mapping("Source statuses", summary.source_status_counts)
    print(f"Unique archive sections: {summary.unique_archive_sections}")
    print(f"Root archive files: {summary.root_archive_files}")
    _print_mapping("Files by archive section", summary.archive_section_counts)
    print(
        "Order numbers: "
        f"filled={summary.filled_order_numbers}, empty={summary.empty_order_numbers}"
    )
    print(
        "Order dates: "
        f"filled={summary.filled_order_dates}, empty={summary.empty_order_dates}"
    )
    _print_mapping("Duplicate order numbers", summary.duplicate_order_numbers)
    _print_mapping("Duplicate order dates", summary.duplicate_order_dates)
    _print_mapping("Duplicate SHA-256 groups", summary.duplicate_sha256)
    _print_issues("Warnings", report.warnings)
    _print_issues("Errors", report.errors)
    print(f"Result: {report.outcome}")


def _print_mapping(title: str, values: dict) -> None:
    print(f"{title}:")
    if not values:
        print("  <none>")
        return
    for key, value in values.items():
        if isinstance(value, (tuple, list)):
            display = ", ".join(str(item) for item in value)
        else:
            display = str(value)
        print(f"  {key}: {display}")


def _print_issues(title: str, issues) -> None:
    print(f"{title}:")
    if not issues:
        print("  <none>")
        return
    for issue in issues:
        location = f" row={issue.excel_row}" if issue.excel_row is not None else ""
        print(f"  [{issue.code}]{location} {issue.message}")


if __name__ == "__main__":
    raise SystemExit(main())
