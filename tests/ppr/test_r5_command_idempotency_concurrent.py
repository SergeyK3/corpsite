# tests/ppr/test_r5_command_idempotency_concurrent.py
"""Concurrent command_id idempotency tests (R5)."""
from __future__ import annotations

import threading
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.ppr.application.authorization import AllowAllAuthorizationPort
from app.ppr.application.command_models import COMMAND_TYPE_MATERIALIZE_PPR, MaterializePprPayload, PprCommandEnvelope
from app.ppr.application.lifecycle_service import PprLifecycleApplicationService
from app.ppr.application.results import RESULT_STATUS_COMMITTED, RESULT_STATUS_IDEMPOTENT_REPLAY
from app.ppr.domain.errors import PprCommandInProgressError
from tests.conftest import table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_person, ppr_db_available, require_ppr_schema


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_concurrent_command_id_single_mutation() -> None:
    require_ppr_schema()
    with engine.begin() as conn:
        if not table_exists(conn, "ppr_command_executions"):
            pytest.skip("ppr_command_executions missing")
        person_id = insert_person(conn, full_name=f"Concurrent {uuid4().hex[:8]}")

    command_id = f"conc-{uuid4().hex}"
    service = PprLifecycleApplicationService(authorization=AllowAllAuthorizationPort())
    results: list = []
    errors: list = []

    def worker() -> None:
        try:
            env = PprCommandEnvelope(
                command_id=command_id,
                command_type=COMMAND_TYPE_MATERIALIZE_PPR,
                actor_id="conc-actor",
                requested_at=datetime.now(UTC),
                payload=MaterializePprPayload(),
                person_id=person_id,
            )
            results.append(service.materialize_ppr(env))
        except PprCommandInProgressError as exc:
            errors.append(exc)
        except Exception as exc:
            errors.append(exc)

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(results) + len(errors) == 2
    committed = [r for r in results if r.status == RESULT_STATUS_COMMITTED]
    replayed = [r for r in results if r.status == RESULT_STATUS_IDEMPOTENT_REPLAY]
    assert len(committed) == 1
    assert len(replayed) + len([e for e in errors if isinstance(e, PprCommandInProgressError)]) >= 0
    assert len(replayed) == 1 or any(isinstance(e, PprCommandInProgressError) for e in errors)

    with engine.begin() as conn:
        meta = conn.execute(
            text("SELECT COUNT(*) FROM public.personnel_record_metadata WHERE person_id = :pid"),
            {"pid": person_id},
        ).scalar_one()
        events = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.personnel_record_events
                WHERE person_id = :pid AND event_type = 'PPR_CREATED'
                """
            ),
            {"pid": person_id},
        ).scalar_one()
        cmds = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.ppr_command_executions
                WHERE command_id = :cid AND status = 'completed'
                """
            ),
            {"cid": command_id},
        ).scalar_one()
    assert int(meta) == 1
    assert int(events) == 1
    assert int(cmds) == 1

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])
