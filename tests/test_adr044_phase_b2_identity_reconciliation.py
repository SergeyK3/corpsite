# tests/test_adr044_phase_b2_identity_reconciliation.py
"""Tests for ADR-044 B2 identity reconciliation execute path."""
from __future__ import annotations

import json
from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.services.identity_reconciliation_service import (
    OUTCOME_APPLY,
    OUTCOME_SKIP_CONFLICT_DUPLICATE_IIN,
    OUTCOME_SKIP_CONFLICT_EI_MISMATCH,
    ITEM_STATUS_APPLIED,
    RUN_STATUS_COMPLETED,
    IdentityReconciliationError,
    apply_candidate,
    build_reconciliation_report,
    run_r1a_dry_run,
    run_r1a_execute,
)
from tests.conftest import auth_headers, table_exists
from tests.test_adr044_phase_b1_identity_reconciliation import (
    B1_TABLES,
    _db_available,
    _insert_active_snapshot,
    _insert_person_employee,
    _isolated_conn,
)

B2_TABLES = B1_TABLES + (
    "identity_reconciliation_runs",
    "identity_reconciliation_items",
)


def _require_b2() -> None:
    with engine.begin() as conn:
        if not all(table_exists(conn, table) for table in B2_TABLES):
            pytest.skip("ADR-044 B2 tables missing — run: alembic upgrade head")


def _persons_count(conn) -> int:
    return int(conn.execute(text("SELECT COUNT(*) FROM public.persons")).scalar_one())


def _users_employee_ids(conn) -> list[tuple[int, int | None]]:
    rows = conn.execute(
        text("SELECT user_id, employee_id FROM public.users ORDER BY user_id")
    ).all()
    return [(int(r[0]), int(r[1]) if r[1] is not None else None) for r in rows]


def _unique_iin() -> str:
    return f"8001{int(uuid4().hex[:8], 16) % 100000000:08d}"


def _setup_apply_candidate(conn, seed, *, iin: str) -> tuple[int, int, int, str]:
    uid = seed["initiator_user_id"]
    person_id, employee_id = _insert_person_employee(
        conn,
        full_name="Execute Test",
        match_key=f"name:execute test {uuid4().hex[:6]}",
        iin=None,
    )
    match_key = conn.execute(
        text("SELECT match_key FROM public.persons WHERE person_id = :id"),
        {"id": person_id},
    ).scalar_one()
    canonical_key = f"emp:{employee_id}"
    snapshot_id = _insert_active_snapshot(
        conn,
        user_id=uid,
        entries={canonical_key: {"full_name": "Execute Test", "iin": iin}},
        employee_ids={canonical_key: employee_id},
    )
    return int(person_id), int(employee_id), int(snapshot_id), str(match_key)


@contextmanager
def _committed_execute_fixture(seed, *, iin: str | None = None):
    """Commit setup data because run_r1a_execute uses independent transactions."""
    resolved_iin = iin or _unique_iin()
    with engine.begin() as conn:
        person_id, employee_id, snapshot_id, match_key = _setup_apply_candidate(
            conn, seed, iin=resolved_iin
        )
        batch_id = conn.execute(
            text(
                """
                SELECT source_batch_id FROM public.hr_canonical_snapshots
                WHERE snapshot_id = :sid
                """
            ),
            {"sid": snapshot_id},
        ).scalar_one()
    try:
        yield person_id, employee_id, snapshot_id, match_key, resolved_iin
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public.identity_reconciliation_items WHERE person_id = :pid"),
                {"pid": person_id},
            )
            conn.execute(
                text(
                    """
                    DELETE FROM public.security_audit_log
                    WHERE target_person_id = :pid
                      AND event_type = 'PERSON_IIN_RECONCILED'
                    """
                ),
                {"pid": person_id},
            )
            conn.execute(
                text(
                    """
                    DELETE FROM public.hr_snapshot_effective_entries
                    WHERE snapshot_id = :sid
                    """
                ),
                {"sid": snapshot_id},
            )
            conn.execute(
                text(
                    """
                    DELETE FROM public.hr_canonical_snapshot_entries
                    WHERE snapshot_id = :sid
                    """
                ),
                {"sid": snapshot_id},
            )
            conn.execute(
                text("DELETE FROM public.hr_canonical_snapshots WHERE snapshot_id = :sid"),
                {"sid": snapshot_id},
            )
            if batch_id is not None:
                conn.execute(
                    text("DELETE FROM public.hr_import_batches WHERE batch_id = :bid"),
                    {"bid": batch_id},
                )
            conn.execute(
                text(
                    """
                    DELETE FROM public.employee_identities
                    WHERE employee_id = :eid AND identity_type = 'IIN'
                    """
                ),
                {"eid": employee_id},
            )
            conn.execute(
                text("DELETE FROM public.employees WHERE employee_id = :eid"),
                {"eid": employee_id},
            )
            conn.execute(text("DELETE FROM public.persons WHERE person_id = :pid"), {"pid": person_id})


