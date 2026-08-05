"""Incoming document attachment service."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.db.engine import engine as default_engine
from app.incoming_information.application.access_service import assert_can_read_document
from app.incoming_information.domain.attachment_validation import (
    storage_extension_for_content_type,
    validate_filename_extension_for_content_type,
    validate_incoming_attachment_bytes,
)
from app.incoming_information.domain.errors import (
    IncomingAttachmentNotFoundError,
    IncomingDocumentForbiddenError,
    IncomingDocumentNotFoundError,
    IncomingDocumentValidationError,
)
from app.incoming_information.domain.models import IncomingAttachmentSnapshot
from app.incoming_information.domain.status import AUDIT_ACTION_ATTACHMENT_ADDED, AUDIT_ACTION_ATTACHMENT_REMOVED
from app.incoming_information.infrastructure.attachment_storage import (
    cleanup_quarantine_artifact,
    delete_incoming_attachment,
    delete_staging_attachment,
    move_attachment_to_quarantine,
    promote_staging_attachment,
    read_incoming_attachment,
    read_staging_attachment,
    restore_attachment_from_quarantine,
)
from app.incoming_information.infrastructure.audit_repository import SqlAlchemyIncomingDocumentAuditRepository
from app.incoming_information.infrastructure.repository import SqlAlchemyIncomingDocumentRepository
from app.incoming_information.permissions import can_admin, can_register
from app.security.directory_scope import is_privileged

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AttachmentFileDeletionTarget:
    incoming_document_id: int
    file_id: str
    extension: str
    attachment_id: int
    quarantine_id: str | None = None


def _row_to_attachment(row: dict[str, Any]) -> IncomingAttachmentSnapshot:
    return IncomingAttachmentSnapshot(
        attachment_id=int(row["attachment_id"]),
        incoming_document_id=int(row["incoming_document_id"]),
        file_id=str(row["file_id"]),
        original_filename=str(row["original_filename"]),
        content_type=str(row["content_type"]),
        size_bytes=int(row["size_bytes"]),
        uploaded_by_user_id=int(row["uploaded_by_user_id"]),
        created_at=row["created_at"],
    )


def _get_attachment_row(conn: Connection, attachment_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT
                attachment_id,
                incoming_document_id,
                file_id,
                original_filename,
                content_type,
                size_bytes,
                uploaded_by_user_id,
                created_at
            FROM public.incoming_document_attachments
            WHERE attachment_id = :attachment_id
            LIMIT 1
            """
        ),
        {"attachment_id": int(attachment_id)},
    ).mappings().first()
    return dict(row) if row else None


def _storage_extension(snapshot: IncomingAttachmentSnapshot) -> str:
    return storage_extension_for_content_type(snapshot.content_type)


def _prepare_upload_metadata(
    *,
    content_type: str | None,
    original_filename: str,
    size_bytes: int,
    staging_id: str,
) -> tuple[str, str, str]:
    content = read_staging_attachment(staging_id)
    storage_extension = validate_incoming_attachment_bytes(content, content_type=content_type)
    safe_filename = str(original_filename or "attachment").strip() or "attachment"
    if len(safe_filename) > 255:
        safe_filename = safe_filename[:255]
    validate_filename_extension_for_content_type(safe_filename, content_type=content_type)
    file_id = uuid.uuid4().hex.lower()
    if len(file_id) != 32:
        raise IncomingDocumentValidationError("Attachment file id generation failed.")
    if int(size_bytes) != len(content):
        raise IncomingDocumentValidationError("Attachment size mismatch.")
    return file_id, storage_extension, safe_filename


def assert_can_mutate_attachments(user: dict[str, Any]) -> None:
    if is_privileged(user) or can_admin(user) or can_register(user):
        return
    raise IncomingDocumentForbiddenError("Attachment mutation permission required.")


