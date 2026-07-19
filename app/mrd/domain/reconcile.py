"""Pure reconcile planning for Detected Differences (ADR-058)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from app.mrd.domain.comparison_models import ComparisonCandidate
from app.mrd.domain.difference_models import DetectedDifferenceRecord
from app.mrd.domain.logical_key import candidate_signature
from app.mrd.domain.types import (
    DIFFERENCE_LIFECYCLE_CONFIRMED,
    DIFFERENCE_LIFECYCLE_DETECTED,
    DIFFERENCE_LIFECYCLE_REJECTED,
)


class ReconcileActionKind(str, Enum):
    KEEP_DETECTED = "keep_detected"
    CREATE_DETECTED = "create_detected"
    SUPERSEDE_AND_CREATE = "supersede_and_create"
    SUPERSEDE_ORPHAN = "supersede_orphan"
    SKIP_TERMINAL = "skip_terminal"


@dataclass(frozen=True, slots=True)
class ReconcileAction:
    kind: ReconcileActionKind
    logical_key: str
    candidate: ComparisonCandidate | None = None
    existing_difference_id: int | None = None


_TERMINAL = frozenset({DIFFERENCE_LIFECYCLE_CONFIRMED, DIFFERENCE_LIFECYCLE_REJECTED})


def _candidate_signature(candidate: ComparisonCandidate) -> str:
    return candidate.signature


def _difference_signature(difference: DetectedDifferenceRecord) -> str:
    return candidate_signature(old_value=difference.old_value, new_value=difference.new_value)


def plan_reconcile(
    *,
    candidates: Iterable[ComparisonCandidate],
    existing: Iterable[DetectedDifferenceRecord],
) -> list[ReconcileAction]:
    candidate_by_key = {c.logical_key: c for c in candidates}
    existing_by_key: dict[str, list[DetectedDifferenceRecord]] = {}
    for row in existing:
        existing_by_key.setdefault(row.logical_key, []).append(row)

    actions: list[ReconcileAction] = []

    for logical_key, candidate in candidate_by_key.items():
        rows = existing_by_key.get(logical_key, [])
        terminal = next((r for r in rows if r.lifecycle_status in _TERMINAL), None)
        if terminal is not None:
            actions.append(
                ReconcileAction(
                    kind=ReconcileActionKind.SKIP_TERMINAL,
                    logical_key=logical_key,
                    existing_difference_id=terminal.difference_id,
                )
            )
            continue

        open_detected = next(
            (r for r in rows if r.lifecycle_status == DIFFERENCE_LIFECYCLE_DETECTED),
            None,
        )
        if open_detected is None:
            actions.append(
                ReconcileAction(
                    kind=ReconcileActionKind.CREATE_DETECTED,
                    logical_key=logical_key,
                    candidate=candidate,
                )
            )
            continue

        if _difference_signature(open_detected) == _candidate_signature(candidate):
            actions.append(
                ReconcileAction(
                    kind=ReconcileActionKind.KEEP_DETECTED,
                    logical_key=logical_key,
                    candidate=candidate,
                    existing_difference_id=open_detected.difference_id,
                )
            )
        else:
            actions.append(
                ReconcileAction(
                    kind=ReconcileActionKind.SUPERSEDE_AND_CREATE,
                    logical_key=logical_key,
                    candidate=candidate,
                    existing_difference_id=open_detected.difference_id,
                )
            )

    for logical_key, rows in existing_by_key.items():
        if logical_key in candidate_by_key:
            continue
        open_detected = next(
            (r for r in rows if r.lifecycle_status == DIFFERENCE_LIFECYCLE_DETECTED),
            None,
        )
        if open_detected is not None:
            actions.append(
                ReconcileAction(
                    kind=ReconcileActionKind.SUPERSEDE_ORPHAN,
                    logical_key=logical_key,
                    existing_difference_id=open_detected.difference_id,
                )
            )

    return actions