@pytest.mark.skipif(not _db_available(), reason="DB unavailable")
def test_execute_applies_persons_iin(seed):
    _require_b2()
    with _committed_execute_fixture(seed) as (person_id, _, snapshot_id, match_key, resolved_iin):
        with engine.connect() as conn:
            report = run_r1a_execute(
                conn,
                actor_user_id=seed["initiator_user_id"],
                snapshot_id=snapshot_id,
                person_id=person_id,
            )
        assert report["dry_run"] is False
        assert report["execute_summary"]["applied"] == 1
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT iin, match_key FROM public.persons WHERE person_id = :id"),
                {"id": person_id},
            ).mappings().first()
        assert row["iin"] == resolved_iin
        assert row["match_key"] == match_key


@pytest.mark.skipif(not _db_available(), reason="DB unavailable")
def test_execute_inserts_employee_identities(seed):
    _require_b2()
    with _committed_execute_fixture(seed) as (person_id, employee_id, snapshot_id, _, resolved_iin):
        with engine.connect() as conn:
            run_r1a_execute(
                conn,
                actor_user_id=seed["initiator_user_id"],
                snapshot_id=snapshot_id,
                person_id=person_id,
            )
            ei = conn.execute(
                text(
                    """
                    SELECT identity_value
                    FROM public.employee_identities
                    WHERE employee_id = :eid AND identity_type = 'IIN' AND valid_to IS NULL
                    """
                ),
                {"eid": employee_id},
            ).mappings().first()
        assert ei is not None
        assert ei["identity_value"] == resolved_iin


@pytest.mark.skipif(not _db_available(), reason="DB unavailable")
def test_execute_does_not_change_match_key(seed):
    _require_b2()
    with _committed_execute_fixture(seed) as (person_id, _, snapshot_id, match_key, _):
        with engine.connect() as conn:
            run_r1a_execute(
                conn,
                actor_user_id=seed["initiator_user_id"],
                snapshot_id=snapshot_id,
                person_id=person_id,
            )
            after = conn.execute(
                text("SELECT match_key FROM public.persons WHERE person_id = :id"),
                {"id": person_id},
            ).scalar_one()
        assert after == match_key


@pytest.mark.skipif(not _db_available(), reason="DB unavailable")
def test_execute_does_not_create_person(seed):
    _require_b2()
    with _committed_execute_fixture(seed) as (person_id, _, snapshot_id, _, _):
        with engine.connect() as conn:
            before_execute = _persons_count(conn)
            run_r1a_execute(
                conn,
                actor_user_id=seed["initiator_user_id"],
                snapshot_id=snapshot_id,
                person_id=person_id,
            )
            assert _persons_count(conn) == before_execute


@pytest.mark.skipif(not _db_available(), reason="DB unavailable")
def test_execute_skips_already_filled(seed):
    _require_b2()
    with _committed_execute_fixture(seed) as (person_id, _, snapshot_id, _, resolved_iin):
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE public.persons SET iin = :iin WHERE person_id = :id"),
                {"iin": resolved_iin, "id": person_id},
            )
        with engine.connect() as conn:
            report = run_r1a_execute(
                conn,
                actor_user_id=seed["initiator_user_id"],
                snapshot_id=snapshot_id,
                person_id=person_id,
            )
        assert report["execute_summary"]["applied"] == 0


@pytest.mark.skipif(not _db_available(), reason="DB unavailable")
def test_execute_skips_conflicting_iin(seed):
    _require_b2()
    iin = _unique_iin()
    with engine.begin() as conn:
        _insert_person_employee(
            conn,
            full_name="Holder",
            match_key=f"iin:{iin}",
            iin=iin,
        )
    with _committed_execute_fixture(seed, iin=iin) as (person_id, _, snapshot_id, _, _):
        with engine.connect() as conn:
            preview = run_r1a_dry_run(conn, snapshot_id=snapshot_id)
            hit = next(c for c in preview["candidates"] if c["person_id"] == person_id)
            assert hit["outcome"] == OUTCOME_SKIP_CONFLICT_DUPLICATE_IIN
            report = run_r1a_execute(
                conn,
                actor_user_id=seed["initiator_user_id"],
                snapshot_id=snapshot_id,
                person_id=person_id,
            )
            row = conn.execute(
                text("SELECT iin FROM public.persons WHERE person_id = :id"),
                {"id": person_id},
            ).scalar_one()
        assert report["execute_summary"]["applied"] == 0
        assert row is None


