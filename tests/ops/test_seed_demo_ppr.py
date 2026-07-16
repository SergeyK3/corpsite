"""Tests for unified demo PPR pipeline ops script."""
from __future__ import annotations

import pytest

from scripts.ops.seed_demo_ppr import (
    DEMO_SECTION_MANIFEST,
    EXECUTE_STAGE_ORDER,
    ROLLBACK_STAGE_ORDER,
    PipelineError,
)


def test_demo_section_manifest_covers_all_ops_sections() -> None:
    assert set(DEMO_SECTION_MANIFEST) == {
        "general",
        "education",
        "training",
        "employment_biography",
        "military",
        "family",
    }
    assert "family" in DEMO_SECTION_MANIFEST


def test_rollback_stage_order_is_reverse_of_execute() -> None:
    assert ROLLBACK_STAGE_ORDER == tuple(reversed(EXECUTE_STAGE_ORDER))
    assert ROLLBACK_STAGE_ORDER[0] == "family"
    assert ROLLBACK_STAGE_ORDER[-1] == "applicants"


def test_main_defaults_to_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.ops.seed_demo_ppr as mod
    from scripts.ops.seed_demo_ppr import PipelineReport

    captured: list[dict] = []

    def _capture(**kwargs):
        captured.append(kwargs)
        return PipelineReport(mode="dry_run")

    monkeypatch.setattr(mod, "run", _capture)
    assert mod.main([]) == 0
    assert captured == [{"execute": False, "rollback": False}]


def test_main_returns_nonzero_on_pipeline_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.ops.seed_demo_ppr as mod
    from scripts.ops.seed_demo_ppr import PipelineReport

    def _fail(**kwargs):
        report = PipelineReport(mode="execute", ok=False, error="employment_biography: boom")
        raise PipelineError(report)

    monkeypatch.setattr(mod, "run", _fail)
    assert mod.main(["--execute"]) == 1


def test_run_execute_runs_all_sections_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.ops.seed_demo_ppr as mod
    from scripts.ops.seed_demo_employment_biography import SeedReport

    order: list[str] = []

    monkeypatch.setattr(mod, "_require_execute_allowed", lambda **kwargs: None)
    monkeypatch.setattr(
        mod,
        "_execute_stage",
        lambda stage, *, execute, db_engine: order.append(stage)
        or (SeedReport(mode="execute") if stage != "applicants" else {"mode": "execute"}),
    )

    report = mod.run(execute=True)
    assert order == ["applicants", "employment_biography", "military", "family"]
    assert report.mode == "execute"
    assert report.completed_stages == list(order)


def test_run_rollback_runs_all_stages_in_reverse_order(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.ops.seed_demo_ppr as mod
    from scripts.ops.seed_demo_employment_biography import SeedReport

    order: list[str] = []

    monkeypatch.setattr(mod, "_require_execute_allowed", lambda **kwargs: None)
    monkeypatch.setattr(
        mod,
        "_rollback_stage",
        lambda stage, *, execute, db_engine: order.append(stage)
        or (SeedReport(mode="rollback_execute") if stage != "applicants" else {"mode": "rollback"}),
    )

    report = mod.run(execute=True, rollback=True)
    assert order == ["family", "military", "employment_biography", "applicants"]
    assert report.mode == "rollback"
    assert report.completed_stages == list(order)
