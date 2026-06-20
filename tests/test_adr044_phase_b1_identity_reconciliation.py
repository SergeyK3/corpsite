# tests/test_adr044_phase_b1_identity_reconciliation.py
"""Tests for ADR-044 B1 identity reconciliation dry-run."""
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
    OUTCOME_SKIP_ALREADY_FILLED,
    OUTCOME_SKIP_CONFLICT_DUPLICATE_IIN,
    OUTCOME_SKIP_CONFLICT_EXISTING_IIN,
    OUTCOME_SKIP_INCOMPLETE,
    SOURCE_P1,
    SOURCE_P2,
    SOURCE_P3,
    build_reconciliation_candidates,
    build_reconciliation_report,
    classify_candidate,
    normalize_iin,
    resolve_iin_for_person,
    run_r1a_dry_run,
    run_validation_gates,
)
from tests.conftest import auth_headers, insert_returning_id, table_exists

B1_TABLES = (
    "persons",
    "employees",
    "employee_identities",
    "hr_canonical_snapshots",
    "hr_canonical_snapshot_entries",
    "hr_snapshot_effective_entries",
    "hr_review_overrides",
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_b1() -> None:
    with engine.begin() as conn:
        if not all(table_exists(conn, table) for table in B1_TABLES):
            pytest.skip("ADR-044 B1 tables missing — run: alembic upgrade head")


@contextmanager
def _isolated_conn():
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            yield conn
        finally:
            trans.rollback()


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
        {"file_name": f"b1_{uuid4().hex[:8]}.xlsx", "uid": user_id},
    ).scalar_one()


def _insert_active_snapshot(
    conn,
    *,
    user_id: int,
    entries: dict[str, dict],
    employee_ids: dict[str, int] | None = None,
) -> int:
    conn.execute(
        text(
            """
            UPDATE public.hr_canonical_snapshots
            SET status = 'superseded', superseded_at = NOW()
            WHERE status = 'active' AND source_type = 'HR_CONTROL_LIST'
            """
        )
    )
    version = 944_000 + int(uuid4().hex[:3], 16)
    snapshot_id = insert_returning_id(
        conn,
        table="hr_canonical_snapshots",
        id_col="snapshot_id",
        values={
            "source_batch_id": _insert_batch(conn, user_id),
            "source_type": "HR_CONTROL_LIST",
            "version": version,
            "status": "active",
            "entry_count": len(entries),
            "promoted_by": user_id,
        },
    )
    employee_ids = employee_ids or {}
    for match_key, payload in entries.items():
        iin = payload.get("iin")
        emp_id = employee_ids.get(match_key)
        insert_returning_id(
            conn,
            table="hr_canonical_snapshot_entries",
            id_col="entry_id",
            values={
                "snapshot_id": snapshot_id,
                "entity_scope": match_key,
                "record_kind": "roster",
                "match_key": match_key,
                "canonical_hash": "b1" + uuid4().hex,
                "payload": json.dumps(payload),
                "iin": iin,
                "employee_id": emp_id,
            },
        )
    return int(snapshot_id)


def _insert_effective_row(
    conn,
    *,
    snapshot_id: int,
    match_key: str,
    payload: dict,
    entry_id: int,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO public.hr_snapshot_effective_entries (
                snapshot_id, canonical_entry_id, scope_type, scope_key,
                person_key, match_key, record_kind,
                effective_payload, payload_hash, override_version_hash
            )
            VALUES (
                :snapshot_id, :entry_id, 'PERSON', :scope_key,
                :person_key, :match_key, 'roster',
                CAST(:payload AS jsonb), :hash, :ovh
            )
            """
        ),
        {
            "snapshot_id": snapshot_id,
            "entry_id": entry_id,
            "scope_key": f"PERSON:{match_key}",
            "person_key": match_key,
            "match_key": match_key,
            "payload": json.dumps(payload),
            "hash": uuid4().hex,
            "ovh": uuid4().hex,
        },
    )


def _get_entry_id(conn, snapshot_id: int, match_key: str) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT entry_id FROM public.hr_canonical_snapshot_entries
                WHERE snapshot_id = :sid AND match_key = :mk
                """
            ),
            {"sid": snapshot_id, "mk": match_key},
        ).scalar_one()
    )


