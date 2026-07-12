"""Deterministic runtime fingerprint service (UDE-010)."""
from __future__ import annotations

import hashlib

from app.document_engine.editorial.editorial_models import EditorialFingerprint
from app.document_engine.read_models.locale import LocaleBlockReadModel


class FingerprintService:
    """Computes deterministic runtime fingerprints — no database hashes."""

    @staticmethod
    def _canonical_payload(
        *,
        generator_key: str | None,
        generator_version: str | None,
        generated_text: str | None,
        scope: str,
        block_type: str,
        order_item_id: int | None,
    ) -> str:
        parts = (
            str(generator_key or ""),
            str(generator_version or ""),
            str(scope),
            str(block_type),
            str(order_item_id if order_item_id is not None else ""),
            str(generated_text or ""),
        )
        return "|".join(parts)

    @staticmethod
    def compute_runtime_fingerprint(
        *,
        generator_key: str | None,
        generator_version: str | None,
        generated_text: str | None,
        scope: str,
        block_type: str,
        order_item_id: int | None,
    ) -> EditorialFingerprint:
        canonical = FingerprintService._canonical_payload(
            generator_key=generator_key,
            generator_version=generator_version,
            generated_text=generated_text,
            scope=scope,
            block_type=block_type,
            order_item_id=order_item_id,
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return EditorialFingerprint(
            value=digest,
            generator_key=generator_key,
            generator_version=generator_version,
            source_fingerprint=None,
        )

    @staticmethod
    def from_read_block(block: LocaleBlockReadModel) -> EditorialFingerprint:
        runtime = FingerprintService.compute_runtime_fingerprint(
            generator_key=block.generator_key,
            generator_version=block.generator_version,
            generated_text=block.generated_text,
            scope=block.scope,
            block_type=block.block_type,
            order_item_id=block.order_item_id,
        )
        return EditorialFingerprint(
            value=runtime.value,
            generator_key=block.generator_key,
            generator_version=block.generator_version,
            source_fingerprint=block.source_fingerprint,
        )

    @staticmethod
    def has_generated_changed(
        *,
        stored_fingerprint: str | None,
        current_fingerprint: str,
    ) -> bool:
        if not str(stored_fingerprint or "").strip():
            return False
        return str(stored_fingerprint) != str(current_fingerprint)

    @staticmethod
    def runtime_matches_source(block: LocaleBlockReadModel) -> bool:
        """True when runtime fingerprint inputs match stored source_fingerprint context."""
        if not block.source_fingerprint:
            return True
        runtime = FingerprintService.compute_runtime_fingerprint(
            generator_key=block.generator_key,
            generator_version=block.generator_version,
            generated_text=block.generated_text,
            scope=block.scope,
            block_type=block.block_type,
            order_item_id=block.order_item_id,
        )
        return not FingerprintService.has_generated_changed(
            stored_fingerprint=block.source_fingerprint,
            current_fingerprint=runtime.value,
        )
