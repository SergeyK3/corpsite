"""SQLAlchemy adapter for PersonRepository (read-only general section projection)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from app.ppr.domain.errors import PprPersonNotFoundError
from app.ppr.domain.person_models import PersonGeneralReadSnapshot

_READ_COLUMNS = (
    "person_id",
    "full_name",
    "last_name",
    "first_name",
    "middle_name",
    "birth_date",
    "iin",
    "created_at",
    "updated_at",
)


def _mapping_to_snapshot(row: RowMapping | dict[str, Any]) -> PersonGeneralReadSnapshot:
    birth = row.get("birth_date")
    return PersonGeneralReadSnapshot(
        person_id=int(row["person_id"]),
        full_name=str(row["full_name"]),
        last_name=str(row["last_name"]) if row.get("last_name") is not None else None,
        first_name=str(row["first_name"]) if row.get("first_name") is not None else None,
        middle_name=str(row["middle_name"]) if row.get("middle_name") is not None else None,
        birth_date=birth if isinstance(birth, date) else None,
        iin=str(row["iin"]) if row.get("iin") is not None else None,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class SqlAlchemyPersonRepository:
    """Read-only — Person BC identity fields and PPR cadre writes deferred to R5."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def load_general_read_snapshot(self, person_id: int) -> PersonGeneralReadSnapshot:
        stmt = text(
            """
            SELECT person_id, full_name, last_name, first_name, middle_name,
                   birth_date, iin, created_at, updated_at
            FROM public.persons
            WHERE person_id = :person_id
            """
        )
        row = self._conn.execute(stmt, {"person_id": person_id}).mappings().one_or_none()
        if row is None:
            raise PprPersonNotFoundError(f"Person not found: person_id={person_id}")
        return _mapping_to_snapshot(row)
