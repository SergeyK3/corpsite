"""Unit tests for intake personal payload fields."""
from __future__ import annotations

from app.personnel_intake.domain.models import empty_intake_draft_payload


def test_empty_intake_draft_payload_is_public_canonical_without_personnel_number() -> None:
    payload = empty_intake_draft_payload()
    assert payload["schema_version"] == 2
    assert payload["personal"]["birth_place"] is None
    assert payload["personal"]["photo_file_id"] is None
    assert "personnel_number" not in payload["personal"]
