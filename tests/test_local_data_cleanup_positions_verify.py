# tests/test_local_data_cleanup_positions_verify.py
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text

_TOOLKIT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "local_data_cleanup"
if str(_TOOLKIT_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLKIT_DIR))

from personnel_cleanup_fk_graph import SafetyAbort, assert_local_dev_database  # noqa: E402
from positions_domain import (  # noqa: E402
    BLOCKED_UNEXPECTED_MISSING_POLICY,
    build_positions_verify_report,
    compute_allowlist_hash,
    validate_positions_verify_allowlist,
    verify_allowlisted_positions_removed,
    verify_blocked_position_entities,
    verify_protected_position_entities,
)


def _minimal_allowlist(*, positions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "version": 1,
        "protected": {
            "persons": [],
            "employees": [],
            "users": [],
            "units": [],
            "positions": [],
            "roles": [],
        },
        "persons": [],
        "employees": [],
        "users": [],
        "units": [],
        "assignments": [],
        "positions": positions
        or [
            {
                "id": 9001,
                "label": "test-pos",
                "reason": "fixture",
                "expected_signature": {"name": "pytest_verify_fixture", "category": "other"},
            }
        ],
        "identities": [],
        "batches": [],
        "snapshots": [],
        "audit": [],
        "roles": [],
        "reconciliation": {"items": [], "runs": []},
    }


class _MappingsResult:
    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows

    def mappings(self):
        mock = MagicMock()
        mock.all.return_value = self._rows
        mock.first.return_value = self._rows[0] if self._rows else None
        return mock


class _ScalarResult:
    def __init__(self, value: Any):
        self._value = value

    def scalar(self):
        return self._value


def _make_conn(handler):
    conn = MagicMock()

    def execute(stmt, params=None):
        sql = str(stmt)
        return handler(sql, params or {})

    conn.execute.side_effect = execute
    return conn


def test_validate_positions_verify_allowlist_requires_positions_section():
    with pytest.raises(SafetyAbort, match="allowlist.positions section is required"):
        validate_positions_verify_allowlist({"protected": {"positions": []}})


def test_validate_positions_verify_allowlist_rejects_empty_positions():
    allowlist = _minimal_allowlist()
    allowlist["positions"] = []
    with pytest.raises(SafetyAbort, match="at least one entry"):
        validate_positions_verify_allowlist(allowlist)


def test_validate_positions_verify_allowlist_rejects_duplicate_ids():
    allowlist = _minimal_allowlist(
        positions=[
            {"id": 10, "expected_signature": {"name": "a", "category": "other"}},
            {"id": 10, "expected_signature": {"name": "b", "category": "other"}},
        ]
    )
    with pytest.raises(SafetyAbort, match="duplicate id=10"):
        validate_positions_verify_allowlist(allowlist)


def test_validate_positions_verify_allowlist_rejects_protected_overlap():
    allowlist = _minimal_allowlist()
    allowlist["positions"] = [
        {"id": 1, "expected_signature": {"name": "Архивариус", "category": "other"}}
    ]
    with pytest.raises(SafetyAbort, match="overlaps protected"):
        validate_positions_verify_allowlist(allowlist)


def test_compute_allowlist_hash_is_stable():
    allowlist = _minimal_allowlist()
    assert compute_allowlist_hash(allowlist) == compute_allowlist_hash(allowlist)


def test_verify_allowlisted_positions_removed_passes_when_absent():
    allowlist = _minimal_allowlist()

    def handler(sql, params):
        if "FROM public.positions WHERE position_id" in sql:
            return _MappingsResult([])
        raise AssertionError(sql)

    conn = _make_conn(handler)
    result = verify_allowlisted_positions_removed(conn, allowlist)
    assert result["passed"] is True
    assert result["remaining_count"] == 0


def test_verify_allowlisted_positions_removed_fails_when_still_present():
    allowlist = _minimal_allowlist()

    def handler(sql, params):
        if "FROM public.positions WHERE position_id" in sql:
            return _MappingsResult(
                [{"position_id": 9001, "name": "pytest_verify_fixture", "category": "other"}]
            )
        raise AssertionError(sql)

    conn = _make_conn(handler)
    result = verify_allowlisted_positions_removed(conn, allowlist)
    assert result["passed"] is False
    assert result["remaining_count"] == 1


def test_verify_allowlisted_positions_removed_fails_on_id_reuse():
    allowlist = _minimal_allowlist()

    def handler(sql, params):
        if "FROM public.positions WHERE position_id" in sql:
            return _MappingsResult(
                [{"position_id": 9001, "name": "different_name_now", "category": "other"}]
            )
        raise AssertionError(sql)

    conn = _make_conn(handler)
    result = verify_allowlisted_positions_removed(conn, allowlist)
    assert result["passed"] is False
    assert result["id_reuse_failures"]


def test_verify_protected_position_entities_fails_when_archivist_missing():
    allowlist = _minimal_allowlist()

    def handler(sql, params):
        if "FROM public.positions WHERE position_id" in sql:
            return _MappingsResult([])
        raise AssertionError(sql)

    conn = _make_conn(handler)
    result = verify_protected_position_entities(conn, allowlist)
    assert result["passed"] is False
    assert any("position_id=1" in msg for msg in result["failures"])


