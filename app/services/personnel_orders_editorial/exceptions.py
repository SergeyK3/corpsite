"""Editorial service error types (WP-PO-EDIT-002)."""
from __future__ import annotations

from typing import Any, Dict, List


class PersonnelOrderReadyGateError(RuntimeError):
    """Ready-for-signature blocked by editorial gate problems."""

    def __init__(self, problems: List[Dict[str, Any]]):
        self.problems = list(problems)
        super().__init__("READY_GATE_FAILED")


class PersonnelOrderEditorialBlockNotFoundError(LookupError):
    """Editorial block not found for the given order."""


class PersonnelOrderEditorialConflictError(RuntimeError):
    """Optimistic concurrency / revision conflict on editorial write."""
