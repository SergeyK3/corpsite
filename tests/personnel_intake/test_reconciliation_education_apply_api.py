"""API integration tests for education reconciliation decision apply."""
from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_migration import EDUCATION_KIND_BASIC, LIFECYCLE_STATUS_ACTIVE
from app.main import app
from app.personnel_intake.application.reconciliation.dto import DecideSectionCommand
from app.personnel_intake.application.reconciliation.engine import ReconciliationDecisionEngine
from app.personnel_intake.application.reconciliation.plugins.education import (
    EducationReconciliationPlugin,
)
from app.personnel_intake.application.reconciliation.registry import SectionReconciliationRegistry
from app.personnel_intake.domain.reconciliation.actions import (
    APPLY_STATUS_APPLIED,
    APPLY_STATUS_BLOCKED,
    REASON_APPLY_STALE_ROW_VERSION,
    RECONCILE_ACTION_ADD,
    RECONCILE_ACTION_KEEP_EXISTING,
)
from app.personnel_intake.infrastructure.reconciliation_repository import (
    SqlAlchemyReconciliationDecisionRepository,
)
from app.ppr.application.authorization import AllowAllAuthorizationPort
from app.ppr.application.command_models import (
    COMMAND_TYPE_MATERIALIZE_PPR,
    MaterializePprPayload,
    PprCommandEnvelope,
)
from app.ppr.application.lifecycle_service import PprLifecycleApplicationService
from app.ppr.application.uow_participation import bind_participating_uow
from app.ppr.domain.section_models import EducationRecord
from app.ppr.infrastructure.section_repository import (
    SqlAlchemySectionMutationRepository,
    SqlAlchemySectionReadRepository,
)
from tests.conftest import auth_headers, insert_returning_id, table_exists
from tests.personnel_intake.edu_plugin_helpers import intake_row
from tests.ppr.conftest import cleanup_person_graph, insert_person, ppr_db_available

TABLE = "personnel_intake_reconciliation_decisions"
APPLY_PATH = (
    "/directory/personnel-applications/{application_id}/intake/reconciliation/"
    "decisions/{decision_id}/apply"
)


def _require_schema() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, TABLE):
            pytest.skip(f"{TABLE} missing — run: alembic upgrade head")
        if not table_exists(conn, "person_education"):
            pytest.skip("person_education missing — run: alembic upgrade head")
        if not table_exists(conn, "personnel_record_metadata"):
            pytest.skip("personnel_record_metadata missing — run: alembic upgrade head")


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


def _engine() -> ReconciliationDecisionEngine:
    registry = SectionReconciliationRegistry()
    registry.register(EducationReconciliationPlugin())
    return ReconciliationDecisionEngine(registry)


def _seed(conn, seed):
    person_id = insert_person(conn, full_name=f"Edu Apply API {uuid4().hex[:6]}")
    application_id = insert_returning_id(
        conn,
        table="personnel_applications",
        id_col="application_id",
        values={
            "person_id": person_id,
            "application_received_at": date(2026, 7, 24),
            "registered_by_user_id": int(seed["initiator_user_id"]),
            "idempotency_key": f"edu-apply-api-{uuid4().hex}",
        },
    )
    return person_id, application_id


def _materialize(conn, person_id: int) -> None:
    uow = bind_participating_uow(conn)
    lifecycle = PprLifecycleApplicationService(authorization=AllowAllAuthorizationPort())
    lifecycle.materialize_ppr_participating(
        uow,
        PprCommandEnvelope(
            command_id=f"mat-edu-api-{uuid4().hex}",
            command_type=COMMAND_TYPE_MATERIALIZE_PPR,
            actor_id="test-actor",
            requested_at=datetime.now(UTC),
            payload=MaterializePprPayload(),
            person_id=person_id,
        ),
    )


