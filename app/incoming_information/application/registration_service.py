"""Registration service for Incoming Information."""
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.db.engine import engine as default_engine
from app.incoming_information.application.access_service import assert_can_register_in_org
from app.incoming_information.domain.errors import IncomingDocumentValidationError
from app.incoming_information.domain.party_validation import (
    validate_addressee_fields_exclusive,
    validate_sender_fields_exclusive,
)
from app.incoming_information.domain.reference_validation import (
    employee_exists,
    org_unit_exists,
    person_exists,
    position_exists,
    user_exists,
)
from app.incoming_information.domain.models import IncomingDocumentCreatePayload, IncomingDocumentSnapshot
from app.incoming_information.domain.status import (
    ACCESS_LEVEL_NORMAL,
    ACCESS_LEVEL_RESTRICTED,
    ACCESS_LEVELS,
    ADDRESSEE_KINDS,
    ADDRESSEE_KIND_EMPLOYEE,
    ADDRESSEE_KIND_ORG_UNIT,
    ADDRESSEE_KIND_POSITION,
    ADDRESSEE_KIND_TEXT,
    ADDRESSEE_KIND_USER,
    SENDER_KINDS,
    SENDER_KIND_EMPLOYEE,
    SENDER_KIND_EXTERNAL_TEXT,
    SENDER_KIND_ORG_UNIT,
    SENDER_KIND_PERSON,
)
from app.incoming_information.infrastructure.audit_repository import SqlAlchemyIncomingDocumentAuditRepository
from app.incoming_information.infrastructure.registration_counter import allocate_registration_number
from app.incoming_information.infrastructure.repository import SqlAlchemyIncomingDocumentRepository
from app.incoming_information.permissions import can_register


def _validate_party(payload_kwargs: dict[str, Any]) -> None:
    sender_kind = payload_kwargs["sender_kind"]
    if sender_kind not in SENDER_KINDS:
        raise IncomingDocumentValidationError(f"Invalid sender_kind: {sender_kind}")
    addressee_kind = payload_kwargs["addressee_kind"]
    if addressee_kind not in ADDRESSEE_KINDS:
        raise IncomingDocumentValidationError(f"Invalid addressee_kind: {addressee_kind}")

    if sender_kind == SENDER_KIND_EXTERNAL_TEXT and not str(payload_kwargs.get("sender_text") or "").strip():
        raise IncomingDocumentValidationError("sender_text is required for EXTERNAL_TEXT sender.")
    if sender_kind == SENDER_KIND_PERSON and not payload_kwargs.get("sender_person_id"):
        raise IncomingDocumentValidationError("sender_person_id is required for PERSON sender.")
    if sender_kind == SENDER_KIND_EMPLOYEE and not payload_kwargs.get("sender_employee_id"):
        raise IncomingDocumentValidationError("sender_employee_id is required for EMPLOYEE sender.")
    if sender_kind == SENDER_KIND_ORG_UNIT and not payload_kwargs.get("sender_org_unit_id"):
        raise IncomingDocumentValidationError("sender_org_unit_id is required for ORG_UNIT sender.")

    if addressee_kind == ADDRESSEE_KIND_TEXT and not str(payload_kwargs.get("addressee_text") or "").strip():
        raise IncomingDocumentValidationError("addressee_text is required for TEXT addressee.")
    if addressee_kind == ADDRESSEE_KIND_USER and not payload_kwargs.get("addressee_user_id"):
        raise IncomingDocumentValidationError("addressee_user_id is required for USER addressee.")
    if addressee_kind == ADDRESSEE_KIND_EMPLOYEE and not payload_kwargs.get("addressee_employee_id"):
        raise IncomingDocumentValidationError("addressee_employee_id is required for EMPLOYEE addressee.")
    if addressee_kind == ADDRESSEE_KIND_ORG_UNIT and not payload_kwargs.get("addressee_org_unit_id"):
        raise IncomingDocumentValidationError("addressee_org_unit_id is required for ORG_UNIT addressee.")
    if addressee_kind == ADDRESSEE_KIND_POSITION and not payload_kwargs.get("addressee_position_id"):
        raise IncomingDocumentValidationError("addressee_position_id is required for POSITION addressee.")

    validate_sender_fields_exclusive(
        sender_kind,
        sender_person_id=payload_kwargs.get("sender_person_id"),
        sender_employee_id=payload_kwargs.get("sender_employee_id"),
        sender_org_unit_id=payload_kwargs.get("sender_org_unit_id"),
        sender_text=payload_kwargs.get("sender_text"),
    )
    validate_addressee_fields_exclusive(
        addressee_kind,
        addressee_user_id=payload_kwargs.get("addressee_user_id"),
        addressee_employee_id=payload_kwargs.get("addressee_employee_id"),
        addressee_org_unit_id=payload_kwargs.get("addressee_org_unit_id"),
        addressee_position_id=payload_kwargs.get("addressee_position_id"),
        addressee_text=payload_kwargs.get("addressee_text"),
    )


