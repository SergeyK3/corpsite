# tests/incoming_information/test_workflow_fsm.py
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers, create_unit
from tests.incoming_information.conftest import (
    utc_today,
    cleanup_incoming_documents,
    grant_user_permission,
    register_test_document,
    revoke_user_access_grants,
)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_same_registration_and_responsible_org_unit_allowed(client, seed, ii_register_headers):
    body = register_test_document(client, seed, ii_register_headers)
    assert body["registration_org_unit_id"] == body["responsible_org_unit_id"]
    with engine.begin() as conn:
        cleanup_incoming_documents(conn, [int(body["incoming_document_id"])])


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_registration_org_unit_is_immutable(client, seed, ii_control_headers):
    body = register_test_document(client, seed, ii_control_headers)
    document_id = int(body["incoming_document_id"])
    original_registration_org_unit_id = int(body["registration_org_unit_id"])

    with engine.begin() as conn:
        other_unit_id = create_unit(conn, "pytest_other_unit")

    transfer = client.post(
        f"/api/incoming-information/incoming-documents/{document_id}/transfer",
        json={
            "expected_version": body["row_version"],
            "transfer_scope": "INTERNAL",
            "target_org_unit_id": other_unit_id,
            "comment": "Internal transfer",
        },
        headers=ii_control_headers,
    )
    assert transfer.status_code == 200, transfer.text
    assert transfer.json()["registration_org_unit_id"] == original_registration_org_unit_id
    assert transfer.json()["responsible_org_unit_id"] == other_unit_id

    with engine.begin() as conn:
        cleanup_incoming_documents(conn, [document_id])


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_assign_creates_single_active_primary(client, seed, ii_control_headers):
    body = register_test_document(client, seed, ii_control_headers)
    document_id = int(body["incoming_document_id"])
    primary_user_id = int(seed["executor_user_id"])

    assigned = client.post(
        f"/api/incoming-information/incoming-documents/{document_id}/assign",
        json={
            "expected_version": body["row_version"],
            "primary_user_id": primary_user_id,
        },
        headers=ii_control_headers,
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["status_code"] == "ASSIGNED"

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT COUNT(*) AS cnt
                FROM public.incoming_document_assignments
                WHERE incoming_document_id = :document_id
                  AND role = 'PRIMARY'
                  AND completed_at IS NULL
                  AND cancelled_at IS NULL
                """
            ),
            {"document_id": document_id},
        ).one()
        assert int(rows[0]) == 1

    duplicate = client.post(
        f"/api/incoming-information/incoming-documents/{document_id}/assign",
        json={
            "expected_version": assigned.json()["row_version"],
            "primary_user_id": int(seed["initiator_user_id"]),
        },
        headers=ii_control_headers,
    )
    assert duplicate.status_code == 422
    assert duplicate.json()["detail"]["code"] == "INVALID_STATUS_TRANSITION"

    with engine.begin() as conn:
        cleanup_incoming_documents(conn, [document_id])


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_reassign_preserves_assignment_history(client, seed, ii_control_headers):
    body = register_test_document(client, seed, ii_control_headers)
    document_id = int(body["incoming_document_id"])
    assigned = client.post(
        f"/api/incoming-information/incoming-documents/{document_id}/assign",
        json={
            "expected_version": body["row_version"],
            "primary_user_id": int(seed["executor_user_id"]),
        },
        headers=ii_control_headers,
    ).json()
    reassign = client.post(
        f"/api/incoming-information/incoming-documents/{document_id}/reassign",
        json={
            "expected_version": assigned["row_version"],
            "primary_user_id": int(seed["initiator_user_id"]),
            "reason": "Replacement",
        },
        headers=ii_control_headers,
    )
    assert reassign.status_code == 200, reassign.text

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT role, cancelled_at IS NOT NULL AS cancelled
                FROM public.incoming_document_assignments
                WHERE incoming_document_id = :document_id
                ORDER BY assignment_id ASC
                """
            ),
            {"document_id": document_id},
        ).all()
        assert len(rows) == 2
        assert rows[0][0] == "PRIMARY" and rows[0][1] is True
        assert rows[1][0] == "PRIMARY" and rows[1][1] is False

    with engine.begin() as conn:
        cleanup_incoming_documents(conn, [document_id])


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_internal_transfer_resets_to_registered_and_clears_assignments(client, seed, ii_control_headers):
    body = register_test_document(client, seed, ii_control_headers)
    document_id = int(body["incoming_document_id"])
    assigned = client.post(
        f"/api/incoming-information/incoming-documents/{document_id}/assign",
        json={
            "expected_version": body["row_version"],
            "primary_user_id": int(seed["executor_user_id"]),
        },
        headers=ii_control_headers,
    ).json()
    started = client.post(
        f"/api/incoming-information/incoming-documents/{document_id}/start",
        json={"expected_version": assigned["row_version"]},
        headers=ii_control_headers,
    )
    assert started.status_code == 200

    with engine.begin() as conn:
        target_unit_id = create_unit(conn, "pytest_transfer_target")

    transferred = client.post(
        f"/api/incoming-information/incoming-documents/{document_id}/transfer",
        json={
            "expected_version": started.json()["row_version"],
            "transfer_scope": "INTERNAL",
            "target_org_unit_id": target_unit_id,
            "comment": "Transfer to another unit",
        },
        headers=ii_control_headers,
    )
    assert transferred.status_code == 200, transferred.text
    assert transferred.json()["status_code"] == "REGISTERED"

    with engine.connect() as conn:
        active = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.incoming_document_assignments
                WHERE incoming_document_id = :document_id
                  AND completed_at IS NULL
                  AND cancelled_at IS NULL
                """
            ),
            {"document_id": document_id},
        ).one()
        assert int(active[0]) == 0

    with engine.begin() as conn:
        cleanup_incoming_documents(conn, [document_id])


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_reopen_without_primary_goes_to_registered(client, seed, ii_control_headers):
    document = _resolve_and_close(client, seed, ii_control_headers)
    document_id = int(document["incoming_document_id"])

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE public.incoming_document_assignments
                SET cancelled_at = now(), cancel_reason = 'TEST'
                WHERE incoming_document_id = :document_id
                  AND cancelled_at IS NULL
                """
            ),
            {"document_id": document_id},
        )

    reopened = client.post(
        f"/api/incoming-information/incoming-documents/{document_id}/reopen",
        json={"expected_version": document["row_version"], "reason": "Need rework"},
        headers=ii_control_headers,
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["status_code"] == "REGISTERED"

    with engine.begin() as conn:
        cleanup_incoming_documents(conn, [document_id])


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_reopen_with_primary_goes_to_in_progress(client, seed, ii_control_headers):
    document = _resolve_and_close(client, seed, ii_control_headers)
    document_id = int(document["incoming_document_id"])
    reopened = client.post(
        f"/api/incoming-information/incoming-documents/{document_id}/reopen",
        json={"expected_version": document["row_version"], "reason": "Need rework"},
        headers=ii_control_headers,
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["status_code"] == "IN_PROGRESS"

    with engine.begin() as conn:
        cleanup_incoming_documents(conn, [document_id])


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_coexecutor_cannot_resolve(client, seed, ii_control_headers):
    body = register_test_document(client, seed, ii_control_headers)
    document_id = int(body["incoming_document_id"])
    executor_id = int(seed["executor_user_id"])
    coexecutor_id = int(seed["initiator_user_id"])

    assigned = client.post(
        f"/api/incoming-information/incoming-documents/{document_id}/assign",
        json={
            "expected_version": body["row_version"],
            "primary_user_id": executor_id,
            "coexecutor_user_ids": [coexecutor_id],
        },
        headers=ii_control_headers,
    ).json()
    started = client.post(
        f"/api/incoming-information/incoming-documents/{document_id}/start",
        json={"expected_version": assigned["row_version"]},
        headers=ii_control_headers,
    ).json()

    with engine.begin() as conn:
        grant_user_permission(conn, coexecutor_id, "INCOMING_INFO_EXECUTE")
        grant_user_permission(conn, coexecutor_id, "INCOMING_INFO_READ")

    co_headers = auth_headers(coexecutor_id)
    resolve = client.post(
        f"/api/incoming-information/incoming-documents/{document_id}/resolve",
        json={
            "expected_version": started["row_version"],
            "execution_result": "Done by coexecutor",
        },
        headers=co_headers,
    )
    assert resolve.status_code == 403

    with engine.begin() as conn:
        cleanup_incoming_documents(conn, [document_id])
        revoke_user_access_grants(conn, coexecutor_id)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_resolved_requires_result_and_executed_at(client, seed, ii_control_headers):
    body = register_test_document(client, seed, ii_control_headers)
    document_id = int(body["incoming_document_id"])
    in_progress = _assign_and_start(client, seed, ii_control_headers, body)

    bad = client.post(
        f"/api/incoming-information/incoming-documents/{document_id}/resolve",
        json={"expected_version": in_progress["row_version"], "execution_result": "   "},
        headers=ii_control_headers,
    )
    assert bad.status_code == 422

    with engine.begin() as conn:
        cleanup_incoming_documents(conn, [document_id])


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_close_requires_resolved_status(client, seed, ii_control_headers):
    body = register_test_document(client, seed, ii_control_headers)
    document_id = int(body["incoming_document_id"])
    in_progress = _assign_and_start(client, seed, ii_control_headers, body)

    close = client.post(
        f"/api/incoming-information/incoming-documents/{document_id}/close",
        json={
            "expected_version": in_progress["row_version"],
            "control_decision": "Accepted",
        },
        headers=ii_control_headers,
    )
    assert close.status_code == 422

    with engine.begin() as conn:
        cleanup_incoming_documents(conn, [document_id])


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_external_text_recipient_does_not_require_target_org_unit(client, seed, ii_control_headers):
    body = register_test_document(client, seed, ii_control_headers)
    document_id = int(body["incoming_document_id"])
    transferred = client.post(
        f"/api/incoming-information/incoming-documents/{document_id}/transfer",
        json={
            "expected_version": body["row_version"],
            "transfer_scope": "EXTERNAL",
            "recipient_kind": "TEXT",
            "recipient_text": "External authority",
            "comment": "Sent outside",
        },
        headers=ii_control_headers,
    )
    assert transferred.status_code == 200, transferred.text
    assert transferred.json()["status_code"] == "TRANSFERRED"

    with engine.begin() as conn:
        cleanup_incoming_documents(conn, [document_id])


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_cancel_requires_reason(client, seed, ii_register_headers):
    body = register_test_document(client, seed, ii_register_headers)
    document_id = int(body["incoming_document_id"])
    cancel = client.post(
        f"/api/incoming-information/incoming-documents/{document_id}/cancel",
        json={"expected_version": body["row_version"], "reason": "   "},
        headers=ii_register_headers,
    )
    assert cancel.status_code == 422

    with engine.begin() as conn:
        cleanup_incoming_documents(conn, [document_id])


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_concurrent_operations_with_same_expected_version(client, seed, ii_control_headers):
    body = register_test_document(client, seed, ii_control_headers)
    document_id = int(body["incoming_document_id"])
    version = int(body["row_version"])

    def _assign(user_id: int):
        return client.post(
            f"/api/incoming-information/incoming-documents/{document_id}/assign",
            json={"expected_version": version, "primary_user_id": user_id},
            headers=ii_control_headers,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(_assign, int(seed["executor_user_id"]))
        second = pool.submit(_assign, int(seed["initiator_user_id"]))
        statuses = sorted([first.result().status_code, second.result().status_code])

    assert statuses == [200, 409]

    with engine.begin() as conn:
        cleanup_incoming_documents(conn, [document_id])


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_restricted_workflow_endpoint_requires_participation(client, seed, ii_control_headers, ii_outsider_headers):
    body = register_test_document(
        client,
        seed,
        ii_control_headers,
        access_level="RESTRICTED",
    )
    document_id = int(body["incoming_document_id"])
    denied = client.post(
        f"/api/incoming-information/incoming-documents/{document_id}/assign",
        json={
            "expected_version": body["row_version"],
            "primary_user_id": int(seed["executor_user_id"]),
        },
        headers=ii_outsider_headers,
    )
    assert denied.status_code == 403

    with engine.begin() as conn:
        cleanup_incoming_documents(conn, [document_id])


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_rejected_operation_leaves_no_partial_audit(client, seed, ii_control_headers):
    body = register_test_document(client, seed, ii_control_headers)
    document_id = int(body["incoming_document_id"])
    assigned = client.post(
        f"/api/incoming-information/incoming-documents/{document_id}/assign",
        json={
            "expected_version": body["row_version"],
            "primary_user_id": int(seed["executor_user_id"]),
        },
        headers=ii_control_headers,
    ).json()

    rejected = client.post(
        f"/api/incoming-information/incoming-documents/{document_id}/start",
        json={"expected_version": body["row_version"]},
        headers=ii_control_headers,
    )
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["code"] == "VERSION_CONFLICT"

    with engine.connect() as conn:
        audit_count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.incoming_document_audit
                WHERE incoming_document_id = :document_id
                  AND action = 'OPERATION_ASSIGN'
                """
            ),
            {"document_id": document_id},
        ).one()
        assert int(audit_count[0]) == 1

    with engine.begin() as conn:
        cleanup_incoming_documents(conn, [document_id])


def _assign_and_start(client, seed, headers, body):
    assigned = client.post(
        f"/api/incoming-information/incoming-documents/{body['incoming_document_id']}/assign",
        json={
            "expected_version": body["row_version"],
            "primary_user_id": int(seed["executor_user_id"]),
            "controller_user_id": int(seed["executor_user_id"]),
        },
        headers=headers,
    ).json()
    started = client.post(
        f"/api/incoming-information/incoming-documents/{body['incoming_document_id']}/start",
        json={"expected_version": assigned["row_version"]},
        headers=headers,
    )
    assert started.status_code == 200, started.text
    return started.json()


def _resolve_and_close(client, seed, headers):
    body = register_test_document(client, seed, headers)
    in_progress = _assign_and_start(client, seed, headers, body)
    document_id = int(body["incoming_document_id"])
    resolved = client.post(
        f"/api/incoming-information/incoming-documents/{document_id}/resolve",
        json={
            "expected_version": in_progress["row_version"],
            "execution_result": "Completed",
            "executed_at": utc_today().isoformat(),
        },
        headers=headers,
    )
    assert resolved.status_code == 200, resolved.text
    closed = client.post(
        f"/api/incoming-information/incoming-documents/{document_id}/close",
        json={
            "expected_version": resolved.json()["row_version"],
            "control_decision": "Accepted",
        },
        headers=headers,
    )
    assert closed.status_code == 200, closed.text
    return closed.json()
