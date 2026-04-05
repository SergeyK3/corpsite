# tests/test_tasks_post_identity.py
from __future__ import annotations

from tests.conftest import auth_headers


def _minimal_adhoc_payload(seed: dict, **extra: object) -> dict:
    base = {
        "title": "pytest post identity",
        "period_id": int(seed["period_id"]),
        "executor_role_id": int(seed["executor_role_id"]),
        "assignment_scope": seed["assignment_scope"],
        "status_code": "IN_PROGRESS",
        "approver_user_id": int(seed["initiator_user_id"]),
    }
    base.update(extra)
    return base


def test_non_admin_cannot_spoof_initiator_user_id(client, seed) -> None:
    uid = int(seed["initiator_user_id"])
    other = int(seed["executor_user_id"])
    r = client.post(
        "/tasks/",
        json=_minimal_adhoc_payload(seed, initiator_user_id=other),
        headers=auth_headers(uid),
    )
    assert r.status_code == 403, r.text
    assert "initiator" in (r.json().get("detail") or "").lower()


def test_non_admin_cannot_spoof_created_by_user_id(client, seed) -> None:
    uid = int(seed["initiator_user_id"])
    other = int(seed["executor_user_id"])
    r = client.post(
        "/tasks/",
        json=_minimal_adhoc_payload(seed, created_by_user_id=other),
        headers=auth_headers(uid),
    )
    assert r.status_code == 403, r.text
    assert "created_by" in (r.json().get("detail") or "").lower()


def test_non_admin_may_echo_own_identity_fields(client, seed) -> None:
    uid = int(seed["initiator_user_id"])
    r = client.post(
        "/tasks/",
        json=_minimal_adhoc_payload(
            seed,
            title="pytest echo identity",
            initiator_user_id=uid,
            created_by_user_id=uid,
        ),
        headers=auth_headers(uid),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert int(body["initiator_user_id"]) == uid
    assert int(body.get("created_by_user_id") or 0) == uid


def test_create_task_without_identity_fields_uses_jwt_user(client, seed) -> None:
    uid = int(seed["initiator_user_id"])
    r = client.post(
        "/tasks/",
        json=_minimal_adhoc_payload(seed, title="pytest implicit identity"),
        headers=auth_headers(uid),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert int(body["initiator_user_id"]) == uid
    assert int(body.get("created_by_user_id") or 0) == uid
