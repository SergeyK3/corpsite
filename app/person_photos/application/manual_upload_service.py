"""Register trusted manual Person photos through the canonical photo ledger."""
from __future__ import annotations

import logging

from sqlalchemy.engine import Engine

from app.db.engine import engine as default_engine
from app.db.models.person_photos import (
    CANONICALIZATION_MODE_TRANSFER,
    MIME_TYPE_JPEG,
    SOURCE_KIND_MANUAL_UPLOAD,
)
from app.person_photos.application.event_builder import (
    build_person_photo_ppr_event,
    build_provenance_link_event,
)
from app.person_photos.domain.command_ids import manual_photo_command_id
from app.person_photos.domain.errors import (
    CanonicalFileIntegrityError,
    CanonicalFileMissingError,
    LedgerPersonMismatchError,
    PhotoReplacementRequiresApprovalError,
)
from app.person_photos.domain.models import (
    CanonicalizePersonPhotoResult,
    MUTATION_KIND_INSERT,
    MUTATION_KIND_SUPERSEDE,
    RESULT_COMMITTED,
    RESULT_IDEMPOTENT_OK,
    RESULT_PROVENANCE_LINKED,
    RegisterManualPersonPhotoRequest,
)
from app.person_photos.infrastructure.photo_storage import (
    PreparedCanonicalPhoto,
    delete_canonical_photo_file,
    prepare_canonical_photo_from_bytes,
    verify_canonical_photo_file,
)
from app.person_photos.infrastructure.repository import PersonPhotoRepository, utcnow
from app.ppr.infrastructure.ppr_event_repository import SqlAlchemyPprEventRepository

logger = logging.getLogger(__name__)


def _discard_prepared_file_best_effort(storage_rel_path: str) -> None:
    try:
        delete_canonical_photo_file(storage_rel_path)
    except Exception:
        logger.exception("Failed to discard uncommitted manual Person photo file.")


def _validate_existing_photo(repo: PersonPhotoRepository, *, person_photo_id: int, person_id: int):
    photo = repo.get_photo(person_photo_id)
    if photo is None:
        raise CanonicalFileMissingError(
            f"Ledger references missing person_photo_id={person_photo_id}"
        )
    if photo.person_id != person_id:
        raise LedgerPersonMismatchError(
            f"Ledger person_id={photo.person_id} != expected={person_id}"
        )
    try:
        verify_canonical_photo_file(
            photo.storage_rel_path,
            expected_checksum_sha256=photo.checksum_sha256,
        )
    except FileNotFoundError as exc:
        raise CanonicalFileMissingError(photo.storage_rel_path) from exc
    except ValueError as exc:
        raise CanonicalFileIntegrityError(str(exc)) from exc
    return photo


def register_manual_person_photo(
    request: RegisterManualPersonPhotoRequest,
    *,
    engine: Engine = default_engine,
) -> CanonicalizePersonPhotoResult:
    """Register a validated JPEG as a manual-upload canonical Person photo."""
    if request.person_id < 1:
        raise ValueError("person_id must be positive.")
    if request.actor_user_id < 1:
        raise ValueError("actor_user_id must be positive.")
    command_id = manual_photo_command_id(request.request_id)

    with engine.begin() as conn:
        repo = PersonPhotoRepository(conn)
        existing = repo.find_source_by_command_id(command_id)
        if existing is not None:
            repo.lock_person(request.person_id)
            photo = _validate_existing_photo(
                repo,
                person_photo_id=existing.person_photo_id,
                person_id=request.person_id,
            )
            return CanonicalizePersonPhotoResult(
                status=RESULT_IDEMPOTENT_OK,
                person_photo_id=photo.person_photo_id,
                person_photo_source_id=existing.person_photo_source_id,
                command_id=command_id,
                ppr_event_ids=(),
                storage_rel_path=photo.storage_rel_path,
            )

    prepared = prepare_canonical_photo_from_bytes(
        person_id=request.person_id,
        content=request.jpeg_content,
    )
    result: CanonicalizePersonPhotoResult | None = None
    discard_prepared_after_commit = False
    try:
        with engine.begin() as conn:
            repo = PersonPhotoRepository(conn)
            events = SqlAlchemyPprEventRepository(conn)
            repo.lock_person(request.person_id)

            existing = repo.find_source_by_command_id(command_id)
            if existing is not None:
                photo = _validate_existing_photo(
                    repo,
                    person_photo_id=existing.person_photo_id,
                    person_id=request.person_id,
                )
                result = CanonicalizePersonPhotoResult(
                    status=RESULT_IDEMPOTENT_OK,
                    person_photo_id=photo.person_photo_id,
                    person_photo_source_id=existing.person_photo_source_id,
                    command_id=command_id,
                    ppr_event_ids=(),
                    storage_rel_path=photo.storage_rel_path,
                )
                discard_prepared_after_commit = True
            else:
                active = repo.get_active_photo(request.person_id)
                if active is not None and active.checksum_sha256 == prepared.checksum_sha256:
                    result = _link_manual_provenance(
                        repo=repo,
                        events=events,
                        request=request,
                        command_id=command_id,
                        target_photo=active,
                    )
                    discard_prepared_after_commit = True
                else:
                    if active is not None and not request.allow_replace:
                        raise PhotoReplacementRequiresApprovalError(
                            "A different active Person photo already exists."
                        )
                    result = _commit_manual_photo(
                        repo=repo,
                        events=events,
                        request=request,
                        command_id=command_id,
                        prepared=prepared,
                        active=active,
                    )

        if discard_prepared_after_commit:
            _discard_prepared_file_best_effort(prepared.storage_rel_path)
        prepared = None
        assert result is not None
        return result
    except Exception:
        if prepared is not None:
            _discard_prepared_file_best_effort(prepared.storage_rel_path)
        raise


