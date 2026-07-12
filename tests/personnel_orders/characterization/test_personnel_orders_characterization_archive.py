# tests/personnel_orders/characterization/test_personnel_orders_characterization_archive.py
"""Characterization: Personnel Orders archive / restore behavior (UDE-007)."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers, create_role, create_user
from tests.personnel_orders.characterization._helpers import (
    archive_payload,
    cleanup_order,
    create_draft_order,
    set_order_status,
    unique_suffix,
)
from tests.test_wp_po_lc_del_005_archive_api import _cleanup_user, _grant_user_permission

pytestmark = pytest.mark.usefixtures("_require_po_characterization_schema")


@pytest.fixture
def archive_user(seed):
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        role_id = create_role(conn, f"pytest_char_archive_{suffix}")
        user_id = create_user(
            conn,
            full_name=f"Char Archive {suffix}",
            role_id=role_id,
            unit_id=int(seed["unit_id"]),
        )
        _grant_user_permission(conn, user_id=user_id, permission_code="PERSONNEL_ORDERS_ARCHIVE")
        _grant_user_permission(conn, user_id=user_id, permission_code="PERSONNEL_ORDERS_RESTORE")
    try:
        yield {"user_id": user_id, "headers": auth_headers(user_id)}
    finally:
        with engine.begin() as conn:
            _cleanup_user(conn, user_id)


def test_personnel_orders_characterization_archive_registered_order(
    client, archive_user, privileged_headers
) -> None:
    order_id = create_draft_order(client, privileged_headers, suffix=unique_suffix())
    try:
        set_order_status(order_id, "REGISTERED")
        archived = client.post(
            f"/directory/personnel-orders/{order_id}/archive",
            json=archive_payload(),
            headers=archive_user["headers"],
        )
        assert archived.status_code == 200, archived.text
        assert archived.json()["order"]["is_archived"] is True
        assert archived.json()["order"]["status"] == "REGISTERED"
    finally:
        cleanup_order(order_id)


def test_personnel_orders_characterization_archived_mutation_returns_order_archived(
    client, archive_user, privileged_headers
) -> None:
    order_id = create_draft_order(client, privileged_headers, suffix=unique_suffix())
    try:
        set_order_status(order_id, "REGISTERED")
        archived = client.post(
            f"/directory/personnel-orders/{order_id}/archive",
            json=archive_payload(),
            headers=archive_user["headers"],
        )
        assert archived.status_code == 200, archived.text

        blocked = client.patch(
            f"/directory/personnel-orders/{order_id}",
            json={"legal_basis_article": "49"},
            headers=privileged_headers,
        )
        assert blocked.status_code == 409, blocked.text
        assert blocked.json()["detail"]["code"] == "ORDER_ARCHIVED"
    finally:
        cleanup_order(order_id)


def test_personnel_orders_characterization_archived_read_and_audit_remain_available(
    client, archive_user, privileged_headers
) -> None:
    order_id = create_draft_order(client, privileged_headers, suffix=unique_suffix())
    try:
        set_order_status(order_id, "REGISTERED")
        archived = client.post(
            f"/directory/personnel-orders/{order_id}/archive",
            json=archive_payload(),
            headers=archive_user["headers"],
        )
        assert archived.status_code == 200, archived.text

        detail = client.get(
            f"/directory/personnel-orders/{order_id}",
            headers=privileged_headers,
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["order"]["is_archived"] is True

        audit = client.get(
            f"/directory/personnel-orders/{order_id}/lifecycle-audit",
            headers=privileged_headers,
        )
        assert audit.status_code == 200, audit.text
        assert any(item["action"] == "ARCHIVE" for item in audit.json()["items"])
    finally:
        cleanup_order(order_id)


def test_personnel_orders_characterization_restore_clears_archive(
    client, archive_user, privileged_headers
) -> None:
    order_id = create_draft_order(client, privileged_headers, suffix=unique_suffix())
    try:
        set_order_status(order_id, "REGISTERED")
        archived = client.post(
            f"/directory/personnel-orders/{order_id}/archive",
            json=archive_payload(),
            headers=archive_user["headers"],
        )
        assert archived.status_code == 200, archived.text

        restored = client.post(
            f"/directory/personnel-orders/{order_id}/restore",
            json={},
            headers=archive_user["headers"],
        )
        assert restored.status_code == 200, restored.text
        assert restored.json()["order"]["is_archived"] is False

        with engine.begin() as conn:
            archived_at = conn.execute(
                text(
                    """
                    SELECT archived_at
                    FROM public.personnel_orders
                    WHERE order_id = :order_id
                    """
                ),
                {"order_id": order_id},
            ).scalar_one()
        assert archived_at is None
    finally:
        cleanup_order(order_id)
