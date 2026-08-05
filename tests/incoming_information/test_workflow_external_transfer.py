# tests/incoming_information/test_workflow_external_transfer.py
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.incoming_information.conftest import advance_document_to_status


@pytest.mark.parametrize(
    "source_status",
    ["REGISTERED", "ASSIGNED", "IN_PROGRESS", "WAITING_INFORMATION"],
)
@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_external_transfer_allowed_from_workflow_statuses(client, seed, ii_control_headers, source_status):
    document = advance_document_to_status(client, seed, ii_control_headers, source_status)
    document_id = int(document["incoming_document_id"])

    response = client.post(
        f"/api/incoming-information/incoming-documents/{document_id}/transfer",
        json={
            "expected_version": document["row_version"],
            "transfer_scope": "EXTERNAL",
            "recipient_kind": "TEXT",
            "recipient_text": "External authority",
            "comment": "Transferred outside",
        },
        headers=ii_control_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status_code"] == "TRANSFERRED"
    assert body["external_recipient_kind"] == "TEXT"
    assert body["external_recipient_text"] == "External authority"
    assert body["transferred_at"] is not None

    with engine.connect() as conn:
        active_assignments = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.incoming_document_assignments
                WHERE incoming_document_id = :document_id
                  AND completed_at IS NULL
                  AND cancelled_at IS NULL
                """
            ),
            {"document_id": document_id},
        ).one()
        transfer_rows = conn.execute(
            text(
                """
                SELECT transfer_scope, recipient_kind, recipient_text, new_status_code
                FROM public.incoming_document_transfers
                WHERE incoming_document_id = :document_id
                """
            ),
            {"document_id": document_id},
        ).one()
        audit_rows = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.incoming_document_audit
                WHERE incoming_document_id = :document_id
                  AND action = 'OPERATION_TRANSFER'
                """
            ),
            {"document_id": document_id},
        ).one()

    assert int(active_assignments[0]) == 0
    assert transfer_rows[0] == "EXTERNAL"
    assert transfer_rows[1] == "TEXT"
    assert transfer_rows[2] == "External authority"
    assert transfer_rows[3] == "TRANSFERRED"
    assert int(audit_rows[0]) == 1
