# tests/document_engine/editorial/test_editorial_services.py
"""Unit tests for shared editorial runtime (UDE-010)."""
from __future__ import annotations

import pytest

from app.document_engine.editorial.editorial_models import ReviewState
from app.document_engine.editorial.editorial_service import EditorialService
from app.document_engine.editorial.facade import DocumentEngineEditorialFacade
from app.document_engine.editorial.fingerprint_service import FingerprintService
from app.document_engine.editorial.localization_service import LocalizationService
from app.document_engine.editorial.official_draft_builder import OfficialDraftBuilder
from app.document_engine.editorial.override_resolver import OverrideResolver
from app.document_engine.editorial.review_policy import ReviewPolicy
from app.document_engine.read_services.facade import DocumentEngineReadFacade
from app.document_engine.value_objects.identity import DocumentKind
from app.document_engine.value_objects.localization import LocaleCode, StalenessState
from app.document_engine.value_objects.provenance import TextSourceType
from tests.document_engine.adapters._fixtures import (
    synthetic_audit_row,
    synthetic_detail,
    synthetic_editorial_block,
    synthetic_editorial_state,
)


@pytest.fixture
def read_snapshot():
    detail = synthetic_detail()
    return DocumentEngineReadFacade.from_detail(
        detail,
        supplement={"void_kind": None},
        editorial=synthetic_editorial_state(),
        audit_items=[synthetic_audit_row()],
    )


def test_override_resolver_effective_semantics() -> None:
    assert OverrideResolver.resolve_effective(
        generated_text="Generated",
        override_text=None,
    ) == "Generated"
    assert OverrideResolver.resolve_effective(
        generated_text="Generated",
        override_text="Manual",
    ) == "Manual"
    assert OverrideResolver.has_override("  ") is False
    assert OverrideResolver.has_override("Manual") is True


def test_fingerprint_service_is_deterministic() -> None:
    first = FingerprintService.compute_runtime_fingerprint(
        generator_key="title",
        generator_version="1",
        generated_text="Generated title",
        scope="order",
        block_type="title",
        order_item_id=None,
    )
    second = FingerprintService.compute_runtime_fingerprint(
        generator_key="title",
        generator_version="1",
        generated_text="Generated title",
        scope="order",
        block_type="title",
        order_item_id=None,
    )
    assert first.value == second.value
    assert len(first.value) == 64


def test_fingerprint_service_detects_change() -> None:
    fp = FingerprintService.compute_runtime_fingerprint(
        generator_key="title",
        generator_version="1",
        generated_text="A",
        scope="order",
        block_type="title",
        order_item_id=None,
    )
    changed = FingerprintService.compute_runtime_fingerprint(
        generator_key="title",
        generator_version="1",
        generated_text="B",
        scope="order",
        block_type="title",
        order_item_id=None,
    )
    assert FingerprintService.has_generated_changed(
        stored_fingerprint=fp.value,
        current_fingerprint=changed.value,
    )


def test_review_policy_maps_adapter_status() -> None:
    assert ReviewPolicy.from_adapter_review_status("CURRENT") == ReviewState.CURRENT
    assert ReviewPolicy.from_adapter_review_status("STALE") == ReviewState.STALE
    assert ReviewPolicy.from_adapter_review_status("REVIEW_REQUIRED") == ReviewState.REVIEW_REQUIRED
    assert ReviewPolicy.from_adapter_review_status("GENERATION_FAILED") == ReviewState.REVIEW_REQUIRED
    assert ReviewPolicy.from_adapter_review_status("UNKNOWN_STATUS") == ReviewState.UNKNOWN


def test_review_policy_from_staleness() -> None:
    assert ReviewPolicy.from_staleness_state(StalenessState.CURRENT) == ReviewState.CURRENT
    assert ReviewPolicy.from_staleness_state(StalenessState.STALE_FINGERPRINT_MISMATCH) == ReviewState.STALE
    assert ReviewPolicy.from_staleness_state(StalenessState.REVIEW_REQUIRED) == ReviewState.REVIEW_REQUIRED


def test_localization_service_override_block_classification(read_snapshot) -> None:
    views = LocalizationService.from_locale_model(read_snapshot.locale)
    assert len(views) == 2
    ru_view = next(view for view in views if view.locale == LocaleCode.RU)
    assert len(ru_view.effective_blocks) == 2
    assert len(ru_view.generated_blocks) == 2
    assert len(ru_view.override_blocks) == 0


def test_localization_service_override_semantics() -> None:
    detail = synthetic_detail()
    editorial = {
        "order_id": 1001,
        "order_blocks": [
            synthetic_editorial_block(override_text="Manual override"),
        ],
        "items": [],
    }
    snapshot = DocumentEngineReadFacade.from_detail(detail, editorial=editorial)
    views = LocalizationService.from_locale_model(snapshot.locale)
    assert len(views[0].override_blocks) == 1
    block = views[0].override_blocks[0]
    assert block.effective_text == "Manual override"
    assert block.text_source_type == TextSourceType.OVERRIDE
    assert block.review_state == ReviewState.CURRENT


def test_editorial_service_builds_document(read_snapshot) -> None:
    document = EditorialService.from_snapshot(read_snapshot)
    assert document.document_kind == DocumentKind.PERSONNEL_ORDER
    assert len(document.locales) == 2
    assert len(document.sections) == 1
    total_blocks = sum(len(section.blocks) for section in document.sections)
    assert total_blocks == 3


def test_official_draft_builder_no_document_id(read_snapshot) -> None:
    draft = OfficialDraftBuilder.from_snapshot(read_snapshot)
    assert not hasattr(draft, "document_id")
    assert draft.workspace_reference == "po:1001"
    assert draft.item_count == 1
    assert len(draft.locale_blocks) == 3
    assert draft.document_kind == DocumentKind.PERSONNEL_ORDER


def test_editorial_facade_aggregates_all(read_snapshot) -> None:
    snapshot = DocumentEngineEditorialFacade.from_read_snapshot(read_snapshot)
    assert snapshot.editorial.document_kind == DocumentKind.PERSONNEL_ORDER
    assert len(snapshot.localization) == 2
    assert snapshot.official_draft is not None
    assert snapshot.official_draft.item_count == 1


def test_editorial_facade_from_detail() -> None:
    detail = synthetic_detail()
    snapshot = DocumentEngineEditorialFacade.from_detail(
        detail,
        editorial=synthetic_editorial_state(),
    )
    assert snapshot.editorial.legacy_status == "DRAFT"
    assert snapshot.official_draft is not None


def test_editorial_models_are_immutable(read_snapshot) -> None:
    snapshot = DocumentEngineEditorialFacade.from_read_snapshot(read_snapshot)
    with pytest.raises(AttributeError):
        snapshot.editorial.legacy_status = "CHANGED"  # type: ignore[misc]
