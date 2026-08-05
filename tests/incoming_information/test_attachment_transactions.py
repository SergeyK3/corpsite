# tests/incoming_information/test_attachment_transactions.py
from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.engine.base import RootTransaction

from app.db.engine import engine
from app.incoming_information.application.attachment_service import (
    execute_attachment_deletion,
    execute_attachment_upload,
)
from app.incoming_information.domain.status import (
    AUDIT_ACTION_ATTACHMENT_ADDED,
    AUDIT_ACTION_ATTACHMENT_REMOVED,
)
from app.incoming_information.infrastructure.attachment_storage import (
    cleanup_quarantine_artifact,
    incoming_attachment_path,
    list_orphan_paths_in_root,
    list_quarantine_artifacts_in_root,
    quarantine_artifact_path,
    read_incoming_attachment,
    staging_attachment_path,
    write_staging_attachment,
)
from app.incoming_information.infrastructure.audit_repository import SqlAlchemyIncomingDocumentAuditRepository
from tests.incoming_information.conftest import build_user_dict, register_test_document

_ORIGINAL_CONNECTION_EXECUTE = Connection.execute


def _attachment_count(document_id: int) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.incoming_document_attachments
                    WHERE incoming_document_id = :document_id
                    """
                ),
                {"document_id": document_id},
            ).one()[0]
        )


def _audit_count(document_id: int, *, action: str) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.incoming_document_audit
                    WHERE incoming_document_id = :document_id
                      AND action = :action
                    """
                ),
                {"document_id": document_id, "action": action},
            ).one()[0]
        )


def _upload_fixture(client, seed, headers, *, staging_id: str = "a" * 32):
    document = register_test_document(client, seed, headers)
    document_id = int(document["incoming_document_id"])
    content = b"%PDF-1.4 fixture"
    write_staging_attachment(staging_id, content)
    user = build_user_dict(int(seed["executor_user_id"]))
    return document_id, staging_id, content, user


def _uploaded_attachment(client, seed, headers, *, staging_id: str):
    document_id, _staging_id, content, user = _upload_fixture(
        client,
        seed,
        headers,
        staging_id=staging_id,
    )
    snapshot = execute_attachment_upload(
        engine,
        user=user,
        incoming_document_id=document_id,
        staging_id=staging_id,
        content_type="application/pdf",
        original_filename="report.pdf",
        size_bytes=len(content),
    )
    return document_id, snapshot, "pdf", content, user


def _assert_no_upload_artifacts(
    document_id: int,
    *,
    staging_id: str,
    file_id: str | None = None,
    ext: str = "pdf",
) -> None:
    assert _attachment_count(document_id) == 0
    assert _audit_count(document_id, action=AUDIT_ACTION_ATTACHMENT_ADDED) == 0
    assert not staging_attachment_path(staging_id).is_file()
    assert not list_orphan_paths_in_root()
    if file_id is not None:
        assert read_incoming_attachment(document_id, file_id, ext) is None


