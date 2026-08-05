"""Filesystem storage for incoming document attachments."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from app.config import PROJECT_ROOT, env

_FILE_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_STAGING_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_ENV_NAME = "INCOMING_INFO_STORAGE_ROOT"
_STAGING_DIR = "_staging"
_QUARANTINE_DIR = "_quarantine"
_QUARANTINE_SUFFIX = ".trash"


def resolve_path_within_root(root: Path, *relative_parts: str) -> Path:
    root_resolved = Path(root).resolve()
    candidate = root_resolved.joinpath(*relative_parts).resolve()
    if not candidate.is_relative_to(root_resolved):
        raise ValueError("Attachment path escapes storage root.")
    return candidate


def incoming_attachment_storage_root() -> Path:
    configured = env(_ENV_NAME)
    if not configured:
        raise RuntimeError(
            f"{_ENV_NAME} must be set. "
            "Local example: runtime/incoming-information/attachments. "
            "Production example: /var/lib/corpsite/incoming-information/attachments."
        )
    path = Path(configured)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def ensure_incoming_attachment_storage_root() -> Path:
    root = incoming_attachment_storage_root().resolve()
    try:
        root.mkdir(parents=True, exist_ok=True)
        staging = root / _STAGING_DIR
        staging.mkdir(parents=True, exist_ok=True)
        quarantine = root / _QUARANTINE_DIR
        quarantine.mkdir(parents=True, exist_ok=True)
        probe = root / ".write_probe"
        probe.write_bytes(b"ok")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        raise RuntimeError(
            f"{_ENV_NAME} is not writable by the backend user: {root}"
        ) from exc
    return root


def normalize_attachment_file_id(value: str | None) -> str:
    file_id = str(value or "").strip().lower()
    if not file_id:
        return ""
    if not _FILE_ID_RE.fullmatch(file_id):
        raise ValueError("Invalid attachment file id.")
    return file_id


def normalize_staging_id(value: str | None) -> str:
    staging_id = str(value or "").strip().lower()
    if not staging_id:
        return ""
    if not _STAGING_ID_RE.fullmatch(staging_id):
        raise ValueError("Invalid attachment staging id.")
    return staging_id


def incoming_attachment_path(incoming_document_id: int, file_id: str, extension: str) -> Path:
    safe_id = normalize_attachment_file_id(file_id)
    if not safe_id:
        raise ValueError("Invalid attachment file id.")
    ext = str(extension or "bin").strip().lower().lstrip(".")
    if not ext or not re.fullmatch(r"[a-z0-9]{1,8}", ext):
        raise ValueError("Invalid attachment extension.")
    root = ensure_incoming_attachment_storage_root()
    return resolve_path_within_root(
        root,
        str(int(incoming_document_id)),
        f"{safe_id}.{ext}",
    )


def staging_attachment_path(staging_id: str) -> Path:
    safe_id = normalize_staging_id(staging_id)
    if not safe_id:
        raise ValueError("Invalid attachment staging id.")
    root = ensure_incoming_attachment_storage_root()
    return resolve_path_within_root(root, _STAGING_DIR, f"{safe_id}.part")


def write_staging_attachment(staging_id: str, content: bytes) -> Path:
    path = staging_attachment_path(staging_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def read_staging_attachment(staging_id: str) -> bytes:
    path = staging_attachment_path(staging_id)
    if not path.is_file():
        raise FileNotFoundError(f"Staging attachment {staging_id} not found.")
    return path.read_bytes()


def delete_staging_attachment(staging_id: str) -> None:
    if not str(staging_id or "").strip():
        return
    path = staging_attachment_path(staging_id)
    if path.is_file():
        path.unlink()


def promote_staging_attachment(
    staging_id: str,
    incoming_document_id: int,
    file_id: str,
    extension: str,
) -> Path:
    staging_path = staging_attachment_path(staging_id)
    if not staging_path.is_file():
        raise FileNotFoundError(f"Staging attachment {staging_id} not found.")
    permanent_path = incoming_attachment_path(incoming_document_id, file_id, extension)
    permanent_path.parent.mkdir(parents=True, exist_ok=True)
    staging_path.replace(permanent_path)
    return permanent_path


def save_incoming_attachment(
    incoming_document_id: int,
    file_id: str,
    extension: str,
    content: bytes,
) -> Path:
    path = incoming_attachment_path(incoming_document_id, file_id, extension)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def read_incoming_attachment(incoming_document_id: int, file_id: str, extension: str) -> bytes | None:
    path = incoming_attachment_path(incoming_document_id, file_id, extension)
    if not path.is_file():
        return None
    return path.read_bytes()


def delete_incoming_attachment(incoming_document_id: int, file_id: str, extension: str) -> None:
    if not str(file_id or "").strip():
        return
    path = incoming_attachment_path(incoming_document_id, file_id, extension)
    if path.is_file():
        path.unlink()


def quarantine_artifact_path(quarantine_id: str) -> Path:
    safe_id = normalize_staging_id(quarantine_id)
    if not safe_id:
        raise ValueError("Invalid quarantine id.")
    root = ensure_incoming_attachment_storage_root()
    return resolve_path_within_root(root, _QUARANTINE_DIR, f"{safe_id}{_QUARANTINE_SUFFIX}")


def move_attachment_to_quarantine(
    incoming_document_id: int,
    file_id: str,
    extension: str,
    *,
    quarantine_id: str | None = None,
) -> str:
    """Atomically move permanent attachment into quarantine before DB delete."""
    import uuid

    artifact_id = normalize_staging_id(quarantine_id or uuid.uuid4().hex)
    if not artifact_id:
        raise ValueError("Invalid quarantine id.")
    source = incoming_attachment_path(incoming_document_id, file_id, extension)
    if not source.is_file():
        raise FileNotFoundError(
            f"Attachment file missing for document {incoming_document_id}, file_id={file_id}."
        )
    destination = quarantine_artifact_path(artifact_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.replace(destination)
    return artifact_id


def restore_attachment_from_quarantine(
    quarantine_id: str,
    incoming_document_id: int,
    file_id: str,
    extension: str,
) -> None:
    """Restore permanent attachment when DB delete rolls back."""
    source = quarantine_artifact_path(quarantine_id)
    if not source.is_file():
        return
    destination = incoming_attachment_path(incoming_document_id, file_id, extension)
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.replace(destination)


def delete_quarantine_artifact(quarantine_id: str) -> None:
    """Remove quarantined file after successful DB delete. Idempotent."""
    if not str(quarantine_id or "").strip():
        return
    path = quarantine_artifact_path(quarantine_id)
    if path.is_file():
        path.unlink()


def cleanup_quarantine_artifact(quarantine_id: str) -> bool:
    """Best-effort quarantine cleanup. Returns False when artifact remains."""
    try:
        delete_quarantine_artifact(quarantine_id)
    except OSError:
        return not quarantine_artifact_path(quarantine_id).is_file()
    return not quarantine_artifact_path(quarantine_id).is_file()


def list_orphan_paths_in_root(root: Path | None = None) -> list[Path]:
    """Return staging *.part files — for tests/diagnostics."""
    base = (root or ensure_incoming_attachment_storage_root()).resolve()
    staging = base / _STAGING_DIR
    if not staging.is_dir():
        return []
    return sorted(staging.glob("*.part"))


def list_quarantine_artifacts_in_root(root: Path | None = None) -> list[Path]:
    """Return quarantine *.trash files — for tests/diagnostics and retry cleanup."""
    base = (root or ensure_incoming_attachment_storage_root()).resolve()
    quarantine = base / _QUARANTINE_DIR
    if not quarantine.is_dir():
        return []
    return sorted(quarantine.glob(f"*{_QUARANTINE_SUFFIX}"))
