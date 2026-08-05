"""Order link services for Incoming Information."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from app.incoming_information.application.access_service import assert_can_read_document
from app.incoming_information.application.query_service import get_incoming_document_detail
from app.incoming_information.domain.errors import (
    IncomingDocumentConflictError,
    IncomingDocumentForbiddenError,
    IncomingDocumentNotFoundError,
    IncomingDocumentValidationError,
)
from app.incoming_information.domain.models import OperationalOrderLinkSnapshot, PersonnelOrderLinkSnapshot
from app.incoming_information.domain.status import AUDIT_ACTION_LINK_ADDED, AUDIT_ACTION_LINK_REMOVED, LINK_TYPE_OTHER
from app.incoming_information.infrastructure.audit_repository import SqlAlchemyIncomingDocumentAuditRepository
from app.incoming_information.permissions import can_admin, can_resolve, can_register
from app.security.directory_scope import is_privileged


def _raise_duplicate_link_conflict(exc: IntegrityError, *, message: str) -> None:
    constraint = getattr(getattr(exc, "orig", None), "diag", None)
    constraint_name = getattr(constraint, "constraint_name", None) if constraint else None
    if constraint_name and str(constraint_name).startswith("uq_incoming_document_"):
        raise IncomingDocumentConflictError(message) from exc
    if "uq_incoming_document_" in str(exc):
        raise IncomingDocumentConflictError(message) from exc
    raise exc


def _assert_can_manage_links(user: dict[str, Any]) -> None:
    if is_privileged(user) or can_admin(user) or can_register(user) or can_resolve(user):
        return
    raise IncomingDocumentForbiddenError("Order link mutation permission required.")


def _validate_link_type(conn: Connection, link_type_code: str) -> None:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM public.incoming_document_link_types
            WHERE link_type_code = :code AND is_active = TRUE
            LIMIT 1
            """
        ),
        {"code": link_type_code},
    ).first()
    if not row:
        raise IncomingDocumentValidationError(f"Invalid link_type_code: {link_type_code}")


def add_operational_order_link(
    conn: Connection,
    *,
    user: dict[str, Any],
    incoming_document_id: int,
    operational_order_document_id: int,
    link_type_code: str,
    comment: str | None = None,
) -> OperationalOrderLinkSnapshot:
    _assert_can_manage_links(user)
    get_incoming_document_detail(conn, user=user, incoming_document_id=incoming_document_id)
    _validate_link_type(conn, link_type_code)
    if link_type_code == LINK_TYPE_OTHER and not str(comment or "").strip():
        raise IncomingDocumentValidationError("comment is required for OTHER link type.")

    target = conn.execute(
        text(
            """
            SELECT id
            FROM public.operational_order_documents
            WHERE id = :document_id
            LIMIT 1
            """
        ),
        {"document_id": int(operational_order_document_id)},
    ).first()
    if not target:
        raise IncomingDocumentNotFoundError(
            f"Operational order document {operational_order_document_id} not found."
        )

    try:
        row = conn.execute(
            text(
                """
                INSERT INTO public.incoming_document_operational_order_links (
                    incoming_document_id,
                    operational_order_document_id,
                    link_type_code,
                    comment,
                    created_by_user_id
                )
                VALUES (
                    :incoming_document_id,
                    :operational_order_document_id,
                    :link_type_code,
                    :comment,
                    :created_by_user_id
                )
                RETURNING
                    link_id,
                    incoming_document_id,
                    operational_order_document_id,
                    link_type_code,
                    comment,
                    created_by_user_id,
                    created_at
                """
            ),
            {
                "incoming_document_id": int(incoming_document_id),
                "operational_order_document_id": int(operational_order_document_id),
                "link_type_code": link_type_code,
                "comment": comment,
                "created_by_user_id": int(user["user_id"]),
            },
        ).mappings().one()
    except IntegrityError as exc:
        _raise_duplicate_link_conflict(
            exc,
            message="Operational order link already exists.",
        )

    snapshot = OperationalOrderLinkSnapshot(
        link_id=int(row["link_id"]),
        incoming_document_id=int(row["incoming_document_id"]),
        operational_order_document_id=int(row["operational_order_document_id"]),
        link_type_code=str(row["link_type_code"]),
        comment=str(row["comment"]) if row.get("comment") is not None else None,
        created_by_user_id=int(row["created_by_user_id"]),
        created_at=row["created_at"],
        operational_order_registration_number=None,
        operational_order_status=None,
        operational_order_title=None,
    )
    SqlAlchemyIncomingDocumentAuditRepository(conn).append(
        incoming_document_id=incoming_document_id,
        action=AUDIT_ACTION_LINK_ADDED,
        actor_user_id=int(user["user_id"]),
        new_value=str(operational_order_document_id),
        metadata={"target_kind": "operational_order_document", "link_type_code": link_type_code},
    )
    return snapshot