def _patch_connection_execute_for_sql(fragment: str, *, error_message: str):
    def patched_execute(self, statement, *args, **kwargs):
        if fragment in str(statement):
            raise RuntimeError(error_message)
        return _ORIGINAL_CONNECTION_EXECUTE(self, statement, *args, **kwargs)

    return patch.object(Connection, "execute", patched_execute)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_upload_promote_failure_before_commit(client, seed, ii_register_headers, _incoming_info_storage_root):
    document_id, staging_id, content, user = _upload_fixture(client, seed, ii_register_headers)

    with patch(
        "app.incoming_information.application.attachment_service.promote_staging_attachment",
        side_effect=OSError("promote failed"),
    ):
        with pytest.raises(OSError, match="promote failed"):
            execute_attachment_upload(
                engine,
                user=user,
                incoming_document_id=document_id,
                staging_id=staging_id,
                content_type="application/pdf",
                original_filename="report.pdf",
                size_bytes=len(content),
            )

    _assert_no_upload_artifacts(document_id, staging_id=staging_id)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_upload_db_commit_failure_after_promote(client, seed, ii_register_headers, _incoming_info_storage_root):
    document_id, staging_id, content, user = _upload_fixture(client, seed, ii_register_headers)

    def failing_commit(self, _to_root: bool = False):
        raise RuntimeError("commit failed before persistence")

    with patch.object(RootTransaction, "commit", failing_commit):
        with pytest.raises(RuntimeError, match="commit failed before persistence"):
            execute_attachment_upload(
                engine,
                user=user,
                incoming_document_id=document_id,
                staging_id=staging_id,
                content_type="application/pdf",
                original_filename="report.pdf",
                size_bytes=len(content),
            )

    _assert_no_upload_artifacts(document_id, staging_id=staging_id)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_upload_sql_insert_failure_rolls_back(client, seed, ii_register_headers, _incoming_info_storage_root):
    document_id, staging_id, content, user = _upload_fixture(client, seed, ii_register_headers)

    with _patch_connection_execute_for_sql(
        "INSERT INTO public.incoming_document_attachments",
        error_message="insert sql failed",
    ):
        with pytest.raises(RuntimeError, match="insert sql failed"):
            execute_attachment_upload(
                engine,
                user=user,
                incoming_document_id=document_id,
                staging_id=staging_id,
                content_type="application/pdf",
                original_filename="report.pdf",
                size_bytes=len(content),
            )

    _assert_no_upload_artifacts(document_id, staging_id=staging_id)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_upload_audit_failure_rolls_back(client, seed, ii_register_headers, _incoming_info_storage_root):
    document_id, staging_id, content, user = _upload_fixture(client, seed, ii_register_headers)

    with patch.object(
        SqlAlchemyIncomingDocumentAuditRepository,
        "append",
        side_effect=RuntimeError("audit failed"),
    ):
        with pytest.raises(RuntimeError, match="audit failed"):
            execute_attachment_upload(
                engine,
                user=user,
                incoming_document_id=document_id,
                staging_id=staging_id,
                content_type="application/pdf",
                original_filename="report.pdf",
                size_bytes=len(content),
            )

    _assert_no_upload_artifacts(document_id, staging_id=staging_id)


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_upload_happy_path_no_staging_orphans(client, seed, ii_register_headers, _incoming_info_storage_root):
    document_id, snapshot, ext, content, _user = _uploaded_attachment(
        client,
        seed,
        ii_register_headers,
        staging_id="b" * 32,
    )
    assert not list_orphan_paths_in_root()
    assert read_incoming_attachment(document_id, snapshot.file_id, ext) == content
    assert _attachment_count(document_id) == 1
    assert _audit_count(document_id, action=AUDIT_ACTION_ATTACHMENT_ADDED) == 1


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_delete_quarantine_move_failure(client, seed, ii_register_headers, _incoming_info_storage_root):
    document_id, snapshot, ext, content, user = _uploaded_attachment(
        client,
        seed,
        ii_register_headers,
        staging_id="c" * 32,
    )
    permanent_path = incoming_attachment_path(document_id, snapshot.file_id, ext)
    assert permanent_path.is_file()

    with patch(
        "app.incoming_information.application.attachment_service.move_attachment_to_quarantine",
        side_effect=OSError("quarantine move failed"),
    ):
        with pytest.raises(OSError, match="quarantine move failed"):
            execute_attachment_deletion(engine, user=user, attachment_id=snapshot.attachment_id)

    assert permanent_path.is_file()
    assert read_incoming_attachment(document_id, snapshot.file_id, ext) == content
    assert _attachment_count(document_id) == 1
    assert _audit_count(document_id, action=AUDIT_ACTION_ATTACHMENT_REMOVED) == 0
    assert not list_quarantine_artifacts_in_root()


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_delete_sql_delete_failure_restores_permanent(client, seed, ii_register_headers, _incoming_info_storage_root):
    document_id, snapshot, ext, content, user = _uploaded_attachment(
        client,
        seed,
        ii_register_headers,
        staging_id="d" * 32,
    )
    permanent_path = incoming_attachment_path(document_id, snapshot.file_id, ext)
    assert permanent_path.is_file()

    with _patch_connection_execute_for_sql(
        "DELETE FROM public.incoming_document_attachments",
        error_message="delete sql failed",
    ):
        with pytest.raises(RuntimeError, match="delete sql failed"):
            execute_attachment_deletion(engine, user=user, attachment_id=snapshot.attachment_id)

    assert permanent_path.is_file()
    assert read_incoming_attachment(document_id, snapshot.file_id, ext) == content
    assert _attachment_count(document_id) == 1
    assert _audit_count(document_id, action=AUDIT_ACTION_ATTACHMENT_REMOVED) == 0
    assert not list_quarantine_artifacts_in_root()


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_delete_audit_failure_restores_permanent_via_service(
    client,
    seed,
    ii_register_headers,
    _incoming_info_storage_root,
):
    document_id, snapshot, ext, content, user = _uploaded_attachment(
        client,
        seed,
        ii_register_headers,
        staging_id="e" * 32,
    )

    with patch.object(
        SqlAlchemyIncomingDocumentAuditRepository,
        "append",
        side_effect=RuntimeError("audit failed"),
    ):
        with pytest.raises(RuntimeError, match="audit failed"):
            execute_attachment_deletion(engine, user=user, attachment_id=snapshot.attachment_id)

    permanent_path = incoming_attachment_path(document_id, snapshot.file_id, ext)
    assert permanent_path.is_file()
    assert read_incoming_attachment(document_id, snapshot.file_id, ext) == content
    assert _attachment_count(document_id) == 1
    assert _audit_count(document_id, action=AUDIT_ACTION_ATTACHMENT_REMOVED) == 0
    assert not list_quarantine_artifacts_in_root()


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_delete_quarantine_cleanup_raises_still_succeeds(client, seed, ii_register_headers, _incoming_info_storage_root):
    document_id, snapshot, ext, _content, user = _uploaded_attachment(
        client,
        seed,
        ii_register_headers,
        staging_id="f" * 32,
    )

    with patch(
        "app.incoming_information.application.attachment_service.cleanup_quarantine_artifact",
        side_effect=RuntimeError("cleanup exploded"),
    ):
        result = execute_attachment_deletion(engine, user=user, attachment_id=snapshot.attachment_id)

    assert result is not None
    assert result.quarantine_id is not None
    assert quarantine_artifact_path(result.quarantine_id).is_file()
    assert read_incoming_attachment(document_id, snapshot.file_id, ext) is None
    assert _attachment_count(document_id) == 0
    assert _audit_count(document_id, action=AUDIT_ACTION_ATTACHMENT_REMOVED) == 1

    assert cleanup_quarantine_artifact(result.quarantine_id) is True
    assert not quarantine_artifact_path(result.quarantine_id).is_file()


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_delete_quarantine_cleanup_returns_false_still_succeeds(
    client,
    seed,
    ii_register_headers,
    _incoming_info_storage_root,
):
    document_id, snapshot, ext, _content, user = _uploaded_attachment(
        client,
        seed,
        ii_register_headers,
        staging_id="0123456789abcdef0123456789abcdef",
    )

    with patch(
        "app.incoming_information.application.attachment_service.cleanup_quarantine_artifact",
        return_value=False,
    ):
        result = execute_attachment_deletion(engine, user=user, attachment_id=snapshot.attachment_id)

    assert result is not None
    assert result.quarantine_id is not None
    assert quarantine_artifact_path(result.quarantine_id).is_file()
    assert read_incoming_attachment(document_id, snapshot.file_id, ext) is None
    assert _attachment_count(document_id) == 0
    assert _audit_count(document_id, action=AUDIT_ACTION_ATTACHMENT_REMOVED) == 1


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_delete_quarantine_cleanup_idempotent_retry(client, seed, ii_register_headers, _incoming_info_storage_root):
    document_id, snapshot, ext, _content, user = _uploaded_attachment(
        client,
        seed,
        ii_register_headers,
        staging_id="11111111111111111111111111111111",
    )

    with patch(
        "app.incoming_information.application.attachment_service.cleanup_quarantine_artifact",
        return_value=False,
    ):
        result = execute_attachment_deletion(engine, user=user, attachment_id=snapshot.attachment_id)

    assert result is not None
    quarantine_id = result.quarantine_id
    assert quarantine_id is not None
    assert cleanup_quarantine_artifact(quarantine_id) is True
    assert not quarantine_artifact_path(quarantine_id).is_file()
    assert cleanup_quarantine_artifact(quarantine_id) is True


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_delete_happy_path_removes_db_and_file(client, seed, ii_register_headers, _incoming_info_storage_root):
    document_id, snapshot, ext, _content, user = _uploaded_attachment(
        client,
        seed,
        ii_register_headers,
        staging_id="22222222222222222222222222222222",
    )

    result = execute_attachment_deletion(engine, user=user, attachment_id=snapshot.attachment_id)

    assert read_incoming_attachment(document_id, snapshot.file_id, ext) is None
    assert _attachment_count(document_id) == 0
    assert _audit_count(document_id, action=AUDIT_ACTION_ATTACHMENT_REMOVED) == 1
    assert not list_orphan_paths_in_root()
    if result and result.quarantine_id:
        assert not quarantine_artifact_path(result.quarantine_id).is_file()
