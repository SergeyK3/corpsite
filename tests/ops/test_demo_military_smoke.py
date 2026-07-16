"""Smoke tests for demo military service scenarios (WP-PR-031)."""
from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_migration import (
    MILITARY_RECORD_KIND_NOT_APPLICABLE,
    MILITARY_RECORD_KIND_REGISTRATION,
    SECTION_SOURCE_TYPE_ENTERED,
)
from app.main import app
from app.ppr.application.authorization import AllowAllAuthorizationPort
from app.ppr.application.command_models import (
    COMMAND_TYPE_ACTIVATE_PPR,
    COMMAND_TYPE_CREATE_MILITARY_SERVICE,
    COMMAND_TYPE_MATERIALIZE_PPR,
    COMMAND_TYPE_SUPERSEDE_MILITARY_SERVICE,
    COMMAND_TYPE_VOID_MILITARY_SERVICE,
    PprCommandEnvelope,
)
from app.ppr.application.lifecycle_service import PprLifecycleApplicationService
from app.ppr.application.section_service import PprSectionApplicationService
from app.ppr.domain.section_models import SECTION_CODE_PPR_MILITARY
from scripts.ops.create_demo_ppr_applicants import APPLICANTS, audit_person_by_iin
from scripts.ops.seed_demo_military_service import DEMO_MILITARY_BY_KEY, run as run_military_seed
from scripts.ops.seed_demo_employment_biography import run as run_employment_biography
from scripts.ops.create_demo_ppr_applicants import run as run_applicants
from tests.conftest import auth_headers, table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_employee, insert_person, ppr_db_available


def _require_db() -> None:
    if not ppr_db_available():
        pytest.skip("PostgreSQL unavailable")


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def client():
    return TestClient(app)


def _materialize(person_id: int) -> None:
    svc = PprLifecycleApplicationService(authorization=AllowAllAuthorizationPort())
    svc.materialize_ppr(
        PprCommandEnvelope(
            command_id=f"mat-{uuid4().hex}",
            command_type=COMMAND_TYPE_MATERIALIZE_PPR,
            actor_id="wp31-smoke",
            requested_at=datetime.now(UTC),
            payload={},
            person_id=person_id,
        )
    )
    svc.activate_ppr(
        PprCommandEnvelope(
            command_id=f"act-{uuid4().hex}",
            command_type=COMMAND_TYPE_ACTIVATE_PPR,
            actor_id="wp31-smoke",
            requested_at=datetime.now(UTC),
            payload={},
            person_id=person_id,
        )
    )


def _registration_payload(**overrides) -> dict:
    base = {
        "record_kind": MILITARY_RECORD_KIND_REGISTRATION,
        "obligation_status": "liable",
        "registration_category": "II",
        "military_rank": "рядовой",
        "registration_status": "registered",
        "source_type": SECTION_SOURCE_TYPE_ENTERED,
    }
    base.update(overrides)
    return base


def _cleanup_demo_applicants() -> None:
    from scripts.ops.create_demo_ppr_applicants import _delete_person_demo_data, rollback_demo_applicants

    with engine.begin() as conn:
        rollback_demo_applicants(conn, execute=True)
        for spec in APPLICANTS:
            audit = audit_person_by_iin(conn, iin=spec["iin"], expected_name=spec["full_name"])
            if audit.exists and audit.person_id is not None and audit.demo_marked:
                _delete_person_demo_data(conn, int(audit.person_id))


@pytest.fixture()
def allow_demo_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORPSITE_ALLOW_DEMO_PPR_SEED", "1")


