"""Person-centric LK registry query (one row per person_id)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.personnel_applications.domain.status import terminal_statuses_for_partial_index

_TERMINAL_SQL = ", ".join(f"'{s}'" for s in terminal_statuses_for_partial_index())

_RECORD_KINDS = frozenset({"employee", "applicant"})
_EMPLOYEE_STATUS_VALUES = frozenset({"active", "inactive", "all"})


@dataclass(frozen=True, slots=True)
class PersonnelLkRegistryRow:
    person_id: int
    record_kind: str
    employee_id: int | None
    active_application_id: int | None
    fio: str | None
    iin: str | None
    rate: Decimal | float | None
    status: str
    application_status: str | None


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


def _normalize_record_kind(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = str(raw).strip().lower()
    if not value:
        return None
    return value


def _normalize_employee_status(raw: str | None) -> str:
    value = str(raw or "active").strip().lower()
    if value not in _EMPLOYEE_STATUS_VALUES:
        return "active"
    return value


def _employee_branch_sql() -> str:
    return """
        SELECT
            ae.person_id,
            'employee'::text AS record_kind,
            ae.employee_id,
            NULL::bigint AS active_application_id,
            COALESCE(NULLIF(TRIM(p.full_name), ''), NULLIF(TRIM(ae.employee_fio), '')) AS fio,
            NULLIF(TRIM(p.iin), '') AS iin,
            ae.employment_rate AS rate,
            ae.employee_status AS status,
            NULL::text AS application_status,
            ae.org_unit_id AS filter_org_unit_id,
            ae.position_id AS filter_position_id,
            ou.group_id AS filter_org_group_id
        FROM active_employee ae
        JOIN public.persons p ON p.person_id = ae.person_id
        LEFT JOIN public.org_units ou ON ou.unit_id = ae.org_unit_id
    """


def _applicant_branch_sql() -> str:
    return """
        SELECT
            ca.person_id,
            'applicant'::text AS record_kind,
            NULL::bigint AS employee_id,
            ca.application_id AS active_application_id,
            NULLIF(TRIM(p.full_name), '') AS fio,
            NULLIF(TRIM(p.iin), '') AS iin,
            ca.intended_employment_rate AS rate,
            'applicant'::text AS status,
            ca.application_status,
            ca.intended_org_unit_id AS filter_org_unit_id,
            ca.intended_position_id AS filter_position_id,
            ca.intended_org_group_id AS filter_org_group_id
        FROM chosen_application ca
        JOIN public.persons p ON p.person_id = ca.person_id
        WHERE p.person_status = 'active'
    """


def _build_registry_cte(*, include_employees: bool, include_applicants: bool) -> str:
    cte_parts: list[str] = []

    if include_applicants:
        cte_parts.append(
            f"""
            chosen_application AS (
                SELECT DISTINCT ON (pa.person_id)
                    pa.person_id,
                    pa.application_id,
                    pa.status AS application_status,
                    pa.intended_org_group_id,
                    pa.intended_org_unit_id,
                    pa.intended_position_id,
                    pa.intended_employment_rate
                FROM public.personnel_applications pa
                WHERE pa.status NOT IN ({_TERMINAL_SQL})
                  AND NOT EXISTS (
                      SELECT 1
                      FROM public.employees e_block
                      WHERE e_block.person_id = pa.person_id
                        AND COALESCE(e_block.is_active, TRUE) = TRUE
                  )
                ORDER BY pa.person_id, pa.application_received_at DESC, pa.application_id DESC
            )
            """
        )

    if include_employees:
        cte_parts.append(
            """
            active_employee AS (
                SELECT DISTINCT ON (e.person_id)
                    e.person_id,
                    e.employee_id,
                    e.full_name AS employee_fio,
                    e.employment_rate,
                    e.org_unit_id,
                    e.position_id,
                    CASE
                        WHEN COALESCE(e.is_active, TRUE) THEN 'active'
                        ELSE 'inactive'
                    END AS employee_status
                FROM public.employees e
                JOIN public.persons p ON p.person_id = e.person_id
                WHERE p.person_status = 'active'
                ORDER BY e.person_id, e.employee_id DESC
            )
            """
        )

    union_parts: list[str] = []
    if include_employees:
        union_parts.append(_employee_branch_sql())
    if include_applicants:
        union_parts.append(_applicant_branch_sql())

    cte_parts.append(f"registry AS ({' UNION ALL '.join(union_parts)})")
    return "WITH " + ",\n".join(cte_parts)


def list_personnel_lk_registry(
    conn: Connection,
    *,
    q: str | None = None,
    record_kind: str | None = None,
    status: str | None = "active",
    application_status: str | None = None,
    org_group_id: int | None = None,
    org_unit_id: int | None = None,
    position_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PersonnelLkRegistryRow], int]:
    """Return deduplicated person-centric registry rows with stable sort and pagination."""
    if not _table_exists(conn, "persons"):
        return [], 0

    normalized_kind = _normalize_record_kind(record_kind)
    if normalized_kind is not None and normalized_kind not in _RECORD_KINDS:
        return [], 0

    employee_status = _normalize_employee_status(status)
    include_employees = normalized_kind in (None, "employee")
    include_applicants = normalized_kind in (None, "applicant") and _table_exists(
        conn, "personnel_applications"
    )

    if not include_employees and not include_applicants:
        return [], 0

    params: dict[str, Any] = {
        "limit": max(1, min(int(limit), 200)),
        "offset": max(0, int(offset)),
    }

    where: list[str] = ["1=1"]

    if include_employees and not include_applicants:
        where.append("r.record_kind = 'employee'")
    elif include_applicants and not include_employees:
        where.append("r.record_kind = 'applicant'")

    if include_employees:
        if employee_status == "active":
            if include_applicants:
                where.append("(r.record_kind = 'applicant' OR r.status = 'active')")
            else:
                where.append("r.status = 'active'")
        elif employee_status == "inactive":
            where.append("r.record_kind = 'employee' AND r.status = 'inactive'")
        # status=all: no employee-status predicate

    if application_status and str(application_status).strip():
        params["application_status"] = str(application_status).strip()
        if include_employees and include_applicants:
            where.append(
                "(r.record_kind = 'employee' OR r.application_status = :application_status)"
            )
        else:
            where.append("r.application_status = :application_status")

    if org_group_id is not None:
        params["org_group_id"] = int(org_group_id)
        where.append("r.filter_org_group_id = :org_group_id")

    if org_unit_id is not None:
        params["org_unit_id"] = int(org_unit_id)
        where.append("r.filter_org_unit_id = :org_unit_id")

    if position_id is not None:
        params["position_id"] = int(position_id)
        where.append("r.filter_position_id = :position_id")

    if q and str(q).strip():
        params["q"] = f"%{str(q).strip().lower()}%"
        where.append(
            "("
            "LOWER(COALESCE(r.fio, '')) LIKE :q "
            "OR LOWER(COALESCE(r.iin, '')) LIKE :q "
            "OR (r.record_kind = 'applicant' AND CAST(r.active_application_id AS TEXT) LIKE :q)"
            ")"
        )

    where_sql = " AND ".join(where)
    registry_cte = _build_registry_cte(
        include_employees=include_employees,
        include_applicants=include_applicants,
    )

    count_sql = f"""
        {registry_cte}
        SELECT COUNT(*) AS cnt
        FROM registry r
        WHERE {where_sql}
    """
    total = int(conn.execute(text(count_sql), params).scalar_one())

    list_sql = f"""
        {registry_cte}
        SELECT
            r.person_id,
            r.record_kind,
            r.employee_id,
            r.active_application_id,
            r.fio,
            r.iin,
            r.rate,
            r.status,
            r.application_status
        FROM registry r
        WHERE {where_sql}
        ORDER BY LOWER(COALESCE(r.fio, '')) ASC, r.person_id ASC
        LIMIT :limit OFFSET :offset
    """
    rows = conn.execute(text(list_sql), params).mappings().all()

    items = [
        PersonnelLkRegistryRow(
            person_id=int(row["person_id"]),
            record_kind=str(row["record_kind"]),
            employee_id=int(row["employee_id"]) if row.get("employee_id") is not None else None,
            active_application_id=(
                int(row["active_application_id"])
                if row.get("active_application_id") is not None
                else None
            ),
            fio=str(row["fio"]).strip() if row.get("fio") else None,
            iin=str(row["iin"]).strip() if row.get("iin") else None,
            rate=row.get("rate"),
            status=str(row["status"]),
            application_status=(
                str(row["application_status"]) if row.get("application_status") is not None else None
            ),
        )
        for row in rows
    ]
    return items, total
