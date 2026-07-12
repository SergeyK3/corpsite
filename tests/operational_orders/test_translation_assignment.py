# tests/operational_orders/test_translation_assignment.py
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.operational_orders.conftest import cleanup_workspace
from tests.operational_orders.test_helpers import BASE, create_ready_workspace, workspace_payload

pytestmark = pytest.mark.usefixtures("_require_oo_schema_fixture")


def test_ru_only_creates_kk_translation_need(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, _ = create_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref, locales=("ru",)
    )
    try:
        resp = client.post(
            f"{BASE}/{workspace_id}/translation-assignments",
            json={
                "target_locale": "kk",
                "assigned_to": {"reference_type": "PERSON", "reference": author_ref, "display_name": "Translator"},
            },
            headers=oo_editorial_headers,
        )
        assert resp.status_code == 200, resp.text
        assignments = resp.json()["translation_assignments"]
        assert len(assignments) == 1
        assert assignments[0]["target_locale"] == "kk"
        assert assignments[0]["status"] == "REQUESTED"
        assert resp.json()["workspace"]["stage"] == "TRANSLATION_REQUIRED"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_kk_only_creates_ru_translation_need(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, _ = create_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref, locales=("kk",)
    )
    try:
        resp = client.post(
            f"{BASE}/{workspace_id}/translation-assignments",
            json={
                "target_locale": "ru",
                "assigned_to": {"reference_type": "PERSON", "reference": author_ref, "display_name": "Translator"},
            },
            headers=oo_editorial_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["translation_assignments"][0]["target_locale"] == "ru"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_ru_kk_does_not_require_assignment(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, _ = create_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref, locales=("ru", "kk")
    )
    try:
        resp = client.post(
            f"{BASE}/{workspace_id}/translation-assignments",
            json={
                "target_locale": "kk",
                "assigned_to": {"reference_type": "PERSON", "reference": author_ref, "display_name": "Translator"},
            },
            headers=oo_editorial_headers,
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "OO_TRANSLATION_ASSIGNMENT_CONFLICT"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_assignment_lifecycle(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, _ = create_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref, locales=("ru",)
    )
    try:
        create_resp = client.post(
            f"{BASE}/{workspace_id}/translation-assignments",
            json={
                "target_locale": "kk",
                "assigned_to": {"reference_type": "PERSON", "reference": author_ref, "display_name": "Translator"},
            },
            headers=oo_editorial_headers,
        )
        assignment_id = create_resp.json()["translation_assignments"][0]["id"]
        version = create_resp.json()["workspace"]["version"]

        accept_resp = client.post(
            f"{BASE}/{workspace_id}/translation-assignments/{assignment_id}/accept",
            json={"expected_version": version},
            headers=oo_editorial_headers,
        )
        assert accept_resp.status_code == 200
        assert accept_resp.json()["translation_assignments"][0]["status"] == "ACCEPTED"

        add_resp = client.post(
            f"{BASE}/{workspace_id}/blocks",
            json={
                "locale": "kk",
                "block_type": "TITLE",
                "submitted_text": "KK translated title",
                "source_type": "IMPORTED",
                "sequence": 1,
            },
            headers=oo_editorial_headers,
        )
        assert add_resp.status_code == 200
        kk_block = next(b for b in add_resp.json()["blocks"] if b["locale"] == "kk")

        start_resp = client.post(
            f"{BASE}/{workspace_id}/translation-assignments/{assignment_id}/start",
            json={},
            headers=oo_editorial_headers,
        )
        assert start_resp.status_code == 200

        complete_resp = client.post(
            f"{BASE}/{workspace_id}/translation-assignments/{assignment_id}/complete",
            json={"target_block_id": kk_block["block_id"], "block_expected_version": kk_block["version"]},
            headers=oo_editorial_headers,
        )
        assert complete_resp.status_code == 200
        assert complete_resp.json()["translation_assignments"][0]["status"] == "COMPLETED"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_cannot_complete_without_target_text(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, _ = create_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref, locales=("ru",)
    )
    try:
        create_resp = client.post(
            f"{BASE}/{workspace_id}/translation-assignments",
            json={
                "target_locale": "kk",
                "assigned_to": {"reference_type": "PERSON", "reference": author_ref, "display_name": "Translator"},
            },
            headers=oo_editorial_headers,
        )
        assignment_id = create_resp.json()["translation_assignments"][0]["id"]
        client.post(
            f"{BASE}/{workspace_id}/translation-assignments/{assignment_id}/accept",
            json={},
            headers=oo_editorial_headers,
        )
        client.post(
            f"{BASE}/{workspace_id}/translation-assignments/{assignment_id}/start",
            json={},
            headers=oo_editorial_headers,
        )
        complete_resp = client.post(
            f"{BASE}/{workspace_id}/translation-assignments/{assignment_id}/complete",
            json={"target_block_id": 999999},
            headers=oo_editorial_headers,
        )
        assert complete_resp.status_code in {409, 422}
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_duplicate_active_assignment_prevention(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, _ = create_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref, locales=("ru",)
    )
    try:
        payload = {
            "target_locale": "kk",
            "assigned_to": {"reference_type": "PERSON", "reference": author_ref, "display_name": "Translator"},
        }
        assert client.post(
            f"{BASE}/{workspace_id}/translation-assignments", json=payload, headers=oo_editorial_headers
        ).status_code == 200
        dup_resp = client.post(
            f"{BASE}/{workspace_id}/translation-assignments", json=payload, headers=oo_editorial_headers
        )
        assert dup_resp.status_code == 409
        assert dup_resp.json()["detail"]["code"] == "OO_TRANSLATION_ASSIGNMENT_CONFLICT"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_cancel_assignment(client, oo_editorial_headers, seed):
    author_ref = str(seed["executor_user_id"])
    workspace_id, _ = create_ready_workspace(
        client, oo_editorial_headers, seed, author_ref=author_ref, locales=("ru",)
    )
    try:
        create_resp = client.post(
            f"{BASE}/{workspace_id}/translation-assignments",
            json={
                "target_locale": "kk",
                "assigned_to": {"reference_type": "PERSON", "reference": author_ref, "display_name": "Translator"},
            },
            headers=oo_editorial_headers,
        )
        assignment_id = create_resp.json()["translation_assignments"][0]["id"]
        cancel_resp = client.post(
            f"{BASE}/{workspace_id}/translation-assignments/{assignment_id}/cancel",
            json={},
            headers=oo_editorial_headers,
        )
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["translation_assignments"][0]["status"] == "CANCELLED"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)
