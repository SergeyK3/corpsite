#!/usr/bin/env python3
"""Seed demo Military Service records for whitelisted demo persons.

Production-safe ops script. Uses PPR application layer only (no direct section INSERTs).
Default mode is dry-run (no writes). Mutations require ``--execute``.

Prerequisites: run ``create_demo_ppr_applicants.py --execute`` first, or use the unified
``seed_demo_ppr.py`` pipeline.

Demo PPR ops on Ubuntu/VPS (``DATABASE_URL`` is taken from the service environment):

.. code-block:: bash

   export CORPSITE_ALLOW_DEMO_PPR_SEED=1
   python scripts/ops/seed_demo_ppr.py --dry-run
   python scripts/ops/seed_demo_ppr.py --execute

On production-like hosts, ``CORPSITE_ALLOW_DEMO_PPR_SEED=1`` is mandatory for ``--execute``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

REPO_ROOT = __file__.replace("\\", "/").rsplit("/", 3)[0]
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from app.db.engine import engine
from app.db.models.personnel_migration import (
    MILITARY_RECORD_KIND_NOT_APPLICABLE,
    MILITARY_RECORD_KIND_REGISTRATION,
    SECTION_SOURCE_TYPE_ENTERED,
)
from app.ppr.domain.models import PPR_LIFECYCLE_NOT_MATERIALIZED
from app.ppr.application.authorization import AllowAllAuthorizationPort
from app.ppr.application.command_models import (
    COMMAND_TYPE_CREATE_MILITARY_SERVICE,
    COMMAND_TYPE_VOID_MILITARY_SERVICE,
    PprCommandEnvelope,
)
from app.ppr.application.section_service import PprSectionApplicationService
from scripts.ops.create_demo_ppr_applicants import (
    APPLICANTS,
    ALLOWED_IINS,
    PersonAudit,
    audit_person_by_iin,
    parse_db_target,
)
from scripts.ops.demo_ppr_section_rollback import (
    DemoSectionRecordRef,
    load_active_demo_record,
    void_record_via_service,
)

DEMO_SUITE = "military_service_v1"
DEMO_SOURCE = "demo_military_service"
OPS_ACTOR_ID = "ops:seed_demo_military_service"

DEMO_MILITARY_BY_KEY: dict[str, dict[str, Any]] = {
    "ahmetov": {
        "demo_record_key": "ahmetov:military:registration-v1",
        "record_kind": MILITARY_RECORD_KIND_REGISTRATION,
        "obligation_status": "liable",
        "registration_category": "II",
        "military_rank": "рядовой",
        "military_specialty_code": "868123А",
        "personnel_composition": "soldiers",
        "fitness_category": "А",
        "registration_status": "registered",
        "commissariat_name": "Районный военкомат Алмалинского района г. Алматы",
        "registered_at": date(2008, 6, 15),
        "notes": "Постановка на воинский учёт при приёме на работу — сведения подтверждены военным билетом.",
    },
    "seitova": {
        "demo_record_key": "seitova:military:not-applicable-v1",
        "record_kind": MILITARY_RECORD_KIND_NOT_APPLICABLE,
        "notes": "Не подлежит воинскому учёту — женский пол, воинская обязанность отсутствует.",
    },
}


@dataclass(slots=True)
class RecordAction:
    person_key: str
    iin: str
    person_id: int | None
    demo_record_key: str
    record_kind: str
    action: str
    detail: str | None = None
    military_id: int | None = None


@dataclass(slots=True)
class SeedReport:
    mode: str
    found_persons: int = 0
    created: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    actions: list[RecordAction] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "summary": {
                "found_persons": self.found_persons,
                "created": self.created,
                "skipped": self.skipped,
                "errors": self.errors,
            },
            "actions": [asdict(action) for action in self.actions],
        }


def _require_execute_allowed(db_target, *, execute: bool) -> None:
    if not execute:
        return
    if os.getenv("CORPSITE_ALLOW_DEMO_PPR_SEED") == "1":
        return
    if db_target.production_like:
        raise SystemExit(
            "Refusing mutating operation on production-like database. "
            "Set CORPSITE_ALLOW_DEMO_PPR_SEED=1 to acknowledge."
        )


def _demo_person_specs() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for applicant in APPLICANTS:
        key = applicant["key"]
        if key not in DEMO_MILITARY_BY_KEY:
            continue
        specs.append(
            {
                "key": key,
                "full_name": applicant["full_name"],
                "iin": applicant["iin"],
                "record": DEMO_MILITARY_BY_KEY[key],
            }
        )
    return specs


def _is_ppr_materialized(conn: Connection, *, person_id: int) -> bool:
    row = conn.execute(
        text(
            """
            SELECT ppr_lifecycle_state
            FROM public.personnel_record_metadata
            WHERE person_id = :person_id
            """
        ),
        {"person_id": person_id},
    ).mappings().first()
    if row is None:
        return False
    state = str(row.get("ppr_lifecycle_state") or "")
    return bool(state) and state != PPR_LIFECYCLE_NOT_MATERIALIZED


def _military_demo_record_exists(
    conn: Connection,
    *,
    person_id: int,
    demo_record_key: str,
) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM public.person_military_service
            WHERE person_id = :person_id
              AND lifecycle_status = 'active'
              AND metadata->>'demo_record_key' = :demo_record_key
            LIMIT 1
            """
        ),
        {"person_id": person_id, "demo_record_key": demo_record_key},
    ).first()
    return row is not None


