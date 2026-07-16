"""Sequential integration test for demo PPR applicant + employment biography seeds."""
from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from scripts.ops.create_demo_ppr_applicants import (
    ALLOWED_IINS,
    APPLICANTS,
    audit_person_by_iin,
    run as run_applicants,
)
from scripts.ops.seed_demo_employment_biography import run as run_employment_biography
from scripts.ops.seed_demo_family import run as run_family
from scripts.ops.seed_demo_military_service import run as run_military_service
from scripts.ops.seed_demo_ppr import run as run_pipeline
from tests.ppr.conftest import ppr_db_available


def _require_db() -> None:
    if not ppr_db_available():
        pytest.skip("PostgreSQL unavailable")


def _count_demo_persons() -> int:
    from app.db.engine import engine

    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.persons
                WHERE iin = ANY(:iins)
                """
            ),
            {"iins": list(ALLOWED_IINS)},
        ).scalar_one()
    return int(row)


def _count_active_demo_employment() -> int:
    from app.db.engine import engine

    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.person_external_employment pee
                JOIN public.persons p ON p.person_id = pee.person_id
                WHERE p.iin = ANY(:iins)
                  AND pee.lifecycle_status = 'active'
                  AND pee.metadata->>'demo_suite' = 'employment_biography_v1'
                """
            ),
            {"iins": list(ALLOWED_IINS)},
        ).scalar_one()
    return int(row)


def _count_active_demo_military() -> int:
    from app.db.engine import engine

    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.person_military_service pms
                JOIN public.persons p ON p.person_id = pms.person_id
                WHERE p.iin = ANY(:iins)
                  AND pms.lifecycle_status = 'active'
                  AND pms.metadata->>'demo_suite' = 'military_service_v1'
                """
            ),
            {"iins": list(ALLOWED_IINS)},
        ).scalar_one()
    return int(row)


def _count_active_demo_family() -> int:
    from app.db.engine import engine

    with engine.connect() as conn:
        row = conn.execute(
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
    return int(row)

def _cleanup_demo_applicants() -> None:
    os.environ["CORPSITE_ALLOW_DEMO_PPR_SEED"] = "1"
    try:
        run_pipeline(execute=True, rollback=True)
    except Exception:
        pass

    from app.db.engine import engine
    from scripts.ops.create_demo_ppr_applicants import (
        _delete_person_demo_data,
    )

    with engine.begin() as conn:
        for spec in APPLICANTS:
            audit = audit_person_by_iin(conn, iin=spec["iin"], expected_name=spec["full_name"])
            if audit.exists and not audit.demo_marked:
                if audit.has_active_employee:
                    pytest.skip(
                        f"Refusing cleanup: active employee on whitelisted IIN {spec['iin']}",
                    )
                if audit.source != "enrollment":
                    pytest.skip(
                        f"Refusing cleanup: non-demo person on IIN {spec['iin']} "
                        f"(source={audit.source!r})",
                    )
                _delete_person_demo_data(conn, int(audit.person_id))
            elif audit.exists and audit.demo_marked and audit.person_id is not None:
                _delete_person_demo_data(conn, int(audit.person_id))


@pytest.fixture()
def allow_demo_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORPSITE_ALLOW_DEMO_PPR_SEED", "1")


def test_applicants_main_defaults_to_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.ops.create_demo_ppr_applicants as mod

    captured: list[dict] = []

    def _capture(**kwargs):
        captured.append(kwargs)
        return {"mode": "dry_run"}

    monkeypatch.setattr(mod, "run", _capture)
    mod.main([])
    assert captured == [{"execute": False, "rollback": False}]


def test_employment_biography_main_defaults_to_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.ops.seed_demo_employment_biography as mod
    from scripts.ops.seed_demo_employment_biography import SeedReport

    captured: list[bool] = []
    monkeypatch.setattr(
        mod,
        "run",
        lambda *, execute: captured.append(execute) or SeedReport(mode="dry_run"),
    )
    mod.main([])
    assert captured == [False]


def test_military_service_main_defaults_to_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.ops.seed_demo_military_service as mod
    from scripts.ops.seed_demo_military_service import SeedReport

    captured: list[bool] = []
    monkeypatch.setattr(
        mod,
        "run",
        lambda *, execute: captured.append(execute) or SeedReport(mode="dry_run"),
    )
    mod.main([])
    assert captured == [False]


def test_family_main_defaults_to_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_pipeline_main_defaults_to_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.ops.seed_demo_ppr as mod
    from scripts.ops.seed_demo_ppr import PipelineReport

    captured: list[dict] = []
    monkeypatch.setattr(
        mod,
        "run",
        lambda **kwargs: captured.append(kwargs) or PipelineReport(mode="dry_run"),
    )
    mod.main([])
    assert captured == [{"execute": False, "rollback": False}]


def test_sequential_demo_seeds_are_idempotent(allow_demo_seed: None) -> None:
    _require_db()

    os.environ["CORPSITE_ALLOW_DEMO_PPR_SEED"] = "1"
    _cleanup_demo_applicants()
    assert _count_demo_persons() == 0
    assert _count_active_demo_employment() == 0
    assert _count_active_demo_military() == 0
    assert _count_active_demo_family() == 0

    run_applicants(execute=True)
    assert _count_demo_persons() == len(APPLICANTS)

    emp_first = run_employment_biography(execute=True)
    assert emp_first.created == 3
    assert _count_active_demo_employment() == 3

    mil_first = run_military_service(execute=True)
    assert mil_first.created == 2
    assert _count_active_demo_military() == 2

    fam_first = run_family(execute=True)
    assert fam_first.created == 5
    assert _count_active_demo_family() == 5

    run_applicants(execute=True)
    assert _count_demo_persons() == len(APPLICANTS)

    emp_second = run_employment_biography(execute=True)
    assert emp_second.created == 0
    assert emp_second.skipped == 3
    assert _count_active_demo_employment() == 3

    mil_second = run_military_service(execute=True)
    assert mil_second.created == 0
    assert mil_second.skipped == 2
    assert _count_active_demo_military() == 2

    fam_second = run_family(execute=True)
    assert fam_second.created == 0
    assert fam_second.skipped == 5
    assert _count_active_demo_family() == 5


def test_unified_pipeline_seeds_all_sections(allow_demo_seed: None) -> None:
    _require_db()

    os.environ["CORPSITE_ALLOW_DEMO_PPR_SEED"] = "1"
    _cleanup_demo_applicants()
    assert _count_demo_persons() == 0

    run_pipeline(execute=True)
    assert _count_demo_persons() == len(APPLICANTS)
    assert _count_active_demo_employment() == 3
    assert _count_active_demo_military() == 2
    assert _count_active_demo_family() == 5

    run_pipeline(execute=True)
    assert _count_demo_persons() == len(APPLICANTS)
    assert _count_active_demo_employment() == 3
    assert _count_active_demo_military() == 2
    assert _count_active_demo_family() == 5