def list_operational_order_links(
    conn: Connection,
    *,
    user: dict[str, Any],
    incoming_document_id: int,
) -> list[OperationalOrderLinkSnapshot]:
    get_incoming_document_detail(conn, user=user, incoming_document_id=incoming_document_id)
    rows = conn.execute(
        text(
            """
            SELECT
                l.link_id,
                l.incoming_document_id,
                l.operational_order_document_id,
                l.link_type_code,
                l.comment,
                l.created_by_user_id,
                l.created_at,
                d.registration_number AS operational_order_registration_number,
                d.status AS operational_order_status,
                w.proposed_title AS operational_order_title
            FROM public.incoming_document_operational_order_links l
            JOIN public.operational_order_documents d
              ON d.id = l.operational_order_document_id
            LEFT JOIN public.operational_order_draft_workspaces w
              ON w.workspace_id = d.workspace_id
            WHERE l.incoming_document_id = :incoming_document_id
            ORDER BY l.created_at ASC, l.link_id ASC
            """
        ),
        {"incoming_document_id": int(incoming_document_id)},
    ).mappings().all()
    return [
        OperationalOrderLinkSnapshot(
            link_id=int(row["link_id"]),
            incoming_document_id=int(row["incoming_document_id"]),
            operational_order_document_id=int(row["operational_order_document_id"]),
            link_type_code=str(row["link_type_code"]),
            comment=str(row["comment"]) if row.get("comment") is not None else None,
            created_by_user_id=int(row["created_by_user_id"]),
            created_at=row["created_at"],
            operational_order_registration_number=str(row["operational_order_registration_number"])
            if row.get("operational_order_registration_number") is not None
            else None,
            operational_order_status=str(row["operational_order_status"])
            if row.get("operational_order_status") is not None
            else None,
            operational_order_title=str(row["operational_order_title"])
            if row.get("operational_order_title") is not None
            else None,
        )
        for row in rows
    ]


def delete_operational_order_link(
    conn: Connection,
    *,
    user: dict[str, Any],
    incoming_document_id: int,
    link_id: int,
) -> None:
    _assert_can_manage_links(user)
    get_incoming_document_detail(conn, user=user, incoming_document_id=incoming_document_id)
    row = conn.execute(
        text(
            """
            DELETE FROM public.incoming_document_operational_order_links
            WHERE link_id = :link_id
              AND incoming_document_id = :incoming_document_id
            RETURNING operational_order_document_id
            """
        ),
        {"link_id": int(link_id), "incoming_document_id": int(incoming_document_id)},
    ).first()
    if not row:
        raise IncomingDocumentNotFoundError(f"Operational order link {link_id} not found.")
    SqlAlchemyIncomingDocumentAuditRepository(conn).append(
        incoming_document_id=incoming_document_id,
        action=AUDIT_ACTION_LINK_REMOVED,
        actor_user_id=int(user["user_id"]),
        old_value=str(row[0]),
        metadata={"target_kind": "operational_order_document", "link_id": link_id},
    )


