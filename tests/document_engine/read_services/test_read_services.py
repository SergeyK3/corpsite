# tests/document_engine/read_services/test_read_services.py
"""Unit tests for shared read services (UDE-009)."""
from __future__ import annotations

import pytest

from app.document_engine.adapters.personnel.read_adapter import PersonnelReadAdapter
from app.document_engine.contracts.party import PartyReferenceType
from app.document_engine.read_services.audit import AuditReadService
from app.document_engine.read_services.document import DocumentReadService
from app.document_engine.read_services.facade import DocumentEngineReadFacade
from app.document_engine.read_services.item import ItemReadService
from app.document_engine.read_services.lifecycle import LifecycleReadService
from app.document_engine.read_services.localization import LocalizationReadService
from app.document_engine.read_services.print import PrintReadService
from app.document_engine.value_objects.identity import DocumentKind, DocumentSpecialization
from app.document_engine.value_objects.lifecycle import ArchiveState, DocumentLifecycleState, VoidKind
from app.document_engine.value_objects.localization import LocaleCode, StalenessState
from app.document_engine.value_objects.provenance import TextSourceType
from tests.document_engine.adapters._fixtures import (
    synthetic_audit_row,
    synthetic_detail,
    synthetic_editorial_block,
    synthetic_editorial_state,
    synthetic_item,
    synthetic_order_header,
)


@pytest.fixture
def full_bundle():
    detail = synthetic_detail()
    return PersonnelReadAdapter.from_detail(
        detail,
        supplement={"void_kind": "CANCEL"},
        editorial=synthetic_editorial_state(),
        audit_items=[synthetic_audit_row()],
    )


def test_document_read_service_maps_from_bundle(full_bundle) -> None:
    model = DocumentReadService.from_bundle(full_bundle)
    assert model.document_id.value == "po:1001"
    assert model.document_kind == DocumentKind.PERSONNEL_ORDER
    assert model.specialization == DocumentSpecialization.PERSONNEL
    assert model.lifecycle_state == DocumentLifecycleState.DRAFT
    assert model.void_kind == VoidKind.CANCEL
    assert model.metadata.order_number == "SYN-1001"


def test_document_read_service_from_detail() -> None:
    detail = synthetic_detail()
    model = DocumentReadService.from_detail(detail, supplement={"void_kind": None})
    assert model.document_id.value == "po:1001"
    assert model.is_archived is False


def test_lifecycle_read_service_from_header() -> None:
    header = synthetic_order_header(status="REGISTERED", is_archived=True)
    model = LifecycleReadService.from_header(header, supplement={"void_kind": "ANNUL"})
    assert model.lifecycle_state == DocumentLifecycleState.REGISTERED
    assert model.archive_state == ArchiveState.ARCHIVED
    assert model.void_kind == VoidKind.ANNUL


def test_lifecycle_read_service_from_bundle_matches_document(full_bundle) -> None:
    lifecycle = LifecycleReadService.from_bundle(full_bundle)
    document = DocumentReadService.from_bundle(full_bundle)
    assert lifecycle.document_id == document.document_id
    assert lifecycle.lifecycle_state == document.lifecycle_state
    assert lifecycle.archive_state == document.archive_state
    assert lifecycle.void_kind == document.void_kind


def test_localization_read_service_editorial_blocks() -> None:
    editorial = synthetic_editorial_state()
    model = LocalizationReadService.from_editorial_state(editorial)
    assert len(model.blocks) == 3
    assert model.blocks[0].locale == LocaleCode.RU
    assert model.blocks[0].effective_text == "Generated title"


def test_localization_read_service_override_semantics() -> None:
    block = synthetic_editorial_block(override_text="Manual override")
    editorial = {"order_id": 1001, "order_blocks": [block], "items": []}
    model = LocalizationReadService.from_editorial_state(editorial)
    assert model.blocks[0].text_source_type == TextSourceType.OVERRIDE
    assert model.blocks[0].effective_text == "Manual override"
    assert model.blocks[0].staleness_state == StalenessState.CURRENT