def test_demo_seed_payloads_match_wp_pr_031_spec() -> None:
    ahmetov = DEMO_MILITARY_BY_KEY["ahmetov"]
    seitova = DEMO_MILITARY_BY_KEY["seitova"]
    assert ahmetov["record_kind"] == MILITARY_RECORD_KIND_REGISTRATION
    assert ahmetov["military_rank"] == "рядовой"
    assert ahmetov["military_specialty_code"] == "868123А"
    assert seitova["record_kind"] == MILITARY_RECORD_KIND_NOT_APPLICABLE
    assert "notes" in seitova
    for forbidden in (
        "obligation_status",
        "military_rank",
        "registered_at",
        "military_id_book_number",
    ):
        assert forbidden not in seitova


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL unavailable")
def test_sequential_demo_seed_includes_military_idempotently(allow_demo_seed: None) -> None:
    _require_db()
    os.environ["CORPSITE_ALLOW_DEMO_PPR_SEED"] = "1"
    _cleanup_demo_applicants()

    run_applicants(execute=True)
    run_employment_biography(execute=True)
    first = run_military_seed(execute=True)
    assert first.created == 2

    second = run_military_seed(execute=True)
    assert second.created == 0
    assert second.skipped == 2

    with engine.connect() as conn:
        ahmetov = audit_person_by_iin(
            conn,
            iin=APPLICANTS[0]["iin"],
            expected_name=APPLICANTS[0]["full_name"],
        )
        seitova = audit_person_by_iin(
            conn,
            iin=APPLICANTS[1]["iin"],
            expected_name=APPLICANTS[1]["full_name"],
        )
        assert ahmetov.person_id is not None
        assert seitova.person_id is not None

        ahmetov_row = conn.execute(
            text(
                """
                SELECT record_kind, military_rank, obligation_status, notes
                FROM public.person_military_service
                WHERE person_id = :person_id AND lifecycle_status = 'active'
                """
            ),
            {"person_id": ahmetov.person_id},
        ).mappings().one()
        seitova_row = conn.execute(
            text(
                """
                SELECT record_kind, military_rank, obligation_status, notes
                FROM public.person_military_service
                WHERE person_id = :person_id AND lifecycle_status = 'active'
                """
            ),
            {"person_id": seitova.person_id},
        ).mappings().one()

    assert ahmetov_row["record_kind"] == MILITARY_RECORD_KIND_REGISTRATION
    assert ahmetov_row["military_rank"] == "рядовой"
    assert ahmetov_row["obligation_status"] == "liable"
    assert seitova_row["record_kind"] == MILITARY_RECORD_KIND_NOT_APPLICABLE
    assert seitova_row["military_rank"] is None
    assert seitova_row["obligation_status"] is None


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL unavailable")
def test_smoke_supersede_moves_prior_record_to_history(client, privileged_headers) -> None:
    _require_db()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"WP31 Smoke Supersede {suffix}")
    _materialize(person_id)

    section = PprSectionApplicationService(authorization=AllowAllAuthorizationPort())
    created = section.create_military_service(
        PprCommandEnvelope(
            command_id=f"cre-{uuid4().hex}",
            command_type=COMMAND_TYPE_CREATE_MILITARY_SERVICE,
            actor_id="wp31-smoke",
            requested_at=datetime.now(UTC),
            payload=_registration_payload(military_rank="рядовой (A)"),
            person_id=person_id,
        )
    )
    assert created.section_record_id is not None
    with engine.begin() as conn:
        updated_at = conn.execute(
            text("SELECT updated_at FROM public.person_military_service WHERE military_id = :rid"),
            {"rid": created.section_record_id},
        ).scalar_one()

    section.supersede_military_service(
        PprCommandEnvelope(
            command_id=f"sup-{uuid4().hex}",
            command_type=COMMAND_TYPE_SUPERSEDE_MILITARY_SERVICE,
            actor_id="wp31-smoke",
            requested_at=datetime.now(UTC),
            payload={
                "record_id": created.section_record_id,
                "expected_updated_at": updated_at,
                "replacement": _registration_payload(military_rank="ефрейтор (B)"),
            },
            person_id=person_id,
        )
    )

    response = client.get(f"/api/ppr/persons/{person_id}", headers=privileged_headers)
    assert response.status_code == 200, response.text
    military = response.json()["sections"][SECTION_CODE_PPR_MILITARY]
    assert len(military["active"]) == 1
    assert military["active"][0]["military_rank"] == "ефрейтор (B)"
    assert len(military["superseded"]) == 1
    assert military["superseded"][0]["military_rank"] == "рядовой (A)"

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL unavailable")
def test_smoke_void_moves_active_to_voided(client, privileged_headers) -> None:
    _require_db()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"WP31 Smoke Void {suffix}")
    _materialize(person_id)

    section = PprSectionApplicationService(authorization=AllowAllAuthorizationPort())
    created = section.create_military_service(
        PprCommandEnvelope(
            command_id=f"cre-{uuid4().hex}",
            command_type=COMMAND_TYPE_CREATE_MILITARY_SERVICE,
            actor_id="wp31-smoke",
            requested_at=datetime.now(UTC),
            payload=_registration_payload(),
            person_id=person_id,
        )
    )
    assert created.section_record_id is not None
    with engine.begin() as conn:
        updated_at = conn.execute(
            text("SELECT updated_at FROM public.person_military_service WHERE military_id = :rid"),
            {"rid": created.section_record_id},
        ).scalar_one()

    section.void_military_service(
        PprCommandEnvelope(
            command_id=f"void-{uuid4().hex}",
            command_type=COMMAND_TYPE_VOID_MILITARY_SERVICE,
            actor_id="wp31-smoke",
            requested_at=datetime.now(UTC),
            payload={
                "record_id": created.section_record_id,
                "reason": "smoke void",
                "expected_updated_at": updated_at,
            },
            person_id=person_id,
        )
    )

    response = client.get(f"/api/ppr/persons/{person_id}", headers=privileged_headers)
    assert response.status_code == 200
    military = response.json()["sections"][SECTION_CODE_PPR_MILITARY]
    assert military["active"] == []
    assert len(military["voided"]) == 1

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL unavailable")
def test_smoke_not_applicable_via_person_route(client, privileged_headers) -> None:
    _require_db()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"WP31 Smoke NA {suffix}")
    _materialize(person_id)

    section = PprSectionApplicationService(authorization=AllowAllAuthorizationPort())
    section.create_military_service(
        PprCommandEnvelope(
            command_id=f"cre-{uuid4().hex}",
            command_type=COMMAND_TYPE_CREATE_MILITARY_SERVICE,
            actor_id="wp31-smoke",
            requested_at=datetime.now(UTC),
            payload={
                "record_kind": MILITARY_RECORD_KIND_NOT_APPLICABLE,
                "notes": "Не подлежит воинскому учёту",
                "source_type": SECTION_SOURCE_TYPE_ENTERED,
            },
            person_id=person_id,
        )
    )

    response = client.get(f"/api/ppr/persons/{person_id}", headers=privileged_headers)
    assert response.status_code == 200
    record = response.json()["sections"][SECTION_CODE_PPR_MILITARY]["active"][0]
    assert record["record_kind"] == MILITARY_RECORD_KIND_NOT_APPLICABLE
    assert record["notes"] == "Не подлежит воинскому учёту"
    assert record.get("military_rank") is None
    assert "military_id_book_number" not in record

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL unavailable")
def test_smoke_employee_route_returns_military_section(client, privileged_headers) -> None:
    _require_db()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"WP31 Smoke Emp {suffix}")
        employee_id = insert_employee(conn, full_name=f"WP31 Emp {suffix}", person_id=person_id)
    _materialize(person_id)

    section = PprSectionApplicationService(authorization=AllowAllAuthorizationPort())
    section.create_military_service(
        PprCommandEnvelope(
            command_id=f"cre-{uuid4().hex}",
            command_type=COMMAND_TYPE_CREATE_MILITARY_SERVICE,
            actor_id="wp31-smoke",
            requested_at=datetime.now(UTC),
            payload=_registration_payload(military_rank="сержант"),
            person_id=person_id,
        )
    )

    response = client.get(f"/api/ppr/employees/{employee_id}", headers=privileged_headers)
    assert response.status_code == 200
    military = response.json()["sections"][SECTION_CODE_PPR_MILITARY]
    assert len(military["active"]) == 1
    assert military["active"][0]["military_rank"] == "сержант"

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[employee_id])


def test_demo_section_coverage_manifest() -> None:
    """Demo consistency manifest — documents which PPR sections ops seed provides."""
    ops_sections = {
        "general": "create_demo_ppr_applicants (envelope + person scalars)",
        "education": "create_demo_ppr_applicants",
        "training": "create_demo_ppr_applicants (ahmetov only)",
        "employment_biography": "seed_demo_employment_biography",
        "military": "seed_demo_military_service",
    }
    missing_in_ops = ["family"]
    assert "military" in ops_sections
    assert missing_in_ops == ["family"]
