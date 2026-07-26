"""Canonicalize intake photo into person-scoped storage (WP-ADR061-001C)."""
from __future__ import annotations

import logging

from sqlalchemy.engine import Engine

from app.db.engine import engine as default_engine
from app.db.models.person_photos import MIME_TYPE_JPEG, SOURCE_KIND_INTAKE
from app.person_photos.application.event_builder import (
    build_person_photo_ppr_event,
    build_provenance_link_event,
)
from app.person_photos.domain.command_ids import intake_photo_command_id
from app.person_photos.domain.errors import (
    CanonicalFileIntegrityError,
    CanonicalFileMissingError,
    IntakePhotoUnavailableError,
    LedgerPersonMismatchError,
    PhotoCanonicalizationError,
)
from app.person_photos.domain.models import (
    CanonicalizeIntakePhotoRequest,
    CanonicalizePersonPhotoResult,
    MUTATION_KIND_INSERT,
    MUTATION_KIND_SUPERSEDE,
    RESULT_COMMITTED,
    RESULT_IDEMPOTENT_OK,
    RESULT_PROVENANCE_LINKED,
)
from app.person_photos.infrastructure.photo_storage import (
    PreparedCanonicalPhoto,
    delete_canonical_photo_file,
    prepare_canonical_photo_from_bytes,
    verify_canonical_photo_file,
)
from app.person_photos.infrastructure.repository import PersonPhotoRepository, utcnow
from app.personnel_intake.infrastructure.photo_storage import (
    normalize_intake_photo_file_id,
    read_intake_photo,
    ensure_intake_photo_storage_root,
)
from app.ppr.infrastructure.ppr_event_repository import SqlAlchemyPprEventRepository

logger = logging.getLogger(__name__)


def _discard_prepared_file_best_effort(storage_rel_path: str) -> None:
    try:
        delete_canonical_photo_file(storage_rel_path)
    except Exception:
        logger.exception(
            "Failed to delete prepared canonical photo file %s; "
            "orphan reconciliation may detect it.",
            storage_rel_path,
        )

def canonicalize_person_photo(
    request: CanonicalizeIntakePhotoRequest,
    *,
    engine: Engine = default_engine,
) -> CanonicalizePersonPhotoResult:
    intake_file_id = normalize_intake_photo_file_id(request.intake_photo_file_id)
    if not intake_file_id:
        raise IntakePhotoUnavailableError("Intake photo file id is empty.")

    command_id = intake_photo_command_id(request.application_id, intake_file_id)

    with engine.begin() as conn:
        repo = PersonPhotoRepository(conn)
        existing = _find_intake_ledger(
            repo,
            application_id=request.application_id,
            intake_photo_file_id=intake_file_id,
            command_id=command_id,
        )
        if existing is not None:
            repo.lock_person(request.person_id)
            return _replay_existing(
                repo=repo,
                existing=existing,
                request=request,
                command_id=command_id,
            )

    intake_bytes = read_intake_photo(request.application_id, intake_file_id)
    if intake_bytes is None:
        raise IntakePhotoUnavailableError(
            f"Intake photo missing for application_id={request.application_id} "
            f"file_id={intake_file_id}"
        )

    ensure_intake_photo_storage_root()
    try:
        prepared = prepare_canonical_photo_from_bytes(
            person_id=request.person_id,
            content=intake_bytes,
        )
    except Exception as exc:
        raise PhotoCanonicalizationError("Failed to prepare canonical photo file.") from exc

    result: CanonicalizePersonPhotoResult | None = None
    discard_prepared_after_commit = False
    try:
        with engine.begin() as conn:
            repo = PersonPhotoRepository(conn)
            events = SqlAlchemyPprEventRepository(conn)
            repo.lock_person(request.person_id)

            existing = _find_intake_ledger(
                repo,
                application_id=request.application_id,
                intake_photo_file_id=intake_file_id,
                command_id=command_id,
            )
            if existing is not None:
                result = _replay_existing(
                    repo=repo,
                    existing=existing,
                    request=request,
                    command_id=command_id,
                )
                discard_prepared_after_commit = True
            else:
                repo.assert_application_belongs_to_person(
                    application_id=request.application_id,
                    person_id=request.person_id,
                )

                active = repo.get_active_photo(request.person_id)
                if active is not None and active.checksum_sha256 == prepared.checksum_sha256:
                    result = _link_provenance_only(
                        repo=repo,
                        events=events,
                        request=request,
                        command_id=command_id,
                        target_photo=active,
                    )
                    discard_prepared_after_commit = True
                else:
                    result = _commit_new_canonical_photo(
                        repo=repo,
                        events=events,
                        request=request,
                        command_id=command_id,
                        intake_file_id=intake_file_id,
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


def _find_intake_ledger(
    repo: PersonPhotoRepository,
    *,
    application_id: int,
    intake_photo_file_id: str,
    command_id: str,
):
    return repo.find_intake_source(
        application_id=application_id,
        intake_photo_file_id=intake_photo_file_id,
    ) or repo.find_source_by_command_id(command_id)


def _commit_new_canonical_photo(
    *,
    repo: PersonPhotoRepository,
    events: SqlAlchemyPprEventRepository,
    request: CanonicalizeIntakePhotoRequest,
    command_id: str,
    intake_file_id: str,
    prepared: PreparedCanonicalPhoto,
    active,
) -> CanonicalizePersonPhotoResult:
    now = utcnow()
    prior_photo_id: int | None = None
    event_ids: list[int] = []
    if active is not None:
        prior_photo_id = active.person_photo_id
        repo.supersede_photo(active.person_photo_id, superseded_at=now)
        superseded_event = events.append(
            build_person_photo_ppr_event(
                person_id=request.person_id,
                person_photo_id=active.person_photo_id,
                actor_user_id=request.actor_user_id,
                command_id=command_id,
                correlation_id=request.correlation_id,
                mutation_kind=MUTATION_KIND_SUPERSEDE,
                checksum_sha256=active.checksum_sha256,
                canonicalization_mode=request.canonicalization_mode,
                source_application_id=request.application_id,
                source_intake_photo_file_id=intake_file_id,
                prior_active_person_photo_id=active.person_photo_id,
            )
        )
        event_ids.append(int(superseded_event.event_id))

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
        source_kind=SOURCE_KIND_INTAKE,
        canonicalization_mode=request.canonicalization_mode,
        source_application_id=request.application_id,
        source_intake_photo_file_id=intake_file_id,
        command_id=command_id,
        correlation_id=request.correlation_id,
        application_status_snapshot=request.application_status_snapshot,
        canonicalized_by_user_id=request.actor_user_id,
    )
    added_event = events.append(
        build_person_photo_ppr_event(
            person_id=request.person_id,
            person_photo_id=person_photo_id,
            actor_user_id=request.actor_user_id,
            command_id=command_id,
            correlation_id=request.correlation_id,
            mutation_kind=MUTATION_KIND_INSERT,
            checksum_sha256=prepared.checksum_sha256,
            canonicalization_mode=request.canonicalization_mode,
            source_application_id=request.application_id,
            source_intake_photo_file_id=intake_file_id,
            prior_active_person_photo_id=prior_photo_id,
        )
    )
    event_ids.append(int(added_event.event_id))
    return CanonicalizePersonPhotoResult(
        status=RESULT_COMMITTED,
        person_photo_id=person_photo_id,
        person_photo_source_id=source_id,
        command_id=command_id,
        ppr_event_ids=tuple(event_ids),
        storage_rel_path=prepared.storage_rel_path,
    )


