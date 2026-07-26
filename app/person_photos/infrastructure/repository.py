"""Repository for person_photos and person_photo_sources."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.models.person_photos import SOURCE_KIND_INTAKE
from app.person_photos.domain.errors import (
    ApplicationNotFoundError,
    ApplicationPersonMismatchError,
)
from app.person_photos.domain.models import PersonPhotoRow, PersonPhotoSourceRow


class PersonPhotoRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def assert_application_belongs_to_person(
        self,
        *,
        application_id: int,
        person_id: int,
    ) -> None:
        row = self._conn.execute(
            text(
                """
                SELECT person_id
                FROM public.personnel_applications
                WHERE application_id = :application_id
                """
            ),
            {"application_id": application_id},
        ).scalar_one_or_none()
        if row is None:
            raise ApplicationNotFoundError(
                f"Application {application_id} not found."
            )
        if int(row) != int(person_id):
            raise ApplicationPersonMismatchError(
                f"Application {application_id} does not belong to person_id={person_id}."
            )

    def lock_person(self, person_id: int) -> None:
        row = self._conn.execute(
            text(
                """
                SELECT person_id
                FROM public.persons
                WHERE person_id = :person_id
                FOR UPDATE
                """
            ),
            {"person_id": person_id},
        ).first()
        if row is None:
            raise LookupError(f"Person not found: {person_id}")

    def get_active_photo(self, person_id: int) -> PersonPhotoRow | None:
        row = self._conn.execute(
            text(
                """
                SELECT person_photo_id, person_id, file_id, storage_rel_path, mime_type,
                       byte_size, checksum_sha256, is_active, superseded_at
                FROM public.person_photos
                WHERE person_id = :person_id
                  AND is_active = TRUE
                LIMIT 1
                """
            ),
            {"person_id": person_id},
        ).mappings().first()
        return _map_photo(row) if row else None

    def get_photo(self, person_photo_id: int) -> PersonPhotoRow | None:
        row = self._conn.execute(
            text(
                """
                SELECT person_photo_id, person_id, file_id, storage_rel_path, mime_type,
                       byte_size, checksum_sha256, is_active, superseded_at
                FROM public.person_photos
                WHERE person_photo_id = :person_photo_id
                """
            ),
            {"person_photo_id": person_photo_id},
        ).mappings().first()
        return _map_photo(row) if row else None

    def find_intake_source(
        self,
        *,
        application_id: int,
        intake_photo_file_id: str,
    ) -> PersonPhotoSourceRow | None:
        row = self._conn.execute(
            text(
                """
                SELECT person_photo_source_id, person_photo_id, person_id, source_kind,
                       canonicalization_mode, source_application_id,
                       source_intake_photo_file_id, command_id
                FROM public.person_photo_sources
                WHERE source_kind = :source_kind
                  AND source_application_id = :application_id
                  AND source_intake_photo_file_id = :intake_photo_file_id
                """
            ),
            {
                "source_kind": SOURCE_KIND_INTAKE,
                "application_id": application_id,
                "intake_photo_file_id": intake_photo_file_id,
            },
        ).mappings().first()
        return _map_source(row) if row else None

    def find_source_by_command_id(self, command_id: str) -> PersonPhotoSourceRow | None:
        row = self._conn.execute(
            text(
                """
                SELECT person_photo_source_id, person_photo_id, person_id, source_kind,
                       canonicalization_mode, source_application_id,
                       source_intake_photo_file_id, command_id
                FROM public.person_photo_sources
                WHERE command_id = :command_id
                """
            ),
            {"command_id": command_id},
        ).mappings().first()
        return _map_source(row) if row else None

    def insert_photo(
        self,
        *,
        person_id: int,
        file_id: str,
        storage_rel_path: str,
        mime_type: str,
        byte_size: int,
        checksum_sha256: str,
        is_active: bool,
        superseded_at: datetime | None,
        uploaded_by_user_id: int | None,
    ) -> int:
        row = self._conn.execute(
            text(
                """
                INSERT INTO public.person_photos (
                    person_id, file_id, storage_rel_path, mime_type, byte_size,
                    checksum_sha256, is_active, superseded_at, uploaded_by_user_id
                ) VALUES (
                    :person_id, :file_id, :storage_rel_path, :mime_type, :byte_size,
                    :checksum_sha256, :is_active, :superseded_at, :uploaded_by_user_id
                )
                RETURNING person_photo_id
                """
            ),
            {
                "person_id": person_id,
                "file_id": file_id,
                "storage_rel_path": storage_rel_path,
                "mime_type": mime_type,
                "byte_size": byte_size,
                "checksum_sha256": checksum_sha256,
                "is_active": is_active,
                "superseded_at": superseded_at,
                "uploaded_by_user_id": uploaded_by_user_id,
            },
        ).mappings().one()
        return int(row["person_photo_id"])

    def supersede_photo(self, person_photo_id: int, *, superseded_at: datetime) -> None:
        self._conn.execute(
            text(
                """
                UPDATE public.person_photos
                SET is_active = FALSE, superseded_at = :superseded_at
                WHERE person_photo_id = :person_photo_id
                """
            ),
            {"person_photo_id": person_photo_id, "superseded_at": superseded_at},
        )

    def insert_source(
        self,
        *,
        person_photo_id: int,
        person_id: int,
        source_kind: str,
        canonicalization_mode: str,
        source_application_id: int | None,
        source_intake_photo_file_id: str | None,
        command_id: str,
        correlation_id: str | None,
        application_status_snapshot: str | None,
        canonicalized_by_user_id: int | None,
    ) -> int:
        row = self._conn.execute(
            text(
                """
                INSERT INTO public.person_photo_sources (
                    person_photo_id, person_id, source_kind, canonicalization_mode,
                    source_application_id, source_intake_photo_file_id, command_id,
                    correlation_id, application_status_snapshot, canonicalized_by_user_id
                ) VALUES (
                    :person_photo_id, :person_id, :source_kind, :canonicalization_mode,
                    :source_application_id, :source_intake_photo_file_id, :command_id,
                    :correlation_id, :application_status_snapshot, :canonicalized_by_user_id
                )
                RETURNING person_photo_source_id
                """
            ),
            {
                "person_photo_id": person_photo_id,
                "person_id": person_id,
                "source_kind": source_kind,
                "canonicalization_mode": canonicalization_mode,
                "source_application_id": source_application_id,
                "source_intake_photo_file_id": source_intake_photo_file_id,
                "command_id": command_id,
                "correlation_id": correlation_id,
                "application_status_snapshot": application_status_snapshot,
                "canonicalized_by_user_id": canonicalized_by_user_id,
            },
        ).mappings().one()
        return int(row["person_photo_source_id"])

    def list_storage_rel_paths(self) -> set[str]:
        rows = self._conn.execute(
            text("SELECT storage_rel_path FROM public.person_photos")
        ).mappings().all()
        return {str(row["storage_rel_path"]) for row in rows}


def _map_photo(row: Any) -> PersonPhotoRow:
    return PersonPhotoRow(
        person_photo_id=int(row["person_photo_id"]),
        person_id=int(row["person_id"]),
        file_id=str(row["file_id"]),
        storage_rel_path=str(row["storage_rel_path"]),
        mime_type=str(row["mime_type"]),
        byte_size=int(row["byte_size"]),
        checksum_sha256=str(row["checksum_sha256"]),
        is_active=bool(row["is_active"]),
        superseded_at=row["superseded_at"],
    )


def _map_source(row: Any) -> PersonPhotoSourceRow:
    return PersonPhotoSourceRow(
        person_photo_source_id=int(row["person_photo_source_id"]),
        person_photo_id=int(row["person_photo_id"]),
        person_id=int(row["person_id"]),
        source_kind=str(row["source_kind"]),
        canonicalization_mode=str(row["canonicalization_mode"]),
        source_application_id=(
            int(row["source_application_id"]) if row["source_application_id"] is not None else None
        ),
        source_intake_photo_file_id=row["source_intake_photo_file_id"],
        command_id=str(row["command_id"]),
    )


def utcnow() -> datetime:
    return datetime.now(UTC)
