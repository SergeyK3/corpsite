"""Person-scoped canonical JPEG storage (ADR-061)."""
from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

from app.db.models.person_photos import MIME_TYPE_JPEG
from app.person_photos.domain.errors import CanonicalFileCollisionError
from app.personnel_intake.domain.photo_validation import validate_intake_photo_bytes
from app.personnel_intake.infrastructure.photo_storage import (
    intake_photo_storage_root,
    resolve_path_within_root,
)

_TMP_DIR_NAME = ".tmp"


@dataclass(frozen=True, slots=True)
class PreparedCanonicalPhoto:
    file_id: str
    storage_rel_path: str
    absolute_path: Path
    byte_size: int
    checksum_sha256: str


def normalize_photo_file_id(value: str | None) -> str:
    file_id = str(value or "").strip().lower()
    if len(file_id) != 32 or any(ch not in "0123456789abcdef" for ch in file_id):
        raise ValueError("Invalid canonical photo file id.")
    return file_id


def generate_photo_file_id() -> str:
    return secrets.token_hex(16)


def storage_rel_path(person_id: int, file_id: str) -> str:
    safe_id = normalize_photo_file_id(file_id)
    return f"person/{int(person_id)}/{safe_id}.jpg"


def canonical_photo_absolute_path(storage_rel_path_value: str) -> Path:
    root = intake_photo_storage_root()
    parts = storage_rel_path_value.replace("\\", "/").split("/")
    if len(parts) != 3 or parts[0] != "person" or not parts[2].endswith(".jpg"):
        raise ValueError("Invalid canonical storage_rel_path.")
    return resolve_path_within_root(root, parts[0], parts[1], parts[2])


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def validate_canonical_photo_bytes(content: bytes) -> None:
    validate_intake_photo_bytes(content, content_type=MIME_TYPE_JPEG)


def _publish_canonical_photo_atomically(*, temp_path: Path, final_path: Path) -> None:
    if final_path.exists():
        raise CanonicalFileCollisionError(
            f"Canonical photo already exists at {final_path.as_posix()}"
        )
    try:
        os.link(os.fspath(temp_path), os.fspath(final_path))
    except FileExistsError as exc:
        raise CanonicalFileCollisionError(
            f"Canonical photo already exists at {final_path.as_posix()}"
        ) from exc
    temp_path.unlink(missing_ok=True)


def prepare_canonical_photo_from_bytes(
    *,
    person_id: int,
    content: bytes,
    file_id: str | None = None,
) -> PreparedCanonicalPhoto:
    validate_canonical_photo_bytes(content)
    checksum = sha256_hex(content)
    resolved_file_id = normalize_photo_file_id(file_id) if file_id else generate_photo_file_id()
    rel_path = storage_rel_path(person_id, resolved_file_id)
    final_path = canonical_photo_absolute_path(rel_path)
    temp_path = resolve_path_within_root(
        intake_photo_storage_root(),
        _TMP_DIR_NAME,
        "person",
        str(int(person_id)),
        f"{resolved_file_id}.jpg.part",
    )
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        temp_path.write_bytes(content)
        read_back = temp_path.read_bytes()
        validate_canonical_photo_bytes(read_back)
        read_checksum = sha256_hex(read_back)
        if read_checksum != checksum:
            raise RuntimeError("Canonical photo read-back checksum mismatch.")
        _publish_canonical_photo_atomically(temp_path=temp_path, final_path=final_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    finally:
        temp_path.unlink(missing_ok=True)

    return PreparedCanonicalPhoto(
        file_id=resolved_file_id,
        storage_rel_path=rel_path,
        absolute_path=final_path,
        byte_size=len(content),
        checksum_sha256=checksum,
    )


def read_canonical_photo(storage_rel_path_value: str) -> bytes | None:
    path = canonical_photo_absolute_path(storage_rel_path_value)
    if not path.is_file():
        return None
    return path.read_bytes()


def delete_canonical_photo_file(storage_rel_path_value: str) -> None:
    path = canonical_photo_absolute_path(storage_rel_path_value)
    if path.is_file():
        path.unlink()


def verify_canonical_photo_file(
    storage_rel_path_value: str,
    *,
    expected_checksum_sha256: str,
) -> None:
    content = read_canonical_photo(storage_rel_path_value)
    if content is None:
        raise FileNotFoundError(storage_rel_path_value)
    validate_canonical_photo_bytes(content)
    actual = sha256_hex(content)
    if actual != expected_checksum_sha256.lower():
        raise ValueError("Canonical photo checksum mismatch.")
