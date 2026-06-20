# tests/test_adr043_phase_b3_runtime_services.py
"""Tests for ADR-043 Phase B3 runtime override and effective canonical services."""
from __future__ import annotations

import json
from contextlib import contextmanager
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.hr_effective_canonical_service import (
    apply_overrides_to_payload,
    compute_override_version_hash,
    refresh_person_effective_entry,
    resolve_effective_person,
)
from app.services.hr_override_stewardship_service import (
    StewardshipRuleNotFoundError,
    resolve_stewardship_rule,
)
from app.services.hr_review_override_backfill_service import execute_backfill, preview_backfill
from app.services.hr_review_override_service import (
    EVENT_APPROVED,
    EVENT_CREATED,
    EVENT_MARKED_STALE,
    EVENT_RECONFIRMED,
    EVENT_SUPERSEDED,
    InvalidOverrideTransitionError,
    ReviewOverrideError,
    approve_override,
    create_override,
    mark_stale,
    reconfirm_override,
    reject_override,
    revoke_override,
    supersede_override,
)
from tests.conftest import insert_returning_id, table_exists

PHASE_B2_TABLES = (
    "hr_override_stewardship_rules",
    "hr_review_overrides",
    "hr_review_override_history",
    "hr_snapshot_effective_entries",
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_b3() -> None:
    with _isolated_conn() as conn:
        if not all(table_exists(conn, table) for table in PHASE_B2_TABLES):
            pytest.skip("ADR-043 Phase B2/B3 tables missing — run: alembic upgrade head")


def _history_events(conn, override_id: int) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT event_type
            FROM public.hr_review_override_history
            WHERE override_id = :oid
            ORDER BY history_id ASC
            """
        ),
        {"oid": override_id},
    ).fetchall()
    return [str(row[0]) for row in rows]


@contextmanager
def _isolated_conn():
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            yield conn
        finally:
            trans.rollback()


def _ensure_test_snapshot(conn, *, user_id: int, match_key: str) -> tuple[int, int]:
    """Return (snapshot_id, entry_id) for an isolated active snapshot row."""
    batch_id = conn.execute(
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
        {"file_name": f"b3_snapshot_{uuid4().hex[:8]}.xlsx", "uid": user_id},
    ).scalar_one()
    snapshot_id = insert_returning_id(
        conn,
        table="hr_canonical_snapshots",
        id_col="snapshot_id",
        values={
            "source_batch_id": batch_id,
            "source_type": "HR_CONTROL_LIST",
            "version": 999_000 + int(uuid4().hex[:4], 16) % 1000,
            "status": "superseded",
            "entry_count": 1,
            "promoted_by": user_id,
        },
    )
    payload = {
        "full_name": "Test Person",
        "iin": "123456789012",
        "birth_date": "1990-01-01",
        "department": "Dept A",
        "position_raw": "Doctor",
    }
    entry_id = insert_returning_id(
        conn,
        table="hr_canonical_snapshot_entries",
        id_col="entry_id",
        values={
            "snapshot_id": snapshot_id,
            "entity_scope": "employee",
            "record_kind": "roster",
            "match_key": match_key,
            "canonical_hash": "pytest" + uuid4().hex,
            "payload": json.dumps(payload),
        },
    )
    return snapshot_id, entry_id, int(batch_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_stewardship_resolves_identity_iin(seed):
    _require_b3()
    with _isolated_conn() as conn:
        rule = resolve_stewardship_rule(conn, field_path="identity.iin", scope_type="PERSON")
    assert int(rule["required_tier"]) == 2
    assert rule["owner_domain"] == "HR"
    assert bool(rule["requires_evidence"]) is True


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_create_tier0_override_active_immediately(seed):
    _require_b3()
    user_id = seed["executor_user_id"]
    suffix = uuid4().hex[:8]
    scope_key = f"PERSON:match:b3-tier0-{suffix}"

    with _isolated_conn() as conn:
        created = create_override(
            conn,
            scope_type="PERSON",
            scope_key=scope_key,
            field_path="note.text",
            override_value="operator note",
            created_by_user_id=user_id,
            tier=0,
            owner_domain="HR",
            person_key=f"match:b3-tier0-{suffix}",
        )
        assert created["status"] == "active"
        events = _history_events(conn, int(created["override_id"]))
        assert events == [EVENT_CREATED]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_tier_validation_rejects_wrong_tier(seed):
    _require_b3()
    user_id = seed["executor_user_id"]
    suffix = uuid4().hex[:8]
    scope_key = f"PERSON:match:b3-tier-{suffix}"

    with _isolated_conn() as conn:
        with pytest.raises(StewardshipRuleNotFoundError):
            create_override(
                conn,
                scope_type="PERSON",
                scope_key=scope_key,
                field_path="identity.iin",
                override_value="123456789012",
                created_by_user_id=user_id,
                tier=0,
                owner_domain="HR",
                evidence_url="https://example.com/evidence",
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_evidence_required_for_identity_iin(seed):
    _require_b3()
    user_id = seed["executor_user_id"]
    suffix = uuid4().hex[:8]
    scope_key = f"PERSON:match:b3-evidence-{suffix}"

    with _isolated_conn() as conn:
        with pytest.raises(StewardshipRuleNotFoundError):
            create_override(
                conn,
                scope_type="PERSON",
                scope_key=scope_key,
                field_path="identity.iin",
                override_value="123456789012",
                created_by_user_id=user_id,
                tier=2,
                owner_domain="HR",
                justification="Missing evidence should fail validation",
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_tier2_pending_requires_second_approver(seed):
    _require_b3()
    creator_id = seed["executor_user_id"]
    approver_id = seed["initiator_user_id"]
    suffix = uuid4().hex[:8]
    scope_key = f"PERSON:match:b3-tier2-{suffix}"

    override_id: int | None = None
    with _isolated_conn() as conn:
        created = create_override(
            conn,
            scope_type="PERSON",
            scope_key=scope_key,
            field_path="identity.iin",
            override_value="123456789012",
            created_by_user_id=creator_id,
            tier=2,
            owner_domain="HR",
            justification="Tier 2 identity correction for pytest",
            evidence_url="https://example.com/evidence.pdf",
        )
        override_id = int(created["override_id"])
        assert created["status"] == "pending_approval"

        with pytest.raises(ReviewOverrideError):
            approve_override(
                conn,
                override_id=override_id,
                approved_by_user_id=creator_id,
            )

        approved = approve_override(
            conn,
            override_id=override_id,
            approved_by_user_id=approver_id,
            approval_comment="Second approver confirmed",
        )
        assert approved["status"] == "active"
        events = _history_events(conn, override_id)
        assert EVENT_CREATED in events
        assert EVENT_APPROVED in events


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_supersede_flow(seed):
    _require_b3()
    user_id = seed["executor_user_id"]
    suffix = uuid4().hex[:8]
    scope_key = f"PERSON:match:b3-supersede-{suffix}"

    old_id: int | None = None
    new_id: int | None = None
    with _isolated_conn() as conn:
        old = create_override(
            conn,
            scope_type="PERSON",
            scope_key=scope_key,
            field_path="note.text",
            override_value="old note",
            created_by_user_id=user_id,
            tier=0,
            owner_domain="HR",
        )
        old_id = int(old["override_id"])

        new = supersede_override(
            conn,
            old_override_id=old_id,
            new_override_value="new note",
            created_by_user_id=user_id,
        )
        new_id = int(new["override_id"])
        assert new["status"] == "active"

        old_row = conn.execute(
            text("SELECT status, superseded_by_override_id FROM public.hr_review_overrides WHERE override_id = :id"),
            {"id": old_id},
        ).mappings().one()
        assert old_row["status"] == "superseded"
        assert int(old_row["superseded_by_override_id"]) == new_id

        events = _history_events(conn, old_id)
        assert EVENT_SUPERSEDED in events


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_stale_and_reconfirm_flow(seed):
    _require_b3()
    user_id = seed["executor_user_id"]
    suffix = uuid4().hex[:8]
    scope_key = f"PERSON:match:b3-stale-{suffix}"

    with _isolated_conn() as conn:
        created = create_override(
            conn,
            scope_type="PERSON",
            scope_key=scope_key,
            field_path="note.text",
            override_value="stale candidate",
            created_by_user_id=user_id,
            tier=0,
            owner_domain="HR",
        )
        oid = int(created["override_id"])

        marked = mark_stale(conn, override_id=oid, stale_reason="document_expired", actor_user_id=user_id)
        assert marked["stale_flag"] is True
        assert EVENT_MARKED_STALE in _history_events(conn, oid)

        reconfirmed = reconfirm_override(conn, override_id=oid, reconfirmed_by_user_id=user_id)
        assert reconfirmed["stale_flag"] is False
        assert EVENT_RECONFIRMED in _history_events(conn, oid)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_duplicate_active_override_rejected(seed):
    _require_b3()
    user_id = seed["executor_user_id"]
    suffix = uuid4().hex[:8]
    scope_key = f"PERSON:match:b3-dup-{suffix}"

    with _isolated_conn() as conn:
        first = create_override(
            conn,
            scope_type="PERSON",
            scope_key=scope_key,
            field_path="note.text",
            override_value="first",
            created_by_user_id=user_id,
            tier=0,
            owner_domain="HR",
        )
        with pytest.raises(ReviewOverrideError):
            create_override(
                conn,
                scope_type="PERSON",
                scope_key=scope_key,
                field_path="note.text",
                override_value="second",
                created_by_user_id=user_id,
                tier=0,
                owner_domain="HR",
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_apply_overrides_to_payload_unit():
    canonical = {"full_name": "Base Name", "iin": "111111111111"}
    overrides = [
        {"override_id": 2, "field_path": "identity.full_name", "override_value": "Effective Name"},
        {"override_id": 1, "field_path": "identity.iin", "override_value": "222222222222"},
    ]
    effective, applied_ids, _ = apply_overrides_to_payload(canonical, overrides)
    assert effective["full_name"] == "Effective Name"
    assert effective["iin"] == "222222222222"
    assert applied_ids == [2, 1]
    assert "identity.full_name" in effective["_override_fields"]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_resolve_effective_person_and_cache_refresh(seed):
    _require_b3()
    user_id = seed["executor_user_id"]
    suffix = uuid4().hex[:8]
    person_key = f"name:b3-effective-{suffix}"
    scope_key = f"PERSON:{person_key}"

    snapshot_id: int | None = None
    override_id: int | None = None
    with _isolated_conn() as conn:
        if not table_exists(conn, "hr_canonical_snapshots"):
            pytest.skip("canonical snapshot tables missing")

        snapshot_id, _entry_id, batch_id = _ensure_test_snapshot(conn, user_id=user_id, match_key=person_key)

        created = create_override(
            conn,
            scope_type="PERSON",
            scope_key=scope_key,
            field_path="identity.full_name",
            override_value="Overridden Name",
            created_by_user_id=user_id,
            tier=2,
            owner_domain="HR",
            justification="Effective resolver pytest override",
            evidence_url="https://example.com/evidence",
            person_key=person_key,
        )
        override_id = int(created["override_id"])
        approve_override(
            conn,
            override_id=override_id,
            approved_by_user_id=seed["initiator_user_id"],
        )

        resolved = resolve_effective_person(conn, person_key=person_key, snapshot_id=snapshot_id)
        assert resolved["effective_payload"]["full_name"] == "Overridden Name"
        assert override_id in resolved["applied_override_ids"]

        first_refresh = refresh_person_effective_entry(
            conn, person_key=person_key, snapshot_id=snapshot_id
        )
        second_refresh = refresh_person_effective_entry(
            conn, person_key=person_key, snapshot_id=snapshot_id
        )
        assert first_refresh["payload_hash"] == second_refresh["payload_hash"]
        assert first_refresh["override_version_hash"] == second_refresh["override_version_hash"]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_backfill_dry_run_and_execute_idempotent(seed):
    _require_b3()
    user_id = seed["executor_user_id"]

    with _isolated_conn() as conn:
        preview = preview_backfill(conn, default_created_by_user_id=user_id)
        assert "create_count" in preview
        assert "skip_count" in preview

        dry = execute_backfill(conn, dry_run=True, default_created_by_user_id=user_id)
        assert dry["dry_run"] is True
        assert dry["created_count"] == 0

        if dry["create_count"] == 0:
            return

        first = execute_backfill(conn, dry_run=False, default_created_by_user_id=user_id)
        second = execute_backfill(conn, dry_run=False, default_created_by_user_id=user_id)
        assert first["created_count"] >= 0
        assert second["created_count"] == 0


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_revoke_requires_active(seed):
    _require_b3()
    user_id = seed["executor_user_id"]
    suffix = uuid4().hex[:8]
    scope_key = f"PERSON:match:b3-revoke-{suffix}"

    with _isolated_conn() as conn:
        created = create_override(
            conn,
            scope_type="PERSON",
            scope_key=scope_key,
            field_path="note.text",
            override_value="revoke me",
            created_by_user_id=user_id,
            tier=0,
            owner_domain="HR",
        )
        oid = int(created["override_id"])
        revoked = revoke_override(
            conn,
            override_id=oid,
            revoked_by_user_id=user_id,
            revoke_reason="Manual revoke during pytest",
        )
        assert revoked["status"] == "revoked"
        with pytest.raises(InvalidOverrideTransitionError):
            revoke_override(
                conn,
                override_id=oid,
                revoked_by_user_id=user_id,
                revoke_reason="Cannot revoke twice",
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_override_version_hash_stable():
    overrides = [
        {"override_id": 10, "updated_at": "2026-01-01T00:00:00+00:00"},
        {"override_id": 5, "updated_at": "2026-01-02T00:00:00+00:00"},
    ]
    h1 = compute_override_version_hash(overrides)
    h2 = compute_override_version_hash(list(reversed(overrides)))
    assert h1 == h2
