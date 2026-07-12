# tests/document_engine/lifecycle/test_lifecycle_compatibility.py
"""Compatibility tests — upstream snapshots vs lifecycle evaluation (UDE-011)."""
from __future__ import annotations

from app.document_engine.lifecycle.compatibility import (
    build_lifecycle_compatibility_report,
    format_lifecycle_compatibility_report,
)
from app.document_engine.lifecycle.facade import DocumentEngineLifecycleFacade
from app.document_engine.read_services.facade import DocumentEngineReadFacade
from tests.document_engine.adapters._fixtures import (
    synthetic_audit_row,
    synthetic_detail,
    synthetic_editorial_state,
)


def test_lifecycle_preserves_read_and_editorial_state() -> None:
    detail = synthetic_detail()
    read_snapshot = DocumentEngineReadFacade.from_detail(
        detail,
        supplement={"void_kind": None},
        editorial=synthetic_editorial_state(),
        audit_items=[synthetic_audit_row()],
    )
    report = build_lifecycle_compatibility_report(read_snapshot)
    assert report.is_compatible is True
    assert "compatible" in format_lifecycle_compatibility_report(report)


def test_read_editorial_lifecycle_chain() -> None:
    detail = synthetic_detail()
    read_snapshot = DocumentEngineReadFacade.from_detail(
        detail,
        editorial=synthetic_editorial_state(),
    )
    lifecycle_snapshot = DocumentEngineLifecycleFacade.from_read_snapshot(read_snapshot)
    assert lifecycle_snapshot.evaluation is not None
    assert (
        lifecycle_snapshot.evaluation.lifecycle.lifecycle_state
        == read_snapshot.document.lifecycle_state
    )
    assert (
        lifecycle_snapshot.evaluation.decision.current_state
        == read_snapshot.document.lifecycle_state
    )


def test_lifecycle_does_not_assign_document_id() -> None:
    detail = synthetic_detail()
    snapshot = DocumentEngineLifecycleFacade.from_detail(
        detail,
        editorial=synthetic_editorial_state(),
    )
    assert snapshot.activation is not None
    assert not hasattr(snapshot.activation, "document_id")
    draft = snapshot.evaluation.promotion_readiness if snapshot.evaluation else None
    assert draft is not None or snapshot.promotion_readiness is not None
