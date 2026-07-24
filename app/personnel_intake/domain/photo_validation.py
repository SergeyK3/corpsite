"""Server-side validation for intake applicant photos."""
from __future__ import annotations

import io
from typing import Final

from app.personnel_intake.domain.errors import PersonnelIntakeValidationError

INTAKE_PHOTO_MAX_BYTES: Final[int] = 500 * 1024
INTAKE_PHOTO_WIDTH: Final[int] = 600
INTAKE_PHOTO_HEIGHT: Final[int] = 800
INTAKE_PHOTO_ALLOWED_CONTENT_TYPES: Final[frozenset[str]] = frozenset({"image/jpeg", "application/octet-stream"})

_EXECUTABLE_SIGNATURES: Final[tuple[bytes, ...]] = (
    b"MZ",
    b"\x7fELF",
    b"%PDF",
    b"<?xml",
    b"<svg",
    b"PK\x03\x04",
)


def _require_pillow():
    try:
        from PIL import Image  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError("Pillow is required for intake photo validation") from exc
    return Image


def validate_intake_photo_bytes(content: bytes, *, content_type: str | None = None) -> None:
    if not content:
        raise PersonnelIntakeValidationError("Photo file is empty.")
    if len(content) > INTAKE_PHOTO_MAX_BYTES:
        raise PersonnelIntakeValidationError("Photo exceeds 500 KB limit.")

    lowered = str(content_type or "").strip().lower()
    if lowered and lowered not in INTAKE_PHOTO_ALLOWED_CONTENT_TYPES:
        raise PersonnelIntakeValidationError("Only JPEG photos are accepted.")

    head = content[:512].lstrip()
    if head.startswith(b"<?xml") or head.startswith(b"<svg") or b"<svg" in head[:256].lower():
        raise PersonnelIntakeValidationError("SVG images are not allowed.")
    for signature in _EXECUTABLE_SIGNATURES:
        if content.startswith(signature):
            raise PersonnelIntakeValidationError("Unsupported photo content.")

    if not content.startswith(b"\xff\xd8"):
        raise PersonnelIntakeValidationError("Photo must be JPEG.")

    Image = _require_pillow()
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.load()
            if image.format != "JPEG":
                raise PersonnelIntakeValidationError("Photo must be JPEG.")
            width, height = image.size
            if (width, height) != (INTAKE_PHOTO_WIDTH, INTAKE_PHOTO_HEIGHT):
                raise PersonnelIntakeValidationError(
                    f"Photo must be {INTAKE_PHOTO_WIDTH}x{INTAKE_PHOTO_HEIGHT} pixels."
                )
    except PersonnelIntakeValidationError:
        raise
    except Exception as exc:
        raise PersonnelIntakeValidationError("Photo could not be decoded as JPEG.") from exc
