"""Security contract tests for the employee-owned ``/api/ppr/me`` read path."""
from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth import create_access_token, get_current_user
from app.db.engine import engine
from app.db.models.personnel_verification import CONTROL_POINT_EMPLOYMENT_EPISODE
from app.personnel_verification.infrastructure.repository import PersonnelVerificationRepository
from app.main import app
from app.ppr.application.authorization import AllowAllAuthorizationPort
from app.ppr.application.command_models import COMMAND_TYPE_MATERIALIZE_PPR, MaterializePprPayload, PprCommandEnvelope
from app.ppr.application.lifecycle_service import PprLifecycleApplicationService
from tests.ppr.conftest import (
    cleanup_person_graph,
    insert_employee,
    insert_person,
    ppr_db_available,
    require_ppr_schema,
)


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def linked_self_user(seed):
    """A normal user with only a direct User → Employee → Person relation."""
    require_ppr_schema()
    suffix = uuid4().hex[:8]
    user_id = int(seed["initiator_user_id"])
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"Self Card {suffix}")
        employee_id = insert_employee(
            conn,
            full_name=f"Self Card Employee {suffix}",
            person_id=person_id,
        )
        conn.execute(
            text("UPDATE public.users SET employee_id = :employee_id WHERE user_id = :user_id"),
            {"employee_id": employee_id, "user_id": user_id},
        )
    try:
        yield {"user_id": user_id, "employee_id": employee_id, "person_id": person_id}
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE public.users SET employee_id = NULL WHERE user_id = :user_id"),
                {"user_id": user_id},
            )
            cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[employee_id])


def _authenticate_as(user_id: int, **extra: object) -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id, **extra}


