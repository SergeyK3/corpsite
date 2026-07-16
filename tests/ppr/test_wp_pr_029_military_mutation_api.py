# tests/ppr/test_wp_pr_029_military_mutation_api.py
"""REST mutation API tests for PPR-MILITARY (WP-PR-029)."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_migration import (
    MILITARY_RECORD_KIND_REGISTRATION,
    SECTION_SOURCE_TYPE_ENTERED,
)
from app.main import app
from app.ppr.application.authorization import AllowAllAuthorizationPort
from app.ppr.application.command_models import (
    COMMAND_TYPE_ACTIVATE_PPR,
    COMMAND_TYPE_CREATE_MILITARY_SERVICE,
    COMMAND_TYPE_MATERIALIZE_PPR,
    MaterializePprPayload,
    PprCommandEnvelope,
)
from app.ppr.application.lifecycle_service import PprLifecycleApplicationService
from app.ppr.application.results import RESULT_STATUS_COMMITTED, RESULT_STATUS_IDEMPOTENT_REPLAY
from app.ppr.application.section_service import PprSectionApplicationService
from app.ppr.domain.section_models import SECTION_CODE_PPR_MILITARY
from tests.conftest import auth_headers, table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_employee, insert_person, ppr_db_available, require_ppr_schema


def _require_metadata_schema() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_record_metadata"):
            pytest.skip("personnel_record_metadata missing — run: alembic upgrade head")
        if not table_exists(conn, "person_military_service"):
            pytest.skip("person_military_service missing — run: alembic upgrade head")


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
        person_id = insert_person(conn, full_name=f"WP29 API {suffix}")
    yield person_id
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])


@pytest.fixture
def linked_person_employee():
    require_ppr_schema()
    _require_metadata_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"WP29 Linked {suffix}")
        employee_id = insert_employee(conn, full_name=f"WP29 Emp {suffix}", person_id=person_id)
    yield {"person_id": person_id, "employee_id": employee_id}
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[employee_id])


def _materialize(person_id: int) -> None:
    svc = PprLifecycleApplicationService(authorization=AllowAllAuthorizationPort())
    svc.materialize_ppr(
        PprCommandEnvelope(
            command_id=f"wp29-mat-{uuid4().hex}",
            command_type=COMMAND_TYPE_MATERIALIZE_PPR,
            actor_id="wp29-test",
            requested_at=datetime.now(UTC),
            payload=MaterializePprPayload(),
            person_id=person_id,
        )
    )
    svc.activate_ppr(
        PprCommandEnvelope(
            command_id=f"wp29-act-{uuid4().hex}",
            command_type=COMMAND_TYPE_ACTIVATE_PPR,
            actor_id="wp29-test",
            requested_at=datetime.now(UTC),
            payload={},
            person_id=person_id,
        )
    )


def _create_payload(*, command_id: str | None = None) -> dict:
    return {
        "command_id": command_id or f"wp29-create-{uuid4().hex}",
        "record": {
            "record_kind": MILITARY_RECORD_KIND_REGISTRATION,
            "obligation_status": "liable",
            "registration_category": "II",
            "military_rank": "рядовой",
            "registration_status": "registered",
            "source_type": SECTION_SOURCE_TYPE_ENTERED,
        },
    }


def _seed_record(person_id: int) -> tuple[int, datetime]:
    section_service = PprSectionApplicationService(authorization=AllowAllAuthorizationPort())
    result = section_service.create_military_service(
        PprCommandEnvelope(
            command_id=f"wp29-seed-{uuid4().hex}",
            command_type=COMMAND_TYPE_CREATE_MILITARY_SERVICE,
            actor_id="wp29-test",
            requested_at=datetime.now(UTC),
            payload=_create_payload()["record"],
            person_id=person_id,
        )
    )
    assert result.section_record_id is not None
    with engine.begin() as conn:
        updated_at = conn.execute(
            text("SELECT updated_at FROM public.person_military_service WHERE military_id = :rid"),
            {"rid": result.section_record_id},
        ).scalar_one()
    return int(result.section_record_id), updated_at


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_openapi_has_military_mutation_routes(client: TestClient) -> None:
    paths = client.get("/openapi.json").json().get("paths", {})
    assert "/api/ppr/persons/{person_id}/military-service/records" in paths
    assert "/api/ppr/persons/{person_id}/military-service/records/{record_id}/void" in paths
    assert "/api/ppr/persons/{person_id}/military-service/records/{record_id}/supersede" in paths
    assert "/api/ppr/employees/{employee_id}/military-service/records" in paths


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_create_by_person_returns_201(
    client: TestClient,
    bare_person: int,
    privileged_headers,
) -> None:
    _materialize(bare_person)
    resp = client.post(
        f"/api/ppr/persons/{bare_person}/military-service/records",
        headers=privileged_headers,
        json=_create_payload(),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["section_code"] == SECTION_CODE_PPR_MILITARY
    assert body["status"] == RESULT_STATUS_COMMITTED


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_create_by_employee_resolves_person(
    client: TestClient,
    linked_person_employee: dict,
    privileged_headers,
) -> None:
    person_id = linked_person_employee["person_id"]
    employee_id = linked_person_employee["employee_id"]
    _materialize(person_id)
    resp = client.post(
        f"/api/ppr/employees/{employee_id}/military-service/records",
        headers=privileged_headers,
        json=_create_payload(),
    )
    assert resp.status_code == 201
    assert resp.json()["resolved_person_id"] == person_id


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_void_by_person(
    client: TestClient,
    bare_person: int,
    privileged_headers,
) -> None:
    _materialize(bare_person)
    record_id, updated_at = _seed_record(bare_person)
    resp = client.post(
        f"/api/ppr/persons/{bare_person}/military-service/records/{record_id}/void",
        headers=privileged_headers,
        json={
            "command_id": f"wp29-void-{uuid4().hex}",
            "reason": "Ошибочная запись",
            "expected_updated_at": updated_at.isoformat(),
        },
    )
    assert resp.status_code == 200
    assert resp.json()["section_mutation_kind"] == "void"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_supersede_by_person(
    client: TestClient,
    bare_person: int,
    privileged_headers,
) -> None:
    _materialize(bare_person)
    record_id, updated_at = _seed_record(bare_person)
    resp = client.post(
        f"/api/ppr/persons/{bare_person}/military-service/records/{record_id}/supersede",
        headers=privileged_headers,
        json={
            "command_id": f"wp29-sup-{uuid4().hex}",
            "expected_updated_at": updated_at.isoformat(),
            "replacement": {
                "record_kind": MILITARY_RECORD_KIND_REGISTRATION,
                "obligation_status": "liable",
                "military_rank": "лейтенант",
                "registration_status": "registered",
                "source_type": SECTION_SOURCE_TYPE_ENTERED,
            },
        },
    )
    assert resp.status_code == 200
    assert resp.json()["section_mutation_kind"] == "supersede"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_create_idempotent_replay(
    client: TestClient,
    bare_person: int,
    privileged_headers,
) -> None:
    _materialize(bare_person)
    command_id = f"wp29-idem-{uuid4().hex}"
    payload = _create_payload(command_id=command_id)
    first = client.post(
        f"/api/ppr/persons/{bare_person}/military-service/records",
        headers=privileged_headers,
        json=payload,
    )
    second = client.post(
        f"/api/ppr/persons/{bare_person}/military-service/records",
        headers=privileged_headers,
        json=payload,
    )
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["status"] == RESULT_STATUS_IDEMPOTENT_REPLAY


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_stale_void_returns_409(
    client: TestClient,
    bare_person: int,
    privileged_headers,
) -> None:
    _materialize(bare_person)
    record_id, updated_at = _seed_record(bare_person)
    resp = client.post(
        f"/api/ppr/persons/{bare_person}/military-service/records/{record_id}/void",
        headers=privileged_headers,
        json={
            "command_id": f"wp29-stale-{uuid4().hex}",
            "reason": "fail",
            "expected_updated_at": updated_at.replace(year=2000).isoformat(),
        },
    )
    assert resp.status_code == 409


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_second_active_create_returns_409(
    client: TestClient,
    bare_person: int,
    privileged_headers,
) -> None:
    _materialize(bare_person)
    first = client.post(
        f"/api/ppr/persons/{bare_person}/military-service/records",
        headers=privileged_headers,
        json=_create_payload(),
    )
    assert first.status_code == 201
    second = client.post(
        f"/api/ppr/persons/{bare_person}/military-service/records",
        headers=privileged_headers,
        json=_create_payload(),
    )
    assert second.status_code == 409