@pytest.mark.skipif(not _db_available(), reason="DB unavailable")
def test_execute_skips_ei_mismatch(seed):
    _require_b2()
    with _committed_execute_fixture(seed) as (person_id, employee_id, snapshot_id, _, resolved_iin):
        wrong_iin = _unique_iin()
        while wrong_iin == resolved_iin:
            wrong_iin = _unique_iin()
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO public.employee_identities (
                        employee_id, identity_type, identity_value, is_primary, created_by
                    )
                    VALUES (:eid, 'IIN', :iin, TRUE, :uid)
                    """
                ),
                {"eid": employee_id, "iin": wrong_iin, "uid": seed["initiator_user_id"]},
            )
        with engine.connect() as conn:
            preview = run_r1a_dry_run(conn, snapshot_id=snapshot_id)
            hit = next(c for c in preview["candidates"] if c["person_id"] == person_id)
            assert hit["outcome"] == OUTCOME_SKIP_CONFLICT_EI_MISMATCH
            report = run_r1a_execute(
                conn,
                actor_user_id=seed["initiator_user_id"],
                snapshot_id=snapshot_id,
                person_id=person_id,
            )
        assert report["execute_summary"]["applied"] == 0


@pytest.mark.skipif(not _db_available(), reason="DB unavailable")
def test_execute_is_idempotent(seed):
    _require_b2()
    with _committed_execute_fixture(seed) as (person_id, _, snapshot_id, _, _):
        with engine.connect() as conn:
            first = run_r1a_execute(
                conn,
                actor_user_id=seed["initiator_user_id"],
                snapshot_id=snapshot_id,
                person_id=person_id,
            )
            second = run_r1a_execute(
                conn,
                actor_user_id=seed["initiator_user_id"],
                snapshot_id=snapshot_id,
                person_id=person_id,
            )
        assert first["execute_summary"]["applied"] == 1
        assert second["execute_summary"]["applied"] == 0


@pytest.mark.skipif(not _db_available(), reason="DB unavailable")
def test_per_person_rollback_payload(seed):
    _require_b2()
    resolved_iin = _unique_iin()
    with _isolated_conn() as conn:
        person_id, employee_id, snapshot_id, match_key = _setup_apply_candidate(
            conn, seed, iin=resolved_iin
        )
        preview = build_reconciliation_report(conn, snapshot_id=snapshot_id)
        candidate = next(c for c in preview["apply_preview"] if c["person_id"] == person_id)
        run_id = conn.execute(
            text(
                """
                INSERT INTO public.identity_reconciliation_runs (
                    phase, dry_run, actor_user_id, snapshot_id, status
                )
                VALUES ('R1a', FALSE, :uid, :sid, 'running')
                RETURNING run_id
                """
            ),
            {"uid": seed["initiator_user_id"], "sid": snapshot_id},
        ).scalar_one()
        result = apply_candidate(
            conn,
            candidate=candidate,
            snapshot_id=snapshot_id,
            actor_user_id=seed["initiator_user_id"],
            run_id=int(run_id),
        )
        assert result["status"] == ITEM_STATUS_APPLIED
        item = conn.execute(
            text(
                """
                SELECT rollback_payload
                FROM public.identity_reconciliation_items
                WHERE run_id = :run_id AND person_id = :pid
                """
            ),
            {"run_id": run_id, "pid": person_id},
        ).mappings().first()
        payload = item["rollback_payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        assert payload["previous_iin"] is None
        assert payload["resolved_iin"] == resolved_iin
        assert payload["match_key"] == match_key
        assert payload.get("ei_identity_id") is not None

        conn.execute(
            text("UPDATE public.persons SET iin = NULL WHERE person_id = :id"),
            {"id": person_id},
        )
        if payload.get("ei_identity_id"):
            conn.execute(
                text("DELETE FROM public.employee_identities WHERE identity_id = :id"),
                {"id": payload["ei_identity_id"]},
            )
        row = conn.execute(
            text("SELECT iin FROM public.persons WHERE person_id = :id"),
            {"id": person_id},
        ).scalar_one()
        assert row is None


@pytest.mark.skipif(not _db_available(), reason="DB unavailable")
def test_g1_blocks_batch_execute(seed, monkeypatch):
    _require_b2()

    def _blocked_preview(conn, *, snapshot_id=None):
        return {
            "execute_allowed": False,
            "snapshot_id": snapshot_id or 1,
            "gates": [{"gate_id": "G1", "blocks_execute": True, "count": 1}],
            "apply_preview": [],
            "summary": {"apply_count": 0},
        }

    monkeypatch.setattr(
        "app.services.identity_reconciliation_service.build_reconciliation_report",
        _blocked_preview,
    )
    with engine.connect() as conn:
        with pytest.raises(IdentityReconciliationError) as exc:
            run_r1a_execute(
                conn,
                actor_user_id=seed["initiator_user_id"],
                snapshot_id=1,
            )
    assert "G1" in exc.value.message


@pytest.mark.skipif(not _db_available(), reason="DB unavailable")
def test_g4_blocks_batch_execute(seed):
    _require_b2()
    with _isolated_conn() as conn:
        uid = seed["initiator_user_id"]
        shared_iin = "800115300788"
        p1, e1 = _insert_person_employee(
            conn, full_name="Shared A", match_key=f"name:shared a {uuid4().hex[:4]}", iin=None
        )
        p2, e2 = _insert_person_employee(
            conn, full_name="Shared B", match_key=f"name:shared b {uuid4().hex[:4]}", iin=None
        )
        snapshot_id = _insert_active_snapshot(
            conn,
            user_id=uid,
            entries={
                f"emp:{e1}": {"full_name": "Shared A", "iin": shared_iin},
                f"emp:{e2}": {"full_name": "Shared B", "iin": shared_iin},
            },
            employee_ids={f"emp:{e1}": e1, f"emp:{e2}": e2},
        )
        preview = run_r1a_dry_run(conn, snapshot_id=snapshot_id)
        g4 = next(g for g in preview["gates"] if g["gate_id"] == "G4")
        assert g4["count"] >= 1
        assert preview["execute_allowed"] is False


@pytest.mark.skipif(not _db_available(), reason="DB unavailable")
def test_g5_blocks_batch_execute(seed):
    _require_b2()
    with _isolated_conn() as conn:
        conn.execute(
            text(
                """
                UPDATE public.hr_canonical_snapshots
                SET status = 'superseded', superseded_at = NOW()
                WHERE status = 'active' AND source_type = 'HR_CONTROL_LIST'
                """
            )
        )
        preview = build_reconciliation_report(conn)
        assert preview["execute_allowed"] is False


@pytest.mark.skipif(not _db_available(), reason="DB unavailable")
def test_abitaev_case_execute(seed):
    _require_b2()
    with _committed_execute_fixture(seed) as (person_id, _, snapshot_id, match_key, resolved_iin):
        with engine.connect() as conn:
            users_before = _users_employee_ids(conn)
        with engine.connect() as conn:
            report = run_r1a_execute(
                conn,
                actor_user_id=seed["initiator_user_id"],
                snapshot_id=snapshot_id,
                person_id=person_id,
            )
        assert report["execute_summary"]["applied"] == 1
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT iin, match_key FROM public.persons WHERE person_id = :id"),
                {"id": person_id},
            ).mappings().first()
            dup_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM public.persons
                    WHERE iin = :iin AND person_status = 'active'
                    """
                ),
                {"iin": resolved_iin},
            ).scalar_one()
            users_after = _users_employee_ids(conn)
            rerun = run_r1a_execute(
                conn,
                actor_user_id=seed["initiator_user_id"],
                snapshot_id=snapshot_id,
                person_id=person_id,
            )
        assert row["iin"] == resolved_iin
        assert row["match_key"] == match_key
        assert int(dup_count) == 1
        assert users_after == users_before
        assert rerun["execute_summary"]["applied"] == 0


