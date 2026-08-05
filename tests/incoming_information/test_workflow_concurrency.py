# tests/incoming_information/test_workflow_concurrency.py
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.incoming_information.conftest import register_test_document


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_concurrent_assign_with_same_expected_version_is_atomic(client, seed, ii_control_headers):
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
        responses = sorted([first.result(), second.result()], key=lambda item: item.status_code)

    assert responses[0].status_code == 200
    assert responses[1].status_code == 409
    assert responses[1].json()["detail"]["code"] == "VERSION_CONFLICT"

    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT row_version, status_id
                FROM public.incoming_documents
                WHERE incoming_document_id = :document_id
                """
            ),
            {"document_id": document_id},
        ).one()
        status_code = conn.execute(
            text(
                """
                SELECT code
                FROM public.incoming_document_statuses
                WHERE status_id = :status_id
                """
            ),
            {"status_id": int(row[1])},
        ).one()[0]
        primary_count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.incoming_document_assignments
                WHERE incoming_document_id = :document_id
                  AND role = 'PRIMARY'
                  AND completed_at IS NULL
                  AND cancelled_at IS NULL
                """
            ),
            {"document_id": document_id},
        ).one()[0]
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
        ).one()[0]

    assert int(row[0]) == version + 1
    assert status_code == "ASSIGNED"
    assert int(primary_count) == 1
    assert int(audit_count) == 1
