"""Tests for production-safe demo Family seed ops script."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from scripts.ops.create_demo_ppr_applicants import ALLOWED_IINS, APPLICANTS, PersonAudit
from scripts.ops.seed_demo_family import (
    DEMO_FAMILY_BY_KEY,
    _build_payload,
    _demo_person_specs,
    _require_execute_allowed,
    build_seed_plan,
    parse_db_target,
    plan_record_action,
    run,
)


def test_demo_person_specs_use_whitelisted_iins_only() -> None:
    specs = _demo_person_specs()
    assert {spec["iin"] for spec in specs} <= ALLOWED_IINS
    assert {spec["key"] for spec in specs} == set(DEMO_FAMILY_BY_KEY.keys())
    assert len(specs) == len(APPLICANTS)


def test_build_payload_relative_includes_metadata_key() -> None:
    record = DEMO_FAMILY_BY_KEY["ahmetov"][0]
    payload = _build_payload(record)
    assert payload["relationship_type"] == "spouse"
    assert payload["full_name"] == "Ахметова Гульнара Сериковна"
    assert payload["birth_date"] == date(1992, 6, 15)
    assert payload["metadata"]["demo_record_key"] == "ahmetov:relative:spouse"
    assert payload["metadata"]["demo_suite"] == "family_v1"


def test_build_payload_includes_organization_name() -> None:
    record = DEMO_FAMILY_BY_KEY["seitova"][0]
    payload = _build_payload(record)
    assert payload["organization_name"] == "ТОО «СтройСервис»"


def test_plan_record_action_dry_run_create() -> None:
    audit = PersonAudit(
        exists=True,
        person_id=501,
        full_name="Ахметов Айдар Серикович",
        person_status="active",
        match_key="demo:ppr-applicant:ahmetov",
        source="demo_ppr_applicant",
        hr_relationship_context="CANDIDATE",
        has_active_employee=False,
        demo_marked=True,
        safe_to_touch=True,
        block_reason=None,
    )
    action = plan_record_action(
        person_spec={"key": "ahmetov", "iin": "900101350123"},
        audit=audit,
        record_spec=DEMO_FAMILY_BY_KEY["ahmetov"][0],
        materialized=True,
        exists=False,
        execute=False,
    )
    assert action.action == "dry_run_create"


def test_plan_record_action_skips_existing() -> None:
    audit = PersonAudit(
        exists=True,
        person_id=501,
        full_name="Ахметов Айдар Серикович",
        person_status="active",
        match_key="demo:ppr-applicant:ahmetov",
        source="demo_ppr_applicant",
        hr_relationship_context="CANDIDATE",
        has_active_employee=False,
        demo_marked=True,
        safe_to_touch=True,
        block_reason=None,
    )
    action = plan_record_action(
        person_spec={"key": "ahmetov", "iin": "900101350123"},
        audit=audit,
        record_spec=DEMO_FAMILY_BY_KEY["ahmetov"][0],
        materialized=True,
        exists=True,
        execute=True,
    )
    assert action.action == "skipped"
    assert action.detail == "active demo record already exists"


def test_plan_record_action_skips_unmaterialized() -> None:
    audit = PersonAudit(
        exists=True,
        person_id=501,
        full_name="Ахметов Айдар Серикович",
        person_status="active",
        match_key="demo:ppr-applicant:ahmetov",
        source="demo_ppr_applicant",
        hr_relationship_context="CANDIDATE",
        has_active_employee=False,
        demo_marked=True,
        safe_to_touch=True,
        block_reason=None,
    )
    action = plan_record_action(
        person_spec={"key": "ahmetov", "iin": "900101350123"},
        audit=audit,
        record_spec=DEMO_FAMILY_BY_KEY["ahmetov"][0],
        materialized=False,
        exists=False,
        execute=True,
    )
    assert action.action == "skipped"
    assert "not materialized" in (action.detail or "")


def test_require_execute_allowed_blocks_production_without_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CORPSITE_ALLOW_DEMO_PPR_SEED", raising=False)
    target = parse_db_target("postgresql://user:pass@46.247.42.47:5432/corpsite")
    with pytest.raises(SystemExit):
        _require_execute_allowed(target, execute=True)


def test_build_seed_plan_dry_run_counts_creates(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = MagicMock()
    monkeypatch.setattr(
        "scripts.ops.seed_demo_family.audit_person_by_iin",
        lambda _conn, *, iin, expected_name: PersonAudit(
            exists=True,
            person_id=501,
            full_name=expected_name,
            person_status="active",
            match_key="demo:ppr-applicant:ahmetov",
            source="demo_ppr_applicant",
            hr_relationship_context="CANDIDATE",
            has_active_employee=False,
            demo_marked=True,
            safe_to_touch=True,
            block_reason=None,
        ),
    )
    monkeypatch.setattr(
        "scripts.ops.seed_demo_family._is_ppr_materialized",
        lambda _conn, *, person_id: True,
    )
    monkeypatch.setattr(
        "scripts.ops.seed_demo_family._family_demo_record_exists",
        lambda _conn, *, person_id, demo_record_key: False,
    )
    report, pending = build_seed_plan(conn, execute=False)
    assert report.created == sum(len(records) for records in DEMO_FAMILY_BY_KEY.values())
    assert pending == []


def test_main_defaults_to_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.ops.seed_demo_family as mod
    from scripts.ops.seed_demo_family import SeedReport

    captured: list[bool] = []
    monkeypatch.setattr(
        mod,
        "run",
        lambda *, execute: captured.append(execute) or SeedReport(mode="dry_run"),
    )
    mod.main([])
    assert captured == [False]
