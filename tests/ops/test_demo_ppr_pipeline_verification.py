"""Final verification tests for WP-PPR-DEMO-001 unified pipeline."""
from __future__ import annotations

import os
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text

from scripts.ops.create_demo_ppr_applicants import ALLOWED_IINS, APPLICANTS, audit_person_by_iin
from scripts.ops.seed_demo_ppr import PipelineError, run as run_pipeline
from tests.ppr.conftest import ppr_db_available


def _require_db() -> None:
    if not ppr_db_available():
        pytest.skip("PostgreSQL unavailable")


def _db_counts() -> dict[str, int]:
    from app.db.engine import engine

    with engine.connect() as conn:
        persons = conn.execute(
            text("SELECT COUNT(*) FROM public.persons WHERE iin = ANY(:iins)"),
            {"iins": list(ALLOWED_IINS)},
        ).scalar_one()
        events = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.personnel_record_events pre
                JOIN public.persons p ON p.person_id = pre.person_id
                WHERE p.iin = ANY(:iins)
                """
            ),
            {"iins": list(ALLOWED_IINS)},
        ).scalar_one()
        commands = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.ppr_command_executions pce
                JOIN public.persons p ON p.person_id = pce.person_id
                WHERE p.iin = ANY(:iins)
                """
            ),
            {"iins": list(ALLOWED_IINS)},
        ).scalar_one()
        active_family = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.person_relatives pr
                JOIN public.persons p ON p.person_id = pr.person_id
                WHERE p.iin = ANY(:iins)
                  AND pr.lifecycle_status = 'active'
                """
            ),
            {"iins": list(ALLOWED_IINS)},
        ).scalar_one()
        demo_family = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.person_relatives pr
                JOIN public.persons p ON p.person_id = pr.person_id
                WHERE p.iin = ANY(:iins)
                  AND pr.lifecycle_status = 'active'
                  AND pr.metadata->>'demo_suite' = 'family_v1'
                """
            ),
            {"iins": list(ALLOWED_IINS)},
        ).scalar_one()
    return {
        "persons": int(persons),
        "events": int(events),
        "commands": int(commands),
        "active_family": int(active_family),
        "demo_family": int(demo_family),
    }


def _cleanup_demo() -> None:
    os.environ["CORPSITE_ALLOW_DEMO_PPR_SEED"] = "1"
    try:
        run_pipeline(execute=True, rollback=True)
    except PipelineError:
        pass
    from app.db.engine import engine
    from scripts.ops.create_demo_ppr_applicants import _delete_person_demo_data

    with engine.begin() as conn:
        for spec in APPLICANTS:
            audit = audit_person_by_iin(conn, iin=spec["iin"], expected_name=spec["full_name"])
            if audit.exists and audit.demo_marked and audit.person_id is not None:
                _delete_person_demo_data(conn, int(audit.person_id))


@pytest.fixture()
def allow_demo_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORPSITE_ALLOW_DEMO_PPR_SEED", "1")


def _stable_demo_counts() -> dict[str, int]:
    counts = _db_counts()
    return {
        "persons": counts["persons"],
        "demo_family": counts["demo_family"],
        "active_family": counts["active_family"],
    }


def test_execute_twice_is_idempotent(allow_demo_seed: None) -> None:
    _require_db()
    _cleanup_demo()

    run_pipeline(execute=True)
    first = _stable_demo_counts()
    assert first["persons"] == len(APPLICANTS)
    assert first["demo_family"] == 5

    run_pipeline(execute=True)
    second = _stable_demo_counts()
    assert second == first


def test_rollback_twice_is_idempotent(allow_demo_seed: None) -> None:
    _require_db()
    _cleanup_demo()
    run_pipeline(execute=True)

    run_pipeline(execute=True, rollback=True)
    after_first = _db_counts()
    assert after_first["persons"] == 0
    assert after_first["demo_family"] == 0

    report = run_pipeline(execute=True, rollback=True)
    assert report.ok is True
    assert {stage.stage for stage in report.stages} == {
        "family",
        "military",
        "employment_biography",
        "applicants",
    }
    assert all(stage.status == "completed" for stage in report.stages)
    assert _db_counts() == after_first


