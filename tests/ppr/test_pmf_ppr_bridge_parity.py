# tests/ppr/test_pmf_ppr_bridge_parity.py
"""PMF entry-point parity tests for PPR bridge (flag OFF/ON)."""
from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_migration import (
    DOMAIN_CODE_EDUCATION,
    EDUCATION_KIND_BASIC,
    EVENT_TYPE_EDUCATION_MIGRATED,
    ITEM_STATUS_COMMITTED,
    LIFECYCLE_STATUS_ACTIVE,
    RUN_STATUS_COMMITTED,
    TRAINING_KIND_COURSE,
)
from app.services.education_migration_plugin import RECORD_KIND_EDUCATION, RECORD_KIND_TRAINING
from app.services.personnel_migration_commit_service import (
    add_draft_item_tx,
    commit_run_tx,
    create_draft_run_tx,
    void_run_tx,
)
from tests.conftest import get_columns, insert_returning_id, table_exists
from tests.test_pmf_1_schema import _require_schema

ACTOR_ID = "pmf-bridge-test-actor"


@pytest.fixture(autouse=True)
def _reset_bridge_flag(monkeypatch):
    monkeypatch.delenv("PPR_PMF_BRIDGE_ENABLED", raising=False)
    monkeypatch.delenv("PPR_PMF_BRIDGE_ALLOW_PRODUCTION", raising=False)
    yield


def _insert_person(conn, *, full_name: str) -> int:
    suffix = uuid4().hex[:12]
    cols = get_columns(conn, "persons")
    values: dict = {"full_name": full_name}
    if "match_key" in cols:
        values["match_key"] = f"bridge:{suffix}"
    if "source" in cols:
        values["source"] = "manual"
    if "person_status" in cols:
        values["person_status"] = "active"
    return insert_returning_id(conn, table="persons", id_col="person_id", values=values)


def _insert_employee(conn, *, full_name: str, person_id: int) -> int:
    cols = get_columns(conn, "employees")
    values: dict = {"full_name": full_name, "is_active": True}
    if "employment_rate" in cols:
        values["employment_rate"] = 1.00
    if "person_id" in cols:
        values["person_id"] = person_id
    return insert_returning_id(conn, table="employees", id_col="employee_id", values=values)


@pytest.fixture
def bridge_fixture():
    _require_schema()
    with engine.begin() as conn:
        if not table_exists(conn, "ppr_command_executions"):
            pytest.skip("ppr_command_executions missing")
        person_id = _insert_person(conn, full_name=f"Bridge Person {uuid4().hex[:6]}")
        employee_id = _insert_employee(conn, full_name=f"Bridge Emp {uuid4().hex[:6]}", person_id=person_id)
    yield {"person_id": person_id, "employee_id": employee_id}
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM public.ppr_command_executions WHERE person_id = :pid"), {"pid": person_id})
        conn.execute(text("DELETE FROM public.personnel_record_events WHERE person_id = :pid"), {"pid": person_id})
        conn.execute(text("DELETE FROM public.person_education WHERE person_id = :pid"), {"pid": person_id})
        conn.execute(text("DELETE FROM public.person_training WHERE person_id = :pid"), {"pid": person_id})
        conn.execute(text("DELETE FROM public.personnel_record_metadata WHERE person_id = :pid"), {"pid": person_id})
        conn.execute(
            text(
                """
                DELETE FROM public.personnel_migration_items
                WHERE run_id IN (
                    SELECT run_id FROM public.personnel_migration_runs WHERE person_id = :pid
                )
                """
            ),
            {"pid": person_id},
        )
        conn.execute(text("DELETE FROM public.personnel_migration_runs WHERE person_id = :pid"), {"pid": person_id})
        conn.execute(text("DELETE FROM public.employees WHERE employee_id = :eid"), {"eid": employee_id})
        conn.execute(text("DELETE FROM public.persons WHERE person_id = :pid"), {"pid": person_id})


