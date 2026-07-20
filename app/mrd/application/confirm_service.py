"""Confirm Detected Difference — atomic event + lifecycle + MRD entry."""
from __future__ import annotations

from app.mrd.domain.candidate_builder import CONFLICT_ATTRIBUTE
from app.mrd.domain.difference_models import ConfirmDifferenceCommand, ConfirmDifferenceResult
from app.mrd.domain.errors import (
    DifferenceConfirmForbiddenError,
    DifferenceNotFoundError,
    DifferenceStateConflictError,
    MrdNotFoundError,
)
from app.mrd.domain.invariants import validate_mrd_status_for_confirm
from app.mrd.domain.types import (
    DIFFERENCE_LIFECYCLE_DETECTED,
    MRD_STATUS_ACTIVE,
    TECHNICAL_DIFF_CONFLICT,
)
from app.mrd.infrastructure.repository import SqlAlchemyMrdRepository, utcnow


class ConfirmDifferenceService:
    """Confirm handler: Confirmed Change event + difference CONFIRMED + MRD entry."""

    def __init__(self, repo: SqlAlchemyMrdRepository) -> None:
        self._repo = repo

    def confirm(self, command: ConfirmDifferenceCommand) -> ConfirmDifferenceResult:
        difference = self._repo.load_difference(command.difference_id)
        if difference is None:
            raise DifferenceNotFoundError(f"difference_id={command.difference_id} not found")
        if difference.lifecycle_status != DIFFERENCE_LIFECYCLE_DETECTED:
            raise DifferenceStateConflictError(
                f"Confirm requires DETECTED; got {difference.lifecycle_status!r}"
            )
        if difference.row_version != command.expected_row_version:
            raise DifferenceStateConflictError("Stale Detected Difference row_version")

        if not command.resolve_conflict:
            if difference.technical_diff_class == TECHNICAL_DIFF_CONFLICT:
                raise DifferenceConfirmForbiddenError(
                    "CONFLICT technical_diff_class cannot be confirmed until resolved"
                )
            if difference.attribute == CONFLICT_ATTRIBUTE:
                raise DifferenceConfirmForbiddenError(
                    "Conflict attribute differences cannot be confirmed until resolved"
                )

        active_mrd = self._repo.resolve_active_mrd(difference.report_period)
        if active_mrd is None or active_mrd.mrd_id != difference.mrd_id:
            raise MrdNotFoundError(
                "Detected Difference must target ACTIVE MRD for its report_period"
            )
        validate_mrd_status_for_confirm(active_mrd.status)
        if active_mrd.status != MRD_STATUS_ACTIVE:
            raise MrdNotFoundError(f"MRD mrd_id={difference.mrd_id} is not ACTIVE")

        confirmed_at = utcnow()
        confirmed_change_id = self._repo.insert_confirmed_change(
            difference=difference,
            confirmed_by=command.confirmed_by,
            confirmed_at=confirmed_at,
            basis=command.basis,
        )
        self._repo.mark_confirmed(
            command.difference_id,
            expected_row_version=command.expected_row_version,
            confirmed_by=command.confirmed_by,
            confirmed_at=confirmed_at,
        )

        match_key = str(difference.origin_context.get("match_key") or difference.entity_scope)
        record_kind = difference.record_kind or "roster"
        entry_id = self._repo.apply_attribute_change(
            mrd_id=difference.mrd_id,
            match_key=match_key,
            entity_scope=difference.entity_scope,
            record_kind=record_kind,
            attribute=difference.attribute,
            old_value=difference.old_value,
            new_value=difference.new_value,
            confirmed_change_id=confirmed_change_id,
        )

        mrd_after = self._repo.load_mrd(difference.mrd_id)
        if mrd_after is not None and mrd_after.version == active_mrd.version:
            pass
        else:
            raise RuntimeError("Confirm must not change MRD version number")

        batch_id = (difference.origin_context or {}).get("batch_id")
        if batch_id is not None:
            from app.services.hr_import_review_exception_service import run_post_difference_review_completion

            run_post_difference_review_completion(
                self._repo._conn,
                batch_id=int(batch_id),
                actor_user_id=int(command.confirmed_by),
            )

        return ConfirmDifferenceResult(
            confirmed_change_id=confirmed_change_id,
            difference_id=command.difference_id,
            mrd_id=difference.mrd_id,
            entry_id=entry_id,
        )
