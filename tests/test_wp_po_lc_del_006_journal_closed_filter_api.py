# tests/test_wp_po_lc_del_006_journal_closed_filter_api.py
"""API tests for WP-PO-LC-006 personnel orders journal closed-document filtering."""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.db.engine import engine
from tests.conftest import auth_headers, create_role, create_user
from tests.test_wp_po_003_personnel_orders_schema import _require_lc_del_003_schema
from tests.test_wp_po_lc_del_005_archive_api import (
    _archive_payload,
    _cleanup_order,
    _cleanup_user,
    _create_draft_order,
    _grant_user_permission,
    _set_order_status,
)

pytestmark = pytest.mark.usefixtures("_require_lc_del_006_schema_fixture")


@pytest.fixture(scope="module", autouse=True)
def _require_lc_del_006_schema_fixture():
    _require_lc_del_003_schema()


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def archive_user(seed):
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        role_id = create_role(conn, f"pytest_del006_archive_{suffix}")
        user_id = create_user(
            conn,
            full_name=f"DEL006 Archive {suffix}",
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


def _archive_order(client, archive_headers, privileged_headers, order_id: int) -> None:
    _set_order_status(order_id, "REGISTERED")
    archived = client.post(
        f"/directory/personnel-orders/{order_id}/archive",
        json=_archive_payload(),
        headers=archive_headers,
    )
    assert archived.status_code == 200, archived.text


def test_list_excludes_voided_by_default(client, privileged_headers) -> None:
    order_id = _create_draft_order(client, privileged_headers)
    try:
        _set_order_status(order_id, "VOIDED")
        default_ids = _list_ids(client, privileged_headers)
        assert order_id not in default_ids
    finally:
        _cleanup_order(order_id)


def test_list_excludes_archived_and_voided_by_default(
    client,
    archive_user,
    privileged_headers,
) -> None:
    voided_id = _create_draft_order(client, privileged_headers, suffix="voided")
    archived_id = _create_draft_order(client, privileged_headers, suffix="archived")
    try:
        _set_order_status(voided_id, "VOIDED")
        _archive_order(client, archive_user["headers"], privileged_headers, archived_id)

        default_ids = _list_ids(client, privileged_headers)
        assert voided_id not in default_ids
        assert archived_id not in default_ids
    finally:
        _cleanup_order(voided_id)
        _cleanup_order(archived_id)


def test_include_closed_shows_voided_and_archived(
    client,
    archive_user,
    privileged_headers,
) -> None:
    voided_id = _create_draft_order(client, privileged_headers, suffix="closed-voided")
    archived_id = _create_draft_order(client, privileged_headers, suffix="closed-archived")
    try:
        _set_order_status(voided_id, "VOIDED")
        _archive_order(client, archive_user["headers"], privileged_headers, archived_id)

        closed_ids = _list_ids(client, privileged_headers, "include_closed=true")
        assert voided_id in closed_ids
        assert archived_id in closed_ids
    finally:
        _cleanup_order(voided_id)
        _cleanup_order(archived_id)


def test_include_archived_alias_matches_include_closed(
    client,
    archive_user,
    privileged_headers,
) -> None:
    archived_id = _create_draft_order(client, privileged_headers, suffix="alias-archived")
    try:
        _archive_order(client, archive_user["headers"], privileged_headers, archived_id)

        alias_ids = _list_ids(client, privileged_headers, "include_archived=true")
        canonical_ids = _list_ids(client, privileged_headers, "include_closed=true")
        assert archived_id in alias_ids
        assert alias_ids == canonical_ids
    finally:
        _cleanup_order(archived_id)


def test_status_voided_returns_non_archived_voided_when_closed_false(
    client,
    privileged_headers,
) -> None:
    order_id = _create_draft_order(client, privileged_headers, suffix="voided-filter")
    try:
        _set_order_status(order_id, "VOIDED")
        default_ids = _list_ids(client, privileged_headers)
        filtered_ids = _list_ids(client, privileged_headers, "status=VOIDED")
        assert order_id not in default_ids
        assert order_id in filtered_ids
    finally:
        _cleanup_order(order_id)


def test_status_voided_excludes_archived_voided_when_closed_false(
    client,
    archive_user,
    privileged_headers,
) -> None:
    order_id = _create_draft_order(client, privileged_headers, suffix="archived-voided")
    try:
        _set_order_status(order_id, "VOIDED")
        archived = client.post(
            f"/directory/personnel-orders/{order_id}/archive",
            json=_archive_payload(),
            headers=archive_user["headers"],
        )
        assert archived.status_code == 200, archived.text

        filtered_ids = _list_ids(client, privileged_headers, "status=VOIDED")
        assert order_id not in filtered_ids
    finally:
        _cleanup_order(order_id)


def test_include_closed_status_voided_includes_archived_voided(
    client,
    archive_user,
    privileged_headers,
) -> None:
    order_id = _create_draft_order(client, privileged_headers, suffix="closed-archived-voided")
    try:
        _set_order_status(order_id, "VOIDED")
        archived = client.post(
            f"/directory/personnel-orders/{order_id}/archive",
            json=_archive_payload(),
            headers=archive_user["headers"],
        )
        assert archived.status_code == 200, archived.text

        filtered_ids = _list_ids(
            client,
            privileged_headers,
            "status=VOIDED&include_closed=true",
        )
        assert order_id in filtered_ids
    finally:
        _cleanup_order(order_id)


def test_status_registered_excludes_archived_when_closed_false(
    client,
    archive_user,
    privileged_headers,
) -> None:
    order_id = _create_draft_order(client, privileged_headers, suffix="archived-registered")
    try:
        _archive_order(client, archive_user["headers"], privileged_headers, order_id)

        filtered_ids = _list_ids(client, privileged_headers, "status=REGISTERED")
        assert order_id not in filtered_ids
    finally:
        _cleanup_order(order_id)


@pytest.mark.parametrize(
    "target_status",
    ["DRAFT", "READY_FOR_SIGNATURE", "SIGNED", "REGISTERED"],
)
def test_active_pipeline_statuses_visible_by_default(
    client,
    privileged_headers,
    target_status: str,
) -> None:
    order_id = _create_draft_order(client, privileged_headers, suffix=target_status.lower())
    try:
        if target_status != "DRAFT":
            _set_order_status(order_id, target_status)
        default_ids = _list_ids(client, privileged_headers)
        assert order_id in default_ids
    finally:
        _cleanup_order(order_id)
