"""Read the same verified canonical Person photo for personnel and self cards."""
from __future__ import annotations

import hmac

from app.db.engine import engine
from app.db.models.person_photos import MIME_TYPE_JPEG
from app.person_photos.infrastructure.photo_storage import (
    read_canonical_photo,
    sha256_hex,
    validate_canonical_photo_bytes,
)
from app.person_photos.infrastructure.repository import PersonPhotoRepository
from app.personnel_intake.domain.errors import PersonnelIntakeValidationError


def load_verified_person_photo(person_id: int, *, user: dict | None = None) -> bytes | None:
    """Return verified JPEG bytes or None; callers authorize the Person first."""
    if user is not None:
        from app.personnel_files.service import active_photo
        managed, content = active_photo(user, person_id)
        if managed:
            return content
    with engine.connect() as conn:
        photo = PersonPhotoRepository(conn).get_active_photo(person_id)
    if photo is None or photo.mime_type != MIME_TYPE_JPEG:
        return None

    try:
        content = read_canonical_photo(photo.storage_rel_path)
        if content is None:
            return None
        validate_canonical_photo_bytes(content)
        if not hmac.compare_digest(
            sha256_hex(content), photo.checksum_sha256.strip().lower()
        ):
            return None
        return content
    except (OSError, ValueError, PersonnelIntakeValidationError):
        return None
