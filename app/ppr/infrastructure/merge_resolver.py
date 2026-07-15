"""Iterative merge redirect resolver (read-only, fail-closed)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.ppr.domain.errors import (
    PprMergeCycleError,
    PprMergeDepthExceededError,
    PprMergeTargetMissingError,
    PprPersonNotFoundError,
)
from app.ppr.domain.identity_models import (
    MAX_MERGE_REDIRECT_DEPTH,
    PERSON_STATUS_MERGED,
    PersonIdentitySnapshot,
)


@dataclass(frozen=True, slots=True)
class MergeResolution:
    source_person_id: int
    resolved_person_id: int
    merge_redirected: bool
    merge_chain: tuple[int, ...]


def resolve_merge_chain(
    start_person_id: int,
    load_identity: Callable[[int], PersonIdentitySnapshot | None],
    *,
    max_depth: int = MAX_MERGE_REDIRECT_DEPTH,
) -> MergeResolution:
    """Follow merged_into_person_id chain to survivor without mutating data."""
    if max_depth < 1:
        raise PprMergeDepthExceededError(
            f"Merge redirect depth limit must be positive (got {max_depth})."
        )

    chain: list[int] = [start_person_id]
    visited: set[int] = {start_person_id}
    current_id = start_person_id

    first = load_identity(current_id)
    if first is None:
        raise PprPersonNotFoundError(f"Person not found: person_id={start_person_id}")

    if first.person_status != PERSON_STATUS_MERGED:
        return MergeResolution(
            source_person_id=start_person_id,
            resolved_person_id=current_id,
            merge_redirected=False,
            merge_chain=tuple(chain),
        )

    for _ in range(max_depth):
        snapshot = load_identity(current_id)
        if snapshot is None:
            raise PprMergeTargetMissingError(
                f"Merge target missing in chain at person_id={current_id}"
            )
        if snapshot.person_status != PERSON_STATUS_MERGED:
            return MergeResolution(
                source_person_id=start_person_id,
                resolved_person_id=current_id,
                merge_redirected=start_person_id != current_id,
                merge_chain=tuple(chain),
            )

        target_id = snapshot.merged_into_person_id
        if target_id is None:
            raise PprMergeTargetMissingError(
                f"Merged person_id={current_id} has no merged_into_person_id"
            )
        if target_id in visited:
            raise PprMergeCycleError(
                f"Merge cycle detected involving person_id={target_id}"
            )

        chain.append(target_id)
        visited.add(target_id)
        current_id = target_id

    raise PprMergeDepthExceededError(
        f"Merge redirect depth exceeded for person_id={start_person_id} "
        f"(limit={max_depth})"
    )
