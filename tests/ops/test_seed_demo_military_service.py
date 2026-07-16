"""Tests for production-safe demo Military Service seed ops script."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from app.db.models.personnel_migration import (
    MILITARY_RECORD_KIND_NOT_APPLICABLE,
    MILITARY_RECORD_KIND_REGISTRATION,
)
from scripts.ops.create_demo_ppr_applicants import ALLOWED_IINS, APPLICANTS, PersonAudit
from scripts.ops.seed_demo_military_service import (
    DEMO_MILITARY_BY_KEY,
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
    assert {spec["key"] for spec in specs} == set(DEMO_MILITARY_BY_KEY.keys())
    assert len(specs) == len(APPLICANTS)


def test_build_payload_ahmetov_registration_includes_realistic_fields() -> None:
    record = DEMO_MILITARY_BY_KEY["ahmetov"]
    payload = _build_payload(record)
    assert payload["record_kind"] == MILITARY_RECORD_KIND_REGISTRATION
    assert payload["obligation_status"] == "liable"
    assert payload["registration_category"] == "II"
    assert payload["military_rank"] == "рядовой"
    assert payload["military_specialty_code"] == "868123А"
    assert payload["personnel_composition"] == "soldiers"
    assert payload["fitness_category"] == "А"
    assert payload["registration_status"] == "registered"
    assert payload["commissariat_name"].startswith("Районный военкомат")
    assert payload["registered_at"] == date(2008, 6, 15)
    assert payload["metadata"]["demo_record_key"] == "ahmetov:military:registration-v1"
    assert payload["metadata"]["demo_suite"] == "military_service_v1"
    assert "military_id_book_number" not in payload
    assert "registration_certificate_number" not in payload


def test_build_payload_seitova_not_applicable_has_notes_only() -> None:
    record = DEMO_MILITARY_BY_KEY["seitova"]
    payload = _build_payload(record)
    assert payload == {
        "record_kind": MILITARY_RECORD_KIND_NOT_APPLICABLE,
        "source_type": "entered",
        "notes": record["notes"],
        "metadata": {
            "demo": True,
            "demo_suite": "military_service_v1",
            "demo_source": "demo_military_service",
            "demo_record_key": "seitova:military:not-applicable-v1",
        },
    }
    assert "obligation_status" not in payload
    assert "military_rank" not in payload
    assert "registered_at" not in payload


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
        record_spec=DEMO_MILITARY_BY_KEY["ahmetov"],
        materialized=True,
        exists=False,
        execute=False,
    )
    assert action.action == "dry_run_create"


def test_build_seed_plan_dry_run_counts_would_create() -> None:
    conn = MagicMock()
    person_specs = [
        {
            "key": "ahmetov",
            "full_name": "Ахметов Айдар Серикович",
            "iin": "900101350123",
            "record": DEMO_MILITARY_BY_KEY["ahmetov"],
        },
        {
            "key": "seitova",
            "full_name": "Сейтова Алия Маратовна",
            "iin": "950515450456",
            "record": DEMO_MILITARY_BY_KEY["seitova"],
        },
    ]

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "scripts.ops.seed_demo_military_service.audit_person_by_iin",
            lambda _conn, *, iin, expected_name: PersonAudit(
                exists=True,
                person_id=501 if iin == "900101350123" else 502,
                full_name=expected_name,
                person_status="active",
                match_key=f"demo:ppr-applicant:{iin[-3:]}",
                source="demo_ppr_applicant",
                hr_relationship_context="CANDIDATE",
                has_active_employee=False,
                demo_marked=True,
                safe_to_touch=True,
                block_reason=None,
            ),
        )
        mp.setattr(
            "scripts.ops.seed_demo_military_service._is_ppr_materialized",
            lambda *_args, **_kwargs: True,
        )
        mp.setattr(
            "scripts.ops.seed_demo_military_service._military_demo_record_exists",
            lambda *_args, **_kwargs: False,
        )
        report, pending = build_seed_plan(conn, execute=False, person_specs=person_specs)

    assert report.mode == "dry_run"
    assert report.found_persons == 2
    assert report.created == 2
    assert report.skipped == 0
    assert pending == []


def test_build_seed_plan_idempotent_skips_existing() -> None:
    conn = MagicMock()
    person_specs = [
        {
            "key": "ahmetov",
            "full_name": "Ахметов Айдар Серикович",
            "iin": "900101350123",
            "record": DEMO_MILITARY_BY_KEY["ahmetov"],
        }
    ]

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "scripts.ops.seed_demo_military_service.audit_person_by_iin",
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
            "scripts.ops.seed_demo_military_service._is_ppr_materialized",
            lambda *_args, **_kwargs: True,
        )
        mp.setattr(
            "scripts.ops.seed_demo_military_service._military_demo_record_exists",
            lambda *_args, **_kwargs: True,
        )
        report, pending = build_seed_plan(conn, execute=True, person_specs=person_specs)

    assert report.created == 0
    assert report.skipped == 1
    assert pending == []


def test_require_execute_allowed_blocks_production_without_flag() -> None:
    target = parse_db_target("postgresql://postgres@46.247.42.47:5432/corpsite")
    with pytest.raises(SystemExit):
        _require_execute_allowed(target, execute=True)


def test_run_dry_run_does_not_mutate(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.ops.seed_demo_military_service import SeedReport

    execute_called = {"value": False}

    def _fail_execute(*_args, **_kwargs):
        execute_called["value"] = True
        raise AssertionError("execute_seed_plan must not run in dry-run")

    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres@127.0.0.1:5432/corpsite")
    monkeypatch.setattr(
        "scripts.ops.seed_demo_military_service.build_seed_plan",
        lambda *_args, **_kwargs: (
            SeedReport(mode="dry_run", created=2, skipped=0, found_persons=2),
            [],
        ),
    )
    monkeypatch.setattr("scripts.ops.seed_demo_military_service.execute_seed_plan", _fail_execute)

    report = run(execute=False)
    assert execute_called["value"] is False
    assert report.mode == "dry_run"