def _record_metadata(demo_record_key: str) -> dict[str, Any]:
    return {
        "demo": True,
        "demo_suite": DEMO_SUITE,
        "demo_source": DEMO_SOURCE,
        "demo_record_key": demo_record_key,
    }


def _build_payload(record_spec: dict[str, Any]) -> dict[str, Any]:
    demo_record_key = str(record_spec["demo_record_key"])
    payload: dict[str, Any] = {
        "record_kind": record_spec["record_kind"],
        "source_type": SECTION_SOURCE_TYPE_ENTERED,
        "metadata": _record_metadata(demo_record_key),
    }
    for field_name in (
        "obligation_status",
        "registration_category",
        "military_rank",
        "military_specialty_code",
        "personnel_composition",
        "fitness_category",
        "registration_status",
        "commissariat_name",
        "registered_at",
        "deregistered_at",
        "notes",
    ):
        if field_name in record_spec and record_spec[field_name] is not None:
            payload[field_name] = record_spec[field_name]
    return payload


def _section_service() -> PprSectionApplicationService:
    return PprSectionApplicationService(authorization=AllowAllAuthorizationPort())


def _command_envelope(*, person_id: int, payload: dict[str, Any]) -> PprCommandEnvelope:
    return PprCommandEnvelope(
        command_id=f"demo-mil-{uuid4().hex}",
        command_type=COMMAND_TYPE_CREATE_MILITARY_SERVICE,
        actor_id=OPS_ACTOR_ID,
        requested_at=datetime.now(UTC),
        payload=payload,
        person_id=person_id,
        correlation_id=f"demo-mil-{uuid4().hex[:12]}",
    )


def plan_record_action(
    *,
    person_spec: dict[str, Any],
    audit: PersonAudit,
    record_spec: dict[str, Any],
    materialized: bool,
    exists: bool,
    execute: bool,
) -> RecordAction:
    base = RecordAction(
        person_key=person_spec["key"],
        iin=person_spec["iin"],
        person_id=audit.person_id,
        demo_record_key=str(record_spec["demo_record_key"]),
        record_kind=str(record_spec["record_kind"]),
        action="pending",
    )

    if not audit.exists or audit.person_id is None:
        return RecordAction(
            **{**asdict(base), "action": "skipped", "detail": "demo person not found by IIN"}
        )
    if not audit.safe_to_touch:
        return RecordAction(
            **{
                **asdict(base),
                "action": "skipped",
                "detail": audit.block_reason or "person is not safe to touch",
            }
        )
    if not materialized:
        return RecordAction(
            **{
                **asdict(base),
                "action": "skipped",
                "detail": "PPR envelope not materialized — run create_demo_ppr_applicants first",
            }
        )
    if exists:
        return RecordAction(
            **{**asdict(base), "action": "skipped", "detail": "active demo record already exists"}
        )
    if not execute:
        return RecordAction(
            **{**asdict(base), "action": "dry_run_create", "detail": "would create via application layer"}
        )
    return RecordAction(**{**asdict(base), "action": "create", "detail": None})


def build_seed_plan(
    conn: Connection,
    *,
    execute: bool,
    person_specs: list[dict[str, Any]] | None = None,
) -> tuple[SeedReport, list[tuple[RecordAction, dict[str, Any]]]]:
    specs = person_specs if person_specs is not None else _demo_person_specs()
    report = SeedReport(mode="execute" if execute else "dry_run")
    pending_creates: list[tuple[RecordAction, dict[str, Any]]] = []

    found_keys: set[str] = set()
    for person_spec in specs:
        audit = audit_person_by_iin(
            conn,
            iin=person_spec["iin"],
            expected_name=person_spec["full_name"],
        )
        materialized = (
            _is_ppr_materialized(conn, person_id=audit.person_id)
            if audit.person_id is not None
            else False
        )
        if audit.exists and audit.safe_to_touch and audit.person_id is not None:
            found_keys.add(person_spec["key"])

        record_spec = person_spec["record"]
        exists = (
            _military_demo_record_exists(
                conn,
                person_id=audit.person_id,
                demo_record_key=str(record_spec["demo_record_key"]),
            )
            if audit.person_id is not None
            else False
        )
        action = plan_record_action(
            person_spec=person_spec,
            audit=audit,
            record_spec=record_spec,
            materialized=materialized,
            exists=exists,
            execute=execute,
        )
        report.actions.append(action)
        if action.action == "create":
            pending_creates.append((action, _build_payload(record_spec)))
        elif action.action == "dry_run_create":
            report.created += 1
        elif action.action == "skipped":
            report.skipped += 1
        else:
            report.errors.append(f"{action.demo_record_key}: unknown action {action.action}")

    report.found_persons = len(found_keys)
    return report, pending_creates


