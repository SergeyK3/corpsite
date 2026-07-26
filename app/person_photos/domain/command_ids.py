"""Stable command identifiers for person photo canonicalization."""
from __future__ import annotations


def intake_photo_command_id(application_id: int, intake_photo_file_id: str) -> str:
    return f"person-photo:canonicalize:intake:{application_id}:{intake_photo_file_id}"