def _insert_attachment_row_and_audit(
    conn: Connection,
    *,
    user: dict[str, Any],
    incoming_document_id: int,
    file_id: str,
    safe_filename: str,
    content_type: str | None,
    size_bytes: int,
) -> IncomingAttachmentSnapshot:
    assert_can_mutate_attachments(user)
    repo = SqlAlchemyIncomingDocumentRepository(conn)
    document = repo.get_by_id(incoming_document_id)
    if document is None:
        raise IncomingDocumentNotFoundError(f"Incoming document {incoming_document_id} not found.")
    assert_can_read_document(conn, user=user, document=document)

    row = conn.execute(
        text(
            """
            INSERT INTO public.incoming_document_attachments (
                incoming_document_id,
                storage_type,
                file_id,
                original_filename,
                content_type,
                size_bytes,
                uploaded_by_user_id
            )
            VALUES (
                :incoming_document_id,
                'LOCAL_SHARE',
                :file_id,
                :original_filename,
                :content_type,
                :size_bytes,
                :uploaded_by_user_id
            )
            RETURNING
                attachment_id,
                incoming_document_id,
                file_id,
                original_filename,
                content_type,
                size_bytes,
                uploaded_by_user_id,
                created_at
            """
        ),
        {
            "incoming_document_id": int(incoming_document_id),
            "file_id": file_id,
            "original_filename": safe_filename,
            "content_type": str(content_type or "application/octet-stream").split(";", 1)[0].lower(),
            "size_bytes": int(size_bytes),
            "uploaded_by_user_id": int(user["user_id"]),
        },
    ).mappings().one()
    snapshot = _row_to_attachment(dict(row))
    SqlAlchemyIncomingDocumentAuditRepository(conn).append(
        incoming_document_id=incoming_document_id,
        action=AUDIT_ACTION_ATTACHMENT_ADDED,
        actor_user_id=int(user["user_id"]),
        new_value=file_id,
        metadata={"original_filename": safe_filename, "attachment_id": snapshot.attachment_id},
    )
    return snapshot


def upload_attachment_from_staging(
    conn: Connection,
    *,
    user: dict[str, Any],
    incoming_document_id: int,
    staging_id: str,
    content_type: str | None,
    original_filename: str,
    size_bytes: int,
    file_id: str,
    extension: str,
    safe_filename: str,
) -> IncomingAttachmentSnapshot:
    """Insert attachment row and audit after promote. Caller owns file compensation."""
    return _insert_attachment_row_and_audit(
        conn,
        user=user,
        incoming_document_id=incoming_document_id,
        file_id=file_id,
        safe_filename=safe_filename,
        content_type=content_type,
        size_bytes=size_bytes,
    )


def execute_attachment_upload(
    db_engine: Engine,
    *,
    user: dict[str, Any],
    incoming_document_id: int,
    staging_id: str,
    content_type: str | None,
    original_filename: str,
    size_bytes: int,
) -> IncomingAttachmentSnapshot:
    """Compensating upload: staging → promote → INSERT/audit in one DB transaction."""
    file_id, extension, safe_filename = _prepare_upload_metadata(
        content_type=content_type,
        original_filename=original_filename,
        size_bytes=size_bytes,
        staging_id=staging_id,
    )
    permanent_created = False
    try:
        promote_staging_attachment(staging_id, incoming_document_id, file_id, extension)
        permanent_created = True
        with db_engine.begin() as conn:
            return upload_attachment_from_staging(
                conn,
                user=user,
                incoming_document_id=incoming_document_id,
                staging_id=staging_id,
                content_type=content_type,
                original_filename=original_filename,
                size_bytes=size_bytes,
                file_id=file_id,
                extension=extension,
                safe_filename=safe_filename,
            )
    except Exception:
        if permanent_created:
            delete_incoming_attachment(incoming_document_id, file_id, extension)
        else:
            delete_staging_attachment(staging_id)
        raise


def finalize_upload_from_staging(
    staging_id: str,
    incoming_document_id: int,
    file_id: str,
    extension: str,
) -> None:
    promote_staging_attachment(staging_id, incoming_document_id, file_id, extension)


def cleanup_staging_upload(staging_id: str) -> None:
    delete_staging_attachment(staging_id)


def list_attachments(
    conn: Connection,
    *,
    user: dict[str, Any],
    incoming_document_id: int,
) -> list[IncomingAttachmentSnapshot]:
    repo = SqlAlchemyIncomingDocumentRepository(conn)
    document = repo.get_by_id(incoming_document_id)
    if document is None:
        raise IncomingDocumentNotFoundError(f"Incoming document {incoming_document_id} not found.")
    assert_can_read_document(conn, user=user, document=document)
    rows = conn.execute(
        text(
            """
            SELECT
                attachment_id,
                incoming_document_id,
                file_id,
                original_filename,
                content_type,
                size_bytes,
                uploaded_by_user_id,
                created_at
            FROM public.incoming_document_attachments
            WHERE incoming_document_id = :incoming_document_id
            ORDER BY created_at ASC, attachment_id ASC
            """
        ),
        {"incoming_document_id": int(incoming_document_id)},
    ).mappings().all()
    return [_row_to_attachment(dict(row)) for row in rows]


def read_attachment_content(
    conn: Connection,
    *,
    user: dict[str, Any],
    attachment_id: int,
) -> tuple[IncomingAttachmentSnapshot, bytes]:
    row = _get_attachment_row(conn, attachment_id)
    if row is None:
        raise IncomingAttachmentNotFoundError(f"Attachment {attachment_id} not found.")
    snapshot = _row_to_attachment(row)
    repo = SqlAlchemyIncomingDocumentRepository(conn)
    document = repo.require_by_id(snapshot.incoming_document_id)
    assert_can_read_document(conn, user=user, document=document)
    ext = _storage_extension(snapshot)
    content = read_incoming_attachment(snapshot.incoming_document_id, snapshot.file_id, ext)
    if content is None:
        raise IncomingAttachmentNotFoundError("Attachment file is missing on storage.")
    return snapshot, content


