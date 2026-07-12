"""Review state policy — computation only, no lifecycle transitions (UDE-010)."""
from __future__ import annotations

from app.document_engine.editorial.editorial_models import ReviewState
from app.document_engine.editorial.fingerprint_service import FingerprintService
from app.document_engine.editorial.override_resolver import OverrideResolver
from app.document_engine.read_models.locale import LocaleBlockReadModel
from app.document_engine.value_objects.localization import StalenessState

_ADAPTER_REVIEW_TO_STATE = {
    "CURRENT": ReviewState.CURRENT,
    "STALE": ReviewState.STALE,
    "REVIEW_REQUIRED": ReviewState.REVIEW_REQUIRED,
    "GENERATION_FAILED": ReviewState.REVIEW_REQUIRED,
}

_STALENESS_TO_REVIEW = {
    StalenessState.CURRENT: ReviewState.CURRENT,
    StalenessState.STALE_SEMANTIC_CHANGE: ReviewState.STALE,
    StalenessState.STALE_RU_CHANGE_AFTER_KK: ReviewState.STALE,
    StalenessState.STALE_FINGERPRINT_MISMATCH: ReviewState.STALE,
    StalenessState.REVIEW_REQUIRED: ReviewState.REVIEW_REQUIRED,
}


class ReviewPolicy:
    """Maps adapter review signals to shared ReviewState."""

    @staticmethod
    def from_adapter_review_status(review_status: str) -> ReviewState:
        normalized = str(review_status or "").strip().upper()
        return _ADAPTER_REVIEW_TO_STATE.get(normalized, ReviewState.UNKNOWN)

    @staticmethod
    def from_staleness_state(staleness: StalenessState) -> ReviewState:
        return _STALENESS_TO_REVIEW.get(staleness, ReviewState.UNKNOWN)

    @staticmethod
    def compute_for_block(block: LocaleBlockReadModel) -> ReviewState:
        """Derive review state preserving adapter-provided observable behavior."""
        from_status = ReviewPolicy.from_adapter_review_status(block.review_status)
        if from_status != ReviewState.UNKNOWN:
            return from_status

        from_staleness = ReviewPolicy.from_staleness_state(block.staleness_state)
        if from_staleness != ReviewState.UNKNOWN:
            return from_staleness

        fingerprint = FingerprintService.from_read_block(block)
        if OverrideResolver.has_override(block.override_text):
            if FingerprintService.has_generated_changed(
                stored_fingerprint=block.source_fingerprint,
                current_fingerprint=fingerprint.value,
            ):
                return ReviewState.REVIEW_REQUIRED

        return ReviewState.CURRENT
