"""Typed immutable output models for the archive import dry-run."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Literal


IssueSeverity = Literal["WARNING", "ERROR"]


@dataclass(frozen=True, slots=True)
class SourceOrderRow:
    excel_row: int
    source_number: str
    file_name: str
    document_type: str
    source_status: str
    event_type: str
    order_number: str
    order_date_raw: str
    note: str
    source_folder: str
    archive_section: str
    relative_path: str


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    severity: IssueSeverity
    message: str
    excel_row: int | None = None
    field: str | None = None
    related_rows: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class ValidationRowResult:
    source: SourceOrderRow
    resolved_path: str | None
    parsed_order_date: date | None
    extension: str
    file_exists: bool
    file_size_bytes: int | None
    sha256: str | None
    issues: tuple[ValidationIssue, ...]

    @property
    def is_valid(self) -> bool:
        return not any(issue.severity == "ERROR" for issue in self.issues)


@dataclass(frozen=True, slots=True)
class DryRunSummary:
    total_rows: int
    valid_rows: int
    error_rows: int
    existing_files: int
    extension_counts: dict[str, int]
    source_status_counts: dict[str, int]
    unique_archive_sections: int
    root_archive_files: int
    archive_section_counts: dict[str, int]
    filled_order_numbers: int
    empty_order_numbers: int
    filled_order_dates: int
    empty_order_dates: int
    duplicate_order_numbers: dict[str, tuple[int, ...]]
    duplicate_order_dates: dict[str, tuple[int, ...]]
    duplicate_sha256: dict[str, tuple[int, ...]]


@dataclass(frozen=True, slots=True)
class DryRunReport:
    xlsx_path: str
    archive_root: str
    sheet_name: str
    header_row: int
    source_headers: dict[str, str]
    rows: tuple[ValidationRowResult, ...]
    summary: DryRunSummary
    warnings: tuple[ValidationIssue, ...]
    errors: tuple[ValidationIssue, ...]

    @property
    def outcome(self) -> Literal["PASS", "FAIL"]:
        return "FAIL" if self.errors else "PASS"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["outcome"] = self.outcome
        return _json_ready(payload)


def _json_ready(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value
