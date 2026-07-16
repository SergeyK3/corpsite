"""PPR candidate roster, intended employment, and HR context sync."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.db.engine import engine as default_engine
from app.ppr.domain.models import (
    HR_RELATIONSHIP_CANDIDATE,
    HR_RELATIONSHIP_EMPLOYED,
    HR_RELATIONSHIP_CONTEXTS,
)
from app.ppr.infrastructure.ppr_repository import SqlAlchemyPprRepository


@dataclass(frozen=True, slots=True)
class IntendedEmploymentSnapshot:
    person_id: int
    org_group_id: int | None
    org_unit_id: int | None
    position_id: int | None
    employment_rate: float | None
    org_group_name: str | None = None
    org_unit_name: str | None = None
    position_name: str | None = None


def _table_exists(conn: Connection, table_name: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :table_name
            LIMIT 1
            """
        ),
        {"table_name": table_name},
    ).first()
    return row is not None


def _column_exists(conn: Connection, table_name: str, column_name: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table_name
              AND column_name = :column_name
            LIMIT 1
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    ).first()
    return row is not None


def _load_hr_relationship_context(conn: Connection, person_id: int) -> str | None:
    if not _table_exists(conn, "personnel_record_metadata"):
        return None
    row = conn.execute(
        text(
            """
            SELECT hr_relationship_context
            FROM public.personnel_record_metadata
            WHERE person_id = :person_id
            LIMIT 1
            """
        ),
        {"person_id": int(person_id)},
    ).mappings().first()
    if row is None:
        return None
    return str(row.get("hr_relationship_context") or "").strip() or None


def _require_candidate_context(conn: Connection, person_id: int) -> None:
    context = _load_hr_relationship_context(conn, person_id)
    if context != HR_RELATIONSHIP_CANDIDATE:
        raise ValueError(
            f"Person {person_id} hr_relationship_context={context!r} is not CANDIDATE."
        )


def load_intended_employment(conn: Connection, person_id: int) -> IntendedEmploymentSnapshot | None:
    if not _table_exists(conn, "personnel_record_metadata"):
        return None
    if not _column_exists(conn, "personnel_record_metadata", "intended_org_unit_id"):
        return None

    row = conn.execute(
        text(
            """
            SELECT
                prm.person_id,
                prm.intended_org_group_id,
                prm.intended_org_unit_id,
                prm.intended_position_id,
                prm.intended_employment_rate,
                dg.group_name AS org_group_name,
                ou.name AS org_unit_name,
                p.name AS position_name
            FROM public.personnel_record_metadata prm
            LEFT JOIN public.deps_group dg
              ON dg.group_id = prm.intended_org_group_id
            LEFT JOIN public.org_units ou
              ON ou.unit_id = prm.intended_org_unit_id
            LEFT JOIN public.positions p
              ON p.position_id = prm.intended_position_id
            WHERE prm.person_id = :person_id
            LIMIT 1
            """
        ),
        {"person_id": int(person_id)},
    ).mappings().first()
    if row is None:
        return None

    rate_raw = row.get("intended_employment_rate")
    rate: float | None = None
    if rate_raw is not None:
        rate = float(rate_raw)

    return IntendedEmploymentSnapshot(
        person_id=int(row["person_id"]),
        org_group_id=int(row["intended_org_group_id"]) if row.get("intended_org_group_id") is not None else None,
        org_unit_id=int(row["intended_org_unit_id"]) if row.get("intended_org_unit_id") is not None else None,
        position_id=int(row["intended_position_id"]) if row.get("intended_position_id") is not None else None,
        employment_rate=rate,
        org_group_name=str(row["org_group_name"]).strip() if row.get("org_group_name") else None,
        org_unit_name=str(row["org_unit_name"]).strip() if row.get("org_unit_name") else None,
        position_name=str(row["position_name"]).strip() if row.get("position_name") else None,
    )