def _insert_person_employee(
    conn,
    *,
    full_name: str,
    match_key: str,
    iin: str | None = None,
) -> tuple[int, int]:
    person_id = insert_returning_id(
        conn,
        table="persons",
        id_col="person_id",
        values={
            "full_name": full_name,
            "match_key": match_key,
            "iin": iin,
            "person_status": "active",
            "source": "migration",
        },
    )
    employee_id = insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values={
            "full_name": full_name,
            "person_id": person_id,
            "is_active": True,
            "operational_status": "active",
        },
    )
    return int(person_id), int(employee_id)


# --- unit tests (no DB) ---


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("800115300290", "800115300290"),
        ("800 115 300 290", "800115300290"),
        ("123", None),
        (None, None),
        ("", None),
    ],
)
def test_normalize_iin(raw, expected):
    assert normalize_iin(raw) == expected


def test_classify_duplicate_iin_unit():
    with _isolated_conn() as conn:
        holder_id, _ = _insert_person_employee(
            conn,
            full_name="Holder",
            match_key="iin:111111111111",
            iin="111111111111",
        )
        person_id, _ = _insert_person_employee(
            conn,
            full_name="Target",
            match_key="name:target",
            iin=None,
        )
        person = {
            "person_id": person_id,
            "full_name": "Target",
            "match_key": "name:target",
            "iin": None,
        }
        resolved = {"iin": "111111111111", "source": SOURCE_P3, "chain": [], "ambiguous": False}
        result = classify_candidate(
            conn,
            person=person,
            resolved=resolved,
            employee_id=None,
            active_ei=None,
            canonical_person_key="name:target",
        )
        assert result["outcome"] == OUTCOME_SKIP_CONFLICT_DUPLICATE_IIN
        assert result["holder_person_id"] == holder_id


def test_classify_existing_iin_mismatch_unit():
    with _isolated_conn() as conn:
        person_id, _ = _insert_person_employee(
            conn,
            full_name="Mismatch",
            match_key="iin:800115300290",
            iin="800115300290",
        )
        person = conn.execute(
            text("SELECT * FROM public.persons WHERE person_id = :id"),
            {"id": person_id},
        ).mappings().first()
        resolved = {"iin": "999999999999", "source": SOURCE_P3, "chain": [], "ambiguous": False}
        result = classify_candidate(
            conn,
            person=dict(person),
            resolved=resolved,
            employee_id=None,
            active_ei=None,
            canonical_person_key="iin:800115300290",
        )
        assert result["outcome"] == OUTCOME_SKIP_CONFLICT_EXISTING_IIN


def test_classify_invalid_iin_via_incomplete():
    with _isolated_conn() as conn:
        person_id, _ = _insert_person_employee(
            conn,
            full_name="No IIN",
            match_key="name:no-iin",
            iin=None,
        )
        person = {"person_id": person_id, "full_name": "No IIN", "match_key": "name:no-iin", "iin": None}
        resolved = {"iin": None, "source": None, "chain": [], "ambiguous": False}
        result = classify_candidate(
            conn,
            person=person,
            resolved=resolved,
            employee_id=None,
            active_ei=None,
            canonical_person_key="name:no-iin",
        )
        assert result["outcome"] == OUTCOME_SKIP_INCOMPLETE


# --- integration tests ---


