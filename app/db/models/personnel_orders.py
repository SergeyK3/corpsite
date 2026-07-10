"""Personnel orders ORM models (WP-PO-003 storage foundation).

MVP order types: HIRE, TRANSFER, TERMINATION, CONCURRENT_DUTY_START, CONCURRENT_DUTY_END.
See docs/personnel-orders/WP-PO-002-personnel-orders-architecture-scope-decision.md.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
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

ORDER_CLASS_PERSONNEL = "PERSONNEL"

ORDER_TYPE_HIRE = "HIRE"
ORDER_TYPE_TRANSFER = "TRANSFER"
ORDER_TYPE_TERMINATION = "TERMINATION"
ORDER_TYPE_CONCURRENT_DUTY_START = "CONCURRENT_DUTY_START"
ORDER_TYPE_CONCURRENT_DUTY_END = "CONCURRENT_DUTY_END"
ORDER_TYPE_COMPOSITE = "COMPOSITE"

MVP_ORDER_TYPE_CODES = (
    ORDER_TYPE_HIRE,
    ORDER_TYPE_TRANSFER,
    ORDER_TYPE_TERMINATION,
    ORDER_TYPE_CONCURRENT_DUTY_START,
    ORDER_TYPE_CONCURRENT_DUTY_END,
)

MVP_HEADER_ORDER_TYPE_CODES = MVP_ORDER_TYPE_CODES + (ORDER_TYPE_COMPOSITE,)

MVP_ITEM_TYPE_CODES = MVP_ORDER_TYPE_CODES

ORDER_STATUS_DRAFT = "DRAFT"
ORDER_STATUS_READY_FOR_SIGNATURE = "READY_FOR_SIGNATURE"
ORDER_STATUS_SIGNED = "SIGNED"
ORDER_STATUS_REGISTERED = "REGISTERED"
ORDER_STATUS_VOIDED = "VOIDED"

ORDER_STATUSES = (
    ORDER_STATUS_DRAFT,
    ORDER_STATUS_READY_FOR_SIGNATURE,
    ORDER_STATUS_SIGNED,
    ORDER_STATUS_REGISTERED,
    ORDER_STATUS_VOIDED,
)

SOURCE_MODE_PAPER = "PAPER"
SOURCE_MODE_DIGITAL = "DIGITAL"

ITEM_STATUS_ACTIVE = "ACTIVE"
ITEM_STATUS_VOIDED = "VOIDED"

LOCALE_KK = "kk"
LOCALE_RU = "ru"

ATTACHMENT_KIND_SIGNED_SCAN = "SIGNED_SCAN"
ATTACHMENT_KIND_BASIS_DOCUMENT = "BASIS_DOCUMENT"
ATTACHMENT_KIND_UNSIGNED_DRAFT = "UNSIGNED_DRAFT"

STORAGE_TYPE_LOCAL_SHARE = "LOCAL_SHARE"
STORAGE_TYPE_URL = "URL"

PRINT_FORMAT_PDF = "pdf"
PRINT_FORMAT_DOCX = "docx"


class PersonnelOrder(Base):
    """Header record for a personnel order (кадровый приказ)."""

    __tablename__ = "personnel_orders"
    __table_args__ = (
        UniqueConstraint("order_number", name="uq_personnel_orders_order_number"),
        Index("ix_personnel_orders_status", "status"),
        Index("ix_personnel_orders_order_date", "order_date"),
        Index("ix_personnel_orders_type_code", "order_type_code"),
    )

    order_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Nullable until paper-journal registration (WP-PO-008 Paper First drafts).
    order_number: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    order_type_code: Mapped[str] = mapped_column(Text, nullable=False)
    order_class: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{ORDER_CLASS_PERSONNEL}'"),
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    source_mode: Mapped[str] = mapped_column(Text, nullable=False)
    legal_basis_article: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signed_by_employee_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("employees.employee_id", ondelete="SET NULL"),
        nullable=True,
    )
    signed_by_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signed_by_position: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    executor_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    basis_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    void_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
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


class PersonnelOrderItem(Base):
    """Single numbered clause within a personnel order."""

    __tablename__ = "personnel_order_items"
    __table_args__ = (
        UniqueConstraint("order_id", "item_number", name="uq_personnel_order_items_order_item_number"),
        Index("ix_personnel_order_items_order_id", "order_id"),
        Index("ix_personnel_order_items_employee_id", "employee_id"),
        Index("ix_personnel_order_items_type_code", "item_type_code"),
    )

    item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("personnel_orders.order_id", ondelete="RESTRICT"),
        nullable=False,
    )
    item_number: Mapped[int] = mapped_column(Integer, nullable=False)
    item_type_code: Mapped[str] = mapped_column(Text, nullable=False)
    employee_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("employees.employee_id", ondelete="RESTRICT"),
        nullable=True,
    )
    effective_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    item_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{ITEM_STATUS_ACTIVE}'"),
    )
    void_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class PersonnelOrderLocalizedText(Base):
    """Rendered or edited order text for a locale (kk authoritative)."""

    __tablename__ = "personnel_order_localized_texts"
    __table_args__ = (
        UniqueConstraint("order_id", "locale", name="uq_personnel_order_localized_texts_order_locale"),
        Index("ix_personnel_order_localized_texts_order_id", "order_id"),
    )

    localized_text_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("personnel_orders.order_id", ondelete="RESTRICT"),
        nullable=False,
    )
    locale: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    preamble: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    render_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    is_authoritative: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
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


class PersonnelOrderAttachment(Base):
    """File reference for signed scan, basis document, or draft export."""

    __tablename__ = "personnel_order_attachments"
    __table_args__ = (Index("ix_personnel_order_attachments_order_id", "order_id"),)

    attachment_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("personnel_orders.order_id", ondelete="RESTRICT"),
        nullable=False,
    )
    attachment_kind: Mapped[str] = mapped_column(Text, nullable=False)
    storage_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text(f"'{STORAGE_TYPE_LOCAL_SHARE}'"),
    )
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    locale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class PersonnelOrderPrint(Base):
    """Generated printable snapshot (PDF/DOCX metadata; generation out of MVP scope)."""

    __tablename__ = "personnel_order_prints"
    __table_args__ = (Index("ix_personnel_order_prints_order_id", "order_id"),)

    print_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("personnel_orders.order_id", ondelete="RESTRICT"),
        nullable=False,
    )
    locale: Mapped[str] = mapped_column(Text, nullable=False)
    format: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_signed_copy: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
    render_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    generated_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
