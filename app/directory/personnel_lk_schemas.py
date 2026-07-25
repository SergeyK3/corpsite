"""Pydantic schemas for person-centric LK registry API."""
from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.personnel_lk.application.registry_query_service import PersonnelLkRegistryRow


class PersonnelLkRegistryItemOut(BaseModel):
    person_id: int
    record_kind: Literal["employee", "applicant"]
    id: int | None = Field(
        default=None,
        description="Employee id when record_kind=employee; null for applicants.",
    )
    employee_id: int | None = None
    active_application_id: int | None = None
    fio: str | None = None
    iin: str | None = None
    rate: Decimal | float | None = None
    status: str
    application_status: str | None = None


class PersonnelLkRegistryListOut(BaseModel):
    items: list[PersonnelLkRegistryItemOut]
    total: int
    limit: int
    offset: int


def registry_row_to_out(row: PersonnelLkRegistryRow) -> PersonnelLkRegistryItemOut:
    return PersonnelLkRegistryItemOut(
        person_id=row.person_id,
        record_kind=row.record_kind,  # type: ignore[arg-type]
        id=row.employee_id,
        employee_id=row.employee_id,
        active_application_id=row.active_application_id,
        fio=row.fio,
        iin=row.iin,
        rate=row.rate,
        status=row.status,
        application_status=row.application_status,
    )
