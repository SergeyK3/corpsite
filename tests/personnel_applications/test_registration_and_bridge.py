# tests/personnel_applications/test_registration_and_bridge.py
"""Registration service, repository, envelope projection, and roster transition tests."""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.personnel_applications.application.envelope_projection import sync_envelope_intended_projection
from app.personnel_applications.application.registration_service import (
    build_card_href,
    register_personnel_application,
)
from app.personnel_applications.domain.errors import (
    ActiveEmployeeBlocksRegistrationError,
    VacancyCheckGateError,
)
from app.personnel_applications.domain.status import VACANCY_CHECK_CONFIRMED_VISUALLY
from app.ppr.domain.models import HR_RELATIONSHIP_CANDIDATE, HR_RELATIONSHIP_EMPLOYED, HR_RELATIONSHIP_FORMER_EMPLOYEE
from app.services.ppr_candidate_service import list_ppr_applicants
from tests.personnel_applications.conftest import (
    insert_person_with_iin,
    load_envelope_intended,
    materialize_envelope,
    require_personnel_applications_schema,
)
from tests.ppr.conftest import cleanup_person_graph, insert_employee, ppr_db_available


def _unique_iin(prefix: str = "9") -> str:
    suffix = uuid4().int % 10_000_000_000
    return f"{prefix}{suffix:011d}"[:12]


def _seed_user_id(conn) -> int:
    row = conn.execute(text("SELECT user_id FROM public.users LIMIT 1")).mappings().first()
    assert row is not None
    return int(row["user_id"])


def _optional_org_unit_id(conn) -> int | None:
    row = conn.execute(text("SELECT unit_id FROM public.org_units LIMIT 1")).mappings().first()
    if row is None:
        return None
    return int(row["unit_id"])


@pytest.fixture
def pa_env(pa_db_available):
    require_personnel_applications_schema()
    yield


