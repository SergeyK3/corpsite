"""SQLAlchemy repository for Person-level Telegram identity (ADR-TG-001)."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection, RowMapping
from sqlalchemy.exc import IntegrityError

from app.db.models.person_telegram import (
    BOT_CODE_INTAKE_PPR,
    BOT_CODE_OPERATIONAL_TASKS,
    PERSON_TELEGRAM_BOT_CODES,
    PersonTelegramBinding,
    PersonTelegramBotActivation,
)
from app.personnel_intake.domain.errors import PersonnelIntakeConflictError, PersonnelIntakeNotFoundError
from app.personnel_intake.domain.models import (
    PersonTelegramBindingSnapshot,
    PersonTelegramBotActivationSnapshot,
)

_BINDING_COLUMNS = (
    PersonTelegramBinding.binding_id,
    PersonTelegramBinding.person_id,
    PersonTelegramBinding.telegram_user_id,
    PersonTelegramBinding.telegram_username,
    PersonTelegramBinding.revoked_at,
    PersonTelegramBinding.created_at,
    PersonTelegramBinding.updated_at,
)

_ACTIVATION_COLUMNS = (
    PersonTelegramBotActivation.activation_id,
    PersonTelegramBotActivation.person_id,
    PersonTelegramBotActivation.bot_code,
    PersonTelegramBotActivation.first_activated_at,
    PersonTelegramBotActivation.last_activated_at,
)


def _binding_from_row(row: RowMapping | dict[str, Any]) -> PersonTelegramBindingSnapshot:
    username = row.get("telegram_username")
    return PersonTelegramBindingSnapshot(
        binding_id=int(row["binding_id"]),
        person_id=int(row["person_id"]),
        telegram_user_id=int(row["telegram_user_id"]),
        telegram_username=str(username).strip() if username is not None else None,
        revoked_at=row.get("revoked_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _activation_from_row(row: RowMapping | dict[str, Any]) -> PersonTelegramBotActivationSnapshot:
    return PersonTelegramBotActivationSnapshot(
        activation_id=int(row["activation_id"]),
        person_id=int(row["person_id"]),
        bot_code=str(row["bot_code"]),
        first_activated_at=row["first_activated_at"],
        last_activated_at=row["last_activated_at"],
    )


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SqlAlchemyPersonTelegramRepository:
    """Persistence adapter — caller owns transaction and commit."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def get_active_by_person_id(self, person_id: int) -> PersonTelegramBindingSnapshot | None:
        stmt = (
            select(*_BINDING_COLUMNS)
            .where(
                PersonTelegramBinding.person_id == int(person_id),
                PersonTelegramBinding.revoked_at.is_(None),
            )
            .limit(1)
        )
        row = self._conn.execute(stmt).mappings().one_or_none()
        if row is None:
            return None
        return _binding_from_row(row)

    def get_active_by_telegram_user_id(
        self,
        telegram_user_id: int,
    ) -> PersonTelegramBindingSnapshot | None:
        stmt = (
            select(*_BINDING_COLUMNS)
            .where(
                PersonTelegramBinding.telegram_user_id == int(telegram_user_id),
                PersonTelegramBinding.revoked_at.is_(None),
            )
            .limit(1)
        )
        row = self._conn.execute(stmt).mappings().one_or_none()
        if row is None:
            return None
        return _binding_from_row(row)

    def create_binding(
        self,
        person_id: int,
        telegram_user_id: int,
        telegram_username: str | None,
    ) -> PersonTelegramBindingSnapshot:
        person_id = int(person_id)
        telegram_user_id = int(telegram_user_id)
        normalized_username = str(telegram_username).strip() if telegram_username is not None else None
        if normalized_username == "":
            normalized_username = None

        if self.get_active_by_person_id(person_id) is not None:
            raise PersonnelIntakeConflictError(
                "Active Telegram binding already exists for this person.",
                code="ACTIVE_PERSON_TELEGRAM_BINDING_EXISTS",
            )
        if self.get_active_by_telegram_user_id(telegram_user_id) is not None:
            raise PersonnelIntakeConflictError(
                "Active Telegram binding already exists for this Telegram user.",
                code="ACTIVE_TELEGRAM_USER_BINDING_EXISTS",
            )

        stmt = (
            pg_insert(PersonTelegramBinding)
            .values(
                person_id=person_id,
                telegram_user_id=telegram_user_id,
                telegram_username=normalized_username,
            )
            .returning(*_BINDING_COLUMNS)
        )
        try:
            row = self._conn.execute(stmt).mappings().one()
        except IntegrityError as exc:
            raise PersonnelIntakeConflictError(
                "Active Telegram binding already exists.",
                code="ACTIVE_TELEGRAM_BINDING_EXISTS",
            ) from exc
        return _binding_from_row(row)

    def revoke_binding(self, binding_id: int) -> PersonTelegramBindingSnapshot:
        now = _utcnow()
        stmt = (
            update(PersonTelegramBinding)
            .where(
                PersonTelegramBinding.binding_id == int(binding_id),
                PersonTelegramBinding.revoked_at.is_(None),
            )
            .values(revoked_at=now, updated_at=now)
            .returning(*_BINDING_COLUMNS)
        )
        row = self._conn.execute(stmt).mappings().one_or_none()
        if row is None:
            raise PersonnelIntakeNotFoundError(
                f"Active Telegram binding {binding_id} not found.",
            )
        return _binding_from_row(row)

    def upsert_activation(
        self,
        person_id: int,
        bot_code: str,
    ) -> PersonTelegramBotActivationSnapshot:
        person_id = int(person_id)
        normalized_bot_code = str(bot_code).strip()
        if normalized_bot_code not in PERSON_TELEGRAM_BOT_CODES:
            raise ValueError(
                f"Unsupported bot_code {bot_code!r}; expected one of {PERSON_TELEGRAM_BOT_CODES}.",
            )

        now = _utcnow()
        stmt = (
            pg_insert(PersonTelegramBotActivation)
            .values(
                person_id=person_id,
                bot_code=normalized_bot_code,
                first_activated_at=now,
                last_activated_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_person_telegram_bot_activations_person_bot",
                set_={"last_activated_at": now},
            )
            .returning(*_ACTIVATION_COLUMNS)
        )
        row = self._conn.execute(stmt).mappings().one()
        return _activation_from_row(row)


__all__ = [
    "BOT_CODE_INTAKE_PPR",
    "BOT_CODE_OPERATIONAL_TASKS",
    "PERSON_TELEGRAM_BOT_CODES",
    "SqlAlchemyPersonTelegramRepository",
]