def execute_seed_plan(
    pending_creates: list[tuple[RecordAction, dict[str, Any]]],
    *,
    db_engine: Engine,
) -> None:
    section = _section_service()
    for action, payload in pending_creates:
        assert action.person_id is not None
        result = section.create_military_service(
            _command_envelope(person_id=action.person_id, payload=payload)
        )
        action.military_id = result.section_record_id
        action.detail = result.status


def run(*, execute: bool = False, db: Engine | None = None) -> SeedReport:
    db_engine = db or engine
    db_target = parse_db_target(os.getenv("DATABASE_URL", ""))
    _require_execute_allowed(db_target, execute=execute)

    print("=== AUDIT ===")
    print(
        json.dumps(
            {
                "host": db_target.host,
                "port": db_target.port,
                "dbname": db_target.dbname,
                "schema": db_target.schema,
                "production_like": db_target.production_like,
                "allowed_iins": sorted(ALLOWED_IINS),
                "demo_persons": [spec["key"] for spec in _demo_person_specs()],
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    with db_engine.connect() as conn:
        report, pending_creates = build_seed_plan(conn, execute=execute)

    if execute and pending_creates:
        execute_seed_plan(pending_creates, db_engine=db_engine)
        report.created = sum(1 for action, _ in pending_creates if action.action == "create")
    elif execute:
        report.created = 0

    print("=== REPORT ===")
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, default=str))
    return report


def build_rollback_plan(
    conn: Connection,
    *,
    execute: bool,
) -> tuple[SeedReport, list[DemoSectionRecordRef]]:
    report = SeedReport(mode="rollback_execute" if execute else "rollback_dry_run")
    pending_voids: list[DemoSectionRecordRef] = []

    for applicant in APPLICANTS:
        key = applicant["key"]
        record_spec = DEMO_MILITARY_BY_KEY.get(key)
        if record_spec is None:
            continue
        audit = audit_person_by_iin(
            conn,
            iin=applicant["iin"],
            expected_name=applicant["full_name"],
        )
        demo_record_key = str(record_spec["demo_record_key"])
        base = RecordAction(
            person_key=key,
            iin=applicant["iin"],
            person_id=audit.person_id,
            demo_record_key=demo_record_key,
            record_kind=str(record_spec["record_kind"]),
            action="pending",
        )
        if not audit.exists or audit.person_id is None:
            report.actions.append(
                RecordAction(
                    **{**asdict(base), "action": "skipped", "detail": "demo person not found by IIN"}
                )
            )
            report.skipped += 1
            continue
        ref = load_active_demo_record(
            conn,
            table="person_military_service",
            id_column="military_id",
            person_id=int(audit.person_id),
            demo_suite=DEMO_SUITE,
            demo_record_key=demo_record_key,
        )
        if ref is None:
            report.actions.append(
                RecordAction(
                    **{**asdict(base), "action": "skipped", "detail": "active demo record not found"}
                )
            )
            report.skipped += 1
            continue
        if not execute:
            report.actions.append(
                RecordAction(
                    **{
                        **asdict(base),
                        "action": "dry_run_void",
                        "detail": "would void via application layer",
                        "military_id": ref.record_id,
                    }
                )
            )
            report.created += 1
            continue
        pending_voids.append(ref)
        report.actions.append(
            RecordAction(**{**asdict(base), "action": "void", "military_id": ref.record_id})
        )

    return report, pending_voids


def execute_rollback_plan(pending_voids: list[DemoSectionRecordRef]) -> None:
    section = _section_service()
    for ref in pending_voids:
        void_record_via_service(
            void_fn=section.void_military_service,
            command_type=COMMAND_TYPE_VOID_MILITARY_SERVICE,
            actor_id=OPS_ACTOR_ID,
            record=ref,
            command_prefix="demo-mil-void",
        )


def run_rollback(*, execute: bool = False, db: Engine | None = None) -> SeedReport:
    db_engine = db or engine
    db_target = parse_db_target(os.getenv("DATABASE_URL", ""))
    _require_execute_allowed(db_target, execute=execute)

    with db_engine.connect() as conn:
        report, pending_voids = build_rollback_plan(conn, execute=execute)

    if execute and pending_voids:
        execute_rollback_plan(pending_voids)
        report.created = len(pending_voids)
    elif execute:
        report.created = 0

    print("=== ROLLBACK REPORT ===")
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, default=str))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed demo Military Service for whitelisted demo persons.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Audit and print manifest without writes (default).",
    )
    mode.add_argument(
        "--execute",
        action="store_true",
        help="Create missing demo military service records idempotently.",
    )
    args = parser.parse_args(argv)
    run(execute=bool(args.execute))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
