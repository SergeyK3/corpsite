# tests/incoming_information/test_seed_role_isolation.py
"""Regression: seed principals must not inherit reserved privileged role ids."""
from __future__ import annotations

from datetime import date

from tests.incoming_information.conftest import utc_today, ensure_system_admin_role_row

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.security.directory_scope import SYSTEM_ADMIN_ROLE_ID, is_privileged
from tests.conftest import assert_non_privileged_role_id, auth_headers, _RESERVED_PRIVILEGED_ROLE_IDS

pytestmark = pytest.mark.usefixtures("_require_ii_schema_fixture")


def test_seed_roles_are_not_reserved_privileged_ids(seed):
    reserved = _RESERVED_PRIVILEGED_ROLE_IDS
    for key in ("executor_role_id", "initiator_role_id"):
        role_id = int(seed[key])
        assert_non_privileged_role_id(role_id, label=key)
        assert role_id not in reserved


def test_seed_users_are_not_privileged(seed):
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT user_id, role_id
                FROM public.users
                WHERE user_id = ANY(:uids)
                """
            ),
            {"uids": [int(seed["executor_user_id"]), int(seed["initiator_user_id"])]},
        ).mappings().all()
    for row in rows:
        ctx = {"user_id": int(row["user_id"]), "role_id": int(row["role_id"])}
        assert not is_privileged(ctx), ctx


def test_seed_outsider_register_returns_forbidden(client, seed, ii_outsider_headers):
    with engine.connect() as conn:
        doc_type_id = conn.execute(
            text("SELECT document_type_id FROM public.incoming_document_types WHERE code='OTHER' LIMIT 1")
        ).scalar_one()
        channel_id = conn.execute(
            text("SELECT receipt_channel_id FROM public.incoming_receipt_channels WHERE code='OTHER' LIMIT 1")
        ).scalar_one()
    response = client.post(
        "/api/incoming-information/incoming-documents",
        json={
            "received_at": utc_today().isoformat(),
            "document_type_id": int(doc_type_id),
            "receipt_channel_id": int(channel_id),
            "summary": "Isolation regression",
            "sender_kind": "EXTERNAL_TEXT",
            "sender_text": "Author",
            "addressee_kind": "ORG_UNIT",
            "addressee_org_unit_id": int(seed["unit_id"]),
            "registration_org_unit_id": int(seed["unit_id"]),
        },
        headers=ii_outsider_headers,
    )
    assert response.status_code == 403


def test_explicit_system_admin_role_remains_privileged(seed):
    admin_id = int(seed["initiator_user_id"])
    with engine.connect() as conn:
        original_role_id = conn.execute(
            text("SELECT role_id FROM public.users WHERE user_id = :uid"),
            {"uid": admin_id},
        ).scalar_one()
    with engine.begin() as conn:
        ensure_system_admin_role_row(conn)
        conn.execute(
            text("UPDATE public.users SET role_id = :rid WHERE user_id = :uid"),
            {"rid": int(SYSTEM_ADMIN_ROLE_ID), "uid": admin_id},
        )
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT user_id, role_id FROM public.users WHERE user_id = :uid"),
                {"uid": admin_id},
            ).mappings().one()
        assert int(row["role_id"]) == int(SYSTEM_ADMIN_ROLE_ID)
        assert is_privileged(dict(row))
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE public.users SET role_id = :rid WHERE user_id = :uid"),
                {"rid": int(original_role_id), "uid": admin_id},
            )
