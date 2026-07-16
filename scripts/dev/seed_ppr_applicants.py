#!/usr/bin/env python3
"""Seed two PPR applicants (CANDIDATE) with education and intended employment.

Usage:
  python scripts/dev/seed_ppr_applicants.py
  python scripts/dev/seed_ppr_applicants.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from uuid import uuid4

from sqlalchemy import text

REPO_ROOT = __file__.replace("\\", "/").rsplit("/", 3)[0]
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from app.db.engine import engine
from app.db.models.personnel_migration import (
    EDUCATION_KIND_BASIC,
    TRAINING_KIND_CONTINUING_EDUCATION,
)
from app.ppr.domain.models import HR_RELATIONSHIP_CANDIDATE
from app.services.ppr_candidate_service import save_intended_employment

APPLICANTS = [
    {
        "key": "ahmetov",
        "full_name": "Ахметов Айдар Серикович",
        "iin": "900101350123",
        "birth_date": date(1990, 1, 1),
        "education": {
            "education_kind": EDUCATION_KIND_BASIC,
            "institution_name": "КазНМУ им. С.Д. Асфендиярова",
            "specialty": "Лечебное дело",
            "qualification": "Врач",
            "completed_at": date(2014, 6, 30),
        },
        "intended_rate": 1.0,
        "intended_complete": True,
        "training": [
            {
                "training_kind": TRAINING_KIND_CONTINUING_EDUCATION,
                "title": "Организация архивного дела в медицинских учреждениях",
                "organization_name": "Казахский медицинский университет непрерывного образования",
                "started_at": date(2024, 9, 1),
                "completed_at": date(2025, 2, 28),
                "hours": 72,
                "source_field": "continuing_education",
            },
        ],
    },
    {
        "key": "seitova",
        "full_name": "Сейтова Алия Маратовна",
        "iin": "950515450456",
        "birth_date": date(1995, 5, 15),
        "education": {
            "education_kind": EDUCATION_KIND_BASIC,
            "institution_name": "Карагандинский медицинский университет",
            "specialty": "Сестринское дело",
            "qualification": "Медицинская сестра",
            "completed_at": date(2018, 6, 25),
        },
        "intended_rate": 0.5,
        "intended_complete": False,
        "training": [],
    },
]


def _pick_placement(conn) -> tuple[int, int, int]:
    """Pick a consistent org_group_id + org_unit_id + position_id triple.

    Prefers HR (unit 73) with «Архивариус МЦ» when present — matches Ahmetov's
    test narrative. Never uses the MMC root (unit 41 / ORG_MAIN): its group_id is
    NULL and must not be paired with a deps_group row.
    """
    preferred = conn.execute(
        text(
            """
            SELECT ou.group_id, ou.unit_id, p.position_id
            FROM public.org_units ou
            JOIN public.org_unit_allowed_positions ouap
              ON ouap.org_unit_id = ou.unit_id
            JOIN public.positions p
              ON p.position_id = ouap.position_id
            WHERE ou.unit_id = 73
              AND p.position_id = 340
              AND ou.group_id IS NOT NULL
              AND COALESCE(ou.is_active, TRUE) = TRUE
            LIMIT 1
            """
        )
    ).mappings().first()
    if preferred is not None:
        return (
            int(preferred["group_id"]),
            int(preferred["unit_id"]),
            int(preferred["position_id"]),
        )

    row = conn.execute(
        text(
            """
            SELECT ou.group_id, ou.unit_id, MIN(p.position_id) AS position_id
            FROM public.org_units ou
            JOIN public.org_unit_allowed_positions ouap
              ON ouap.org_unit_id = ou.unit_id
            JOIN public.positions p
              ON p.position_id = ouap.position_id
            WHERE ou.group_id IS NOT NULL
              AND COALESCE(ou.is_active, TRUE) = TRUE
            GROUP BY ou.group_id, ou.unit_id
            ORDER BY ou.group_id ASC, ou.unit_id ASC
            LIMIT 1
            """
        )
    ).mappings().first()
    if row is None:
        raise RuntimeError(
            "No org unit with group_id and allowed positions — seed org structure first."
        )
    return int(row["group_id"]), int(row["unit_id"]), int(row["position_id"])


def _upsert_person(conn, *, full_name: str, iin: str, birth_date: date) -> int:
    existing = conn.execute(
        text("SELECT person_id FROM public.persons WHERE iin = :iin LIMIT 1"),
        {"iin": iin},
    ).mappings().first()
    if existing:
        person_id = int(existing["person_id"])
        conn.execute(
            text(
                """
                UPDATE public.persons
                SET full_name = :full_name,
                    birth_date = :birth_date,
                    person_status = 'active',
                    updated_at = now()
                WHERE person_id = :person_id
                """
            ),
            {"person_id": person_id, "full_name": full_name, "birth_date": birth_date},
        )
        return person_id

    row = conn.execute(
        text(
            """
            INSERT INTO public.persons (
                full_name, iin, birth_date, match_key, person_status, source
            )
            VALUES (
                :full_name, :iin, :birth_date, :match_key, 'active', 'enrollment'
            )
            RETURNING person_id
            """
        ),
        {
            "full_name": full_name,
            "iin": iin,
            "birth_date": birth_date,
            "match_key": f"seed-applicant:{uuid4().hex[:10]}",
        },
    ).mappings().one()
    return int(row["person_id"])


def _ensure_candidate_envelope(conn, person_id: int) -> None:
    conn.execute(
        text(
            """
            INSERT INTO public.personnel_record_metadata (
                person_id, ppr_lifecycle_state, hr_relationship_context, version
            )
            VALUES (:person_id, 'CREATED', :ctx, 1)
            ON CONFLICT (person_id) DO UPDATE
            SET hr_relationship_context = EXCLUDED.hr_relationship_context,
                updated_at = now()
            """
        ),
        {"person_id": person_id, "ctx": HR_RELATIONSHIP_CANDIDATE},
    )


def _materialize_candidate(person_id: int) -> None:
    with engine.begin() as conn:
        _ensure_candidate_envelope(conn, person_id)


def _insert_education(conn, *, person_id: int, education: dict) -> None:
    conn.execute(
        text(
            """
            DELETE FROM public.person_education
            WHERE person_id = :person_id
              AND institution_name = :institution_name
            """
        ),
        {"person_id": person_id, "institution_name": education["institution_name"]},
    )
    conn.execute(
        text(
            """
            INSERT INTO public.person_education (
                person_id,
                education_kind,
                institution_name,
                specialty,
                qualification,
                completed_at,
                verification_status,
                lifecycle_status
            )
            VALUES (
                :person_id,
                :education_kind,
                :institution_name,
                :specialty,
                :qualification,
                :completed_at,
                'verified',
                'active'
            )
            """
        ),
        {"person_id": person_id, **education},
    )


def _replace_training(conn, *, person_id: int, records: list[dict]) -> None:
    conn.execute(
        text("DELETE FROM public.person_training WHERE person_id = :person_id"),
        {"person_id": person_id},
    )
    for record in records:
        conn.execute(
            text(
                """
                INSERT INTO public.person_training (
                    person_id,
                    training_kind,
                    title,
                    organization_name,
                    hours,
                    started_at,
                    completed_at,
                    verification_status,
                    lifecycle_status,
                    source_field
                )
                VALUES (
                    :person_id,
                    :training_kind,
                    :title,
                    :organization_name,
                    :hours,
                    :started_at,
                    :completed_at,
                    'verified',
                    'active',
                    :source_field
                )
                """
            ),
            {
                "person_id": person_id,
                "hours": record.get("hours"),
                **record,
            },
        )


def seed(*, dry_run: bool) -> list[dict]:
    if dry_run:
        return [{"dry_run": True, **spec} for spec in APPLICANTS]

    created: list[dict] = []
    with engine.begin() as conn:
        org_group_id, org_unit_id, position_id = _pick_placement(conn)

    for spec in APPLICANTS:
        with engine.begin() as conn:
            person_id = _upsert_person(
                conn,
                full_name=spec["full_name"],
                iin=spec["iin"],
                birth_date=spec["birth_date"],
            )

        _materialize_candidate(person_id)

        intended_position_id = position_id if spec.get("intended_complete", True) else None

        with engine.begin() as conn:
            save_intended_employment(
                conn,
                person_id=person_id,
                org_group_id=org_group_id,
                org_unit_id=org_unit_id,
                position_id=intended_position_id,
                employment_rate=float(spec["intended_rate"]),
            )
            _insert_education(conn, person_id=person_id, education=spec["education"])
            _replace_training(conn, person_id=person_id, records=list(spec.get("training") or []))

        created.append(
            {
                "person_id": person_id,
                "key": spec["key"],
                "full_name": spec["full_name"],
                "iin": spec["iin"],
                "org_group_id": org_group_id,
                "org_unit_id": org_unit_id,
                "position_id": intended_position_id,
                "employment_rate": spec["intended_rate"],
                "intended_complete": spec.get("intended_complete", True),
            }
        )
    return created


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed PPR applicant test records")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    rows = seed(dry_run=args.dry_run)
    print("Applicants:")
    for row in rows:
        print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
