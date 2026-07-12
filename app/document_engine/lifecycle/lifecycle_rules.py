"""Lifecycle transition rules — evaluation only (UDE-011)."""
from __future__ import annotations

from app.document_engine.lifecycle.lifecycle_models import LifecycleGate, LifecycleTransition
from app.document_engine.value_objects.lifecycle import DocumentLifecycleState

_TRANSITION_SPECS: tuple[tuple[DocumentLifecycleState, DocumentLifecycleState, LifecycleGate], ...] = (
    (DocumentLifecycleState.DRAFT, DocumentLifecycleState.READY_FOR_SIGNATURE, LifecycleGate.MARK_READY),
    (DocumentLifecycleState.DRAFT, DocumentLifecycleState.VOIDED, LifecycleGate.CANCEL),
    (DocumentLifecycleState.READY_FOR_SIGNATURE, DocumentLifecycleState.DRAFT, LifecycleGate.RETURN_TO_DRAFT),
    (DocumentLifecycleState.READY_FOR_SIGNATURE, DocumentLifecycleState.SIGNED, LifecycleGate.SIGN),
    (DocumentLifecycleState.READY_FOR_SIGNATURE, DocumentLifecycleState.VOIDED, LifecycleGate.CANCEL),
    (DocumentLifecycleState.SIGNED, DocumentLifecycleState.REGISTERED, LifecycleGate.REGISTER),
    (DocumentLifecycleState.SIGNED, DocumentLifecycleState.VOIDED, LifecycleGate.ANNUL),
    (DocumentLifecycleState.REGISTERED, DocumentLifecycleState.VOIDED, LifecycleGate.ANNUL),
)

_STRUCTURALLY_ALLOWED: dict[DocumentLifecycleState, set[DocumentLifecycleState]] = {
    DocumentLifecycleState.DRAFT: {
        DocumentLifecycleState.READY_FOR_SIGNATURE,
        DocumentLifecycleState.VOIDED,
    },
    DocumentLifecycleState.READY_FOR_SIGNATURE: {
        DocumentLifecycleState.DRAFT,
        DocumentLifecycleState.SIGNED,
        DocumentLifecycleState.VOIDED,
    },
    DocumentLifecycleState.SIGNED: {
        DocumentLifecycleState.REGISTERED,
        DocumentLifecycleState.VOIDED,
    },
    DocumentLifecycleState.REGISTERED: {DocumentLifecycleState.VOIDED},
    DocumentLifecycleState.VOIDED: set(),
}


class LifecycleRules:
    """Structural lifecycle transition model per UDE-005."""

    @staticmethod
    def structurally_allowed(
        current: DocumentLifecycleState,
        target: DocumentLifecycleState,
    ) -> bool:
        return target in _STRUCTURALLY_ALLOWED.get(current, set())

    @staticmethod
    def gate_for_transition(
        current: DocumentLifecycleState,
        target: DocumentLifecycleState,
    ) -> LifecycleGate | None:
        for from_state, to_state, gate in _TRANSITION_SPECS:
            if from_state == current and to_state == target:
                return gate
        return None

    @staticmethod
    def possible_transitions(
        current: DocumentLifecycleState,
    ) -> tuple[tuple[DocumentLifecycleState, LifecycleGate], ...]:
        return tuple(
            (to_state, gate)
            for from_state, to_state, gate in _TRANSITION_SPECS
            if from_state == current
        )

    @staticmethod
    def evaluate_transition(
        current: DocumentLifecycleState,
        target: DocumentLifecycleState,
        *,
        gate_ready: bool,
        reason: str | None = None,
    ) -> LifecycleTransition:
        gate = LifecycleRules.gate_for_transition(current, target)
        structurally = LifecycleRules.structurally_allowed(current, target)
        allowed = structurally and gate_ready and gate is not None
        return LifecycleTransition(
            from_state=current,
            to_state=target,
            gate=gate or LifecycleGate.MARK_READY,
            allowed=allowed,
            reason=reason,
        )

    @staticmethod
    def void_kind_for_gate(gate: LifecycleGate) -> str | None:
        if gate == LifecycleGate.CANCEL:
            return "CANCEL"
        if gate == LifecycleGate.ANNUL:
            return "ANNUL"
        return None