def _insert_education(conn, *, person_id: int, **overrides) -> EducationRecord:
    values = dict(
        institution_name="МГУ",
        education_kind=EDUCATION_KIND_BASIC,
        specialty="Математика",
        qualification="Бакалавр",
        started_at=date(2015, 9, 1),
        completed_at=date(2019, 6, 30),
        diploma_number="D-1",
        document_type="diploma",
    )
    values.update(overrides)
    document_type = values.pop("document_type", "diploma")
    metadata = {"document_type": document_type} if document_type is not None else {}
    inserted = SqlAlchemySectionMutationRepository(conn).insert_record(
        EducationRecord(
            person_id=person_id,
            metadata=metadata or None,
            lifecycle_status=LIFECYCLE_STATUS_ACTIVE,
            **values,
        )
    )
    assert inserted.record_id is not None
    return inserted


def _decide(conn, *, application_id: int, person_id: int, records: list[dict]):
    return _engine().decide_section(
        conn,
        DecideSectionCommand(
            application_id=application_id,
            person_id=person_id,
            section_code="education",
            section_payload={"records": records},
            decision_source="system",
            correlation_id="edu-apply-api",
            digest_algorithm_version="canon-json-v1",
        ),
    )


def _active_education_count(conn, person_id: int) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT count(*)
                FROM public.person_education
                WHERE person_id = :person_id AND lifecycle_status = 'active'
                """
            ),
            {"person_id": person_id},
        ).scalar_one()
    )


def _cleanup(person_id: int, decision_ids: list[int]) -> None:
    with engine.begin() as conn:
        if decision_ids:
            conn.execute(
                text(
                    """
                    DELETE FROM public.personnel_intake_reconciliation_decisions
                    WHERE decision_id = ANY(:ids)
                    """
                ),
                {"ids": decision_ids},
            )
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])


def _apply_url(application_id: int, decision_id: int) -> str:
    return APPLY_PATH.format(application_id=application_id, decision_id=decision_id)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_api_apply_add_commits_ppr_and_status(client, privileged_headers, seed) -> None:
    _require_schema()
    records = [intake_row(institution="API Add Uni")]
    with engine.begin() as setup:
        person_id, application_id = _seed(setup, seed)
        _materialize(setup, person_id)
        decided = _decide(
            setup, application_id=application_id, person_id=person_id, records=records
        )
        decision = decided.decisions[0].decision
        assert decision.action == RECONCILE_ACTION_ADD
        decision_id = int(decision.decision_id)

    try:
        resp = client.post(
            _apply_url(application_id, decision_id),
            headers=privileged_headers,
            json={"section_payload": {"records": records}},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["apply_status"] == APPLY_STATUS_APPLIED
        assert body["result_status"] == "applied"
        assert body["action"] == RECONCILE_ACTION_ADD
        assert body["section_record_id"] is not None
        section_record_id = int(body["section_record_id"])

        with engine.connect() as verify:
            reloaded = SqlAlchemyReconciliationDecisionRepository(verify).require_by_id(
                decision_id
            )
            assert reloaded.apply_status == APPLY_STATUS_APPLIED
            assert _active_education_count(verify, person_id) == 1
            loaded = SqlAlchemySectionReadRepository(verify).load_record(
                person_id, "PPR-EDUCATION", section_record_id
            )
            assert isinstance(loaded, EducationRecord)
            assert loaded.institution_name == "API Add Uni"
            assert (loaded.metadata or {}).get("reconciliation_decision_id") == decision_id
    finally:
        _cleanup(person_id, [decision_id])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_api_apply_keep_existing_no_ppr_mutation(client, privileged_headers, seed) -> None:
    _require_schema()
    records = [intake_row(institution="API Keep Uni")]
    with engine.begin() as setup:
        person_id, application_id = _seed(setup, seed)
        _materialize(setup, person_id)
        row = _insert_education(setup, person_id=person_id, institution_name="API Keep Uni")
        decided = _decide(
            setup, application_id=application_id, person_id=person_id, records=records
        )
        decision = decided.decisions[0].decision
        assert decision.action == RECONCILE_ACTION_KEEP_EXISTING
        decision_id = int(decision.decision_id)
        before_count = _active_education_count(setup, person_id)

    try:
        resp = client.post(
            _apply_url(application_id, decision_id),
            headers=privileged_headers,
            json={"section_payload": {"records": records}},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["apply_status"] == APPLY_STATUS_APPLIED
        assert body["result_status"] == "applied"
        assert body["section_record_id"] is None

        with engine.connect() as verify:
            assert _active_education_count(verify, person_id) == before_count
            loaded = SqlAlchemySectionReadRepository(verify).load_record(
                person_id, "PPR-EDUCATION", int(row.record_id)
            )
            assert isinstance(loaded, EducationRecord)
            assert loaded.updated_at == row.updated_at
            assert (loaded.metadata or {}).get("reconciliation_decision_id") is None
    finally:
        _cleanup(person_id, [decision_id])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_api_apply_terminal_replay(client, privileged_headers, seed) -> None:
    _require_schema()
    records = [intake_row(institution="API Replay Uni")]
    with engine.begin() as setup:
        person_id, application_id = _seed(setup, seed)
        _materialize(setup, person_id)
        decided = _decide(
            setup, application_id=application_id, person_id=person_id, records=records
        )
        decision_id = int(decided.decisions[0].decision.decision_id)

    try:
        first = client.post(
            _apply_url(application_id, decision_id),
            headers=privileged_headers,
            json={"section_payload": {"records": records}},
        )
        assert first.status_code == 200, first.text
        assert first.json()["apply_status"] == APPLY_STATUS_APPLIED

        second = client.post(
            _apply_url(application_id, decision_id),
            headers=privileged_headers,
            json={"section_payload": {"records": records}},
        )
        assert second.status_code == 200, second.text
        body = second.json()
        assert body["idempotent_replay"] is True
        assert body["result_status"] == "idempotent_replay"
        assert body["apply_status"] == APPLY_STATUS_APPLIED

        with engine.connect() as verify:
            assert _active_education_count(verify, person_id) == 1
    finally:
        _cleanup(person_id, [decision_id])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_api_apply_blocked_when_canonical_changed(client, privileged_headers, seed) -> None:
    _require_schema()
    records = [intake_row(specialty="Химия")]
    with engine.begin() as setup:
        person_id, application_id = _seed(setup, seed)
        _materialize(setup, person_id)
        row = _insert_education(setup, person_id=person_id, specialty=None)
        decided = _decide(
            setup, application_id=application_id, person_id=person_id, records=records
        )
        decision = decided.decisions[0].decision
        decision_id = int(decision.decision_id)
        setup.execute(
            text(
                """
                UPDATE public.person_education
                SET specialty = 'Биология',
                    updated_at = clock_timestamp()
                WHERE education_id = :record_id
                  AND person_id = :person_id
                """
            ),
            {"record_id": int(row.record_id), "person_id": person_id},
        )

    try:
        resp = client.post(
            _apply_url(application_id, decision_id),
            headers=privileged_headers,
            json={"section_payload": {"records": records}},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["apply_status"] == APPLY_STATUS_BLOCKED
        assert body["result_status"] == "blocked_new_decide_required"
        assert body["reason_code"] == REASON_APPLY_STALE_ROW_VERSION
        assert body["redecide_required"] is True
        assert body["failure_evidence"] is not None

        with engine.connect() as verify:
            loaded = SqlAlchemySectionReadRepository(verify).load_record(
                person_id, "PPR-EDUCATION", int(row.record_id)
            )
            assert isinstance(loaded, EducationRecord)
            assert loaded.specialty == "Биология"
            assert (loaded.metadata or {}).get("reconciliation_decision_id") is None
            reloaded = SqlAlchemyReconciliationDecisionRepository(verify).require_by_id(
                decision_id
            )
            assert reloaded.apply_status == APPLY_STATUS_BLOCKED
    finally:
        _cleanup(person_id, [decision_id])
