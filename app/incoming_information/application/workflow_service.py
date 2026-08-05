"""Workflow service for Incoming Information FSM operations."""
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.incoming_information.application.access_service import (
    assert_can_assign_document,
    assert_can_control_document,
    assert_can_execute_document,
    assert_can_mutate_document,
    assert_can_resolve_document,
)
from app.incoming_information.domain import fsm
from app.incoming_information.domain.errors import (
    IncomingDocumentConflictError,
    IncomingDocumentForbiddenError,
    IncomingDocumentInvalidTransitionError,
    IncomingDocumentValidationError,
)
from app.incoming_information.domain.party_validation import validate_external_transfer_recipient_exclusive
from app.incoming_information.domain.models import IncomingDocumentSnapshot
from app.incoming_information.domain.status import (
    ASSIGNMENT_CANCEL_REASON_REASSIGN,
    ASSIGNMENT_CANCEL_REASON_TRANSFER,
    ASSIGNMENT_ROLE_COEXECUTOR,
    ASSIGNMENT_ROLE_PRIMARY,
    AUDIT_ACTION_OPERATION_ASSIGN,
    AUDIT_ACTION_OPERATION_CANCEL,
    AUDIT_ACTION_OPERATION_CHANGE_DEADLINE,
    AUDIT_ACTION_OPERATION_CLOSE,
    AUDIT_ACTION_OPERATION_REASSIGN,
    AUDIT_ACTION_OPERATION_REOPEN,
    AUDIT_ACTION_OPERATION_RESOLVE,
    AUDIT_ACTION_OPERATION_RESUME,
    AUDIT_ACTION_OPERATION_START,
    AUDIT_ACTION_OPERATION_TRANSFER,
    AUDIT_ACTION_OPERATION_WAIT,
    RECIPIENT_KIND_ORG_UNIT,
    RECIPIENT_KIND_TEXT,
    RECIPIENT_KIND_USER,
    STATUS_ASSIGNED,
    STATUS_CANCELLED,
    STATUS_CLOSED,
    STATUS_IN_PROGRESS,
    STATUS_REGISTERED,
    STATUS_RESOLVED,
    STATUS_TRANSFERRED,
    STATUS_WAITING_INFORMATION,
    TRANSFER_SCOPE_EXTERNAL,
    TRANSFER_SCOPE_INTERNAL,
)
from app.incoming_information.infrastructure.audit_repository import SqlAlchemyIncomingDocumentAuditRepository
from app.incoming_information.infrastructure.repository import SqlAlchemyIncomingDocumentRepository
from app.incoming_information.infrastructure.workflow_repository import SqlAlchemyIncomingWorkflowRepository
from app.incoming_information.permissions import can_control, can_register
from sqlalchemy.engine import Connection


def _invalid_transition(source: str, operation: str) -> IncomingDocumentInvalidTransitionError:
    return IncomingDocumentInvalidTransitionError(
        f"Operation {operation} is not allowed from status {source}."
    )