def _validate_registration_references(conn: Connection, payload_kwargs: dict[str, Any]) -> None:
    sender_kind = payload_kwargs["sender_kind"]
    addressee_kind = payload_kwargs["addressee_kind"]
    if sender_kind == SENDER_KIND_PERSON and not person_exists(conn, int(payload_kwargs["sender_person_id"])):
        raise IncomingDocumentValidationError("sender_person_id is invalid.")
    if sender_kind == SENDER_KIND_EMPLOYEE and not employee_exists(conn, int(payload_kwargs["sender_employee_id"])):
        raise IncomingDocumentValidationError("sender_employee_id is invalid.")
    if sender_kind == SENDER_KIND_ORG_UNIT and not org_unit_exists(conn, int(payload_kwargs["sender_org_unit_id"])):
        raise IncomingDocumentValidationError("sender_org_unit_id is invalid.")
    if addressee_kind == ADDRESSEE_KIND_USER and not user_exists(conn, int(payload_kwargs["addressee_user_id"])):
        raise IncomingDocumentValidationError("addressee_user_id is invalid.")
    if addressee_kind == ADDRESSEE_KIND_EMPLOYEE and not employee_exists(conn, int(payload_kwargs["addressee_employee_id"])):
        raise IncomingDocumentValidationError("addressee_employee_id is invalid.")
    if addressee_kind == ADDRESSEE_KIND_ORG_UNIT and not org_unit_exists(conn, int(payload_kwargs["addressee_org_unit_id"])):
        raise IncomingDocumentValidationError("addressee_org_unit_id is invalid.")
    if addressee_kind == ADDRESSEE_KIND_POSITION and not position_exists(conn, int(payload_kwargs["addressee_position_id"])):
        raise IncomingDocumentValidationError("addressee_position_id is invalid.")
    if not org_unit_exists(conn, int(payload_kwargs["registration_org_unit_id"])):
        raise IncomingDocumentValidationError("registration_org_unit_id is invalid.")
    responsible_org_unit_id = payload_kwargs.get("responsible_org_unit_id")
    if responsible_org_unit_id is not None and not org_unit_exists(conn, int(responsible_org_unit_id)):
        raise IncomingDocumentValidationError("responsible_org_unit_id is invalid.")


def resolve_default_responsible_org_unit_id(
    conn: Connection,
    *,
    addressee_kind: str,
    addressee_user_id: int | None,
    addressee_employee_id: int | None,
    addressee_org_unit_id: int | None,
    registration_org_unit_id: int,
) -> int:
    if addressee_kind == ADDRESSEE_KIND_ORG_UNIT and addressee_org_unit_id is not None:
        return int(addressee_org_unit_id)
    if addressee_kind == ADDRESSEE_KIND_USER and addressee_user_id is not None:
        row = conn.execute(
            text(
                """
                SELECT unit_id
                FROM public.users
                WHERE user_id = :user_id
                LIMIT 1
                """
            ),
            {"user_id": int(addressee_user_id)},
        ).first()
        if row and row[0] is not None:
            return int(row[0])
    if addressee_kind == ADDRESSEE_KIND_EMPLOYEE and addressee_employee_id is not None:
        row = conn.execute(
            text(
                """
                SELECT org_unit_id
                FROM public.employees
                WHERE employee_id = :employee_id
                LIMIT 1
                """
            ),
            {"employee_id": int(addressee_employee_id)},
        ).first()
        if row and row[0] is not None:
            return int(row[0])
    return int(registration_org_unit_id)


