"""ORM models for Person-level Telegram identity (ADR-TG-001)."""
from __future__ import annotations

from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, ForeignKey, Index, Text, UniqueConstraint, text

from app.db.base import Base

BOT_CODE_INTAKE_PPR = "intake_ppr"
BOT_CODE_OPERATIONAL_TASKS = "operational_tasks"
PERSON_TELEGRAM_BOT_CODES = (BOT_CODE_INTAKE_PPR, BOT_CODE_OPERATIONAL_TASKS)


class PersonTelegramBinding(Base):
    __tablename__ = "person_telegram_bindings"
    __table_args__ = (
        CheckConstraint(
            "telegram_user_id > 0",
            name="chk_person_telegram_bindings_telegram_user_id_positive",
        ),
        Index(
            "uq_person_telegram_bindings_telegram_user_id_active",
            "telegram_user_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index(
            "uq_person_telegram_bindings_person_id_active",
            "person_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index(
            "ix_person_telegram_bindings_person_id_history",
            "person_id",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
        {"schema": "public"},
    )

    binding_id = Column(BigInteger, primary_key=True, autoincrement=True)
    person_id = Column(
        BigInteger,
        ForeignKey("public.persons.person_id", ondelete="RESTRICT"),
        nullable=False,
    )
    telegram_user_id = Column(BigInteger, nullable=False)
    telegram_username = Column(Text, nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class PersonTelegramBotActivation(Base):
    __tablename__ = "person_telegram_bot_activations"
    __table_args__ = (
        UniqueConstraint(
            "person_id",
            "bot_code",
            name="uq_person_telegram_bot_activations_person_bot",
        ),
        CheckConstraint(
            "bot_code IN ('intake_ppr', 'operational_tasks')",
            name="chk_person_telegram_bot_activations_bot_code",
        ),
        {"schema": "public"},
    )

    activation_id = Column(BigInteger, primary_key=True, autoincrement=True)
    person_id = Column(
        BigInteger,
        ForeignKey("public.persons.person_id", ondelete="RESTRICT"),
        nullable=False,
    )
    bot_code = Column(Text, nullable=False)
    first_activated_at = Column(DateTime(timezone=True), nullable=False)
    last_activated_at = Column(DateTime(timezone=True), nullable=False)
