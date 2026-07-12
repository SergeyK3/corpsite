# tests/document_engine/editorial/test_editorial_compatibility.py
"""Compatibility tests — read model vs editorial model (UDE-010)."""
from __future__ import annotations

from app.document_engine.editorial.compatibility import (
    build_editorial_compatibility_report,
    format_editorial_compatibility_report,
)
from app.document_engine.editorial.facade import DocumentEngineEditorialFacade
from app.document_engine.read_services.facade import DocumentEngineReadFacade
from tests.document_engine.adapters._fixtures import (
    synthetic_audit_row,
    synthetic_detail,
    synthetic_editorial_block,
    synthetic_editorial_state,
)


def test_editorial_preserves_read_model_information() -> None:
    detail = synthetic_detail()
    read_snapshot = DocumentEngineReadFacade.from_detail(
        detail,
        supplement={"void_kind": None},
        editorial=synthetic_editorial_state(),
        audit_items=[synthetic_audit_row()],
    )
    report = build_editorial_compatibility_report(read_snapshot)
    assert report.is_compatible is True
    assert "compatible" in format_editorial_compatibility_report(report)


def test_read_to_editorial_chain_matches_facade() -> None:
    detail = synthetic_detail()
    read_snapshot = DocumentEngineReadFacade.from_detail(
        detail,
        editorial=synthetic_editorial_state(),
    )
    editorial_snapshot = DocumentEngineEditorialFacade.from_read_snapshot(read_snapshot)
    assert len(read_snapshot.locale.blocks) == sum(
        len(locale.blocks) for locale in editorial_snapshot.editorial.locales
    )
    assert read_snapshot.document.document_kind == editorial_snapshot.editorial.document_kind
    assert editorial_snapshot.official_draft is not None
    assert editorial_snapshot.official_draft.workspace_reference == read_snapshot.document.document_id.value


def test_override_effective_preserved_in_editorial() -> None:
    detail = synthetic_detail()
    editorial = {
        "order_id": 1001,
        "order_blocks": [
            synthetic_editorial_block(override_text="Manual override"),
        ],
        "items": [],
    }
    read_snapshot = DocumentEngineReadFacade.from_detail(detail, editorial=editorial)
    report = build_editorial_compatibility_report(read_snapshot)
    assert report.is_compatible is True
    block = read_snapshot.locale.blocks[0]
    editorial_block = editorial_snapshot_block(read_snapshot)
    assert block.effective_text == editorial_block.effective_text


def editorial_snapshot_block(read_snapshot):
    editorial = DocumentEngineEditorialFacade.from_read_snapshot(read_snapshot)
    return editorial.editorial.locales[0].blocks[0]
