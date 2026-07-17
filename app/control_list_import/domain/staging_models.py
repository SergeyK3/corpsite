"""In-memory staging snapshots used by normalization service (WP-CL-004)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class StagingCellInput:
    column_index: int
    raw_value: Optional[str]
    inferred_type: Optional[str] = None


@dataclass(frozen=True)
class StagingRowInput:
    row_id: int
    sheet_name: str
    excel_row_number: int
    row_kind: str
    cells: tuple[StagingCellInput, ...]


@dataclass(frozen=True)
class StagingSheetInput:
    sheet_name: str
    rows: tuple[StagingRowInput, ...]


@dataclass(frozen=True)
class StagingRunInput:
    import_run_id: int
    sheets: tuple[StagingSheetInput, ...]
