"""Control List mapping profile ORM models (ADR-057 / WP-CL-003).

Mapping profiles are versioned configuration — not staging snapshots and not canonical PPR data.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

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
from sqlalchemy.orm import Mapped, mapped_column

from app.control_list_import.domain.vocabulary import PARSER_CODES, SEMANTIC_FIELDS
from app.db.base import Base

PROFILE_STATUS_DRAFT = "draft"
PROFILE_STATUS_ACTIVE = "active"
PROFILE_STATUS_ARCHIVED = "archived"

PROFILE_STATUSES = frozenset(
    {
        PROFILE_STATUS_DRAFT,
        PROFILE_STATUS_ACTIVE,
        PROFILE_STATUS_ARCHIVED,
    }
)

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


def _sql_in(values: frozenset[str]) -> str:
    return ", ".join(f"'{value}'" for value in sorted(values))


class ControlListMappingProfile(Base):
    """Versioned mapping profile configuration for a control-list workbook family."""

    __tablename__ = "control_list_mapping_profiles"
    __table_args__ = (
        UniqueConstraint(
            "profile_code",
            "profile_version",
            name="uq_control_list_mapping_profiles_code_version",
        ),
        CheckConstraint(
            "length(trim(profile_code)) > 0",
            name="chk_control_list_mapping_profiles_code_nonempty",
        ),
        CheckConstraint(
            "length(trim(profile_name)) > 0",
            name="chk_control_list_mapping_profiles_name_nonempty",
        ),
        CheckConstraint(
            "profile_version >= 1",
            name="chk_control_list_mapping_profiles_version_positive",
        ),
        CheckConstraint(
            f"status IN ({_sql_in(PROFILE_STATUSES)})",
            name="chk_control_list_mapping_profiles_status",
        ),
        Index(
            "ix_control_list_mapping_profiles_status",
            "status",
            "profile_code",
            "profile_version",
        ),
        Index("ix_control_list_mapping_profiles_created_by", "created_by", "created_at"),
    )

    profile_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_code: Mapped[str] = mapped_column(Text, nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ControlListMappingProfileSheet(Base):
    """Sheet-level mapping rules within a profile version."""

    __tablename__ = "control_list_mapping_profile_sheets"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "sheet_name",
            name="uq_control_list_mapping_profile_sheets_profile_name",
        ),
        CheckConstraint(
            "length(trim(sheet_name)) > 0",
            name="chk_control_list_mapping_profile_sheets_sheet_name_nonempty",
        ),
        CheckConstraint(
            "personnel_category IN ("
            "'doctor', 'nursing_staff', 'junior_medical_staff', 'other_staff', 'unknown'"
            ")",
            name="chk_control_list_mapping_profile_sheets_personnel_category",
        ),
        CheckConstraint(
            "employment_mode IN ('primary', 'concurrent', 'unknown')",
            name="chk_control_list_mapping_profile_sheets_employment_mode",
        ),
        CheckConstraint(
            "sheet_purpose IN ('personnel_control_list', 'declaration', 'unknown')",
            name="chk_control_list_mapping_profile_sheets_sheet_purpose",
        ),
        CheckConstraint(
            "header_row_override IS NULL OR header_row_override >= 1",
            name="chk_control_list_mapping_profile_sheets_header_row_override",
        ),
        Index("ix_control_list_mapping_profile_sheets_profile", "profile_id", "sheet_name"),
    )

    profile_sheet_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("control_list_mapping_profiles.profile_id", ondelete="CASCADE"),
        nullable=False,
    )
    sheet_name: Mapped[str] = mapped_column(Text, nullable=False)
    personnel_category: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'unknown'"),
    )
    employment_mode: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'unknown'"),
    )
    sheet_purpose: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'unknown'"),
    )
    header_row_override: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class ControlListMappingProfileColumn(Base):
    """Column-level semantic mapping and parser selection within a profile sheet rule."""

    __tablename__ = "control_list_mapping_profile_columns"
    __table_args__ = (
        UniqueConstraint(
            "profile_sheet_id",
            "column_index",
            name="uq_control_list_mapping_profile_columns_sheet_column",
        ),
        CheckConstraint(
            "column_index >= 1",
            name="chk_control_list_mapping_profile_columns_column_index_positive",
        ),
        CheckConstraint(
            f"semantic_field IN ({_sql_in(SEMANTIC_FIELDS)})",
            name="chk_control_list_mapping_profile_columns_semantic_field",
        ),
        CheckConstraint(
            f"parser_code IN ({_sql_in(PARSER_CODES)})",
            name="chk_control_list_mapping_profile_columns_parser_code",
        ),
        Index(
            "ix_control_list_mapping_profile_columns_sheet",
            "profile_sheet_id",
            "column_index",
        ),
        Index("ix_control_list_mapping_profile_columns_semantic_field", "semantic_field"),
    )

    profile_column_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_sheet_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("control_list_mapping_profile_sheets.profile_sheet_id", ondelete="CASCADE"),
        nullable=False,
    )
    column_index: Mapped[int] = mapped_column(Integer, nullable=False)
    column_letter: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_header: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Import-domain semantic target — not a PPR column name.
    semantic_field: Mapped[str] = mapped_column(Text, nullable=False)
    # Parser selection for normalization pipeline — not a PPR mutation.
    parser_code: Mapped[str] = mapped_column(Text, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
