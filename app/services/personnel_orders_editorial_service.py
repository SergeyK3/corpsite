"""Editorial persistence service for personnel orders (WP-PO-EDIT-002).

Thin public facade over ``app.services.personnel_orders_editorial`` modules.

Review status semantics
-----------------------
CURRENT
    Generated text matches the current structured fingerprint. Override is
    absent, OR override is present and the fingerprint is unchanged since the
    last generate / edit acknowledgment.

STALE
    Override is present AND stored ``source_fingerprint`` differs from the
    current structured fingerprint (structured data changed under an override).
    Prefer this on structured change without regenerate (R9).

REVIEW_REQUIRED
    After regenerate that kept an override while the fingerprint changed; OR
    unsupported basis policy for the item type. Prefer this on regenerate with
    override kept + fingerprint changed.

GENERATION_FAILED
    The last generate attempt for the block raised an exception.
"""
from __future__ import annotations

from app.services.personnel_orders_editorial.availability import editorial_tables_available
from app.services.personnel_orders_editorial.exceptions import (
    PersonnelOrderEditorialBlockNotFoundError,
    PersonnelOrderEditorialConflictError,
    PersonnelOrderReadyGateError,
)
from app.services.personnel_orders_editorial.generation_service import generate_editorial
from app.services.personnel_orders_editorial.mapper import effective_text
from app.services.personnel_orders_editorial.ready_gate import evaluate_ready_gate
from app.services.personnel_orders_editorial.service import (
    get_editorial_state,
    patch_editorial_block,
    reset_block_to_generated,
)
from app.services.personnel_orders_editorial.stale import mark_blocks_stale_after_structured_change

__all__ = [
    "PersonnelOrderReadyGateError",
    "PersonnelOrderEditorialBlockNotFoundError",
    "PersonnelOrderEditorialConflictError",
    "effective_text",
    "editorial_tables_available",
    "get_editorial_state",
    "generate_editorial",
    "patch_editorial_block",
    "reset_block_to_generated",
    "evaluate_ready_gate",
    "mark_blocks_stale_after_structured_change",
]
