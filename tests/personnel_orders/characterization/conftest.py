"""Pytest fixtures for Personnel Orders characterization tests (UDE-007)."""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.db.engine import engine
from tests.conftest import auth_headers, create_role, create_user
from tests.test_wp_po_003_personnel_orders_schema import (
    _require_lc_del_003_schema,
    _require_schema,
)
from tests.test_wp_po_lc_del_004_cancel_api import _cleanup_user, _grant_user_permission


@pytest.fixture(scope="module", autouse=True)
def _require_po_characterization_schema() -> None:
    _require_schema()
    _require_lc_del_003_schema()


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def cancel_own_user(seed):
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        role_id = create_role(conn, f"pytest_char_cancel_own_{suffix}")
        user_id = create_user(
            conn,
            full_name=f"Char Cancel Own {suffix}",
            role_id=role_id,
            unit_id=int(seed["unit_id"]),
        )
        _grant_user_permission(conn, user_id=user_id, permission_code="PERSONNEL_ORDERS_CANCEL_OWN")
    try:
        yield {"user_id": user_id, "headers": auth_headers(user_id)}
    finally:
        with engine.begin() as conn:
            _cleanup_user(conn, user_id)
