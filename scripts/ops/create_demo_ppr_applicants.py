#!/usr/bin/env python3
"""Create two demonstration PPR applicants via application/service layer.

Production-safe one-off ops script. Does NOT run on production by default.
Default mode is dry-run (no writes). Mutations require ``--execute``.

Demo PPR ops on Ubuntu/VPS (``DATABASE_URL`` is taken from the service environment):

.. code-block:: bash

   export CORPSITE_ALLOW_DEMO_PPR_SEED=1
   python scripts/ops/create_demo_ppr_applicants.py --dry-run
   python scripts/ops/create_demo_ppr_applicants.py --execute
   python scripts/ops/seed_demo_employment_biography.py --dry-run
   python scripts/ops/seed_demo_employment_biography.py --execute
   python scripts/ops/seed_demo_military_service.py --dry-run
   python scripts/ops/seed_demo_military_service.py --execute

On production-like hosts, ``CORPSITE_ALLOW_DEMO_PPR_SEED=1`` is mandatory for ``--execute``
and ``--rollback``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

REPO_ROOT = __file__.replace("\\", "/").rsplit("/", 3)[0]
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from app.db.engine import engine
from app.db.models.personnel_migration import (
    EDUCATION_KIND_BASIC,
    TRAINING_KIND_CONTINUING_EDUCATION,
)
from app.ppr.application.authorization import AllowAllAuthorizationPort
from app.ppr.application.command_models import (
    COMMAND_TYPE_ADD_EDUCATION,
    COMMAND_TYPE_ADD_TRAINING,
    COMMAND_TYPE_MATERIALIZE_PPR,
    MaterializePprPayload,
    PprCommandEnvelope,
)
from app.ppr.application.lifecycle_service import PprLifecycleApplicationService
from app.ppr.application.section_service import PprSectionApplicationService
from app.ppr.domain.models import HR_RELATIONSHIP_CANDIDATE
from app.services.ppr_candidate_service import (
    save_intended_employment,
    update_hr_relationship_context_tx,
)

DEMO_MATCH_KEY_PREFIX = "demo:ppr-applicant:"
DEMO_SOURCE = "manual"
DEMO_METADATA: dict[str, Any] = {"demo": True, "demo_suite": "ppr_applicant_v1"}
ALLOWED_IINS = frozenset({"900101350123", "950515450456"})
OPS_ACTOR_ID = "ops:create_demo_ppr_applicants"
PRODUCTION_HOST_MARKERS = frozenset({"46.247.42.47", "mmc.004.kz"})

APPLICANTS: list[dict[str, Any]] = [
    {
        "key": "ahmetov",
        "full_name": "Ахметов Айдар Серикович",
        "iin": "900101350123",
        "birth_date": date(1990, 1, 1),
        "intended_rate": 1.0,
        "intended_complete": True,
        "education": {
            "education_kind": EDUCATION_KIND_BASIC,
            "institution_name": "КазНМУ им. С.Д. Асфендиярова",
            "specialty": "Лечебное дело",
            "qualification": "Врач",
            "completed_at": date(2014, 6, 30),
        },
        "training": {
            "training_kind": TRAINING_KIND_CONTINUING_EDUCATION,
            "title": "Организация архивного дела в медицинских учреждениях",
            "organization_name": "Казахский медицинский университет непрерывного образования",
            "started_at": date(2024, 9, 1),
            "completed_at": date(2025, 2, 28),
            "hours": Decimal("72"),
            "metadata": {**DEMO_METADATA, "source_field": "continuing_education"},
        },
    },
    {
        "key": "seitova",
        "full_name": "Сейтова Алия Маратовна",
        "iin": "950515450456",
        "birth_date": date(1995, 5, 15),
        "intended_rate": 0.5,
        "intended_complete": False,
        "education": {
            "education_kind": EDUCATION_KIND_BASIC,
            "institution_name": "Карагандинский медицинский университет",
            "specialty": "Сестринское дело",
            "qualification": "Медицинская сестра",
            "completed_at": date(2018, 6, 25),
        },
        "training": None,
    },
]


@dataclass(frozen=True, slots=True)
class DbTarget:
    host: str
    port: int | None
    dbname: str
    schema: str = "public"
    production_like: bool = False


@dataclass(frozen=True, slots=True)
class PlacementCandidate:
    org_group_id: int
    org_unit_id: int
    position_id: int
    group_name: str
    unit_code: str
    unit_name: str
    position_name: str


@dataclass(frozen=True, slots=True)
class PersonAudit:
    exists: bool
    person_id: int | None
    full_name: str | None
    person_status: str | None
    match_key: str | None
    source: str | None
    hr_relationship_context: str | None
    has_active_employee: bool
    demo_marked: bool
    safe_to_touch: bool
    block_reason: str | None


def parse_db_target(database_url: str) -> DbTarget:
    raw = (database_url or "").strip()
    if not raw:
        raise RuntimeError("DATABASE_URL is not set")
    normalized = raw.replace("postgresql+psycopg2://", "postgresql://").replace(
        "postgresql+psycopg://",
        "postgresql://",
    )
    parsed = urlparse(normalized)
    host = (parsed.hostname or "").strip() or "unknown"
    port = parsed.port
    dbname = (parsed.path or "").lstrip("/") or "unknown"
    production_like = host in PRODUCTION_HOST_MARKERS
    return DbTarget(host=host, port=port, dbname=dbname, production_like=production_like)


def is_demo_match_key(match_key: str | None) -> bool:
    return bool(match_key) and str(match_key).startswith(DEMO_MATCH_KEY_PREFIX)


def audit_person_by_iin(conn: Connection, *, iin: str, expected_name: str) -> PersonAudit:
    row = conn.execute(
        text(
            """
            SELECT
                p.person_id,
                p.full_name,
                p.person_status,
                p.match_key,
                p.source,
                prm.hr_relationship_context,
                EXISTS (
                    SELECT 1
                    FROM public.employees e
                    WHERE e.person_id = p.person_id
                      AND COALESCE(e.is_active, TRUE) = TRUE
                ) AS has_active_employee
            FROM public.persons p
            LEFT JOIN public.personnel_record_metadata prm
              ON prm.person_id = p.person_id
            WHERE p.iin = :iin
            LIMIT 1
            """
        ),
        {"iin": iin},
    ).mappings().first()

    if row is None:
        return PersonAudit(
            exists=False,
            person_id=None,
            full_name=None,
            person_status=None,
            match_key=None,
            source=None,
            hr_relationship_context=None,
            has_active_employee=False,
            demo_marked=False,
            safe_to_touch=True,
            block_reason=None,
        )

    match_key = str(row.get("match_key") or "") or None
    source = str(row.get("source") or "") or None
    full_name = str(row.get("full_name") or "").strip()
    demo_marked = is_demo_match_key(match_key)
    has_employee = bool(row.get("has_active_employee"))

    block_reason: str | None = None
    safe = True
    if has_employee:
        safe = False
        block_reason = "active employee exists — refusing to modify real person"
    elif not demo_marked and full_name != expected_name:
        safe = False
        block_reason = (
            f"person with IIN exists but is not demo-marked and name differs "
            f"({full_name!r} != {expected_name!r})"
        )
    elif not demo_marked:
        safe = False
        block_reason = "person with IIN exists but is not demo-marked"

    return PersonAudit(
        exists=True,
        person_id=int(row["person_id"]),
        full_name=full_name or None,
        person_status=str(row.get("person_status") or "") or None,
        match_key=match_key,
        source=source,
        hr_relationship_context=str(row.get("hr_relationship_context") or "") or None,
        has_active_employee=has_employee,
        demo_marked=demo_marked,
        safe_to_touch=safe,
        block_reason=block_reason,
    )


def list_placement_candidates(conn: Connection) -> list[PlacementCandidate]:
    rows = conn.execute(
        text(
            """
            SELECT
                ou.group_id AS org_group_id,
                ou.unit_id AS org_unit_id,
                p.position_id,
                dg.group_name,
                ou.code AS unit_code,
                ou.name AS unit_name,
                p.name AS position_name
            FROM public.org_units ou
            JOIN public.org_unit_allowed_positions ouap
              ON ouap.org_unit_id = ou.unit_id
            JOIN public.positions p
              ON p.position_id = ouap.position_id
            JOIN public.deps_group dg
              ON dg.group_id = ou.group_id
            WHERE ou.group_id IS NOT NULL
              AND COALESCE(ou.is_active, TRUE) = TRUE
            ORDER BY
                CASE WHEN UPPER(ou.code) = 'HR' THEN 0 ELSE 1 END,
                ou.group_id ASC,
                ou.unit_id ASC,
                p.position_id ASC
            """
        )
    ).mappings().all()
    return [
        PlacementCandidate(
            org_group_id=int(row["org_group_id"]),
            org_unit_id=int(row["org_unit_id"]),
            position_id=int(row["position_id"]),
            group_name=str(row["group_name"]),
            unit_code=str(row.get("unit_code") or ""),
            unit_name=str(row["unit_name"]),
            position_name=str(row["position_name"]),
        )
        for row in rows
    ]


def resolve_placement(
    candidates: list[PlacementCandidate],
    *,
    complete: bool,
    preferred_position_hint: str | None = None,
    prefer_unit_code: str | None = "HR",
) -> PlacementCandidate | None:
    if not candidates:
        return None

    filtered = list(candidates)
    if prefer_unit_code:
        code = prefer_unit_code.strip().upper()
        by_unit = [row for row in filtered if row.unit_code.strip().upper() == code]
        if by_unit:
            filtered = by_unit

    if not complete:
        base = filtered[0]
        return PlacementCandidate(
            org_group_id=base.org_group_id,
            org_unit_id=base.org_unit_id,
            position_id=base.position_id,
            group_name=base.group_name,
            unit_code=base.unit_code,
            unit_name=base.unit_name,
            position_name=base.position_name,
        )

    if preferred_position_hint:
        hint = preferred_position_hint.casefold()
        for row in filtered:
            if hint in row.position_name.casefold():
                return row

    # Stable fallback: highest position_id inside preferred unit/group slice.
    return max(filtered, key=lambda row: row.position_id)


def _command_envelope(
    *,
    command_type: str,
    person_id: int,
    payload: Any,
) -> PprCommandEnvelope:
    return PprCommandEnvelope(
        command_id=f"demo-ppr-{uuid4().hex}",
        command_type=command_type,
        actor_id=OPS_ACTOR_ID,
        requested_at=datetime.now(UTC),
        payload=payload,
        person_id=person_id,
        correlation_id=f"demo-ppr-{uuid4().hex[:12]}",
    )


def _lifecycle_service() -> PprLifecycleApplicationService:
    return PprLifecycleApplicationService(authorization=AllowAllAuthorizationPort())


def _section_service() -> PprSectionApplicationService:
    return PprSectionApplicationService(authorization=AllowAllAuthorizationPort())


def _education_exists(conn: Connection, *, person_id: int, institution_name: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM public.person_education
            WHERE person_id = :person_id
              AND institution_name = :institution_name
              AND lifecycle_status = 'active'
            LIMIT 1
            """
        ),
        {"person_id": person_id, "institution_name": institution_name},
    ).first()
    return row is not None


