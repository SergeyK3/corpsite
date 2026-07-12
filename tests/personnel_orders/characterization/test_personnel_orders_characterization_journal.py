# tests/personnel_orders/characterization/test_personnel_orders_characterization_journal.py
"""Characterization: Personnel Orders journal filtering behavior (UDE-007)."""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.db.engine import engine
from tests.conftest import auth_headers, create_role, create_user
from tests.personnel_orders.characterization._helpers import (
    cleanup_order,
    create_draft_order,
    set_order_status,
    unique_suffix,
)
from tests.test_wp_po_lc_del_005_archive_api import _archive_payload, _cleanup_user, _grant_user_permission

pytestmark = pytest.mark.usefixtures("_require_po_characterization_schema")


@pytest.fixture
def archive_user(seed):
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        role_id = create_role(conn, f"pytest_char_journal_{suffix}")
        user_id = create_user(
            conn,
            full_name=f"Char Journal {suffix}",
            role_id=role_id,
            unit_id=int(seed["unit_id"]),
        )
        _grant_user_permission(conn, user_id=user_id, permission_code="PERSONNEL_ORDERS_ARCHIVE")
    try:
        yield {"user_id": user_id, "headers": auth_headers(user_id)}
    finally:
        with engine.begin() as conn:
            _cleanup_user(conn, user_id)


def _list_ids(client, headers, query: str = "") -> set[int]:
    path = "/directory/personnel-orders"
    if query:
        path = f"{path}?{query}"
    resp = client.get(path, headers=headers)
    assert resp.status_code == 200, resp.text
    return {int(item["order_id"]) for item in resp.json()["items"]}


def test_personnel_orders_characterization_journal_hides_voided_by_default(
    client, privileged_headers
) -> None:
    order_id = create_draft_order(client, privileged_headers, suffix=unique_suffix())
    try:
        set_order_status(order_id, "VOIDED")
        assert order_id not in _list_ids(client, privileged_headers)
        assert order_id in _list_ids(client, privileged_headers, "include_closed=true")
    finally:
        cleanup_order(order_id)


def test_personnel_orders_characterization_journal_hides_archived_by_default(
    client, archive_user, privileged_headers
) -> None:
    order_id = create_draft_order(client, privileged_headers, suffix=unique_suffix())
    try:
        set_order_status(order_id, "REGISTERED")
        archived = client.post(
            f"/directory/personnel-orders/{order_id}/archive",
            json=_archive_payload(),
            headers=archive_user["headers"],
        )
        assert archived.status_code == 200, archived.text
        assert order_id not in _list_ids(client, privileged_headers)
        assert order_id in _list_ids(client, privileged_headers, "include_closed=true")
    finally:
        cleanup_order(order_id)


def test_personnel_orders_characterization_journal_include_archived_alias(
    client, archive_user, privileged_headers
) -> None:
    order_id = create_draft_order(client, privileged_headers, suffix=unique_suffix())
    try:
        set_order_status(order_id, "REGISTERED")
        archived = client.post(
            f"/directory/personnel-orders/{order_id}/archive",
            json=_archive_payload(),
            headers=archive_user["headers"],
        )
        assert archived.status_code == 200, archived.text
        assert order_id in _list_ids(client, privileged_headers, "include_archived=true")
    finally:
        cleanup_order(order_id)


def test_personnel_orders_characterization_journal_active_orders_remain_visible(
    client, privileged_headers
) -> None:
    order_id = create_draft_order(client, privileged_headers, suffix=unique_suffix())
    try:
        assert order_id in _list_ids(client, privileged_headers)
        assert order_id in _list_ids(client, privileged_headers, "include_closed=false")
    finally:
        cleanup_order(order_id)
