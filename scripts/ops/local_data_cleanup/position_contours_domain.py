#!/usr/bin/env python3
"""Position-contours cleanup domain: plan / execute / verify for blocked test positions."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from personnel_cleanup_fk_graph import (
    SafetyAbort,
    fetch_fk_catalog,
    load_allowlist,
    save_report,
    table_exists,
    table_pk_column,
)
from positions_domain import (
    HR_ETALON_POSITION_NAMES,
    PROTECTED_POSITION_IDS,
    _column_exists,
    _normalize_signature_value,
    position_dependency_counts,
)

# Seed from prior blocked-positions audit — not used for deletion selection.
SEED_BLOCKED_POSITION_IDS = frozenset({298, 299, 325, 326})

PROTECTED_ORG_UNIT_IDS = frozenset({41})
PROTECTED_EMPLOYEE_IDS = frozenset({138})

CLASSIFICATION_FULLY_TEST = "FULLY_TEST_DELETABLE"
CLASSIFICATION_TEST_SHARED = "TEST_BUT_SHARED"
CLASSIFICATION_HISTORICAL = "HISTORICAL_REFERENCE_ONLY"
CLASSIFICATION_REAL = "REAL_OR_AMBIGUOUS"

SEMANTIC_REF_COLUMNS = frozenset(
    {
        "employee_id",
        "person_id",
        "order_id",
        "position_id",
        "from_position_id",
        "to_position_id",
        "from_org_unit_id",
        "to_org_unit_id",
        "org_unit_id",
        "unit_id",
        "order_item_id",
        "item_id",
        "catalog_position_id",
        "target_position_id",
        "signed_by_employee_id",
    }
)

JSON_LIKE_COLUMNS = frozenset({"payload", "metadata", "metadata_json", "changes", "field_diffs"})

ORDER_CHILD_TABLES: list[tuple[str, str, str]] = [
    ("personnel_order_item_editorial_blocks", "order_item_id", "item_id"),
    ("personnel_order_item_bases", "order_item_id", "item_id"),
    ("personnel_order_items", "order_id", "order_id"),
    ("personnel_order_localized_texts", "order_id", "order_id"),
    ("personnel_order_attachments", "order_id", "order_id"),
    ("personnel_order_prints", "order_id", "order_id"),
    ("personnel_order_editorial_blocks", "order_id", "order_id"),
    ("personnel_order_lifecycle_audit", "order_id", "order_id"),
    ("personnel_orders", "order_id", "order_id"),
]

TABLE_PK_MAP: dict[str, str] = {
    "personnel_order_item_editorial_blocks": "item_editorial_block_id",
    "personnel_order_item_bases": "item_basis_id",
    "personnel_order_items": "item_id",
    "personnel_order_lifecycle_audit": "id",
    "personnel_order_localized_texts": "localized_text_id",
    "personnel_order_attachments": "attachment_id",
    "personnel_order_prints": "print_id",
    "personnel_order_editorial_blocks": "editorial_block_id",
    "personnel_orders": "order_id",
    "employee_events": "event_id",
    "employees": "employee_id",
    "org_units": "unit_id",
    "positions": "position_id",
}

DELETE_PHASE_ORDER: list[tuple[str, str]] = [
    ("personnel_order_item_editorial_blocks", "id"),
    ("personnel_order_item_bases", "id"),
    ("personnel_order_lifecycle_audit", "id"),
    ("personnel_order_localized_texts", "id"),
    ("personnel_order_attachments", "id"),
    ("personnel_order_prints", "id"),
    ("personnel_order_editorial_blocks", "id"),
    ("personnel_order_items", "item_id"),
    ("employee_events", "event_id"),
    ("employee_assignment_links", "link_id"),
    ("person_assignments", "assignment_id"),
    ("employee_identities", "identity_id"),
    ("enrollment_history", "id"),
    ("employee_documents", "document_id"),
    ("hr_import_normalized_records", "normalized_record_id"),
    ("hr_change_events", "event_id"),
    ("identity_reconciliation_items", "item_id"),
    ("employees", "employee_id"),
    ("personnel_orders", "order_id"),
    ("org_unit_allowed_positions", "org_unit_allowed_position_id"),
    ("org_unit_aliases", "alias_id"),
    ("org_units", "unit_id"),
    ("position_aliases", "alias_id"),
    ("positions", "position_id"),
]


@dataclass
class ContourObject:
    table: str
    pk_column: str
    obj_id: int
    label: str
    signature: dict[str, Any]
    contour: str
    classification: str
    reasons: list[str] = field(default_factory=list)
    parent_refs: list[str] = field(default_factory=list)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch_row(conn: Connection, table: str, pk_column: str, obj_id: int) -> dict[str, Any] | None:
    if not table_exists(conn, table):
        return None
    row = conn.execute(
        text(f"SELECT * FROM public.{table} WHERE {pk_column} = :id"),
        {"id": obj_id},
    ).mappings().first()
    return dict(row) if row else None


def _list_public_tables(conn: Connection) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        )
    ).fetchall()
    return [str(r[0]) for r in rows]


def _list_matviews(conn: Connection) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT matviewname FROM pg_matviews WHERE schemaname = 'public' ORDER BY matviewname
            """
        )
    ).fetchall()
    return [str(r[0]) for r in rows]


