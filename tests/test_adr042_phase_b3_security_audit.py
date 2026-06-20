# tests/test_adr042_phase_b3_security_audit.py
"""Tests for ADR-042 Phase B3 security audit service."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.security_audit_service import (
    list_security_events,
    sanitize_metadata,
    write_security_event,
)
from tests.conftest import table_exists


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_b2() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "security_audit_log"):
            pytest.skip("ADR-042 B2 security_audit_log missing")


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_sanitize_metadata_rejects_password_like_keys():
    with pytest.raises(ValueError, match="Forbidden"):
        sanitize_metadata({"password": "secret"})

    with pytest.raises(ValueError, match="Forbidden"):
        sanitize_metadata({"user_token": "abc"})

    clean = sanitize_metadata({"login_masked": "a***@corp.local", "grant_id": 1})
    assert clean == {"login_masked": "a***@corp.local", "grant_id": 1}


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_write_and_list_security_event(seed):
    _require_b2()
    suffix = uuid4().hex[:8]

    audit_id = write_security_event(
        event_type="ACCESS_GRANTED",
        actor_user_id=int(seed["initiator_user_id"]),
        metadata={"note": f"pytest_{suffix}"},
    )
    assert audit_id is not None

    result = list_security_events(
        event_type="ACCESS_GRANTED",
        actor_user_id=int(seed["initiator_user_id"]),
        limit=20,
    )
    assert result["total"] >= 1
    assert any(item["audit_id"] == audit_id for item in result["items"])

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.security_audit_log WHERE audit_id = :id"),
            {"id": audit_id},
        )