def test_new_person_registration_creates_application_and_projects(pa_env) -> None:
    iin = _unique_iin("1")
    person_ids: list[int] = []
    with engine.begin() as conn:
        user_id = _seed_user_id(conn)
        org_unit_id = _optional_org_unit_id(conn)
        result = register_personnel_application(
            conn,
            iin_raw=iin,
            full_name="Новый претендент Тест",
            birth_date=date(1995, 5, 15),
            application_received_at=date(2026, 7, 17),
            vacancy_check_status=VACANCY_CHECK_CONFIRMED_VISUALLY,
            vacancy_checked_at=None,
            vacancy_checked_by_user_id=None,
            intended_org_group_id=None,
            intended_org_unit_id=org_unit_id,
            intended_position_id=None,
            intended_employment_rate=1.0 if org_unit_id is not None else None,
            intended_vacancy_text="Терапевт",
            contact_mobile_phone="+77001112233",
            contact_email="applicant@example.com",
            hr_note="test",
            idempotency_key=None,
            registered_by_user_id=user_id,
            actor_id=f"user:{user_id}",
        )
        person_ids.append(result.person_id)
        assert result.action == "created"
        assert result.card_href == build_card_href(result.person_id)
        env = load_envelope_intended(conn, result.person_id)
        if org_unit_id is not None:
            assert env["intended_org_unit_id"] == org_unit_id
            assert env["intended_employment_rate"] is not None
        row = conn.execute(
            text(
                """
                SELECT hr_relationship_context
                FROM public.personnel_record_metadata
                WHERE person_id = :person_id
                """
            ),
            {"person_id": result.person_id},
        ).mappings().one()
        assert row["hr_relationship_context"] == HR_RELATIONSHIP_CANDIDATE
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_existing_person_reuse_without_new_person_row(pa_env) -> None:
    iin = _unique_iin("2")
    person_ids: list[int] = []
    with engine.begin() as conn:
        user_id = _seed_user_id(conn)
        org_unit_id = _optional_org_unit_id(conn)
        person_id = insert_person_with_iin(conn, full_name="Существующий Person", iin=iin)
        person_ids.append(person_id)
        materialize_envelope(conn, person_id, hr_context=HR_RELATIONSHIP_CANDIDATE)
        result = register_personnel_application(
            conn,
            iin_raw=iin,
            full_name=None,
            birth_date=None,
            application_received_at=date(2026, 7, 17),
            vacancy_check_status=VACANCY_CHECK_CONFIRMED_VISUALLY,
            vacancy_checked_at=None,
            vacancy_checked_by_user_id=None,
            intended_org_group_id=None,
            intended_org_unit_id=org_unit_id,
            intended_position_id=None,
            intended_employment_rate=None,
            intended_vacancy_text=None,
            contact_mobile_phone=None,
            contact_email=None,
            hr_note=None,
            idempotency_key=None,
            registered_by_user_id=user_id,
            actor_id=f"user:{user_id}",
        )
        assert result.person_id == person_id
        assert result.action == "created"
        count = conn.execute(
            text("SELECT COUNT(*) FROM public.persons WHERE iin = :iin"),
            {"iin": iin},
        ).scalar_one()
        assert int(count) == 1
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_former_employee_reuse_does_not_switch_context(pa_env) -> None:
    iin = _unique_iin("3")
    person_ids: list[int] = []
    employee_ids: list[int] = []
    with engine.begin() as conn:
        user_id = _seed_user_id(conn)
        org_unit_id = _optional_org_unit_id(conn)
        person_id = insert_person_with_iin(conn, full_name="Бывший сотрудник", iin=iin)
        person_ids.append(person_id)
        employee_ids.append(
            insert_employee(conn, full_name="Бывший сотрудник", person_id=person_id, is_active=False)
        )
        materialize_envelope(conn, person_id, hr_context=HR_RELATIONSHIP_FORMER_EMPLOYEE)
        register_personnel_application(
            conn,
            iin_raw=iin,
            full_name=None,
            birth_date=None,
            application_received_at=date(2026, 7, 17),
            vacancy_check_status=VACANCY_CHECK_CONFIRMED_VISUALLY,
            vacancy_checked_at=None,
            vacancy_checked_by_user_id=None,
            intended_org_group_id=None,
            intended_org_unit_id=org_unit_id,
            intended_position_id=None,
            intended_employment_rate=None,
            intended_vacancy_text=None,
            contact_mobile_phone=None,
            contact_email=None,
            hr_note=None,
            idempotency_key=None,
            registered_by_user_id=user_id,
            actor_id=f"user:{user_id}",
        )
        ctx = conn.execute(
            text(
                "SELECT hr_relationship_context FROM public.personnel_record_metadata WHERE person_id = :pid"
            ),
            {"pid": person_id},
        ).scalar_one()
        assert ctx == HR_RELATIONSHIP_FORMER_EMPLOYEE
        env = load_envelope_intended(conn, person_id)
        if org_unit_id is not None:
            assert env["intended_org_unit_id"] == org_unit_id
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)


def test_active_employee_blocks_registration(pa_env) -> None:
    iin = _unique_iin("4")
    person_ids: list[int] = []
    employee_ids: list[int] = []
    with engine.begin() as conn:
        user_id = _seed_user_id(conn)
        person_id = insert_person_with_iin(conn, full_name="Active Employee Block", iin=iin)
        person_ids.append(person_id)
        employee_ids.append(
            insert_employee(conn, full_name="Active Employee Block", person_id=person_id, is_active=True)
        )
        materialize_envelope(conn, person_id, hr_context=HR_RELATIONSHIP_EMPLOYED)
        with pytest.raises(ActiveEmployeeBlocksRegistrationError):
            register_personnel_application(
                conn,
                iin_raw=iin,
                full_name=None,
                birth_date=None,
                application_received_at=date(2026, 7, 17),
                vacancy_check_status=VACANCY_CHECK_CONFIRMED_VISUALLY,
                vacancy_checked_at=None,
                vacancy_checked_by_user_id=None,
                intended_org_group_id=None,
                intended_org_unit_id=None,
                intended_position_id=None,
                intended_employment_rate=None,
                intended_vacancy_text=None,
                contact_mobile_phone=None,
                contact_email=None,
                hr_note=None,
                idempotency_key=None,
                registered_by_user_id=user_id,
                actor_id=f"user:{user_id}",
            )
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)