def test_verify_protected_position_entities_fails_on_signature_mismatch():
    allowlist = _minimal_allowlist()
    allowlist["protected"]["positions"] = [
        {
            "id": 42,
            "label": "protected-test",
            "expected_signature": {"name": "Expected Name", "category": "other"},
        }
    ]

    def handler(sql, params):
        if "position_id = :id" in sql:
            pid = params.get("id")
            if pid == 1:
                return _MappingsResult(
                    [{"position_id": 1, "name": "Архивариус", "category": "other"}]
                )
            if pid == 42:
                return _MappingsResult(
                    [{"position_id": 42, "name": "Actual Different", "category": "other"}]
                )
        raise AssertionError((sql, params))

    conn = _make_conn(handler)
    result = verify_protected_position_entities(conn, allowlist)
    assert result["passed"] is False
    assert any("signature mismatch" in msg for msg in result["failures"])


def test_verify_blocked_position_entities_passes_when_expected_remain():
    before_manifest = {
        "blocked_candidates": [
            {"position_id": 298, "name": "PILOT hire 20260708"},
        ]
    }

    def handler(sql, params):
        if "information_schema.tables" in sql:
            return _ScalarResult(1)
        if "information_schema.columns" in sql:
            return _ScalarResult(0)
        if "FROM public.positions WHERE position_id" in sql:
            return _MappingsResult(
                [{"position_id": 298, "name": "PILOT hire 20260708", "category": "other"}]
            )
        if "COUNT(*)" in sql:
            return _ScalarResult(1)
        raise AssertionError(sql)

    conn = _make_conn(handler)
    result = verify_blocked_position_entities(conn, before_manifest=before_manifest)
    assert result["passed"] is True
    assert result["results"][0]["status"] == "present"


def test_verify_blocked_position_entities_fails_when_expected_missing():
    assert BLOCKED_UNEXPECTED_MISSING_POLICY == "fail"
    before_manifest = {
        "blocked_candidates": [
            {"position_id": 298, "name": "PILOT hire 20260708"},
        ]
    }

    def handler(sql, params):
        if "FROM public.positions WHERE position_id" in sql:
            return _MappingsResult([])
        raise AssertionError(sql)

    conn = _make_conn(handler)
    result = verify_blocked_position_entities(conn, before_manifest=before_manifest)
    assert result["passed"] is False
    assert result["results"][0]["status"] == "missing"


def test_wrong_database_name_fails_guard():
    with pytest.raises(SafetyAbort, match="does not match"):
        assert_local_dev_database(
            "postgresql://postgres@127.0.0.1:5432/wrong_db",
            expected_database_name="corpsite",
        )


def test_verify_performs_no_dml():
    """Ensure build_positions_verify_report issues only read queries."""
    allowlist = _minimal_allowlist()
    issued: list[str] = []

    def handler(sql, params):
        issued.append(sql.strip().upper())
        if "FROM PUBLIC.POSITIONS" in sql.upper() and "COUNT" not in sql.upper():
            return _MappingsResult([])
        if "COUNT(*)" in sql.upper():
            return _ScalarResult(0)
        if "INFORMATION_SCHEMA" in sql.upper():
            return _ScalarResult(0)
        if "ORG_UNIT_ALLOWED_POSITIONS" in sql.upper():
            return _MappingsResult([])
        if "ORG_UNITS" in sql.upper():
            return _MappingsResult([])
        if "ILIKE" in sql.upper():
            return _MappingsResult([])
        return _ScalarResult(0)

    conn = _make_conn(handler)
    build_positions_verify_report(
        conn,
        allowlist,
        {"database": "corpsite", "url_redacted": "postgresql://postgres@127.0.0.1:5432/corpsite"},
        before_manifest={"blocked_candidates": []},
    )
    forbidden = ("INSERT ", "UPDATE ", "DELETE ", "CREATE ", "ALTER ", "DROP ", "TRUNCATE ")
    for sql in issued:
        for token in forbidden:
            assert token not in sql, f"verify issued forbidden DML/DDL: {sql}"


def _db_available() -> bool:
    try:
        from app.db.engine import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture
def db_conn():
    from app.db.engine import engine

    if not _db_available():
        pytest.skip("Database unavailable")
    with engine.connect() as conn:
        trans = conn.begin()
        yield conn
        trans.rollback()


@pytest.mark.skipif(not _db_available(), reason="Database unavailable")
def test_integration_positions_verify_against_live_db(db_conn):
    """Read-only integration check: archivist and etalon positions present."""
    allowlist = _minimal_allowlist(
        positions=[
            {
                "id": 999999991,
                "label": "nonexistent-verify-test",
                "reason": "integration fixture — not in DB",
                "expected_signature": {"name": "nonexistent_verify_test", "category": "other"},
            }
        ]
    )
    report = build_positions_verify_report(
        db_conn,
        allowlist,
        {
            "host": "127.0.0.1",
            "database": "corpsite",
            "url_redacted": "postgresql://postgres@127.0.0.1:5432/corpsite",
            "classification": "local/dev",
        },
        before_manifest={
            "mode": "audit",
            "domain": "positions",
            "blocked_candidates": [],
        },
    )
    assert report["checks"]["allowlisted_positions_removed"]["passed"] is True
    assert report["checks"]["protected_positions"]["passed"] is True
    assert report["checks"]["etalon_hr_positions"]["passed"] is True
    assert report["checks"]["hr_allowed_etalon_links"]["passed"] is True
    assert report["checks"]["fk_integrity_deleted_positions"]["passed"] is True
    assert report["checks"]["execute_manifest_consistency"]["passed"] is True
