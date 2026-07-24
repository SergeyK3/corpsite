"""Human-readable archive/export filenames for intake photos.

Physical storage uses a stable ``{photo_file_id}.jpg`` under
``{PERSONNEL_PHOTO_STORAGE_ROOT}/{application_id}/``. Archive names are only
for manual search and HR export and must keep Cyrillic while stripping
filesystem-forbidden characters.
"""
from __future__ import annotations

import re
from urllib.parse import quote

_FORBIDDEN_CHARS_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')
_WHITESPACE_RE = re.compile(r"\s+")
_MULTI_UNDERSCORE_RE = re.compile(r"_+")


def sanitize_intake_photo_archive_part(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = _FORBIDDEN_CHARS_RE.sub("", text)
    text = _WHITESPACE_RE.sub("_", text)
    text = _MULTI_UNDERSCORE_RE.sub("_", text)
    return text.strip("._")


def build_intake_photo_archive_filename(
    *,
    last_name: str | None,
    first_name: str | None,
    application_id: int,
    personnel_number: str | None = None,
) -> str:
    surname = sanitize_intake_photo_archive_part(last_name) or "БезФамилии"
    name = sanitize_intake_photo_archive_part(first_name) or "БезИмени"
    number = sanitize_intake_photo_archive_part(personnel_number)
    suffix = number if number else str(int(application_id))
    return f"{surname}_{name}_{suffix}.jpg"


def build_intake_photo_content_disposition(archive_filename: str) -> str:
    """RFC 5987 Content-Disposition preserving Cyrillic via filename*."""
    safe_ascii = "photo.jpg"
    encoded = quote(str(archive_filename or safe_ascii), safe="")
    return f"inline; filename=\"{safe_ascii}\"; filename*=UTF-8''{encoded}"
