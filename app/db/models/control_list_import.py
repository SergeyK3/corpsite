"""Control List import staging ORM models (ADR-057 / WP-CL-002).

Staging stores immutable profiler snapshots per import_run. It is not Source of Truth;
semantic_hint and sheet classification fields are recommendations, not canonical mapping.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

RUN_STATUS_STAGED = "staged"
RUN_STATUS_FAILED = "failed"
RUN_STATUS_CANCELLED = "cancelled"

SHEET_STATUS_ANALYZED = "analyzed"
SHEET_STATUS_EXCLUDED = "excluded"

PERSONNEL_CATEGORY_DOCTOR = "doctor"
PERSONNEL_CATEGORY_NURSING_STAFF = "nursing_staff"
PERSONNEL_CATEGORY_JUNIOR_MEDICAL_STAFF = "junior_medical_staff"
PERSONNEL_CATEGORY_OTHER_STAFF = "other_staff"
PERSONNEL_CATEGORY_UNKNOWN = "unknown"

EMPLOYMENT_MODE_PRIMARY = "primary"
EMPLOYMENT_MODE_CONCURRENT = "concurrent"
EMPLOYMENT_MODE_UNKNOWN = "unknown"

SHEET_PURPOSE_PERSONNEL_CONTROL_LIST = "personnel_control_list"
SHEET_PURPOSE_DECLARATION = "declaration"
SHEET_PURPOSE_UNKNOWN = "unknown"

ROW_KIND_EMPTY = "empty"
ROW_KIND_HEADER = "header"
ROW_KIND_TITLE = "title"
ROW_KIND_FOOTER = "footer"
ROW_KIND_DATA = "data"
ROW_KIND_SECTION_HEADER = "section_header"
ROW_KIND_UNKNOWN = "unknown"

INFERRED_TYPE_EMPTY = "empty"
INFERRED_TYPE_TEXT = "text"
INFERRED_TYPE_INTEGER = "integer"
INFERRED_TYPE_DECIMAL = "decimal"
INFERRED_TYPE_EXCEL_DATE = "excel_date"
INFERRED_TYPE_DATE_TEXT = "date_text"
INFERRED_TYPE_IIN_CANDIDATE = "iin_candidate"
INFERRED_TYPE_PHONE_CANDIDATE = "phone_candidate"
INFERRED_TYPE_COMPOSITE_TEXT = "composite_text"
INFERRED_TYPE_FORMULA = "formula"
INFERRED_TYPE_ERROR = "error"


class ControlListImportRun(Base):
    """One staging import run for a source workbook snapshot.

    Each run captures profiler output at a point in time (``profiler_version``).
    Staging is not canonical SoT — see ADR-057 §5.1 and WP-CL-002 §3.5.
    """

    __tablename__ = "control_list_import_runs"
    __table_args__ = (
        CheckConstraint(
            "length(trim(source_filename)) > 0",
            name="chk_control_list_import_runs_source_filename_nonempty",
        ),
        CheckConstraint(
            "length(source_sha256) = 64 AND source_sha256 ~ '^[0-9a-f]{64}$'",
            name="chk_control_list_import_runs_source_sha256_format",
        ),
        CheckConstraint(
            "length(trim(profiler_version)) > 0",
            name="chk_control_list_import_runs_profiler_version_nonempty",
        ),
        CheckConstraint(
            f"status IN ('{RUN_STATUS_STAGED}', '{RUN_STATUS_FAILED}', '{RUN_STATUS_CANCELLED}')",
            name="chk_control_list_import_runs_status",
        ),
        Index("ix_control_list_import_runs_status", "status", "imported_at"),
        Index("ix_control_list_import_runs_source_sha256", "source_sha256", "imported_at"),
        Index("ix_control_list_import_runs_imported_by", "imported_by", "imported_at"),
    )

    import_run_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_filename: Mapped[str] = mapped_column(Text, nullable=False)
    source_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    imported_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    profiler_version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'staged'"))


class ControlListImportSheet(Base):
    """Workbook sheet snapshot within an import run.

    ``personnel_category``, ``employment_mode`` and ``sheet_purpose`` are profiler
    classification snapshots for this run — not canonical mapping or Person attributes.
    Re-importing the same workbook may yield different values in a new run.
    """

    __tablename__ = "control_list_import_sheets"
    __table_args__ = (
        UniqueConstraint("import_run_id", "sheet_index", name="uq_control_list_import_sheets_run_index"),
        UniqueConstraint("import_run_id", "sheet_name", name="uq_control_list_import_sheets_run_name"),
        CheckConstraint("sheet_index >= 0", name="chk_control_list_import_sheets_sheet_index_positive"),
        CheckConstraint(
            "length(trim(sheet_name)) > 0",
            name="chk_control_list_import_sheets_sheet_name_nonempty",
        ),
        CheckConstraint(
            "personnel_category IN ("
            "'doctor', 'nursing_staff', 'junior_medical_staff', 'other_staff', 'unknown'"
            ")",
            name="chk_control_list_import_sheets_personnel_category",
        ),
        CheckConstraint(
            "employment_mode IN ('primary', 'concurrent', 'unknown')",
            name="chk_control_list_import_sheets_employment_mode",
        ),
        CheckConstraint(
            "sheet_purpose IN ('personnel_control_list', 'declaration', 'unknown')",
            name="chk_control_list_import_sheets_sheet_purpose",
        ),
        CheckConstraint(
            "status IN ('analyzed', 'excluded')",
            name="chk_control_list_import_sheets_status",
        ),
        Index("ix_control_list_import_sheets_run", "import_run_id", "sheet_index"),
        Index("ix_control_list_import_sheets_run_status", "import_run_id", "status"),
    )

    sheet_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    import_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("control_list_import_runs.import_run_id", ondelete="CASCADE"),
        nullable=False,
    )
    sheet_name: Mapped[str] = mapped_column(Text, nullable=False)
    sheet_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # Profiler snapshot at import_run time — not canonical sheet classification.
    personnel_category: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'unknown'"),
    )
    # Profiler snapshot; sheet context only — not a Person / PPR attribute.
    employment_mode: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'unknown'"),
    )
    # Profiler snapshot at import_run time — not canonical mapping.
    sheet_purpose: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'unknown'"),
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'analyzed'"))


class ControlListImportRow(Base):
    """Excel row snapshot within a staged sheet.

    ``row_kind`` is a profiler classification snapshot, not a canonical record type.
    """

    __tablename__ = "control_list_import_rows"
    __table_args__ = (
        UniqueConstraint("sheet_id", "excel_row_number", name="uq_control_list_import_rows_sheet_row"),
        CheckConstraint(
            "excel_row_number >= 1",
            name="chk_control_list_import_rows_excel_row_number_positive",
        ),
        CheckConstraint(
            "row_kind IN ("
            "'empty', 'header', 'title', 'footer', 'data', 'section_header', 'unknown'"
            ")",
            name="chk_control_list_import_rows_row_kind",
        ),
        Index("ix_control_list_import_rows_sheet", "sheet_id", "excel_row_number"),
        Index("ix_control_list_import_rows_sheet_kind", "sheet_id", "row_kind"),
    )

    row_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sheet_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("control_list_import_sheets.sheet_id", ondelete="CASCADE"),
        nullable=False,
    )
    excel_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    row_kind: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'unknown'"))
    section_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    section_caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ControlListImportCell(Base):
    """Excel cell snapshot with raw value and profiler typing metadata.

    ``semantic_hint`` is a profiler header-alias recommendation — not canonical column
    mapping (that lives in mapping profiles, WP-CL-003+). ``inferred_type`` and
    ``issue_codes`` are profiler snapshots, not normalized canonical values.
    """

    __tablename__ = "control_list_import_cells"
    __table_args__ = (
        UniqueConstraint("row_id", "column_index", name="uq_control_list_import_cells_row_column"),
        CheckConstraint(
            "column_index >= 1",
            name="chk_control_list_import_cells_column_index_positive",
        ),
        CheckConstraint(
            "length(trim(column_letter)) > 0",
            name="chk_control_list_import_cells_column_letter_nonempty",
        ),
        CheckConstraint(
            "inferred_type IN ("
            "'empty', 'text', 'integer', 'decimal', 'excel_date', 'date_text', "
            "'iin_candidate', 'phone_candidate', 'composite_text', 'formula', 'error'"
            ")",
            name="chk_control_list_import_cells_inferred_type",
        ),
        CheckConstraint(
            "jsonb_typeof(issue_codes) = 'array'",
            name="chk_control_list_import_cells_issue_codes_array",
        ),
        Index("ix_control_list_import_cells_row", "row_id", "column_index"),
        Index(
            "ix_control_list_import_cells_semantic_hint",
            "semantic_hint",
            postgresql_where=text("semantic_hint IS NOT NULL"),
        ),
    )

    cell_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    row_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("control_list_import_rows.row_id", ondelete="CASCADE"),
        nullable=False,
    )
    column_letter: Mapped[str] = mapped_column(Text, nullable=False)
    column_index: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_header: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    normalized_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Profiler-inferred type snapshot — not canonical normalized type.
    inferred_type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'empty'"))
    issue_codes: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    # Profiler header-alias recommendation — NOT canonical semantic field mapping.
    semantic_hint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_composite: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