def test_rollback_preserves_manual_family_record(allow_demo_seed: None) -> None:
    _require_db()
    _cleanup_demo()
    run_pipeline(execute=True)

    from app.db.engine import engine
    from app.db.models.personnel_migration import RELATIONSHIP_TYPE_FATHER
    from app.ppr.application.authorization import AllowAllAuthorizationPort
    from app.ppr.application.command_models import COMMAND_TYPE_ADD_RELATIVE, PprCommandEnvelope
    from app.ppr.application.section_service import PprSectionApplicationService

    ahmetov_iin = APPLICANTS[0]["iin"]
    with engine.connect() as conn:
        audit = audit_person_by_iin(conn, iin=ahmetov_iin, expected_name=APPLICANTS[0]["full_name"])
        person_id = int(audit.person_id)

    section = PprSectionApplicationService(authorization=AllowAllAuthorizationPort())
    manual_name = "Ручной Родственник Тестович"
    section.add_relative(
        PprCommandEnvelope(
            command_id=f"manual-family-{uuid4().hex}",
            command_type=COMMAND_TYPE_ADD_RELATIVE,
            actor_id="test-manual-family",
            requested_at=datetime.now(UTC),
            payload={
                "relationship_type": RELATIONSHIP_TYPE_FATHER,
                "full_name": manual_name,
                "birth_date": date(1960, 1, 1),
            },
            person_id=person_id,
        )
    )

    run_pipeline(execute=True, rollback=True)

    with engine.connect() as conn:
        audit = audit_person_by_iin(conn, iin=ahmetov_iin, expected_name=APPLICANTS[0]["full_name"])
        assert audit.exists is True
        manual = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.person_relatives
                WHERE person_id = :person_id
                  AND lifecycle_status = 'active'
                  AND full_name = :full_name
                """
            ),
            {"person_id": audit.person_id, "full_name": manual_name},
        ).scalar_one()
        demo = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.person_relatives
                WHERE person_id = :person_id
                  AND lifecycle_status = 'active'
                  AND metadata->>'demo_suite' = 'family_v1'
                """
            ),
            {"person_id": audit.person_id},
        ).scalar_one()

    assert int(manual) == 1
    assert int(demo) == 0

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                DELETE FROM public.person_relatives
                WHERE person_id = :person_id AND full_name = :full_name
                """
            ),
            {"person_id": audit.person_id, "full_name": manual_name},
        )
        from scripts.ops.create_demo_ppr_applicants import _delete_person_demo_data

        if audit.person_id is not None:
            _delete_person_demo_data(conn, int(audit.person_id))


def test_partial_pipeline_rollback_is_safe(allow_demo_seed: None) -> None:
    _require_db()
    _cleanup_demo()

    from scripts.ops.create_demo_ppr_applicants import run as run_applicants
    from scripts.ops.seed_demo_employment_biography import run as run_employment

    run_applicants(execute=True)
    run_employment(execute=True)

    report = run_pipeline(execute=True, rollback=True)
    assert report.ok is True
    counts = _db_counts()
    assert counts["persons"] == 0
    assert counts["demo_family"] == 0


def test_stage_failure_stops_pipeline_with_nonzero_exit(allow_demo_seed: None, monkeypatch) -> None:
    import scripts.ops.seed_demo_ppr as mod

    monkeypatch.setattr(mod, "_require_execute_allowed", lambda **kwargs: None)

    def _fail_employment(stage: str, *, execute: bool, db_engine):
        if stage == "applicants":
            return {"mode": "execute"}
        if stage == "employment_biography":
            raise RuntimeError("simulated stage failure")
        raise AssertionError(f"unexpected stage after failure: {stage}")

    monkeypatch.setattr(mod, "_execute_stage", _fail_employment)

    with pytest.raises(PipelineError) as exc_info:
        mod.run(execute=True)

    report = exc_info.value.report
    assert report.ok is False
    assert report.failed_stages == ["employment_biography"]
    assert report.completed_stages == ["applicants"]
    assert "military" not in report.completed_stages
    assert "family" not in report.completed_stages

    assert mod.main(["--execute"]) == 1


def test_dry_run_does_not_mutate_db(allow_demo_seed: None) -> None:
    _require_db()
    _cleanup_demo()

    before = _db_counts()
    report = run_pipeline(execute=False)
    after = _db_counts()

    assert report.ok is True
    assert report.mode == "dry_run"
    assert len(report.stages) == 4
    assert all(stage.status == "completed" for stage in report.stages)
    assert before == after
    assert after["events"] == 0
    assert after["commands"] == 0


def test_rollback_order_is_reverse_of_seed(allow_demo_seed: None, monkeypatch) -> None:
    import scripts.ops.seed_demo_ppr as mod

    order: list[str] = []
    monkeypatch.setattr(mod, "_require_execute_allowed", lambda **kwargs: None)
    monkeypatch.setattr(
        mod,
        "_rollback_stage",
        lambda stage, *, execute, db_engine: order.append(stage) or {"stage": stage},
    )

    mod.run(execute=True, rollback=True)
    assert order == ["family", "military", "employment_biography", "applicants"]