def _commit_manual_photo(
    *,
    repo: PersonPhotoRepository,
    events: SqlAlchemyPprEventRepository,
    request: RegisterManualPersonPhotoRequest,
    command_id: str,
    prepared: PreparedCanonicalPhoto,
    active,
) -> CanonicalizePersonPhotoResult:
    event_ids: list[int] = []
    prior_photo_id: int | None = None
    if active is not None:
        prior_photo_id = active.person_photo_id
        repo.supersede_photo(active.person_photo_id, superseded_at=utcnow())
        event = events.append(
            build_person_photo_ppr_event(
                person_id=request.person_id,
                person_photo_id=active.person_photo_id,
                actor_user_id=request.actor_user_id,
                command_id=command_id,
                correlation_id=request.correlation_id,
                mutation_kind=MUTATION_KIND_SUPERSEDE,
                checksum_sha256=active.checksum_sha256,
                source_kind=SOURCE_KIND_MANUAL_UPLOAD,
                canonicalization_mode=CANONICALIZATION_MODE_TRANSFER,
                source_application_id=None,
                source_intake_photo_file_id=None,
                prior_active_person_photo_id=active.person_photo_id,
            )
        )
        event_ids.append(int(event.event_id))

    person_photo_id = repo.insert_photo(
        person_id=request.person_id,
        file_id=prepared.file_id,
        storage_rel_path=prepared.storage_rel_path,
        mime_type=MIME_TYPE_JPEG,
        byte_size=prepared.byte_size,
        checksum_sha256=prepared.checksum_sha256,
        is_active=True,
        superseded_at=None,
        uploaded_by_user_id=request.actor_user_id,
    )
    source_id = repo.insert_source(
        person_photo_id=person_photo_id,
        person_id=request.person_id,
        source_kind=SOURCE_KIND_MANUAL_UPLOAD,
        canonicalization_mode=CANONICALIZATION_MODE_TRANSFER,
        source_application_id=None,
        source_intake_photo_file_id=None,
        command_id=command_id,
        correlation_id=request.correlation_id,
        application_status_snapshot=None,
        canonicalized_by_user_id=request.actor_user_id,
    )
    event = events.append(
        build_person_photo_ppr_event(
            person_id=request.person_id,
            person_photo_id=person_photo_id,
            actor_user_id=request.actor_user_id,
            command_id=command_id,
            correlation_id=request.correlation_id,
            mutation_kind=MUTATION_KIND_INSERT,
            checksum_sha256=prepared.checksum_sha256,
            source_kind=SOURCE_KIND_MANUAL_UPLOAD,
            canonicalization_mode=CANONICALIZATION_MODE_TRANSFER,
            source_application_id=None,
            source_intake_photo_file_id=None,
            prior_active_person_photo_id=prior_photo_id,
        )
    )
    event_ids.append(int(event.event_id))
    return CanonicalizePersonPhotoResult(
        status=RESULT_COMMITTED,
        person_photo_id=person_photo_id,
        person_photo_source_id=source_id,
        command_id=command_id,
        ppr_event_ids=tuple(event_ids),
        storage_rel_path=prepared.storage_rel_path,
    )


def _link_manual_provenance(
    *,
    repo: PersonPhotoRepository,
    events: SqlAlchemyPprEventRepository,
    request: RegisterManualPersonPhotoRequest,
    command_id: str,
    target_photo,
) -> CanonicalizePersonPhotoResult:
    _validate_existing_photo(
        repo,
        person_photo_id=target_photo.person_photo_id,
        person_id=request.person_id,
    )
    source_id = repo.insert_source(
        person_photo_id=target_photo.person_photo_id,
        person_id=request.person_id,
        source_kind=SOURCE_KIND_MANUAL_UPLOAD,
        canonicalization_mode=CANONICALIZATION_MODE_TRANSFER,
        source_application_id=None,
        source_intake_photo_file_id=None,
        command_id=command_id,
        correlation_id=request.correlation_id,
        application_status_snapshot=None,
        canonicalized_by_user_id=request.actor_user_id,
    )
    event = events.append(
        build_provenance_link_event(
            person_id=request.person_id,
            person_photo_id=target_photo.person_photo_id,
            actor_user_id=request.actor_user_id,
            command_id=command_id,
            correlation_id=request.correlation_id,
            checksum_sha256=target_photo.checksum_sha256,
            canonicalization_mode=CANONICALIZATION_MODE_TRANSFER,
            source_application_id=None,
            source_intake_photo_file_id=None,
            source_kind=SOURCE_KIND_MANUAL_UPLOAD,
        )
    )
    return CanonicalizePersonPhotoResult(
        status=RESULT_PROVENANCE_LINKED,
        person_photo_id=target_photo.person_photo_id,
        person_photo_source_id=source_id,
        command_id=command_id,
        ppr_event_ids=(int(event.event_id),),
        storage_rel_path=target_photo.storage_rel_path,
    )
