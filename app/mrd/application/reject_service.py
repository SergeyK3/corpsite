"""Reject Detected Difference — lifecycle only, no MRD mutation."""
from __future__ import annotations

from app.mrd.domain.difference_models import RejectDifferenceCommand, RejectDifferenceResult
from app.mrd.domain.errors import DifferenceNotFoundError, DifferenceStateConflictError
from app.mrd.domain.types import DIFFERENCE_LIFECYCLE_DETECTED, DIFFERENCE_LIFECYCLE_REJECTED
from app.mrd.infrastructure.repository import SqlAlchemyMrdRepository, utcnow


class RejectDifferenceService:
    """Reject handler: difference → REJECTED without Confirmed Change."""

    def __init__(self, repo: SqlAlchemyMrdRepository) -> None:
        self._repo = repo

    def reject(self, command: RejectDifferenceCommand) -> RejectDifferenceResult:
        difference = self._repo.load_difference(command.difference_id)
        if difference is None:
            raise DifferenceNotFoundError(f"difference_id={command.difference_id} not found")
        if difference.lifecycle_status != DIFFERENCE_LIFECYCLE_DETECTED:
            raise DifferenceStateConflictError(
                f"Reject requires DETECTED; got {difference.lifecycle_status!r}"
            )
        if difference.row_version != command.expected_row_version:
            raise DifferenceStateConflictError("Stale Detected Difference row_version")

        rejected_at = utcnow()
        self._repo.mark_rejected(
            command.difference_id,
            expected_row_version=command.expected_row_version,
            rejected_by=command.rejected_by,
            rejected_at=rejected_at,
            basis=command.basis,
        )
        return RejectDifferenceResult(
            difference_id=command.difference_id,
            lifecycle_status=DIFFERENCE_LIFECYCLE_REJECTED,
            rejected_at=rejected_at,
        )
