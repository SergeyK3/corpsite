"""Incoming Information access control."""
from __future__ import annotations

from typing import Any

from app.incoming_information.domain.errors import IncomingDocumentForbiddenError
from app.incoming_information.domain.models import IncomingDocumentSnapshot
from app.incoming_information.domain.status import ACCESS_LEVEL_RESTRICTED
from app.incoming_information.infrastructure.repository import SqlAlchemyIncomingDocumentRepository
from app.incoming_information.infrastructure.workflow_repository import SqlAlchemyIncomingWorkflowRepository
from app.incoming_information.permissions import (
    can_control,
    can_execute,
    can_read,
    can_register,
    can_resolve,
    can_restricted_bypass,
    has_base_read_permission,
)
from app.incoming_information.scope import document_in_user_scope, resolve_user_scope_unit_ids
from sqlalchemy import text
from sqlalchemy.engine import Connection


def employee_id_for_user(conn: Connection, user_id: int) -> int | None:
    row = conn.execute(
        text(
            """
            SELECT employee_id
            FROM public.users
            WHERE user_id = :user_id
            LIMIT 1
            """
        ),
        {"user_id": int(user_id)},
    ).first()
    if not row or row[0] is None:
        return None
    return int(row[0])


def user_is_restricted_participant(
    conn: Connection,
    *,
    user: dict[str, Any],
    document: IncomingDocumentSnapshot,
) -> bool:
    user_id = int(user["user_id"])
    if document.created_by_user_id == user_id:
        return True
    if document.controller_user_id == user_id:
        return True
    if document.addressee_user_id == user_id:
        return True
    employee_id = user.get("employee_id")
    if employee_id is None:
        employee_id = employee_id_for_user(conn, user_id)
    if employee_id is not None and document.addressee_employee_id == int(employee_id):
        return True
    repo = SqlAlchemyIncomingDocumentRepository(conn)
    return repo.user_is_active_assignee(document.incoming_document_id, user_id)


def assert_can_read_document(
    conn: Connection,
    *,
    user: dict[str, Any],
    document: IncomingDocumentSnapshot,
) -> None:
    if not has_base_read_permission(user):
        raise IncomingDocumentForbiddenError("Incoming document read access denied.")

    if document.access_level == ACCESS_LEVEL_RESTRICTED:
        if user_is_restricted_participant(conn, user=user, document=document):
            return
        if can_restricted_bypass(user):
            return
        raise IncomingDocumentForbiddenError("Restricted document access denied.")

    if not document_in_user_scope(user, document):
        raise IncomingDocumentForbiddenError("Document is outside permitted org scope.")


def assert_can_register_in_org(user: dict[str, Any], registration_org_unit_id: int) -> None:
    scope = resolve_user_scope_unit_ids(user)
    if scope is None:
        return
    if int(registration_org_unit_id) not in scope:
        raise IncomingDocumentForbiddenError("Registration org unit is outside permitted scope.")


def assert_can_mutate_document(
    conn: Connection,
    *,
    user: dict[str, Any],
    document: IncomingDocumentSnapshot,
) -> None:
    assert_can_read_document(conn, user=user, document=document)


def assert_can_control_document(
    conn: Connection,
    *,
    user: dict[str, Any],
    document: IncomingDocumentSnapshot,
) -> None:
    assert_can_mutate_document(conn, user=user, document=document)
    user_id = int(user["user_id"])
    if document.access_level == ACCESS_LEVEL_RESTRICTED:
        if document.controller_user_id == user_id:
            return
        if can_restricted_bypass(user):
            return
        raise IncomingDocumentForbiddenError(
            "Restricted document control requires assigned controller or restricted bypass."
        )
    if can_control(user):
        return
    if document.controller_user_id == user_id:
        return
    raise IncomingDocumentForbiddenError("Incoming document control permission required.")


def assert_can_assign_document(
    conn: Connection,
    *,
    user: dict[str, Any],
    document: IncomingDocumentSnapshot,
) -> None:
    assert_can_mutate_document(conn, user=user, document=document)
    if can_control(user):
        return
    raise IncomingDocumentForbiddenError("Incoming document assignment permission required.")


def assert_can_execute_document(
    conn: Connection,
    *,
    user: dict[str, Any],
    document: IncomingDocumentSnapshot,
    require_primary: bool = False,
) -> None:
    assert_can_mutate_document(conn, user=user, document=document)
    user_id = int(user["user_id"])
    wf_repo = SqlAlchemyIncomingWorkflowRepository(conn)
    if require_primary and not wf_repo.user_is_active_primary(document.incoming_document_id, user_id):
        raise IncomingDocumentForbiddenError("Active PRIMARY assignment required.")
    is_active_assignee = wf_repo.user_is_active_assignee(document.incoming_document_id, user_id)
    if not is_active_assignee:
        raise IncomingDocumentForbiddenError(
            "Active assignment and INCOMING_INFO_EXECUTE permission required."
        )
    if not can_execute(user):
        raise IncomingDocumentForbiddenError("Incoming document execution permission required.")


def assert_can_resolve_document(
    conn: Connection,
    *,
    user: dict[str, Any],
    document: IncomingDocumentSnapshot,
) -> None:
    assert_can_mutate_document(conn, user=user, document=document)
    user_id = int(user["user_id"])
    wf_repo = SqlAlchemyIncomingWorkflowRepository(conn)
    if wf_repo.user_is_active_coexecutor(document.incoming_document_id, user_id):
        if not wf_repo.user_is_active_primary(document.incoming_document_id, user_id):
            raise IncomingDocumentForbiddenError("COEXECUTOR cannot perform global resolve.")
    if wf_repo.user_is_active_primary(document.incoming_document_id, user_id):
        return
    if document.controller_user_id == user_id:
        return
    if document.access_level == ACCESS_LEVEL_RESTRICTED:
        if can_restricted_bypass(user):
            return
        raise IncomingDocumentForbiddenError(
            "Restricted document resolve requires PRIMARY, controller, or restricted bypass."
        )
    if can_resolve(user):
        return
    raise IncomingDocumentForbiddenError("Incoming document resolve permission required.")