def _ensure_employment_policy(*, user_id: int) -> None:
    """Publish the verification policy required for employment supersede."""
    with engine.begin() as conn:
        repo = PersonnelVerificationRepository(conn)
        if repo.get_active_policy(CONTROL_POINT_EMPLOYMENT_EPISODE) is not None:
            return
        draft = repo.create_policy_draft(
            control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
            effective_from=date(2026, 1, 1),
            decision_basis=f"Self employment supersede test {uuid4().hex[:8]}",
            created_by_user_id=user_id,
        )
        repo.publish_policy(policy_id=draft.policy_id, published_by_user_id=user_id)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_self_card_reads_only_server_resolved_person_without_visibility(
    client: TestClient,
    linked_self_user: dict[str, int],
) -> None:
    _authenticate_as(linked_self_user["user_id"])

    response = client.request(
        "GET",
        "/api/ppr/me?person_id=999999&employee_id=999998",
        json={"person_id": 999997, "employee_id": 999996},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "READY"
    assert body["card"]["general"]["full_name"].startswith("Self Card ")
    # The self API neither accepts nor returns a subject selector.
    assert "identity" not in body["card"]
    assert "metadata" not in body["card"]
    assert "events" not in body["card"]
    assert "resolved_person_id" not in str(body)
    assert "999999" not in str(body)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_self_operational_assignment_is_id_free_and_exposes_only_own_iin(
    client: TestClient,
    linked_self_user: dict[str, int],
) -> None:
    """The assignment comes from Employee, never visibility or person_assignment."""
    _authenticate_as(linked_self_user["user_id"])
    with engine.begin() as conn:
        conn.execute(
            text("""INSERT INTO public.employee_identities(employee_id, identity_type, identity_value, is_primary)
                    VALUES(:employee_id, 'IIN', '990101123456', TRUE)"""),
            {"employee_id": linked_self_user["employee_id"]},
        )

    response = client.request(
        "GET",
        "/api/ppr/me/operational-assignment?employee_id=999999&person_id=999998",
        json={"employee_id": 999997, "person_id": 999996},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "READY"
    assert body["operational_assignment"]["operational_status"] == "active"
    assert body["operational_assignment"]["employment_rate"] == 1.0
    assert body["operational_assignment"]["iin"] == "990101123456"
    assert "employee_id" not in str(body)
    assert "person_id" not in str(body)
    assert "999999" not in str(body)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_self_card_returns_no_employee_link_for_user_without_employee(
    client: TestClient,
    seed,
) -> None:
    _authenticate_as(int(seed["initiator_user_id"]))

    response = client.get("/api/ppr/me")

    assert response.status_code == 200
    assert response.json() == {"status": "NO_EMPLOYEE_LINK", "card": None}


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_self_card_returns_person_not_linked_without_creating_person(
    client: TestClient,
    seed,
) -> None:
    require_ppr_schema()
    suffix = uuid4().hex[:8]
    user_id = int(seed["initiator_user_id"])
    with engine.begin() as conn:
        employee_id = insert_employee(conn, full_name=f"Self Orphan {suffix}")
        conn.execute(
            text("UPDATE public.users SET employee_id = :employee_id WHERE user_id = :user_id"),
            {"employee_id": employee_id, "user_id": user_id},
        )
    try:
        _authenticate_as(user_id)
        response = client.get("/api/ppr/me")
        assert response.status_code == 200
        assert response.json() == {"status": "PERSON_NOT_LINKED", "card": None}
        with engine.connect() as conn:
            assert conn.execute(
                text("SELECT person_id FROM public.employees WHERE employee_id = :employee_id"),
                {"employee_id": employee_id},
            ).scalar_one() is None
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE public.users SET employee_id = NULL WHERE user_id = :user_id"),
                {"user_id": user_id},
            )
            conn.execute(
                text("DELETE FROM public.employees WHERE employee_id = :employee_id"),
                {"employee_id": employee_id},
            )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_self_card_database_invariant_prevents_ambiguous_active_employee_person_relation(
    client: TestClient,
    linked_self_user: dict[str, int],
) -> None:
    """The resolver has a defensive ambiguity check; the DB makes it unreachable.

    A second active Employee for the same Person would be an identity ambiguity,
    so the partial unique index must reject it before a self-card can resolve.
    """
    suffix = uuid4().hex[:8]
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            insert_employee(
                conn,
                full_name=f"Duplicate relation {suffix}",
                person_id=linked_self_user["person_id"],
            )

    _authenticate_as(linked_self_user["user_id"])
    response = client.get("/api/ppr/me")
    assert response.status_code == 200
    assert response.json()["status"] == "READY"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_event_permission_does_not_participate_in_self_resolution(
    client: TestClient,
    linked_self_user: dict[str, int],
) -> None:
    _authenticate_as(linked_self_user["user_id"], has_personnel_events_read=True)

    response = client.get("/api/ppr/me")

    assert response.status_code == 200
    assert response.json()["status"] == "READY"


def test_self_card_requires_authenticated_user(client: TestClient) -> None:
    response = client.get("/api/ppr/me")
    assert response.status_code == 401


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_self_card_rejects_inactive_authenticated_user(
    client: TestClient,
    seed,
) -> None:
    """Authentication remains the 403 gate; no self resolution follows it."""
    user_id = int(seed["initiator_user_id"])
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE public.users SET is_active = FALSE WHERE user_id = :user_id"),
            {"user_id": user_id},
        )
    try:
        response = client.get(
            "/api/ppr/me",
            headers={"Authorization": f"Bearer {create_access_token(user_id)}"},
        )
        assert response.status_code == 403
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE public.users SET is_active = TRUE WHERE user_id = :user_id"),
                {"user_id": user_id},
            )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_self_edit_contacts_and_languages_are_id_free_audited_and_preserve_profile(
    client: TestClient,
    linked_self_user: dict[str, int],
) -> None:
    _authenticate_as(linked_self_user["user_id"])
    person_id = linked_self_user["person_id"]
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO personnel_record_metadata(person_id, additional_profile) VALUES(:person_id, CAST(:profile AS jsonb)) ON CONFLICT(person_id) DO UPDATE SET additional_profile=EXCLUDED.additional_profile"),
            {"person_id": person_id, "profile": '{"awards":[{"name":"keep"}],"foreign_languages":[{"language":"English","proficiency":"B1"}]}'},
        )

    contacts = {
        "command_id": f"self-contacts-{uuid4().hex}", "expected_version": 0,
        "mobile_phone": "+7 700 123 45 67", "email": "self@example.test",
    }
    first = client.put("/api/ppr/me/contacts", json=contacts)
    assert first.status_code == 200
    assert client.put("/api/ppr/me/contacts", json=contacts).json()["idempotent"] is True
    assert client.put("/api/ppr/me/contacts", json={**contacts, "person_id": 999999}).status_code == 422

    languages = {"command_id": f"self-languages-{uuid4().hex}", "foreign_languages": [{"language": "German", "proficiency": "B2"}]}
    response = client.put("/api/ppr/me/foreign-languages", json=languages)
    assert response.status_code == 200
    assert client.put("/api/ppr/me/foreign-languages", json=languages).json()["idempotent"] is True
    assert client.put("/api/ppr/me/foreign-languages", json={**languages, "employee_id": 999999}).status_code == 422
    with engine.connect() as conn:
        profile = conn.execute(text("SELECT additional_profile FROM personnel_record_metadata WHERE person_id=:person_id"), {"person_id": person_id}).scalar_one()
        events = conn.execute(text("SELECT event_type,event_payload FROM personnel_record_events WHERE person_id=:person_id AND event_type IN ('PPR_CONTACTS_SELF_UPDATED','PPR_FOREIGN_LANGUAGES_SELF_UPDATED') ORDER BY event_id"), {"person_id": person_id}).mappings().all()
    assert profile["awards"] == [{"name": "keep"}]
    assert profile["foreign_languages"] == [{"language": "German", "proficiency": "B2"}]
    assert all(event["event_payload"]["source"] == "EMPLOYEE_SELF_SERVICE" for event in events)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_self_education_create_is_id_free_and_emits_self_source(
    client: TestClient,
    linked_self_user: dict[str, int],
) -> None:
    _authenticate_as(linked_self_user["user_id"])
    person_id = linked_self_user["person_id"]
    lifecycle = PprLifecycleApplicationService(authorization=AllowAllAuthorizationPort())
    lifecycle.materialize_ppr(PprCommandEnvelope(
        command_id=f"materialize-{uuid4().hex}", command_type=COMMAND_TYPE_MATERIALIZE_PPR,
        actor_id=str(linked_self_user["user_id"]), requested_at=datetime.now(UTC),
        payload=MaterializePprPayload(), person_id=person_id,
    ))
    body = {"command_id": f"self-education-{uuid4().hex}", "record": {"education_kind": "masters", "institution_name": "КазНУ"}}
    response = client.post("/api/ppr/me/education/records", json=body)
    assert response.status_code == 200
    assert client.post("/api/ppr/me/education/records", json={**body, "person_id": 999999}).status_code == 422
    with engine.connect() as conn:
        event = conn.execute(text("SELECT event_payload FROM personnel_record_events WHERE person_id=:person_id AND event_payload->>'command_id'=:command_id ORDER BY event_id DESC LIMIT 1"), {"person_id": person_id, "command_id": body["command_id"]}).scalar_one()
    assert event["source"] == "EMPLOYEE_SELF_SERVICE"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_first_self_education_save_materializes_envelope_and_commits(client: TestClient, linked_self_user: dict[str, int]) -> None:
    _authenticate_as(linked_self_user["user_id"])
    response = client.post("/api/ppr/me/education/records", json={"command_id": f"first-education-{uuid4().hex}", "record": {"education_kind": "masters", "institution_name": "First save"}})
    assert response.status_code == 200
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1 FROM personnel_record_metadata WHERE person_id=:person_id"), {"person_id": linked_self_user["person_id"]}).scalar_one() == 1
        assert conn.execute(text("SELECT institution_name FROM person_education WHERE person_id=:person_id AND lifecycle_status='active'"), {"person_id": linked_self_user["person_id"]}).scalar_one() == "First save"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_self_employment_biography_is_id_free_idempotent_and_audited(client: TestClient, linked_self_user: dict[str, int]) -> None:
    _authenticate_as(linked_self_user["user_id"])
    person_id = linked_self_user["person_id"]
    lifecycle = PprLifecycleApplicationService(authorization=AllowAllAuthorizationPort())
    lifecycle.materialize_ppr(PprCommandEnvelope(command_id=f"materialize-{uuid4().hex}", command_type=COMMAND_TYPE_MATERIALIZE_PPR, actor_id=str(linked_self_user["user_id"]), requested_at=datetime.now(UTC), payload=MaterializePprPayload(), person_id=person_id))
    body = {"command_id": f"self-job-{uuid4().hex}", "record": {"record_kind": "episode", "employer_name": "Example", "position_title": "Engineer", "started_at": "2020-01-01"}}
    response = client.post("/api/ppr/me/employment-biography/records", json=body)
    assert response.status_code == 200
    assert "person_id" not in str(response.json()) and "employee_id" not in str(response.json())
    assert client.post("/api/ppr/me/employment-biography/records", json=body).status_code == 200
    with engine.connect() as conn:
        row = conn.execute(text("SELECT employer_name,position_title FROM person_external_employment WHERE person_id=:person_id AND lifecycle_status='active'"), {"person_id": person_id}).mappings().one()
        event = conn.execute(text("SELECT event_payload FROM personnel_record_events WHERE person_id=:person_id AND event_payload->>'command_id'=:command_id ORDER BY event_id DESC LIMIT 1"), {"person_id": person_id, "command_id": body["command_id"]}).scalar_one()
    assert row["employer_name"] == "Example" and event["source"] == "EMPLOYEE_SELF_SERVICE"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_self_foreign_languages_can_reload_cas_version_and_save_again(
    client: TestClient, linked_self_user: dict[str, int]
) -> None:
    """A current version returned by the ID-free GET must be accepted by the next PUT."""
    _authenticate_as(linked_self_user["user_id"])
    first = client.put("/api/ppr/me/foreign-languages", json={
        "command_id": f"language-first-{uuid4().hex}",
        "foreign_languages": [{"language": "English", "proficiency": "Со словарём"}],
    })
    assert first.status_code == 200
    version_one = client.get("/api/ppr/me/foreign-languages").json()["updated_at"]
    second = client.put("/api/ppr/me/foreign-languages", json={
        "command_id": f"language-second-{uuid4().hex}",
        "expected_updated_at": version_one,
        "foreign_languages": [{"language": "English", "proficiency": "Читает и может объясняться"}],
    })
    assert second.status_code == 200
    reloaded = client.get("/api/ppr/me/foreign-languages").json()
    assert reloaded["foreign_languages"] == [{"language": "English", "proficiency": "Читает и может объясняться"}]
    third = client.put("/api/ppr/me/foreign-languages", json={
        "command_id": f"language-third-{uuid4().hex}",
        "expected_updated_at": reloaded["updated_at"],
        "foreign_languages": [{"language": "English", "proficiency": "Владеет свободно"}],
    })
    assert third.status_code == 200
    assert client.put("/api/ppr/me/foreign-languages", json={
        "command_id": f"language-stale-{uuid4().hex}",
        "expected_updated_at": version_one,
        "foreign_languages": [{"language": "English", "proficiency": "Со словарём"}],
    }).status_code == 409


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_self_employment_supersede_is_versioned_cas_id_free_and_audited(
    client: TestClient, linked_self_user: dict[str, int]
) -> None:
    _authenticate_as(linked_self_user["user_id"])
    person_id = linked_self_user["person_id"]
    _ensure_employment_policy(user_id=linked_self_user["user_id"])
    lifecycle = PprLifecycleApplicationService(authorization=AllowAllAuthorizationPort())
    lifecycle.materialize_ppr(PprCommandEnvelope(
        command_id=f"materialize-{uuid4().hex}", command_type=COMMAND_TYPE_MATERIALIZE_PPR,
        actor_id=str(linked_self_user["user_id"]), requested_at=datetime.now(UTC),
        payload=MaterializePprPayload(), person_id=person_id,
    ))
    created = client.post("/api/ppr/me/employment-biography/records", json={
        "command_id": f"self-job-{uuid4().hex}",
        "record": {"record_kind": "episode", "employer_name": "Before", "position_title": "Engineer", "started_at": "2020-01-01"},
    })
    assert created.status_code == 200
    with engine.connect() as conn:
        original = conn.execute(text("""
            SELECT employment_id, updated_at, employer_name, lifecycle_status
            FROM person_external_employment
            WHERE person_id=:person_id AND employer_name='Before'
        """), {"person_id": person_id}).mappings().one()

    body = {
        "command_id": f"self-job-supersede-{uuid4().hex}",
        "expected_updated_at": original["updated_at"].isoformat(),
        "replacement": {"record_kind": "episode", "employer_name": "After", "position_title": "Senior engineer", "started_at": "2020-01-01"},
    }
    route = f"/api/ppr/me/employment-biography/records/{original['employment_id']}/supersede"
    first = client.post(route, json=body)
    assert first.status_code == 200
    assert client.post(route, json=body).status_code == 200
    assert client.post(route, json={**body, "person_id": 999999}).status_code == 422
    stale = client.post(route, json={**body, "command_id": f"stale-{uuid4().hex}", "expected_updated_at": "2000-01-01T00:00:00+00:00"})
    assert stale.status_code == 409

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT employment_id, employer_name, lifecycle_status
            FROM person_external_employment WHERE person_id=:person_id ORDER BY employment_id
        """), {"person_id": person_id}).mappings().all()
        event = conn.execute(text("""
            SELECT event_payload FROM personnel_record_events
            WHERE person_id=:person_id AND event_payload->>'command_id'=:command_id
            ORDER BY event_id DESC LIMIT 1
        """), {"person_id": person_id, "command_id": body["command_id"]}).scalar_one()

    assert any(row["employment_id"] == original["employment_id"] and row["employer_name"] == "Before" and row["lifecycle_status"] == "active" for row in rows)
    assert any(row["employment_id"] != original["employment_id"] and row["employer_name"] == "After" for row in rows)
    assert event["source"] == "EMPLOYEE_SELF_SERVICE"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_self_edit_sequence_contacts_education_languages_then_reload(client: TestClient, linked_self_user: dict[str, int]) -> None:
    """HTTP integration regression: each write survives the next self-card reload."""
    _authenticate_as(linked_self_user["user_id"])
    person_id = linked_self_user["person_id"]
    PprLifecycleApplicationService(authorization=AllowAllAuthorizationPort()).materialize_ppr(PprCommandEnvelope(command_id=f"materialize-{uuid4().hex}", command_type=COMMAND_TYPE_MATERIALIZE_PPR, actor_id=str(linked_self_user["user_id"]), requested_at=datetime.now(UTC), payload=MaterializePprPayload(), person_id=person_id))
    assert client.put("/api/ppr/me/contacts", json={"command_id": f"contacts-{uuid4().hex}", "expected_version": 0, "mobile_phone": "+77001234567", "email": "self@example.test"}).status_code == 200
    assert client.post("/api/ppr/me/education/records", json={"command_id": f"education-{uuid4().hex}", "record": {"education_kind": "masters", "institution_name": "University"}}).status_code == 200
    assert client.put("/api/ppr/me/foreign-languages", json={"command_id": f"language-{uuid4().hex}", "foreign_languages": [{"language": "Турецкий", "proficiency": "Владеет свободно"}]}).status_code == 200
    assert client.get("/api/ppr/me/contacts").json()["canonical"]["mobile_phone"] == "+77001234567"
    card = client.get("/api/ppr/me").json()["card"]
    assert card["sections"]["PPR-EDUCATION"]["active"][0]["institution_name"] == "University"
    assert card["additional"]["foreign_languages"] == [{"language": "Турецкий", "proficiency": "Владеет свободно"}]
    with engine.connect() as conn:
        sources = conn.execute(text("SELECT event_payload->>'source' FROM personnel_record_events WHERE person_id=:person_id AND event_payload ? 'command_id'"), {"person_id": person_id}).scalars().all()
    assert "EMPLOYEE_SELF_SERVICE" in sources
