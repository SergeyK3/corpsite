# tests/document_engine/read_services/test_read_service_compatibility.py
"""Compatibility tests — adapter bundle vs read service snapshot (UDE-009)."""
from __future__ import annotations

from app.document_engine.adapters.personnel.compatibility import (
    build_compatibility_report,
    format_compatibility_report,
)
from app.document_engine.adapters.personnel.read_adapter import PersonnelReadAdapter
from app.document_engine.read_services.compatibility import (
    compare_bundle_to_read_snapshot,
    format_read_service_compatibility_report,
)
from app.document_engine.read_services.facade import DocumentEngineReadFacade
from tests.document_engine.adapters._fixtures import (
    synthetic_audit_row,
    synthetic_detail,
    synthetic_editorial_state,
)


def test_read_service_matches_adapter_for_synthetic_detail() -> None:
    detail = synthetic_detail()
    bundle = PersonnelReadAdapter.from_detail(
        detail,
        supplement={"void_kind": None},
        editorial=synthetic_editorial_state(),
        audit_items=[synthetic_audit_row()],
    )
    snapshot = DocumentEngineReadFacade.from_bundle(bundle)
    report = compare_bundle_to_read_snapshot(bundle, snapshot)
    assert report.is_compatible is True
    assert "compatible" in format_read_service_compatibility_report(report)


def test_legacy_to_adapter_to_read_service_chain() -> None:
    detail = synthetic_detail()
    adapter_report = build_compatibility_report(
        detail,
        supplement={"void_kind": None},
        editorial=synthetic_editorial_state(),
        audit_items=[synthetic_audit_row()],
    )
    assert adapter_report.is_compatible is True
    assert "compatible" in format_compatibility_report(adapter_report)

    bundle = PersonnelReadAdapter.from_detail(
        detail,
        supplement={"void_kind": None},
        editorial=synthetic_editorial_state(),
        audit_items=[synthetic_audit_row()],
    )
    snapshot = DocumentEngineReadFacade.from_detail(
        detail,
        supplement={"void_kind": None},
        editorial=synthetic_editorial_state(),
        audit_items=[synthetic_audit_row()],
    )
    read_report = compare_bundle_to_read_snapshot(bundle, snapshot)
    assert read_report.is_compatible is True


def test_read_service_preserves_void_kind_supplement_gap() -> None:
    """Document known void_kind API gap — read service must not mask it."""
    detail = synthetic_detail()
    bundle = PersonnelReadAdapter.from_detail(
        detail,
        supplement={"void_kind": "CANCEL"},
    )
    snapshot = DocumentEngineReadFacade.from_bundle(bundle)
    assert detail["order"].get("void_kind") is None
    assert snapshot.document.void_kind is not None
    assert snapshot.lifecycle.void_kind is not None
    report = compare_bundle_to_read_snapshot(bundle, snapshot)
    assert report.is_compatible is True
