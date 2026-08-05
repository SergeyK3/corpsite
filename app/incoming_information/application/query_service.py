"""Read/query services for Incoming Information."""
from __future__ import annotations

from typing import Any

from sqlalchemy.engine import Connection, Engine

from app.db.engine import engine as default_engine
from app.incoming_information.application.access_service import assert_can_read_document, employee_id_for_user
from app.incoming_information.domain.errors import IncomingDocumentForbiddenError, IncomingDocumentNotFoundError
from app.incoming_information.domain.models import IncomingDocumentListItem, IncomingDocumentSnapshot
from app.incoming_information.infrastructure.audit_repository import SqlAlchemyIncomingDocumentAuditRepository
from app.incoming_information.infrastructure.repository import SqlAlchemyIncomingDocumentRepository
from app.incoming_information.permissions import (
    can_restricted_bypass,
    has_base_read_permission,
)
from app.incoming_information.scope import resolve_document_read_scope_unit_ids


def _user_has_any_read_permission(user: dict[str, Any]) -> bool:
    """RESTRICTED_BYPASS alone does not grant list/detail access."""
    return has_base_read_permission(user)


def get_incoming_document_detail(
    conn: Connection,
    *,
    user: dict[str, Any],
    incoming_document_id: int,
) -> IncomingDocumentSnapshot:
    if not _user_has_any_read_permission(user):
        raise IncomingDocumentForbiddenError("Incoming document read access denied.")
    repo = SqlAlchemyIncomingDocumentRepository(conn)
    document = repo.get_by_id(incoming_document_id)
    if document is None:
        raise IncomingDocumentNotFoundError(f"Incoming document {incoming_document_id} not found.")
    assert_can_read_document(conn, user=user, document=document)
    return document


def list_incoming_documents(
    conn: Connection,
    *,
    user: dict[str, Any],
    q: str | None = None,
    status_id: int | None = None,
    document_type_id: int | None = None,
    responsible_org_unit_id: int | None = None,
    overdue_only: bool | None = None,
    limit: int = 50,
    offset: int = 0,
    sort: str = "registered_at",
) -> tuple[list[IncomingDocumentListItem], int]:
    if not _user_has_any_read_permission(user):
        raise IncomingDocumentForbiddenError("Incoming document read access denied.")

    scope = resolve_document_read_scope_unit_ids(user)
    employee_id = employee_id_for_user(conn, int(user["user_id"]))
    repo = SqlAlchemyIncomingDocumentRepository(conn)
    return repo.list_documents(
        q=q,
        status_id=status_id,
        document_type_id=document_type_id,
        responsible_org_unit_id=responsible_org_unit_id,
        responsible_org_unit_ids=scope,
        overdue_only=overdue_only,
        limit=limit,
        offset=offset,
        sort=sort,
        access_user_id=int(user["user_id"]),
        access_employee_id=employee_id,
        restricted_bypass=can_restricted_bypass(user) and has_base_read_permission(user),
    )


def list_incoming_document_audit(
    conn: Connection,
    *,
    user: dict[str, Any],
    incoming_document_id: int,
) -> list[dict[str, Any]]:
    document = get_incoming_document_detail(
        conn,
        user=user,
        incoming_document_id=incoming_document_id,
    )
    _ = document
    return SqlAlchemyIncomingDocumentAuditRepository(conn).list_for_document(incoming_document_id)


def get_incoming_document_detail_with_engine(
    *,
    user: dict[str, Any],
    incoming_document_id: int,
    db_engine: Engine | None = None,
) -> IncomingDocumentSnapshot:
    db = db_engine or default_engine
    with db.connect() as conn:
        return get_incoming_document_detail(conn, user=user, incoming_document_id=incoming_document_id)


def list_incoming_documents_with_engine(
    *,
    user: dict[str, Any],
    db_engine: Engine | None = None,
    **kwargs: Any,
) -> tuple[list[IncomingDocumentListItem], int]:
    db = db_engine or default_engine
    with db.connect() as conn:
        return list_incoming_documents(conn, user=user, **kwargs)
