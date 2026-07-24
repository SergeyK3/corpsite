"""Section reconciliation plugins (decide-phase)."""
from __future__ import annotations

from app.personnel_intake.application.reconciliation.plugins.education import (
    EducationReconciliationPlugin,
    register_education_plugin,
)
from app.personnel_intake.application.reconciliation.registry import SectionReconciliationRegistry


def register_default_section_plugins(registry: SectionReconciliationRegistry) -> None:
    """Register built-in decide-phase section plugins."""
    register_education_plugin(registry)


__all__ = [
    "EducationReconciliationPlugin",
    "register_default_section_plugins",
    "register_education_plugin",
]
