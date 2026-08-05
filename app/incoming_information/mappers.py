"""Response mappers for Incoming Information."""
from __future__ import annotations

from app.incoming_information.domain.models import (
    IncomingAttachmentSnapshot,
    IncomingDocumentListItem,
    IncomingDocumentSnapshot,
    OperationalOrderLinkSnapshot,
    PersonnelOrderLinkSnapshot,
)
from app.incoming_information.schemas import (
    IncomingAttachmentOut,
    IncomingDocumentListItemOut,
    IncomingDocumentOut,
    OperationalOrderLinkOut,
    PersonnelOrderLinkOut,
)


def document_to_out(document: IncomingDocumentSnapshot) -> IncomingDocumentOut:
    return IncomingDocumentOut(
        incoming_document_id=document.incoming_document_id,
        registration_number=document.registration_number,
        registration_year=document.registration_year,
        registration_seq=document.registration_seq,
        received_at=document.received_at,
        registered_at=document.registered_at,
        document_type_id=document.document_type_id,
        document_type_code=document.document_type_code,
        document_type_label=document.document_type_label,
        receipt_channel_id=document.receipt_channel_id,
        receipt_channel_code=document.receipt_channel_code,
        receipt_channel_label=document.receipt_channel_label,
        status_id=document.status_id,
        status_code=document.status_code,
        status_label=document.status_label,
        status_is_terminal=document.status_is_terminal,
        planned_result_id=document.planned_result_id,
        planned_result_code=document.planned_result_code,
        planned_result_label=document.planned_result_label,
        summary=document.summary,
        access_level=document.access_level,
        sender_kind=document.sender_kind,
        sender_person_id=document.sender_person_id,
        sender_employee_id=document.sender_employee_id,
        sender_org_unit_id=document.sender_org_unit_id,
        sender_text=document.sender_text,
        addressee_kind=document.addressee_kind,
        addressee_user_id=document.addressee_user_id,
        addressee_employee_id=document.addressee_employee_id,
        addressee_org_unit_id=document.addressee_org_unit_id,
        addressee_position_id=document.addressee_position_id,
        addressee_text=document.addressee_text,
        registration_org_unit_id=document.registration_org_unit_id,
        responsible_org_unit_id=document.responsible_org_unit_id,
        resolution_text=document.resolution_text,
        due_date=document.due_date,
        planned_result_note=document.planned_result_note,
        executed_at=document.executed_at,
        execution_result=document.execution_result,
        closed_at=document.closed_at,
        note=document.note,
        priority_level=document.priority_level,
        is_control_document=document.is_control_document,
        received_after_registration_exception=document.received_after_registration_exception,
        exception_comment=document.exception_comment,
        transfer_comment=document.transfer_comment,
        cancellation_reason=document.cancellation_reason,
        control_decision=document.control_decision,
        control_comment=document.control_comment,
        controller_user_id=document.controller_user_id,
        row_version=document.row_version,
        closed_by_user_id=document.closed_by_user_id,
        cancelled_at=document.cancelled_at,
        cancelled_by_user_id=document.cancelled_by_user_id,
        transferred_at=document.transferred_at,
        transferred_by_user_id=document.transferred_by_user_id,
        resolve_recorded_at=document.resolve_recorded_at,
        reopened_at=document.reopened_at,
        reopen_reason=document.reopen_reason,
        reopen_count=document.reopen_count,
        external_recipient_kind=document.external_recipient_kind,
        external_recipient_user_id=document.external_recipient_user_id,
        external_recipient_org_unit_id=document.external_recipient_org_unit_id,
        external_recipient_text=document.external_recipient_text,
        created_by_user_id=document.created_by_user_id,
        updated_by_user_id=document.updated_by_user_id,
        created_at=document.created_at,
        updated_at=document.updated_at,
        is_overdue=document.is_overdue,
    )


def list_item_to_out(item: IncomingDocumentListItem) -> IncomingDocumentListItemOut:
    return IncomingDocumentListItemOut(
        incoming_document_id=item.incoming_document_id,
        registration_number=item.registration_number,
        registered_at=item.registered_at,
        document_type_label=item.document_type_label,
        summary=item.summary,
        sender_display=item.sender_display,
        addressee_display=item.addressee_display,
        primary_executor_display=item.primary_executor_display,
        due_date=item.due_date,
        status_code=item.status_code,
        status_label=item.status_label,
        access_level=item.access_level,
        responsible_org_unit_id=item.responsible_org_unit_id,
        is_overdue=item.is_overdue,
    )


def attachment_to_out(item: IncomingAttachmentSnapshot) -> IncomingAttachmentOut:
    return IncomingAttachmentOut(
        attachment_id=item.attachment_id,
        incoming_document_id=item.incoming_document_id,
        file_id=item.file_id,
        original_filename=item.original_filename,
        content_type=item.content_type,
        size_bytes=item.size_bytes,
        uploaded_by_user_id=item.uploaded_by_user_id,
        created_at=item.created_at,
    )


def operational_link_to_out(item: OperationalOrderLinkSnapshot) -> OperationalOrderLinkOut:
    return OperationalOrderLinkOut(
        link_id=item.link_id,
        incoming_document_id=item.incoming_document_id,
        operational_order_document_id=item.operational_order_document_id,
        link_type_code=item.link_type_code,
        comment=item.comment,
        created_by_user_id=item.created_by_user_id,
        created_at=item.created_at,
        operational_order_registration_number=item.operational_order_registration_number,
        operational_order_status=item.operational_order_status,
        operational_order_title=item.operational_order_title,
    )


def personnel_link_to_out(item: PersonnelOrderLinkSnapshot) -> PersonnelOrderLinkOut:
    return PersonnelOrderLinkOut(
        link_id=item.link_id,
        incoming_document_id=item.incoming_document_id,
        personnel_order_id=item.personnel_order_id,
        link_type_code=item.link_type_code,
        comment=item.comment,
        created_by_user_id=item.created_by_user_id,
        created_at=item.created_at,
        personnel_order_number=item.personnel_order_number,
        personnel_order_status=item.personnel_order_status,
    )