def _create_education_run(employee_id: int) -> int:
    run = create_draft_run_tx(
        domain_code=DOMAIN_CODE_EDUCATION,
        employee_context_id=employee_id,
        actor_id=ACTOR_ID,
        allow_disabled_domain=True,
    )
    add_draft_item_tx(
        run_id=run["run_id"],
        source_kind="manual",
        record_kind=RECORD_KIND_EDUCATION,
        draft_payload={
            "education_kind": EDUCATION_KIND_BASIC,
            "institution_name": "Bridge University",
        },
    )
    return int(run["run_id"])


def test_bridge_off_legacy_commit(bridge_fixture, monkeypatch) -> None:
    monkeypatch.setenv("PPR_PMF_BRIDGE_ENABLED", "false")
    run_id = _create_education_run(bridge_fixture["employee_id"])
    result = commit_run_tx(run_id=run_id, actor_id=ACTOR_ID)
    assert result["run_status"] == RUN_STATUS_COMMITTED

    with engine.begin() as conn:
        legacy = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.personnel_record_events
                WHERE person_id = :pid AND event_type = :etype
                """
            ),
            {"pid": bridge_fixture["person_id"], "etype": EVENT_TYPE_EDUCATION_MIGRATED},
        ).scalar_one()
        canonical = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.personnel_record_events
                WHERE person_id = :pid AND event_type = 'PPR_SECTION_ADDED'
                """
            ),
            {"pid": bridge_fixture["person_id"]},
        ).scalar_one()
        cmd_rows = conn.execute(
            text("SELECT COUNT(*) FROM public.ppr_command_executions WHERE person_id = :pid"),
            {"pid": bridge_fixture["person_id"]},
        ).scalar_one()
    assert int(legacy) == 1
    assert int(canonical) == 0
    assert int(cmd_rows) == 0


def test_bridge_on_canonical_commit(bridge_fixture, monkeypatch) -> None:
    monkeypatch.setenv("PPR_PMF_BRIDGE_ENABLED", "true")
    run_id = _create_education_run(bridge_fixture["employee_id"])
    result = commit_run_tx(run_id=run_id, actor_id=ACTOR_ID)
    assert result["run_status"] == RUN_STATUS_COMMITTED
    assert len(result["event_ids"]) == 1

    with engine.begin() as conn:
        legacy = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.personnel_record_events
                WHERE person_id = :pid AND event_type = :etype
                """
            ),
            {"pid": bridge_fixture["person_id"], "etype": EVENT_TYPE_EDUCATION_MIGRATED},
        ).scalar_one()
        canonical = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.personnel_record_events
                WHERE person_id = :pid AND event_type = 'PPR_SECTION_ADDED'
                """
            ),
            {"pid": bridge_fixture["person_id"]},
        ).scalar_one()
        education_rows = conn.execute(
            text("SELECT COUNT(*) FROM public.person_education WHERE person_id = :pid"),
            {"pid": bridge_fixture["person_id"]},
        ).scalar_one()
        cmd_rows = conn.execute(
            text("SELECT COUNT(*) FROM public.ppr_command_executions WHERE person_id = :pid"),
            {"pid": bridge_fixture["person_id"]},
        ).scalar_one()
    assert int(legacy) == 0
    assert int(canonical) == 1
    assert int(education_rows) == 1
    assert int(cmd_rows) >= 1


def test_bridge_on_replay_no_duplicate(bridge_fixture, monkeypatch) -> None:
    monkeypatch.setenv("PPR_PMF_BRIDGE_ENABLED", "true")
    run_id = _create_education_run(bridge_fixture["employee_id"])
    first = commit_run_tx(run_id=run_id, actor_id=ACTOR_ID)
    with pytest.raises(Exception):
        commit_run_tx(run_id=run_id, actor_id=ACTOR_ID)
    del first
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT COUNT(*) FROM public.person_education WHERE person_id = :pid"),
            {"pid": bridge_fixture["person_id"]},
        ).scalar_one()
    assert int(rows) == 1
