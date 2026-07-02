# tests/test_scheduler_status_route.py
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.main import app

# Browser same-origin URL (see docs/ops/NGINX_SAME_ORIGIN_API_RUNBOOK.md):
# GET /api/regular-tasks/scheduler-status → nginx strips /api → FastAPI path below.
BROWSER_SCHEDULER_STATUS_PATH = "/api/regular-tasks/scheduler-status"
FASTAPI_SCHEDULER_STATUS_PATH = "/regular-tasks/scheduler-status"


def _regular_tasks_route_paths() -> list[str]:
    return [
        route.path
        for route in app.routes
        if hasattr(route, "path") and route.path.startswith("/regular-tasks")
    ]


def test_scheduler_status_route_registered_before_regular_task_id_param():
    """Static route must be registered before /regular-tasks/{regular_task_id}."""
    paths = _regular_tasks_route_paths()
    scheduler_idx = paths.index(FASTAPI_SCHEDULER_STATUS_PATH)
    param_idx = paths.index("/regular-tasks/{regular_task_id}")
    assert scheduler_idx < param_idx


def test_api_scheduler_status_route_not_shadowed_by_regular_task_id():
    """GET /api/regular-tasks/scheduler-status must not match /regular-tasks/{regular_task_id}."""
    fake_user = {"user_id": 1, "role_id": 2, "is_active": True}
    payload = {
        "automatic_enabled": False,
        "status": "no_data",
        "status_label": "off",
        "status_explanation": "test",
        "observation_window_days": 8,
        "last_result_label": "-",
        "hint": "hint",
        "recommended_action": {"label": "none", "href": None, "kind": "none"},
        "checked_at": "2026-07-02T12:00:00+05:00",
        "period_diagnostics": [],
        "automatic_runs_in_journal": 0,
    }

    @contextmanager
    def fake_begin():
        yield MagicMock()

    app.dependency_overrides[get_current_user] = lambda: fake_user
    try:
        with patch("app.services.regular_tasks_public_router.engine.begin", fake_begin):
            with patch(
                "app.services.regular_tasks_public_router.build_regular_task_scheduler_status",
                return_value=payload,
            ):
                client = TestClient(app, raise_server_exceptions=False)
                resp = client.get(FASTAPI_SCHEDULER_STATUS_PATH)

        assert resp.status_code == 200, (
            f"{BROWSER_SCHEDULER_STATUS_PATH} (effective {FASTAPI_SCHEDULER_STATUS_PATH}): {resp.text}"
        )
        assert "int_parsing" not in resp.text
        body = resp.json()
        assert body["status"] == "no_data"
        assert body["status_explanation"] == "test"
        assert body["recommended_action"]["kind"] == "none"
    finally:
        app.dependency_overrides.clear()


def test_api_scheduler_status_without_auth_returns_401_not_422():
    """Unauthenticated browser call must fail auth (401), not path parsing (422)."""
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get(FASTAPI_SCHEDULER_STATUS_PATH)

    assert resp.status_code == 401, (
        f"{BROWSER_SCHEDULER_STATUS_PATH} (effective {FASTAPI_SCHEDULER_STATUS_PATH}): {resp.text}"
    )
    assert "int_parsing" not in resp.text
    detail = resp.json().get("detail")
    if isinstance(detail, list):
        locs = [item.get("loc") for item in detail if isinstance(item, dict)]
        assert ["path", "regular_task_id"] not in locs
