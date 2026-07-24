"""API integration tests for listing reconciliation decisions (WP-011 read path)."""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.personnel_intake.application.reconciliation.dto import DecideSectionCommand
from app.personnel_intake.application.reconciliation.engine import ReconciliationDecisionEngine
from app.personnel_intake.application.reconciliation.plugins.education import (
    EducationReconciliationPlugin,
)
from app.personnel_intake.application.reconciliation.registry import SectionReconciliationRegistry
from tests.conftest import auth_headers, insert_returning_id, table_exists
from tests.personnel_intake.edu_plugin_helpers import intake_row
from tests.ppr.conftest import cleanup_person_graph, insert_person, ppr_db_available

TABLE = "personnel_intake_reconciliation_decisions"
LIST_PATH = "/directory/personnel-applications/{application_id}/intake/reconciliation/decisions"


def _require_schema() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, TABLE):
            pytest.skip(f"{TABLE} missing — run: alembic upgrade head")


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
    person_id = insert_person(conn, full_name=f"Recon List API {uuid4().hex[:6]}")
    application_id = insert_returning_id(
        conn,
        table="personnel_applications",
        id_col="application_id",
        values={
            "person_id": person_id,
            "application_received_at": date(2026, 7, 24),
            "registered_by_user_id": int(seed["initiator_user_id"]),
            "idempotency_key": f"recon-list-api-{uuid4().hex}",
        },
    )
    other_person_id = insert_person(conn, full_name=f"Recon List Other {uuid4().hex[:6]}")
    other_application_id = insert_returning_id(
        conn,
        table="personnel_applications",
        id_col="application_id",
        values={
            "person_id": other_person_id,
            "application_received_at": date(2026, 7, 24),
            "registered_by_user_id": int(seed["initiator_user_id"]),
            "idempotency_key": f"recon-list-other-{uuid4().hex}",
        },
    )
    return person_id, application_id, other_person_id, other_application_id


def _decide(conn, *, application_id: int, person_id: int) -> int:
    records = [intake_row(institution="List API Uni")]
    result = _engine().decide_section(
        conn,
        DecideSectionCommand(
            application_id=application_id,
            person_id=person_id,
            section_code="education",
            section_payload={"records": records},
            decision_source="system",
            correlation_id="recon-list-api",
            digest_algorithm_version="canon-json-v1",
        ),
    )
    return int(result.decisions[0].decision.decision_id)


def _list_url(application_id: int, *, section_code: str | None = "education") -> str:
    path = LIST_PATH.format(application_id=application_id)
    if section_code is None:
        return path
    return f"{path}?section_code={section_code}"


def _cleanup(*person_ids: int, decision_ids: list[int]) -> None:
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
        cleanup_person_graph(conn, person_ids=list(person_ids), employee_ids=[])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_list_reconciliation_decisions_empty_200(client, privileged_headers, seed) -> None:
    _require_schema()
    with engine.begin() as setup:
        person_id, application_id, _, _ = _seed(setup, seed)

    try:
        res = client.get(_list_url(application_id), headers=privileged_headers)
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["application_id"] == application_id
        assert body["section_code"] == "education"
        assert body["items"] == []
        assert body["total"] == 0
    finally:
        _cleanup(person_id, decision_ids=[])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_list_reconciliation_decisions_scoped_to_application_and_section(
    client, privileged_headers, seed
) -> None:
    _require_schema()
    decision_ids: list[int] = []
    with engine.begin() as setup:
        person_id, application_id, other_person_id, other_application_id = _seed(setup, seed)
        decision_ids.append(_decide(setup, application_id=application_id, person_id=person_id))
        decision_ids.append(
            _decide(setup, application_id=other_application_id, person_id=other_person_id)
        )

    try:
        res = client.get(_list_url(application_id), headers=privileged_headers)
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1
        item = body["items"][0]
        assert item["application_id"] == application_id
        assert item["person_id"] == person_id
        assert item["section_code"] == "education"
        assert item["decision_id"] == decision_ids[0]

        other_section = client.get(
            _list_url(application_id, section_code="personal"),
            headers=privileged_headers,
        )
        assert other_section.status_code == 200, other_section.text
        other_section_body = other_section.json()
        assert other_section_body["application_id"] == application_id
        assert other_section_body["section_code"] == "personal"
        assert other_section_body["items"] == []
        assert other_section_body["total"] == 0
    finally:
        _cleanup(person_id, other_person_id, decision_ids=decision_ids)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_list_reconciliation_decisions_requires_hr_admin(client, seed, monkeypatch) -> None:
    _require_schema()
    monkeypatch.delenv("DIRECTORY_PRIVILEGED_USER_IDS", raising=False)
    with engine.begin() as setup:
        person_id, application_id, other_person_id, _ = _seed(setup, seed)

    try:
        res = client.get(_list_url(application_id), headers=auth_headers(seed["executor_user_id"]))
        assert res.status_code == 403
    finally:
        _cleanup(person_id, other_person_id, decision_ids=[])
