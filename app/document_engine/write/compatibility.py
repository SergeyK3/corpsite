"""Compatibility harness — lifecycle runtime vs write runtime (UDE-012)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.document_engine.lifecycle.facade import DocumentEngineLifecycleSnapshot
from app.document_engine.write.aggregate_models import DocumentAggregate
from app.document_engine.write.command_results import WriteEvaluation


@dataclass(frozen=True, slots=True)
class WriteCompatibilityDifference:
    path: str
    lifecycle_value: Any
    write_value: Any
    note: str | None = None


@dataclass(frozen=True, slots=True)
class WriteCompatibilityReport:
    document_id: str | None
    differences: tuple[WriteCompatibilityDifference, ...]

    @property
    def is_compatible(self) -> bool:
        return not self.differences


def compare_aggregate_to_lifecycle(
    aggregate: DocumentAggregate,
    lifecycle_snapshot: DocumentEngineLifecycleSnapshot,
) -> WriteCompatibilityReport:
    differences: list[WriteCompatibilityDifference] = []

    def add(path: str, lifecycle: Any, write: Any, note: str | None = None) -> None:
        if lifecycle != write:
            differences.append(
                WriteCompatibilityDifference(
                    path=path,
                    lifecycle_value=lifecycle,
                    write_value=write,
                    note=note,
                )
            )

    evaluation = lifecycle_snapshot.evaluation
    if evaluation is None:
        return WriteCompatibilityReport(
            document_id=aggregate.document_id.value,
            differences=(
                WriteCompatibilityDifference(
                    path="evaluation",
                    lifecycle_value=None,
                    write_value="present",
                    note="missing lifecycle evaluation",
                ),
            ),
        )

    add("lifecycle_state", evaluation.lifecycle.lifecycle_state, aggregate.lifecycle_state)
    add("archive_state", evaluation.lifecycle.archive_state, aggregate.archive_state)
    add("void_kind", evaluation.lifecycle.void_kind, aggregate.void_kind)
    add(
        "decision.current_state",
        evaluation.decision.current_state,
        aggregate.lifecycle_state,
    )

    return WriteCompatibilityReport(
        document_id=aggregate.document_id.value,
        differences=tuple(differences),
    )


def compare_write_evaluation_to_lifecycle(
    evaluation: WriteEvaluation,
    lifecycle_snapshot: DocumentEngineLifecycleSnapshot,
    aggregate: DocumentAggregate,
) -> WriteCompatibilityReport:
    report = compare_aggregate_to_lifecycle(aggregate, lifecycle_snapshot)
    differences = list(report.differences)

    if evaluation.mutation_plan is not None:
        plan = evaluation.mutation_plan
        decision = lifecycle_snapshot.lifecycle_decision
        if decision is not None and plan.to_lifecycle_state is not None:
            matching = [
                t for t in decision.allowed_transitions
                if t.to_state == plan.to_lifecycle_state
            ]
            if matching and plan.is_allowed != matching[0].allowed:
                differences.append(
                    WriteCompatibilityDifference(
                        path="mutation_plan.allowed",
                        lifecycle_value=matching[0].allowed,
                        write_value=plan.is_allowed,
                        note="write plan must align with lifecycle gate",
                    )
                )

    return WriteCompatibilityReport(
        document_id=aggregate.document_id.value,
        differences=tuple(differences),
    )


def format_write_compatibility_report(report: WriteCompatibilityReport) -> str:
    if report.is_compatible:
        ref = report.document_id or "unknown"
        return f"{ref}: write runtime compatible with lifecycle runtime"
    lines = [f"{report.document_id}: {len(report.differences)} write difference(s)"]
    for diff in report.differences:
        note = f" ({diff.note})" if diff.note else ""
        lines.append(
            f"  - {diff.path}: lifecycle={diff.lifecycle_value!r} "
            f"write={diff.write_value!r}{note}"
        )
    return "\n".join(lines)
