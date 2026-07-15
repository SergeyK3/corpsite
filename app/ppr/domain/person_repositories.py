"""PersonRepository contract — read-only general section projection (WP-PR-010 §4.3)."""
from __future__ import annotations

from typing import Protocol

from app.ppr.domain.person_models import PersonGeneralReadSnapshot


class PersonRepository(Protocol):
    """Read-only Person general/cadre projection for PPR.

    Writable cadre updates deferred to R5 UpdateGeneralSection (no version on persons).
    """

    def load_general_read_snapshot(self, person_id: int) -> PersonGeneralReadSnapshot:
        """Load composite read snapshot for person_id (direct row, no merge redirect)."""
