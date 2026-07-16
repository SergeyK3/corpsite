#!/usr/bin/env python3
"""Unified production demo pipeline for PPR CANDIDATE cards.

One command seeds all implemented PPR sections for whitelisted demo applicants:

- **general / education / training** — ``create_demo_ppr_applicants``
- **employment_biography** — ``seed_demo_employment_biography``
- **military** — ``seed_demo_military_service``
- **family** — ``seed_demo_family``

Default mode is dry-run (no writes). Mutations require ``--execute``.

Rollback runs in reverse seed order and voids lifecycle sections via application
commands using exact ``demo_suite`` / ``demo_record_key`` markers only.

Demo PPR ops on Ubuntu/VPS (``DATABASE_URL`` is taken from the service environment):

.. code-block:: bash

   export CORPSITE_ALLOW_DEMO_PPR_SEED=1
   python scripts/ops/seed_demo_ppr.py --dry-run
   python scripts/ops/seed_demo_ppr.py --execute
   python scripts/ops/seed_demo_ppr.py --rollback

On production-like hosts, ``CORPSITE_ALLOW_DEMO_PPR_SEED=1`` is mandatory for ``--execute``
and ``--rollback``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy.engine import Engine

REPO_ROOT = __file__.replace("\\", "/").rsplit("/", 3)[0]
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from app.db.engine import engine
from scripts.ops.create_demo_ppr_applicants import parse_db_target, run as run_applicants
from scripts.ops.seed_demo_employment_biography import (
    SeedReport,
    run as run_employment_biography,
    run_rollback as rollback_employment_biography,
)
from scripts.ops.seed_demo_family import run as run_family, run_rollback as rollback_family
from scripts.ops.seed_demo_military_service import (
    run as run_military_service,
    run_rollback as rollback_military_service,
)

DEMO_SECTION_MANIFEST: dict[str, str] = {
    "general": "create_demo_ppr_applicants (envelope + person scalars)",
    "education": "create_demo_ppr_applicants",
    "training": "create_demo_ppr_applicants (ahmetov only)",
    "employment_biography": "seed_demo_employment_biography",
    "military": "seed_demo_military_service",
    "family": "seed_demo_family",
}

EXECUTE_STAGE_ORDER: tuple[str, ...] = (
    "applicants",
    "employment_biography",
    "military",
    "family",
)

ROLLBACK_STAGE_ORDER: tuple[str, ...] = tuple(reversed(EXECUTE_STAGE_ORDER))


class PipelineError(Exception):
    """Raised when a pipeline stage fails; carries the partial report."""

    def __init__(self, report: PipelineReport):
        self.report = report
        super().__init__(report.error or "pipeline stage failed")


@dataclass(slots=True)
class StageOutcome:
    stage: str
    status: str
    detail: str | None = None
    result: Any = None


@dataclass(slots=True)
class PipelineReport:
    mode: str
    sections: dict[str, str] = field(default_factory=lambda: dict(DEMO_SECTION_MANIFEST))
    stages: list[StageOutcome] = field(default_factory=list)
    ok: bool = True
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def completed_stages(self) -> list[str]:
        return [stage.stage for stage in self.stages if stage.status == "completed"]

    @property
    def skipped_stages(self) -> list[str]:
        return [stage.stage for stage in self.stages if stage.status == "skipped"]

    @property
    def failed_stages(self) -> list[str]:
        return [stage.stage for stage in self.stages if stage.status == "failed"]


def _require_execute_allowed(*, execute: bool, rollback: bool) -> None:
    if not execute and not rollback:
        return
    if os.getenv("CORPSITE_ALLOW_DEMO_PPR_SEED") == "1":
        return
    db_target = parse_db_target(os.getenv("DATABASE_URL", ""))
    if db_target.production_like:
        raise SystemExit(
            "Refusing mutating operation on production-like database. "
            "Set CORPSITE_ALLOW_DEMO_PPR_SEED=1 to acknowledge."
        )


def _execute_stage(
    stage: str,
    *,
    execute: bool,
    db_engine: Engine,
) -> Any:
    if stage == "applicants":
        return run_applicants(execute=execute, rollback=False, db=db_engine)
    if stage == "employment_biography":
        return run_employment_biography(execute=execute, db=db_engine)
    if stage == "military":
        return run_military_service(execute=execute, db=db_engine)
    if stage == "family":
        return run_family(execute=execute, db=db_engine)
    raise ValueError(f"unknown execute stage: {stage}")


def _rollback_stage(
    stage: str,
    *,
    execute: bool,
    db_engine: Engine,
) -> Any:
    if stage == "applicants":
        return run_applicants(execute=execute, rollback=True, db=db_engine)
    if stage == "employment_biography":
        return rollback_employment_biography(execute=execute, db=db_engine)
    if stage == "military":
        return rollback_military_service(execute=execute, db=db_engine)
    if stage == "family":
        return rollback_family(execute=execute, db=db_engine)
    raise ValueError(f"unknown rollback stage: {stage}")


def _serialize_stage_result(result: Any) -> Any:
    if isinstance(result, SeedReport):
        return result.to_dict()
    return result


def _run_stages(
    *,
    stage_order: tuple[str, ...],
    stage_runner: Callable[..., Any],
    execute: bool,
    db_engine: Engine,
    mode: str,
) -> PipelineReport:
    report = PipelineReport(mode=mode)

    for stage in stage_order:
        try:
            result = stage_runner(stage, execute=execute, db_engine=db_engine)
            report.stages.append(
                StageOutcome(
                    stage=stage,
                    status="completed",
                    result=_serialize_stage_result(result),
                )
            )
        except Exception as exc:
            report.stages.append(
                StageOutcome(
                    stage=stage,
                    status="failed",
                    detail=str(exc),
                )
            )
            report.ok = False
            report.error = f"{stage}: {exc}"
            break

    return report


def run(
    *,
    execute: bool = False,
    rollback: bool = False,
    db: Engine | None = None,
) -> PipelineReport:
    db_engine = db or engine
    _require_execute_allowed(execute=execute, rollback=rollback)

    mode = "rollback" if rollback else ("execute" if execute else "dry_run")
    stage_order = ROLLBACK_STAGE_ORDER if rollback else EXECUTE_STAGE_ORDER
    stage_runner = _rollback_stage if rollback else _execute_stage

    print("=== PIPELINE ===")
    print(
        json.dumps(
            {
                "mode": mode,
                "stage_order": list(stage_order),
                "sections": DEMO_SECTION_MANIFEST,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    report = _run_stages(
        stage_order=stage_order,
        stage_runner=stage_runner,
        execute=execute,
        db_engine=db_engine,
        mode=mode,
    )

    print("=== PIPELINE REPORT ===")
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, default=str))

    if not report.ok:
        raise PipelineError(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed all demo PPR sections for whitelisted CANDIDATE applicants.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Audit and print manifest for all sections without writes (default).",
    )
    mode.add_argument(
        "--execute",
        action="store_true",
        help="Create or idempotently refresh all demo PPR sections.",
    )
    mode.add_argument(
        "--rollback",
        action="store_true",
        help="Void demo section rows and delete demo-marked applicants (reverse order).",
    )
    args = parser.parse_args(argv)
    try:
        run(execute=bool(args.execute), rollback=bool(args.rollback))
    except PipelineError:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
