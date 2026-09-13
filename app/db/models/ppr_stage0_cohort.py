"""Persisted, immutable Stage 0 PPR migration cohort snapshots."""
from __future__ import annotations

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

RUN_KIND_BASE = "BASE"
RUN_KIND_SUPPLEMENTAL = "SUPPLEMENTAL"


class PprStage0CohortRun(Base):
    __tablename__ = "ppr_stage0_cohort_runs"
    __table_args__ = (
        CheckConstraint("run_kind IN ('BASE', 'SUPPLEMENTAL')", name="chk_ppr_s0_run_kind"),
        CheckConstraint("source_type IN ('HR_CONTROL_LIST','CANONICAL_HR')", name="chk_ppr_s0_source_type"),
        CheckConstraint("(source_type='HR_CONTROL_LIST' AND source_batch_status IN ('APPLY_PENDING','APPLIED','PARTIALLY_APPLIED') AND source_batch_id IS NOT NULL) OR (source_type='CANONICAL_HR' AND source_batch_status='CANONICAL' AND source_batch_id IS NULL)", name="chk_ppr_s0_source_binding"),
        CheckConstraint("length(preview_fingerprint) = 64 AND preview_fingerprint ~ '^[0-9a-f]{64}$'", name="chk_ppr_s0_run_fingerprint"),
        Index("uq_ppr_s0_run_fingerprint", "preview_fingerprint", unique=True),
        Index("ix_ppr_s0_run_batch_frozen", "source_batch_id", "frozen_at"),
    )
    stage0_cohort_run_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_kind: Mapped[str] = mapped_column(Text, nullable=False)
    supplemental_of_run_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("ppr_stage0_cohort_runs.stage0_cohort_run_id", ondelete="RESTRICT"))
    source_batch_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("hr_import_batches.batch_id", ondelete="RESTRICT"))
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_batch_status: Mapped[str] = mapped_column(Text, nullable=False)
    preview_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    policy_version: Mapped[str] = mapped_column(Text, nullable=False)
    source_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    frozen_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PprStage0CohortParticipant(Base):
    __tablename__ = "ppr_stage0_cohort_participants"
    __table_args__ = (
        UniqueConstraint("stage0_cohort_run_id", "position", name="uq_ppr_s0_participant_position"),
        UniqueConstraint("stage0_cohort_run_id", "employee_id", name="uq_ppr_s0_participant_employee"),
        UniqueConstraint("stage0_cohort_run_id", "person_id", name="uq_ppr_s0_participant_person"),
        CheckConstraint("position >= 1", name="chk_ppr_s0_participant_position"),
        CheckConstraint("participant_snapshot_version = 1", name="chk_ppr_s0_participant_snapshot_version"),
        CheckConstraint("length(safe_fingerprint) = 64 AND safe_fingerprint ~ '^[0-9a-f]{64}$'", name="chk_ppr_s0_participant_fingerprint"),
    )
    stage0_participant_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    stage0_cohort_run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ppr_stage0_cohort_runs.stage0_cohort_run_id", ondelete="RESTRICT"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    employee_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("employees.employee_id", ondelete="RESTRICT"), nullable=False)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("persons.person_id", ondelete="RESTRICT"), nullable=False)
    source_batch_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("hr_import_batches.batch_id", ondelete="RESTRICT"))
    source_row_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("hr_import_rows.row_id", ondelete="RESTRICT"))
    identity_provenance_record_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("hr_import_normalized_records.normalized_record_id", ondelete="RESTRICT"))
    participant_snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    safe_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    employee_state_version: Mapped[int | None] = mapped_column(BigInteger)
    person_state_version: Mapped[int | None] = mapped_column(BigInteger)
    ppr_lifecycle_version: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PprStage0CohortBlocker(Base):
    __tablename__ = "ppr_stage0_cohort_blockers"
    __table_args__ = (
        UniqueConstraint("stage0_cohort_run_id", "candidate_key", "category", "reason_code", name="uq_ppr_s0_blocker_reason"),
        CheckConstraint("snapshot_version = 1", name="chk_ppr_s0_blocker_snapshot_version"),
        CheckConstraint("length(candidate_key) = 64 AND candidate_key ~ '^[0-9a-f]{64}$'", name="chk_ppr_s0_blocker_candidate_key"),
        CheckConstraint("length(safe_fingerprint) = 64 AND safe_fingerprint ~ '^[0-9a-f]{64}$'", name="chk_ppr_s0_blocker_fingerprint"),
        Index("ix_ppr_s0_blocker_run_category", "stage0_cohort_run_id", "category"),
    )
    stage0_blocker_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    stage0_cohort_run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ppr_stage0_cohort_runs.stage0_cohort_run_id", ondelete="RESTRICT"), nullable=False)
    employee_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("employees.employee_id", ondelete="RESTRICT"))
    person_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("persons.person_id", ondelete="RESTRICT"))
    source_batch_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("hr_import_batches.batch_id", ondelete="RESTRICT"))
    source_row_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("hr_import_rows.row_id", ondelete="RESTRICT"))
    identity_provenance_record_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("hr_import_normalized_records.normalized_record_id", ondelete="RESTRICT"))
    candidate_key: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code: Mapped[str] = mapped_column(Text, nullable=False)
    safe_detail: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    safe_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