def delete_attachment_db(
    conn: Connection,
    *,
    user: dict[str, Any],
    attachment_id: int,
) -> AttachmentFileDeletionTarget:
    """Delete DB row and audit only. Permanent file must already be in quarantine."""
    assert_can_mutate_attachments(user)
    row = _get_attachment_row(conn, attachment_id)
    if row is None:
        raise IncomingAttachmentNotFoundError(f"Attachment {attachment_id} not found.")
    snapshot = _row_to_attachment(row)
    repo = SqlAlchemyIncomingDocumentRepository(conn)
    document = repo.require_by_id(snapshot.incoming_document_id)
    assert_can_read_document(conn, user=user, document=document)
    ext = _storage_extension(snapshot)
    conn.execute(
        text("DELETE FROM public.incoming_document_attachments WHERE attachment_id = :attachment_id"),
        {"attachment_id": int(attachment_id)},
    )
    SqlAlchemyIncomingDocumentAuditRepository(conn).append(
        incoming_document_id=snapshot.incoming_document_id,
        action=AUDIT_ACTION_ATTACHMENT_REMOVED,
        actor_user_id=int(user["user_id"]),
        old_value=snapshot.file_id,
        metadata={"attachment_id": snapshot.attachment_id},
    )
    return AttachmentFileDeletionTarget(
        incoming_document_id=snapshot.incoming_document_id,
        file_id=snapshot.file_id,
        extension=ext,
        attachment_id=snapshot.attachment_id,
    )


def _best_effort_cleanup_quarantine_after_commit(quarantine_id: str) -> bool:
    """Post-commit quarantine cleanup. Never restores permanent; never raises."""
    if not str(quarantine_id or "").strip():
        return True
    try:
        cleaned = cleanup_quarantine_artifact(quarantine_id)
        if not cleaned:
            logger.warning(
                "Quarantine artifact remains after attachment delete commit: quarantine_id=%s",
                quarantine_id,
            )
        return cleaned
    except Exception:
        logger.exception(
            "Quarantine cleanup failed after successful attachment delete: quarantine_id=%s",
            quarantine_id,
        )
        return False


def execute_attachment_deletion(
    db_engine: Engine,
    *,
    user: dict[str, Any],
    attachment_id: int,
) -> AttachmentFileDeletionTarget | None:
    """Quarantine delete: move file → DELETE/audit → commit → best-effort quarantine cleanup."""
    with db_engine.connect() as conn:
        row = _get_attachment_row(conn, attachment_id)
    if row is None:
        raise IncomingAttachmentNotFoundError(f"Attachment {attachment_id} not found.")
    snapshot = _row_to_attachment(row)
    ext = _storage_extension(snapshot)

    try:
        quarantine_id = move_attachment_to_quarantine(
            snapshot.incoming_document_id,
            snapshot.file_id,
            ext,
        )
    except FileNotFoundError:
        with db_engine.begin() as conn:
            if _get_attachment_row(conn, attachment_id) is None:
                raise IncomingAttachmentNotFoundError(
                    f"Attachment {attachment_id} not found."
                ) from None
            target = delete_attachment_db(conn, user=user, attachment_id=attachment_id)
        return AttachmentFileDeletionTarget(
            incoming_document_id=target.incoming_document_id,
            file_id=target.file_id,
            extension=target.extension,
            attachment_id=target.attachment_id,
        )
    try:
        with db_engine.begin() as conn:
            target = delete_attachment_db(conn, user=user, attachment_id=attachment_id)
    except Exception:
        restore_attachment_from_quarantine(
            quarantine_id,
            snapshot.incoming_document_id,
            snapshot.file_id,
            ext,
        )
        raise

    _best_effort_cleanup_quarantine_after_commit(quarantine_id)
    return AttachmentFileDeletionTarget(
        incoming_document_id=target.incoming_document_id,
        file_id=target.file_id,
        extension=target.extension,
        attachment_id=target.attachment_id,
        quarantine_id=quarantine_id,
    )


def finalize_attachment_file_deletion(target: AttachmentFileDeletionTarget) -> None:
    if target.quarantine_id:
        cleanup_quarantine_artifact(target.quarantine_id)
        return
    delete_incoming_attachment(target.incoming_document_id, target.file_id, target.extension)


def upload_attachment_with_engine(
    *,
    user: dict[str, Any],
    db_engine: Engine | None = None,
    **kwargs: Any,
) -> IncomingAttachmentSnapshot:
    db = db_engine or default_engine
    return execute_attachment_upload(db, user=user, **kwargs)
