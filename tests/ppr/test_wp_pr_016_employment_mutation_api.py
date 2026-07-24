# tests/ppr/test_wp_pr_016_employment_mutation_api.py
"""API tests for WP-PR-016 employment biography mutation endpoints."""
from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_migration import (
    EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
)
from app.db.models.personnel_verification import CONTROL_POINT_EMPLOYMENT_EPISODE
from app.main import app
from app.personnel_verification.infrastructure.repository import PersonnelVerificationRepository
from app.ppr.application.authorization import AllowAllAuthorizationPort
from app.ppr.application.command_models import (
    COMMAND_TYPE_ADD_EXTERNAL_EMPLOYMENT,
    COMMAND_TYPE_MATERIALIZE_PPR,
    MaterializePprPayload,
    PprCommandEnvelope,
)
from app.ppr.application.lifecycle_service import PprLifecycleApplicationService
from app.ppr.application.results import RESULT_STATUS_COMMITTED, RESULT_STATUS_IDEMPOTENT_REPLAY
from app.ppr.application.section_service import PprSectionApplicationService
from app.ppr.domain.section_models import SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY
from tests.conftest import auth_headers, table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_employee, insert_person, ppr_db_available, require_ppr_schema


def _require_metadata_schema() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_record_metadata"):
            pytest.skip("personnel_record_metadata missing — run: alembic upgrade head")


def _ensure_employment_policy(*, user_id: int) -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "verification_policies"):
            pytest.skip("verification_policies missing — run: alembic upgrade head")
        repo = PersonnelVerificationRepository(conn)
        if repo.get_active_policy(CONTROL_POINT_EMPLOYMENT_EPISODE) is not None:
            return
        draft = repo.create_policy_draft(
            control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
            effective_from=date(2026, 1, 1),
            decision_basis=f"WP-VER-005A wp16 policy {uuid4().hex[:8]}",
            created_by_user_id=user_id,
        )
        repo.publish_policy(policy_id=draft.policy_id, published_by_user_id=user_id)


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def bare_person():
    require_ppr_schema()
    _require_metadata_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"WP16 Bare {suffix}")
    yield person_id
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])


@pytest.fixture
def other_person():
    require_ppr_schema()
    _require_metadata_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"WP16 Other {suffix}")
    yield person_id
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])


@pytest.fixture
def linked_person_employee():
    require_ppr_schema()
    _require_metadata_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"WP16 Linked {suffix}")
        employee_id = insert_employee(conn, full_name=f"WP16 Emp {suffix}", person_id=person_id)
    yield {"person_id": person_id, "employee_id": employee_id}
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[employee_id])


def _materialize(person_id: int) -> None:
    svc = PprLifecycleApplicationService(authorization=AllowAllAuthorizationPort())
    svc.materialize_ppr(
        PprCommandEnvelope(
            command_id=f"wp16-mat-{uuid4().hex}",
            command_type=COMMAND_TYPE_MATERIALIZE_PPR,
            actor_id="wp16-test",
            requested_at=datetime.now(UTC),
            payload=MaterializePprPayload(),
            person_id=person_id,
        )
    )


def _create_payload(*, command_id: str | None = None) -> dict:
    return {
        "command_id": command_id or f"wp16-create-{uuid4().hex}",
        "record": {
            "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
            "employer_name": "ТОО «API Employer»",
            "position_title": "Инженер",
            "started_at": "2018-03-01",
        },
    }