@pytest.mark.skipif(not _db_available(), reason="DB unavailable")
def test_execute_writes_audit_and_journal(seed):
    _require_b2()
    with _committed_execute_fixture(seed) as (person_id, _, snapshot_id, _, _):
        with engine.connect() as conn:
            report = run_r1a_execute(
                conn,
                actor_user_id=seed["initiator_user_id"],
                snapshot_id=snapshot_id,
                person_id=person_id,
            )
            run_id = report["run_id"]
            run = conn.execute(
                text(
                    "SELECT status, dry_run FROM public.identity_reconciliation_runs WHERE run_id = :id"
                ),
                {"id": run_id},
            ).mappings().first()
            item_count = conn.execute(
                text(
                    "SELECT COUNT(*) FROM public.identity_reconciliation_items WHERE run_id = :id"
                ),
                {"id": run_id},
            ).scalar_one()
            audit_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM public.security_audit_log
                    WHERE event_type = 'PERSON_IIN_RECONCILED'
                      AND target_person_id = :pid
                    """
                ),
                {"pid": person_id},
            ).scalar_one()
        assert run["dry_run"] is False
        assert run["status"] == RUN_STATUS_COMPLETED
        assert int(item_count) >= 1
        assert int(audit_count) >= 1


@pytest.mark.skipif(not _db_available(), reason="DB unavailable")
def test_api_execute_requires_admin(client: TestClient, seed, monkeypatch):
    _require_b2()
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    headers = auth_headers(seed["initiator_user_id"])
    with _committed_execute_fixture(seed) as (person_id, _, snapshot_id, _, _):
        resp = client.post(
            "/admin/personnel/identity/reconciliation/r1a/execute",
            headers=headers,
            json={"snapshot_id": snapshot_id, "person_id": person_id, "limit": 1},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["dry_run"] is False
    assert "run_id" in body
