# tests/test_adr043_phase_c4_1_lifecycle_api.py
"""Tests for ADR-043 Phase C4.1 personnel lifecycle REST API."""
from __future__ import annotations

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers, create_role, create_user, insert_returning_id, table_exists

PHASE_C4_TABLES = (
    "hr_personnel_lifecycle_runs",
    "hr_personnel_change_events",
    "hr_snapshot_effective_entries",
    "hr_canonical_snapshots",
    "hr_canonical_snapshot_entries",
    "hr_review_overrides",
    "access_roles",
    "access_grants",
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_c4() -> None:
    with engine.begin() as conn:
        if not all(table_exists(conn, table) for table in PHASE_C4_TABLES):
            pytest.skip("ADR-043 Phase C4 tables missing — run: alembic upgrade head")


def _get_access_role_id(conn, code: str) -> int:
    return int(
        conn.execute(
            text("SELECT access_role_id FROM public.access_roles WHERE code = :code LIMIT 1"),
            {"code": code},
        ).scalar_one()
    )


def _insert_batch(conn, user_id: int) -> int:
    return conn.execute(
        text(
            """
            INSERT INTO public.hr_import_batches (
                source_type, file_name, imported_by, status,
                total_rows, valid_rows, error_rows
            )
            VALUES ('HR_CONTROL_LIST', :file_name, :uid, 'PARSED', 1, 1, 0)
            RETURNING batch_id
            """
        ),
        {"file_name": f"c4_{uuid4().hex[:8]}.xlsx", "uid": user_id},
    ).scalar_one()


def _setup_snapshot_pair(
    conn,
    *,
    user_id: int,
    prior_entries: dict[str, dict],
    new_entries: dict[str, dict],
) -> tuple[int, int]:
    base_version = 930_000 + int(uuid4().hex[:3], 16)
    prior_id = insert_returning_id(
        conn,
        table="hr_canonical_snapshots",
        id_col="snapshot_id",
        values={
            "source_batch_id": _insert_batch(conn, user_id),
            "source_type": "HR_CONTROL_LIST",
            "version": base_version,
            "status": "superseded",
            "entry_count": len(prior_entries),
            "promoted_by": user_id,
        },
    )
    new_id = insert_returning_id(
        conn,
        table="hr_canonical_snapshots",
        id_col="snapshot_id",
        values={
            "source_batch_id": _insert_batch(conn, user_id),
            "source_type": "HR_CONTROL_LIST",
            "version": base_version + 1,
            "status": "superseded",
            "entry_count": len(new_entries),
            "promoted_by": user_id,
        },
    )
    for match_key, payload in prior_entries.items():
        insert_returning_id(
            conn,
            table="hr_canonical_snapshot_entries",
            id_col="entry_id",
            values={
                "snapshot_id": prior_id,
                "entity_scope": match_key,
                "record_kind": "roster",
                "match_key": match_key,
                "canonical_hash": "c4" + uuid4().hex,
                "payload": json.dumps(payload),
            },
        )
    for match_key, payload in new_entries.items():
        insert_returning_id(
            conn,
            table="hr_canonical_snapshot_entries",
            id_col="entry_id",
            values={
                "snapshot_id": new_id,
                "entity_scope": match_key,
                "record_kind": "roster",
                "match_key": match_key,
                "canonical_hash": "c4" + uuid4().hex,
                "payload": json.dumps(payload),
            },
        )
    return int(prior_id), int(new_id)


def _cleanup_overrides_for_scope_keys(scope_keys: list[str]) -> None:
    if not scope_keys:
        return
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL session_replication_role = replica"))
        override_ids = [
            int(row)
            for row in conn.execute(
                text(
                    """
                    SELECT override_id FROM public.hr_review_overrides
                    WHERE scope_key = ANY(:keys)
                    """
                ),
                {"keys": scope_keys},
            ).scalars().all()
        ]
        if not override_ids:
            conn.execute(text("SET LOCAL session_replication_role = origin"))
            return
        conn.execute(
            text(
                """
                DELETE FROM public.hr_review_override_history
                WHERE override_id = ANY(:oids)
                """
            ),
            {"oids": override_ids},
        )
        conn.execute(
            text(
                """
                UPDATE public.hr_review_overrides
                SET supersedes_override_id = NULL, superseded_by_override_id = NULL
                WHERE override_id = ANY(:oids)
                   OR supersedes_override_id = ANY(:oids)
                   OR superseded_by_override_id = ANY(:oids)
                """
            ),
            {"oids": override_ids},
        )
        conn.execute(
            text("DELETE FROM public.hr_review_overrides WHERE override_id = ANY(:oids)"),
            {"oids": override_ids},
        )
        conn.execute(text("SET LOCAL session_replication_role = origin"))


def _cleanup_snapshot_pair(prior_id: int, new_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                DELETE FROM public.hr_personnel_lifecycle_runs
                WHERE previous_snapshot_id = :prior AND snapshot_id = :new
                """
            ),
            {"prior": prior_id, "new": new_id},
        )
        conn.execute(
            text(
                """
                DELETE FROM public.hr_personnel_change_events
                WHERE previous_snapshot_id = :prior AND snapshot_id = :new
                """
            ),
            {"prior": prior_id, "new": new_id},
        )
        conn.execute(
            text("DELETE FROM public.hr_snapshot_effective_entries WHERE snapshot_id = ANY(:ids)"),
            {"ids": [prior_id, new_id]},
        )
        conn.execute(
            text("DELETE FROM public.hr_canonical_snapshot_entries WHERE snapshot_id = ANY(:ids)"),
            {"ids": [prior_id, new_id]},
        )
        for sid in (prior_id, new_id):
            row = conn.execute(
                text("SELECT source_batch_id FROM public.hr_canonical_snapshots WHERE snapshot_id = :sid"),
                {"sid": sid},
            ).mappings().first()
            conn.execute(
                text("DELETE FROM public.hr_canonical_snapshots WHERE snapshot_id = :sid"),
                {"sid": sid},
            )
            if row and row.get("source_batch_id"):
                conn.execute(
                    text("DELETE FROM public.hr_import_batches WHERE batch_id = :bid"),
                    {"bid": int(row["source_batch_id"])},
                )


def _lifecycle_payload(prior_id: int, new_id: int, **kwargs) -> dict:
    return {
        "previous_snapshot_id": prior_id,
        "snapshot_id": new_id,
        "refresh_cache": kwargs.get("refresh_cache", True),
        "enqueue": kwargs.get("enqueue", False),
        "sync_persons": kwargs.get("sync_persons", False),
    }


@pytest.fixture
def admin_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def non_admin_headers(seed):
    return auth_headers(seed["executor_user_id"])


@pytest.fixture
def hr_manager_headers(seed, admin_headers, client):
    grant_id = None
    with engine.begin() as conn:
        role_id = _get_access_role_id(conn, "HR_ENROLLMENT_MANAGER")
    resp = client.post(
        "/admin/access/grants",
        headers=admin_headers,
        json={
            "access_role_id": role_id,
            "target_type": "USER",
            "target_id": seed["executor_user_id"],
            "reason": "c4 hr manager test",
        },
    )
    assert resp.status_code == 200, resp.text
    grant_id = int(resp.json()["grant_id"])
    yield auth_headers(seed["executor_user_id"])
    if grant_id is not None:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public.access_grants WHERE grant_id = :gid"),
                {"gid": grant_id},
            )


@pytest.fixture
def unprivileged_headers(seed):
    """Third user in the test unit without admin or HR grants."""
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        role_id = create_role(conn, f"pytest_unprivileged_{suffix}")
        user_id = create_user(
            conn,
            full_name="Pytest Unprivileged",
            role_id=role_id,
            unit_id=seed["unit_id"],
        )
    yield auth_headers(user_id)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM public.users WHERE user_id = :uid"), {"uid": user_id})
        conn.execute(text("DELETE FROM public.roles WHERE role_id = :rid"), {"rid": role_id})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_non_admin_cannot_access_personnel_api(client: TestClient, seed, non_admin_headers):
    _require_c4()
    resp = client.get("/admin/personnel/lifecycle/runs", headers=non_admin_headers)
    assert resp.status_code == 403


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_hr_manager_can_access_personnel_api(client: TestClient, seed, hr_manager_headers):
    _require_c4()
    resp = client.get("/admin/personnel/lifecycle/runs", headers=hr_manager_headers, params={"limit": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_preview_does_not_create_persons(client: TestClient, seed, admin_headers):
    _require_c4()
    suffix = uuid4().hex[:8]
    person = f"name:c4-preview-{suffix}"
    base = {"full_name": "Existing", "department": "A", "position_raw": "Doc", "org_unit_id": seed["unit_id"]}

    with engine.begin() as conn:
        prior_id, new_id = _setup_snapshot_pair(
            conn,
            user_id=seed["executor_user_id"],
            prior_entries={person: base},
            new_entries={
                person: base,
                f"name:c4-new-{suffix}": {
                    "full_name": "New",
                    "department": "B",
                    "position_raw": "Nurse",
                    "org_unit_id": seed["unit_id"],
                },
            },
        )
        persons_before = int(conn.execute(text("SELECT COUNT(*) FROM public.persons")).scalar_one())

    try:
        resp = client.post(
            "/admin/personnel/lifecycle/run-preview",
            headers=admin_headers,
            json=_lifecycle_payload(prior_id, new_id, sync_persons=True, enqueue=True),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["dry_run"] is True
        assert body["run_status"] == "completed"

        with engine.connect() as conn:
            persons_after = int(conn.execute(text("SELECT COUNT(*) FROM public.persons")).scalar_one())
        assert persons_before == persons_after
    finally:
        _cleanup_snapshot_pair(prior_id, new_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_execute_creates_lifecycle_run(client: TestClient, seed, admin_headers):
    _require_c4()
    suffix = uuid4().hex[:8]
    person = f"name:c4-run-{suffix}"

    with engine.begin() as conn:
        prior_id, new_id = _setup_snapshot_pair(
            conn,
            user_id=seed["executor_user_id"],
            prior_entries={},
            new_entries={
                person: {
                    "full_name": "API Run",
                    "department": "A",
                    "position_raw": "Doc",
                    "org_unit_id": seed["unit_id"],
                }
            },
        )
        runs_before = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM public.hr_personnel_lifecycle_runs
                    WHERE previous_snapshot_id = :prior AND snapshot_id = :new
                    """
                ),
                {"prior": prior_id, "new": new_id},
            ).scalar_one()
        )

    try:
        resp = client.post(
            "/admin/personnel/lifecycle/run",
            headers=admin_headers,
            json=_lifecycle_payload(prior_id, new_id),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["dry_run"] is False
        assert body["run_id"] is not None
        assert body["personnel_events"]["events_created"] > 0

        detail = client.get(f"/admin/personnel/lifecycle/runs/{body['run_id']}", headers=admin_headers)
        assert detail.status_code == 200
        assert detail.json()["status"] == "completed"

        with engine.connect() as conn:
            runs_after = int(
                conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM public.hr_personnel_lifecycle_runs
                        WHERE previous_snapshot_id = :prior AND snapshot_id = :new
                        """
                    ),
                    {"prior": prior_id, "new": new_id},
                ).scalar_one()
            )
        assert runs_after == runs_before + 1
    finally:
        _cleanup_snapshot_pair(prior_id, new_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_rerun_via_api_does_not_duplicate_events(client: TestClient, seed, admin_headers):
    _require_c4()
    suffix = uuid4().hex[:8]
    person = f"name:c4-rerun-{suffix}"

    with engine.begin() as conn:
        prior_id, new_id = _setup_snapshot_pair(
            conn,
            user_id=seed["executor_user_id"],
            prior_entries={},
            new_entries={
                person: {
                    "full_name": "Rerun",
                    "department": "A",
                    "position_raw": "Doc",
                    "org_unit_id": seed["unit_id"],
                }
            },
        )

    try:
        first = client.post(
            "/admin/personnel/lifecycle/run",
            headers=admin_headers,
            json=_lifecycle_payload(prior_id, new_id),
        )
        assert first.status_code == 200
        second = client.post(
            "/admin/personnel/lifecycle/run",
            headers=admin_headers,
            json=_lifecycle_payload(prior_id, new_id),
        )
        assert second.status_code == 200
        assert first.json()["personnel_events"]["events_created"] > 0
        assert second.json()["personnel_events"]["events_created"] == 0
    finally:
        _cleanup_snapshot_pair(prior_id, new_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_personnel_events_list_and_filter(client: TestClient, seed, admin_headers):
    _require_c4()
    suffix = uuid4().hex[:8]
    person = f"name:c4-events-{suffix}"

    with engine.begin() as conn:
        prior_id, new_id = _setup_snapshot_pair(
            conn,
            user_id=seed["executor_user_id"],
            prior_entries={},
            new_entries={
                person: {
                    "full_name": "Events",
                    "department": "A",
                    "position_raw": "Doc",
                    "org_unit_id": seed["unit_id"],
                }
            },
        )

    try:
        run_resp = client.post(
            "/admin/personnel/lifecycle/run",
            headers=admin_headers,
            json=_lifecycle_payload(prior_id, new_id),
        )
        assert run_resp.status_code == 200

        list_resp = client.get(
            "/admin/personnel/events",
            headers=admin_headers,
            params={
                "snapshot_id": new_id,
                "person_key": person,
                "event_type": "NEW_PERSON",
                "limit": 10,
                "sort_by": "detected_at",
                "sort_dir": "desc",
            },
        )
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert data["total"] >= 1
        event_id = data["items"][0]["personnel_event_id"]

        detail = client.get(f"/admin/personnel/events/{event_id}", headers=admin_headers)
        assert detail.status_code == 200
        assert detail.json()["person_key"] == person
    finally:
        _cleanup_snapshot_pair(prior_id, new_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_override_workflow_via_api(client: TestClient, seed, admin_headers):
    _require_c4()
    suffix = uuid4().hex[:8]
    scope_key = f"PERSON:match:c4-api-{suffix}"

    try:
        create_resp = client.post(
            "/admin/personnel/overrides",
            headers=admin_headers,
            json={
                "scope_type": "PERSON",
                "scope_key": scope_key,
                "field_path": "note.text",
                "override_value": "api note",
                "tier": 0,
                "owner_domain": "HR",
                "person_key": f"match:c4-api-{suffix}",
            },
        )
        assert create_resp.status_code == 200, create_resp.text
        override_id = int(create_resp.json()["override_id"])
        assert create_resp.json()["status"] == "active"

        list_resp = client.get(
            "/admin/personnel/overrides",
            headers=admin_headers,
            params={"scope_type": "PERSON", "limit": 5},
        )
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] >= 1

        revoke_resp = client.post(
            f"/admin/personnel/overrides/{override_id}/revoke",
            headers=admin_headers,
            json={"reason": "api test revoke reason"},
        )
        assert revoke_resp.status_code == 200
        assert revoke_resp.json()["status"] == "revoked"
    finally:
        _cleanup_overrides_for_scope_keys([scope_key])


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_tier2_approve_requires_hr_governance(
    client: TestClient, seed, admin_headers, hr_manager_headers, unprivileged_headers
):
    _require_c4()
    suffix = uuid4().hex[:8]
    scope_key = f"PERSON:match:c4-tier2-{suffix}"

    try:
        create_resp = client.post(
            "/admin/personnel/overrides",
            headers=hr_manager_headers,
            json={
                "scope_type": "PERSON",
                "scope_key": scope_key,
                "field_path": "identity.iin",
                "override_value": "123456789012",
                "tier": 2,
                "owner_domain": "HR",
                "justification": "C4 tier2 approve test",
                "evidence_url": "https://example.com/evidence.pdf",
                "person_key": f"match:c4-tier2-{suffix}",
            },
        )
        assert create_resp.status_code == 200, create_resp.text
        override_id = int(create_resp.json()["override_id"])
        assert create_resp.json()["status"] == "pending_approval"

        denied = client.post(
            f"/admin/personnel/overrides/{override_id}/approve",
            headers=unprivileged_headers,
            json={"comment": "should fail"},
        )
        assert denied.status_code == 403

        approved = client.post(
            f"/admin/personnel/overrides/{override_id}/approve",
            headers=admin_headers,
            json={"comment": "governance approver"},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "active"
    finally:
        _cleanup_overrides_for_scope_keys([scope_key])


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_effective_person_endpoint(client: TestClient, seed, admin_headers):
    _require_c4()
    suffix = uuid4().hex[:8]
    person_key = f"name:c4-effective-{suffix}"
    scope_key = f"PERSON:{person_key}"

    with engine.begin() as conn:
        prior_id, new_id = _setup_snapshot_pair(
            conn,
            user_id=seed["executor_user_id"],
            prior_entries={},
            new_entries={
                person_key: {
                    "full_name": "Canonical Name",
                    "department": "A",
                    "position_raw": "Doc",
                }
            },
        )

    try:
        create_resp = client.post(
            "/admin/personnel/overrides",
            headers=admin_headers,
            json={
                "scope_type": "PERSON",
                "scope_key": scope_key,
                "field_path": "roster.department",
                "override_value": "Dept Override",
                "tier": 0,
                "owner_domain": "HR",
                "person_key": person_key,
            },
        )
        assert create_resp.status_code == 200, create_resp.text

        resp = client.get(
            "/admin/personnel/effective-person",
            headers=admin_headers,
            params={"person_key": person_key, "snapshot_id": new_id},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["person_key"] == person_key
        assert body["canonical_payload"]["full_name"] == "Canonical Name"
        assert body["effective_payload"]["department"] == "Dept Override"
        assert len(body["applied_override_ids"]) >= 1
    finally:
        _cleanup_overrides_for_scope_keys([scope_key])
        _cleanup_snapshot_pair(prior_id, new_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_validation_endpoint(client: TestClient, seed, admin_headers):
    _require_c4()
    suffix = uuid4().hex[:8]
    person = f"name:c4-validate-{suffix}"

    with engine.begin() as conn:
        prior_id, new_id = _setup_snapshot_pair(
            conn,
            user_id=seed["executor_user_id"],
            prior_entries={},
            new_entries={
                person: {
                    "full_name": "Validate",
                    "department": "A",
                    "position_raw": "Doc",
                    "org_unit_id": seed["unit_id"],
                }
            },
        )

    try:
        resp = client.get(
            "/admin/personnel/lifecycle/validation",
            headers=admin_headers,
            params={"previous_snapshot_id": prior_id, "snapshot_id": new_id},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["previous_snapshot_id"] == prior_id
        assert body["snapshot_id"] == new_id
        assert len(body["checks"]) >= 4
        codes = {c["code"] for c in body["checks"]}
        assert "duplicate_active_overrides" in codes
        assert "personnel_events_stuck_detected" in codes
    finally:
        _cleanup_snapshot_pair(prior_id, new_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_partial_pipeline_flags(client: TestClient, seed, admin_headers):
    _require_c4()
    suffix = uuid4().hex[:8]
    person = f"name:c4-partial-{suffix}"

    with engine.begin() as conn:
        prior_id, new_id = _setup_snapshot_pair(
            conn,
            user_id=seed["executor_user_id"],
            prior_entries={},
            new_entries={
                person: {
                    "full_name": "Partial",
                    "department": "A",
                    "position_raw": "Doc",
                    "org_unit_id": seed["unit_id"],
                }
            },
        )
        persons_before = int(conn.execute(text("SELECT COUNT(*) FROM public.persons")).scalar_one())

    try:
        preview = client.post(
            "/admin/personnel/lifecycle/run-preview",
            headers=admin_headers,
            json=_lifecycle_payload(
                prior_id,
                new_id,
                refresh_cache=False,
                sync_persons=False,
                enqueue=False,
            ),
        )
        assert preview.status_code == 200
        body = preview.json()
        assert body["effective_cache"].get("skipped") is True
        assert body["person_sync"].get("skipped") is True

        with engine.connect() as conn:
            persons_after = int(conn.execute(text("SELECT COUNT(*) FROM public.persons")).scalar_one())
        assert persons_before == persons_after
    finally:
        _cleanup_snapshot_pair(prior_id, new_id)
