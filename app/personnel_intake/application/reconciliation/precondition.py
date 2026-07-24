"""Canonical precondition token builder (WP-004 §7.3)."""
from __future__ import annotations

from app.personnel_intake.application.reconciliation.dto import CanonicalRecordRef
from app.personnel_intake.domain.reconciliation.digest import DigestBuilder


def build_add_precondition(
    *,
    digest_builder: DigestBuilder,
    canonicals: tuple[CanonicalRecordRef, ...],
) -> str:
    """Digest of sorted active canonical payload_digest set at decide time."""
    digests = sorted(
        str(ref.payload_digest)
        for ref in canonicals
        if ref.lifecycle_status == "active" and ref.payload_digest
    )
    return "none-match:" + digest_builder.payload_digest(digests)


def build_keep_precondition(*, row_version: str) -> str:
    return f"keep:row_version:{row_version}"


def build_row_version_precondition(*, row_version: str) -> str:
    return f"row_version:{row_version}"


def build_manual_precondition(*, reason_code: str) -> str:
    return f"manual:{reason_code}"


__all__ = [
    "build_add_precondition",
    "build_keep_precondition",
    "build_manual_precondition",
    "build_row_version_precondition",
]
