"""IdentityRepository contract (WP-PR-010 §4.4)."""
from __future__ import annotations

from typing import Protocol

from app.ppr.domain.identity_models import IdentityResolution, PersonIdentitySnapshot


class IdentityRepository(Protocol):
    """Read-only identity resolution — employee/person linkage and merge redirect."""

    def resolve_person_id(self, person_id: int) -> IdentityResolution:
        """Resolve direct person_id to canonical survivor (merge-aware)."""

    def resolve_employee_id(self, employee_id: int) -> IdentityResolution:
        """Resolve employee_id → person_id → canonical survivor."""

    def load_identity(self, person_id: int) -> PersonIdentitySnapshot:
        """Load identity-owned slice for a person_id without merge redirect."""

    def resolve_survivor(self, person_id: int) -> int:
        """Return canonical survivor person_id after merge redirect."""