def save_intended_employment(
    conn: Connection,
    *,
    person_id: int,
    org_group_id: int | None,
    org_unit_id: int | None,
    position_id: int | None,
    employment_rate: float | None,
) -> IntendedEmploymentSnapshot:
    repo = SqlAlchemyPprRepository(conn)
    if not repo.exists_envelope(person_id):
        raise LookupError(f"PPR envelope not found for person_id={person_id}")
    _require_candidate_context(conn, person_id)

    rate_value: Decimal | None = None
    if employment_rate is not None:
        rate_value = Decimal(str(employment_rate))

    conn.execute(
        text(
            """
            UPDATE public.personnel_record_metadata
            SET intended_org_group_id = :org_group_id,
                intended_org_unit_id = :org_unit_id,
                intended_position_id = :position_id,
                intended_employment_rate = :employment_rate,
                updated_at = now()
            WHERE person_id = :person_id
            """
        ),
        {
            "person_id": int(person_id),
            "org_group_id": org_group_id,
            "org_unit_id": org_unit_id,
            "position_id": position_id,
            "employment_rate": rate_value,
        },
    )
    loaded = load_intended_employment(conn, person_id)
    assert loaded is not None
    return loaded


def update_hr_relationship_context_tx(
    conn: Connection,
    *,
    person_id: int,
    hr_relationship_context: str,
) -> bool:
    if hr_relationship_context not in HR_RELATIONSHIP_CONTEXTS:
        raise ValueError(f"invalid hr_relationship_context: {hr_relationship_context!r}")

    repo = SqlAlchemyPprRepository(conn)
    envelope = repo.load_envelope(person_id)
    if envelope is None:
        return False
    if envelope.hr_relationship_context == hr_relationship_context:
        return True

    updated = envelope.with_updates(hr_relationship_context=hr_relationship_context)
    repo.update_envelope(updated, expected_version=envelope.version)
    return True


def sync_hr_context_after_hire(conn: Connection, *, employee_id: int) -> bool:
    row = conn.execute(
        text(
            """
            SELECT e.person_id, prm.hr_relationship_context
            FROM public.employees e
            LEFT JOIN public.personnel_record_metadata prm
              ON prm.person_id = e.person_id
            WHERE e.employee_id = :employee_id
            LIMIT 1
            """
        ),
        {"employee_id": int(employee_id)},
    ).mappings().first()
    if row is None or row.get("person_id") is None:
        return False
    if str(row.get("hr_relationship_context") or "") != HR_RELATIONSHIP_CANDIDATE:
        return False
    return update_hr_relationship_context_tx(
        conn,
        person_id=int(row["person_id"]),
        hr_relationship_context=HR_RELATIONSHIP_EMPLOYED,
    )