def _validate_replay(
    *,
    repo: PersonPhotoRepository,
    existing_person_photo_id: int,
    expected_person_id: int,
) -> None:
    photo = repo.get_photo(existing_person_photo_id)
    if photo is None:
        raise CanonicalFileMissingError(
            f"Ledger references missing person_photo_id={existing_person_photo_id}"
        )
    if photo.person_id != expected_person_id:
        raise LedgerPersonMismatchError(
            f"Ledger person_id={photo.person_id} != expected={expected_person_id}"
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


def _replay_existing(
    *,
    repo: PersonPhotoRepository,
    existing,
    request: CanonicalizeIntakePhotoRequest,
    command_id: str,
) -> CanonicalizePersonPhotoResult:
    _validate_replay(
        repo=repo,
        existing_person_photo_id=existing.person_photo_id,
        expected_person_id=request.person_id,
    )
    return CanonicalizePersonPhotoResult(
        status=RESULT_IDEMPOTENT_OK,
        person_photo_id=existing.person_photo_id,
        person_photo_source_id=existing.person_photo_source_id,
        command_id=command_id,
        ppr_event_ids=(),
        storage_rel_path=repo.get_photo(existing.person_photo_id).storage_rel_path,
    )


def _link_provenance_only(
    *,
    repo: PersonPhotoRepository,
    events: SqlAlchemyPprEventRepository,
    request: CanonicalizeIntakePhotoRequest,
    command_id: str,
    target_photo,
) -> CanonicalizePersonPhotoResult:
    _validate_replay(
        repo=repo,
        existing_person_photo_id=target_photo.person_photo_id,
        expected_person_id=request.person_id,
    )
    intake_file_id = normalize_intake_photo_file_id(request.intake_photo_file_id)
    source_id = repo.insert_source(
        person_photo_id=target_photo.person_photo_id,
        person_id=request.person_id,
        source_kind=SOURCE_KIND_INTAKE,
        canonicalization_mode=request.canonicalization_mode,
        source_application_id=request.application_id,
        source_intake_photo_file_id=intake_file_id,
        command_id=command_id,
        correlation_id=request.correlation_id,
        application_status_snapshot=request.application_status_snapshot,
        canonicalized_by_user_id=request.actor_user_id,
    )
    link_event = events.append(
        build_provenance_link_event(
            person_id=request.person_id,
            person_photo_id=target_photo.person_photo_id,
            actor_user_id=request.actor_user_id,
            command_id=command_id,
            correlation_id=request.correlation_id,
            checksum_sha256=target_photo.checksum_sha256,
            canonicalization_mode=request.canonicalization_mode,
            source_application_id=request.application_id,
            source_intake_photo_file_id=intake_file_id,
        )
    )
    return CanonicalizePersonPhotoResult(
        status=RESULT_PROVENANCE_LINKED,
        person_photo_id=target_photo.person_photo_id,
        person_photo_source_id=source_id,
        command_id=command_id,
        ppr_event_ids=(int(link_event.event_id),),
        storage_rel_path=target_photo.storage_rel_path,
    )
