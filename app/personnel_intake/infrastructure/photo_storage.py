"""Filesystem storage for intake applicant photos.

Canonical on-disk layout (single configured root):
  ``{PERSONNEL_PHOTO_STORAGE_ROOT}/{application_id}/{photo_file_id}.jpg``

``photo_file_id`` is a stable 32-char hex id. Full name is never used as a
physical path component. All upload/read/replace/delete paths go through this
module only.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.config import PROJECT_ROOT, env

_PHOTO_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_ENV_NAME = "PERSONNEL_PHOTO_STORAGE_ROOT"


def resolve_path_within_root(root: Path, *relative_parts: str) -> Path:
    """Resolve ``root / parts`` and reject any escape outside ``root``."""
    root_resolved = Path(root).resolve()
    candidate = root_resolved.joinpath(*relative_parts).resolve()
    if not candidate.is_relative_to(root_resolved):
        raise ValueError("Photo path escapes storage root.")
    return candidate


def intake_photo_storage_root() -> Path:
    """Return configured photo storage root (mandatory env).

    Relative values are resolved against the project root (local:
    ``runtime/personnel-intake/photos``). Absolute values are used as-is
    (production example: ``/var/lib/corpsite/personnel-photos``).
    """
    configured = env(_ENV_NAME)
    if not configured:
        raise RuntimeError(
            f"{_ENV_NAME} must be set. "
            "Local example: runtime/personnel-intake/photos. "
            "Production example: /var/lib/corpsite/personnel-photos."
        )
    path = Path(configured)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def ensure_intake_photo_storage_root() -> Path:
    """Create storage root if missing and verify backend write access."""
    root = intake_photo_storage_root().resolve()
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".write_probe"
        probe.write_bytes(b"ok")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        raise RuntimeError(
            f"{_ENV_NAME} is not writable by the backend user: {root}"
        ) from exc
    return root


def normalize_intake_photo_file_id(value: str | None) -> str:
    file_id = str(value or "").strip().lower()
    if not file_id:
        return ""
    if not _PHOTO_ID_RE.fullmatch(file_id):
        raise ValueError("Invalid photo file id.")
    return file_id


def intake_photo_path(application_id: int, file_id: str) -> Path:
    safe_id = normalize_intake_photo_file_id(file_id)
    if not safe_id:
        raise ValueError("Invalid photo file id.")
    root = ensure_intake_photo_storage_root()
    return resolve_path_within_root(root, str(int(application_id)), f"{safe_id}.jpg")


def save_intake_photo(application_id: int, file_id: str, content: bytes) -> Path:
    path = intake_photo_path(application_id, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def read_intake_photo(application_id: int, file_id: str) -> bytes | None:
    path = intake_photo_path(application_id, file_id)
    if not path.is_file():
        return None
    return path.read_bytes()


def delete_intake_photo(application_id: int, file_id: str) -> None:
    if not str(file_id or "").strip():
        return
    path = intake_photo_path(application_id, file_id)
    if path.is_file():
        path.unlink()