def _require_non_empty(value: str | None, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise IncomingDocumentValidationError(f"{field} is required.")
    return text


def _raise_on_primary_integrity_error(exc: IntegrityError) -> None:
    message = str(getattr(exc, "orig", exc))
    if "uq_incoming_document_assignments_one_primary" in message:
        raise IncomingDocumentConflictError("Document already has an active PRIMARY assignment.") from exc
    raise exc


def _load_locked(
    conn: Connection,
    *,
    incoming_document_id: int,
    expected_version: int,
) -> tuple[IncomingDocumentSnapshot, SqlAlchemyIncomingDocumentRepository, SqlAlchemyIncomingWorkflowRepository, SqlAlchemyIncomingDocumentAuditRepository]:
    wf_repo = SqlAlchemyIncomingWorkflowRepository(conn)
    wf_repo.lock_document(incoming_document_id)
    wf_repo.assert_expected_version(incoming_document_id, expected_version)
    doc_repo = SqlAlchemyIncomingDocumentRepository(conn)
    document = doc_repo.require_by_id(incoming_document_id)
    audit_repo = SqlAlchemyIncomingDocumentAuditRepository(conn)
    return document, doc_repo, wf_repo, audit_repo


def _status_id(doc_repo: SqlAlchemyIncomingDocumentRepository, code: str) -> int:
    status_id = doc_repo.get_status_id_by_code(code)
    if status_id is None:
        raise RuntimeError(f"Missing incoming status seed: {code}")
    return status_id


def _apply_transition(
    *,
    wf_repo: SqlAlchemyIncomingWorkflowRepository,
    audit_repo: SqlAlchemyIncomingDocumentAuditRepository,
    document: IncomingDocumentSnapshot,
    expected_version: int,
    actor_user_id: int,
    new_status_code: str,
    new_status_id: int,
    audit_action: str,
    fields: dict[str, Any] | None = None,
    comment: str | None = None,
    field_changes: dict[str, Any] | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> IncomingDocumentSnapshot:
    update_fields = dict(fields or {})
    update_fields["status_id"] = new_status_id
    version_after = wf_repo.update_document_fields(
        incoming_document_id=document.incoming_document_id,
        expected_version=expected_version,
        updated_by_user_id=actor_user_id,
        fields=update_fields,
    )
    audit_repo.append_operation(
        incoming_document_id=document.incoming_document_id,
        action=audit_action,
        actor_user_id=actor_user_id,
        old_status_code=document.status_code,
        new_status_code=new_status_code,
        version_before=expected_version,
        version_after=version_after,
        comment=comment,
        field_changes=field_changes,
        extra_metadata=extra_metadata,
    )
    doc_repo = SqlAlchemyIncomingDocumentRepository(wf_repo._conn)
    return doc_repo.require_by_id(document.incoming_document_id)


def _ensure_no_active_primary(wf_repo: SqlAlchemyIncomingWorkflowRepository, document_id: int) -> None:
    if wf_repo.get_active_primary(document_id) is not None:
        raise IncomingDocumentConflictError("Document already has an active PRIMARY assignment.")


def _ensure_active_primary(wf_repo: SqlAlchemyIncomingWorkflowRepository, document_id: int) -> dict[str, Any]:
    primary = wf_repo.get_active_primary(document_id)
    if primary is None:
        raise IncomingDocumentValidationError("Active PRIMARY assignment is required.")
    return primary


def assign_incoming_document(
    conn: Connection,
    *,
    user: dict[str, Any],
    incoming_document_id: int,
    expected_version: int,
    primary_user_id: int,
    coexecutor_user_ids: list[int] | None = None,
    org_unit_id: int | None = None,
    due_date: date | None = None,
    controller_user_id: int | None = None,
) -> IncomingDocumentSnapshot:
    document, doc_repo, wf_repo, audit_repo = _load_locked(
        conn, incoming_document_id=incoming_document_id, expected_version=expected_version
    )
    assert_can_assign_document(conn, user=user, document=document)
    if document.status_code not in fsm.ASSIGN_SOURCE_STATUSES:
        raise _invalid_transition(document.status_code, "assign")
    _ensure_no_active_primary(wf_repo, document.incoming_document_id)

    target_org_unit_id = int(org_unit_id or document.responsible_org_unit_id)
    if not wf_repo.org_unit_exists(target_org_unit_id):
        raise IncomingDocumentValidationError("org_unit_id is invalid.")
    if not wf_repo.user_exists(primary_user_id):
        raise IncomingDocumentValidationError("primary_user_id is invalid.")
    if controller_user_id is not None and not wf_repo.user_exists(controller_user_id):
        raise IncomingDocumentValidationError("controller_user_id is invalid.")

    actor_user_id = int(user["user_id"])
    primary_employee_id = wf_repo.resolve_employee_id_for_user(primary_user_id)
    try:
        wf_repo.create_assignment(
            incoming_document_id=document.incoming_document_id,
            assignee_user_id=primary_user_id,
            assignee_employee_id=primary_employee_id,
            org_unit_id=target_org_unit_id,
            role=ASSIGNMENT_ROLE_PRIMARY,
            assigned_by_user_id=actor_user_id,
            due_date=due_date,
        )
    except IntegrityError as exc:
        _raise_on_primary_integrity_error(exc)

    coexecutor_ids = list(dict.fromkeys(coexecutor_user_ids or []))
    for co_user_id in coexecutor_ids:
        if co_user_id == primary_user_id:
            continue
        if not wf_repo.user_exists(co_user_id):
            raise IncomingDocumentValidationError(f"Invalid coexecutor user_id: {co_user_id}")
        wf_repo.create_assignment(
            incoming_document_id=document.incoming_document_id,
            assignee_user_id=co_user_id,
            assignee_employee_id=wf_repo.resolve_employee_id_for_user(co_user_id),
            org_unit_id=target_org_unit_id,
            role=ASSIGNMENT_ROLE_COEXECUTOR,
            assigned_by_user_id=actor_user_id,
            due_date=due_date,
        )

    fields: dict[str, Any] = {}
    if due_date is not None:
        fields["due_date"] = due_date
    if controller_user_id is not None:
        fields["controller_user_id"] = controller_user_id

    return _apply_transition(
        wf_repo=wf_repo,
        audit_repo=audit_repo,
        document=document,
        expected_version=expected_version,
        actor_user_id=actor_user_id,
        new_status_code=STATUS_ASSIGNED,
        new_status_id=_status_id(doc_repo, STATUS_ASSIGNED),
        audit_action=AUDIT_ACTION_OPERATION_ASSIGN,
        fields=fields,
        extra_metadata={
            "primary_user_id": primary_user_id,
            "coexecutor_user_ids": coexecutor_ids,
            "org_unit_id": target_org_unit_id,
        },
    )


def reassign_incoming_document(
    conn: Connection,
    *,
    user: dict[str, Any],
    incoming_document_id: int,
    expected_version: int,
    primary_user_id: int,
    reason: str | None = None,
    org_unit_id: int | None = None,
) -> IncomingDocumentSnapshot:
    document, doc_repo, wf_repo, audit_repo = _load_locked(
        conn, incoming_document_id=incoming_document_id, expected_version=expected_version
    )
    assert_can_assign_document(conn, user=user, document=document)
    if document.status_code not in fsm.REASSIGN_SOURCE_STATUSES:
        raise _invalid_transition(document.status_code, "reassign")
    old_primary = _ensure_active_primary(wf_repo, document.incoming_document_id)
    if not wf_repo.user_exists(primary_user_id):
        raise IncomingDocumentValidationError("primary_user_id is invalid.")

    actor_user_id = int(user["user_id"])
    target_org_unit_id = int(org_unit_id or document.responsible_org_unit_id)
    if not wf_repo.org_unit_exists(target_org_unit_id):
        raise IncomingDocumentValidationError("org_unit_id is invalid.")
    wf_repo.cancel_active_primary(
        incoming_document_id=document.incoming_document_id,
        cancel_reason=ASSIGNMENT_CANCEL_REASON_REASSIGN,
    )
    try:
        wf_repo.create_assignment(
            incoming_document_id=document.incoming_document_id,
            assignee_user_id=primary_user_id,
            assignee_employee_id=wf_repo.resolve_employee_id_for_user(primary_user_id),
            org_unit_id=target_org_unit_id,
            role=ASSIGNMENT_ROLE_PRIMARY,
            assigned_by_user_id=actor_user_id,
        )
    except IntegrityError as exc:
        _raise_on_primary_integrity_error(exc)

    version_after = wf_repo.bump_version(
        incoming_document_id=document.incoming_document_id,
        expected_version=expected_version,
        updated_by_user_id=actor_user_id,
    )
    audit_repo.append_operation(
        incoming_document_id=document.incoming_document_id,
        action=AUDIT_ACTION_OPERATION_REASSIGN,
        actor_user_id=actor_user_id,
        old_status_code=document.status_code,
        new_status_code=document.status_code,
        version_before=expected_version,
        version_after=version_after,
        comment=reason,
        extra_metadata={
            "old_primary_user_id": old_primary["assignee_user_id"],
            "new_primary_user_id": primary_user_id,
        },
    )
    return doc_repo.require_by_id(document.incoming_document_id)


def transfer_incoming_document(
    conn: Connection,
    *,
    user: dict[str, Any],
    incoming_document_id: int,
    expected_version: int,
    transfer_scope: str,
    comment: str,
    target_org_unit_id: int | None = None,
    recipient_kind: str | None = None,
    recipient_user_id: int | None = None,
    recipient_org_unit_id: int | None = None,
    recipient_text: str | None = None,
) -> IncomingDocumentSnapshot:
    document, doc_repo, wf_repo, audit_repo = _load_locked(
        conn, incoming_document_id=incoming_document_id, expected_version=expected_version
    )
    assert_can_assign_document(conn, user=user, document=document)
    actor_user_id = int(user["user_id"])
    transfer_comment = _require_non_empty(comment, "comment")

    if transfer_scope == TRANSFER_SCOPE_INTERNAL:
        if document.status_code not in fsm.INTERNAL_TRANSFER_SOURCE_STATUSES:
            raise _invalid_transition(document.status_code, "transfer")
        if target_org_unit_id is None:
            raise IncomingDocumentValidationError("target_org_unit_id is required for internal transfer.")
        if not wf_repo.org_unit_exists(target_org_unit_id):
            raise IncomingDocumentValidationError("target_org_unit_id is invalid.")
        cancelled = wf_repo.cancel_active_assignments(
            incoming_document_id=document.incoming_document_id,
            cancel_reason=ASSIGNMENT_CANCEL_REASON_TRANSFER,
        )
        wf_repo.insert_transfer(
            incoming_document_id=document.incoming_document_id,
            transfer_scope=TRANSFER_SCOPE_INTERNAL,
            from_responsible_org_unit_id=document.responsible_org_unit_id,
            to_responsible_org_unit_id=int(target_org_unit_id),
            recipient_kind=None,
            recipient_user_id=None,
            recipient_org_unit_id=None,
            recipient_text=None,
            comment=transfer_comment,
            previous_status_code=document.status_code,
            new_status_code=STATUS_REGISTERED,
            actor_user_id=actor_user_id,
        )
        return _apply_transition(
            wf_repo=wf_repo,
            audit_repo=audit_repo,
            document=document,
            expected_version=expected_version,
            actor_user_id=actor_user_id,
            new_status_code=STATUS_REGISTERED,
            new_status_id=_status_id(doc_repo, STATUS_REGISTERED),
            audit_action=AUDIT_ACTION_OPERATION_TRANSFER,
            fields={"responsible_org_unit_id": int(target_org_unit_id)},
            comment=transfer_comment,
            field_changes={
                "responsible_org_unit_id": {
                    "old": document.responsible_org_unit_id,
                    "new": int(target_org_unit_id),
                }
            },
            extra_metadata={
                "transfer_scope": TRANSFER_SCOPE_INTERNAL,
                "cancelled_assignments": cancelled,
            },
        )

    if transfer_scope == TRANSFER_SCOPE_EXTERNAL:
        if document.status_code not in fsm.EXTERNAL_TRANSFER_SOURCE_STATUSES:
            raise _invalid_transition(document.status_code, "transfer")
        if recipient_kind not in {RECIPIENT_KIND_USER, RECIPIENT_KIND_ORG_UNIT, RECIPIENT_KIND_TEXT}:
            raise IncomingDocumentValidationError("recipient_kind is required for external transfer.")
        validate_external_transfer_recipient_exclusive(
            recipient_kind,
            recipient_user_id=recipient_user_id,
            recipient_org_unit_id=recipient_org_unit_id,
            recipient_text=recipient_text,
        )
        if recipient_kind == RECIPIENT_KIND_USER:
            if recipient_user_id is None:
                raise IncomingDocumentValidationError("recipient_user_id is required.")
            if not wf_repo.user_exists(recipient_user_id):
                raise IncomingDocumentValidationError("recipient_user_id is invalid.")
        elif recipient_kind == RECIPIENT_KIND_ORG_UNIT:
            if recipient_org_unit_id is None:
                raise IncomingDocumentValidationError("recipient_org_unit_id is required.")
            if not wf_repo.org_unit_exists(recipient_org_unit_id):
                raise IncomingDocumentValidationError("recipient_org_unit_id is invalid.")
        else:
            recipient_text = _require_non_empty(recipient_text, "recipient_text")

        cancelled = wf_repo.cancel_active_assignments(
            incoming_document_id=document.incoming_document_id,
            cancel_reason=ASSIGNMENT_CANCEL_REASON_TRANSFER,
        )
        now = datetime.now(UTC)
        wf_repo.insert_transfer(
            incoming_document_id=document.incoming_document_id,
            transfer_scope=TRANSFER_SCOPE_EXTERNAL,
            from_responsible_org_unit_id=document.responsible_org_unit_id,
            to_responsible_org_unit_id=None,
            recipient_kind=recipient_kind,
            recipient_user_id=recipient_user_id,
            recipient_org_unit_id=recipient_org_unit_id,
            recipient_text=recipient_text.strip() if recipient_text else None,
            comment=transfer_comment,
            previous_status_code=document.status_code,
            new_status_code=STATUS_TRANSFERRED,
            actor_user_id=actor_user_id,
        )
        return _apply_transition(
            wf_repo=wf_repo,
            audit_repo=audit_repo,
            document=document,
            expected_version=expected_version,
            actor_user_id=actor_user_id,
            new_status_code=STATUS_TRANSFERRED,
            new_status_id=_status_id(doc_repo, STATUS_TRANSFERRED),
            audit_action=AUDIT_ACTION_OPERATION_TRANSFER,
            fields={
                "transfer_comment": transfer_comment,
                "transferred_at": now,
                "transferred_by_user_id": actor_user_id,
                "external_recipient_kind": recipient_kind,
                "external_recipient_user_id": recipient_user_id,
                "external_recipient_org_unit_id": recipient_org_unit_id,
                "external_recipient_text": recipient_text.strip() if recipient_text else None,
            },
            comment=transfer_comment,
            extra_metadata={
                "transfer_scope": TRANSFER_SCOPE_EXTERNAL,
                "recipient_kind": recipient_kind,
                "cancelled_assignments": cancelled,
            },
        )

    raise IncomingDocumentValidationError(f"Invalid transfer_scope: {transfer_scope}")


def start_incoming_document(
    conn: Connection,
    *,
    user: dict[str, Any],
    incoming_document_id: int,
    expected_version: int,
) -> IncomingDocumentSnapshot:
    document, doc_repo, wf_repo, audit_repo = _load_locked(
        conn, incoming_document_id=incoming_document_id, expected_version=expected_version
    )
    assert_can_execute_document(conn, user=user, document=document, require_primary=True)
    if document.status_code not in fsm.START_SOURCE_STATUSES:
        raise _invalid_transition(document.status_code, "start")
    _ensure_active_primary(wf_repo, document.incoming_document_id)
    return _apply_transition(
        wf_repo=wf_repo,
        audit_repo=audit_repo,
        document=document,
        expected_version=expected_version,
        actor_user_id=int(user["user_id"]),
        new_status_code=STATUS_IN_PROGRESS,
        new_status_id=_status_id(doc_repo, STATUS_IN_PROGRESS),
        audit_action=AUDIT_ACTION_OPERATION_START,
    )


def request_information_incoming_document(
    conn: Connection,
    *,
    user: dict[str, Any],
    incoming_document_id: int,
    expected_version: int,
    reason: str | None = None,
) -> IncomingDocumentSnapshot:
    document, doc_repo, wf_repo, audit_repo = _load_locked(
        conn, incoming_document_id=incoming_document_id, expected_version=expected_version
    )
    assert_can_execute_document(conn, user=user, document=document)
    if document.status_code not in fsm.WAIT_SOURCE_STATUSES:
        raise _invalid_transition(document.status_code, "request-information")
    _ensure_active_primary(wf_repo, document.incoming_document_id)
    return _apply_transition(
        wf_repo=wf_repo,
        audit_repo=audit_repo,
        document=document,
        expected_version=expected_version,
        actor_user_id=int(user["user_id"]),
        new_status_code=STATUS_WAITING_INFORMATION,
        new_status_id=_status_id(doc_repo, STATUS_WAITING_INFORMATION),
        audit_action=AUDIT_ACTION_OPERATION_WAIT,
        comment=reason,
    )


def resume_incoming_document(
    conn: Connection,
    *,
    user: dict[str, Any],
    incoming_document_id: int,
    expected_version: int,
    comment: str | None = None,
) -> IncomingDocumentSnapshot:
    document, doc_repo, wf_repo, audit_repo = _load_locked(
        conn, incoming_document_id=incoming_document_id, expected_version=expected_version
    )
    assert_can_execute_document(conn, user=user, document=document)
    if document.status_code not in fsm.RESUME_SOURCE_STATUSES:
        raise _invalid_transition(document.status_code, "resume")
    _ensure_active_primary(wf_repo, document.incoming_document_id)
    return _apply_transition(
        wf_repo=wf_repo,
        audit_repo=audit_repo,
        document=document,
        expected_version=expected_version,
        actor_user_id=int(user["user_id"]),
        new_status_code=STATUS_IN_PROGRESS,
        new_status_id=_status_id(doc_repo, STATUS_IN_PROGRESS),
        audit_action=AUDIT_ACTION_OPERATION_RESUME,
        comment=comment,
    )


def change_deadline_incoming_document(
    conn: Connection,
    *,
    user: dict[str, Any],
    incoming_document_id: int,
    expected_version: int,
    new_due_date: date,
    reason: str,
) -> IncomingDocumentSnapshot:
    document, doc_repo, wf_repo, audit_repo = _load_locked(
        conn, incoming_document_id=incoming_document_id, expected_version=expected_version
    )
    assert_can_assign_document(conn, user=user, document=document)
    if document.status_code not in fsm.CHANGE_DEADLINE_SOURCE_STATUSES:
        raise _invalid_transition(document.status_code, "change-deadline")
    reason_text = _require_non_empty(reason, "reason")
    actor_user_id = int(user["user_id"])
    wf_repo.insert_deadline_change(
        incoming_document_id=document.incoming_document_id,
        previous_due_date=document.due_date,
        new_due_date=new_due_date,
        reason=reason_text,
        changed_by_user_id=actor_user_id,
    )
    version_after = wf_repo.update_document_fields(
        incoming_document_id=document.incoming_document_id,
        expected_version=expected_version,
        updated_by_user_id=actor_user_id,
        fields={"due_date": new_due_date},
    )
    audit_repo.append_operation(
        incoming_document_id=document.incoming_document_id,
        action=AUDIT_ACTION_OPERATION_CHANGE_DEADLINE,
        actor_user_id=actor_user_id,
        old_status_code=document.status_code,
        new_status_code=document.status_code,
        version_before=expected_version,
        version_after=version_after,
        comment=reason_text,
        field_changes={
            "due_date": {
                "old": document.due_date.isoformat() if document.due_date else None,
                "new": new_due_date.isoformat(),
            }
        },
    )
    return doc_repo.require_by_id(document.incoming_document_id)


def resolve_incoming_document(
    conn: Connection,
    *,
    user: dict[str, Any],
    incoming_document_id: int,
    expected_version: int,
    execution_result: str,
    executed_at: date | None = None,
) -> IncomingDocumentSnapshot:
    document, doc_repo, wf_repo, audit_repo = _load_locked(
        conn, incoming_document_id=incoming_document_id, expected_version=expected_version
    )
    assert_can_resolve_document(conn, user=user, document=document)
    if document.status_code not in fsm.RESOLVE_SOURCE_STATUSES:
        raise _invalid_transition(document.status_code, "resolve")
    _ensure_active_primary(wf_repo, document.incoming_document_id)
    result_text = _require_non_empty(execution_result, "execution_result")
    actual_executed_at = executed_at or date.today()
    if actual_executed_at > date.today():
        raise IncomingDocumentValidationError("executed_at cannot be in the future.")
    recorded_at = datetime.now(UTC)
    return _apply_transition(
        wf_repo=wf_repo,
        audit_repo=audit_repo,
        document=document,
        expected_version=expected_version,
        actor_user_id=int(user["user_id"]),
        new_status_code=STATUS_RESOLVED,
        new_status_id=_status_id(doc_repo, STATUS_RESOLVED),
        audit_action=AUDIT_ACTION_OPERATION_RESOLVE,
        fields={
            "execution_result": result_text,
            "executed_at": actual_executed_at,
            "resolve_recorded_at": recorded_at,
        },
        field_changes={
            "execution_result": {"old": document.execution_result, "new": result_text},
            "executed_at": {
                "old": document.executed_at.isoformat() if document.executed_at else None,
                "new": actual_executed_at.isoformat(),
            },
        },
        extra_metadata={"resolve_recorded_at": recorded_at.isoformat()},
    )


def close_incoming_document(
    conn: Connection,
    *,
    user: dict[str, Any],
    incoming_document_id: int,
    expected_version: int,
    control_decision: str,
    comment: str | None = None,
) -> IncomingDocumentSnapshot:
    document, doc_repo, wf_repo, audit_repo = _load_locked(
        conn, incoming_document_id=incoming_document_id, expected_version=expected_version
    )
    assert_can_control_document(conn, user=user, document=document)
    if document.status_code not in fsm.CLOSE_SOURCE_STATUSES:
        raise _invalid_transition(document.status_code, "close")
    if not document.execution_result or document.executed_at is None:
        raise IncomingDocumentValidationError("Document must be resolved before close.")
    decision = _require_non_empty(control_decision, "control_decision")
    actor_user_id = int(user["user_id"])
    now = datetime.now(UTC)
    return _apply_transition(
        wf_repo=wf_repo,
        audit_repo=audit_repo,
        document=document,
        expected_version=expected_version,
        actor_user_id=actor_user_id,
        new_status_code=STATUS_CLOSED,
        new_status_id=_status_id(doc_repo, STATUS_CLOSED),
        audit_action=AUDIT_ACTION_OPERATION_CLOSE,
        fields={
            "closed_at": now,
            "closed_by_user_id": actor_user_id,
            "control_decision": decision,
            "control_comment": comment.strip() if comment else None,
        },
        comment=comment,
        field_changes={
            "control_decision": {"old": document.control_decision, "new": decision},
            "control_comment": {"old": document.control_comment, "new": comment},
        },
        extra_metadata={"control_decision": decision},
    )


def reopen_incoming_document(
    conn: Connection,
    *,
    user: dict[str, Any],
    incoming_document_id: int,
    expected_version: int,
    reason: str,
) -> IncomingDocumentSnapshot:
    document, doc_repo, wf_repo, audit_repo = _load_locked(
        conn, incoming_document_id=incoming_document_id, expected_version=expected_version
    )
    assert_can_control_document(conn, user=user, document=document)
    if document.status_code not in fsm.REOPEN_SOURCE_STATUSES:
        raise _invalid_transition(document.status_code, "reopen")
    reason_text = _require_non_empty(reason, "reason")
    actor_user_id = int(user["user_id"])
    primary = wf_repo.get_active_primary(document.incoming_document_id)
    new_status = STATUS_IN_PROGRESS if primary else STATUS_REGISTERED
    now = datetime.now(UTC)
    return _apply_transition(
        wf_repo=wf_repo,
        audit_repo=audit_repo,
        document=document,
        expected_version=expected_version,
        actor_user_id=actor_user_id,
        new_status_code=new_status,
        new_status_id=_status_id(doc_repo, new_status),
        audit_action=AUDIT_ACTION_OPERATION_REOPEN,
        fields={
            "closed_at": None,
            "closed_by_user_id": None,
            "control_decision": None,
            "control_comment": None,
            "execution_result": None,
            "executed_at": None,
            "resolve_recorded_at": None,
            "reopen_count": document.reopen_count + 1,
            "reopened_at": now,
            "reopen_reason": reason_text,
        },
        comment=reason_text,
        field_changes={
            "execution_result": {"old": document.execution_result, "new": None},
            "executed_at": {
                "old": document.executed_at.isoformat() if document.executed_at else None,
                "new": None,
            },
            "closed_at": {
                "old": document.closed_at.isoformat() if document.closed_at else None,
                "new": None,
            },
        },
    )


def cancel_incoming_document(
    conn: Connection,
    *,
    user: dict[str, Any],
    incoming_document_id: int,
    expected_version: int,
    reason: str,
) -> IncomingDocumentSnapshot:
    document, doc_repo, wf_repo, audit_repo = _load_locked(
        conn, incoming_document_id=incoming_document_id, expected_version=expected_version
    )
    reason_text = _require_non_empty(reason, "reason")
    actor_user_id = int(user["user_id"])

    if document.status_code in fsm.CANCEL_REGISTER_STATUSES:
        if not can_register(user) and not can_control(user):
            raise IncomingDocumentForbiddenError(
                "INCOMING_INFO_REGISTER permission required for cancel in this status."
            )
    elif document.status_code in fsm.CANCEL_CONTROL_STATUSES:
        if not can_control(user):
            raise IncomingDocumentForbiddenError(
                "INCOMING_INFO_CONTROL permission required for cancel in this status."
            )
    else:
        raise _invalid_transition(document.status_code, "cancel")

    assert_can_mutate_document(conn, user=user, document=document)

    now = datetime.now(UTC)
    wf_repo.cancel_active_assignments(
        incoming_document_id=document.incoming_document_id,
        cancel_reason="CANCEL",
    )
    return _apply_transition(
        wf_repo=wf_repo,
        audit_repo=audit_repo,
        document=document,
        expected_version=expected_version,
        actor_user_id=actor_user_id,
        new_status_code=STATUS_CANCELLED,
        new_status_id=_status_id(doc_repo, STATUS_CANCELLED),
        audit_action=AUDIT_ACTION_OPERATION_CANCEL,
        fields={
            "cancellation_reason": reason_text,
            "cancelled_at": now,
            "cancelled_by_user_id": actor_user_id,
        },
        comment=reason_text,
    )
