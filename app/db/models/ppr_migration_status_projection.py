"""Safe, current read model for WP-PPR-MIG-005B."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

PPR_MIGRATION_SECTIONS = (
    "general",
    "education",
    "training",
    "relatives",
    "military",
    "employment_biography",
    "employment_history",
    "foreign_languages",
    "awards",
    "academic_degrees_titles",
)
PPR_MIGRATION_STATUS_CODES = ("NOT_STARTED", "PROCESSING", "AUTO_READY", "REVIEW_REQUIRED", "CORRECTED_BY_HR", "ACCEPTED", "NO_SOURCE_DATA", "NOT_APPLICABLE", "BLOCKED", "STALE", "ERROR")

class PprMigrationStatusUniverse(Base):
    __tablename__ = "ppr_migration_status_universes"
    universe_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    universe_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    base_cohort_run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ppr_stage0_cohort_runs.stage0_cohort_run_id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class PprMigrationSectionStatusProjection(Base):
    __tablename__ = "ppr_migration_section_status_projection"
    universe_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ppr_migration_status_universes.universe_id"), primary_key=True)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("persons.person_id"), primary_key=True)
    section_code: Mapped[str] = mapped_column(Text, primary_key=True)
    employee_context_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("employees.employee_id"), nullable=False)
    org_unit_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("org_units.unit_id"))
    status_code: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code: Mapped[str] = mapped_column(Text, nullable=False)
    source_cohort_run_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    target_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    binding_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    row_version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
