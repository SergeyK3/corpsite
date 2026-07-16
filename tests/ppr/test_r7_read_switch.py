# tests/ppr/test_r7_read_switch.py
"""Read-switch dispatcher tests for PPR R7."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.ppr.application.config import PprReadPathConfigError
from app.ppr.domain.errors import PprReadLegacyAdapterError
from app.ppr.domain.identity_models import (
    INPUT_KIND_EMPLOYEE_ID,
    IdentityResolution,
    PersonIdentitySnapshot,
    RESULT_DIRECT,
)
from app.ppr.domain.models import PPR_LIFECYCLE_NOT_MATERIALIZED
from app.ppr.domain.person_models import PersonGeneralReadSnapshot
from app.ppr.domain.section_models import SECTION_CODE_PPR_EDUCATION, SECTION_CODE_PPR_FAMILY, SECTION_CODE_PPR_TRAINING
from app.ppr.read.models import PprCompositeReadMetadata, PprCompositeReadModel, PprSectionAggregation
from app.ppr.read.query_service import PprQueryApplicationService
from app.services.personnel_card_read_dispatcher import PersonnelCardReadDispatcher


def _fake_composite(person_id: int = 1, employee_id: int = 2) -> PprCompositeReadModel:
    now = datetime.now(UTC)
    resolution = IdentityResolution(
        input_kind=INPUT_KIND_EMPLOYEE_ID,
        input_id=employee_id,
        employee_id=employee_id,
        source_person_id=person_id,
        resolved_person_id=person_id,
        merge_redirected=False,
        merge_chain=(person_id,),
        result_code=RESULT_DIRECT,
    )
    identity = PersonIdentitySnapshot(
        person_id=person_id,
        person_status="active",
        merged_into_person_id=None,
        match_key="test",
        iin=None,
    )
    general = PersonGeneralReadSnapshot(
        person_id=person_id,
        full_name="Test Person",
        last_name=None,
        first_name=None,
        middle_name=None,
        birth_date=None,
        iin=None,
        created_at=now,
        updated_at=now,
    )
    return PprCompositeReadModel(
        person_id=person_id,
        employee_id=employee_id,
        materialized=False,
        lifecycle_state=PPR_LIFECYCLE_NOT_MATERIALIZED,
        hr_relationship_context=None,
        envelope_version=None,
        envelope_created_at=None,
        envelope_updated_at=None,
        identity=identity,
        identity_resolution=resolution,
        general=general,
        education=PprSectionAggregation(section_code=SECTION_CODE_PPR_EDUCATION, active=()),
        training=PprSectionAggregation(section_code=SECTION_CODE_PPR_TRAINING, active=()),
        family=PprSectionAggregation(section_code=SECTION_CODE_PPR_FAMILY, active=()),
        events=None,
        intended_employment=None,
        metadata=PprCompositeReadMetadata(
            evaluated_at=now,
            source_person_id=person_id,
            merge_redirected=False,
        ),
    )


@pytest.fixture
def legacy_card():
    return {
        "employee_id": 42,
        "full_name": "Test Person",
        "profile": {"basic": {"iin": None, "birth_date": None}, "education": [], "training": []},
    }


def test_legacy_mode_calls_legacy_only(legacy_card, monkeypatch):
    monkeypatch.setenv("PPR_READ_PATH_MODE", "legacy")
    query = MagicMock(spec=PprQueryApplicationService)
    dispatcher = PersonnelCardReadDispatcher(query_service=query)
    conn = MagicMock()
    with patch(
        "app.services.personnel_card_read_dispatcher.get_employee_import_card",
        return_value=legacy_card,
    ) as legacy_fn:
        result = dispatcher.load_import_card(conn, 42)
    assert result == legacy_card
    legacy_fn.assert_called_once_with(conn, 42)
    query.load_by_employee_id.assert_not_called()


def test_shadow_mode_returns_legacy_and_calls_ppr(legacy_card, monkeypatch):
    monkeypatch.setenv("PPR_READ_PATH_MODE", "shadow")
    query = MagicMock(spec=PprQueryApplicationService)
    query.load_by_employee_id.return_value = _fake_composite()
    dispatcher = PersonnelCardReadDispatcher(query_service=query)
    conn = MagicMock()
    with patch(
        "app.services.personnel_card_read_dispatcher.get_employee_import_card",
        return_value=legacy_card,
    ):
        result = dispatcher.load_import_card(conn, 42)
    assert result == legacy_card
    query.load_by_employee_id.assert_called_once_with(42)


def test_shadow_ppr_error_does_not_break_legacy(legacy_card, monkeypatch):
    monkeypatch.setenv("PPR_READ_PATH_MODE", "shadow")
    query = MagicMock(spec=PprQueryApplicationService)
    query.load_by_employee_id.side_effect = RuntimeError("ppr down")
    dispatcher = PersonnelCardReadDispatcher(query_service=query)
    conn = MagicMock()
    with patch(
        "app.services.personnel_card_read_dispatcher.get_employee_import_card",
        return_value=legacy_card,
    ):
        result = dispatcher.load_import_card(conn, 42)
    assert result == legacy_card


def test_ppr_mode_blocked_without_adapter(monkeypatch):
    monkeypatch.setenv("PPR_READ_PATH_MODE", "ppr")
    monkeypatch.delenv("PPR_READ_LEGACY_ADAPTER_ENABLED", raising=False)
    dispatcher = PersonnelCardReadDispatcher(query_service=MagicMock())
    conn = MagicMock()
    with pytest.raises(PprReadLegacyAdapterError):
        dispatcher.load_import_card(conn, 42)


def test_ppr_mode_calls_query_not_legacy(monkeypatch):
    monkeypatch.setenv("PPR_READ_PATH_MODE", "ppr")
    monkeypatch.setenv("PPR_READ_LEGACY_ADAPTER_ENABLED", "true")
    query = MagicMock(spec=PprQueryApplicationService)
    query.load_by_employee_id.return_value = _fake_composite()
    dispatcher = PersonnelCardReadDispatcher(query_service=query)
    conn = MagicMock()
    with patch("app.services.personnel_card_read_dispatcher.get_employee_import_card") as legacy_fn:
        result = dispatcher.load_import_card(conn, 42)
    legacy_fn.assert_not_called()
    assert result["ppr_read_adapter"] is True
    assert result["resolved_person_id"] == 1


def test_invalid_mode_rejected(monkeypatch):
    monkeypatch.setenv("PPR_READ_PATH_MODE", "invalid-mode")
    with pytest.raises(PprReadPathConfigError):
        PersonnelCardReadDispatcher().load_import_card(MagicMock(), 1)


def test_production_shadow_blocked_without_allow(monkeypatch):
    monkeypatch.setenv("PPR_READ_PATH_MODE", "shadow")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("PPR_READ_PATH_ALLOW_PRODUCTION", raising=False)
    with pytest.raises(PprReadPathConfigError):
        PersonnelCardReadDispatcher().load_import_card(MagicMock(), 1)


def test_shadow_comparator_match(legacy_card):
    from app.ppr.application.shadow_comparator import SHADOW_RESULT_MATCH, compare_legacy_import_card_to_ppr

    result = compare_legacy_import_card_to_ppr(legacy_card, _fake_composite())
    assert result.result == SHADOW_RESULT_MATCH
    assert result.mismatch_fields == ()


def test_shadow_comparator_mismatch_on_name(legacy_card):
    from app.ppr.application.shadow_comparator import SHADOW_RESULT_MISMATCH, compare_legacy_import_card_to_ppr

    legacy_card["full_name"] = "Different Name"
    result = compare_legacy_import_card_to_ppr(legacy_card, _fake_composite())
    assert result.result == SHADOW_RESULT_MISMATCH
    assert "full_name" in result.mismatch_fields
