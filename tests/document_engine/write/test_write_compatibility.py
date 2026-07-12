# tests/document_engine/write/test_write_compatibility.py
"""Compatibility tests — lifecycle runtime vs write runtime (UDE-012)."""
from __future__ import annotations

from app.document_engine.write.compatibility import (
    compare_aggregate_to_lifecycle,
    format_write_compatibility_report,
)
from app.document_engine.write.facade import DocumentEngineWriteFacade
from tests.document_engine.adapters._fixtures import (
    synthetic_audit_row,
    synthetic_detail,
    synthetic_editorial_state,
)


def test_aggregate_aligns_with_lifecycle_runtime() -> None:
    detail = synthetic_detail()
    context = DocumentEngineWriteFacade.build_context_from_detail(
        detail,
        supplement={"void_kind": None},
        editorial=synthetic_editorial_state(),
        audit_items=[synthetic_audit_row()],
    )
    aggregate = context.aggregate
    assert aggregate is not None
    report = compare_aggregate_to_lifecycle(aggregate, context.lifecycle_snapshot)
    assert report.is_compatible is True
    assert "compatible" in format_write_compatibility_report(report)


def test_write_create_preserves_lifecycle_state() -> None:
    detail = synthetic_detail()
    context = DocumentEngineWriteFacade.build_context_from_detail(
        detail,
        editorial=synthetic_editorial_state(),
    )
    result = DocumentEngineWriteFacade.create_from_draft(context)
    assert result.aggregate is not None
    assert (
        result.aggregate.lifecycle_state
        == context.lifecycle_snapshot.evaluation.lifecycle.lifecycle_state
    )


def test_write_has_no_side_effects_on_upstream() -> None:
    detail = synthetic_detail()
    context = DocumentEngineWriteFacade.build_context_from_detail(
        detail,
        editorial=synthetic_editorial_state(),
    )
    original_state = context.lifecycle_snapshot.evaluation.lifecycle.lifecycle_state
    DocumentEngineWriteFacade.promote_from_draft(context)
    assert (
        context.lifecycle_snapshot.evaluation.lifecycle.lifecycle_state == original_state
    )
