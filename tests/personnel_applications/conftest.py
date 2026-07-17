# tests/personnel_applications/conftest.py
"""Shared fixtures for Personnel Application tests."""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from datetime import UTC, datetime
from sqlalchemy import text

from app.db.engine import engine
from app.ppr.application.authorization import AllowAllAuthorizationPort
from app.ppr.application.command_models import (
    COMMAND_TYPE_MATERIALIZE_PPR,
    MaterializePprPayload,
    PprCommandEnvelope,
)
from app.ppr.application.lifecycle_service import PprLifecycleApplicationService
from app.ppr.domain.models import HR_RELATIONSHIP_CANDIDATE, HR_RELATIONSHIP_FORMER_EMPLOYEE
from tests.conftest import get_columns, insert_returning_id, table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_employee, insert_person, ppr_db_available


def require_personnel_applications_schema() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_applications"):
            pytest.skip("personnel_applications missing — run: alembic upgrade head")


def insert_person_with_iin(
    conn,
    *,
    full_name: str,
    iin: str,
    birth_date: date | None = None,
    prefix: str = "pa",
) -> int:
    suffix = uuid4().hex[:12]
    cols = get_columns(conn, "persons")
    values: dict = {
        "full_name": full_name,
        "iin": iin,
        "match_key": f"{prefix}:{suffix}",
        "person_status": "active",
        "source": "manual",
    }
    if birth_date is not None and "birth_date" in cols:
        values["birth_date"] = birth_date
    return insert_returning_id(conn, table="persons", id_col="person_id", values=values)


def materialize_envelope(conn, person_id: int, *, hr_context: str = HR_RELATIONSHIP_CANDIDATE) -> None:
    svc = PprLifecycleApplicationService(authorization=AllowAllAuthorizationPort())
    from app.ppr.infrastructure.application_unit_of_work import PprApplicationUnitOfWork

    uow = PprApplicationUnitOfWork().bind_participating(conn)
    svc.materialize_ppr_participating(
        uow,
        PprCommandEnvelope(
            command_id=f"test:materialize:{person_id}:{uuid4().hex[:8]}",
            command_type=COMMAND_TYPE_MATERIALIZE_PPR,
            actor_id="test",
            requested_at=datetime.now(UTC),
            person_id=person_id,
            payload=MaterializePprPayload(hr_relationship_context=hr_context),
        ),
    )


def load_envelope_intended(conn, person_id: int) -> dict:
    row = conn.execute(
        text(
            """
            SELECT intended_org_group_id, intended_org_unit_id,
                   intended_position_id, intended_employment_rate
            FROM public.personnel_record_metadata
            WHERE person_id = :person_id
            """
        ),
        {"person_id": person_id},
    ).mappings().one()
    return dict(row)


@pytest.fixture
def pa_db_available():
    if not ppr_db_available():
        pytest.skip("PostgreSQL not available")
    require_personnel_applications_schema()
