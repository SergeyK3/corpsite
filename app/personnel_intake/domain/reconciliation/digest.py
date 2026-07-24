"""Versioned canonical-JSON digests for reconciliation (WP-004 §3.3)."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Protocol

from app.personnel_intake.domain.reconciliation.errors import ReconciliationValidationError

DIGEST_ALGORITHM_CANON_JSON_V1 = "canon-json-v1"


class DigestBuilder(Protocol):
    """Versioned digest builder."""

    version: str

    def canonical_json(self, value: Any) -> str:
        """Serialize value to canonical JSON string (UTF-8 domain validated)."""

    def payload_digest(self, value: Any) -> str:
        """SHA-256 hex (lowercase) of UTF-8 canonical JSON."""

    def verify_or_compute(
        self,
        normalized_content: Any,
        claimed_payload_digest: str | None,
    ) -> str:
        """Compute digest; optionally verify a plugin claim."""


class CanonJsonV1DigestBuilder:
    """JSON-native-only canonical JSON + SHA-256 (`canon-json-v1`)."""

    version: str = DIGEST_ALGORITHM_CANON_JSON_V1

    def _normalize(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ReconciliationValidationError(
                    "Non-finite float is not allowed in canon-json-v1.",
                    code="INVALID_DIGEST_INPUT",
                )
            return value
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            items: list[tuple[str, Any]] = []
            for key, raw in value.items():
                if not isinstance(key, str):
                    raise ReconciliationValidationError(
                        f"Dict keys must be str (got {type(key)!r}).",
                        code="INVALID_DIGEST_INPUT",
                    )
                normalized = self._normalize(raw)
                if normalized is None:
                    continue
                items.append((key, normalized))
            items.sort(key=lambda item: item[0])
            return dict(items)
        if isinstance(value, (list, tuple)):
            return [self._normalize(item) for item in value]
        raise ReconciliationValidationError(
            f"Unsupported type for canon-json-v1: {type(value)!r}.",
            code="INVALID_DIGEST_INPUT",
        )

    def canonical_json(self, value: Any) -> str:
        normalized = self._normalize(value)
        return json.dumps(
            normalized,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    def payload_digest(self, value: Any) -> str:
        encoded = self.canonical_json(value).encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        if not digest or len(digest) != 64:
            raise ReconciliationValidationError(
                "Computed payload digest must be a non-empty 64-char hex string.",
                code="INVALID_DIGEST_OUTPUT",
            )
        return digest

    def verify_or_compute(
        self,
        normalized_content: Any,
        claimed_payload_digest: str | None,
    ) -> str:
        computed = self.payload_digest(normalized_content)
        if claimed_payload_digest is not None and claimed_payload_digest != computed:
            raise ReconciliationValidationError(
                "Plugin claimed_payload_digest does not match computed digest.",
                code="PLUGIN_DIGEST_MISMATCH",
            )
        return computed


class DigestBuilderRegistry:
    """Resolve digest builders by algorithm version (WP-004 §3.3.0)."""

    def __init__(self) -> None:
        self._builders: dict[str, DigestBuilder] = {
            DIGEST_ALGORITHM_CANON_JSON_V1: CanonJsonV1DigestBuilder(),
        }

    def register(self, builder: DigestBuilder) -> None:
        self._builders[builder.version] = builder

    def resolve(self, version: str) -> DigestBuilder:
        builder = self._builders.get(version)
        if builder is None:
            raise ReconciliationValidationError(
                f"Unsupported digest_algorithm_version {version!r}.",
                code="UNSUPPORTED_DIGEST_ALGORITHM",
            )
        return builder


DEFAULT_DIGEST_BUILDER_REGISTRY = DigestBuilderRegistry()


__all__ = [
    "DIGEST_ALGORITHM_CANON_JSON_V1",
    "CanonJsonV1DigestBuilder",
    "DEFAULT_DIGEST_BUILDER_REGISTRY",
    "DigestBuilder",
    "DigestBuilderRegistry",
]
