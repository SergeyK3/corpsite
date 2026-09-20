"""PostgreSQL coverage for the HR-confirmed active-Employee Person-card flow."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.services.adr048_person_resolution_service import (
    Adr048PersonCandidate,
    Adr048PersonResolution,
)
import app.services.active_employee_person_card_service as active_card_service
from app.services.active_employee_person_card_service import (
    active_employee_person_card_preflight,
    create_active_employee_person_card_tx,
)
from app.services.adr065_person_link_service import PersonLinkError
from tests.conftest import auth_headers, table_exists
from tests.personnel_applications.conftest import insert_person_with_iin
from tests.personnel_lk.conftest import require_personnel_lk_schema, seed_user_id, unique_iin
from tests.ppr.conftest import insert_employee


@pytest.fixture
def active_employee_case(monkeypatch):
    require_personnel_lk_schema()
    with engine.begin() as conn:
        if any(not table_exists(conn, name) for name in ("employee_identities", "personnel_identity_link_operations")):
            pytest.skip("active-employee card workflow schema is not migrated")
        actor = seed_user_id(conn)
        unit_id = conn.execute(text("SELECT unit_id FROM org_units WHERE is_active IS TRUE ORDER BY unit_id LIMIT 1")).scalar_one()
        position_id = conn.execute(text("SELECT position_id FROM positions ORDER BY position_id LIMIT 1")).scalar_one()
        employee_id = insert_employee(conn, full_name=f"Active card employee {uuid4().hex[:12]}")
        iin = unique_iin("6")
        conn.execute(
            text("UPDATE employees SET org_unit_id=:unit_id, position_id=:position_id, employment_rate=1.0, "
                 "date_from=NULL, date_to=NULL, is_active=TRUE, operational_status='active' WHERE employee_id=:employee_id"),
            {"unit_id": unit_id, "position_id": position_id, "employee_id": employee_id},
        )
        conn.execute(
            text("INSERT INTO employee_identities(employee_id,identity_type,identity_value,is_primary,created_by) "
                 "VALUES (:employee_id,'IIN',:iin,TRUE,:actor)"),
            {"employee_id": employee_id, "iin": iin, "actor": actor},
        )
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(actor))
    return {"actor": int(actor), "employee_id": int(employee_id), "iin": iin}


def _preflight(case):
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            conn.exec_driver_sql("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            return active_employee_person_card_preflight(conn, employee_id=case["employee_id"])
        finally:
            tx.rollback()


def test_preflight_is_ready_without_assignment_intent(active_employee_case):
    result = _preflight(active_employee_case)
    assert result["ready"] is True
    assert result["blockers"] == []
    assert result["expected_precondition"]
    assert result["iin"] == {"present": True, "last4": active_employee_case["iin"][-4:]}
    assert result["person_candidates"] == []


def test_create_replay_audit_and_preserve_operational_assignment(active_employee_case):
    preflight = _preflight(active_employee_case)
    employee_id = active_employee_case["employee_id"]
    with engine.begin() as conn:
        before = dict(conn.execute(text("SELECT org_unit_id,position_id,employment_rate,date_from,date_to FROM employees WHERE employee_id=:employee_id"), {"employee_id": employee_id}).mappings().one())
        result = create_active_employee_person_card_tx(
            conn,
            employee_id=employee_id,
            expected_precondition=preflight["expected_precondition"],
            request_id=f"active-card-{uuid4()}",
            actor_user_id=active_employee_case["actor"],
            hr_confirmed=True,
        )
    assert result["decision"] == "CREATE"
    with engine.begin() as conn:
        replay = create_active_employee_person_card_tx(
            conn,
            employee_id=employee_id,
            expected_precondition=preflight["expected_precondition"],
            request_id=result["request_id"],
            actor_user_id=active_employee_case["actor"],
            hr_confirmed=True,
        )
        after = dict(conn.execute(text("SELECT person_id,org_unit_id,position_id,employment_rate,date_from,date_to FROM employees WHERE employee_id=:employee_id"), {"employee_id": employee_id}).mappings().one())
        audit = conn.execute(text("SELECT actor_user_id,employee_id,person_id,decision,normalized_record_ids::text FROM personnel_identity_link_operations WHERE request_id=:request_id"), {"request_id": result["request_id"]}).mappings().one()
        assignments = conn.execute(text("SELECT count(*) FROM person_assignments WHERE person_id=:person_id"), {"person_id": result["person_id"]}).scalar_one()
        links = conn.execute(text("SELECT count(*) FROM employee_assignment_links WHERE employee_id=:employee_id"), {"employee_id": employee_id}).scalar_one()
    assert replay["decision"] == "REPLAY" and replay["person_id"] == result["person_id"]
    assert {key: after[key] for key in before} == before
    assert after["person_id"] == result["person_id"]
    assert dict(audit) == {"actor_user_id": active_employee_case["actor"], "employee_id": employee_id, "person_id": result["person_id"], "decision": "CREATE", "normalized_record_ids": "[]"}
    assert assignments == 0 and links == 0


def test_requires_hr_confirmation_without_mutation(active_employee_case):
    preflight = _preflight(active_employee_case)
    with pytest.raises(PersonLinkError) as exc:
        with engine.begin() as conn:
            create_active_employee_person_card_tx(
                conn, employee_id=active_employee_case["employee_id"], expected_precondition=preflight["expected_precondition"],
                request_id=f"active-card-no-confirm-{uuid4()}", actor_user_id=active_employee_case["actor"], hr_confirmed=False,
            )
    assert exc.value.code == "HR_CONFIRMATION_REQUIRED"
    with engine.begin() as conn:
        assert conn.execute(text("SELECT person_id FROM employees WHERE employee_id=:employee_id"), {"employee_id": active_employee_case["employee_id"]}).scalar_one() is None


def test_preflight_blocks_existing_and_ambiguous_persons(active_employee_case, monkeypatch):
    with engine.begin() as conn:
        insert_person_with_iin(conn, full_name="Existing person", iin=active_employee_case["iin"], prefix="active-card-existing")
    existing = _preflight(active_employee_case)
    assert existing["ready"] is False
    assert {item["code"] for item in existing["blockers"]} == {"PERSON_ALREADY_EXISTS"}

    # The normal schema prevents two active Persons with one IIN.  Preserve the
    # defence for restored/legacy data by exercising the resolver's ambiguous
    # result explicitly, rather than disabling the production unique index.
    monkeypatch.setattr(
        active_card_service,
        "resolve_person_create_or_link_exact_iin_tx",
        lambda *_args, **_kwargs: Adr048PersonResolution(
            decision="AMBIGUOUS",
            candidates=(
                Adr048PersonCandidate(1, active_employee_case["iin"], "active", None, (), ()),
                Adr048PersonCandidate(2, active_employee_case["iin"], "active", None, (), ()),
            ),
            reason_codes=("PERSON_IDENTITY_AMBIGUOUS",),
        ),
    )
    ambiguous = _preflight(active_employee_case)
    assert ambiguous["ready"] is False
    assert {item["code"] for item in ambiguous["blockers"]} == {"PERSON_IDENTITY_AMBIGUOUS"}


def test_api_preflight_and_apply(active_employee_case):
    client = TestClient(app)
    headers = auth_headers(active_employee_case["actor"])
    preflight = client.post("/directory/personnel/lk/active-employee-card/preflight", headers=headers, json={"employee_id": active_employee_case["employee_id"]})
    assert preflight.status_code == 200
    body = preflight.json()
    assert body["ready"] is True and "assignment_intent" not in body
    rejected = client.post("/directory/personnel/lk/active-employee-card/apply", headers=headers, json={"employee_id": active_employee_case["employee_id"], "expected_precondition": body["expected_precondition"], "request_id": f"active-card-api-{uuid4()}", "hr_confirmed": False})
    assert rejected.status_code == 422
    applied = client.post("/directory/personnel/lk/active-employee-card/apply", headers=headers, json={"employee_id": active_employee_case["employee_id"], "expected_precondition": body["expected_precondition"], "request_id": f"active-card-api-{uuid4()}", "hr_confirmed": True})
    assert applied.status_code == 200
    assert applied.json()["decision"] == "CREATE"