def _table_columns(conn: Connection, table: str) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :t
            ORDER BY ordinal_position
            """
        ),
        {"t": table},
    ).fetchall()
    return [str(r[0]) for r in rows]


def discover_seed_positions(conn: Connection) -> list[dict[str, Any]]:
    out = []
    for pid in sorted(SEED_BLOCKED_POSITION_IDS):
        row = _fetch_row(conn, "positions", "position_id", pid)
        if row:
            out.append(row)
    return out


def discover_employees_for_positions(conn: Connection, position_ids: list[int]) -> list[dict[str, Any]]:
    if not position_ids:
        return []
    return [
        dict(r)
        for r in conn.execute(
            text(
                """
                SELECT e.*, p.name AS position_name, ou.code AS org_unit_code, ou.name AS org_unit_name
                FROM public.employees e
                JOIN public.positions p ON p.position_id = e.position_id
                LEFT JOIN public.org_units ou ON ou.unit_id = e.org_unit_id
                WHERE e.position_id = ANY(:ids)
                ORDER BY e.employee_id
                """
            ),
            {"ids": position_ids},
        ).mappings().all()
    ]


def discover_events_for_positions(
    conn: Connection, position_ids: list[int], employee_ids: list[int]
) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in conn.execute(
            text(
                """
                SELECT ee.*
                FROM public.employee_events ee
                WHERE ee.from_position_id = ANY(:pids) OR ee.to_position_id = ANY(:pids)
                   OR ee.employee_id = ANY(:eids)
                ORDER BY ee.event_id
                """
            ),
            {"pids": position_ids, "eids": employee_ids or [-1]},
        ).mappings().all()
    ]


def discover_orders_for_events(conn: Connection, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order_ids = sorted({int(e["order_id"]) for e in events if e.get("order_id")})
    return discover_orders_by_ids(conn, order_ids)


def discover_orders_by_ids(conn: Connection, order_ids: list[int]) -> list[dict[str, Any]]:
    if not order_ids:
        return []
    return [
        dict(r)
        for r in conn.execute(
            text("SELECT * FROM public.personnel_orders WHERE order_id = ANY(:ids) ORDER BY order_id"),
            {"ids": order_ids},
        ).mappings().all()
    ]


def discover_order_items(
    conn: Connection, order_ids: list[int], employee_ids: list[int], position_ids: list[int]
) -> list[dict[str, Any]]:
    clauses = []
    params: dict[str, Any] = {}
    if order_ids:
        clauses.append("poi.order_id = ANY(:order_ids)")
        params["order_ids"] = order_ids
    if employee_ids:
        clauses.append("poi.employee_id = ANY(:employee_ids)")
        params["employee_ids"] = employee_ids
    if position_ids:
        clauses.append(
            "(poi.payload::text LIKE ANY(:plikes) OR poi.payload::text LIKE ANY(:tplikes) OR poi.payload::text LIKE ANY(:fplikes))"
        )
        params["plikes"] = [f'%"position_id": {pid}%' for pid in position_ids]
        params["tplikes"] = [f'%"to_position_id": {pid}%' for pid in position_ids]
        params["fplikes"] = [f'%"from_position_id": {pid}%' for pid in position_ids]
    if not clauses:
        return []
    where = " OR ".join(f"({c})" for c in clauses)
    return [
        dict(r)
        for r in conn.execute(
            text(f"SELECT poi.* FROM public.personnel_order_items poi WHERE {where} ORDER BY poi.item_id"),
            params,
        ).mappings().all()
    ]


def discover_order_children(conn: Connection, order_ids: list[int], item_ids: list[int]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    specs = [
        ("personnel_order_localized_texts", "order_id", order_ids),
        ("personnel_order_attachments", "order_id", order_ids),
        ("personnel_order_prints", "order_id", order_ids),
        ("personnel_order_editorial_blocks", "order_id", order_ids),
        ("personnel_order_lifecycle_audit", "order_id", order_ids),
        ("personnel_order_item_editorial_blocks", "order_item_id", item_ids),
        ("personnel_order_item_bases", "order_item_id", item_ids),
    ]
    for table, col, ids in specs:
        if not ids or not table_exists(conn, table):
            out[table] = []
            continue
        pk = TABLE_PK_MAP.get(table) or table_pk_column(conn, table) or "id"
        rows = conn.execute(
            text(f"SELECT * FROM public.{table} WHERE {col} = ANY(:ids) ORDER BY {pk}"),
            {"ids": ids},
        ).mappings().all()
        out[table] = [dict(r) for r in rows]
    return out


def _child_ids(order_children: dict[str, list[dict]], table: str) -> list[int]:
    rows = order_children.get(table) or []
    if not rows:
        return []
    pk = TABLE_PK_MAP.get(table) or table_pk_column_from_inventory(table, rows)
    return [int(r[pk]) for r in rows]


def discover_users_for_org_units(conn: Connection, unit_ids: list[int]) -> list[dict[str, Any]]:
    if not unit_ids or not table_exists(conn, "users"):
        return []
    return [
        dict(r)
        for r in conn.execute(
            text(
                "SELECT user_id, full_name, google_login, unit_id, employee_id, role_id "
                "FROM public.users WHERE unit_id = ANY(:ids) ORDER BY user_id"
            ),
            {"ids": unit_ids},
        ).mappings().all()
    ]


def discover_pytest_org_units(conn: Connection, employee_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unit_ids = sorted({int(r["org_unit_id"]) for r in employee_rows if r.get("org_unit_id")})
    if not unit_ids:
        return []
    rows = conn.execute(
        text("SELECT * FROM public.org_units WHERE unit_id = ANY(:ids) ORDER BY unit_id"),
        {"ids": unit_ids},
    ).mappings().all()
    result = []
    for row in rows:
        d = dict(row)
        other_emp = int(
            conn.execute(
                text(
                    "SELECT COUNT(*) FROM public.employees e WHERE e.org_unit_id = :uid "
                    "AND e.employee_id != ALL(:eids)"
                ),
                {"uid": int(d["unit_id"]), "eids": [int(r["employee_id"]) for r in employee_rows] or [-1]},
            ).scalar()
            or 0
        )
        d["other_employee_count"] = other_emp
        result.append(d)
    return result


def scan_semantic_references(
    conn: Connection,
    *,
    position_ids: list[int],
    employee_ids: list[int],
    order_ids: list[int],
    org_unit_ids: list[int],
) -> dict[str, Any]:
    """Scan all public tables/views for column and JSON semantic references."""
    hits: list[dict[str, Any]] = []
    tables = _list_public_tables(conn)
    matviews = _list_matviews(conn)

    id_sets = {
        "position_id": position_ids,
        "from_position_id": position_ids,
        "to_position_id": position_ids,
        "catalog_position_id": position_ids,
        "target_position_id": position_ids,
        "employee_id": employee_ids,
        "signed_by_employee_id": employee_ids,
        "order_id": order_ids,
        "org_unit_id": org_unit_ids,
        "unit_id": org_unit_ids,
        "from_org_unit_id": org_unit_ids,
        "to_org_unit_id": org_unit_ids,
    }

    for table in tables:
        cols = _table_columns(conn, table)
        pk = table_pk_column(conn, table) or cols[0] if cols else "id"
        for col in cols:
            if col not in id_sets or not id_sets[col]:
                continue
            ids = id_sets[col]
            try:
                rows = conn.execute(
                    text(
                        f"SELECT {pk} AS ref_id, {col} AS matched_value "
                        f"FROM public.{table} WHERE {col} = ANY(:ids) ORDER BY {pk}"
                    ),
                    {"ids": ids},
                ).mappings().all()
                for row in rows:
                    hits.append(
                        {
                            "table": table,
                            "pk_column": pk,
                            "ref_id": int(row["ref_id"]),
                            "column": col,
                            "matched_value": int(row["matched_value"]),
                            "ref_type": "fk_column",
                        }
                    )
            except Exception as exc:
                hits.append({"table": table, "column": col, "ref_type": "scan_error", "error": str(exc)[:200]})

        json_cols = [c for c in cols if c in JSON_LIKE_COLUMNS]
        for jcol in json_cols:
            for pid in position_ids:
                for needle in (f'"position_id": {pid}', f'"to_position_id": {pid}', f'"from_position_id": {pid}'):
                    try:
                        rows = conn.execute(
                            text(
                                f"SELECT {pk} AS ref_id FROM public.{table} "
                                f"WHERE {jcol}::text LIKE :pat ORDER BY {pk}"
                            ),
                            {"pat": f"%{needle}%"},
                        ).mappings().all()
                        for row in rows:
                            hits.append(
                                {
                                    "table": table,
                                    "pk_column": pk,
                                    "ref_id": int(row["ref_id"]),
                                    "column": jcol,
                                    "matched_value": pid,
                                    "ref_type": "json_semantic",
                                    "needle": needle,
                                }
                            )
                    except Exception:
                        pass

    mv_hits = []
    for mv in matviews:
        mv_hits.append({"matview": mv, "note": "matview present — refresh may be needed post-cleanup"})

    return {
        "hits": hits,
        "hit_count": len([h for h in hits if h.get("ref_type") in {"fk_column", "json_semantic"}]),
        "matviews": mv_hits,
        "scanned_tables": len(tables),
    }


def classify_position_325(
    *,
    position_row: dict[str, Any],
    employees: list[dict],
    events: list[dict],
    order_items: list[dict],
    semantic_hits: list[dict],
) -> dict[str, Any]:
    """Resolve 325 ambiguity: historical-only anchor within fully-test contour."""
    current_employees = [e for e in employees if int(e["position_id"]) == 325]
    position_events = [
        e for e in events if int(e.get("from_position_id") or 0) == 325 or int(e.get("to_position_id") or 0) == 325
    ]
    payload_refs = [h for h in semantic_hits if h.get("matched_value") == 325 and "personnel_order" in h.get("table", "")]
    event_employee_ids = {int(e["employee_id"]) for e in position_events}
    all_test_employees = all(
        "pytest" in str(e.get("full_name", "")).lower() or "pilot" in str(e.get("full_name", "")).lower()
        for e in employees
        if int(e["employee_id"]) in event_employee_ids
    ) if event_employee_ids else True

    if current_employees:
        classification = CLASSIFICATION_TEST_SHARED
        resolution = "has current employee — not historical-only"
    elif not position_events:
        classification = CLASSIFICATION_REAL
        resolution = "no events and no employees — ambiguous orphan"
    elif payload_refs:
        classification = CLASSIFICATION_TEST_SHARED
        resolution = "referenced in personnel order payload"
    elif all_test_employees and not payload_refs:
        classification = CLASSIFICATION_FULLY_TEST
        resolution = (
            "HISTORICAL_REFERENCE_ONLY as standalone role, but FULLY_TEST_DELETABLE as part of "
            "pytest_correct contour: zero current employees, events 540/541 belong exclusively to "
            "test employee 153, no order items; delete events before position 325"
        )
    else:
        classification = CLASSIFICATION_REAL
        resolution = "events linked to non-test employees"

    return {
        "position_id": 325,
        "standalone_role": CLASSIFICATION_HISTORICAL if not current_employees and position_events else CLASSIFICATION_REAL,
        "contour_role": classification,
        "resolution": resolution,
        "current_employee_count": len(current_employees),
        "event_count": len(position_events),
        "payload_ref_count": len(payload_refs),
        "delete_after": ["employee_events:540", "employee_events:541", "employee_events:542"],
        "delete_with_contour": True,
    }


def build_contour_inventory(conn: Connection) -> dict[str, Any]:
    position_ids = sorted(SEED_BLOCKED_POSITION_IDS)
    positions = discover_seed_positions(conn)
    employees = discover_employees_for_positions(conn, position_ids)
    employee_ids = [int(e["employee_id"]) for e in employees]
    events = discover_events_for_positions(conn, position_ids, employee_ids)
    orders = discover_orders_for_events(conn, events)
    order_ids = [int(o["order_id"]) for o in orders]
    items = discover_order_items(conn, order_ids, employee_ids, position_ids)
    item_ids = [int(i["item_id"]) for i in items]
    order_ids = sorted(set(order_ids) | {int(i["order_id"]) for i in items})
    orders = discover_orders_by_ids(conn, order_ids) if order_ids else []
    order_children = discover_order_children(conn, order_ids, item_ids)
    org_units = discover_pytest_org_units(conn, employees)

    # Extend employees from events (employee 153 may not be on 325/326 only through position filter)
    extra_emp_ids = sorted({int(e["employee_id"]) for e in events} - set(employee_ids))
    if extra_emp_ids:
        extra_rows = [
            dict(r)
            for r in conn.execute(
                text(
                    """
                    SELECT e.*, p.name AS position_name, ou.code AS org_unit_code
                    FROM public.employees e
                    JOIN public.positions p ON p.position_id = e.position_id
                    LEFT JOIN public.org_units ou ON ou.unit_id = e.org_unit_id
                    WHERE e.employee_id = ANY(:ids)
                    """
                ),
                {"ids": extra_emp_ids},
            ).mappings().all()
        ]
        employees = employees + extra_rows
        employee_ids = [int(e["employee_id"]) for e in employees]
        org_units = discover_pytest_org_units(conn, employees)

    event_org_ids: set[int] = set()
    for ev in events:
        for key in ("from_org_unit_id", "to_org_unit_id"):
            if ev.get(key):
                event_org_ids.add(int(ev[key]))
        meta = ev.get("metadata") or {}
        ou_change = (meta.get("changes") or {}).get("org_unit_id") or {}
        for side in ("from", "to"):
            val = ou_change.get(side)
            if val is not None:
                event_org_ids.add(int(val))
    known_org_ids = {int(u["unit_id"]) for u in org_units}
    extra_org_ids = sorted(event_org_ids - known_org_ids - PROTECTED_ORG_UNIT_IDS)
    if extra_org_ids:
        for d in conn.execute(
            text("SELECT * FROM public.org_units WHERE unit_id = ANY(:ids) ORDER BY unit_id"),
            {"ids": extra_org_ids},
        ).mappings().all():
            row = dict(d)
            row["other_employee_count"] = int(
                conn.execute(
                    text("SELECT COUNT(*) FROM public.employees WHERE org_unit_id = :uid"),
                    {"uid": int(row["unit_id"])},
                ).scalar()
                or 0
            )
            org_units.append(row)

    org_unit_ids = [int(u["unit_id"]) for u in org_units]
    semantic = scan_semantic_references(
        conn,
        position_ids=position_ids,
        employee_ids=employee_ids,
        order_ids=order_ids,
        org_unit_ids=org_unit_ids,
    )

    pos325 = next((p for p in positions if int(p["position_id"]) == 325), {})
    classification_325 = classify_position_325(
        position_row=pos325,
        employees=employees,
        events=events,
        order_items=items,
        semantic_hits=semantic["hits"],
    )

    pilot_contour = {
        "label": "pilot-po-20260708",
        "classification": CLASSIFICATION_FULLY_TEST,
        "shared_warnings": [
            "org_unit_id=41 (ORG_MAIN) is REAL — do not delete; employee 138 remains"
        ],
        "positions": [298, 299],
        "employees": [142, 143, 144, 145],
        "employee_events": [331, 332],
        "personnel_orders": order_ids,
        "personnel_order_items": item_ids,
        "personnel_order_lifecycle_audit": _child_ids(order_children, "personnel_order_lifecycle_audit"),
        "personnel_order_localized_texts": _child_ids(order_children, "personnel_order_localized_texts"),
        "personnel_order_attachments": _child_ids(order_children, "personnel_order_attachments"),
        "personnel_order_prints": _child_ids(order_children, "personnel_order_prints"),
        "personnel_order_editorial_blocks": _child_ids(order_children, "personnel_order_editorial_blocks"),
        "personnel_order_item_editorial_blocks": _child_ids(
            order_children, "personnel_order_item_editorial_blocks"
        ),
        "personnel_order_item_bases": _child_ids(order_children, "personnel_order_item_bases"),
        "protected_parent_org_units": [41],
        "protected_employees": [138],
    }

    pytest_org_deletable = []
    pytest_org_blocked: list[dict[str, Any]] = []
    for u in org_units:
        uid = int(u["unit_id"])
        if uid in PROTECTED_ORG_UNIT_IDS:
            continue
        if int(u.get("other_employee_count", 0)) > 0:
            pytest_org_blocked.append({"unit_id": uid, "reason": "other employees in unit"})
            continue
        unit_users = discover_users_for_org_units(conn, [uid])
        if unit_users:
            pytest_org_blocked.append(
                {
                    "unit_id": uid,
                    "reason": "users still reference org unit",
                    "users": unit_users,
                    "classification": CLASSIFICATION_TEST_SHARED,
                }
            )
            continue
        pytest_org_deletable.append(uid)
    pytest_contour = {
        "label": "pytest-correct-wp002",
        "classification": CLASSIFICATION_FULLY_TEST,
        "positions": [325, 326],
        "position_325_resolution": classification_325,
        "employees": [153],
        "employee_events": [540, 541, 542],
        "personnel_orders": [],
        "org_units_candidate": pytest_org_deletable,
        "org_units_blocked": pytest_org_blocked,
    }

    return {
        "seed_position_ids": position_ids,
        "positions": positions,
        "employees": employees,
        "employee_events": events,
        "personnel_orders": orders,
        "personnel_order_items": items,
        "order_children": order_children,
        "org_units": org_units,
        "semantic_scan": semantic,
        "contours": [pilot_contour, pytest_contour],
        "protected": {
            "position_ids": sorted(PROTECTED_POSITION_IDS),
            "org_unit_ids": sorted(PROTECTED_ORG_UNIT_IDS),
            "employee_ids": sorted(PROTECTED_EMPLOYEE_IDS),
            "hr_etalon_position_names": HR_ETALON_POSITION_NAMES,
        },
    }


def _signature_from_row(row: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    return {f: row.get(f) for f in fields if f in row}


def build_allowlist_draft(inventory: dict[str, Any]) -> dict[str, Any]:
    """Build allowlist draft from plan inventory for external review."""
    allowlist: dict[str, Any] = {
        "version": 1,
        "description": "Position-contours cleanup allowlist — generated by plan mode",
        "contours": [],
        "protected": {
            "persons": [],
            "employees": [{"id": 138, "label": "real-employee-makibaeva", "reason": "real employee in ORG_MAIN"}],
            "users": [],
            "units": [{"id": 41, "label": "ORG_MAIN", "reason": "production org unit"}],
            "positions": [{"id": 1, "label": "archivist", "reason": "protected"}],
            "roles": [],
        },
        "persons": [],
        "employees": [],
        "users": [],
        "units": [],
        "assignments": [],
        "positions": [],
        "employee_events": [],
        "personnel_orders": [],
        "personnel_order_items": [],
        "personnel_order_lifecycle_audit": [],
        "personnel_order_localized_texts": [],
        "personnel_order_attachments": [],
        "personnel_order_prints": [],
        "personnel_order_editorial_blocks": [],
        "personnel_order_item_editorial_blocks": [],
        "personnel_order_item_bases": [],
        "identities": [],
        "batches": [],
        "snapshots": [],
        "audit": [],
        "roles": [],
        "reconciliation": {"items": [], "runs": []},
    }

    row_index = {
        "employees": {int(r["employee_id"]): r for r in inventory["employees"]},
        "positions": {int(r["position_id"]): r for r in inventory["positions"]},
        "employee_events": {int(r["event_id"]): r for r in inventory["employee_events"]},
        "personnel_orders": {int(r["order_id"]): r for r in inventory["personnel_orders"]},
        "personnel_order_items": {int(r["item_id"]): r for r in inventory["personnel_order_items"]},
    }
    for table, rows in inventory.get("order_children", {}).items():
        pk = table_pk_column_from_inventory(table, rows)
        row_index[table] = {int(r[pk]): r for r in rows}

    for contour in inventory["contours"]:
        allowlist["contours"].append({"label": contour["label"], "classification": contour["classification"]})

        for pid in contour.get("positions", []):
            row = row_index["positions"].get(pid, {})
            allowlist["positions"].append(
                {
                    "id": pid,
                    "label": f"pos-{pid}",
                    "reason": f"{contour['label']} contour",
                    "parent_contour": contour["label"],
                    "expected_signature": _signature_from_row(row, ["name", "category"]),
                }
            )
        for eid in contour.get("employees", []):
            row = row_index["employees"].get(eid, {})
            allowlist["employees"].append(
                {
                    "id": eid,
                    "label": f"emp-{eid}",
                    "reason": f"{contour['label']} contour",
                    "parent_contour": contour["label"],
                    "expected_signature": _signature_from_row(row, ["full_name", "org_unit_id", "position_id"]),
                }
            )
        for evid in contour.get("employee_events", []):
            row = row_index["employee_events"].get(evid, {})
            allowlist["employee_events"].append(
                {
                    "id": evid,
                    "label": f"evt-{evid}",
                    "reason": f"{contour['label']} contour",
                    "parent_contour": contour["label"],
                    "expected_signature": _signature_from_row(
                        row, ["employee_id", "event_type", "from_position_id", "to_position_id"]
                    ),
                }
            )
        for oid in contour.get("personnel_orders", []):
            row = row_index["personnel_orders"].get(oid, {})
            allowlist["personnel_orders"].append(
                {
                    "id": oid,
                    "label": f"ord-{oid}",
                    "reason": f"{contour['label']} contour",
                    "parent_contour": contour["label"],
                    "expected_signature": _signature_from_row(row, ["order_number", "status", "order_type_code"]),
                }
            )
        for iid in contour.get("personnel_order_items", []):
            row = row_index["personnel_order_items"].get(iid, {})
            allowlist["personnel_order_items"].append(
                {
                    "id": iid,
                    "label": f"item-{iid}",
                    "reason": f"{contour['label']} contour",
                    "parent_contour": contour["label"],
                    "expected_signature": _signature_from_row(row, ["order_id", "item_type_code", "employee_id"]),
                }
            )
        for aid in contour.get("personnel_order_lifecycle_audit", []):
            rows = inventory["order_children"].get("personnel_order_lifecycle_audit", [])
            row = next((r for r in rows if int(r["id"]) == aid), {})
            allowlist["personnel_order_lifecycle_audit"].append(
                {
                    "id": aid,
                    "label": f"audit-{aid}",
                    "reason": f"{contour['label']} contour",
                    "parent_contour": contour["label"],
                    "expected_signature": _signature_from_row(row, ["order_id", "action", "new_status"]),
                }
            )
        child_sections = [
            ("personnel_order_localized_texts", ["order_id", "locale"]),
            ("personnel_order_attachments", ["order_id"]),
            ("personnel_order_prints", ["order_id"]),
            ("personnel_order_editorial_blocks", ["order_id", "block_type"]),
            ("personnel_order_item_editorial_blocks", ["order_item_id", "block_type"]),
            ("personnel_order_item_bases", ["order_item_id"]),
        ]
        for section, sig_fields in child_sections:
            for cid in contour.get(section, []):
                rows = inventory["order_children"].get(section, [])
                pk = TABLE_PK_MAP.get(section, "id")
                row = next((r for r in rows if int(r[pk]) == cid), {})
                allowlist[section].append(
                    {
                        "id": cid,
                        "label": f"{section}-{cid}",
                        "reason": f"{contour['label']} contour",
                        "parent_contour": contour["label"],
                        "expected_signature": _signature_from_row(row, sig_fields),
                    }
                )
        for uid in contour.get("org_units_candidate", []):
            row = next((u for u in inventory["org_units"] if int(u["unit_id"]) == uid), {})
            allowlist["units"].append(
                {
                    "id": uid,
                    "label": f"unit-{uid}",
                    "reason": f"{contour['label']} exclusive pytest org unit",
                    "parent_contour": contour["label"],
                    "expected_signature": _signature_from_row(row, ["code", "name"]),
                }
            )

    return allowlist


def table_pk_column_from_inventory(table: str, rows: list[dict]) -> str:
    if table in TABLE_PK_MAP:
        return TABLE_PK_MAP[table]
    if not rows:
        return "id"
    if table == "personnel_order_items":
        return "item_id"
    if table == "personnel_orders":
        return "order_id"
    if "item_id" in rows[0]:
        return "item_id"
    if "id" in rows[0]:
        return "id"
    return list(rows[0].keys())[0]


def load_contour_allowlist(path: Path) -> dict[str, Any]:
    from personnel_cleanup_fk_graph import assert_external_path

    external = assert_external_path(path, label="Allowlist")
    if not external.is_file():
        raise SafetyAbort(f"Allowlist not found: {external}")
    with external.open(encoding="utf-8") as fh:
        data = json.load(fh)
    required = ("positions", "employees", "protected")
    for key in required:
        if key not in data:
            raise SafetyAbort(f"Contour allowlist missing section: {key}")
    return data


def build_delete_steps_from_allowlist(allowlist: dict[str, Any]) -> list[dict[str, Any]]:
    phase_specs: list[tuple[str, str, str]] = [
        ("personnel_order_item_editorial_blocks", "personnel_order_item_editorial_blocks", "item_editorial_block_id"),
        ("personnel_order_item_bases", "personnel_order_item_bases", "item_basis_id"),
        ("personnel_order_lifecycle_audit", "personnel_order_lifecycle_audit", "id"),
        ("personnel_order_localized_texts", "personnel_order_localized_texts", "localized_text_id"),
        ("personnel_order_attachments", "personnel_order_attachments", "attachment_id"),
        ("personnel_order_prints", "personnel_order_prints", "print_id"),
        ("personnel_order_editorial_blocks", "personnel_order_editorial_blocks", "editorial_block_id"),
        ("employee_events", "employee_events", "event_id"),
        ("personnel_order_items", "personnel_order_items", "item_id"),
        ("employees", "employees", "employee_id"),
        ("personnel_orders", "personnel_orders", "order_id"),
        ("units", "org_units", "unit_id"),
        ("positions", "positions", "position_id"),
    ]
    steps: list[dict[str, Any]] = []
    for allowlist_key, table, pk in phase_specs:
        items = allowlist.get(allowlist_key) or []
        if not items:
            continue
        steps.append(
            {
                "phase": len(steps) + 1,
                "table": table,
                "pk_column": pk,
                "ids": [int(x["id"]) for x in items],
                "labels": {int(x["id"]): x.get("label", str(x["id"])) for x in items},
            }
        )
    return steps


def verify_contour_signatures(conn: Connection, allowlist: dict[str, Any]) -> None:
    checks: list[tuple[str, str, str, list[str]]] = [
        ("positions", "positions", "position_id", ["name", "category"]),
        ("employees", "employees", "employee_id", ["full_name", "org_unit_id", "position_id"]),
        ("employee_events", "employee_events", "event_id", ["employee_id", "event_type", "from_position_id", "to_position_id"]),
        ("personnel_orders", "personnel_orders", "order_id", ["order_number", "status", "order_type_code"]),
        ("personnel_order_items", "personnel_order_items", "item_id", ["order_id", "item_type_code", "employee_id"]),
        ("personnel_order_lifecycle_audit", "personnel_order_lifecycle_audit", "id", ["order_id", "action", "new_status"]),
        ("units", "org_units", "unit_id", ["code", "name"]),
    ]
    for section, table, pk, fields in checks:
        for item in allowlist.get(section) or []:
            obj_id = int(item["id"])
            if section == "positions" and obj_id in PROTECTED_POSITION_IDS:
                raise SafetyAbort(f"ABORT: position_id={obj_id} is protected")
            if section == "employees" and obj_id in PROTECTED_EMPLOYEE_IDS:
                raise SafetyAbort(f"ABORT: employee_id={obj_id} is protected")
            if section == "units" and obj_id in PROTECTED_ORG_UNIT_IDS:
                raise SafetyAbort(f"ABORT: org_unit_id={obj_id} is protected")
            row = _fetch_row(conn, table, pk, obj_id)
            if row is None:
                raise SafetyAbort(f"ABORT: {table} id={obj_id} missing in database")
            for field in item["expected_signature"]:
                if field not in fields:
                    continue
                exp = _normalize_signature_value(item["expected_signature"][field])
                act = _normalize_signature_value(row.get(field))
                if exp != act:
                    raise SafetyAbort(
                        f"ABORT: {table} id={obj_id} signature mismatch {field!r}: expected {exp!r} got {act!r}"
                    )


def run_position_contours_plan(
    engine: Engine,
    db_identity: dict[str, Any],
    *,
    manifest_out,
    allowlist_out: Any = None,
) -> dict[str, Any]:
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        inventory = build_contour_inventory(conn)
        allowlist_draft = build_allowlist_draft(inventory)
        delete_steps = build_delete_steps_from_allowlist(allowlist_draft)
        fk_catalog = fetch_fk_catalog(conn)

    if allowlist_out:
        from personnel_cleanup_fk_graph import assert_external_path

        path = assert_external_path(allowlist_out, label="Allowlist draft")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(allowlist_draft, fh, indent=2, ensure_ascii=False, default=str)
            fh.write("\n")

    manifest = {
        "timestamp": _utc_now(),
        "command": "plan",
        "mode": "plan",
        "domain": "position-contours",
        "database": db_identity,
        "execute_ready": True,
        "inventory": inventory,
        "delete_plan": {
            "steps": delete_steps,
            "total_rows": sum(len(s["ids"]) for s in delete_steps),
        },
        "allowlist_draft_path": str(allowlist_out) if allowlist_out else None,
        "allowlist_hash": hashlib.sha256(
            json.dumps(allowlist_draft, sort_keys=True, default=str).encode()
        ).hexdigest(),
        "fk_edge_count": len(fk_catalog),
    }
    out_path = save_report(manifest_out, manifest)
    print(f"DOMAIN: position-contours")
    print(f"MODE: plan")
    print(f"CONTOURS: {len(inventory['contours'])}")
    print(f"DELETE STEPS: {len(delete_steps)}")
    print(f"TOTAL ROWS PLANNED: {manifest['delete_plan']['total_rows']}")
    print(f"SEMANTIC HITS: {inventory['semantic_scan']['hit_count']}")
    print(f"POSITION 325: {inventory['contours'][1]['position_325_resolution']['resolution']}")
    print(f"EXECUTE READY: {manifest['execute_ready']}")
    if allowlist_out:
        print(f"ALLOWLIST DRAFT: {allowlist_out}")
    print(f"MANIFEST: {out_path}")
    return manifest


def run_position_contours_execute(
    engine: Engine,
    allowlist: dict[str, Any],
    db_identity: dict[str, Any],
    *,
    manifest_out,
) -> dict[str, Any]:
    steps = build_delete_steps_from_allowlist(allowlist)
    deleted: list[dict[str, Any]] = []
    with engine.begin() as conn:
        verify_contour_signatures(conn, allowlist)
        for step in steps:
            table = step["table"]
            pk = step["pk_column"]
            ids = step["ids"]
            if not ids or not table_exists(conn, table):
                continue
            result = conn.execute(
                text(f"DELETE FROM public.{table} WHERE {pk} = ANY(:ids)"),
                {"ids": ids},
            )
            rc = int(result.rowcount or 0)
            for obj_id in ids:
                deleted.append(
                    {
                        "table": table,
                        "id": obj_id,
                        "label": step["labels"].get(obj_id, str(obj_id)),
                        "rowcount": rc,
                        "phase": step["phase"],
                    }
                )
    manifest = {
        "timestamp": _utc_now(),
        "command": "execute",
        "mode": "execute",
        "domain": "position-contours",
        "database": db_identity,
        "transaction_status": "committed",
        "deleted": deleted,
        "deleted_by_table": _count_by_table(deleted),
    }
    out_path = save_report(manifest_out, manifest)
    print(f"EXECUTE position-contours: deleted {len(deleted)} object refs")
    print(f"MANIFEST: {out_path}")
    return manifest


def _count_by_table(deleted: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for d in deleted:
        out[d["table"]] = out.get(d["table"], 0) + 1
    return out


def run_position_contours_verify(
    engine: Engine,
    allowlist: dict[str, Any],
    db_identity: dict[str, Any],
    *,
    manifest_out,
    before_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    checks: dict[str, Any] = {}

    with engine.connect() as conn:
        for section, table, pk in [
            ("positions", "positions", "position_id"),
            ("employees", "employees", "employee_id"),
            ("employee_events", "employee_events", "event_id"),
            ("personnel_orders", "personnel_orders", "order_id"),
            ("personnel_order_items", "personnel_order_items", "item_id"),
            ("units", "org_units", "unit_id"),
        ]:
            items = allowlist.get(section) or []
            ids = [int(x["id"]) for x in items]
            remaining = 0
            if ids and table_exists(conn, table):
                remaining = int(
                    conn.execute(
                        text(f"SELECT COUNT(*) FROM public.{table} WHERE {pk} = ANY(:ids)"),
                        {"ids": ids},
                    ).scalar()
                    or 0
                )
            checks[f"allowlisted_{section}_remaining"] = remaining
            if remaining:
                failures.append(f"{section}: {remaining} allowlisted rows still present")

        for pid in PROTECTED_POSITION_IDS:
            row = _fetch_row(conn, "positions", "position_id", pid)
            if not row:
                failures.append(f"protected position_id={pid} missing")

        for eid in PROTECTED_EMPLOYEE_IDS:
            row = _fetch_row(conn, "employees", "employee_id", eid)
            if not row:
                failures.append(f"protected employee_id={eid} missing")

        for uid in PROTECTED_ORG_UNIT_IDS:
            row = _fetch_row(conn, "org_units", "unit_id", uid)
            if not row:
                failures.append(f"protected org_unit_id={uid} missing")

        seed_remaining = [
            pid
            for pid in SEED_BLOCKED_POSITION_IDS
            if _fetch_row(conn, "positions", "position_id", pid)
        ]
        checks["seed_blocked_positions_remaining"] = seed_remaining
        if seed_remaining:
            failures.append(f"seed blocked positions still present: {seed_remaining}")

        inventory = build_contour_inventory(conn)
        checks["post_semantic_hit_count"] = inventory["semantic_scan"]["hit_count"]
        if inventory["semantic_scan"]["hit_count"] > 0:
            warnings.append(f"semantic refs remain: {inventory['semantic_scan']['hit_count']}")

    passed = len(failures) == 0
    manifest = {
        "timestamp": _utc_now(),
        "command": "verify",
        "mode": "verify",
        "domain": "position-contours",
        "database": db_identity,
        "checks": checks,
        "result": {"passed": passed, "failures": failures, "warnings": warnings},
    }
    out_path = save_report(manifest_out, manifest)
    print(f"VERIFY position-contours passed={passed}")
    print(f"MANIFEST: {out_path}")
    return manifest