def register_incoming_document(
    conn: Connection,
    *,
    user: dict[str, Any],
    received_at: date,
    document_type_id: int,
    receipt_channel_id: int,
    summary: str,
    access_level: str = ACCESS_LEVEL_NORMAL,
    sender_kind: str,
    sender_person_id: int | None = None,
    sender_employee_id: int | None = None,
    sender_org_unit_id: int | None = None,
    sender_text: str | None = None,
    addressee_kind: str,
    addressee_user_id: int | None = None,
    addressee_employee_id: int | None = None,
    addressee_org_unit_id: int | None = None,
    addressee_position_id: int | None = None,
    addressee_text: str | None = None,
    registration_org_unit_id: int,
    responsible_org_unit_id: int | None = None,
    received_after_registration_exception: bool = False,
    exception_comment: str | None = None,
    note: str | None = None,
    is_control_document: bool = False,
    priority_level: str | None = None,
) -> IncomingDocumentSnapshot:
    if not can_register(user):
        from app.incoming_information.domain.errors import IncomingDocumentForbiddenError

        raise IncomingDocumentForbiddenError("Registration permission required.")

    if access_level not in ACCESS_LEVELS:
        raise IncomingDocumentValidationError(f"Invalid access_level: {access_level}")
    if not str(summary or "").strip():
        raise IncomingDocumentValidationError("summary is required.")

    payload_kwargs = {
        "sender_kind": sender_kind,
        "sender_person_id": sender_person_id,
        "sender_employee_id": sender_employee_id,
        "sender_org_unit_id": sender_org_unit_id,
        "sender_text": sender_text,
        "addressee_kind": addressee_kind,
        "addressee_user_id": addressee_user_id,
        "addressee_employee_id": addressee_employee_id,
        "addressee_org_unit_id": addressee_org_unit_id,
        "addressee_position_id": addressee_position_id,
        "addressee_text": addressee_text,
    }
    _validate_party(payload_kwargs)
    _validate_registration_references(
        conn,
        {
            **payload_kwargs,
            "registration_org_unit_id": registration_org_unit_id,
            "responsible_org_unit_id": responsible_org_unit_id,
        },
    )

    assert_can_register_in_org(user, registration_org_unit_id)

    registered_at = datetime.now(UTC)
    if received_at > registered_at.date() and not received_after_registration_exception:
        raise IncomingDocumentValidationError(
            "received_at cannot be after registered_at without exception flag and comment."
        )
    if received_after_registration_exception and not str(exception_comment or "").strip():
        raise IncomingDocumentValidationError("exception_comment is required when received_after_registration_exception is true.")

    repo = SqlAlchemyIncomingDocumentRepository(conn)
    if not repo.dictionary_exists("incoming_document_types", document_type_id):
        raise IncomingDocumentValidationError("document_type_id is invalid or inactive.")
    if not repo.dictionary_exists("incoming_receipt_channels", receipt_channel_id):
        raise IncomingDocumentValidationError("receipt_channel_id is invalid or inactive.")

    resolved_responsible = responsible_org_unit_id or resolve_default_responsible_org_unit_id(
        conn,
        addressee_kind=addressee_kind,
        addressee_user_id=addressee_user_id,
        addressee_employee_id=addressee_employee_id,
        addressee_org_unit_id=addressee_org_unit_id,
        registration_org_unit_id=registration_org_unit_id,
    )

    registration_year = registered_at.year
    registration_seq, registration_number = allocate_registration_number(
        conn,
        registration_year=registration_year,
    )
    status_id = repo.resolve_initial_status_id()

    payload = IncomingDocumentCreatePayload(
        received_at=received_at,
        document_type_id=int(document_type_id),
        receipt_channel_id=int(receipt_channel_id),
        summary=str(summary).strip(),
        access_level=access_level,
        sender_kind=sender_kind,
        sender_person_id=sender_person_id,
        sender_employee_id=sender_employee_id,
        sender_org_unit_id=sender_org_unit_id,
        sender_text=sender_text,
        addressee_kind=addressee_kind,
        addressee_user_id=addressee_user_id,
        addressee_employee_id=addressee_employee_id,
        addressee_org_unit_id=addressee_org_unit_id,
        addressee_position_id=addressee_position_id,
        addressee_text=addressee_text,
        registration_org_unit_id=int(registration_org_unit_id),
        responsible_org_unit_id=int(resolved_responsible),
        received_after_registration_exception=bool(received_after_registration_exception),
        exception_comment=exception_comment,
        note=note,
        is_control_document=bool(is_control_document),
        priority_level=priority_level,
        created_by_user_id=int(user["user_id"]),
    )

    created = repo.create(
        payload=payload,
        registration_number=registration_number,
        registration_year=registration_year,
        registration_seq=registration_seq,
        status_id=status_id,
        registered_at=registered_at,
    )
    SqlAlchemyIncomingDocumentAuditRepository(conn).append_created(
        incoming_document_id=created.incoming_document_id,
        actor_user_id=int(user["user_id"]),
        registration_number=created.registration_number,
    )
    return created


def register_incoming_document_with_engine(
    *,
    user: dict[str, Any],
    db_engine: Engine | None = None,
    **kwargs: Any,
) -> IncomingDocumentSnapshot:
    db = db_engine or default_engine
    with db.begin() as conn:
        return register_incoming_document(conn, user=user, **kwargs)