def list_ppr_applicants(
    conn: Connection,
    *,
    q: str | None = None,
    org_group_id: int | None = None,
    org_unit_id: int | None = None,
    position_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    if not _table_exists(conn, "personnel_record_metadata"):
        return [], 0

    where = [
        "prm.hr_relationship_context = :candidate_ctx",
        "p.person_status = 'active'",
        """
        NOT EXISTS (
            SELECT 1
            FROM public.employees e
            WHERE e.person_id = p.person_id
              AND COALESCE(e.is_active, TRUE) = TRUE
        )
        """,
    ]
    params: dict[str, Any] = {
        "candidate_ctx": HR_RELATIONSHIP_CANDIDATE,
        "limit": int(limit),
        "offset": int(offset),
    }

    if q:
        params["q"] = f"%{q.strip().lower()}%"
        where.append(
            "(LOWER(p.full_name) LIKE :q OR LOWER(COALESCE(p.iin, '')) LIKE :q "
            "OR CAST(p.person_id AS TEXT) LIKE :q)"
        )
    if org_group_id is not None:
        params["org_group_id"] = int(org_group_id)
        where.append("prm.intended_org_group_id = :org_group_id")
    if org_unit_id is not None:
        params["org_unit_id"] = int(org_unit_id)
        where.append("prm.intended_org_unit_id = :org_unit_id")
    if position_id is not None:
        params["position_id"] = int(position_id)
        where.append("prm.intended_position_id = :position_id")

    where_sql = " AND ".join(where)
    total = int(
        conn.execute(
            text(
                f"""
                SELECT COUNT(*) AS cnt
                FROM public.persons p
                JOIN public.personnel_record_metadata prm ON prm.person_id = p.person_id
                WHERE {where_sql}
                """
            ),
            params,
        ).mappings().first()["cnt"]
    )

    rows = conn.execute(
        text(
            f"""
            SELECT
                p.person_id,
                p.full_name,
                p.iin,
                p.birth_date,
                prm.hr_relationship_context,
                prm.intended_org_group_id,
                prm.intended_org_unit_id,
                prm.intended_position_id,
                prm.intended_employment_rate,
                dg.group_name AS org_group_name,
                ou.name AS org_unit_name,
                pos.name AS position_name
            FROM public.persons p
            JOIN public.personnel_record_metadata prm ON prm.person_id = p.person_id
            LEFT JOIN public.deps_group dg
              ON dg.group_id = prm.intended_org_group_id
            LEFT JOIN public.org_units ou
              ON ou.unit_id = prm.intended_org_unit_id
            LEFT JOIN public.positions pos
              ON pos.position_id = prm.intended_position_id
            WHERE {where_sql}
            ORDER BY LOWER(p.full_name) ASC, p.person_id ASC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()

    items: list[dict[str, Any]] = []
    for row in rows:
        rate_raw = row.get("intended_employment_rate")
        items.append(
            {
                "id": None,
                "person_id": int(row["person_id"]),
                "record_kind": "applicant",
                "fio": str(row["full_name"]).strip() if row.get("full_name") else None,
                "department": {"id": None, "name": None},
                "position": {
                    "id": row.get("intended_position_id"),
                    "name": row.get("position_name"),
                },
                "org_unit": {
                    "unit_id": row.get("intended_org_unit_id"),
                    "name": row.get("org_unit_name"),
                    "code": None,
                    "parent_unit_id": None,
                    "is_active": None,
                },
                "rate": float(rate_raw) if rate_raw is not None else None,
                "status": "applicant",
                "hr_relationship_context": row.get("hr_relationship_context"),
                "date_from": None,
                "date_to": None,
                "source": {"relation": "ppr_candidate"},
            }
        )
    return items, total


def load_hire_defaults(
    conn: Connection,
    *,
    person_id: int,
) -> dict[str, Any] | None:
    if _load_hr_relationship_context(conn, person_id) != HR_RELATIONSHIP_CANDIDATE:
        return None
    snapshot = load_intended_employment(conn, person_id)
    if snapshot is None:
        return None
    if (
        snapshot.org_unit_id is None
        and snapshot.position_id is None
        and snapshot.employment_rate is None
    ):
        return None
    return {
        "person_id": snapshot.person_id,
        "org_group_id": snapshot.org_group_id,
        "org_unit_id": snapshot.org_unit_id,
        "position_id": snapshot.position_id,
        "employment_rate": snapshot.employment_rate,
        "org_group_name": snapshot.org_group_name,
        "org_unit_name": snapshot.org_unit_name,
        "position_name": snapshot.position_name,
    }


def load_intended_org_unit_id(conn: Connection, person_id: int) -> int | None:
    row = conn.execute(
        text(
            """
            SELECT intended_org_unit_id
            FROM public.personnel_record_metadata
            WHERE person_id = :person_id
            LIMIT 1
            """
        ),
        {"person_id": int(person_id)},
    ).mappings().first()
    if row is None or row.get("intended_org_unit_id") is None:
        return None
    return int(row["intended_org_unit_id"])


def with_connection(engine: Engine | None = None):
    db = engine or default_engine
    return db.begin()
