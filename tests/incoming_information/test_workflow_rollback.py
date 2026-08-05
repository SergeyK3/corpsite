# tests/incoming_information/test_workflow_rollback.py
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.incoming_information.application.workflow_service import (
    change_deadline_incoming_document,
    reassign_incoming_document,
    transfer_incoming_document,
)
from app.incoming_information.infrastructure.audit_repository import SqlAlchemyIncomingDocumentAuditRepository
from tests.incoming_information.conftest import (
    assign_primary,
    build_user_dict,
    register_test_document,
    utc_today,
)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_reassign_rolls_back_when_audit_write_fails(client, seed, ii_control_headers):
    document = register_test_document(client, seed, ii_control_headers)
    assigned = assign_primary(
        client,
        document,
        ii_control_headers,
        primary_user_id=int(seed["executor_user_id"]),
    )
    document_id = int(assigned["incoming_document_id"])
    user = build_user_dict(int(seed["executor_user_id"]))

    with patch.object(
        SqlAlchemyIncomingDocumentAuditRepository,
        "append_operation",
        side_effect=RuntimeError("audit failed"),
    ):
        with pytest.raises(RuntimeError, match="audit failed"):
            with engine.begin() as conn:
                reassign_incoming_document(
                    conn,
                    user=user,
                    incoming_document_id=document_id,
                    expected_version=int(assigned["row_version"]),
                    primary_user_id=int(seed["initiator_user_id"]),
                    reason="Replacement",
                )

    with engine.connect() as conn:
        active_primary = conn.execute(
            text(
                """
                SELECT assignee_user_id
                FROM public.incoming_document_assignments
                WHERE incoming_document_id = :document_id
                  AND role = 'PRIMARY'
                  AND completed_at IS NULL
                  AND cancelled_at IS NULL
                """
            ),
            {"document_id": document_id},
        ).one()
        audit_count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.incoming_document_audit
                WHERE incoming_document_id = :document_id
                  AND action = 'OPERATION_REASSIGN'
                """
            ),
            {"document_id": document_id},
        ).one()[0]

    assert int(active_primary[0]) == int(seed["executor_user_id"])
    assert int(audit_count) == 0


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_external_transfer_rolls_back_when_audit_write_fails(client, seed, ii_control_headers):
    document = register_test_document(client, seed, ii_control_headers)
    assigned = assign_primary(
        client,
        document,
        ii_control_headers,
        primary_user_id=int(seed["executor_user_id"]),
    )
    document_id = int(assigned["incoming_document_id"])
    user = build_user_dict(int(seed["executor_user_id"]))

    with patch.object(
        SqlAlchemyIncomingDocumentAuditRepository,
        "append_operation",
        side_effect=RuntimeError("audit failed"),
    ):
        with pytest.raises(RuntimeError, match="audit failed"):
            with engine.begin() as conn:
                transfer_incoming_document(
                    conn,
                    user=user,
                    incoming_document_id=document_id,
                    expected_version=int(assigned["row_version"]),
                    transfer_scope="EXTERNAL",
                    comment="Outside",
                    recipient_kind="TEXT",
                    recipient_text="External authority",
                )

    with engine.connect() as conn:
        status_code = conn.execute(
            text(
                """
                SELECT st.code
                FROM public.incoming_documents d
                JOIN public.incoming_document_statuses st ON st.status_id = d.status_id
                WHERE d.incoming_document_id = :document_id
                """
            ),
            {"document_id": document_id},
        ).one()[0]
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
        ).one()[0]
        transfer_count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.incoming_document_transfers
                WHERE incoming_document_id = :document_id
                """
            ),
            {"document_id": document_id},
        ).one()[0]

    assert status_code == "ASSIGNED"
    assert int(active_assignments) == 1
    assert int(transfer_count) == 0


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_change_deadline_rolls_back_when_audit_write_fails(client, seed, ii_control_headers):
    document = register_test_document(client, seed, ii_control_headers)
    document_id = int(document["incoming_document_id"])
    user = build_user_dict(int(seed["executor_user_id"]))
    new_due_date = utc_today() + timedelta(days=7)
    with engine.begin() as conn:
        from tests.incoming_information.conftest import grant_permissions

        grant_permissions(
            conn,
            int(seed["executor_user_id"]),
            "INCOMING_INFO_CONTROL",
            "INCOMING_INFO_READ",
            "INCOMING_INFO_REGISTER",
        )

    with patch.object(
        SqlAlchemyIncomingDocumentAuditRepository,
        "append_operation",
        side_effect=RuntimeError("audit failed"),
    ):
        with pytest.raises(RuntimeError, match="audit failed"):
            with engine.begin() as conn:
                change_deadline_incoming_document(
                    conn,
                    user=user,
                    incoming_document_id=document_id,
                    expected_version=int(document["row_version"]),
                    new_due_date=new_due_date,
                    reason="Extend",
                )

    with engine.connect() as conn:
        due_date = conn.execute(
            text(
                """
                SELECT due_date
                FROM public.incoming_documents
                WHERE incoming_document_id = :document_id
                """
            ),
            {"document_id": document_id},
        ).one()[0]
        deadline_changes = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.incoming_document_deadline_changes
                WHERE incoming_document_id = :document_id
                """
            ),
            {"document_id": document_id},
        ).one()[0]

    assert due_date is None
    assert int(deadline_changes) == 0
