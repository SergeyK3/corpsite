"""Read-only reconciliation of the position catalog and current assignments."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any, Iterable, Mapping

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _name_key(value: str) -> str:
    """Case and whitespace are insignificant; spelling is not guessed."""
    return " ".join(value.split()).casefold()


def _employees(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[int, dict[str, Any]] = {}
    for row in rows:
        employee_id = int(row["employee_id"])
        employee = by_id.setdefault(employee_id, {
            "employee_id": employee_id,
            "full_name": str(row["full_name"] or f"Сотрудник #{employee_id}"),
            "departments": set(),
        })
        unit_name = str(row["org_unit_name"] or "").strip()
        if unit_name:
            employee["departments"].add(unit_name)
    return [
        {**employee, "departments": sorted(employee["departments"], key=str.casefold)}
        for employee in sorted(by_id.values(), key=lambda e: (e["full_name"].casefold(), e["employee_id"]))
    ]


def assemble_position_assignment_reconciliation(
    positions: Iterable[Mapping[str, Any]],
    assignments: Iterable[Mapping[str, Any]],
    *,
    as_of: date,
    has_position_active_flag: bool = False,
) -> dict[str, Any]:
    """Every headline count is the length of its matching detail list."""
    catalog = [dict(row) for row in positions]
    linked = [dict(row) for row in assignments]
    by_position_id: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in linked:
        by_position_id[int(row["position_id"])].append(row)

    duplicate_ids: dict[str, list[int]] = defaultdict(list)
    for row in catalog:
        duplicate_ids[_name_key(str(row["name"]))].append(int(row["position_id"]))

    catalog_items: list[dict[str, Any]] = []
    for row in catalog:
        position_id = int(row["position_id"])
        employees = _employees(by_position_id[position_id])
        catalog_items.append({
            "position_id": position_id,
            "name": str(row["name"]),
            "type_code": row.get("type_code"),
            "type_name": row.get("type_name"),
            "is_active": row.get("is_active") if has_position_active_flag else None,
            "employee_count": len(employees),
            "employees": employees,
            "possible_duplicate_ids": sorted(
                other for other in duplicate_ids[_name_key(str(row["name"]))]
                if other != position_id
            ),
        })
    catalog_items.sort(key=lambda row: (_name_key(row["name"]), row["position_id"]))
    catalog_by_id = {row["position_id"]: row for row in catalog_items}

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in catalog_items:
        if item["employee_count"]:
            groups[_name_key(item["name"])].append(item)
    assignment_names: list[dict[str, Any]] = []
    for key, entries in groups.items():
        people_rows = [row for entry in entries for row in by_position_id[entry["position_id"]]]
        employees = _employees(people_rows)
        assignment_names.append({
            "name": entries[0]["name"],
            "normalized_name": key,
            "employee_count": len(employees),
            "employees": employees,
            "positions": [{
                "position_id": entry["position_id"],
                "name": entry["name"],
                "employee_count": entry["employee_count"],
                "employees": entry["employees"],
            } for entry in entries],
            "possible_duplicate_ids": [entry["position_id"] for entry in entries]
            if len(entries) > 1 else [],
        })
    assignment_names.sort(key=lambda row: (row["normalized_name"], row["name"]))

    missing_references = []
    for position_id in sorted(by_position_id):
        if position_id not in catalog_by_id:
            employees = _employees(by_position_id[position_id])
            missing_references.append({
                "position_id": position_id,
                "employee_count": len(employees),
                "employees": employees,
            })
    without_assignments = [item for item in catalog_items if item["employee_count"] == 0]
    active_items = [item for item in catalog_items if item["is_active"] is True]
    inactive_items = [item for item in catalog_items if item["is_active"] is False]

    return {
        "report_code": "position_assignment_reconciliation",
        "as_of": as_of.isoformat(),
        "assignment_name_source": "position_catalog_reference",
        "independent_assignment_name_available": False,
        "position_active_flag_available": has_position_active_flag,
        "metrics": {
            "assignment_names": len(assignment_names),
            "catalog_positions": len(catalog_items),
            "active_catalog_positions": len(active_items) if has_position_active_flag else None,
            "inactive_catalog_positions": len(inactive_items) if has_position_active_flag else None,
            "assignment_names_missing_in_catalog": None,
            "catalog_without_active_assignments": len(without_assignments),
        },
        "assignment_names": assignment_names,
        "catalog_positions": catalog_items,
        "assignment_names_missing_in_catalog": [],
        "catalog_without_active_assignments": without_assignments,
        "missing_position_references": missing_references,
    }


def build_position_assignment_reconciliation(engine: Engine) -> dict[str, Any]:
    """Use one database snapshot; assignment titles are not stored separately."""
    with engine.connect() as conn:
        conn.exec_driver_sql("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        as_of = conn.execute(text("SELECT CURRENT_DATE")).scalar_one()
        has_active_flag = bool(conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'positions'
                  AND column_name = 'is_active'
            )
        """)).scalar_one())
        active_column = "p.is_active" if has_active_flag else "NULL::boolean AS is_active"
        positions = conn.execute(text(f"""
            SELECT p.position_id, p.name, p.type_code, pt.name AS type_name,
                   {active_column}
            FROM public.positions p
            LEFT JOIN public.position_types pt ON pt.code = p.type_code
            ORDER BY p.position_id
        """)).mappings().all()
        assignments = conn.execute(text("""
            SELECT pa.position_id, e.employee_id,
                   COALESCE(NULLIF(BTRIM(person.full_name), ''),
                            NULLIF(BTRIM(e.full_name), '')) AS full_name,
                   ou.name AS org_unit_name
            FROM public.person_assignments pa
            JOIN public.employees e ON e.person_id = pa.person_id
            JOIN public.persons person ON person.person_id = pa.person_id
            LEFT JOIN public.org_units ou ON ou.unit_id = pa.org_unit_id
            WHERE pa.active_flag IS TRUE
              AND pa.lifecycle_status = 'active'
              AND pa.start_date <= :as_of
              AND (pa.end_date IS NULL OR pa.end_date >= :as_of)
              AND e.is_active IS TRUE
              AND e.operational_status = 'active'
              AND COALESCE(e.date_from, :as_of) <= :as_of
              AND (e.date_to IS NULL OR e.date_to >= :as_of)
              AND COALESCE(person.person_status, 'active') = 'active'
              AND person.merged_into_person_id IS NULL
        """), {"as_of": as_of}).mappings().all()
    return assemble_position_assignment_reconciliation(
        positions, assignments, as_of=as_of,
        has_position_active_flag=has_active_flag,
    )
