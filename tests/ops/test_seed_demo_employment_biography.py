"""Tests for production-safe demo Employment Biography seed ops script."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from scripts.ops.create_demo_ppr_applicants import ALLOWED_IINS, APPLICANTS, PersonAudit
from scripts.ops.seed_demo_employment_biography import (
    DEMO_EMPLOYMENT_BY_KEY,
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
    assert {spec["key"] for spec in specs} == set(DEMO_EMPLOYMENT_BY_KEY.keys())
    assert len(specs) == len(APPLICANTS)


def test_build_payload_episode_includes_metadata_key() -> None:
    record = DEMO_EMPLOYMENT_BY_KEY["ahmetov"][0]
    payload = _build_payload(record)
    assert payload["record_kind"] == "episode"
    assert payload["employer_name"] == "ГП №7 г. Алматы"
    assert payload["metadata"]["demo_record_key"] == "ahmetov:episode:gp7-almaty"
    assert payload["metadata"]["demo_suite"] == "employment_biography_v1"


def test_build_payload_narrative_has_notes_only() -> None:
    record = DEMO_EMPLOYMENT_BY_KEY["ahmetov"][1]
    payload = _build_payload(record)
    assert payload["record_kind"] == "narrative_summary"
    assert "employer_name" not in payload
    assert payload["notes"].startswith("Сводный стаж")


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
        record_spec=DEMO_EMPLOYMENT_BY_KEY["ahmetov"][0],
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
        record_spec=DEMO_EMPLOYMENT_BY_KEY["ahmetov"][0],
        materialized=True,
        exists=True,
        execute=True,
    )
    assert action.action == "skipped"
    assert action.detail == "active demo record already exists"


def test_plan_record_action_skips_not_materialized() -> None:
    audit = PersonAudit(
        exists=True,
        person_id=501,
        full_name="Ахметов Айдар Серикович",
        person_status="active",
        match_key="demo:ppr-applicant:ahmetov",
        source="demo_ppr_applicant",
        hr_relationship_context=None,
        has_active_employee=False,
        demo_marked=True,
        safe_to_touch=True,
        block_reason=None,
    )
    action = plan_record_action(
        person_spec={"key": "ahmetov", "iin": "900101350123"},
        audit=audit,
        record_spec=DEMO_EMPLOYMENT_BY_KEY["ahmetov"][0],
        materialized=False,
        exists=False,
        execute=True,
    )
    assert action.action == "skipped"
    assert "not materialized" in (action.detail or "")


def test_build_seed_plan_dry_run_counts_would_create() -> None:
    conn = MagicMock()
    person_specs = [
        {
            "key": "ahmetov",
            "full_name": "Ахметов Айдар Серикович",
            "iin": "900101350123",
            "records": DEMO_EMPLOYMENT_BY_KEY["ahmetov"],
        }
    ]

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "scripts.ops.seed_demo_employment_biography.audit_person_by_iin",
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
        mp.setattr(
            "scripts.ops.seed_demo_employment_biography._employment_demo_record_exists",
            lambda *_args, **_kwargs: False,
        )
        report, pending = build_seed_plan(conn, execute=False, person_specs=person_specs)

    assert report.mode == "dry_run"
    assert report.found_persons == 1
    assert report.created == 2
    assert report.skipped == 0
    assert pending == []
    assert all(action.action == "dry_run_create" for action in report.actions)


def test_build_seed_plan_idempotent_skips_existing() -> None:
    conn = MagicMock()
    person_specs = [
        {
            "key": "ahmetov",
            "full_name": "Ахметов Айдар Серикович",
            "iin": "900101350123",
            "records": DEMO_EMPLOYMENT_BY_KEY["ahmetov"],
        }
    ]

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "scripts.ops.seed_demo_employment_biography.audit_person_by_iin",
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
        mp.setattr(
            "scripts.ops.seed_demo_employment_biography._employment_demo_record_exists",
            lambda *_args, **_kwargs: True,
        )
        report, pending = build_seed_plan(conn, execute=True, person_specs=person_specs)

    assert report.created == 0
    assert report.skipped == 2
    assert pending == []


def test_require_execute_allowed_blocks_production_without_flag() -> None:
    target = parse_db_target("postgresql://postgres@46.247.42.47:5432/corpsite")
    with pytest.raises(SystemExit):
        _require_execute_allowed(target, execute=True)


def test_run_dry_run_does_not_mutate(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.ops.seed_demo_employment_biography import SeedReport

    execute_called = {"value": False}

    def _fail_execute(*_args, **_kwargs):
        execute_called["value"] = True
        raise AssertionError("execute_seed_plan must not run in dry-run")

    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres@127.0.0.1:5432/corpsite")
    monkeypatch.setattr(
        "scripts.ops.seed_demo_employment_biography.build_seed_plan",
        lambda *_args, **_kwargs: (
            SeedReport(mode="dry_run", created=2, skipped=0, found_persons=2),
            [],
        ),
    )
    monkeypatch.setattr("scripts.ops.seed_demo_employment_biography.execute_seed_plan", _fail_execute)

    report = run(execute=False)
    assert execute_called["value"] is False
    assert report.mode == "dry_run"