def test_opened_existing_when_active_application_exists(pa_env) -> None:
    iin = _unique_iin("5")
    person_ids: list[int] = []
    with engine.begin() as conn:
        user_id = _seed_user_id(conn)
        org_unit_id = _optional_org_unit_id(conn)
        person_id = insert_person_with_iin(conn, full_name="Duplicate Active", iin=iin)
        person_ids.append(person_id)
        materialize_envelope(conn, person_id)
        first = register_personnel_application(
            conn,
            iin_raw=iin,
            full_name=None,
            birth_date=None,
            application_received_at=date(2026, 7, 17),
            vacancy_check_status=VACANCY_CHECK_CONFIRMED_VISUALLY,
            vacancy_checked_at=None,
            vacancy_checked_by_user_id=None,
            intended_org_group_id=None,
            intended_org_unit_id=org_unit_id,
            intended_position_id=None,
            intended_employment_rate=None,
            intended_vacancy_text=None,
            contact_mobile_phone=None,
            contact_email=None,
            hr_note=None,
            idempotency_key=None,
            registered_by_user_id=user_id,
            actor_id=f"user:{user_id}",
        )
        second = register_personnel_application(
            conn,
            iin_raw=iin,
            full_name=None,
            birth_date=None,
            application_received_at=date(2026, 7, 18),
            vacancy_check_status=VACANCY_CHECK_CONFIRMED_VISUALLY,
            vacancy_checked_at=None,
            vacancy_checked_by_user_id=None,
            intended_org_group_id=None,
            intended_org_unit_id=org_unit_id,
            intended_position_id=None,
            intended_employment_rate=None,
            intended_vacancy_text=None,
            contact_mobile_phone=None,
            contact_email=None,
            hr_note=None,
            idempotency_key=None,
            registered_by_user_id=user_id,
            actor_id=f"user:{user_id}",
        )
        assert second.action == "opened_existing"
        assert second.application_id == first.application_id
        count = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.personnel_applications
                WHERE person_id = :person_id AND status NOT IN (
                    'completed', 'withdrawn', 'cancelled', 'resolution_rejected'
                )
                """
            ),
            {"person_id": person_id},
        ).scalar_one()
        assert int(count) == 1
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_idempotency_key_replay(pa_env) -> None:
    iin = _unique_iin("6")
    idem = f"test-idem-{uuid4().hex}"
    person_ids: list[int] = []
    with engine.begin() as conn:
        user_id = _seed_user_id(conn)
        kwargs = dict(
            iin_raw=iin,
            full_name="Idempotent Person",
            birth_date=None,
            application_received_at=date(2026, 7, 17),
            vacancy_check_status=VACANCY_CHECK_CONFIRMED_VISUALLY,
            vacancy_checked_at=None,
            vacancy_checked_by_user_id=None,
            intended_org_group_id=None,
            intended_org_unit_id=None,
            intended_position_id=None,
            intended_employment_rate=None,
            intended_vacancy_text=None,
            contact_mobile_phone=None,
            contact_email=None,
            hr_note=None,
            idempotency_key=idem,
            registered_by_user_id=user_id,
            actor_id=f"user:{user_id}",
        )
        first = register_personnel_application(conn, **kwargs)
        second = register_personnel_application(conn, **kwargs)
        person_ids.append(first.person_id)
        assert first.application_id == second.application_id
        assert second.action == "opened_existing"
        count = conn.execute(
            text("SELECT COUNT(*) FROM public.personnel_applications WHERE idempotency_key = :k"),
            {"k": idem},
        ).scalar_one()
        assert int(count) == 1
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_vacancy_check_gate(pa_env) -> None:
    iin = _unique_iin("7")
    with engine.begin() as conn:
        user_id = _seed_user_id(conn)
        with pytest.raises(VacancyCheckGateError):
            register_personnel_application(
                conn,
                iin_raw=iin,
                full_name="Gate Test",
                birth_date=None,
                application_received_at=date(2026, 7, 17),
                vacancy_check_status="pending",
                vacancy_checked_at=None,
                vacancy_checked_by_user_id=None,
                intended_org_group_id=None,
                intended_org_unit_id=None,
                intended_position_id=None,
                intended_employment_rate=None,
                intended_vacancy_text=None,
                contact_mobile_phone=None,
                contact_email=None,
                hr_note=None,
                idempotency_key=None,
                registered_by_user_id=user_id,
                actor_id=f"user:{user_id}",
            )


def test_envelope_projection_clears_when_no_active_application(pa_env) -> None:
    iin = _unique_iin("8")
    person_ids: list[int] = []
    with engine.begin() as conn:
        user_id = _seed_user_id(conn)
        org_unit_id = _optional_org_unit_id(conn)
        person_id = insert_person_with_iin(conn, full_name="Clear Projection", iin=iin)
        person_ids.append(person_id)
        materialize_envelope(conn, person_id)
        if org_unit_id is not None:
            conn.execute(
                text(
                    """
                    UPDATE public.personnel_record_metadata
                    SET intended_org_unit_id = :org_unit_id
                    WHERE person_id = :person_id
                    """
                ),
                {"person_id": person_id, "org_unit_id": org_unit_id},
            )
        sync_envelope_intended_projection(conn, person_id)
        env = load_envelope_intended(conn, person_id)
        assert env["intended_org_unit_id"] is None
        result = register_personnel_application(
            conn,
            iin_raw=iin,
            full_name=None,
            birth_date=None,
            application_received_at=date(2026, 7, 17),
            vacancy_check_status=VACANCY_CHECK_CONFIRMED_VISUALLY,
            vacancy_checked_at=None,
            vacancy_checked_by_user_id=None,
            intended_org_group_id=None,
            intended_org_unit_id=org_unit_id,
            intended_position_id=None,
            intended_employment_rate=None,
            intended_vacancy_text=None,
            contact_mobile_phone=None,
            contact_email=None,
            hr_note=None,
            idempotency_key=None,
            registered_by_user_id=user_id,
            actor_id=f"user:{user_id}",
        )
        env = load_envelope_intended(conn, person_id)
        if org_unit_id is not None:
            assert env["intended_org_unit_id"] == org_unit_id
        conn.execute(
            text(
                """
                UPDATE public.personnel_applications
                SET status = 'withdrawn'
                WHERE application_id = :application_id
                """
            ),
            {"application_id": result.application_id},
        )
        sync_envelope_intended_projection(conn, person_id)
        env = load_envelope_intended(conn, person_id)
        assert env["intended_org_unit_id"] is None
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_roster_includes_active_application_and_legacy_candidate(pa_env) -> None:
    app_iin = _unique_iin("8")
    legacy_iin = _unique_iin("9")
    person_ids: list[int] = []
    with engine.begin() as conn:
        user_id = _seed_user_id(conn)
        org_unit_id = _optional_org_unit_id(conn)
        app_person = insert_person_with_iin(conn, full_name="Roster App Person", iin=app_iin)
        legacy_person = insert_person_with_iin(conn, full_name="Roster Legacy Person", iin=legacy_iin)
        person_ids.extend([app_person, legacy_person])
        materialize_envelope(conn, app_person, hr_context=HR_RELATIONSHIP_FORMER_EMPLOYEE)
        materialize_envelope(conn, legacy_person, hr_context=HR_RELATIONSHIP_CANDIDATE)
        register_personnel_application(
            conn,
            iin_raw=app_iin,
            full_name=None,
            birth_date=None,
            application_received_at=date(2026, 7, 17),
            vacancy_check_status=VACANCY_CHECK_CONFIRMED_VISUALLY,
            vacancy_checked_at=None,
            vacancy_checked_by_user_id=None,
            intended_org_group_id=None,
            intended_org_unit_id=org_unit_id,
            intended_position_id=None,
            intended_employment_rate=None,
            intended_vacancy_text=None,
            contact_mobile_phone=None,
            contact_email=None,
            hr_note=None,
            idempotency_key=None,
            registered_by_user_id=user_id,
            actor_id=f"user:{user_id}",
        )
        items, total = list_ppr_applicants(conn, limit=500)
        roster_person_ids = {int(item["person_id"]) for item in items}
        assert app_person in roster_person_ids
        assert legacy_person in roster_person_ids
        assert total >= 2
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])
