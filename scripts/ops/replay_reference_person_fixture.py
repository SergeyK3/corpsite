#!/usr/bin/env python3
"""Replay tests/fixtures/ppr_reference_person.json through Personnel Intake flow.

Uses application services only (register → intake draft → HR review → transfer).
Does not write directly to PPR section tables outside the intake transfer path.

Local/dev only. Default mode is dry-run; mutations require ``--execute``.

.. code-block:: bash

   python scripts/ops/replay_reference_person_fixture.py --dry-run
   export CORPSITE_ALLOW_DEMO_PPR_SEED=1
   python scripts/ops/replay_reference_person_fixture.py --execute
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

load_dotenv(REPO_ROOT / ".env")

from sqlalchemy.engine import Connection, Engine

from app.db.engine import engine as default_engine
from app.personnel_applications.application.registration_service import (
    build_card_href,
    preview_registration,
    register_personnel_application,
)
from app.personnel_applications.domain.status import VACANCY_CHECK_CONFIRMED_VISUALLY
from app.personnel_applications.infrastructure.repository import SqlAlchemyPersonnelApplicationRepository
from app.personnel_intake.application.intake_section_utils import is_intake_section_empty
from app.personnel_intake.application.intake_service import (
    autosave_intake_draft,
    issue_intake_link,
    submit_intake_draft,
)
from app.personnel_intake.domain.errors import PersonnelIntakeConflictError
from app.personnel_intake.infrastructure.repository import SqlAlchemyPersonnelIntakeRepository
from app.personnel_intake.infrastructure.review_repository import SqlAlchemyPersonnelIntakeReviewRepository
from app.personnel_intake.application.review_service import (
    accept_intake_section,
    load_intake_review_state,
    skip_intake_section,
)
from app.personnel_intake.application.transfer_service import transfer_intake_to_ppr
from app.personnel_intake.domain.review_status import (
    INTAKE_REVIEW_SECTIONS,
    INTAKE_SECTION_REVIEW_ACCEPTED,
    INTAKE_SECTION_REVIEW_SKIPPED,
    INTAKE_SECTION_REVIEW_TERMINAL,
    INTAKE_TRANSFER_STATUS_COMPLETED,
)
from app.personnel_intake.domain.status import INTAKE_DRAFT_STATUS_SUBMITTED
from app.ppr.domain.section_models import (
    SECTION_CODE_PPR_EDUCATION,
    SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY,
    SECTION_CODE_PPR_FAMILY,
    SECTION_CODE_PPR_MILITARY,
    SECTION_CODE_PPR_TRAINING,
)
from app.ppr.read.query_service import PprQueryApplicationService
from scripts.ops.reference_person_fixture_mapper import (
    DEFAULT_FIXTURE_PATH,
    fixture_identity,
    fixture_skipped_sections,
    fixture_to_intake_draft,
    load_reference_fixture,
)

OPS_ACTOR_ID = "ops:replay_reference_person_fixture"
LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
PRODUCTION_HOST_MARKERS = frozenset({"46.247.42.47", "mmc.004.kz"})
BLOCKED_URL_MARKERS = (
    "amazonaws.com",
    "amazonaws",
    "rds.",
    ".prod.",
    "-prod.",
    "production.",
    "azure.com",
    "googleapis.com",
    "cloudsql",
)
DEFAULT_OPS_USER_ID = 1


class SafetyAbort(Exception):
    """Fatal safety violation — stop without side effects."""


def parse_db_target(database_url: str) -> dict[str, Any]:
    raw = (database_url or "").strip()
    if not raw:
        raise SafetyAbort("DATABASE_URL is not set")
    normalized = raw.replace("postgresql+psycopg2://", "postgresql://").replace(
        "postgresql+psycopg://",
        "postgresql://",
    )
    parsed = urlparse(normalized)
    host = (parsed.hostname or "").strip() or "unknown"
    port = parsed.port
    dbname = (parsed.path or "").lstrip("/") or "unknown"
    production_like = host in PRODUCTION_HOST_MARKERS or any(
        marker in normalized.lower() for marker in BLOCKED_URL_MARKERS
    )
    local_dev = host in LOCAL_HOSTS
    return {
        "host": host,
        "port": port,
        "dbname": dbname,
        "production_like": production_like,
        "local_dev": local_dev,
    }


def assert_local_dev_guard(*, execute: bool) -> dict[str, Any]:
    db_target = parse_db_target(os.getenv("DATABASE_URL", ""))
    if not db_target["local_dev"]:
        raise SafetyAbort(
            f"BLOCKED: host {db_target['host']!r} is not classified as local/dev. "
            "Only 127.0.0.1, localhost, and ::1 are permitted."
        )
    if db_target["production_like"]:
        raise SafetyAbort(
            f"BLOCKED: database URL looks production-like (host={db_target['host']!r})."
        )
    if execute:
        if os.getenv("CORPSITE_ALLOW_DEMO_PPR_SEED") != "1":
            raise SafetyAbort(
                "Mutating replay requires CORPSITE_ALLOW_DEMO_PPR_SEED=1 on local/dev."
            )
    return db_target


def _ops_user_id() -> int:
    raw = (os.getenv("PPR_REFERENCE_OPS_USER_ID") or "").strip()
    if not raw:
        return DEFAULT_OPS_USER_ID
    return int(raw)


def _section_review_actions(review_state) -> dict[str, str]:
    return {section.section_code: section.status for section in review_state.sections}


def _resolve_existing_reference(conn: Connection, *, iin: str, idempotency_key: str) -> dict[str, Any] | None:
    preview = preview_registration(conn, iin_raw=iin)
    app_repo = SqlAlchemyPersonnelApplicationRepository(conn)
    by_key = app_repo.get_by_idempotency_key(idempotency_key)
    application_id = by_key.application_id if by_key is not None else preview.active_application_id
    person_id = by_key.person_id if by_key is not None else preview.person_id
    if application_id is None or person_id is None:
        return None
    intake_repo = SqlAlchemyPersonnelIntakeRepository(conn)
    review_repo = SqlAlchemyPersonnelIntakeReviewRepository(conn)
    app = app_repo.require_by_id(application_id)
    draft = intake_repo.get_draft_by_application_id(application_id)
    transfer = review_repo.get_transfer(application_id)
    return {
        "person_id": int(person_id),
        "application_id": int(application_id),
        "card_href": build_card_href(int(person_id)),
        "application_status": app.status,
        "transfer_completed": transfer is not None and transfer.status == INTAKE_TRANSFER_STATUS_COMPLETED,
        "transfer_sections": list(transfer.sections_transferred) if transfer else [],
        "draft_submitted": draft is not None and draft.status == INTAKE_DRAFT_STATUS_SUBMITTED,
    }


def _ensure_intake_submitted(
    conn: Connection,
    *,
    application_id: int,
    user_id: int,
    draft_payload: dict[str, Any],
) -> None:
    intake_repo = SqlAlchemyPersonnelIntakeRepository(conn)
    draft = intake_repo.get_draft_by_application_id(application_id)
    if draft is not None and draft.status == INTAKE_DRAFT_STATUS_SUBMITTED:
        return
    try:
        link = issue_intake_link(
            conn,
            application_id=application_id,
            issued_by_user_id=user_id,
        )
    except PersonnelIntakeConflictError:
        link = issue_intake_link(
            conn,
            application_id=application_id,
            issued_by_user_id=user_id,
            reissue=True,
        )
    autosave_intake_draft(conn, raw_token=link.raw_token, payload=draft_payload)
    submit_intake_draft(conn, raw_token=link.raw_token, payload=draft_payload)


def _review_all_sections(conn: Connection, *, application_id: int, draft_payload: dict[str, Any], user_id: int) -> None:
    review_state = load_intake_review_state(conn, application_id)
    statuses = _section_review_actions(review_state)
    for section_code in INTAKE_REVIEW_SECTIONS:
        if statuses.get(section_code) in INTAKE_SECTION_REVIEW_TERMINAL:
            continue
        if is_intake_section_empty(section_code, draft_payload):
            skip_intake_section(
                conn,
                application_id=application_id,
                section_code=section_code,
                reviewed_by_user_id=user_id,
            )
        else:
            accept_intake_section(
                conn,
                application_id=application_id,
                section_code=section_code,
                reviewed_by_user_id=user_id,
            )


def _materialized_sections_report(person_id: int) -> dict[str, Any]:
    query = PprQueryApplicationService()
    composite = query.load_by_person_id(person_id, include_events=False)
    section_counts = {
        "general": 1 if composite.materialized and composite.general.full_name else 0,
        SECTION_CODE_PPR_EDUCATION: len(composite.education.active),
        SECTION_CODE_PPR_TRAINING: len(composite.training.active),
        SECTION_CODE_PPR_FAMILY: len(composite.family.active),
        SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY: len(composite.external_employment.active),
        SECTION_CODE_PPR_MILITARY: len(composite.military.active),
    }
    materialized = [name for name, count in section_counts.items() if count > 0]
    return {
        "materialized": materialized,
        "section_counts": section_counts,
        "lifecycle_state": composite.lifecycle_state,
        "hr_relationship_context": composite.hr_relationship_context,
    }


def build_report(
    *,
    fixture: dict[str, Any],
    db_target: dict[str, Any],
    execute: bool,
    existing: dict[str, Any] | None,
) -> dict[str, Any]:
    identity = fixture_identity(fixture)
    skipped = fixture_skipped_sections(fixture)
    intake_sections = list(INTAKE_REVIEW_SECTIONS)
    return {
        "mode": "execute" if execute else "dry-run",
        "db_target": db_target,
        "fixture_path": str(DEFAULT_FIXTURE_PATH),
        "fixture_person_key": identity["fixture_person_key"],
        "iin": identity["iin"],
        "full_name": identity["full_name"],
        "idempotency_key": identity["idempotency_key"],
        "application_flow": [
            "register_personnel_application",
            "issue_intake_link",
            "autosave_intake_draft + submit_intake_draft",
            "accept_intake_section / skip_intake_section",
            "transfer_intake_to_ppr",
        ],
        "intake_sections_from_fixture": intake_sections,
        "fixture_sections_skipped_no_intake_schema": skipped,
        "existing_reference": existing,
        "would_create": existing is None,
        "would_reuse": existing is not None,
        "would_skip_mutations": existing is not None and existing.get("transfer_completed"),
    }


def replay_reference_person_fixture(
    *,
    execute: bool = False,
    resolve_only: bool = False,
    db: Engine | None = None,
    fixture_path: Path | None = None,
) -> dict[str, Any]:
    db_target = assert_local_dev_guard(execute=execute)
    fixture = load_reference_fixture(fixture_path)
    identity = fixture_identity(fixture)
    draft_payload = fixture_to_intake_draft(fixture)
    skipped = fixture_skipped_sections(fixture)
    user_id = _ops_user_id()
    db_engine = db or default_engine

    with db_engine.connect() as conn:
        existing = _resolve_existing_reference(
            conn,
            iin=identity["iin"],
            idempotency_key=identity["idempotency_key"],
        )

        if resolve_only:
            if existing is None:
                return {"found": False, "iin": identity["iin"], "fixture_person_key": identity["fixture_person_key"]}
            materialized = _materialized_sections_report(existing["person_id"])
            return {
                "found": True,
                "person_id": existing["person_id"],
                "application_id": existing["application_id"],
                "card_href": existing["card_href"],
                "transfer_completed": existing["transfer_completed"],
                **materialized,
                "fixture_sections_skipped_no_intake_schema": skipped,
            }

        report = build_report(
            fixture=fixture,
            db_target=db_target,
            execute=execute,
            existing=existing,
        )

        if not execute:
            report["status"] = "dry-run"
            return report

        if existing is not None and existing["transfer_completed"]:
            materialized = _materialized_sections_report(existing["person_id"])
            report.update(
                {
                    "status": "idempotent_replay",
                    "person_id": existing["person_id"],
                    "application_id": existing["application_id"],
                    "card_href": existing["card_href"],
                    "transfer_sections": existing["transfer_sections"],
                    "fixture_sections_skipped_no_intake_schema": skipped,
                    **materialized,
                }
            )
            return report

        with db_engine.begin() as tx:
            registration = register_personnel_application(
                tx,
                iin_raw=identity["iin"],
                full_name=identity["full_name"],
                birth_date=date.fromisoformat(identity["birth_date"]) if identity["birth_date"] else None,
                application_received_at=date.today(),
                vacancy_check_status=VACANCY_CHECK_CONFIRMED_VISUALLY,
                vacancy_checked_at=None,
                vacancy_checked_by_user_id=None,
                intended_org_group_id=None,
                intended_org_unit_id=None,
                intended_position_id=None,
                intended_employment_rate=None,
                intended_vacancy_text=None,
                contact_mobile_phone=draft_payload["contacts"]["mobile_phone"] or None,
                contact_email=draft_payload["contacts"]["email"] or None,
                hr_note=f"fixture_person_key={identity['fixture_person_key']}",
                idempotency_key=identity["idempotency_key"],
                registered_by_user_id=user_id,
                actor_id=OPS_ACTOR_ID,
            )
        application_id = registration.application_id
        person_id = registration.person_id

        with db_engine.begin() as tx:
            _ensure_intake_submitted(
                tx,
                application_id=application_id,
                user_id=user_id,
                draft_payload=draft_payload,
            )

        with db_engine.begin() as tx:
            _review_all_sections(
                tx,
                application_id=application_id,
                draft_payload=draft_payload,
                user_id=user_id,
            )

        with db_engine.begin() as tx:
            transfer_result = transfer_intake_to_ppr(
                tx,
                application_id=application_id,
                transferred_by_user_id=user_id,
                actor_id=OPS_ACTOR_ID,
            )

        materialized = _materialized_sections_report(person_id)
        report.update(
            {
                "status": "idempotent_replay" if transfer_result.idempotent_replay else "completed",
                "person_id": person_id,
                "application_id": application_id,
                "card_href": build_card_href(person_id),
                "registration_action": registration.action,
                "transfer_sections": list(transfer_result.transfer.sections_transferred),
                "fixture_sections_skipped_no_intake_schema": skipped,
                **materialized,
            }
        )
        return report


def _print_report(report: dict[str, Any]) -> None:
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview actions without writes (default).")
    mode.add_argument("--execute", action="store_true", help="Run intake replay and transfer.")
    parser.add_argument(
        "--resolve-only",
        action="store_true",
        help="Print existing reference person_id/card_href by IIN/fixture key (read-only).",
    )
    parser.add_argument(
        "--fixture-path",
        type=Path,
        default=None,
        help=f"Override fixture path (default: {DEFAULT_FIXTURE_PATH})",
    )
    args = parser.parse_args()
    execute = bool(args.execute)
    if not execute and not args.resolve_only:
        args.dry_run = True

    try:
        report = replay_reference_person_fixture(
            execute=execute,
            resolve_only=args.resolve_only,
            fixture_path=args.fixture_path,
        )
    except SafetyAbort as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise

    _print_report(report)
    if args.resolve_only and not report.get("found"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
