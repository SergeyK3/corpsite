# tests/test_regular_tasks_trigger_source.py
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.services.regular_tasks_service import (
    TRIGGER_SOURCE_AUTOMATIC,
    TRIGGER_SOURCE_CATCH_UP,
    TRIGGER_SOURCE_MANUAL,
    TRIGGER_SOURCE_TEST,
    resolve_trigger_source,
    run_regular_tasks_catch_up_tx,
    run_regular_tasks_generation_tx,
)
from app.services.tasks_service import SYSTEM_ADMIN_ROLE_ID


def test_resolve_trigger_source_matrix():
    assert resolve_trigger_source(dry_run=True) == TRIGGER_SOURCE_TEST
    assert (
        resolve_trigger_source(dry_run=False, catch_up_meta={"preset": "past_week"})
        == TRIGGER_SOURCE_CATCH_UP
    )
    assert (
        resolve_trigger_source(dry_run=False, trigger_source_hint="manual")
        == TRIGGER_SOURCE_MANUAL
    )
    assert (
        resolve_trigger_source(dry_run=False, trigger_source_hint="automatic")
        == TRIGGER_SOURCE_AUTOMATIC
    )
    assert resolve_trigger_source(dry_run=False) == TRIGGER_SOURCE_AUTOMATIC


def test_run_endpoint_sets_manual_trigger_source(monkeypatch):
    captured: dict[str, object] = {}

    def fake_generation_tx(conn, **kwargs):
        captured.update(kwargs)
        return 101, {"trigger_source": kwargs.get("trigger_source_hint"), "dry_run": kwargs.get("dry_run")}

    mock_conn = MagicMock()
    mock_tx = MagicMock()
    mock_tx.__enter__.return_value = mock_conn
    mock_tx.__exit__.return_value = False

    monkeypatch.setattr("app.services.regular_tasks_router.engine.begin", lambda: mock_tx)
    monkeypatch.setattr(
        "app.services.regular_tasks_router.run_regular_tasks_generation_tx",
        fake_generation_tx,
    )
    monkeypatch.setattr(
        "app.services.regular_tasks_router._resolve_runner_user",
        lambda **_: {"user_id": 1, "role_id": int(SYSTEM_ADMIN_ROLE_ID)},
    )

    client = TestClient(app)
    response = client.post(
        "/internal/regular-tasks/run",
        json={"dry_run": False},
        headers={"Authorization": "Bearer pytest-token"},
    )

    assert response.status_code == 200, response.text
    assert captured["trigger_source_hint"] == TRIGGER_SOURCE_MANUAL


def test_run_endpoint_sets_automatic_trigger_source_for_internal_token(monkeypatch):
    captured: dict[str, object] = {}

    def fake_generation_tx(conn, **kwargs):
        captured.update(kwargs)
        return 102, {"trigger_source": TRIGGER_SOURCE_AUTOMATIC, "dry_run": False}

    mock_conn = MagicMock()
    mock_tx = MagicMock()
    mock_tx.__enter__.return_value = mock_conn
    mock_tx.__exit__.return_value = False

    monkeypatch.setattr("app.services.regular_tasks_router.engine.begin", lambda: mock_tx)
    monkeypatch.setattr(
        "app.services.regular_tasks_router.run_regular_tasks_generation_tx",
        fake_generation_tx,
    )
    monkeypatch.setattr(
        "app.services.regular_tasks_router.has_valid_internal_api_token",
        lambda _token: True,
    )
    monkeypatch.setattr(
        "app.services.regular_tasks_router._resolve_runner_user",
        lambda **_: {"user_id": 1, "role_id": int(SYSTEM_ADMIN_ROLE_ID)},
    )

    client = TestClient(app)
    response = client.post(
        "/internal/regular-tasks/run",
        json={"dry_run": False},
        headers={
            "X-Internal-Api-Token": "pytest-internal-token",
            "X-User-Id": "1",
        },
    )

    assert response.status_code == 200, response.text
    assert captured["trigger_source_hint"] == TRIGGER_SOURCE_AUTOMATIC


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_generation_tx_persists_trigger_source_in_stats():
    with engine.begin() as conn:
        run_id, stats = run_regular_tasks_generation_tx(
            conn,
            dry_run=True,
            force_due=True,
            trigger_source_hint=TRIGGER_SOURCE_MANUAL,
        )

        row = conn.execute(
            text("SELECT stats FROM public.regular_task_runs WHERE run_id = :rid"),
            {"rid": int(run_id)},
        ).scalar_one()

        conn.execute(text("DELETE FROM public.regular_task_runs WHERE run_id = :rid"), {"rid": int(run_id)})

    assert stats["trigger_source"] == TRIGGER_SOURCE_TEST
    assert row["trigger_source"] == TRIGGER_SOURCE_TEST


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_catch_up_live_persists_catch_up_trigger_source():
    with engine.begin() as conn:
        run_id, stats, _resolved = run_regular_tasks_catch_up_tx(
            conn,
            preset="manual",
            dry_run=False,
            run_for_date_manual=date(2026, 3, 5),
            schedule_type="weekly",
            org_unit_id=999999,
        )

        conn.execute(text("DELETE FROM public.regular_task_runs WHERE run_id = :rid"), {"rid": int(run_id)})

    assert stats["trigger_source"] == TRIGGER_SOURCE_CATCH_UP
