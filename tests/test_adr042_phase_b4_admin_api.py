# tests/test_adr042_phase_b4_admin_api.py
"""Tests for ADR-042 Phase B4 sysadmin REST API."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.services.enrollment_detector_service import enqueue_enrollment_candidate
from tests.conftest import auth_headers, get_columns, insert_returning_id, table_exists

PHASE_B2_TABLES = (
    "persons",
    "person_assignments",
    "employee_assignment_links",
    "enrollment_queue",
    "enrollment_history",
    "access_roles",
    "access_grants",
    "security_audit_log",
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_b2() -> None:
    with engine.begin() as conn:
        for table in PHASE_B2_TABLES:
            if not table_exists(conn, table):
                pytest.skip(f"ADR-042 B2 table missing: {table}")


@pytest.fixture
def admin_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def non_admin_headers(seed):
    return auth_headers(seed["executor_user_id"])


def _get_access_role_id(conn, code: str) -> int:
    row = conn.execute(
        text("SELECT access_role_id FROM public.access_roles WHERE code = :code LIMIT 1"),
        {"code": code},
    ).scalar_one()
    return int(row)


def _audit_count(*, event_type: str, actor_user_id: int | None = None) -> int:
    with engine.connect() as conn:
        if actor_user_id is None:
            return int(
                conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM public.security_audit_log
                        WHERE event_type = :event_type
                        """
                    ),
                    {"event_type": event_type},
                ).scalar_one()
            )
        return int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM public.security_audit_log
                    WHERE event_type = :event_type AND actor_user_id = :actor
                    """
                ),
                {"event_type": event_type, "actor": actor_user_id},
            ).scalar_one()
        )


def _create_person_with_assignment(conn, seed, suffix: str) -> dict:
    person_id = insert_returning_id(
        conn,
        table="persons",
        id_col="person_id",
        values={
            "full_name": f"B4 Person {suffix}",
            "match_key": f"name:b4 person {suffix}",
            "source": "manual",
            "person_status": "active",
        },
    )
    pos_id = conn.execute(
        text("SELECT position_id FROM public.positions ORDER BY position_id LIMIT 1")
    ).scalar_one()
    assignment_id = insert_returning_id(
        conn,
        table="person_assignments",
        id_col="assignment_id",
        values={
            "person_id": person_id,
            "org_unit_id": int(seed["unit_id"]),
            "position_id": int(pos_id),
            "employment_type": "primary",
            "rate": 1.0,
            "start_date": "2026-01-01",
            "active_flag": True,
            "is_primary": True,
            "lifecycle_status": "active",
            "assignment_key": f"b4-{suffix}|{pos_id}|primary|2026-01-01",
            "source": "manual",
        },
    )
    return {
        "person_id": person_id,
        "assignment_id": assignment_id,
        "position_id": int(pos_id),
    }


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_non_admin_cannot_call_admin_routes(client: TestClient, seed, non_admin_headers):
    _require_b2()
    resp = client.get("/admin/access/effective", headers=non_admin_headers)
    assert resp.status_code == 403

    resp = client.get("/admin/users", headers=non_admin_headers)
    assert resp.status_code == 403

    resp = client.get("/admin/security-audit", headers=non_admin_headers)
    assert resp.status_code == 403


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_admin_can_list_effective_access(client: TestClient, seed, admin_headers):
    _require_b2()
    resp = client.get("/admin/access/effective", headers=admin_headers, params={"limit": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    first = data[0]
    assert "effective_role_code" in first
    assert "access_level" in first
    assert "matched_grants" in first


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_grant_access_creates_row(client: TestClient, seed, admin_headers):
    _require_b2()
    suffix = uuid4().hex[:8]
    grant_id = None

    with engine.begin() as conn:
        ctx = _create_person_with_assignment(conn, seed, suffix)
        role_id = _get_access_role_id(conn, "ACCESS_OBSERVER")

    try:
        resp = client.post(
            "/admin/access/grants",
            headers=admin_headers,
            json={
                "access_role_id": role_id,
                "target_type": "PERSON",
                "target_id": ctx["person_id"],
                "reason": "b4 test grant",
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        grant_id = int(body["grant_id"])

        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT grant_id, active_flag, target_type, target_id
                    FROM public.access_grants
                    WHERE grant_id = :gid
                    """
                ),
                {"gid": grant_id},
            ).mappings().first()
        assert row is not None
        assert row["active_flag"] is True
        assert row["target_type"] == "PERSON"
        assert int(row["target_id"]) == ctx["person_id"]
    finally:
        if grant_id is not None:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM public.security_audit_log WHERE metadata->>'grant_id' = :gid"),
                    {"gid": str(grant_id)},
                )
                conn.execute(
                    text("DELETE FROM public.access_grants WHERE grant_id = :gid"),
                    {"gid": grant_id},
                )
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public.person_assignments WHERE person_id = :pid"),
                {"pid": ctx["person_id"]},
            )
            conn.execute(text("DELETE FROM public.persons WHERE person_id = :pid"), {"pid": ctx["person_id"]})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_revoke_access_soft_revokes_row(client: TestClient, seed, admin_headers):
    _require_b2()
    suffix = uuid4().hex[:8]
    grant_id = None

    with engine.begin() as conn:
        ctx = _create_person_with_assignment(conn, seed, suffix)
        role_id = _get_access_role_id(conn, "ACCESS_MANAGER")

    try:
        create_resp = client.post(
            "/admin/access/grants",
            headers=admin_headers,
            json={
                "access_role_id": role_id,
                "target_type": "PERSON",
                "target_id": ctx["person_id"],
            },
        )
        grant_id = int(create_resp.json()["grant_id"])

        revoke_resp = client.delete(f"/admin/access/grants/{grant_id}", headers=admin_headers)
        assert revoke_resp.status_code == 200
        assert revoke_resp.json().get("revoked") is True

        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT active_flag, revoked_at, revoked_by_user_id
                    FROM public.access_grants WHERE grant_id = :gid
                    """
                ),
                {"gid": grant_id},
            ).mappings().first()
        assert row is not None
        assert row["active_flag"] is False
        assert row["revoked_at"] is not None
        assert int(row["revoked_by_user_id"]) == int(seed["initiator_user_id"])
    finally:
        if grant_id is not None:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM public.security_audit_log WHERE metadata->>'grant_id' = :gid"),
                    {"gid": str(grant_id)},
                )
                conn.execute(text("DELETE FROM public.access_grants WHERE grant_id = :gid"), {"gid": grant_id})
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public.person_assignments WHERE person_id = :pid"),
                {"pid": ctx["person_id"]},
            )
            conn.execute(text("DELETE FROM public.persons WHERE person_id = :pid"), {"pid": ctx["person_id"]})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_grant_revoke_writes_security_audit_log(client: TestClient, seed, admin_headers):
    _require_b2()
    suffix = uuid4().hex[:8]
    grant_id = None
    actor_id = int(seed["initiator_user_id"])

    with engine.begin() as conn:
        ctx = _create_person_with_assignment(conn, seed, suffix)
        role_id = _get_access_role_id(conn, "ACCESS_OBSERVER")
        before_granted = _audit_count(event_type="ACCESS_GRANTED", actor_user_id=actor_id)
        before_revoked = _audit_count(event_type="ACCESS_REVOKED", actor_user_id=actor_id)

    try:
        resp = client.post(
            "/admin/access/grants",
            headers=admin_headers,
            json={
                "access_role_id": role_id,
                "target_type": "PERSON",
                "target_id": ctx["person_id"],
            },
        )
        grant_id = int(resp.json()["grant_id"])
        after_granted = _audit_count(event_type="ACCESS_GRANTED", actor_user_id=actor_id)
        assert after_granted == before_granted + 1

        client.delete(f"/admin/access/grants/{grant_id}", headers=admin_headers)
        after_revoked = _audit_count(event_type="ACCESS_REVOKED", actor_user_id=actor_id)
        assert after_revoked == before_revoked + 1
    finally:
        if grant_id is not None:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM public.security_audit_log WHERE metadata->>'grant_id' = :gid"),
                    {"gid": str(grant_id)},
                )
                conn.execute(text("DELETE FROM public.access_grants WHERE grant_id = :gid"), {"gid": grant_id})
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public.person_assignments WHERE person_id = :pid"),
                {"pid": ctx["person_id"]},
            )
            conn.execute(text("DELETE FROM public.persons WHERE person_id = :pid"), {"pid": ctx["person_id"]})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_detect_enrollment_does_not_create_employees(client: TestClient, seed, admin_headers):
    _require_b2()
    before = _count_employees()
    resp = client.post(
        "/admin/enrollment/detect",
        headers=admin_headers,
        json={"dry_run": True, "limit": 5},
    )
    assert resp.status_code == 200
    after = _count_employees()
    assert before == after
    assert resp.json().get("dry_run") is True


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_approve_reject_writes_enrollment_history(client: TestClient, seed, admin_headers):
    _require_b2()
    suffix = uuid4().hex[:8]
    queue_id = None

    with engine.begin() as conn:
        ctx = _create_person_with_assignment(conn, seed, suffix)

    try:
        enq = enqueue_enrollment_candidate(
            reason="MANUAL_REQUEST",
            person_id=ctx["person_id"],
            assignment_id=ctx["assignment_id"],
            dry_run=False,
        )
        queue_id = int(enq["queue_id"])

        approve_resp = client.post(
            f"/admin/enrollment/queue/{queue_id}/approve",
            headers=admin_headers,
            json={"comment": "approved in test"},
        )
        assert approve_resp.status_code == 200

        with engine.connect() as conn:
            approved_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM public.enrollment_history
                    WHERE queue_id = :qid AND event_type = 'APPROVED'
                    """
                ),
                {"qid": queue_id},
            ).scalar_one()
        assert int(approved_count) == 1

        reject_queue = enqueue_enrollment_candidate(
            reason="MANUAL_REQUEST",
            person_id=ctx["person_id"],
            dry_run=False,
        )
        reject_qid = int(reject_queue["queue_id"])
        if reject_qid == queue_id:
            with engine.begin() as conn:
                reject_qid = insert_returning_id(
                    conn,
                    table="enrollment_queue",
                    id_col="queue_id",
                    values={
                        "person_id": ctx["person_id"],
                        "assignment_id": ctx["assignment_id"],
                        "queue_status": "PENDING",
                        "reason": "MANUAL_REQUEST",
                        "idempotency_key": f"manual-reject-{suffix}",
                    },
                )

        reject_resp = client.post(
            f"/admin/enrollment/queue/{reject_qid}/reject",
            headers=admin_headers,
            json={"comment": "rejected in test"},
        )
        assert reject_resp.status_code == 200

        with engine.connect() as conn:
            rejected_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM public.enrollment_history
                    WHERE queue_id = :qid AND event_type = 'REJECTED'
                    """
                ),
                {"qid": reject_qid},
            ).scalar_one()
        assert int(rejected_count) == 1

        if reject_qid != queue_id:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM public.enrollment_history WHERE queue_id = :qid"),
                    {"qid": reject_qid},
                )
                conn.execute(
                    text("DELETE FROM public.enrollment_queue WHERE queue_id = :qid"),
                    {"qid": reject_qid},
                )
    finally:
        if queue_id is not None:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM public.enrollment_history WHERE queue_id = :qid"),
                    {"qid": queue_id},
                )
                conn.execute(
                    text("DELETE FROM public.enrollment_queue WHERE queue_id = :qid"),
                    {"qid": queue_id},
                )
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public.person_assignments WHERE person_id = :pid"),
                {"pid": ctx["person_id"]},
            )
            conn.execute(text("DELETE FROM public.persons WHERE person_id = :pid"), {"pid": ctx["person_id"]})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_apply_approved_queue_item_creates_or_reuses_employee(client: TestClient, seed, admin_headers):
    _require_b2()
    suffix = uuid4().hex[:8]
    queue_id = None
    employee_id = None

    with engine.begin() as conn:
        ctx = _create_person_with_assignment(conn, seed, suffix)

    try:
        enq = enqueue_enrollment_candidate(
            reason="NEW_ASSIGNMENT",
            person_id=ctx["person_id"],
            assignment_id=ctx["assignment_id"],
            dry_run=False,
        )
        queue_id = int(enq["queue_id"])

        client.post(
            f"/admin/enrollment/queue/{queue_id}/approve",
            headers=admin_headers,
            json={},
        )

        apply_resp = client.post(
            f"/admin/enrollment/queue/{queue_id}/apply",
            headers=admin_headers,
        )
        assert apply_resp.status_code == 200, apply_resp.text
        body = apply_resp.json()
        employee_id = int(body["employee_id"])
        assert body["queue_status"] == "ENROLLED"
        assert body.get("created_employee") is True

        apply_again = client.post(
            f"/admin/enrollment/queue/{queue_id}/apply",
            headers=admin_headers,
        )
        assert apply_again.status_code == 200
        assert apply_again.json().get("already_applied") is True

        with engine.connect() as conn:
            emp_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM public.employees
                    WHERE person_id = :pid
                    """
                ),
                {"pid": ctx["person_id"]},
            ).scalar_one()
            link_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM public.employee_assignment_links
                    WHERE employee_id = :eid AND assignment_id = :aid AND link_status = 'active'
                    """
                ),
                {"eid": employee_id, "aid": ctx["assignment_id"]},
            ).scalar_one()
        assert int(emp_count) == 1
        assert int(link_count) == 1
    finally:
        if employee_id is not None:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM public.employee_assignment_links WHERE employee_id = :eid"),
                    {"eid": employee_id},
                )
                conn.execute(
                    text("DELETE FROM public.employees WHERE employee_id = :eid"),
                    {"eid": employee_id},
                )
        if queue_id is not None:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM public.security_audit_log WHERE metadata->>'queue_id' = :qid"),
                    {"qid": str(queue_id)},
                )
                conn.execute(
                    text("DELETE FROM public.enrollment_history WHERE queue_id = :qid"),
                    {"qid": queue_id},
                )
                conn.execute(
                    text("DELETE FROM public.enrollment_queue WHERE queue_id = :qid"),
                    {"qid": queue_id},
                )
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public.person_assignments WHERE person_id = :pid"),
                {"pid": ctx["person_id"]},
            )
            conn.execute(text("DELETE FROM public.persons WHERE person_id = :pid"), {"pid": ctx["person_id"]})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_assignment_drift_endpoint_defaults_to_dry_run(client: TestClient, seed, admin_headers):
    _require_b2()

    with engine.connect() as conn:
        emp = conn.execute(
            text(
                """
                SELECT employee_id FROM public.employees
                WHERE person_id IS NOT NULL
                ORDER BY employee_id
                LIMIT 1
                """
            )
        ).scalar_one_or_none()
    if emp is None:
        pytest.skip("No linked employee for reconcile test")

    resp = client.post(
        f"/admin/assignments/reconcile/{int(emp)}",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json().get("dry_run") is True


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_lock_unlock_user_updates_columns_and_audit(client: TestClient, seed, admin_headers):
    _require_b2()
    target_user_id = int(seed["executor_user_id"])
    actor_id = int(seed["initiator_user_id"])

    user_cols = set()
    with engine.connect() as conn:
        user_cols = get_columns(conn, "users")
    if "locked_at" not in user_cols:
        pytest.skip("users.locked_at column missing")

    before_locked = _audit_count(event_type="USER_LOCKED", actor_user_id=actor_id)
    lock_resp = client.post(
        f"/admin/users/{target_user_id}/lock",
        headers=admin_headers,
        params={"reason": "admin"},
    )
    assert lock_resp.status_code == 200
    locked_body = lock_resp.json()
    assert locked_body.get("locked_at") is not None
    assert locked_body.get("locked_reason") == "admin"
    assert _audit_count(event_type="USER_LOCKED", actor_user_id=actor_id) == before_locked + 1

    unlock_resp = client.post(
        f"/admin/users/{target_user_id}/unlock",
        headers=admin_headers,
    )
    assert unlock_resp.status_code == 200
    unlocked_body = unlock_resp.json()
    assert unlocked_body.get("locked_at") is None
    assert unlocked_body.get("locked_reason") is None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_security_audit_list_filters_and_sorts_newest_first(client: TestClient, seed, admin_headers):
    _require_b2()
    suffix = uuid4().hex[:8]
    actor_id = int(seed["initiator_user_id"])

    with engine.begin() as conn:
        ctx = _create_person_with_assignment(conn, seed, suffix)
        role_id = _get_access_role_id(conn, "ACCESS_OBSERVER")

    grant_id = None
    try:
        client.post(
            "/admin/access/grants",
            headers=admin_headers,
            json={
                "access_role_id": role_id,
                "target_type": "PERSON",
                "target_id": ctx["person_id"],
            },
        )

        resp = client.get(
            "/admin/security-audit",
            headers=admin_headers,
            params={
                "event_type": "ACCESS_GRANTED",
                "actor_user_id": actor_id,
                "limit": 5,
            },
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert "items" in payload
        items = payload["items"]
        assert len(items) >= 1
        assert items[0]["event_type"] == "ACCESS_GRANTED"
        assert int(items[0]["actor_user_id"]) == actor_id

        if len(items) >= 2:
            first_ts = items[0].get("happened_at") or ""
            second_ts = items[1].get("happened_at") or ""
            assert first_ts >= second_ts

        for item in items:
            meta = item.get("metadata") or {}
            for forbidden in ("password", "token", "secret", "hash"):
                assert forbidden not in {k.lower() for k in meta.keys()}
    finally:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    DELETE FROM public.security_audit_log
                    WHERE actor_user_id = :actor AND event_type = 'ACCESS_GRANTED'
                      AND metadata->>'target_id' = :tid
                    """
                ),
                {"actor": actor_id, "tid": str(ctx["person_id"])},
            )
            conn.execute(
                text("DELETE FROM public.access_grants WHERE target_id = :tid AND target_type = 'PERSON'"),
                {"tid": ctx["person_id"]},
            )
            conn.execute(
                text("DELETE FROM public.person_assignments WHERE person_id = :pid"),
                {"pid": ctx["person_id"]},
            )
            conn.execute(text("DELETE FROM public.persons WHERE person_id = :pid"), {"pid": ctx["person_id"]})


def _count_employees() -> int:
    with engine.connect() as conn:
        return int(conn.execute(text("SELECT COUNT(*) FROM public.employees")).scalar_one())