def add_personnel_order_link(
    conn: Connection,
    *,
    user: dict[str, Any],
    incoming_document_id: int,
    personnel_order_id: int,
    link_type_code: str,
    comment: str | None = None,
) -> PersonnelOrderLinkSnapshot:
    _assert_can_manage_links(user)
    get_incoming_document_detail(conn, user=user, incoming_document_id=incoming_document_id)
    _validate_link_type(conn, link_type_code)
    if link_type_code == LINK_TYPE_OTHER and not str(comment or "").strip():
        raise IncomingDocumentValidationError("comment is required for OTHER link type.")

    target = conn.execute(
        text(
            """
            SELECT order_id
            FROM public.personnel_orders
            WHERE order_id = :order_id
            LIMIT 1
            """
        ),
        {"order_id": int(personnel_order_id)},
    ).first()
    if not target:
        raise IncomingDocumentNotFoundError(f"Personnel order {personnel_order_id} not found.")

    try:
        row = conn.execute(
            text(
                """
                INSERT INTO public.incoming_document_personnel_order_links (
                    incoming_document_id,
                    personnel_order_id,
                    link_type_code,
                    comment,
                    created_by_user_id
                )
                VALUES (
                    :incoming_document_id,
                    :personnel_order_id,
                    :link_type_code,
                    :comment,
                    :created_by_user_id
                )
                RETURNING
                    link_id,
                    incoming_document_id,
                    personnel_order_id,
                    link_type_code,
                    comment,
                    created_by_user_id,
                    created_at
                """
            ),
            {
                "incoming_document_id": int(incoming_document_id),
                "personnel_order_id": int(personnel_order_id),
                "link_type_code": link_type_code,
                "comment": comment,
                "created_by_user_id": int(user["user_id"]),
            },
        ).mappings().one()
    except IntegrityError as exc:
        _raise_duplicate_link_conflict(
            exc,
            message="Personnel order link already exists.",
        )

    snapshot = PersonnelOrderLinkSnapshot(
        link_id=int(row["link_id"]),
        incoming_document_id=int(row["incoming_document_id"]),
        personnel_order_id=int(row["personnel_order_id"]),
        link_type_code=str(row["link_type_code"]),
        comment=str(row["comment"]) if row.get("comment") is not None else None,
        created_by_user_id=int(row["created_by_user_id"]),
        created_at=row["created_at"],
        personnel_order_number=None,
        personnel_order_status=None,
    )
    SqlAlchemyIncomingDocumentAuditRepository(conn).append(
        incoming_document_id=incoming_document_id,
        action=AUDIT_ACTION_LINK_ADDED,
        actor_user_id=int(user["user_id"]),
        new_value=str(personnel_order_id),
        metadata={"target_kind": "personnel_order", "link_type_code": link_type_code},
    )
    return snapshot


def list_personnel_order_links(
    conn: Connection,
    *,
    user: dict[str, Any],
    incoming_document_id: int,
) -> list[PersonnelOrderLinkSnapshot]:
    get_incoming_document_detail(conn, user=user, incoming_document_id=incoming_document_id)
    rows = conn.execute(
        text(
            """
            SELECT
                l.link_id,
                l.incoming_document_id,
                l.personnel_order_id,
                l.link_type_code,
                l.comment,
                l.created_by_user_id,
                l.created_at,
                po.order_number AS personnel_order_number,
                po.status AS personnel_order_status
            FROM public.incoming_document_personnel_order_links l
            JOIN public.personnel_orders po ON po.order_id = l.personnel_order_id
            WHERE l.incoming_document_id = :incoming_document_id
            ORDER BY l.created_at ASC, l.link_id ASC
            """
        ),
        {"incoming_document_id": int(incoming_document_id)},
    ).mappings().all()
    return [
        PersonnelOrderLinkSnapshot(
            link_id=int(row["link_id"]),
            incoming_document_id=int(row["incoming_document_id"]),
            personnel_order_id=int(row["personnel_order_id"]),
            link_type_code=str(row["link_type_code"]),
            comment=str(row["comment"]) if row.get("comment") is not None else None,
            created_by_user_id=int(row["created_by_user_id"]),
            created_at=row["created_at"],
            personnel_order_number=str(row["personnel_order_number"])
            if row.get("personnel_order_number") is not None
            else None,
            personnel_order_status=str(row["personnel_order_status"])
            if row.get("personnel_order_status") is not None
            else None,
        )
        for row in rows
    ]


def delete_personnel_order_link(
    conn: Connection,
    *,
    user: dict[str, Any],
    incoming_document_id: int,
    link_id: int,
) -> None:
    _assert_can_manage_links(user)
    get_incoming_document_detail(conn, user=user, incoming_document_id=incoming_document_id)
    row = conn.execute(
        text(
            """
            DELETE FROM public.incoming_document_personnel_order_links
            WHERE link_id = :link_id
              AND incoming_document_id = :incoming_document_id
            RETURNING personnel_order_id
            """
        ),
        {"link_id": int(link_id), "incoming_document_id": int(incoming_document_id)},
    ).first()
    if not row:
        raise IncomingDocumentNotFoundError(f"Personnel order link {link_id} not found.")
    SqlAlchemyIncomingDocumentAuditRepository(conn).append(
        incoming_document_id=incoming_document_id,
        action=AUDIT_ACTION_LINK_REMOVED,
        actor_user_id=int(user["user_id"]),
        old_value=str(row[0]),
        metadata={"target_kind": "personnel_order", "link_id": link_id},
    )
