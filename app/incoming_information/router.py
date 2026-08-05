"""Incoming Information API router."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from app.auth import get_current_user
from app.db.engine import engine
from app.directory.common import as_http500
from app.incoming_information.application.attachment_service import (
    cleanup_staging_upload,
    execute_attachment_deletion,
    execute_attachment_upload,
    list_attachments,
    read_attachment_content,
)
from app.incoming_information.application.attachment_upload import stream_upload_file_to_staging
from app.incoming_information.domain.content_disposition import build_attachment_content_disposition
from app.incoming_information.application.link_service import (
    add_operational_order_link,
    add_personnel_order_link,
    delete_operational_order_link,
    delete_personnel_order_link,
    list_operational_order_links,
    list_personnel_order_links,
)
from app.incoming_information.application.query_service import (
    get_incoming_document_detail,
    list_incoming_document_audit,
    list_incoming_documents,
)
from app.incoming_information.application.registration_service import register_incoming_document
from app.incoming_information.application.workflow_service import (
    assign_incoming_document,
    cancel_incoming_document,
    change_deadline_incoming_document,
    close_incoming_document,
    reassign_incoming_document,
    reopen_incoming_document,
    request_information_incoming_document,
    resolve_incoming_document,
    resume_incoming_document,
    start_incoming_document,
    transfer_incoming_document,
)
from app.incoming_information.domain.errors import (
    IncomingAttachmentNotFoundError,
    IncomingDocumentConflictError,
    IncomingDocumentForbiddenError,
    IncomingDocumentInvalidTransitionError,
    IncomingDocumentNotFoundError,
    IncomingDocumentPayloadTooLargeError,
    IncomingDocumentValidationError,
    IncomingDocumentVersionConflictError,
    IncomingInformationError,
)
from app.incoming_information.mappers import (
    attachment_to_out,
    document_to_out,
    list_item_to_out,
    operational_link_to_out,
    personnel_link_to_out,
)
from app.incoming_information.schemas import (
    IncomingAssignIn,
    IncomingAttachmentOut,
    IncomingAuditEntryOut,
    IncomingCancelIn,
    IncomingChangeDeadlineIn,
    IncomingCloseIn,
    IncomingDocumentListOut,
    IncomingDocumentOut,
    IncomingDocumentRegisterIn,
    IncomingReassignIn,
    IncomingReopenIn,
    IncomingResolveIn,
    IncomingTransferIn,
    IncomingWorkflowCommentIn,
    OperationalOrderLinkOut,
    OrderLinkIn,
    PersonnelOrderLinkOut,
    WorkflowExpectedVersionIn,
)

router = APIRouter(prefix="/api/incoming-information", tags=["incoming-information"])


def _map_error(exc: IncomingInformationError) -> HTTPException:
    if isinstance(exc, IncomingDocumentNotFoundError):
        return HTTPException(status_code=404, detail={"code": exc.code, "message": str(exc)})
    if isinstance(exc, IncomingAttachmentNotFoundError):
        return HTTPException(status_code=404, detail={"code": exc.code, "message": str(exc)})
    if isinstance(exc, IncomingDocumentForbiddenError):
        return HTTPException(status_code=403, detail={"code": exc.code, "message": str(exc)})
    if isinstance(exc, IncomingDocumentValidationError):
        return HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)})
    if isinstance(exc, IncomingDocumentInvalidTransitionError):
        return HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)})
    if isinstance(exc, IncomingDocumentVersionConflictError):
        return HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)})
    if isinstance(exc, IncomingDocumentPayloadTooLargeError):
        return HTTPException(status_code=413, detail={"code": exc.code, "message": str(exc)})
    if isinstance(exc, IncomingDocumentConflictError):
        return HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)})
    return HTTPException(status_code=400, detail={"code": exc.code, "message": str(exc)})


def _workflow_out(updated) -> IncomingDocumentOut:
    return document_to_out(updated)


@router.post("/incoming-documents", response_model=IncomingDocumentOut)
def post_incoming_document(
    body: IncomingDocumentRegisterIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> IncomingDocumentOut:
    try:
        with engine.begin() as conn:
            created = register_incoming_document(
                conn,
                user=user,
                received_at=body.received_at,
                document_type_id=body.document_type_id,
                receipt_channel_id=body.receipt_channel_id,
                summary=body.summary,
                access_level=body.access_level,
                sender_kind=body.sender_kind,
                sender_person_id=body.sender_person_id,
                sender_employee_id=body.sender_employee_id,
                sender_org_unit_id=body.sender_org_unit_id,
                sender_text=body.sender_text,
                addressee_kind=body.addressee_kind,
                addressee_user_id=body.addressee_user_id,
                addressee_employee_id=body.addressee_employee_id,
                addressee_org_unit_id=body.addressee_org_unit_id,
                addressee_position_id=body.addressee_position_id,
                addressee_text=body.addressee_text,
                registration_org_unit_id=body.registration_org_unit_id,
                responsible_org_unit_id=body.responsible_org_unit_id,
                received_after_registration_exception=body.received_after_registration_exception,
                exception_comment=body.exception_comment,
                note=body.note,
                is_control_document=body.is_control_document,
                priority_level=body.priority_level,
            )
        return document_to_out(created)
    except IncomingInformationError as exc:
        raise _map_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc) from exc


@router.get("/incoming-documents", response_model=IncomingDocumentListOut)
def get_incoming_documents(
    q: str | None = Query(default=None),
    status_id: int | None = Query(default=None, ge=1),
    document_type_id: int | None = Query(default=None, ge=1),
    responsible_org_unit_id: int | None = Query(default=None, ge=1),
    overdue_only: bool | None = Query(default=None),
    sort: str = Query(default="registered_at"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: dict[str, Any] = Depends(get_current_user),
) -> IncomingDocumentListOut:
    try:
        with engine.connect() as conn:
            items, total = list_incoming_documents(
                conn,
                user=user,
                q=q,
                status_id=status_id,
                document_type_id=document_type_id,
                responsible_org_unit_id=responsible_org_unit_id,
                overdue_only=overdue_only,
                limit=limit,
                offset=offset,
                sort=sort,
            )
        return IncomingDocumentListOut(
            items=[list_item_to_out(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
        )
    except IncomingInformationError as exc:
        raise _map_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc) from exc


@router.get("/incoming-documents/{incoming_document_id}", response_model=IncomingDocumentOut)
def get_incoming_document(
    incoming_document_id: int,
    user: dict[str, Any] = Depends(get_current_user),
) -> IncomingDocumentOut:
    try:
        with engine.connect() as conn:
            document = get_incoming_document_detail(
                conn,
                user=user,
                incoming_document_id=incoming_document_id,
            )
        return document_to_out(document)
    except IncomingInformationError as exc:
        raise _map_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc) from exc


@router.get("/incoming-documents/{incoming_document_id}/audit", response_model=list[IncomingAuditEntryOut])
def get_incoming_document_audit(
    incoming_document_id: int,
    user: dict[str, Any] = Depends(get_current_user),
) -> list[IncomingAuditEntryOut]:
    try:
        with engine.connect() as conn:
            rows = list_incoming_document_audit(
                conn,
                user=user,
                incoming_document_id=incoming_document_id,
            )
        return [IncomingAuditEntryOut(**row) for row in rows]
    except IncomingInformationError as exc:
        raise _map_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc) from exc


@router.post(
    "/incoming-documents/{incoming_document_id}/attachments",
    response_model=IncomingAttachmentOut,
)
async def post_incoming_attachment(
    incoming_document_id: int,
    file: UploadFile = File(...),
    user: dict[str, Any] = Depends(get_current_user),
) -> IncomingAttachmentOut:
    import uuid

    staging_id = uuid.uuid4().hex
    try:
        size_bytes = await stream_upload_file_to_staging(file, staging_id)
        created = execute_attachment_upload(
            engine,
            user=user,
            incoming_document_id=incoming_document_id,
            staging_id=staging_id,
            content_type=file.content_type,
            original_filename=file.filename or "attachment",
            size_bytes=size_bytes,
        )
        return attachment_to_out(created)
    except IncomingInformationError as exc:
        cleanup_staging_upload(staging_id)
        raise _map_error(exc) from exc
    except HTTPException:
        cleanup_staging_upload(staging_id)
        raise
    except Exception as exc:
        cleanup_staging_upload(staging_id)
        raise as_http500(exc) from exc


@router.get(
    "/incoming-documents/{incoming_document_id}/attachments",
    response_model=list[IncomingAttachmentOut],
)
def get_incoming_attachments(
    incoming_document_id: int,
    user: dict[str, Any] = Depends(get_current_user),
) -> list[IncomingAttachmentOut]:
    try:
        with engine.connect() as conn:
            items = list_attachments(conn, user=user, incoming_document_id=incoming_document_id)
        return [attachment_to_out(item) for item in items]
    except IncomingInformationError as exc:
        raise _map_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc) from exc


@router.get("/attachments/{attachment_id}/download")
def download_incoming_attachment(
    attachment_id: int,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    try:
        with engine.connect() as conn:
            snapshot, content = read_attachment_content(conn, user=user, attachment_id=attachment_id)
        return Response(
            content=content,
            media_type=snapshot.content_type,
            headers={
                "Content-Disposition": build_attachment_content_disposition(snapshot.original_filename),
            },
        )
    except IncomingInformationError as exc:
        raise _map_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc) from exc


@router.delete("/attachments/{attachment_id}", status_code=204)
def delete_incoming_attachment_route(
    attachment_id: int,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    try:
        execute_attachment_deletion(engine, user=user, attachment_id=attachment_id)
        return Response(status_code=204)
    except IncomingInformationError as exc:
        raise _map_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc) from exc


@router.get(
    "/incoming-documents/{incoming_document_id}/links/operational-orders",
    response_model=list[OperationalOrderLinkOut],
)
def get_operational_order_links(
    incoming_document_id: int,
    user: dict[str, Any] = Depends(get_current_user),
) -> list[OperationalOrderLinkOut]:
    try:
        with engine.connect() as conn:
            items = list_operational_order_links(
                conn,
                user=user,
                incoming_document_id=incoming_document_id,
            )
        return [operational_link_to_out(item) for item in items]
    except IncomingInformationError as exc:
        raise _map_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc) from exc


@router.post(
    "/incoming-documents/{incoming_document_id}/links/operational-orders/{operational_order_document_id}",
    response_model=OperationalOrderLinkOut,
)
def post_operational_order_link(
    incoming_document_id: int,
    operational_order_document_id: int,
    body: OrderLinkIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> OperationalOrderLinkOut:
    try:
        with engine.begin() as conn:
            created = add_operational_order_link(
                conn,
                user=user,
                incoming_document_id=incoming_document_id,
                operational_order_document_id=operational_order_document_id,
                link_type_code=body.link_type_code,
                comment=body.comment,
            )
            enriched = list_operational_order_links(
                conn,
                user=user,
                incoming_document_id=incoming_document_id,
            )
        match = next((item for item in enriched if item.link_id == created.link_id), created)
        return operational_link_to_out(match)
    except IncomingInformationError as exc:
        raise _map_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc) from exc


@router.delete(
    "/incoming-documents/{incoming_document_id}/links/operational-orders/{link_id}",
    status_code=204,
)
def delete_operational_order_link_route(
    incoming_document_id: int,
    link_id: int,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    try:
        with engine.begin() as conn:
            delete_operational_order_link(
                conn,
                user=user,
                incoming_document_id=incoming_document_id,
                link_id=link_id,
            )
        return Response(status_code=204)
    except IncomingInformationError as exc:
        raise _map_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc) from exc


@router.get(
    "/incoming-documents/{incoming_document_id}/links/personnel-orders",
    response_model=list[PersonnelOrderLinkOut],
)
def get_personnel_order_links(
    incoming_document_id: int,
    user: dict[str, Any] = Depends(get_current_user),
) -> list[PersonnelOrderLinkOut]:
    try:
        with engine.connect() as conn:
            items = list_personnel_order_links(
                conn,
                user=user,
                incoming_document_id=incoming_document_id,
            )
        return [personnel_link_to_out(item) for item in items]
    except IncomingInformationError as exc:
        raise _map_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc) from exc


@router.post(
    "/incoming-documents/{incoming_document_id}/links/personnel-orders/{personnel_order_id}",
    response_model=PersonnelOrderLinkOut,
)
def post_personnel_order_link(
    incoming_document_id: int,
    personnel_order_id: int,
    body: OrderLinkIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> PersonnelOrderLinkOut:
    try:
        with engine.begin() as conn:
            created = add_personnel_order_link(
                conn,
                user=user,
                incoming_document_id=incoming_document_id,
                personnel_order_id=personnel_order_id,
                link_type_code=body.link_type_code,
                comment=body.comment,
            )
            enriched = list_personnel_order_links(
                conn,
                user=user,
                incoming_document_id=incoming_document_id,
            )
        match = next((item for item in enriched if item.link_id == created.link_id), created)
        return personnel_link_to_out(match)
    except IncomingInformationError as exc:
        raise _map_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc) from exc


@router.delete(
    "/incoming-documents/{incoming_document_id}/links/personnel-orders/{link_id}",
    status_code=204,
)
def delete_personnel_order_link_route(
    incoming_document_id: int,
    link_id: int,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    try:
        with engine.begin() as conn:
            delete_personnel_order_link(
                conn,
                user=user,
                incoming_document_id=incoming_document_id,
                link_id=link_id,
            )
        return Response(status_code=204)
    except IncomingInformationError as exc:
        raise _map_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc) from exc


@router.post("/incoming-documents/{incoming_document_id}/assign", response_model=IncomingDocumentOut)
def post_assign_incoming_document(
    incoming_document_id: int,
    body: IncomingAssignIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> IncomingDocumentOut:
    try:
        with engine.begin() as conn:
            updated = assign_incoming_document(
                conn,
                user=user,
                incoming_document_id=incoming_document_id,
                expected_version=body.expected_version,
                primary_user_id=body.primary_user_id,
                coexecutor_user_ids=body.coexecutor_user_ids,
                org_unit_id=body.org_unit_id,
                due_date=body.due_date,
                controller_user_id=body.controller_user_id,
            )
        return _workflow_out(updated)
    except IncomingInformationError as exc:
        raise _map_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc) from exc


@router.post("/incoming-documents/{incoming_document_id}/reassign", response_model=IncomingDocumentOut)
def post_reassign_incoming_document(
    incoming_document_id: int,
    body: IncomingReassignIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> IncomingDocumentOut:
    try:
        with engine.begin() as conn:
            updated = reassign_incoming_document(
                conn,
                user=user,
                incoming_document_id=incoming_document_id,
                expected_version=body.expected_version,
                primary_user_id=body.primary_user_id,
                reason=body.reason,
                org_unit_id=body.org_unit_id,
            )
        return _workflow_out(updated)
    except IncomingInformationError as exc:
        raise _map_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc) from exc


@router.post("/incoming-documents/{incoming_document_id}/transfer", response_model=IncomingDocumentOut)
def post_transfer_incoming_document(
    incoming_document_id: int,
    body: IncomingTransferIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> IncomingDocumentOut:
    try:
        with engine.begin() as conn:
            updated = transfer_incoming_document(
                conn,
                user=user,
                incoming_document_id=incoming_document_id,
                expected_version=body.expected_version,
                transfer_scope=body.transfer_scope,
                comment=body.comment,
                target_org_unit_id=body.target_org_unit_id,
                recipient_kind=body.recipient_kind,
                recipient_user_id=body.recipient_user_id,
                recipient_org_unit_id=body.recipient_org_unit_id,
                recipient_text=body.recipient_text,
            )
        return _workflow_out(updated)
    except IncomingInformationError as exc:
        raise _map_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc) from exc


@router.post("/incoming-documents/{incoming_document_id}/start", response_model=IncomingDocumentOut)
def post_start_incoming_document(
    incoming_document_id: int,
    body: WorkflowExpectedVersionIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> IncomingDocumentOut:
    try:
        with engine.begin() as conn:
            updated = start_incoming_document(
                conn,
                user=user,
                incoming_document_id=incoming_document_id,
                expected_version=body.expected_version,
            )
        return _workflow_out(updated)
    except IncomingInformationError as exc:
        raise _map_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc) from exc


@router.post("/incoming-documents/{incoming_document_id}/request-information", response_model=IncomingDocumentOut)
def post_request_information_incoming_document(
    incoming_document_id: int,
    body: IncomingWorkflowCommentIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> IncomingDocumentOut:
    try:
        with engine.begin() as conn:
            updated = request_information_incoming_document(
                conn,
                user=user,
                incoming_document_id=incoming_document_id,
                expected_version=body.expected_version,
                reason=body.reason or body.comment,
            )
        return _workflow_out(updated)
    except IncomingInformationError as exc:
        raise _map_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc) from exc


@router.post("/incoming-documents/{incoming_document_id}/resume", response_model=IncomingDocumentOut)
def post_resume_incoming_document(
    incoming_document_id: int,
    body: IncomingWorkflowCommentIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> IncomingDocumentOut:
    try:
        with engine.begin() as conn:
            updated = resume_incoming_document(
                conn,
                user=user,
                incoming_document_id=incoming_document_id,
                expected_version=body.expected_version,
                comment=body.comment or body.reason,
            )
        return _workflow_out(updated)
    except IncomingInformationError as exc:
        raise _map_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc) from exc


@router.post("/incoming-documents/{incoming_document_id}/change-deadline", response_model=IncomingDocumentOut)
def post_change_deadline_incoming_document(
    incoming_document_id: int,
    body: IncomingChangeDeadlineIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> IncomingDocumentOut:
    try:
        with engine.begin() as conn:
            updated = change_deadline_incoming_document(
                conn,
                user=user,
                incoming_document_id=incoming_document_id,
                expected_version=body.expected_version,
                new_due_date=body.new_due_date,
                reason=body.reason,
            )
        return _workflow_out(updated)
    except IncomingInformationError as exc:
        raise _map_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc) from exc


@router.post("/incoming-documents/{incoming_document_id}/resolve", response_model=IncomingDocumentOut)
def post_resolve_incoming_document(
    incoming_document_id: int,
    body: IncomingResolveIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> IncomingDocumentOut:
    try:
        with engine.begin() as conn:
            updated = resolve_incoming_document(
                conn,
                user=user,
                incoming_document_id=incoming_document_id,
                expected_version=body.expected_version,
                execution_result=body.execution_result,
                executed_at=body.executed_at,
            )
        return _workflow_out(updated)
    except IncomingInformationError as exc:
        raise _map_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc) from exc


@router.post("/incoming-documents/{incoming_document_id}/close", response_model=IncomingDocumentOut)
def post_close_incoming_document(
    incoming_document_id: int,
    body: IncomingCloseIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> IncomingDocumentOut:
    try:
        with engine.begin() as conn:
            updated = close_incoming_document(
                conn,
                user=user,
                incoming_document_id=incoming_document_id,
                expected_version=body.expected_version,
                control_decision=body.control_decision,
                comment=body.comment,
            )
        return _workflow_out(updated)
    except IncomingInformationError as exc:
        raise _map_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc) from exc


@router.post("/incoming-documents/{incoming_document_id}/reopen", response_model=IncomingDocumentOut)
def post_reopen_incoming_document(
    incoming_document_id: int,
    body: IncomingReopenIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> IncomingDocumentOut:
    try:
        with engine.begin() as conn:
            updated = reopen_incoming_document(
                conn,
                user=user,
                incoming_document_id=incoming_document_id,
                expected_version=body.expected_version,
                reason=body.reason,
            )
        return _workflow_out(updated)
    except IncomingInformationError as exc:
        raise _map_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc) from exc


@router.post("/incoming-documents/{incoming_document_id}/cancel", response_model=IncomingDocumentOut)
def post_cancel_incoming_document(
    incoming_document_id: int,
    body: IncomingCancelIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> IncomingDocumentOut:
    try:
        with engine.begin() as conn:
            updated = cancel_incoming_document(
                conn,
                user=user,
                incoming_document_id=incoming_document_id,
                expected_version=body.expected_version,
                reason=body.reason,
            )
        return _workflow_out(updated)
    except IncomingInformationError as exc:
        raise _map_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise as_http500(exc) from exc
