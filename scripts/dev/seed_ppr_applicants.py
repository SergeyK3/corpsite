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
from app.db.models.personnel_migration import EDUCATION_KIND_BASIC
from app.ppr.domain.models import HR_RELATIONSHIP_CANDIDATE
from app.services.ppr_candidate_service import save_intended_employment

APPLICANTS = [
    {
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
    },
    {
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
    },
]


def _pick_placement(conn) -> tuple[int | None, int, int]:
    unit = conn.execute(
        text(
            """
            SELECT unit_id
            FROM public.org_units
            WHERE COALESCE(is_active, TRUE) = TRUE
            ORDER BY unit_id ASC
            LIMIT 1
            """
        )
    ).mappings().first()
    if unit is None:
        raise RuntimeError("No org_units found — seed org structure first.")
    org_unit_id = int(unit["unit_id"])

    group = conn.execute(
        text(
            """
            SELECT group_id
            FROM public.deps_group
            ORDER BY group_id ASC
            LIMIT 1
            """
        )
    ).mappings().first()
    org_group_id = int(group["group_id"]) if group else None

    position = conn.execute(
        text("SELECT position_id FROM public.positions ORDER BY position_id ASC LIMIT 1")
    ).mappings().first()
    if position is None:
        raise RuntimeError("No positions found — seed positions first.")
    return org_group_id, org_unit_id, int(position["position_id"])


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
    existing = conn.execute(
        text(
            """
            SELECT 1
            FROM public.person_education
            WHERE person_id = :person_id
              AND institution_name = :institution_name
            LIMIT 1
            """
        ),
        {"person_id": person_id, "institution_name": education["institution_name"]},
    ).first()
    if existing:
        return

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

        with engine.begin() as conn:
            save_intended_employment(
                conn,
                person_id=person_id,
                org_group_id=org_group_id,
                org_unit_id=org_unit_id,
                position_id=position_id,
                employment_rate=float(spec["intended_rate"]),
            )
            _insert_education(conn, person_id=person_id, education=spec["education"])

        created.append(
            {
                "person_id": person_id,
                "full_name": spec["full_name"],
                "iin": spec["iin"],
                "org_unit_id": org_unit_id,
                "position_id": position_id,
                "employment_rate": spec["intended_rate"],
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
