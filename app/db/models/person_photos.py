"""ORM models for canonical person photos (ADR-061 / WP-ADR061-001B)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CHAR,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SOURCE_KIND_INTAKE = "intake"
SOURCE_KIND_MANUAL_UPLOAD = "manual_upload"
SOURCE_KINDS = (SOURCE_KIND_INTAKE, SOURCE_KIND_MANUAL_UPLOAD)

CANONICALIZATION_MODE_TRANSFER = "transfer"
CANONICALIZATION_MODE_HIRE_APPLY = "hire_apply"
CANONICALIZATION_MODE_BACKFILL = "backfill"
CANONICALIZATION_MODES = (
    CANONICALIZATION_MODE_TRANSFER,
    CANONICALIZATION_MODE_HIRE_APPLY,
    CANONICALIZATION_MODE_BACKFILL,
)

BLOCKER_CODE_INTAKE_PHOTO_UNAVAILABLE = "INTAKE_PHOTO_UNAVAILABLE"
BLOCKER_CODE_PHOTO_CANONICALIZATION_FAILED = "PHOTO_CANONICALIZATION_FAILED"
BLOCKER_CODES = (
    BLOCKER_CODE_INTAKE_PHOTO_UNAVAILABLE,
    BLOCKER_CODE_PHOTO_CANONICALIZATION_FAILED,
)

MIME_TYPE_JPEG = "image/jpeg"
MAX_PHOTO_BYTE_SIZE = 512_000


class PersonPhoto(Base):
    """Canonical person-scoped photo version."""

    __tablename__ = "person_photos"
    __table_args__ = (
        UniqueConstraint("person_photo_id", "person_id", name="uq_person_photos_id_person"),
        UniqueConstraint("storage_rel_path", name="uq_person_photos_storage_rel_path"),
        Index(
            "uq_person_photos_one_active",
            "person_id",
            unique=True,
            postgresql_where=text("is_active = TRUE"),
        ),
        Index("ix_person_photos_person_created", "person_id", "created_at"),
    )

    person_photo_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    person_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("persons.person_id", ondelete="RESTRICT"),
        nullable=False,
    )
    file_id: Mapped[str] = mapped_column(Text, nullable=False)
    storage_rel_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    superseded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    uploaded_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class PersonPhotoSource(Base):
    """Append-only provenance ledger linking intake/manual material to person_photos."""

    __tablename__ = "person_photo_sources"
    __table_args__ = (
        UniqueConstraint("command_id", name="uq_person_photo_sources_command_id"),
        ForeignKeyConstraint(
            ("person_photo_id", "person_id"),
            ("person_photos.person_photo_id", "person_photos.person_id"),
            name="fk_person_photo_sources_photo_person",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_person_photo_sources_intake_material",
            "source_application_id",
            "source_intake_photo_file_id",
            unique=True,
            postgresql_where=text("source_kind = 'intake'"),
        ),
        Index("ix_person_photo_sources_person", "person_id", "canonicalized_at"),
        Index("ix_person_photo_sources_photo", "person_photo_id"),
    )

    person_photo_source_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    person_photo_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    person_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_kind: Mapped[str] = mapped_column(Text, nullable=False)
    canonicalization_mode: Mapped[str] = mapped_column(Text, nullable=False)
    source_application_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    source_intake_photo_file_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    command_id: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    application_status_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    canonicalized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    canonicalized_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=True,
    )


class PersonnelApplicationBlocker(Base):
    """HR-visible blocker for personnel application apply gates."""

    __tablename__ = "personnel_application_blockers"
    __table_args__ = (
        Index(
            "uq_personnel_application_blockers_open",
            "application_id",
            "blocker_code",
            unique=True,
            postgresql_where=text("resolved_at IS NULL"),
        ),
        Index("ix_personnel_application_blockers_application", "application_id", "created_at"),
    )

    blocker_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    application_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("personnel_applications.application_id", ondelete="CASCADE"),
        nullable=False,
    )
    blocker_code: Mapped[str] = mapped_column(Text, nullable=False)
    detail_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=True,
    )


__all__ = [
    "BLOCKER_CODE_INTAKE_PHOTO_UNAVAILABLE",
    "BLOCKER_CODE_PHOTO_CANONICALIZATION_FAILED",
    "BLOCKER_CODES",
    "CANONICALIZATION_MODE_BACKFILL",
    "CANONICALIZATION_MODE_HIRE_APPLY",
    "CANONICALIZATION_MODE_TRANSFER",
    "CANONICALIZATION_MODES",
    "MAX_PHOTO_BYTE_SIZE",
    "MIME_TYPE_JPEG",
    "PersonPhoto",
    "PersonPhotoSource",
    "PersonnelApplicationBlocker",
    "SOURCE_KIND_INTAKE",
    "SOURCE_KIND_MANUAL_UPLOAD",
    "SOURCE_KINDS",
]
