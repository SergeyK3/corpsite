#!/usr/bin/env python3
"""Read-only Control List workbook profiler CLI (WP-CL-001)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.ops.control_list_import.report_writer import write_json_report, write_markdown_report
from scripts.ops.control_list_import.value_types import sha256_file
from scripts.ops.control_list_import.workbook_profile import profile_workbook

DEFAULT_EXCLUSION_TERMS = ("декларация",)


def _default_output_paths(input_path: Path) -> tuple[Path, Path]:
    stem = input_path.with_suffix("")
    return stem.parent / f"{stem.name}-profile.json", stem.parent / f"{stem.name}-profile.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only profiler for historical Control List XLSX workbooks.",
    )
    parser.add_argument("--input", required=True, help="Path to source XLSX (read-only).")
    parser.add_argument(
        "--output-json",
        help="Path for JSON report (default: <input-stem>-profile.json).",
    )
    parser.add_argument(
        "--output-md",
        help="Path for Markdown report (default: <input-stem>-profile.md).",
    )
    parser.add_argument(
        "--exclude-sheet-name-contains",
        action="append",
        default=None,
        help='Exclude sheets whose name contains this term (default: "декларация"). Repeatable.',
    )
    parser.add_argument(
        "--max-samples-per-column",
        type=int,
        default=5,
        help="Maximum masked samples per column (default: 5).",
    )
    parser.add_argument(
        "--header-scan-limit",
        type=int,
        default=30,
        help="Maximum rows scanned for probable header (default: 30).",
    )
    parser.add_argument(
        "--output-diagnostics",
        help="Optional path for standalone diagnostics JSON (e.g. C:\\Temp\\control-list-diagnostics.json).",
    )
    parser.add_argument("--verbose", action="store_true", help="Print progress to stderr.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.is_file():
        parser.error(f"Input file not found: {input_path}")

    exclusion_terms = args.exclude_sheet_name_contains
    if not exclusion_terms:
        exclusion_terms = list(DEFAULT_EXCLUSION_TERMS)

    default_json, default_md = _default_output_paths(input_path)
    output_json = Path(args.output_json) if args.output_json else default_json
    output_md = Path(args.output_md) if args.output_md else default_md

    sha_before = sha256_file(str(input_path))
    if args.verbose:
        print(f"SHA-256 before: {sha_before}", file=sys.stderr)

    report = profile_workbook(
        input_path,
        exclusion_terms=exclusion_terms,
        max_samples_per_column=args.max_samples_per_column,
        header_scan_limit=args.header_scan_limit,
    )

    sha_after = sha256_file(str(input_path))
    if args.verbose:
        print(f"SHA-256 after: {sha_after}", file=sys.stderr)

    unchanged = sha_before == sha_after
    report["source"]["sha256_before"] = sha_before
    report["source"]["sha256_after"] = sha_after
    report["source"]["unchanged"] = unchanged

    if not unchanged:
        print(
            "ERROR: Source file SHA-256 changed during read-only analysis.",
            file=sys.stderr,
        )
        return 2

    write_json_report(output_json, report)
    write_markdown_report(output_md, report)

    if args.output_diagnostics:
        diag_path = Path(args.output_diagnostics)
        diag_path.parent.mkdir(parents=True, exist_ok=True)
        write_json_report(diag_path, report.get("diagnostics", {}))

    if args.verbose:
        print(f"JSON report: {output_json}", file=sys.stderr)
        print(f"Markdown report: {output_md}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
