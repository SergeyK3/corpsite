# tests/test_error_contract.py
from __future__ import annotations

import os
from typing import Any, Dict, Optional, Set, Callable

import pytest

try:
    from fastapi.testclient import TestClient
except Exception as e:
    raise RuntimeError("fastapi TestClient is required for tests") from e


# -------------------------
# Test config (known seeded users in your DB)
# -------------------------
USER_EXECUTOR = 2        # role_id = 1
USER_SUPERVISOR = 34     # role_id = 58 (in SUPERVISOR_ROLE_IDS)
ROLE_EXECUTOR = 1

DEFAULT_PERIOD_ID = int(os.getenv("TEST_PERIOD_ID", "2"))


# -------------------------
# Helpers
# -------------------------
def _ensure_env_for_rbac() -> None:
    """
    app/tasks.py reads SUPERVISOR_ROLE_IDS / DEPUTY_ROLE_IDS at import-time.
    For test stability we set defaults before importing app.main.
    """
    os.environ.setdefault("SUPERVISOR_ROLE_IDS", "58,59")
    os.environ.setdefault("DEPUTY_ROLE_IDS", "60")


def _make_client() -> TestClient:
    _ensure_env_for_rbac()
    from app.main import app  # noqa: WPS433

    return TestClient(app)


def _headers(user_id: int) -> Dict[str, str]:
    return {"X-User-Id": str(int(user_id))}


def _assert_business_error(body: Dict[str, Any], expected_error: str) -> Dict[str, Any]:
    """
    Contract for ADR-003/004 business errors:
      {"detail": {"error": "...", "message": "...", "reason": "...", "hint": "...", "code": "...", ...}}
    """
    assert "detail" in body, f"Expected 'detail' in response JSON, got: {body}"
    detail = body["detail"]
    assert isinstance(detail, dict), f"Expected detail to be object, got: {type(detail)}"

    for k in ("error", "message", "reason", "hint", "code"):
        assert k in detail, f"Missing detail.{k} in: {detail}"

    assert detail["error"] == expected_error, f"Expected error={expected_error}, got: {detail}"
    assert isinstance(detail["code"], str) and detail["code"], f"detail.code must be non-empty string: {detail}"
    return detail


def _create_task(
    c: TestClient,
    *,
    created_by_user_id: int,
    title: str,
    status_code: str,
    executor_role_id: int = ROLE_EXECUTOR,
    period_id: int = DEFAULT_PERIOD_ID,
    assignment_scope: str = "functional",
    description: str = "test",
) -> int:
    payload = {
        "title": title,
        "description": description,
        "period_id": int(period_id),
        "executor_role_id": int(executor_role_id),
        "assignment_scope": assignment_scope,
        "status_code": status_code,
    }
    r = c.post("/tasks", json=payload, headers=_headers(created_by_user_id))
    assert r.status_code == 200, f"Task create failed: {r.status_code} {r.text}"
    data = r.json()
    assert "task_id" in data, f"Expected task_id in response: {data}"
    return int(data["task_id"])


def _submit_report(
    c: TestClient,
    *,
    task_id: int,
    user_id: int,
    link: str = "https://example.com/r-test",
    comment: str = "test",
):
    payload = {"report_link": link, "current_comment": comment}
    return c.post(f"/tasks/{task_id}/report", json=payload, headers=_headers(user_id))


def _patch_task(
    c: TestClient,
    *,
    task_id: int,
    user_id: int,
    payload: Dict[str, Any],
):
    return c.patch(f"/tasks/{task_id}", json=payload, headers=_headers(user_id))


def _approve_task(
    c: TestClient,
    *,
    task_id: int,
    user_id: int,
    approve: bool = True,
    comment: str = "test",
):
    payload = {"approve": bool(approve), "current_comment": comment}
    return c.post(f"/tasks/{task_id}/approve", json=payload, headers=_headers(user_id))


# -------------------------
# Fixtures
# -------------------------
@pytest.fixture(scope="session")
def client() -> TestClient:
    return _make_client()


# -------------------------
# Scenarios
# -------------------------
def _scenario_forbidden_report(client: TestClient):
    task_id = _create_task(
        client,
        created_by_user_id=USER_SUPERVISOR,
        title="CONTRACT: forbidden report",
        status_code="WAITING_REPORT",
        executor_role_id=ROLE_EXECUTOR,
        assignment_scope="functional",
    )
    return _submit_report(client, task_id=task_id, user_id=USER_SUPERVISOR)


def _scenario_conflict_report_status(client: TestClient):
    """
    Variant 2 contract:
      - report from IN_PROGRESS is allowed (200 -> WAITING_APPROVAL)
      - second report attempt must fail with 409 conflict
    """
    task_id = _create_task(
        client,
        created_by_user_id=USER_SUPERVISOR,
        title="CONTRACT: conflict report status",
        status_code="IN_PROGRESS",
        executor_role_id=ROLE_EXECUTOR,
        assignment_scope="functional",
    )

    r1 = _submit_report(client, task_id=task_id, user_id=USER_EXECUTOR)
    assert r1.status_code == 200, r1.text

    r2 = _submit_report(client, task_id=task_id, user_id=USER_EXECUTOR)
    return r2


def _scenario_forbidden_patch(client: TestClient):
    task_id = _create_task(
        client,
        created_by_user_id=USER_SUPERVISOR,
        title="CONTRACT: forbidden patch",
        status_code="IN_PROGRESS",
        executor_role_id=ROLE_EXECUTOR,
        assignment_scope="functional",
    )
    return _patch_task(client, task_id=task_id, user_id=USER_SUPERVISOR, payload={"title": "try patch"})


def _scenario_conflict_patch_status(client: TestClient):
    task_id = _create_task(
        client,
        created_by_user_id=USER_SUPERVISOR,
        title="CONTRACT: conflict patch status",
        status_code="WAITING_REPORT",
        executor_role_id=ROLE_EXECUTOR,
        assignment_scope="functional",
    )
    return _patch_task(client, task_id=task_id, user_id=USER_EXECUTOR, payload={"description": "try patch"})


def _scenario_conflict_approve_no_report(client: TestClient):
    task_id = _create_task(
        client,
        created_by_user_id=USER_SUPERVISOR,
        title="CONTRACT: conflict approve no report",
        status_code="WAITING_APPROVAL",
        executor_role_id=ROLE_EXECUTOR,
        assignment_scope="functional",
    )
    return _approve_task(client, task_id=task_id, user_id=USER_SUPERVISOR, approve=True, comment="test")


# -------------------------
# Tests
# -------------------------
@pytest.mark.parametrize(
    "scenario, expected_http, expected_error",
    [
        (_scenario_forbidden_report, 403, "forbidden"),
        (_scenario_conflict_report_status, 409, "conflict"),
        (_scenario_forbidden_patch, 403, "forbidden"),
        (_scenario_conflict_patch_status, 409, "conflict"),
        (_scenario_conflict_approve_no_report, 409, "conflict"),
    ],
)
def test_business_error_contract(
    client: TestClient,
    scenario: Callable[[TestClient], Any],
    expected_http: int,
    expected_error: str,
) -> None:
    r = scenario(client)
    assert r.status_code == expected_http, r.text

    body = r.json()
    _assert_business_error(body, expected_error)
