# tests/document_engine/test_party_contracts.py
"""Unit tests for UDE PartyReference contracts (UDE-007)."""
from __future__ import annotations

import dataclasses

import pytest

from app.document_engine.contracts.party import PartyReference, PartyReferenceType


def test_party_reference_minimal_person_mapping_shape() -> None:
    ref = PartyReference(
        reference_type=PartyReferenceType.PERSON,
        reference="138",
        display_name="Synthetic Employee",
    )
    assert ref.reference_type == PartyReferenceType.PERSON
    assert ref.reference == "138"
    assert ref.display_name == "Synthetic Employee"
    assert ref.metadata is None


@pytest.mark.parametrize(
    "reference_type",
    [
        PartyReferenceType.PERSON,
        PartyReferenceType.POSITION_ROLE,
        PartyReferenceType.ORG_UNIT,
        PartyReferenceType.COMMISSION,
        PartyReferenceType.WORKING_GROUP,
        PartyReferenceType.EXTERNAL_PARTY,
    ],
)
def test_party_reference_type_values(reference_type: PartyReferenceType) -> None:
    assert reference_type.value == reference_type.name


def test_party_reference_normalizes_reference() -> None:
    ref = PartyReference(
        reference_type=PartyReferenceType.ORG_UNIT,
        reference="  73  ",
    )
    assert ref.reference == "73"


def test_party_reference_rejects_empty_reference() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        PartyReference(
            reference_type=PartyReferenceType.PERSON,
            reference="",
        )


def test_party_reference_metadata_is_copied() -> None:
    source = {"role": "owner"}
    ref = PartyReference(
        reference_type=PartyReferenceType.POSITION_ROLE,
        reference="role-1",
        metadata=source,
    )
    source["role"] = "changed"
    assert ref.metadata == {"role": "owner"}


def test_party_reference_is_immutable() -> None:
    ref = PartyReference(
        reference_type=PartyReferenceType.PERSON,
        reference="1",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        ref.reference = "2"  # type: ignore[misc]
