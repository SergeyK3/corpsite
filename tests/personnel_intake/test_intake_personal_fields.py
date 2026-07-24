"""Unit tests for intake personal payload fields."""
from __future__ import annotations

from app.personnel_intake.domain.models import empty_intake_draft_payload


def test_empty_intake_draft_payload_includes_personal_card_fields() -> None:
    payload = empty_intake_draft_payload()
    assert payload["personal"]["birth_place"] == ""
    assert payload["personal"]["personnel_number"] == ""
