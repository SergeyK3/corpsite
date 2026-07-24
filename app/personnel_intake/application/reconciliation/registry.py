"""Section plugin registry (WP-004 §4.2)."""
from __future__ import annotations

from app.personnel_intake.application.reconciliation.plugin import SectionReconciliationPlugin
from app.personnel_intake.domain.reconciliation.errors import ReconciliationValidationError


class SectionReconciliationRegistry:
    """Map section_code → SectionReconciliationPlugin."""

    def __init__(self) -> None:
        self._plugins: dict[str, SectionReconciliationPlugin] = {}

    def register(self, plugin: SectionReconciliationPlugin) -> None:
        code = str(plugin.section_code)
        if code in self._plugins:
            raise ReconciliationValidationError(
                f"Section plugin already registered for {code!r}.",
                code="DUPLICATE_SECTION_PLUGIN",
            )
        self._plugins[code] = plugin

    def resolve(self, section_code: str) -> SectionReconciliationPlugin | None:
        return self._plugins.get(section_code)

    def require(self, section_code: str) -> SectionReconciliationPlugin:
        plugin = self.resolve(section_code)
        if plugin is None:
            raise ReconciliationValidationError(
                f"No reconciliation plugin registered for section_code={section_code!r}.",
                code="UNKNOWN_SECTION_PLUGIN",
            )
        return plugin


__all__ = ["SectionReconciliationRegistry"]
