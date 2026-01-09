# tests/test_error_contract.py
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import pytest

try:
    from fastapi.testclient import TestClient
except Exception as e:
    raise RuntimeError("fastapi TestClient is required for tests") from e


# Known seeded users in your DB
USER_EXECUTOR = 2     # role_id=1
USER_SUPERVISOR = 34  # role_id=58 (supervisor in env sets below)
ROLE_EXECUTOR = 1

DEFAULT_PERIOD_ID = int(os.getenv("TEST_PERIOD_ID", "2"))


def _ensure_env_for_rbac() -> None:
    # app/tasks.py reads SUPERVISOR_ROLE_IDS / DEPUTY_ROLE_IDS at import-time
    os.environ.setdefault("SUPERVISOR_ROLE_IDS", "58,59")
    os.environ.setdefault("DEPUTY_ROLE_IDS", "60")


@pytest.fixture(scope="session")
def client() -> TestClient:
    _ensure_env_for_rbac()
    from app.main import app  # noqa: WPS433

    return TestClient(app)


def _headers(user_id: int) -> Dict[str, str]:
    return {"X-User-Id": str(int(user_id))}


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


def _submit_report(c: TestClient, *, task_id: int, user_id: int) -> Any:
    payload = {"report_link": "https://example.com/r-test", "current_comment": "test"}
    return c.post(f"/tasks/{task_id}/report", json=payload, headers=_headers(user_id))


def _patch_task(c: TestClient, *, task_id: int, user_id: int) -> Any:
    payload = {"description": "try patch"}
    return c.patch(f"/tasks/{task_id}", json=payload, headers=_headers(user_id))


def _approve_task(c: TestClient, *, task_id: int, user_id: int, approve: bool) -> Any:
    payload = {"approve": bool(approve), "current_comment": "test"}
    return c.post(f"/tasks/{task_id}/approve", json=payload, headers=_headers(user_id))


def _assert_contract(
    resp_json: Dict[str, Any],
    *,
    expected_http: int,
    expected_error: str,
) -> Dict[str, Any]:
    assert isinstance(resp_json, dict), f"Expected JSON object, got: {type(resp_json)}"
    assert "detail" in resp_json, f"Missing 'detail' in response: {resp_json}"

    detail = resp_json["detail"]
    assert isinstance(detail, dict), f"detail must be object, got: {type(detail)}"

    # Required contract fields for business errors
    required = ("error", "message", "reason", "hint", "code")
    for k in required:
        assert k in detail, f"Missing detail.{k} in: {detail}"
        assert detail[k] is not None, f"detail.{k} must not be None in: {detail}"
        assert str(detail[k]).strip() != "", f"detail.{k} must not be empty in: {detail}"

    assert detail["error"] == expected_error, f"Expected detail.error={expected_error}, got: {detail}"

    # Basic code quality
    code = str(detail["code"])
    assert code.upper() == code, f"detail.code must be UPPER_SNAKE_CASE, got: {code}"
    assert " " not in code, f"detail.code must not contain spaces, got: {code}"
    assert len(code) <= 64, f"detail.code must be <= 64 chars, got: {code} ({len(code)})"

    # Category ↔ HTTP mapping
    if code.endswith("_FORBIDDEN") or "_FORBIDDEN_" in code:
        assert expected_http == 403, f"{code} must be returned with HTTP 403"
    if code.endswith("_CONFLICT") or "_CONFLICT_" in code:
        assert expected_http == 409, f"{code} must be returned with HTTP 409"

    return detail


def _scenario_forbidden_report(c: TestClient) -> Any:
    task_id = _create_task(
        c,
        created_by_user_id=USER_SUPERVISOR,
        title="CONTRACT: forbidden report",
        status_code="WAITING_REPORT",
        executor_role_id=ROLE_EXECUTOR,
        assignment_scope="functional",
    )
    return _submit_report(c, task_id=task_id, user_id=USER_SUPERVISOR)


def _scenario_conflict_report_status(c: TestClient) -> Any:
    task_id = _create_task(
        c,
        created_by_user_id=USER_SUPERVISOR,
        title="CONTRACT: conflict report status",
        status_code="IN_PROGRESS",
        executor_role_id=ROLE_EXECUTOR,
        assignment_scope="functional",
    )
    return _submit_report(c, task_id=task_id, user_id=USER_EXECUTOR)


def _scenario_forbidden_patch(c: TestClient) -> Any:
    task_id = _create_task(
        c,
        created_by_user_id=USER_SUPERVISOR,
        title="CONTRACT: forbidden patch",
        status_code="IN_PROGRESS",
        executor_role_id=ROLE_EXECUTOR,
        assignment_scope="functional",
    )
    return _patch_task(c, task_id=task_id, user_id=USER_SUPERVISOR)


def _scenario_conflict_patch_status(c: TestClient) -> Any:
    task_id = _create_task(
        c,
        created_by_user_id=USER_SUPERVISOR,
        title="CONTRACT: conflict patch status",
        status_code="WAITING_REPORT",
        executor_role_id=ROLE_EXECUTOR,
        assignment_scope="functional",
    )
    return _patch_task(c, task_id=task_id, user_id=USER_EXECUTOR)


def _scenario_conflict_approve_no_report(c: TestClient) -> Any:
    task_id = _create_task(
        c,
        created_by_user_id=USER_SUPERVISOR,
        title="CONTRACT: conflict approve no report",
        status_code="WAITING_APPROVAL",
        executor_role_id=ROLE_EXECUTOR,
        assignment_scope="functional",
    )
    return _approve_task(c, task_id=task_id, user_id=USER_SUPERVISOR, approve=True)


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
    scenario,
    expected_http: int,
    expected_error: str,
) -> None:
    r = scenario(client)
    assert r.status_code == expected_http, r.text

    detail = _assert_contract(r.json(), expected_http=expected_http, expected_error=expected_error)

    # Optional but recommended context fields quality
    if "task_id" in detail:
        try:
            int(detail["task_id"])
        except Exception:
            pytest.fail(f"detail.task_id must be int-like, got: {detail.get('task_id')}")
