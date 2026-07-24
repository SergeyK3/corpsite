"""Personnel Migration Framework ORM models (PMF-1 schema foundation).

See docs/adr/ADR-PMF-001-personnel-migration-framework.md and
docs/adr/ADR-EDU-001-employee-education-migration-architecture.md.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

DOMAIN_CODE_EDUCATION = "education"

RUN_STATUS_DRAFT = "draft"
RUN_STATUS_COMMITTED = "committed"
RUN_STATUS_VOIDED = "voided"
RUN_STATUS_FAILED = "failed"

RUN_STATUSES = (
    RUN_STATUS_DRAFT,
    RUN_STATUS_COMMITTED,
    RUN_STATUS_VOIDED,
    RUN_STATUS_FAILED,
)

ITEM_STATUS_DRAFT = "draft"
ITEM_STATUS_COMMITTED = "committed"
ITEM_STATUS_VOIDED = "voided"
ITEM_STATUS_SUPERSEDED = "superseded"
ITEM_STATUS_FAILED = "failed"

ITEM_STATUSES = (
    ITEM_STATUS_DRAFT,
    ITEM_STATUS_COMMITTED,
    ITEM_STATUS_VOIDED,
    ITEM_STATUS_SUPERSEDED,
    ITEM_STATUS_FAILED,
)

EDUCATION_KIND_BASIC = "basic"
EDUCATION_KIND_INTERNSHIP = "internship"
EDUCATION_KIND_RESIDENCY = "residency"
EDUCATION_KIND_MASTERS = "masters"
EDUCATION_KIND_PHD = "phd"
EDUCATION_KIND_OTHER = "other"

EDUCATION_KINDS = (
    EDUCATION_KIND_BASIC,
    EDUCATION_KIND_INTERNSHIP,
    EDUCATION_KIND_RESIDENCY,
    EDUCATION_KIND_MASTERS,
    EDUCATION_KIND_PHD,
    EDUCATION_KIND_OTHER,
)

INSTITUTION_TYPE_UNIVERSITY = "university"
INSTITUTION_TYPE_COLLEGE = "college"
INSTITUTION_TYPE_OTHER = "other"
INSTITUTION_TYPE_UNKNOWN = "unknown"

INSTITUTION_TYPES = (
    INSTITUTION_TYPE_UNIVERSITY,
    INSTITUTION_TYPE_COLLEGE,
    INSTITUTION_TYPE_OTHER,
    INSTITUTION_TYPE_UNKNOWN,
)

TRAINING_KIND_CONTINUING_EDUCATION = "continuing_education"
TRAINING_KIND_COURSE = "course"
TRAINING_KIND_SEMINAR = "seminar"
TRAINING_KIND_MASTER_CLASS = "master_class"
TRAINING_KIND_CERTIFICATE = "certificate"
TRAINING_KIND_OTHER = "other"

TRAINING_KINDS = (
    TRAINING_KIND_CONTINUING_EDUCATION,
    TRAINING_KIND_COURSE,
    TRAINING_KIND_SEMINAR,
    TRAINING_KIND_MASTER_CLASS,
    TRAINING_KIND_CERTIFICATE,
    TRAINING_KIND_OTHER,
)

VERIFICATION_STATUS_PENDING = "pending"
VERIFICATION_STATUS_VERIFIED = "verified"
VERIFICATION_STATUS_NEEDS_ATTENTION = "needs_attention"
VERIFICATION_STATUS_REJECTED = "rejected"

VERIFICATION_STATUSES = (
    VERIFICATION_STATUS_PENDING,
    VERIFICATION_STATUS_VERIFIED,
    VERIFICATION_STATUS_NEEDS_ATTENTION,
    VERIFICATION_STATUS_REJECTED,
)

LIFECYCLE_STATUS_DRAFT = "draft"
LIFECYCLE_STATUS_ACTIVE = "active"
LIFECYCLE_STATUS_SUPERSEDED = "superseded"
LIFECYCLE_STATUS_VOIDED = "voided"

LIFECYCLE_STATUSES = (
    LIFECYCLE_STATUS_DRAFT,
    LIFECYCLE_STATUS_ACTIVE,
    LIFECYCLE_STATUS_SUPERSEDED,
    LIFECYCLE_STATUS_VOIDED,
)

RELATIONSHIP_TYPE_FATHER = "father"
RELATIONSHIP_TYPE_MOTHER = "mother"
RELATIONSHIP_TYPE_BROTHER = "brother"
RELATIONSHIP_TYPE_SISTER = "sister"
RELATIONSHIP_TYPE_SON = "son"
RELATIONSHIP_TYPE_DAUGHTER = "daughter"
RELATIONSHIP_TYPE_SPOUSE = "spouse"
RELATIONSHIP_TYPE_OTHER_CLOSE = "other_close"

RELATIONSHIP_TYPES = (
    RELATIONSHIP_TYPE_FATHER,
    RELATIONSHIP_TYPE_MOTHER,
    RELATIONSHIP_TYPE_BROTHER,
    RELATIONSHIP_TYPE_SISTER,
    RELATIONSHIP_TYPE_SON,
    RELATIONSHIP_TYPE_DAUGHTER,
    RELATIONSHIP_TYPE_SPOUSE,
    RELATIONSHIP_TYPE_OTHER_CLOSE,
)

SECTION_SOURCE_TYPE_ENTERED = "entered"
SECTION_SOURCE_TYPE_IMPORTED = "imported"
SECTION_SOURCE_TYPE_NORMALIZED = "normalized"
SECTION_SOURCE_TYPE_DERIVED = "derived"

EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE = "episode"
EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY = "narrative_summary"
EXTERNAL_EMPLOYMENT_RECORD_KIND_ATTESTATION_NONE = "attestation_none"

EXTERNAL_EMPLOYMENT_RECORD_KINDS = (
    EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
    EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY,
    EXTERNAL_EMPLOYMENT_RECORD_KIND_ATTESTATION_NONE,
)

EXTERNAL_EMPLOYMENT_TYPE_PRIMARY = "primary"
EXTERNAL_EMPLOYMENT_TYPE_PART_TIME = "part_time"
EXTERNAL_EMPLOYMENT_TYPE_CONTRACT = "contract"
EXTERNAL_EMPLOYMENT_TYPE_INTERNSHIP = "internship"
EXTERNAL_EMPLOYMENT_TYPE_OTHER = "other"

EXTERNAL_EMPLOYMENT_TYPES = (
    EXTERNAL_EMPLOYMENT_TYPE_PRIMARY,
    EXTERNAL_EMPLOYMENT_TYPE_PART_TIME,
    EXTERNAL_EMPLOYMENT_TYPE_CONTRACT,
    EXTERNAL_EMPLOYMENT_TYPE_INTERNSHIP,
    EXTERNAL_EMPLOYMENT_TYPE_OTHER,
)

EXTERNAL_EMPLOYMENT_SOURCE_MANUAL = "manual"
EXTERNAL_EMPLOYMENT_SOURCE_IMPORT_ROW = "import_row"
EXTERNAL_EMPLOYMENT_SOURCE_PMF_MIGRATION = "pmf_migration"
EXTERNAL_EMPLOYMENT_SOURCE_INTEGRATION = "integration"

EXTERNAL_EMPLOYMENT_SOURCE_SYSTEMS = (
    EXTERNAL_EMPLOYMENT_SOURCE_MANUAL,
    EXTERNAL_EMPLOYMENT_SOURCE_IMPORT_ROW,
    EXTERNAL_EMPLOYMENT_SOURCE_PMF_MIGRATION,
    EXTERNAL_EMPLOYMENT_SOURCE_INTEGRATION,
)

EXTERNAL_EMPLOYMENT_VERIFICATION_STATUS_DISPUTED = "disputed"

EXTERNAL_EMPLOYMENT_VERIFICATION_STATUSES = (
    VERIFICATION_STATUS_PENDING,
    VERIFICATION_STATUS_VERIFIED,
    EXTERNAL_EMPLOYMENT_VERIFICATION_STATUS_DISPUTED,
)

# ADR-056 §12.1 — section row lifecycle (no draft; wizard draft lives on migration_items).
EXTERNAL_EMPLOYMENT_LIFECYCLE_STATUSES = (
    LIFECYCLE_STATUS_ACTIVE,
    LIFECYCLE_STATUS_SUPERSEDED,
    LIFECYCLE_STATUS_VOIDED,
)

MILITARY_RECORD_KIND_REGISTRATION = "registration"
MILITARY_RECORD_KIND_NOT_APPLICABLE = "not_applicable"

MILITARY_RECORD_KINDS = (
    MILITARY_RECORD_KIND_REGISTRATION,
    MILITARY_RECORD_KIND_NOT_APPLICABLE,
)

# WP-PR-026 §10.1 — no draft on section rows.
MILITARY_LIFECYCLE_STATUSES = (
    LIFECYCLE_STATUS_ACTIVE,
    LIFECYCLE_STATUS_SUPERSEDED,
    LIFECYCLE_STATUS_VOIDED,
)

SECTION_SOURCE_TYPES = (
    SECTION_SOURCE_TYPE_ENTERED,
    SECTION_SOURCE_TYPE_IMPORTED,
    SECTION_SOURCE_TYPE_NORMALIZED,
    SECTION_SOURCE_TYPE_DERIVED,
)

EVENT_TYPE_EDUCATION_MIGRATED = "EDUCATION_MIGRATED"
EVENT_TYPE_EDUCATION_VERIFIED = "EDUCATION_VERIFIED"
EVENT_TYPE_EDUCATION_SUPERSEDED = "EDUCATION_SUPERSEDED"
EVENT_TYPE_EDUCATION_VOIDED = "EDUCATION_VOIDED"


class PersonnelMigrationDomain(Base):
    """Registry of PMF domain plugins."""

    __tablename__ = "personnel_migration_domains"

    domain_code: Mapped[str] = mapped_column(Text, primary_key=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
    target_table_names: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    control_list_columns: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class PersonnelMigrationRun(Base):
    """Technical audit trail for a migration wizard session."""

    __tablename__ = "personnel_migration_runs"
    __table_args__ = (Index("ix_pmf_runs_domain_person", "domain_code", "person_id"),)

    run_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    domain_code: Mapped[str] = mapped_column(
        Text,
        ForeignKey("personnel_migration_domains.domain_code", ondelete="RESTRICT"),
        nullable=False,
    )
    employee_context_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("employees.employee_id", ondelete="SET NULL"),
        nullable=True,
    )
    person_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("persons.person_id", ondelete="RESTRICT"),
        nullable=True,
    )
    run_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{RUN_STATUS_DRAFT}'"),
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    committed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    committed_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    voided_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    void_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )


class PersonnelMigrationItem(Base):
    """Mapping between a staging candidate and a committed personnel record."""

    __tablename__ = "personnel_migration_items"
    __table_args__ = (
        Index("ix_pmf_items_run_id", "run_id"),
        Index("ix_pmf_items_domain_import", "domain_code", "import_batch_id", "import_row_id"),
    )

    item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("personnel_migration_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    domain_code: Mapped[str] = mapped_column(
        Text,
        ForeignKey("personnel_migration_domains.domain_code", ondelete="RESTRICT"),
        nullable=False,
    )
    source_kind: Mapped[str] = mapped_column(Text, nullable=False)
    source_record_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    import_batch_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("hr_import_batches.batch_id", ondelete="SET NULL"),
        nullable=True,
    )
    import_row_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("hr_import_rows.row_id", ondelete="SET NULL"),
        nullable=True,
    )
    record_kind: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_table_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_record_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    item_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{ITEM_STATUS_DRAFT}'"),
    )
    draft_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    source_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    validation_errors: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    committed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    void_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class PersonnelRecordEvent(Base):
    """Business history journal for person-owned personnel records."""

    __tablename__ = "personnel_record_events"
    __table_args__ = (Index("ix_personnel_record_events_person_domain", "person_id", "domain_code"),)

    event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("persons.person_id", ondelete="RESTRICT"),
        nullable=False,
    )
    employee_context_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("employees.employee_id", ondelete="SET NULL"),
        nullable=True,
    )
    domain_code: Mapped[Optional[str]] = mapped_column(
        Text,
        ForeignKey("personnel_migration_domains.domain_code", ondelete="RESTRICT"),
        nullable=True,
    )
    record_table_name: Mapped[str] = mapped_column(Text, nullable=False)
    record_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    migration_run_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("personnel_migration_runs.run_id", ondelete="SET NULL"),
        nullable=True,
    )
    migration_item_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("personnel_migration_items.item_id", ondelete="SET NULL"),
        nullable=True,
    )


class PersonEducation(Base):
    """Permanent structured education record (person-owned SoT)."""

    __tablename__ = "person_education"
    __table_args__ = (
        Index("ix_person_education_person_id", "person_id"),
        Index("ix_person_education_person_lifecycle", "person_id", "lifecycle_status"),
    )

    education_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("persons.person_id", ondelete="RESTRICT"),
        nullable=False,
    )
    employee_context_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("employees.employee_id", ondelete="SET NULL"),
        nullable=True,
    )
    education_kind: Mapped[str] = mapped_column(Text, nullable=False)
    institution_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    institution_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    specialty: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    qualification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    completed_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    diploma_number: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    document_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    verification_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{VERIFICATION_STATUS_PENDING}'"),
    )
    lifecycle_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{LIFECYCLE_STATUS_ACTIVE}'"),
    )
    import_batch_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("hr_import_batches.batch_id", ondelete="SET NULL"),
        nullable=True,
    )
    import_row_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("hr_import_rows.row_id", ondelete="SET NULL"),
        nullable=True,
    )
    source_field: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parse_method: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    migrated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    migrated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )


class PersonTraining(Base):
    """Permanent continuing education / course record (person-owned SoT)."""

    __tablename__ = "person_training"
    __table_args__ = (
        Index("ix_person_training_person_id", "person_id"),
        Index("ix_person_training_person_lifecycle", "person_id", "lifecycle_status"),
    )

    training_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("persons.person_id", ondelete="RESTRICT"),
        nullable=False,
    )
    employee_context_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("employees.employee_id", ondelete="SET NULL"),
        nullable=True,
    )
    training_kind: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    organization_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hours: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    started_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    completed_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    certificate_number: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    document_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    verification_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{VERIFICATION_STATUS_PENDING}'"),
    )
    lifecycle_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{LIFECYCLE_STATUS_ACTIVE}'"),
    )
    import_batch_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("hr_import_batches.batch_id", ondelete="SET NULL"),
        nullable=True,
    )
    import_row_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("hr_import_rows.row_id", ondelete="SET NULL"),
        nullable=True,
    )
    source_field: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parse_method: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    migrated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    migrated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )


class PersonExternalEmployment(Base):
    """External employment biography record (PPR-EMPLOYMENT-BIOGRAPHY, person-owned SoT)."""

    __tablename__ = "person_external_employment"
    __table_args__ = (
        Index("ix_person_external_employment_person_id", "person_id"),
        Index("ix_person_external_employment_person_lifecycle", "person_id", "lifecycle_status"),
        Index(
            "ix_pee_supersedes_employment_id",
            "supersedes_employment_id",
            postgresql_where=text("supersedes_employment_id IS NOT NULL"),
        ),
    )

    employment_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("persons.person_id", ondelete="RESTRICT"),
        nullable=False,
    )
    supersedes_employment_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("person_external_employment.employment_id", ondelete="RESTRICT"),
        nullable=True,
    )
    record_kind: Mapped[str] = mapped_column(Text, nullable=False)
    employer_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    department_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    position_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    employment_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    ended_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    termination_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    document_reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_system: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{EXTERNAL_EMPLOYMENT_SOURCE_MANUAL}'"),
    )
    source_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provenance: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    verification_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{VERIFICATION_STATUS_PENDING}'"),
    )
    lifecycle_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{LIFECYCLE_STATUS_ACTIVE}'"),
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    employee_context_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )


class PersonMilitaryService(Base):
    """Military registration record (PPR-MILITARY, person-owned SoT)."""

    __tablename__ = "person_military_service"
    __table_args__ = (
        Index("ix_person_military_service_person_id", "person_id"),
        Index("ix_person_military_service_person_lifecycle", "person_id", "lifecycle_status"),
    )

    military_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("persons.person_id", ondelete="RESTRICT"),
        nullable=False,
    )
    record_kind: Mapped[str] = mapped_column(Text, nullable=False)
    obligation_status: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    registration_category: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    military_rank: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    military_specialty_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    personnel_composition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fitness_category: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    registration_status: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    commissariat_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    registered_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    deregistered_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    military_id_book_series: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    military_id_book_number: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    registration_certificate_series: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    registration_certificate_number: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verification_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{VERIFICATION_STATUS_PENDING}'"),
    )
    lifecycle_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{LIFECYCLE_STATUS_ACTIVE}'"),
    )
    source_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{SECTION_SOURCE_TYPE_ENTERED}'"),
    )
    provenance: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    employee_context_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )


class PersonRelative(Base):
    """Permanent family/relative record (PPR-FAMILY, person-owned SoT)."""

    __tablename__ = "person_relatives"
    __table_args__ = (
        Index("ix_person_relatives_person_id", "person_id"),
        Index("ix_person_relatives_person_lifecycle", "person_id", "lifecycle_status"),
    )

    relative_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("persons.person_id", ondelete="RESTRICT"),
        nullable=False,
    )
    relationship_type: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    birth_place: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    organization_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    residence_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verification_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{VERIFICATION_STATUS_PENDING}'"),
    )
    lifecycle_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{LIFECYCLE_STATUS_ACTIVE}'"),
    )
    source_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{SECTION_SOURCE_TYPE_ENTERED}'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
