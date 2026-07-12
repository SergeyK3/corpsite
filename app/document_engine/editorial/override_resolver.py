"""Override resolution — effective = override ?? generated (UDE-003)."""
from __future__ import annotations


class OverrideResolver:
    """Resolves effective text from generated and override layers."""

    @staticmethod
    def has_override(override_text: str | None) -> bool:
        return bool(str(override_text or "").strip())

    @staticmethod
    def resolve_effective(
        *,
        generated_text: str | None,
        override_text: str | None,
    ) -> str:
        if OverrideResolver.has_override(override_text):
            return str(override_text).strip()
        return str(generated_text or "")

    @staticmethod
    def text_source_from_layers(
        *,
        generated_text: str | None,
        override_text: str | None,
    ) -> str:
        """Returns 'override' or 'generated' — informational only."""
        return "override" if OverrideResolver.has_override(override_text) else "generated"
