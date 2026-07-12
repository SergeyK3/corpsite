"""Shared editorial and localization runtime (UDE-010).

Read-only editorial model formation — no write path, no persistence.
"""
from __future__ import annotations

from app.document_engine.editorial.compatibility import (
    EditorialCompatibilityDifference,
    EditorialCompatibilityReport,
    build_editorial_compatibility_report,
    compare_read_snapshot_to_editorial,
    format_editorial_compatibility_report,
)
from app.document_engine.editorial.editorial_models import (
    EditorialBlock,
    EditorialDocument,
    EditorialFingerprint,
    EditorialLocale,
    EditorialOverride,
    EditorialSection,
    OfficialDraftLocaleBlock,
    OfficialDraftSnapshot,
    ReviewState,
)
from app.document_engine.editorial.editorial_service import EditorialService
from app.document_engine.editorial.facade import (
    DocumentEngineEditorialFacade,
    DocumentEngineEditorialSnapshot,
)
from app.document_engine.editorial.fingerprint_service import FingerprintService
from app.document_engine.editorial.localization_service import (
    LocalizationService,
    LocalizationView,
)
from app.document_engine.editorial.official_draft_builder import OfficialDraftBuilder
from app.document_engine.editorial.override_resolver import OverrideResolver
from app.document_engine.editorial.review_policy import ReviewPolicy

__all__ = [
    "DocumentEngineEditorialFacade",
    "DocumentEngineEditorialSnapshot",
    "EditorialBlock",
    "EditorialCompatibilityDifference",
    "EditorialCompatibilityReport",
    "EditorialDocument",
    "EditorialFingerprint",
    "EditorialLocale",
    "EditorialOverride",
    "EditorialSection",
    "EditorialService",
    "FingerprintService",
    "LocalizationService",
    "LocalizationView",
    "OfficialDraftBuilder",
    "OfficialDraftLocaleBlock",
    "OfficialDraftSnapshot",
    "OverrideResolver",
    "ReviewPolicy",
    "ReviewState",
    "build_editorial_compatibility_report",
    "compare_read_snapshot_to_editorial",
    "format_editorial_compatibility_report",
]
