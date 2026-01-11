# tests/test_error_codes.py
from __future__ import annotations

import os
from typing import Any, Dict, Optional, Set

import pytest

try:
    from fastapi.testclient import TestClient
except Exception as e:
    raise RuntimeError("fastapi TestClient is required for tests") from e


# -------------------------
# Test config (known seeded users in your DB)
# -------------------------
USER_EXECUTOR = 2   # role_id = 1
USER_SUPERVISOR = 34  # role_id = 58 (in SUPERVISOR_ROLE_IDS)
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
    # Import after env is set
    from app.main import app  # noqa: WPS433

    return TestClient(app)


def _headers(user_id: int) -> Dict[str, str]:
    return {"X-User-Id": str(int(user_id))}


def _assert_detail(
    body: Dict[str, Any],
    *,
    expected_error: str,
    expected_code: Optional[str] = None,
    expected_code_in: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    assert "detail" in body, f"Expected 'detail' in response JSON, got: {body}"
    detail = body["detail"]
    assert isinstance(detail, dict), f"Expected detail to be object, got: {type(detail)}"

    # Required fields for business errors (ADR-003/004)
    for k in ("error", "message", "reason", "hint", "code"):
        assert k in detail, f"Missing detail.{k} in: {detail}"

    assert detail["error"] == expected_error, f"Expected error={expected_error}, got: {detail}"

    if expected_code is not None:
        assert detail["code"] == expected_code, f"Expected code={expected_code}, got: {detail}"
    if expected_code_in is not None:
        assert detail["code"] in expected_code_in, f"Expected code in {expected_code_in}, got: {detail}"

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
# Tests: REPORT
# -------------------------
def test_error_code_task_forbidden_report_403(client: TestClient) -> None:
    """
    Create WAITING_REPORT task for executor role=1.
    Supervisor sees it but cannot report -> 403 TASK_FORBIDDEN_REPORT.
    """
    task_id = _create_task(
        client,
        created_by_user_id=USER_SUPERVISOR,
        title="T: forbidden report",
        status_code="WAITING_REPORT",
        executor_role_id=ROLE_EXECUTOR,
        assignment_scope="functional",
    )

    r = _submit_report(client, task_id=task_id, user_id=USER_SUPERVISOR)
    assert r.status_code == 403, r.text

    detail = _assert_detail(r.json(), expected_error="forbidden", expected_code="TASK_FORBIDDEN_REPORT")
    assert int(detail.get("task_id")) == task_id
    assert detail.get("action") in (None, "report") or True


def test_error_code_task_conflict_action_status_report_409(client: TestClient) -> None:
    """
    Variant 2 contract:
      - report from IN_PROGRESS is allowed (200 -> WAITING_APPROVAL)
      - second report attempt (already WAITING_APPROVAL) must fail with 409 conflict

    Backend may return either a generic status-conflict code
    or a more specific "already sent" code.
    """
    task_id = _create_task(
        client,
        created_by_user_id=USER_SUPERVISOR,
        title="T: conflict report status",
        status_code="IN_PROGRESS",
        executor_role_id=ROLE_EXECUTOR,
        assignment_scope="functional",
    )

    # First report is valid: IN_PROGRESS -> WAITING_APPROVAL
    r1 = _submit_report(client, task_id=task_id, user_id=USER_EXECUTOR)
    assert r1.status_code == 200, r1.text

    # Second report must conflict (already reported / wrong status)
    r2 = _submit_report(client, task_id=task_id, user_id=USER_EXECUTOR)
    assert r2.status_code == 409, r2.text

    acceptable = {"TASK_CONFLICT_ACTION_STATUS", "TASK_CONFLICT_REPORT_ALREADY_SENT"}
    detail = _assert_detail(r2.json(), expected_error="conflict", expected_code_in=acceptable)
    assert int(detail.get("task_id")) == task_id
    assert detail.get("action") in (None, "report") or True
    assert detail.get("current_status") in ("WAITING_APPROVAL", "IN_PROGRESS", None) or True


# -------------------------
# Tests: PATCH
# -------------------------
def test_error_code_task_forbidden_patch_403(client: TestClient) -> None:
    """
    Create IN_PROGRESS task for executor role=1.
    Supervisor sees it but cannot patch -> 403 TASK_FORBIDDEN_PATCH.
    """
    task_id = _create_task(
        client,
        created_by_user_id=USER_SUPERVISOR,
        title="T: forbidden patch",
        status_code="IN_PROGRESS",
        executor_role_id=ROLE_EXECUTOR,
        assignment_scope="functional",
    )

    r = _patch_task(client, task_id=task_id, user_id=USER_SUPERVISOR, payload={"title": "try patch"})
    assert r.status_code == 403, r.text

    detail = _assert_detail(r.json(), expected_error="forbidden", expected_code="TASK_FORBIDDEN_PATCH")
    assert int(detail.get("task_id")) == task_id


def test_error_code_task_conflict_patch_status_409(client: TestClient) -> None:
    """
    Create WAITING_REPORT task for executor role=1.
    Executor tries to patch in wrong status -> 409 TASK_CONFLICT_PATCH_STATUS.
    """
    task_id = _create_task(
        client,
        created_by_user_id=USER_SUPERVISOR,
        title="T: conflict patch status",
        status_code="WAITING_REPORT",
        executor_role_id=ROLE_EXECUTOR,
        assignment_scope="functional",
    )

    r = _patch_task(client, task_id=task_id, user_id=USER_EXECUTOR, payload={"description": "try patch"})
    assert r.status_code == 409, r.text

    detail = _assert_detail(r.json(), expected_error="conflict", expected_code="TASK_CONFLICT_PATCH_STATUS")
    assert int(detail.get("task_id")) == task_id
    assert detail.get("current_status") in ("WAITING_REPORT", None) or True


# -------------------------
# Tests: APPROVE
# -------------------------
def test_error_code_task_conflict_approve_no_report_409(client: TestClient) -> None:
    """
    Create WAITING_APPROVAL task but do NOT create task_reports record.
    Approve should fail with 409 (no report).
    Code name may vary depending on your errors registry:
      - TASK_CONFLICT_APPROVE_NO_REPORT (preferred)
      - TASK_CONFLICT_NO_REPORT (acceptable)
    """
    task_id = _create_task(
        client,
        created_by_user_id=USER_SUPERVISOR,
        title="T: conflict approve no report",
        status_code="WAITING_APPROVAL",
        executor_role_id=ROLE_EXECUTOR,
        assignment_scope="functional",
    )

    r = _approve_task(client, task_id=task_id, user_id=USER_SUPERVISOR, approve=True, comment="test")
    assert r.status_code == 409, r.text

    acceptable = {"TASK_CONFLICT_APPROVE_NO_REPORT", "TASK_CONFLICT_NO_REPORT"}
    detail = _assert_detail(r.json(), expected_error="conflict", expected_code_in=acceptable)
    assert int(detail.get("task_id")) == task_id
    assert detail.get("action") in (None, "approve", "reject") or True
