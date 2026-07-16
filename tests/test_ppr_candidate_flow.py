"""Tests for PPR applicant roster and intended employment."""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.ppr.domain.models import HR_RELATIONSHIP_CANDIDATE, HR_RELATIONSHIP_EMPLOYED
from app.services.ppr_candidate_service import (
    list_ppr_applicants,
    load_hire_defaults,
    save_intended_employment,
    sync_hr_context_after_hire,
    update_hr_relationship_context_tx,
)
from tests.conftest import get_columns, insert_returning_id, table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_employee, insert_person, ppr_db_available, require_ppr_schema


pytestmark = pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL unavailable")


@pytest.fixture(scope="module", autouse=True)
def _require_schema() -> None:
    require_ppr_schema()


def _ensure_candidate_envelope(conn, person_id: int) -> None:
    conn.execute(
        text(
            """
            INSERT INTO public.personnel_record_metadata (
                person_id, ppr_lifecycle_state, hr_relationship_context, version
            )
            VALUES (:person_id, 'CREATED', :ctx, 1)
            ON CONFLICT (person_id) DO UPDATE
            SET hr_relationship_context = EXCLUDED.hr_relationship_context,
                updated_at = now()
            """
        ),
        {"person_id": person_id, "ctx": HR_RELATIONSHIP_CANDIDATE},
    )


def test_list_ppr_applicants_and_hire_defaults() -> None:
    suffix = uuid4().hex[:8]
    person_ids: list[int] = []
    employee_ids: list[int] = []

    try:
        with engine.begin() as conn:
            person_id = insert_person(conn, full_name=f"Applicant Test {suffix}")
            person_ids.append(person_id)
            cols = get_columns(conn, "persons")
            if "iin" in cols:
                digits = "".join(ch for ch in suffix if ch.isdigit())
                iin = (f"9{digits}").ljust(12, "0")[:12]
                conn.execute(
                    text("UPDATE public.persons SET iin = :iin WHERE person_id = :person_id"),
                    {"person_id": person_id, "iin": iin},
                )
            if "birth_date" in cols:
                conn.execute(
                    text("UPDATE public.persons SET birth_date = :d WHERE person_id = :person_id"),
                    {"person_id": person_id, "d": date(1992, 3, 3)},
                )

            _ensure_candidate_envelope(conn, person_id)

        with engine.begin() as conn:
            unit = conn.execute(
                text("SELECT unit_id FROM public.org_units ORDER BY unit_id LIMIT 1")
            ).mappings().first()
            pos = conn.execute(
                text("SELECT position_id FROM public.positions ORDER BY position_id LIMIT 1")
            ).mappings().first()
            assert unit and pos
            save_intended_employment(
                conn,
                person_id=person_id,
                org_group_id=None,
                org_unit_id=int(unit["unit_id"]),
                position_id=int(pos["position_id"]),
                employment_rate=0.75,
            )

            items, total = list_ppr_applicants(conn, q=suffix)
            assert total >= 1
            assert any(int(row["person_id"]) == person_id for row in items)

            defaults = load_hire_defaults(conn, person_id=person_id)
            assert defaults is not None
            assert defaults["org_unit_id"] == int(unit["unit_id"])
            assert defaults["position_id"] == int(pos["position_id"])
            assert defaults["employment_rate"] == 0.75
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)


def test_sync_hr_context_after_hire() -> None:
    suffix = uuid4().hex[:8]
    person_ids: list[int] = []
    employee_ids: list[int] = []

    try:
        with engine.begin() as conn:
            person_id = insert_person(conn, full_name=f"Hire Sync {suffix}")
            person_ids.append(person_id)
            _ensure_candidate_envelope(conn, person_id)

        with engine.begin() as conn:
            employee_id = insert_employee(conn, full_name=f"Hire Sync {suffix}", person_id=person_id)
            employee_ids.append(employee_id)
            changed = sync_hr_context_after_hire(conn, employee_id=employee_id)
            assert changed is True
            row = conn.execute(
                text(
                    "SELECT hr_relationship_context FROM public.personnel_record_metadata WHERE person_id = :pid"
                ),
                {"pid": person_id},
            ).mappings().one()
            assert row["hr_relationship_context"] == HR_RELATIONSHIP_EMPLOYED
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)
