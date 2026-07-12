# tests/document_engine/adapters/test_personnel_adapters.py
"""Unit and golden mapping tests for Personnel read adapters (UDE-008)."""
from __future__ import annotations

import pytest

from app.document_engine.adapters.personnel.audit import PersonnelAuditAdapter
from app.document_engine.adapters.personnel.compatibility import (
    build_compatibility_report,
    format_compatibility_report,
)
from app.document_engine.adapters.personnel.document import PersonnelDocumentAdapter
from app.document_engine.adapters.personnel.item import PersonnelItemAdapter
from app.document_engine.adapters.personnel.lifecycle import PersonnelLifecycleAdapter
from app.document_engine.adapters.personnel.locale import PersonnelLocaleAdapter
from app.document_engine.adapters.personnel.party import PersonnelPartyAdapter
from app.document_engine.adapters.personnel.print import PersonnelPrintAdapter
from app.document_engine.adapters.personnel.read_adapter import PersonnelReadAdapter
from app.document_engine.contracts.party import PartyReferenceType
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


def test_document_adapter_golden_mapping() -> None:
    header = synthetic_order_header(status="REGISTERED")
    view = PersonnelDocumentAdapter.from_header(
        header,
        supplement={"void_kind": "ANNUL"},
    )
    assert view.document_id.value == "po:1001"
    assert view.document_kind == DocumentKind.PERSONNEL_ORDER
    assert view.specialization == DocumentSpecialization.PERSONNEL
    assert view.lifecycle_state == DocumentLifecycleState.REGISTERED
    assert view.archive_state == ArchiveState.ACTIVE
    assert view.void_kind == VoidKind.ANNUL
    assert view.metadata.order_number == "SYN-1001"


def test_lifecycle_adapter_direct_mapping() -> None:
    header = synthetic_order_header(status="READY_FOR_SIGNATURE", is_archived=True)
    assert PersonnelLifecycleAdapter.lifecycle_state(header) == DocumentLifecycleState.READY_FOR_SIGNATURE
    assert PersonnelLifecycleAdapter.archive_state(header) == ArchiveState.ARCHIVED
    assert PersonnelLifecycleAdapter.void_kind(header, supplement={"void_kind": "CANCEL"}) == VoidKind.CANCEL


def test_party_adapter_event_subject_not_responsible_party() -> None:
    item = synthetic_item(employee_id=42)
    party = PersonnelPartyAdapter.from_item(item)
    assert party is not None
    assert party.reference_type == PartyReferenceType.PERSON
    assert party.reference == "42"
    assert party.metadata == {"po_role": "event_subject"}


def test_party_adapter_allows_missing_employee_for_hire() -> None:
    item = synthetic_item(employee_id=None)
    assert PersonnelPartyAdapter.from_item(item) is None


def test_locale_adapter_editorial_override_semantics() -> None:
    block = synthetic_editorial_block(override_text="Manual override")
    view = PersonnelLocaleAdapter.from_editorial_block(block)
    assert view.locale == LocaleCode.RU
    assert view.text_source_type == TextSourceType.OVERRIDE
    assert view.effective_text == "Manual override"
    assert view.staleness_state == StalenessState.CURRENT


def test_locale_adapter_legacy_snapshot_mapping() -> None:
    detail = synthetic_detail()
    snapshots = PersonnelLocaleAdapter.from_localized_texts(detail["localized_texts"])
    assert len(snapshots) == 2
    assert snapshots[0].locale == LocaleCode.RU
    assert snapshots[1].locale == LocaleCode.KK


def test_item_adapter_rate_change_display_alias() -> None:
    item = synthetic_item(
        item_type_code="TRANSFER",
        payload={"to_rate": 0.5},
    )
    view = PersonnelItemAdapter.from_item(item)
    assert view.backend_item_type_code == "TRANSFER"
    assert view.display_item_type_code == "RATE_CHANGE"


@pytest.mark.parametrize(
    "item_type",
    ["HIRE", "TRANSFER", "TERMINATION", "CONCURRENT_DUTY_START", "CONCURRENT_DUTY_END"],
)
def test_item_adapter_supported_backend_types(item_type: str) -> None:
    item = synthetic_item(item_type_code=item_type)
    view = PersonnelItemAdapter.from_item(item)
    assert view.backend_item_type_code == item_type


def test_audit_adapter_append_only_shape() -> None:
    row = synthetic_audit_row()
    event = PersonnelAuditAdapter.from_audit_row(row)
    assert event.action == "CANCEL"
    assert event.new_void_kind == VoidKind.CANCEL
    assert event.metadata_json["permission_used"] == "PERSONNEL_ORDERS_CANCEL_OWN"


def test_print_adapter_status_mark_mapping() -> None:
    assert PersonnelPrintAdapter.status_mark_for_lifecycle("DRAFT") == "draft"
    assert PersonnelPrintAdapter.status_mark_for_lifecycle("READY_FOR_SIGNATURE") == "unsigned"
    assert PersonnelPrintAdapter.status_mark_for_lifecycle("VOIDED") == "cancelled"
    assert PersonnelPrintAdapter.status_mark_for_lifecycle("REGISTERED") == "none"


def test_print_adapter_voided_archived_still_printable() -> None:
    header = synthetic_order_header(status="VOIDED", is_archived=True)
    view = PersonnelPrintAdapter.from_header_and_prints(header, [])
    assert view.printable is True
    assert view.status_mark == "cancelled"


def test_read_adapter_facade_aggregates_all_views() -> None:
    detail = synthetic_detail()
    editorial = synthetic_editorial_state()
    audit = [synthetic_audit_row()]
    bundle = PersonnelReadAdapter.from_detail(
        detail,
        supplement={"void_kind": "CANCEL"},
        editorial=editorial,
        audit_items=audit,
    )
    assert bundle.document.document_id.value == "po:1001"
    assert len(bundle.items) == 1
    assert len(bundle.locale_blocks) == 3
    assert len(bundle.locale_snapshots) == 2
    assert len(bundle.audit_events) == 1
    assert len(bundle.event_subjects) == 1
    assert bundle.print_view is not None


def test_compatibility_harness_reports_no_differences_for_synthetic_detail() -> None:
    detail = synthetic_detail()
    report = build_compatibility_report(detail, supplement={"void_kind": None})
    assert report.is_compatible is True
    assert "compatible" in format_compatibility_report(report)


def test_compatibility_harness_surfaces_void_kind_api_gap() -> None:
    detail = synthetic_detail()
    bundle = PersonnelReadAdapter.from_detail(
        detail,
        supplement={"void_kind": "CANCEL"},
    )
    assert detail["order"].get("void_kind") is None
    assert bundle.document.void_kind == VoidKind.CANCEL
