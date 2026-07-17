"""SQLAlchemy repository for personnel_applications."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection, RowMapping
from sqlalchemy.exc import IntegrityError

from app.db.models.personnel_applications import PersonnelApplication
from app.personnel_applications.domain.errors import (
    PersonnelApplicationDuplicateActiveError,
    PersonnelApplicationNotFoundError,
)
from app.personnel_applications.domain.models import (
    PersonnelApplicationCreatePayload,
    PersonnelApplicationSnapshot,
)
from app.personnel_applications.domain.status import (
    APPLICATION_STATUSES,
    is_active_application_status,
)

_ACTIVE_STATUS_FILTER = tuple(
    status for status in APPLICATION_STATUSES if is_active_application_status(status)
)

_SELECT_COLUMNS = (
    PersonnelApplication.application_id,
    PersonnelApplication.person_id,
    PersonnelApplication.status,
    PersonnelApplication.application_received_at,
    PersonnelApplication.application_source,
    PersonnelApplication.vacancy_check_status,
    PersonnelApplication.vacancy_checked_at,
    PersonnelApplication.vacancy_checked_by_user_id,
    PersonnelApplication.intended_org_group_id,
    PersonnelApplication.intended_org_unit_id,
    PersonnelApplication.intended_position_id,
    PersonnelApplication.intended_employment_rate,
    PersonnelApplication.intended_vacancy_text,
    PersonnelApplication.contact_mobile_phone,
    PersonnelApplication.contact_email,
    PersonnelApplication.director_resolution_status,
    PersonnelApplication.director_resolution_at,
    PersonnelApplication.director_resolution_by_user_id,
    PersonnelApplication.director_resolution_note,
    PersonnelApplication.personnel_order_id,
    PersonnelApplication.registered_at,
    PersonnelApplication.registered_by_user_id,
    PersonnelApplication.hr_note,
    PersonnelApplication.idempotency_key,
    PersonnelApplication.created_at,
    PersonnelApplication.updated_at,
)


def _mapping_to_snapshot(row: RowMapping | dict[str, Any]) -> PersonnelApplicationSnapshot:
    rate = row.get("intended_employment_rate")
    return PersonnelApplicationSnapshot(
        application_id=int(row["application_id"]),
        person_id=int(row["person_id"]),
        status=str(row["status"]),
        application_received_at=row["application_received_at"],
        application_source=str(row["application_source"]),
        vacancy_check_status=str(row["vacancy_check_status"]),
        vacancy_checked_at=row.get("vacancy_checked_at"),
        vacancy_checked_by_user_id=row.get("vacancy_checked_by_user_id"),
        intended_org_group_id=row.get("intended_org_group_id"),
        intended_org_unit_id=row.get("intended_org_unit_id"),
        intended_position_id=row.get("intended_position_id"),
        intended_employment_rate=Decimal(str(rate)) if rate is not None else None,
        intended_vacancy_text=row.get("intended_vacancy_text"),
        contact_mobile_phone=row.get("contact_mobile_phone"),
        contact_email=row.get("contact_email"),
        director_resolution_status=row.get("director_resolution_status"),
        director_resolution_at=row.get("director_resolution_at"),
        director_resolution_by_user_id=row.get("director_resolution_by_user_id"),
        director_resolution_note=row.get("director_resolution_note"),
        personnel_order_id=row.get("personnel_order_id"),
        registered_at=row["registered_at"],
        registered_by_user_id=int(row["registered_by_user_id"]),
        hr_note=row.get("hr_note"),
        idempotency_key=row.get("idempotency_key"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class SqlAlchemyPersonnelApplicationRepository:
    """Persistence adapter — caller owns transaction and commit."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def create(self, payload: PersonnelApplicationCreatePayload) -> PersonnelApplicationSnapshot:
        values = {
            "person_id": payload.person_id,
            "status": payload.status,
            "application_received_at": payload.application_received_at,
            "application_source": payload.application_source,
            "vacancy_check_status": payload.vacancy_check_status,
            "vacancy_checked_at": payload.vacancy_checked_at,
            "vacancy_checked_by_user_id": payload.vacancy_checked_by_user_id,
            "intended_org_group_id": payload.intended_org_group_id,
            "intended_org_unit_id": payload.intended_org_unit_id,
            "intended_position_id": payload.intended_position_id,
            "intended_employment_rate": payload.intended_employment_rate,
            "intended_vacancy_text": payload.intended_vacancy_text,
            "contact_mobile_phone": payload.contact_mobile_phone,
            "contact_email": payload.contact_email,
            "registered_by_user_id": payload.registered_by_user_id,
            "hr_note": payload.hr_note,
            "idempotency_key": payload.idempotency_key,
        }
        stmt = (
            pg_insert(PersonnelApplication)
            .values(**values)
            .returning(PersonnelApplication.application_id)
        )
        try:
            application_id = int(self._conn.execute(stmt).scalar_one())
        except IntegrityError as exc:
            active = self.get_active_by_person_id(payload.person_id)
            if active is not None:
                raise PersonnelApplicationDuplicateActiveError(
                    person_id=payload.person_id,
                    application_id=active.application_id,
                ) from exc
            if payload.idempotency_key:
                existing = self.get_by_idempotency_key(payload.idempotency_key)
                if existing is not None:
                    return existing
            raise
        loaded = self.get_by_id(application_id)
        assert loaded is not None
        return loaded

    def get_by_id(self, application_id: int) -> PersonnelApplicationSnapshot | None:
        stmt = select(*_SELECT_COLUMNS).where(
            PersonnelApplication.application_id == application_id
        )
        row = self._conn.execute(stmt).mappings().one_or_none()
        if row is None:
            return None
        return _mapping_to_snapshot(row)

    def require_by_id(self, application_id: int) -> PersonnelApplicationSnapshot:
        loaded = self.get_by_id(application_id)
        if loaded is None:
            raise PersonnelApplicationNotFoundError(
                f"Personnel application not found: application_id={application_id}"
            )
        return loaded

    def list_history_by_person_id(self, person_id: int) -> list[PersonnelApplicationSnapshot]:
        stmt = (
            select(*_SELECT_COLUMNS)
            .where(PersonnelApplication.person_id == person_id)
            .order_by(PersonnelApplication.created_at.desc(), PersonnelApplication.application_id.desc())
        )
        rows = self._conn.execute(stmt).mappings().all()
        return [_mapping_to_snapshot(row) for row in rows]

    def get_active_by_person_id(self, person_id: int) -> PersonnelApplicationSnapshot | None:
        stmt = (
            select(*_SELECT_COLUMNS)
            .where(
                PersonnelApplication.person_id == person_id,
                PersonnelApplication.status.in_(_ACTIVE_STATUS_FILTER),
            )
            .order_by(PersonnelApplication.created_at.desc(), PersonnelApplication.application_id.desc())
            .limit(1)
        )
        row = self._conn.execute(stmt).mappings().one_or_none()
        if row is None:
            return None
        snapshot = _mapping_to_snapshot(row)
        if not is_active_application_status(snapshot.status):
            return None
        return snapshot

    def has_active_application(self, person_id: int) -> bool:
        return self.get_active_by_person_id(person_id) is not None

    def get_by_idempotency_key(self, idempotency_key: str) -> PersonnelApplicationSnapshot | None:
        key = str(idempotency_key).strip()
        if not key:
            return None
        stmt = select(*_SELECT_COLUMNS).where(PersonnelApplication.idempotency_key == key)
        row = self._conn.execute(stmt).mappings().one_or_none()
        if row is None:
            return None
        return _mapping_to_snapshot(row)

    def person_has_any_application(self, person_id: int) -> bool:
        row = self._conn.execute(
            text(
                """
                SELECT 1
                FROM public.personnel_applications
                WHERE person_id = :person_id
                LIMIT 1
                """
            ),
            {"person_id": int(person_id)},
        ).first()
        return row is not None

    def update_application_fields(
        self,
        application_id: int,
        *,
        status: str | None = None,
        director_resolution_status: str | None = None,
        director_resolution_at: datetime | None = None,
        director_resolution_by_user_id: int | None = None,
        director_resolution_note: str | None = None,
        personnel_order_id: int | None = None,
        clear_director_resolution: bool = False,
        now: datetime | None = None,
    ) -> PersonnelApplicationSnapshot:
        from datetime import UTC, datetime as dt

        updated_at = now or dt.now(UTC)
        sets: list[str] = ["updated_at = :updated_at"]
        params: dict[str, object] = {
            "application_id": int(application_id),
            "updated_at": updated_at,
        }
        if status is not None:
            sets.append("status = :status")
            params["status"] = status
        if clear_director_resolution:
            sets.append("director_resolution_status = NULL")
            sets.append("director_resolution_at = NULL")
            sets.append("director_resolution_by_user_id = NULL")
            sets.append("director_resolution_note = NULL")
        else:
            if director_resolution_status is not None:
                sets.append("director_resolution_status = :director_resolution_status")
                params["director_resolution_status"] = director_resolution_status
            if director_resolution_at is not None:
                sets.append("director_resolution_at = :director_resolution_at")
                params["director_resolution_at"] = director_resolution_at
            if director_resolution_by_user_id is not None:
                sets.append("director_resolution_by_user_id = :director_resolution_by_user_id")
                params["director_resolution_by_user_id"] = director_resolution_by_user_id
            if director_resolution_note is not None:
                sets.append("director_resolution_note = :director_resolution_note")
                params["director_resolution_note"] = director_resolution_note
        if personnel_order_id is not None:
            sets.append("personnel_order_id = :personnel_order_id")
            params["personnel_order_id"] = int(personnel_order_id)

        self._conn.execute(
            text(
                f"""
                UPDATE public.personnel_applications
                SET {", ".join(sets)}
                WHERE application_id = :application_id
                """
            ),
            params,
        )
        return self.require_by_id(application_id)

    def get_by_personnel_order_id(self, order_id: int) -> PersonnelApplicationSnapshot | None:
        stmt = select(*_SELECT_COLUMNS).where(PersonnelApplication.personnel_order_id == int(order_id))
        row = self._conn.execute(stmt).mappings().one_or_none()
        if row is None:
            return None
        return _mapping_to_snapshot(row)
