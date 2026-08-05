# tests/incoming_information/test_list_pagination.py
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers
from tests.incoming_information.conftest import (
    grant_permissions,
    grant_user_permission,
    lookup_dictionary_id,
    register_restricted_document,
    register_test_document,
    revoke_user_access_grants,
)


def _register_normal(client, seed, headers) -> dict:
    return register_test_document(client, seed, headers, access_level="NORMAL")


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_list_pagination_excludes_inaccessible_restricted_and_keeps_total(
    client, seed, ii_register_headers, ii_control_headers
):
    participant_id = int(seed["executor_user_id"])
    outsider_id = int(seed["initiator_user_id"])

    docs = []
    for idx in range(3):
        docs.append(_register_normal(client, seed, ii_register_headers))
    for idx in range(3):
        docs.append(
            register_restricted_document(
                client,
                seed,
                ii_control_headers,
                addressee_user_id=participant_id,
            )
        )
    for idx in range(2):
        with engine.begin() as conn:
            grant_permissions(conn, outsider_id, "INCOMING_INFO_REGISTER", "INCOMING_INFO_READ")
        try:
            docs.append(
                register_restricted_document(
                    client,
                    seed,
                    auth_headers(outsider_id),
                    addressee_user_id=outsider_id,
                )
            )
        finally:
            with engine.begin() as conn:
                revoke_user_access_grants(conn, outsider_id)

    with engine.begin() as conn:
        grant_user_permission(conn, participant_id, "INCOMING_INFO_READ")

    try:
        page1 = client.get(
            "/api/incoming-information/incoming-documents",
            params={"limit": 4, "offset": 0, "sort": "registered_at"},
            headers=auth_headers(participant_id),
        )
        page2 = client.get(
            "/api/incoming-information/incoming-documents",
            params={"limit": 4, "offset": 4, "sort": "registered_at"},
            headers=auth_headers(participant_id),
        )
        assert page1.status_code == 200, page1.text
        assert page2.status_code == 200, page2.text
        body1 = page1.json()
        body2 = page2.json()
        assert body1["total"] == 6
        assert body2["total"] == 6
        ids1 = [int(item["incoming_document_id"]) for item in body1["items"]]
        ids2 = [int(item["incoming_document_id"]) for item in body2["items"]]
        assert len(ids1) == 4
        assert len(ids2) == 2
        assert not set(ids1) & set(ids2)
        hidden_restricted = {int(d["incoming_document_id"]) for d in docs[6:]}
        assert hidden_restricted.isdisjoint(set(ids1) | set(ids2))
    finally:
        with engine.begin() as conn:
            revoke_user_access_grants(conn, participant_id)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_list_bypass_user_sees_all_restricted_in_scope(client, seed, ii_control_headers):
    bypass_id = int(seed["initiator_user_id"])
    participant_id = int(seed["executor_user_id"])
    with engine.begin() as conn:
        grant_user_permission(conn, bypass_id, "INCOMING_INFO_RESTRICTED_BYPASS")
        grant_user_permission(conn, bypass_id, "INCOMING_INFO_READ")

    restricted_a = register_restricted_document(
        client, seed, ii_control_headers, addressee_user_id=participant_id
    )
    restricted_b = register_restricted_document(
        client, seed, ii_control_headers, addressee_user_id=participant_id
    )
    try:
        listing = client.get(
            "/api/incoming-information/incoming-documents",
            params={"limit": 50, "offset": 0},
            headers=auth_headers(bypass_id),
        )
        assert listing.status_code == 200, listing.text
        visible = {int(item["incoming_document_id"]) for item in listing.json()["items"]}
        assert int(restricted_a["incoming_document_id"]) in visible
        assert int(restricted_b["incoming_document_id"]) in visible
    finally:
        with engine.begin() as conn:
            revoke_user_access_grants(conn, bypass_id)