def _training_exists(
    conn: Connection,
    *,
    person_id: int,
    title: str,
    organization_name: str,
) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM public.person_training
            WHERE person_id = :person_id
              AND title = :title
              AND organization_name = :organization_name
              AND lifecycle_status = 'active'
            LIMIT 1
            """
        ),
        {
            "person_id": person_id,
            "title": title,
            "organization_name": organization_name,
        },
    ).first()
    return row is not None


def _insert_demo_person(
    conn: Connection,
    *,
    full_name: str,
    iin: str,
    birth_date: date,
    demo_key: str,
) -> int:
    row = conn.execute(
        text(
            """
            INSERT INTO public.persons (
                full_name, iin, birth_date, match_key, person_status, source
            )
            VALUES (
                :full_name, :iin, :birth_date, :match_key, 'active', :source
            )
            RETURNING person_id
            """
        ),
        {
            "full_name": full_name,
            "iin": iin,
            "birth_date": birth_date,
            "match_key": f"{DEMO_MATCH_KEY_PREFIX}{demo_key}",
            "source": DEMO_SOURCE,
        },
    ).mappings().one()
    return int(row["person_id"])


def _ensure_demo_person(
    conn: Connection,
    *,
    spec: dict[str, Any],
    audit: PersonAudit,
    execute: bool,
) -> int | None:
    if audit.exists:
        if not audit.safe_to_touch:
            raise RuntimeError(audit.block_reason or "unsafe existing person")
        return audit.person_id

    if not execute:
        return None

    return _insert_demo_person(
        conn,
        full_name=spec["full_name"],
        iin=spec["iin"],
        birth_date=spec["birth_date"],
        demo_key=spec["key"],
    )


def _ensure_candidate_envelope(conn: Connection, *, person_id: int, execute: bool) -> str:
    if not execute:
        return "dry_run_materialize"

    lifecycle = _lifecycle_service()
    result = lifecycle.materialize_ppr(
        _command_envelope(
            command_type=COMMAND_TYPE_MATERIALIZE_PPR,
            person_id=person_id,
            payload=MaterializePprPayload(hr_relationship_context=HR_RELATIONSHIP_CANDIDATE),
        )
    )
    status = result.status

    row = conn.execute(
        text(
            """
            SELECT hr_relationship_context
            FROM public.personnel_record_metadata
            WHERE person_id = :person_id
            """
        ),
        {"person_id": person_id},
    ).mappings().first()
    current = str(row.get("hr_relationship_context") or "") if row else ""
    if current != HR_RELATIONSHIP_CANDIDATE:
        update_hr_relationship_context_tx(
            conn,
            person_id=person_id,
            hr_relationship_context=HR_RELATIONSHIP_CANDIDATE,
        )
        status = f"{status}+context_set_candidate"
    return status


def _ensure_education(
    conn: Connection,
    *,
    person_id: int,
    education: dict[str, Any],
    execute: bool,
) -> str:
    institution_name = education["institution_name"]
    if _education_exists(conn, person_id=person_id, institution_name=institution_name):
        return "already_exists"
    if not execute:
        return "dry_run_add_education"

    section = _section_service()
    payload = {**education, "metadata": DEMO_METADATA}
    result = section.add_education(
        _command_envelope(
            command_type=COMMAND_TYPE_ADD_EDUCATION,
            person_id=person_id,
            payload=payload,
        )
    )
    return result.status


def _ensure_training(
    conn: Connection,
    *,
    person_id: int,
    training: dict[str, Any],
    execute: bool,
) -> str:
    if _training_exists(
        conn,
        person_id=person_id,
        title=training["title"],
        organization_name=training["organization_name"],
    ):
        return "already_exists"
    if not execute:
        return "dry_run_add_training"

    section = _section_service()
    payload = dict(training)
    if "metadata" not in payload:
        payload["metadata"] = DEMO_METADATA
    result = section.add_training(
        _command_envelope(
            command_type=COMMAND_TYPE_ADD_TRAINING,
            person_id=person_id,
            payload=payload,
        )
    )
    return result.status


def run_audit(conn: Connection, db_target: DbTarget) -> dict[str, Any]:
    placements = list_placement_candidates(conn)
    placement_for_complete = resolve_placement(
        placements,
        complete=True,
        preferred_position_hint="архив",
    )
    placement_for_partial = resolve_placement(placements, complete=False)

    applicant_audits: dict[str, Any] = {}
    for spec in APPLICANTS:
        audit = audit_person_by_iin(conn, iin=spec["iin"], expected_name=spec["full_name"])
        applicant_audits[spec["key"]] = {
            "spec": spec["full_name"],
            "iin": spec["iin"],
            "audit": audit,
        }

    return {
        "db_target": db_target,
        "placement_candidates_count": len(placements),
        "placement_candidates_preview": [
            {
                "org_group_id": p.org_group_id,
                "group_name": p.group_name,
                "org_unit_id": p.org_unit_id,
                "unit_code": p.unit_code,
                "unit_name": p.unit_name,
                "position_id": p.position_id,
                "position_name": p.position_name,
            }
            for p in placements[:10]
        ],
        "resolved_placement_complete": placement_for_complete,
        "resolved_placement_partial": placement_for_partial,
        "applicant_audits": applicant_audits,
    }


def build_manifest(audit_report: dict[str, Any], *, execute: bool) -> list[dict[str, Any]]:
    complete_placement: PlacementCandidate | None = audit_report["resolved_placement_complete"]
    partial_placement: PlacementCandidate | None = audit_report["resolved_placement_partial"]
    if complete_placement is None or partial_placement is None:
        raise RuntimeError("No verified org group/unit/position triple in catalog")

    manifest: list[dict[str, Any]] = []
    for spec in APPLICANTS:
        placement = complete_placement if spec.get("intended_complete", True) else partial_placement
        intended_position_id = placement.position_id if spec.get("intended_complete", True) else None
        audit: PersonAudit = audit_report["applicant_audits"][spec["key"]]["audit"]
        manifest.append(
            {
                "key": spec["key"],
                "full_name": spec["full_name"],
                "iin": spec["iin"],
                "mode": "execute" if execute else "dry_run",
                "person_action": "create_demo_person" if not audit.exists else "reuse_demo_person",
                "person_id": audit.person_id,
                "hr_relationship_context": HR_RELATIONSHIP_CANDIDATE,
                "employee": None,
                "intended_org_group_id": placement.org_group_id,
                "intended_org_group_name": placement.group_name,
                "intended_org_unit_id": placement.org_unit_id,
                "intended_org_unit_code": placement.unit_code,
                "intended_org_unit_name": placement.unit_name,
                "intended_position_id": intended_position_id,
                "intended_position_name": placement.position_name if intended_position_id else None,
                "employment_rate": spec["intended_rate"],
                "education": spec["education"]["institution_name"],
                "training": (
                    spec["training"]["title"] if spec.get("training") else None
                ),
                "demo_markers": {
                    "match_key_prefix": DEMO_MATCH_KEY_PREFIX,
                    "source": DEMO_SOURCE,
                    "metadata": DEMO_METADATA,
                },
                "audit_safe_to_touch": audit.safe_to_touch,
                "audit_block_reason": audit.block_reason,
            }
        )
    return manifest


def execute_manifest(
    audit_report: dict[str, Any],
    *,
    execute: bool,
    db_engine: Engine,
) -> list[dict[str, Any]]:
    complete_placement: PlacementCandidate = audit_report["resolved_placement_complete"]
    partial_placement: PlacementCandidate = audit_report["resolved_placement_partial"]
    results: list[dict[str, Any]] = []

    for spec in APPLICANTS:
        with db_engine.connect() as conn:
            audit: PersonAudit = audit_person_by_iin(
                conn, iin=spec["iin"], expected_name=spec["full_name"]
            )
        if not audit.safe_to_touch and audit.exists:
            if execute:
                raise RuntimeError(
                    f"{spec['key']}: {audit.block_reason or 'unsafe to touch existing person'}"
                )
            results.append(
                {
                    "key": spec["key"],
                    "person_id": audit.person_id,
                    "skipped": True,
                    "reason": audit.block_reason,
                }
            )
            continue

        placement = complete_placement if spec.get("intended_complete", True) else partial_placement
        intended_position_id = placement.position_id if spec.get("intended_complete", True) else None

        person_id: int | None = None
        if execute:
            with db_engine.begin() as conn:
                person_id = _ensure_demo_person(conn, spec=spec, audit=audit, execute=True)
        else:
            person_id = audit.person_id

        envelope_status = None
        intended_status = None
        education_status = None
        training_status = None

        if person_id is not None or (not execute and audit.exists):
            effective_person_id = person_id if person_id is not None else audit.person_id
            assert effective_person_id is not None

            with db_engine.connect() as conn:
                envelope_status = _ensure_candidate_envelope(
                    conn, person_id=effective_person_id, execute=execute
                )

            if execute:
                with db_engine.begin() as conn:
                    save_intended_employment(
                        conn,
                        person_id=effective_person_id,
                        org_group_id=placement.org_group_id,
                        org_unit_id=placement.org_unit_id,
                        position_id=intended_position_id,
                        employment_rate=float(spec["intended_rate"]),
                    )
                intended_status = "committed"
            else:
                intended_status = "dry_run_save_intended_employment"

            with db_engine.connect() as conn:
                education_status = _ensure_education(
                    conn,
                    person_id=effective_person_id,
                    education=spec["education"],
                    execute=execute,
                )
                if spec.get("training"):
                    training_status = _ensure_training(
                        conn,
                        person_id=effective_person_id,
                        training=spec["training"],
                        execute=execute,
                    )

        results.append(
            {
                "key": spec["key"],
                "person_id": person_id if person_id is not None else audit.person_id,
                "envelope_status": envelope_status,
                "intended_status": intended_status,
                "education_status": education_status,
                "training_status": training_status,
            }
        )
    return results


def _delete_person_demo_data(conn: Connection, person_id: int) -> None:
    """Delete PPR section rows and envelope for a demo person (rollback helper)."""
    conn.execute(
        text("DELETE FROM public.person_military_service WHERE person_id = :person_id"),
        {"person_id": person_id},
    )
    conn.execute(
        text("DELETE FROM public.person_external_employment WHERE person_id = :person_id"),
        {"person_id": person_id},
    )
    conn.execute(
        text("DELETE FROM public.person_relatives WHERE person_id = :person_id"),
        {"person_id": person_id},
    )
    conn.execute(
        text("DELETE FROM public.person_training WHERE person_id = :person_id"),
        {"person_id": person_id},
    )
    conn.execute(
        text("DELETE FROM public.person_education WHERE person_id = :person_id"),
        {"person_id": person_id},
    )
    conn.execute(
        text("DELETE FROM public.personnel_record_events WHERE person_id = :person_id"),
        {"person_id": person_id},
    )
    conn.execute(
        text("DELETE FROM public.ppr_command_executions WHERE person_id = :person_id"),
        {"person_id": person_id},
    )
    conn.execute(
        text("DELETE FROM public.personnel_record_metadata WHERE person_id = :person_id"),
        {"person_id": person_id},
    )
    conn.execute(
        text("DELETE FROM public.persons WHERE person_id = :person_id"),
        {"person_id": person_id},
    )


def rollback_demo_applicants(conn: Connection, *, execute: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in APPLICANTS:
        audit = audit_person_by_iin(conn, iin=spec["iin"], expected_name=spec["full_name"])
        if not audit.exists:
            rows.append({"key": spec["key"], "action": "skip_not_found"})
            continue
        if not audit.demo_marked:
            raise RuntimeError(f"{spec['key']}: refusing rollback for non-demo person_id={audit.person_id}")
        if audit.has_active_employee:
            raise RuntimeError(f"{spec['key']}: refusing rollback — active employee exists")

        if not execute:
            rows.append({"key": spec["key"], "action": "dry_run_delete", "person_id": audit.person_id})
            continue

        person_id = int(audit.person_id)
        _delete_person_demo_data(conn, person_id)
        rows.append({"key": spec["key"], "action": "deleted", "person_id": person_id})
    return rows


def _require_execute_allowed(db_target: DbTarget, *, execute: bool, rollback: bool) -> None:
    if not execute and not rollback:
        return
    if os.getenv("CORPSITE_ALLOW_DEMO_PPR_SEED") == "1":
        return
    if db_target.production_like:
        raise SystemExit(
            "Refusing mutating operation on production-like database. "
            "Set CORPSITE_ALLOW_DEMO_PPR_SEED=1 to acknowledge."
        )


def _print_audit_report(report: dict[str, Any]) -> None:
    db_target: DbTarget = report["db_target"]
    print("=== AUDIT ===")
    print(
        json.dumps(
            {
                "host": db_target.host,
                "port": db_target.port,
                "dbname": db_target.dbname,
                "schema": db_target.schema,
                "production_like": db_target.production_like,
                "placement_candidates_count": report["placement_candidates_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print("placement_candidates_preview:")
    print(json.dumps(report["placement_candidates_preview"], ensure_ascii=False, indent=2))
    for key, item in report["applicant_audits"].items():
        audit: PersonAudit = item["audit"]
        print(
            f"applicant {key}: exists={audit.exists} person_id={audit.person_id} "
            f"safe={audit.safe_to_touch} block={audit.block_reason}"
        )


def run(
    *,
    execute: bool = False,
    rollback: bool = False,
    db: Engine | None = None,
) -> dict[str, Any]:
    db_engine = db or engine
    db_target = parse_db_target(os.getenv("DATABASE_URL", ""))
    _require_execute_allowed(db_target, execute=execute, rollback=rollback)

    with db_engine.connect() as conn:
        audit_report = run_audit(conn, db_target)
        _print_audit_report(audit_report)

        if rollback:
            with db_engine.begin() as tx_conn:
                rollback_rows = rollback_demo_applicants(tx_conn, execute=execute)
            return {"mode": "rollback", "execute": execute, "rollback": rollback_rows}

        manifest = build_manifest(audit_report, execute=execute)
        print("=== MANIFEST ===")
        print(json.dumps(manifest, ensure_ascii=False, indent=2, default=str))

        results = execute_manifest(audit_report, execute=execute, db_engine=db_engine)

        print("=== RESULT ===")
        print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
        return {
            "mode": "execute" if execute else "dry_run",
            "db_target": db_target,
            "manifest": manifest,
            "results": results,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create demo PPR applicants (CANDIDATE) via application layer.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Audit catalog and print manifest without writes (default).",
    )
    mode.add_argument(
        "--execute",
        action="store_true",
        help="Create or idempotently refresh demo applicants.",
    )
    mode.add_argument(
        "--rollback",
        action="store_true",
        help="Delete demo-marked applicants by whitelisted IIN only.",
    )
    args = parser.parse_args(argv)
    execute = bool(args.execute)
    rollback = bool(args.rollback)
    run(execute=execute, rollback=rollback)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