@pytest.mark.skipif(not _db_available(), reason="DB unavailable")
def test_precedence_p1_over_p3(seed):
    _require_b1()
    with _isolated_conn() as conn:
        uid = seed["initiator_user_id"]
        person_id, employee_id = _insert_person_employee(
            conn,
            full_name="Precedence Test",
            match_key="name:precedence test",
            iin=None,
        )
        canonical_key = f"emp:{employee_id}"
        snapshot_id = _insert_active_snapshot(
            conn,
            user_id=uid,
            entries={canonical_key: {"full_name": "Precedence Test", "iin": "800115300290"}},
            employee_ids={canonical_key: employee_id},
        )
        conn.execute(
            text(
                """
                INSERT INTO public.hr_review_overrides (
                    scope_type, scope_key, field_path, override_value,
                    status, tier, owner_domain, persistence_policy,
                    created_by_user_id, creation_channel, justification
                )
                VALUES (
                    'PERSON', :scope_key, 'identity.iin',
                    CAST(:val AS jsonb), 'active', 1, 'HR', 'until_incoming_matches',
                    :uid, 'review_ui', 'test override precedence'
                )
                """
            ),
            {
                "scope_key": f"PERSON:{canonical_key}",
                "val": json.dumps("900115300290"),
                "uid": uid,
            },
        )
        resolved = resolve_iin_for_person(
            conn,
            snapshot_id=snapshot_id,
            canonical_person_key=canonical_key,
            employee_id=employee_id,
        )
        assert resolved["source"] == SOURCE_P1
        assert resolved["iin"] == "900115300290"


@pytest.mark.skipif(not _db_available(), reason="DB unavailable")
def test_precedence_p2_when_no_override(seed):
    _require_b1()
    with _isolated_conn() as conn:
        uid = seed["initiator_user_id"]
        person_id, employee_id = _insert_person_employee(
            conn,
            full_name="Effective Cache",
            match_key="name:effective cache",
            iin=None,
        )
        canonical_key = f"emp:{employee_id}"
        snapshot_id = _insert_active_snapshot(
            conn,
            user_id=uid,
            entries={canonical_key: {"full_name": "Effective Cache", "iin": "800115300111"}},
            employee_ids={canonical_key: employee_id},
        )
        entry_id = _get_entry_id(conn, snapshot_id, canonical_key)
        _insert_effective_row(
            conn,
            snapshot_id=snapshot_id,
            match_key=canonical_key,
            payload={"full_name": "Effective Cache", "iin": "800115300222"},
            entry_id=entry_id,
        )
        resolved = resolve_iin_for_person(
            conn,
            snapshot_id=snapshot_id,
            canonical_person_key=canonical_key,
            employee_id=employee_id,
        )
        assert resolved["source"] == SOURCE_P2
        assert resolved["iin"] == "800115300222"


@pytest.mark.skipif(not _db_available(), reason="DB unavailable")
def test_abitaev_case_dry_run(seed):
    """Әбітаев-style: name match_key, emp canonical, IIN from canonical; match_key unchanged in preview."""
    _require_b1()
    with _isolated_conn() as conn:
        uid = seed["initiator_user_id"]
        iin = "800115300290"
        existing = conn.execute(
            text(
                """
                SELECT p.person_id, p.match_key, p.iin, e.employee_id
                FROM public.persons p
                JOIN public.employees e ON e.person_id = p.person_id
                WHERE p.person_id = 115
                LIMIT 1
                """
            )
        ).mappings().first()

        if existing:
            person_id = int(existing["person_id"])
            employee_id = int(existing["employee_id"])
            match_key = str(existing["match_key"])
        else:
            suffix = uuid4().hex[:8]
            match_key = f"name:abitaev test {suffix}"
            person_id, employee_id = _insert_person_employee(
                conn,
                full_name="Abitaev Test",
                match_key=match_key,
                iin=None,
            )

        canonical_key = f"emp:{employee_id}"
        snapshot_id = _insert_active_snapshot(
            conn,
            user_id=uid,
            entries={
                canonical_key: {
                    "full_name": "Abitaev Test",
                    "iin": iin,
                }
            },
            employee_ids={canonical_key: employee_id},
        )
        candidates = build_reconciliation_candidates(conn, snapshot_id=snapshot_id)
        hit = next(c for c in candidates if c["person_id"] == person_id)
        assert hit["match_key"] == match_key
        assert hit["canonical_person_key"] == canonical_key
        assert hit["resolved_iin"] == iin
        assert hit["outcome"] == OUTCOME_APPLY
        assert hit["would_update_person_iin"] is True
        assert hit["would_insert_employee_identity"] is True


