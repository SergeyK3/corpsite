"""ORM models for Personnel Intake (WP-PPR-INTAKE-001/002)."""
from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


class PersonnelIntakeLink(Base):
    __tablename__ = "personnel_intake_links"
    __table_args__ = {"schema": "public"}

    link_id = Column(BigInteger, primary_key=True, autoincrement=True)
    application_id = Column(
        BigInteger,
        ForeignKey("public.personnel_applications.application_id", ondelete="RESTRICT"),
        nullable=False,
    )
    token_hash = Column(Text, nullable=False, unique=True)
    status = Column(Text, nullable=False, server_default=text("'issued'"))
    issued_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    issued_by_user_id = Column(
        BigInteger,
        ForeignKey("public.users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    opened_at = Column(DateTime(timezone=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by_user_id = Column(
        BigInteger,
        ForeignKey("public.users.user_id", ondelete="RESTRICT"),
        nullable=True,
    )
    superseded_by_link_id = Column(
        BigInteger,
        ForeignKey("public.personnel_intake_links.link_id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class PersonnelIntakeDraft(Base):
    __tablename__ = "personnel_intake_drafts"
    __table_args__ = {"schema": "public"}

    draft_id = Column(BigInteger, primary_key=True, autoincrement=True)
    application_id = Column(
        BigInteger,
        ForeignKey("public.personnel_applications.application_id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    link_id = Column(
        BigInteger,
        ForeignKey("public.personnel_intake_links.link_id", ondelete="RESTRICT"),
        nullable=False,
    )
    status = Column(Text, nullable=False, server_default=text("'editable'"))
    payload = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class PersonnelIntakeSectionReview(Base):
    __tablename__ = "personnel_intake_section_reviews"
    __table_args__ = {"schema": "public"}

    review_id = Column(BigInteger, primary_key=True, autoincrement=True)
    application_id = Column(
        BigInteger,
        ForeignKey("public.personnel_applications.application_id", ondelete="RESTRICT"),
        nullable=False,
    )
    section_code = Column(Text, nullable=False)
    status = Column(Text, nullable=False, server_default=text("'pending'"))
    rework_comment = Column(Text, nullable=True)
    reviewed_by_user_id = Column(
        BigInteger,
        ForeignKey("public.users.user_id", ondelete="RESTRICT"),
        nullable=True,
    )
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class PersonnelIntakeTransfer(Base):
    __tablename__ = "personnel_intake_transfers"
    __table_args__ = {"schema": "public"}

    transfer_id = Column(BigInteger, primary_key=True, autoincrement=True)
    application_id = Column(
        BigInteger,
        ForeignKey("public.personnel_applications.application_id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    status = Column(Text, nullable=False, server_default=text("'pending'"))
    result = Column(Text, nullable=True)
    transferred_by_user_id = Column(
        BigInteger,
        ForeignKey("public.users.user_id", ondelete="RESTRICT"),
        nullable=True,
    )
    transferred_at = Column(DateTime(timezone=True), nullable=True)
    sections_transferred = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    command_ids = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