def test_localization_read_service_legacy_snapshots() -> None:
    detail = synthetic_detail()
    model = LocalizationReadService.from_localized_texts(detail["localized_texts"])
    assert len(model.snapshots) == 2
    assert model.snapshots[0].locale == LocaleCode.RU
    assert model.snapshots[1].locale == LocaleCode.KK


def test_localization_read_service_from_bundle(full_bundle) -> None:
    model = LocalizationReadService.from_bundle(full_bundle)
    assert len(model.blocks) == 3
    assert len(model.snapshots) == 2


def test_audit_read_service_append_only(full_bundle) -> None:
    model = AuditReadService.from_bundle(full_bundle)
    assert model.document_order_id == 1001
    assert len(model.events) == 1
    event = model.events[0]
    assert event.action == "CANCEL"
    assert event.new_void_kind == VoidKind.CANCEL
    assert event.metadata_json["permission_used"] == "PERSONNEL_ORDERS_CANCEL_OWN"


def test_audit_read_service_from_rows() -> None:
    model = AuditReadService.from_audit_rows([synthetic_audit_row()])
    assert len(model.events) == 1
    assert model.document_order_id == 1001


def test_print_read_service_status_mark() -> None:
    header = synthetic_order_header(status="VOIDED", is_archived=True)
    model = PrintReadService.from_header_and_prints(header, [])
    assert model.printable is True
    assert model.status_mark == "cancelled"
    assert model.lifecycle_state == DocumentLifecycleState.VOIDED


def test_print_read_service_from_bundle(full_bundle) -> None:
    model = PrintReadService.from_bundle(full_bundle)
    assert model is not None
    assert model.order_id == 1001
    assert model.records == ()


@pytest.mark.parametrize(
    "item_type",
    ["HIRE", "TRANSFER", "TERMINATION", "CONCURRENT_DUTY_START", "CONCURRENT_DUTY_END"],
)
def test_item_read_service_supported_types(item_type: str) -> None:
    items = ItemReadService.from_items([synthetic_item(item_type_code=item_type)])
    assert items[0].backend_item_type_code == item_type


def test_item_read_service_rate_change_alias() -> None:
    item = synthetic_item(item_type_code="TRANSFER", payload={"to_rate": 0.5})
    model = ItemReadService.from_items([item])[0]
    assert model.backend_item_type_code == "TRANSFER"
    assert model.display_item_type_code == "RATE_CHANGE"


def test_item_read_service_event_subject(full_bundle) -> None:
    items = ItemReadService.from_bundle(full_bundle)
    assert len(items) == 1
    subject = items[0].event_subject
    assert subject is not None
    assert subject.reference_type == PartyReferenceType.PERSON
    assert subject.reference == "42"


def test_read_facade_aggregates_all_services(full_bundle) -> None:
    snapshot = DocumentEngineReadFacade.from_bundle(full_bundle)
    assert snapshot.document.document_id.value == "po:1001"
    assert snapshot.lifecycle.lifecycle_state == DocumentLifecycleState.DRAFT
    assert len(snapshot.items) == 1
    assert len(snapshot.locale.blocks) == 3
    assert len(snapshot.locale.snapshots) == 2
    assert snapshot.audit is not None
    assert len(snapshot.audit.events) == 1
    assert snapshot.print_view is not None
    assert len(snapshot.event_subjects) == 1


def test_read_facade_from_detail() -> None:
    detail = synthetic_detail()
    snapshot = DocumentEngineReadFacade.from_detail(
        detail,
        supplement={"void_kind": None},
        editorial=synthetic_editorial_state(),
        audit_items=[synthetic_audit_row()],
    )
    assert snapshot.document.document_id.value == "po:1001"
    assert snapshot.audit is not None


def test_read_models_are_frozen(full_bundle) -> None:
    snapshot = DocumentEngineReadFacade.from_bundle(full_bundle)
    with pytest.raises(AttributeError):
        snapshot.document.legacy_status = "CHANGED"  # type: ignore[misc]