def _seed_record(person_id: int) -> tuple[int, datetime]:
    section_service = PprSectionApplicationService(authorization=AllowAllAuthorizationPort())
    result = section_service.add_external_employment(
        PprCommandEnvelope(
            command_id=f"wp16-seed-{uuid4().hex}",
            command_type=COMMAND_TYPE_ADD_EXTERNAL_EMPLOYMENT,
            actor_id="wp16-test",
            requested_at=datetime.now(UTC),
            payload={
                "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
                "employer_name": "Seed Employer",
                "position_title": "Seed Role",
                "started_at": date(2017, 1, 1),
            },
            person_id=person_id,
        )
    )
    assert result.section_record_id is not None
    with engine.begin() as conn:
        updated_at = conn.execute(
            text(
                """
                SELECT updated_at
                FROM public.person_external_employment
                WHERE employment_id = :rid
                """
            ),
            {"rid": result.section_record_id},
        ).scalar_one()
    return int(result.section_record_id), updated_at


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_openapi_has_employment_mutation_routes(client: TestClient) -> None:
    paths = client.get("/openapi.json").json().get("paths", {})
    assert "/api/ppr/persons/{person_id}/employment-biography/records" in paths
    assert "/api/ppr/persons/{person_id}/employment-biography/records/{record_id}/void" in paths
    assert "/api/ppr/persons/{person_id}/employment-biography/records/{record_id}/supersede" in paths
    assert "/api/ppr/employees/{employee_id}/employment-biography/records" in paths


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_create_by_person_committed(
    client: TestClient,
    bare_person: int,
    privileged_headers,
) -> None:
    _materialize(bare_person)
    resp = client.post(
        f"/api/ppr/persons/{bare_person}/employment-biography/records",
        headers=privileged_headers,
        json=_create_payload(),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == RESULT_STATUS_COMMITTED
    assert body["resolved_person_id"] == bare_person
    assert body["section_code"] == SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY
    assert body["section_record_id"] is not None
    assert body["event_ids"]

    read_resp = client.get(f"/api/ppr/persons/{bare_person}", headers=privileged_headers)
    assert read_resp.status_code == 200
    active = read_resp.json()["sections"][SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY]["active"]
    assert any(row["employer_name"] == "ТОО «API Employer»" for row in active)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_create_by_employee_committed(
    client: TestClient,
    linked_person_employee: dict,
    privileged_headers,
) -> None:
    _materialize(linked_person_employee["person_id"])
    resp = client.post(
        f"/api/ppr/employees/{linked_person_employee['employee_id']}/employment-biography/records",
        headers=privileged_headers,
        json=_create_payload(),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == RESULT_STATUS_COMMITTED
    assert body["resolved_person_id"] == linked_person_employee["person_id"]


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_void_by_person(
    client: TestClient,
    bare_person: int,
    privileged_headers,
) -> None:
    _materialize(bare_person)
    record_id, updated_at = _seed_record(bare_person)
    resp = client.post(
        f"/api/ppr/persons/{bare_person}/employment-biography/records/{record_id}/void",
        headers=privileged_headers,
        json={
            "command_id": f"wp16-void-{uuid4().hex}",
            "reason": "duplicate entry",
            "expected_updated_at": updated_at.isoformat(),
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == RESULT_STATUS_COMMITTED
    assert body["section_record_id"] == record_id

    read_resp = client.get(f"/api/ppr/persons/{bare_person}", headers=privileged_headers)
    voided = read_resp.json()["sections"][SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY]["voided"]
    assert any(row["record_id"] == record_id for row in voided)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_supersede_by_person(
    client: TestClient,
    bare_person: int,
    privileged_headers,
    seed,
) -> None:
    _ensure_employment_policy(user_id=int(seed["initiator_user_id"]))
    _materialize(bare_person)
    record_id, updated_at = _seed_record(bare_person)
    resp = client.post(
        f"/api/ppr/persons/{bare_person}/employment-biography/records/{record_id}/supersede",
        headers=privileged_headers,
        json={
            "command_id": f"wp16-sup-{uuid4().hex}",
            "expected_updated_at": updated_at.isoformat(),
            "replacement": {
                "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
                "employer_name": "Replacement Employer",
                "position_title": "Lead",
                "started_at": "2020-06-01",
            },
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == RESULT_STATUS_COMMITTED
    assert body["section_record_id"] != record_id

    read_resp = client.get(f"/api/ppr/persons/{bare_person}", headers=privileged_headers)
    section = read_resp.json()["sections"][SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY]
    # WP-VER-005A: prior stays effective-active; pending replacement is hidden until confirm.
    assert any(row["record_id"] == record_id for row in section["active"])
    assert not any(row["employer_name"] == "Replacement Employer" for row in section["active"])
    assert not any(row["record_id"] == record_id for row in section["superseded"])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_create_validation_422(
    client: TestClient,
    bare_person: int,
    privileged_headers,
) -> None:
    _materialize(bare_person)
    resp = client.post(
        f"/api/ppr/persons/{bare_person}/employment-biography/records",
        headers=privileged_headers,
        json={
            "command_id": f"wp16-invalid-{uuid4().hex}",
            "record": {
                "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
                "employer_name": "Missing position",
            },
        },
    )
    assert resp.status_code == 422


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_foreign_person_void_returns_404(
    client: TestClient,
    bare_person: int,
    other_person: int,
    privileged_headers,
) -> None:
    _materialize(bare_person)
    _materialize(other_person)
    record_id, updated_at = _seed_record(bare_person)
    resp = client.post(
        f"/api/ppr/persons/{other_person}/employment-biography/records/{record_id}/void",
        headers=privileged_headers,
        json={
            "command_id": f"wp16-foreign-{uuid4().hex}",
            "reason": "foreign attempt",
            "expected_updated_at": updated_at.isoformat(),
        },
    )
    assert resp.status_code == 404


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_stale_expected_updated_at_returns_409(
    client: TestClient,
    bare_person: int,
    privileged_headers,
) -> None:
    _materialize(bare_person)
    record_id, updated_at = _seed_record(bare_person)
    stale = updated_at.replace(year=2000)
    resp = client.post(
        f"/api/ppr/persons/{bare_person}/employment-biography/records/{record_id}/void",
        headers=privileged_headers,
        json={
            "command_id": f"wp16-stale-{uuid4().hex}",
            "reason": "stale token",
            "expected_updated_at": stale.isoformat(),
        },
    )
    assert resp.status_code == 409


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_create_idempotent_replay(
    client: TestClient,
    bare_person: int,
    privileged_headers,
) -> None:
    _materialize(bare_person)
    command_id = f"wp16-replay-{uuid4().hex}"
    payload = _create_payload(command_id=command_id)
    first = client.post(
        f"/api/ppr/persons/{bare_person}/employment-biography/records",
        headers=privileged_headers,
        json=payload,
    )
    second = client.post(
        f"/api/ppr/persons/{bare_person}/employment-biography/records",
        headers=privileged_headers,
        json=payload,
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    assert first.json()["status"] == RESULT_STATUS_COMMITTED
    assert second.json()["status"] == RESULT_STATUS_IDEMPOTENT_REPLAY
    assert first.json()["section_record_id"] == second.json()["section_record_id"]

    with engine.begin() as conn:
        count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.person_external_employment
                WHERE person_id = :pid
                """
            ),
            {"pid": bare_person},
        ).scalar_one()
    assert int(count) == 1


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_unauthorized_403(client: TestClient, bare_person: int, seed) -> None:
    _materialize(bare_person)
    headers = auth_headers(seed["initiator_user_id"])
    resp = client.post(
        f"/api/ppr/persons/{bare_person}/employment-biography/records",
        headers=headers,
        json=_create_payload(),
    )
    assert resp.status_code == 403


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_not_materialized_returns_409(
    client: TestClient,
    bare_person: int,
    privileged_headers,
) -> None:
    resp = client.post(
        f"/api/ppr/persons/{bare_person}/employment-biography/records",
        headers=privileged_headers,
        json=_create_payload(),
    )
    assert resp.status_code == 409


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_record_employee_context_id_does_not_affect_ownership(
    client: TestClient,
    bare_person: int,
    linked_person_employee: dict,
    privileged_headers,
) -> None:
    _materialize(bare_person)
    foreign_employee_context_id = linked_person_employee["employee_id"]
    resp = client.post(
        f"/api/ppr/persons/{bare_person}/employment-biography/records",
        headers=privileged_headers,
        json={
            "command_id": f"wp16-ctx-{uuid4().hex}",
            "record": {
                "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
                "employer_name": "Context Audit Employer",
                "position_title": "Role",
                "started_at": "2019-01-01",
                "employee_context_id": foreign_employee_context_id,
            },
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["resolved_person_id"] == bare_person
    record_id = body["section_record_id"]
    assert record_id is not None

    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT person_id, employee_context_id
                FROM public.person_external_employment
                WHERE employment_id = :rid
                """
            ),
            {"rid": record_id},
        ).one()
    assert int(row[0]) == bare_person
    assert int(row[1]) == foreign_employee_context_id


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_employee_void_resolves_owner_via_employee_identity_only(
    client: TestClient,
    bare_person: int,
    linked_person_employee: dict,
    privileged_headers,
) -> None:
    _materialize(bare_person)
    _materialize(linked_person_employee["person_id"])
    record_id, updated_at = _seed_record(bare_person)
    resp = client.post(
        f"/api/ppr/employees/{linked_person_employee['employee_id']}/employment-biography/records/{record_id}/void",
        headers=privileged_headers,
        json={
            "command_id": f"wp16-emp-foreign-{uuid4().hex}",
            "reason": "wrong owner via employee route",
            "expected_updated_at": updated_at.isoformat(),
        },
    )
    assert resp.status_code == 404


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_unauthorized_foreign_person_returns_403_before_not_found(
    client: TestClient,
    bare_person: int,
    other_person: int,
    seed,
) -> None:
    _materialize(bare_person)
    record_id, updated_at = _seed_record(bare_person)
    headers = auth_headers(seed["initiator_user_id"])
    resp = client.post(
        f"/api/ppr/persons/{other_person}/employment-biography/records/{record_id}/void",
        headers=headers,
        json={
            "command_id": f"wp16-auth-order-{uuid4().hex}",
            "reason": "should fail auth first",
            "expected_updated_at": updated_at.isoformat(),
        },
    )
    assert resp.status_code == 403


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
@pytest.mark.parametrize(
    "forbidden_field,forbidden_value",
    [
        ("person_id", 999_999),
        ("record_id", 999_999),
        ("lifecycle_status", "voided"),
        ("verification_status", "verified"),
        ("created_at", "2020-01-01T00:00:00+00:00"),
        ("updated_at", "2020-01-01T00:00:00+00:00"),
    ],
)
def test_create_rejects_forbidden_record_fields_422(
    client: TestClient,
    bare_person: int,
    privileged_headers,
    forbidden_field: str,
    forbidden_value,
) -> None:
    _materialize(bare_person)
    record = {
        "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
        "employer_name": "Forbidden Field Employer",
        "position_title": "Role",
        "started_at": "2018-01-01",
        forbidden_field: forbidden_value,
    }
    resp = client.post(
        f"/api/ppr/persons/{bare_person}/employment-biography/records",
        headers=privileged_headers,
        json={"command_id": f"wp16-forbidden-{uuid4().hex}", "record": record},
    )
    assert resp.status_code == 422


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
@pytest.mark.parametrize(
    "forbidden_field,forbidden_value",
    [
        ("person_id", 999_999),
        ("lifecycle_status", "voided"),
        ("verification_status", "verified"),
    ],
)
def test_supersede_replacement_rejects_forbidden_fields_422(
    client: TestClient,
    bare_person: int,
    privileged_headers,
    seed,
    forbidden_field: str,
    forbidden_value,
) -> None:
    _ensure_employment_policy(user_id=int(seed["initiator_user_id"]))
    _materialize(bare_person)
    record_id, updated_at = _seed_record(bare_person)
    replacement = {
        "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
        "employer_name": "Replacement",
        "position_title": "Role",
        "started_at": "2020-01-01",
        forbidden_field: forbidden_value,
    }
    resp = client.post(
        f"/api/ppr/persons/{bare_person}/employment-biography/records/{record_id}/supersede",
        headers=privileged_headers,
        json={
            "command_id": f"wp16-sup-forbidden-{uuid4().hex}",
            "expected_updated_at": updated_at.isoformat(),
            "replacement": replacement,
        },
    )
    assert resp.status_code == 422

