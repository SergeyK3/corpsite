# tests/document_engine/test_value_objects.py
"""Unit tests for UDE shared value objects (UDE-007)."""
from __future__ import annotations

import dataclasses
import enum

import pytest

from app.document_engine.value_objects.identity import (
    DocumentId,
    DocumentKind,
    DocumentSpecialization,
)
from app.document_engine.value_objects.lifecycle import (
    ArchiveState,
    DocumentLifecycleState,
    VoidKind,
)
from app.document_engine.value_objects.drafting import DraftingPath
from app.document_engine.value_objects.localization import LocaleCode, StalenessState
from app.document_engine.value_objects.provenance import TextSourceType


def test_document_id_valid_and_normalized() -> None:
    doc_id = DocumentId("  po-42  ")
    assert doc_id.value == "po-42"
    assert str(doc_id) == "po-42"
    assert DocumentId("po-42") == DocumentId("po-42")


@pytest.mark.parametrize("value", ["", "   ", None])
def test_document_id_rejects_empty(value) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        DocumentId(value)  # type: ignore[arg-type]


def test_document_id_is_immutable() -> None:
    doc_id = DocumentId("doc-1")
    with pytest.raises(dataclasses.FrozenInstanceError):
        doc_id.value = "doc-2"  # type: ignore[misc]


@pytest.mark.parametrize(
    "enum_cls,members",
    [
        (
            DocumentLifecycleState,
            (
                "DRAFT",
                "READY_FOR_SIGNATURE",
                "SIGNED",
                "REGISTERED",
                "VOIDED",
            ),
        ),
        (ArchiveState, ("ACTIVE", "ARCHIVED")),
        (VoidKind, ("CANCEL", "ANNUL")),
        (LocaleCode, ("ru", "kk")),
        (DocumentKind, ("PERSONNEL_ORDER", "OPERATIONAL_ORDER")),
        (DocumentSpecialization, ("PERSONNEL", "OPERATIONAL")),
        (
            StalenessState,
            (
                "CURRENT",
                "STALE_SEMANTIC_CHANGE",
                "STALE_RU_CHANGE_AFTER_KK",
                "STALE_FINGERPRINT_MISMATCH",
                "REVIEW_REQUIRED",
            ),
        ),
        (TextSourceType, ("GENERATED", "OVERRIDE", "SUBMITTED", "IMPORTED")),
        (DraftingPath, ("SUBMITTED_TEXT", "OPERATOR_COMPOSED", "IMPORTED")),
    ],
)
def test_enum_members_are_str_enums(enum_cls, members) -> None:
    assert issubclass(enum_cls, enum.Enum)
    assert issubclass(enum_cls, str)
    assert tuple(member.value for member in enum_cls) == members


def test_document_lifecycle_state_values_match_po_constants() -> None:
    from app.db.models.personnel_orders import ORDER_STATUSES

    shared_values = {state.value for state in DocumentLifecycleState}
    assert shared_values == set(ORDER_STATUSES)


def test_void_kind_values_match_po_constants() -> None:
    from app.db.models.personnel_orders import VOID_KINDS

    shared_values = {kind.value for kind in VoidKind}
    assert shared_values == set(VOID_KINDS)


def test_locale_code_values_match_po_constants() -> None:
    from app.db.models.personnel_orders import LOCALE_KK, LOCALE_RU

    assert LocaleCode.RU.value == LOCALE_RU
    assert LocaleCode.KK.value == LOCALE_KK