@pytest.mark.skipif(not _db_available(), reason="DB unavailable")
def test_idempotent_dry_run(seed):
    _require_b1()
    with _isolated_conn() as conn:
        uid = seed["initiator_user_id"]
        person_id, employee_id = _insert_person_employee(
            conn,
            full_name="Idempotent",
            match_key="name:idempotent",
            iin=None,
        )
        canonical_key = f"emp:{employee_id}"
        snapshot_id = _insert_active_snapshot(
            conn,
            user_id=uid,
            entries={canonical_key: {"full_name": "Idempotent", "iin": "800115300333"}},
            employee_ids={canonical_key: employee_id},
        )
        report1 = run_r1a_dry_run(conn, snapshot_id=snapshot_id)
        report2 = run_r1a_dry_run(conn, snapshot_id=snapshot_id)
        assert report1["summary"]["apply_count"] == report2["summary"]["apply_count"]
        assert report1["summary"]["by_outcome"] == report2["summary"]["by_outcome"]


@pytest.mark.skipif(not _db_available(), reason="DB unavailable")
def test_validation_gates_g1_g5(seed):
    _require_b1()
    with _isolated_conn() as conn:
        uid = seed["initiator_user_id"]
        snapshot_id = _insert_active_snapshot(
            conn,
            user_id=uid,
            entries={"emp:1": {"full_name": "X", "iin": "800115300444"}},
        )
        candidates = build_reconciliation_candidates(conn, snapshot_id=snapshot_id)
        gates = run_validation_gates(conn, candidates=candidates, snapshot_id=snapshot_id)
        gate_ids = {g["gate_id"] for g in gates}
        assert "G1" in gate_ids
        assert "G5" in gate_ids
        g5 = next(g for g in gates if g["gate_id"] == "G5")
        assert g5["passed"] is True


@pytest.mark.skipif(not _db_available(), reason="DB unavailable")
def test_build_reconciliation_report_structure(seed):
    _require_b1()
    with _isolated_conn() as conn:
        uid = seed["initiator_user_id"]
        _insert_active_snapshot(
            conn,
            user_id=uid,
            entries={"emp:99": {"full_name": "Report", "iin": "800115300555"}},
        )
        report = build_reconciliation_report(conn)
        assert report["phase"] == "R1a"
        assert report["dry_run"] is True
        assert "gates" in report
        assert len(report["gates"]) >= 10
        assert "summary" in report


@pytest.mark.skipif(not _db_available(), reason="DB unavailable")
def test_api_preview_r1a(client: TestClient, seed, monkeypatch):
    _require_b1()
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    headers = auth_headers(seed["initiator_user_id"])
    resp = client.get("/admin/personnel/identity/reconciliation/r1a/preview", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["phase"] == "R1a"
    assert body["dry_run"] is True
    assert "gates" in body


@pytest.mark.skipif(not _db_available(), reason="DB unavailable")
def test_api_preview_requires_admin(client: TestClient, seed):
    _require_b1()
    headers = auth_headers(seed["executor_user_id"])
    resp = client.get("/admin/personnel/identity/reconciliation/r1a/preview", headers=headers)
    assert resp.status_code == 403


@pytest.mark.skipif(not _db_available(), reason="DB unavailable")
def test_skip_already_filled_not_in_apply(seed):
    _require_b1()
    with _isolated_conn() as conn:
        uid = seed["initiator_user_id"]
        person_id, employee_id = _insert_person_employee(
            conn,
            full_name="Filled",
            match_key="iin:800115300666",
            iin="800115300666",
        )
        canonical_key = f"emp:{employee_id}"
        snapshot_id = _insert_active_snapshot(
            conn,
            user_id=uid,
            entries={canonical_key: {"full_name": "Filled", "iin": "800115300666"}},
            employee_ids={canonical_key: employee_id},
        )
        candidates = build_reconciliation_candidates(conn, snapshot_id=snapshot_id)
        hit = next(c for c in candidates if c["person_id"] == person_id)
        assert hit["outcome"] == OUTCOME_SKIP_ALREADY_FILLED
