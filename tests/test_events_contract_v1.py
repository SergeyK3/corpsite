# tests/test_events_contract_v1.py
from __future__ import annotations

import os
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

import pytest

try:
    from fastapi.testclient import TestClient
except Exception as e:
    raise RuntimeError("fastapi TestClient is required for tests") from e


# -------------------------
# Test config
# -------------------------
USER_ID = 1  # любой пользователь, у которого есть события
TIME_SKEW = timedelta(seconds=2)


# -------------------------
# Helpers
# -------------------------
RFC3339_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?([+\-]\d{2}:\d{2}|Z)$"
)


def _ensure_env() -> None:
    os.environ.setdefault("SUPERVISOR_ROLE_IDS", "58,59")
    os.environ.setdefault("DEPUTY_ROLE_IDS", "60")


def _make_client() -> TestClient:
    _ensure_env()
    from app.main import app  # noqa: WPS433

    return TestClient(app)


def _headers(user_id: int) -> Dict[str, str]:
    return {"X-User-Id": str(int(user_id))}


def _parse_rfc3339(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    assert dt.tzinfo is not None
    return dt


def _get_events(resp) -> List[Dict[str, Any]]:
    assert resp.headers.get("content-type", "").startswith("application/json")
    data = resp.json()
    assert isinstance(data, list), f"Expected JSON array, got: {type(data)}"
    return data


def _assert_event_shape(ev: Dict[str, Any]) -> None:
    required = {
        "event_id",
        "task_id",
        "event_type",
        "actor_user_id",
        "actor_role_id",
        "created_at",
        "payload",
    }
    assert required.issubset(ev.keys()), f"Missing keys: {required - set(ev.keys())}"

    assert isinstance(ev["event_id"], int) and ev["event_id"] > 0
    assert isinstance(ev["task_id"], int) and ev["task_id"] > 0
    assert isinstance(ev["actor_user_id"], int)
    assert isinstance(ev["actor_role_id"], int)
    assert isinstance(ev["payload"], dict)

    assert isinstance(ev["event_type"], str) and ev["event_type"]
    assert isinstance(ev["created_at"], str)
    assert RFC3339_RE.match(ev["created_at"]), f"Invalid RFC3339: {ev['created_at']}"

    dt = _parse_rfc3339(ev["created_at"])
    now = datetime.now(timezone.utc)
    assert dt <= now + TIME_SKEW, f"created_at too far in future: {dt}"


def _assert_sorted_desc(events: List[Dict[str, Any]]) -> None:
    ids = [e["event_id"] for e in events]
    assert ids == sorted(ids, reverse=True), f"Expected DESC event_id, got {ids}"
    assert len(ids) == len(set(ids)), "event_id must be unique within page"


# -------------------------
# Fixtures
# -------------------------
@pytest.fixture(scope="session")
def client() -> TestClient:
    return _make_client()


# -------------------------
# Tests: basic contract
# -------------------------
@pytest.mark.parametrize("limit", [1, 5, 50])
def test_events_basic_shape_and_sorting(client: TestClient, limit: int) -> None:
    r = client.get(
        f"/tasks/me/events?limit={limit}",
        headers=_headers(USER_ID),
    )
    assert r.status_code == 200, r.text

    events = _get_events(r)
    assert len(events) <= limit

    for ev in events:
        _assert_event_shape(ev)

    _assert_sorted_desc(events)


# -------------------------
# Tests: after_id
# -------------------------
def test_events_after_id_filters_strictly(client: TestClient) -> None:
    r1 = client.get(
        "/tasks/me/events?limit=10",
        headers=_headers(USER_ID),
    )
    assert r1.status_code == 200, r1.text
    page1 = _get_events(r1)

    if not page1:
        pytest.skip("No events to test after_id filtering")

    _assert_sorted_desc(page1)
    after_id = page1[-1]["event_id"]

    r2 = client.get(
        f"/tasks/me/events?limit=50&after_id={after_id}",
        headers=_headers(USER_ID),
    )
    assert r2.status_code == 200, r2.text
    page2 = _get_events(r2)

    for ev in page2:
        assert ev["event_id"] > after_id

    _assert_sorted_desc(page2)


def test_events_after_id_zero_is_invalid(client: TestClient) -> None:
    r = client.get(
        "/tasks/me/events?after_id=0",
        headers=_headers(USER_ID),
    )
    assert r.status_code == 422, r.text


def test_events_after_id_large_returns_empty(client: TestClient) -> None:
    r = client.get(
        "/tasks/me/events?after_id=999999999",
        headers=_headers(USER_ID),
    )
    assert r.status_code == 200, r.text
    events = _get_events(r)
    assert events == []


# -------------------------
# Tests: limit validation
# -------------------------
@pytest.mark.parametrize("limit", [0, -1])
def test_events_invalid_limit(client: TestClient, limit: int) -> None:
    r = client.get(
        f"/tasks/me/events?limit={limit}",
        headers=_headers(USER_ID),
    )
    assert r.status_code in (400, 422), r.text


# -------------------------
# Tests: ACL visibility (deterministic seed)
# -------------------------
def test_events_acl_non_leak_isolated_seed(client: TestClient) -> None:
    """
    Deterministic ACL non-leak test aligned with role-based access:
      - user sees tasks/events in own initiator scope
      - executor queue is role-based, so to test non-leak we must use DIFFERENT executor_role_id for A and B
    """
    from tests._seed_acl import (
        create_user,
        cleanup_user_related_data,
        seed_task_with_event,
        fetch_event_task_ids,
        pick_two_non_priv_role_ids,
    )

    role_a, role_b = pick_two_non_priv_role_ids()
    PERIOD_ID = 2

    # A: initiator role_a, executor role_a
    user_a = create_user(role_id=role_a, name="ACL Initiator A")
    exec_a = create_user(role_id=role_a, name="ACL Executor A")

    # B: initiator role_b, executor role_b
    user_b = create_user(role_id=role_b, name="ACL Initiator B")
    exec_b = create_user(role_id=role_b, name="ACL Executor B")

    try:
        task_a = seed_task_with_event(
            client,
            initiator_user_id=user_a.user_id,
            executor_user_id=exec_a.user_id,
            executor_role_id=role_a,
            title="ACL seed A",
            period_id=PERIOD_ID,
        )

        task_b = seed_task_with_event(
            client,
            initiator_user_id=user_b.user_id,
            executor_user_id=exec_b.user_id,
            executor_role_id=role_b,
            title="ACL seed B",
            period_id=PERIOD_ID,
        )

        events_a = set(fetch_event_task_ids(client, user_a.user_id))
        events_b = set(fetch_event_task_ids(client, user_b.user_id))

        assert task_a in events_a, "User A must see own task events"
        assert task_b in events_b, "User B must see own task events"

        # non-leak across different role queues
        assert task_b not in events_a, "ACL leak: user A sees events of user B"
        assert task_a not in events_b, "ACL leak: user B sees events of user A"
    finally:
        cleanup_user_related_data(user_a.user_id)
        cleanup_user_related_data(exec_a.user_id)
        cleanup_user_related_data(user_b.user_id)
        cleanup_user_related_data(exec_b.user_id)
