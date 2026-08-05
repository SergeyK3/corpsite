"""Safe Content-Disposition header builder for attachment downloads."""
from __future__ import annotations

import re
from urllib.parse import quote


def _strip_crlf(value: str) -> str:
    return value.replace("\r", "").replace("\n", "")


def _ascii_fallback_filename(filename: str) -> str:
    cleaned = _strip_crlf(str(filename or "attachment").strip() or "attachment")
    ascii_only = re.sub(r"[^A-Za-z0-9._-]+", "_", cleaned).strip("._")
    if not ascii_only or ascii_only.lower() in {"pdf", "bin", "txt", "doc", "docx", "jpg", "png"}:
        ascii_only = "attachment"
    elif len(ascii_only) < 3:
        ascii_only = "attachment"
    if len(ascii_only) > 200:
        ascii_only = ascii_only[:200]
    return ascii_only.replace('"', "'")


def build_attachment_content_disposition(original_filename: str) -> str:
    """Return RFC 6266 / RFC 5987 Content-Disposition with ASCII fallback and UTF-8 filename*."""
    raw = _strip_crlf(str(original_filename or "attachment").strip() or "attachment")
    fallback = _ascii_fallback_filename(raw)
    encoded = quote(raw, safe="")
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{encoded}"
