#!/usr/bin/env python3
"""Universal local/dev Personnel and Directory test-data cleanup runner.

Dry-run is the default mode. Execute requires explicit confirmation, backup proof,
and an external allowlist with per-record signatures.

Not for production databases.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

_TOOLKIT_DIR = Path(__file__).resolve().parent
if str(_TOOLKIT_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLKIT_DIR))

from personnel_cleanup_fk_graph import (
    SafetyAbort,
    allowlist_ids_by_table,
    assert_external_path,
    compare_runner_vs_topo,
    create_engine_from_guard,
    expand_blocking_children,
    fetch_fk_catalog,
    load_allowlist,
    resolve_database_url,
    save_report,
    table_exists,
    table_pk_column,
    topological_delete_order,
)

logger = logging.getLogger("personnel_test_cleanup")

EXECUTE_CONFIRM_PHRASE = "DELETE_LOCAL_TEST_DATA"


@dataclass
class DeleteStep:
    table: str
    pk_column: str
    ids: list[int]
    labels: dict[int, str] = field(default_factory=dict)
    phase: str = ""
    conditional: str | None = None


@dataclass
class Plan:
    steps: list[DeleteStep] = field(default_factory=list)
    discovered: dict[str, Any] = field(default_factory=dict)
    blocked: list[dict[str, Any]] = field(default_factory=list)
    protected: list[dict[str, Any]] = field(default_factory=list)
    org_cabinet_chain: dict[str, Any] = field(default_factory=dict)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _normalize(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def _compare_signature(
    entity_type: str,
    entity_id: int,
    expected: dict[str, Any],
    actual: dict[str, Any] | None,
) -> None:
    if actual is None:
        raise SafetyAbort(f"ABORT signature: {entity_type} id={entity_id} missing in database")
    for field_name, expected_value in expected.items():
        actual_value = actual.get(field_name)
        if _normalize(actual_value) != _normalize(expected_value):
            raise SafetyAbort(
                f"ABORT signature: {entity_type} id={entity_id} "
                f"field {field_name!r} expected {expected_value!r} got {actual_value!r}"
            )


def _fetch_map(
    conn: Connection,
    sql: str,
    ids: list[int],
    id_col: str,
) -> dict[int, dict[str, Any]]:
    if not ids:
        return {}
    rows = conn.execute(text(sql), {"ids": ids}).mappings().all()
    return {int(r[id_col]): dict(r) for r in rows}


def verify_allowlist_signatures(conn: Connection, allowlist: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}

    persons = allowlist["persons"]
    person_map = _fetch_map(
        conn,
        "SELECT person_id, full_name, match_key, iin FROM public.persons WHERE person_id = ANY(:ids)",
        [int(x["id"]) for x in persons],
        "person_id",
    )
    for item in persons:
        _compare_signature("person", int(item["id"]), item["expected_signature"], person_map.get(int(item["id"])))
    counts["persons"] = len(persons)

    employees = allowlist["employees"]
    emp_map = _fetch_map(
        conn,
        "SELECT employee_id, person_id, full_name FROM public.employees WHERE employee_id = ANY(:ids)",
        [int(x["id"]) for x in employees],
        "employee_id",
    )
    for item in employees:
        _compare_signature("employee", int(item["id"]), item["expected_signature"], emp_map.get(int(item["id"])))
    counts["employees"] = len(employees)

    users = allowlist["users"]
    user_map = _fetch_map(
        conn,
        "SELECT user_id, full_name, google_login, unit_id, role_id, employee_id "
        "FROM public.users WHERE user_id = ANY(:ids)",
        [int(x["id"]) for x in users],
        "user_id",
    )
    for item in users:
        _compare_signature("user", int(item["id"]), item["expected_signature"], user_map.get(int(item["id"])))
    counts["users"] = len(users)

    units = allowlist["units"]
    unit_map = _fetch_map(
        conn,
        "SELECT unit_id, code, name FROM public.org_units WHERE unit_id = ANY(:ids)",
        [int(x["id"]) for x in units],
        "unit_id",
    )
    for item in units:
        _compare_signature("unit", int(item["id"]), item["expected_signature"], unit_map.get(int(item["id"])))
    counts["units"] = len(units)

    assignments = allowlist["assignments"]
    assignment_ids = [int(x["id"]) for x in assignments]
    if assignment_ids and table_exists(conn, "person_assignments"):
        asn_map = _fetch_map(
            conn,
            "SELECT assignment_id, person_id, org_unit_id, position_id "
            "FROM public.person_assignments WHERE assignment_id = ANY(:ids)",
            assignment_ids,
            "assignment_id",
        )
        for item in assignments:
            _compare_signature(
                "assignment", int(item["id"]), item["expected_signature"], asn_map.get(int(item["id"]))
            )
    counts["assignments"] = len(assignments)

    positions = allowlist["positions"]
    pos_map = _fetch_map(
        conn,
        "SELECT position_id, name, category FROM public.positions WHERE position_id = ANY(:ids)",
        [int(x["id"]) for x in positions],
        "position_id",
    )
    for item in positions:
        _compare_signature("position", int(item["id"]), item["expected_signature"], pos_map.get(int(item["id"])))
    counts["positions"] = len(positions)

    identities = allowlist["identities"]
    identity_ids = [int(x["id"]) for x in identities]
    if identity_ids and table_exists(conn, "employee_identities"):
        id_map = _fetch_map(
            conn,
            "SELECT identity_id, employee_id, identity_type, identity_value "
            "FROM public.employee_identities WHERE identity_id = ANY(:ids)",
            identity_ids,
            "identity_id",
        )
        for item in identities:
            _compare_signature("identity", int(item["id"]), item["expected_signature"], id_map.get(int(item["id"])))
    counts["identities"] = len(identity_ids)

    batches = allowlist["batches"]
    batch_ids = [int(x["id"]) for x in batches]
    if batch_ids and table_exists(conn, "hr_import_batches"):
        batch_map = _fetch_map(
            conn,
            "SELECT batch_id, file_name, status FROM public.hr_import_batches WHERE batch_id = ANY(:ids)",
            batch_ids,
            "batch_id",
        )
        for item in batches:
            _compare_signature("batch", int(item["id"]), item["expected_signature"], batch_map.get(int(item["id"])))
    counts["batches"] = len(batch_ids)

    snapshots = allowlist["snapshots"]
    snapshot_ids = [int(x["id"]) for x in snapshots]
    if snapshot_ids and table_exists(conn, "hr_canonical_snapshots"):
        snap_map = _fetch_map(
            conn,
            "SELECT snapshot_id, status, source_batch_id "
            "FROM public.hr_canonical_snapshots WHERE snapshot_id = ANY(:ids)",
            snapshot_ids,
            "snapshot_id",
        )
        for item in snapshots:
            _compare_signature("snapshot", int(item["id"]), item["expected_signature"], snap_map.get(int(item["id"])))
    counts["snapshots"] = len(snapshot_ids)

    recon_items = allowlist["reconciliation"]["items"]
    item_ids = [int(x["id"]) for x in recon_items]
    if item_ids and table_exists(conn, "identity_reconciliation_items"):
        ri_map = _fetch_map(
            conn,
            "SELECT item_id, run_id, person_id, outcome "
            "FROM public.identity_reconciliation_items WHERE item_id = ANY(:ids)",
            item_ids,
            "item_id",
        )
        for item in recon_items:
            _compare_signature(
                "reconciliation_item", int(item["id"]), item["expected_signature"], ri_map.get(int(item["id"]))
            )
    counts["reconciliation_items"] = len(item_ids)

    recon_runs = allowlist["reconciliation"]["runs"]
    run_ids = [int(x["id"]) for x in recon_runs]
    if run_ids and table_exists(conn, "identity_reconciliation_runs"):
        rr_map = _fetch_map(
            conn,
            "SELECT run_id, status, snapshot_id "
            "FROM public.identity_reconciliation_runs WHERE run_id = ANY(:ids)",
            run_ids,
            "run_id",
        )
        for item in recon_runs:
            _compare_signature(
                "reconciliation_run", int(item["id"]), item["expected_signature"], rr_map.get(int(item["id"]))
            )
    counts["reconciliation_runs"] = len(run_ids)

    audit_items = allowlist["audit"]
    audit_ids = [int(x["id"]) for x in audit_items]
    if audit_ids and table_exists(conn, "security_audit_log"):
        au_map = _fetch_map(
            conn,
            "SELECT audit_id, event_type, target_person_id, actor_user_id "
            "FROM public.security_audit_log WHERE audit_id = ANY(:ids)",
            audit_ids,
            "audit_id",
        )
        for item in audit_items:
            _compare_signature("audit", int(item["id"]), item["expected_signature"], au_map.get(int(item["id"])))
    counts["audit"] = len(audit_ids)

    roles = allowlist["roles"]
    role_map = _fetch_map(
        conn,
        "SELECT role_id, code, name FROM public.roles WHERE role_id = ANY(:ids)",
        [int(x["id"]) for x in roles],
        "role_id",
    )
    for item in roles:
        _compare_signature("role", int(item["id"]), item["expected_signature"], role_map.get(int(item["id"])))
    counts["roles"] = len(roles)

    return counts


def verify_protected_entities(conn: Connection, allowlist: dict[str, Any]) -> list[dict[str, Any]]:
    protected_report: list[dict[str, Any]] = []
    prot = allowlist["protected"]

    for entity_type, table, pk, items in (
        ("person", "persons", "person_id", prot.get("persons", [])),
        ("employee", "employees", "employee_id", prot.get("employees", [])),
        ("user", "users", "user_id", prot.get("users", [])),
        ("unit", "org_units", "unit_id", prot.get("units", [])),
        ("position", "positions", "position_id", prot.get("positions", [])),
        ("role", "roles", "role_id", prot.get("roles", [])),
    ):
        for item in items:
            row = conn.execute(
                text(f"SELECT * FROM public.{table} WHERE {pk} = :id"),
                {"id": int(item["id"])},
            ).mappings().first()
            _compare_signature(
                f"protected_{entity_type}",
                int(item["id"]),
                item["expected_signature"],
                dict(row) if row else None,
            )
            protected_report.append({"type": entity_type, "id": item["id"], "status": "present"})

    return protected_report


def assert_protected_not_in_delete_set(allowlist: dict[str, Any]) -> None:
    protected_ids = {
        "persons": {int(x["id"]) for x in allowlist["protected"].get("persons", [])},
        "employees": {int(x["id"]) for x in allowlist["protected"].get("employees", [])},
        "users": {int(x["id"]) for x in allowlist["protected"].get("users", [])},
        "units": {int(x["id"]) for x in allowlist["protected"].get("units", [])},
        "positions": {int(x["id"]) for x in allowlist["protected"].get("positions", [])},
        "roles": {int(x["id"]) for x in allowlist["protected"].get("roles", [])},
    }
    for section, key in (
        ("persons", "persons"),
        ("employees", "employees"),
        ("users", "users"),
        ("units", "units"),
        ("positions", "positions"),
        ("roles", "roles"),
    ):
        for item in allowlist[section]:
            entity_id = int(item["id"])
            if entity_id in protected_ids[key]:
                raise SafetyAbort(f"ABORT: protected {section[:-1]} {entity_id} appears in delete allowlist")


def _labels_from_allowlist(items: list[dict[str, Any]]) -> dict[int, str]:
    return {int(x["id"]): str(x.get("label", x["id"])) for x in items}


def _role_reference_counts(conn: Connection, role_id: int) -> dict[str, int]:
    counts = {"users": 0, "access_grants": 0, "tasks_executor": 0, "regular_tasks": 0}
    if table_exists(conn, "users"):
        counts["users"] = int(
            conn.execute(text("SELECT COUNT(*) FROM public.users WHERE role_id = :rid"), {"rid": role_id}).scalar()
            or 0
        )
    if table_exists(conn, "access_grants"):
        counts["access_grants"] = int(
            conn.execute(
                text(
                    "SELECT COUNT(*) FROM public.access_grants "
                    "WHERE target_type = 'ROLE' AND target_id = :rid"
                ),
                {"rid": role_id},
            ).scalar()
            or 0
        )
    if table_exists(conn, "tasks"):
        cols = {
            r[0]
            for r in conn.execute(
                text(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='tasks'
                      AND column_name IN ('executor_role_id', 'role_id')
                    """
                )
            ).fetchall()
        }
        for col in cols:
            counts["tasks_executor"] += int(
                conn.execute(
                    text(f"SELECT COUNT(*) FROM public.tasks WHERE {col} = :rid"),
                    {"rid": role_id},
                ).scalar()
                or 0
            )
    if table_exists(conn, "regular_tasks"):
        rt_cols = {
            r[0]
            for r in conn.execute(
                text(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='regular_tasks'
                    """
                )
            ).fetchall()
        }
        parts = [f"{col} = :rid" for col in ("initiator_role_id", "target_role_id", "executor_role_id") if col in rt_cols]
        if parts:
            counts["regular_tasks"] = int(
                conn.execute(
                    text(f"SELECT COUNT(*) FROM public.regular_tasks WHERE {' OR '.join(parts)}"),
                    {"rid": role_id},
                ).scalar()
                or 0
            )
    return counts


def discover_org_cabinet_chain(
    conn: Connection,
    allowlist: dict[str, Any],
) -> tuple[dict[str, Any], list[DeleteStep]]:
    position_ids = {int(x["id"]) for x in allowlist["positions"]}
    unit_ids = {int(x["id"]) for x in allowlist["units"]}
    allow_role_ids = {int(x["id"]) for x in allowlist["roles"]}
    chain: dict[str, list[dict[str, Any]]] = {
        "org_unique_position": [],
        "position_cabinet": [],
        "permission_template": [],
        "legacy_position_mapping": [],
    }

    if not table_exists(conn, "org_unique_position"):
        return {"discovered": chain, "validation": {"skipped": True, "reason": "table missing"}}, []

    oup_rows = [
        dict(r)
        for r in conn.execute(
            text(
                """
                SELECT org_unique_position_id, catalog_position_id, org_unit_id, lifecycle_status
                FROM public.org_unique_position
                WHERE catalog_position_id = ANY(:pids) OR org_unit_id = ANY(:uids)
                ORDER BY org_unique_position_id
                """
            ),
            {"pids": list(position_ids) or [-1], "uids": list(unit_ids) or [-1]},
        ).mappings().all()
    ]
    for row in oup_rows:
        pos_id = row.get("catalog_position_id")
        unit_id = row.get("org_unit_id")
        if pos_id is not None and int(pos_id) not in position_ids:
            raise SafetyAbort(
                f"ABORT: org_unique_position {row['org_unique_position_id']} "
                f"links position outside allowlist"
            )
        if unit_id is not None and int(unit_id) not in unit_ids:
            raise SafetyAbort(
                f"ABORT: org_unique_position {row['org_unique_position_id']} "
                f"links org_unit outside allowlist"
            )
        chain["org_unique_position"].append(
            {"id": int(row["org_unique_position_id"]), "linked_position_id": pos_id, "linked_org_unit_id": unit_id}
        )
    oup_ids = {int(r["org_unique_position_id"]) for r in oup_rows}

    if table_exists(conn, "position_cabinet") and oup_ids:
        pc_rows = [
            dict(r)
            for r in conn.execute(
                text(
                    """
                    SELECT position_cabinet_id, org_unique_position_id
                    FROM public.position_cabinet
                    WHERE org_unique_position_id = ANY(:oup_ids)
                    ORDER BY position_cabinet_id
                    """
                ),
                {"oup_ids": list(oup_ids)},
            ).mappings().all()
        ]
        for row in pc_rows:
            chain["position_cabinet"].append(
                {"id": int(row["position_cabinet_id"]), "org_unique_position_id": int(row["org_unique_position_id"])}
            )
        pc_ids = [int(r["position_cabinet_id"]) for r in pc_rows]
        if table_exists(conn, "permission_template") and pc_ids:
            pt_rows = [
                dict(r)
                for r in conn.execute(
                    text(
                        """
                        SELECT permission_template_id, position_cabinet_id, role_id, access_role_id
                        FROM public.permission_template
                        WHERE position_cabinet_id = ANY(:pc_ids)
                        ORDER BY permission_template_id
                        """
                    ),
                    {"pc_ids": pc_ids},
                ).mappings().all()
            ]
            for row in pt_rows:
                for role_col in ("role_id", "access_role_id"):
                    role_val = row.get(role_col)
                    if role_val is not None and int(role_val) not in allow_role_ids:
                        raise SafetyAbort(
                            f"ABORT: permission_template {row['permission_template_id']} "
                            f"binds role outside allowlist via {role_col}"
                        )
                chain["permission_template"].append(
                    {"id": int(row["permission_template_id"]), "position_cabinet_id": int(row["position_cabinet_id"])}
                )

    if table_exists(conn, "legacy_position_mapping"):
        lpm_rows = [
            dict(r)
            for r in conn.execute(
                text(
                    """
                    SELECT legacy_position_mapping_id, catalog_position_id, org_unit_id, org_unique_position_id
                    FROM public.legacy_position_mapping
                    WHERE catalog_position_id = ANY(:pids)
                       OR org_unit_id = ANY(:uids)
                       OR org_unique_position_id = ANY(:oup_ids)
                    ORDER BY legacy_position_mapping_id
                    """
                ),
                {"pids": list(position_ids) or [-1], "uids": list(unit_ids) or [-1], "oup_ids": list(oup_ids) or [-1]},
            ).mappings().all()
        ]
        for row in lpm_rows:
            chain["legacy_position_mapping"].append({"id": int(row["legacy_position_mapping_id"])})

    delete_order = [
        ("permission_template", "permission_template_id"),
        ("position_cabinet", "position_cabinet_id"),
        ("legacy_position_mapping", "legacy_position_mapping_id"),
        ("org_unique_position", "org_unique_position_id"),
    ]
    steps: list[DeleteStep] = []
    for table, pk in delete_order:
        ids = [int(x["id"]) for x in chain.get(table, [])]
        if not ids:
            continue
        if not table_exists(conn, table):
            raise SafetyAbort(f"ABORT: org_cabinet_chain table missing: {table}")
        steps.append(
            DeleteStep(
                table,
                pk,
                ids,
                {i: f"org_cabinet:{table}:{i}" for i in ids},
                phase="org_cabinet_chain",
            )
        )

    manifest_section = {
        "discovered": chain,
        "validation": {
            "exclusive_to_allowlist": True,
            "counts": {k: len(v) for k, v in chain.items()},
            "delete_order": [t for t, _ in delete_order],
        },
    }
    return manifest_section, steps


def build_delete_plan(conn: Connection, allowlist: dict[str, Any]) -> Plan:
    plan = Plan()
    plan.protected = [{"section": "protected", "entries": allowlist["protected"]}]

    audit_ids = [int(x["id"]) for x in allowlist["audit"]]
    if audit_ids and table_exists(conn, "security_audit_log"):
        plan.steps.append(
            DeleteStep(
                "security_audit_log",
                "audit_id",
                audit_ids,
                _labels_from_allowlist(allowlist["audit"]),
                phase="audit_chain",
            )
        )

    recon_item_ids = [int(x["id"]) for x in allowlist["reconciliation"]["items"]]
    if recon_item_ids and table_exists(conn, "identity_reconciliation_items"):
        plan.steps.append(
            DeleteStep(
                "identity_reconciliation_items",
                "item_id",
                recon_item_ids,
                _labels_from_allowlist(allowlist["reconciliation"]["items"]),
                phase="reconciliation",
            )
        )

    recon_run_ids = [int(x["id"]) for x in allowlist["reconciliation"]["runs"]]
    if recon_run_ids and table_exists(conn, "identity_reconciliation_runs"):
        plan.steps.append(
            DeleteStep(
                "identity_reconciliation_runs",
                "run_id",
                recon_run_ids,
                _labels_from_allowlist(allowlist["reconciliation"]["runs"]),
                phase="reconciliation",
            )
        )

    snapshot_ids = [int(x["id"]) for x in allowlist["snapshots"]]
    if snapshot_ids:
        for child_table in ("hr_snapshot_effective_entries", "hr_canonical_snapshot_entries"):
            if not table_exists(conn, child_table):
                continue
            pk_col = table_pk_column(conn, child_table)
            if not pk_col:
                continue
            rows = conn.execute(
                text(f"SELECT {pk_col} FROM public.{child_table} WHERE snapshot_id = ANY(:ids)"),
                {"ids": snapshot_ids},
            ).scalars().all()
            child_ids = [int(r) for r in rows]
            if child_ids:
                plan.steps.append(
                    DeleteStep(
                        child_table,
                        pk_col,
                        child_ids,
                        {i: f"snapshot_child:{i}" for i in child_ids},
                        phase="hr_chain",
                    )
                )
        if table_exists(conn, "hr_canonical_snapshots"):
            plan.steps.append(
                DeleteStep(
                    "hr_canonical_snapshots",
                    "snapshot_id",
                    snapshot_ids,
                    _labels_from_allowlist(allowlist["snapshots"]),
                    phase="hr_chain",
                )
            )

    batch_ids = [int(x["id"]) for x in allowlist["batches"]]
    if batch_ids and table_exists(conn, "hr_import_batches"):
        plan.steps.append(
            DeleteStep(
                "hr_import_batches",
                "batch_id",
                batch_ids,
                _labels_from_allowlist(allowlist["batches"]),
                phase="hr_chain",
            )
        )

    identity_ids = [int(x["id"]) for x in allowlist["identities"]]
    if identity_ids and table_exists(conn, "employee_identities"):
        plan.steps.append(
            DeleteStep(
                "employee_identities",
                "identity_id",
                identity_ids,
                _labels_from_allowlist(allowlist["identities"]),
                phase="personnel",
            )
        )

    assignment_ids = [int(x["id"]) for x in allowlist["assignments"]]
    if assignment_ids and table_exists(conn, "person_assignments"):
        plan.steps.append(
            DeleteStep(
                "person_assignments",
                "assignment_id",
                assignment_ids,
                _labels_from_allowlist(allowlist["assignments"]),
                phase="personnel",
            )
        )

    user_ids = [int(x["id"]) for x in allowlist["users"]]
    if user_ids:
        if table_exists(conn, "access_grants"):
            grant_ids = [
                int(r)
                for r in conn.execute(
                    text(
                        "SELECT grant_id FROM public.access_grants "
                        "WHERE target_type = 'USER' AND target_id = ANY(:uids)"
                    ),
                    {"uids": user_ids},
                ).scalars().all()
            ]
            if grant_ids:
                plan.steps.append(
                    DeleteStep(
                        "access_grants",
                        "grant_id",
                        grant_ids,
                        {i: f"grant:{i}" for i in grant_ids},
                        phase="access",
                    )
                )
        if table_exists(conn, "personnel_visibility_assignments"):
            pva_ids = [
                int(r)
                for r in conn.execute(
                    text(
                        "SELECT assignment_id FROM public.personnel_visibility_assignments "
                        "WHERE target_user_id = ANY(:uids)"
                    ),
                    {"uids": user_ids},
                ).scalars().all()
            ]
            if pva_ids:
                plan.steps.append(
                    DeleteStep(
                        "personnel_visibility_assignments",
                        "assignment_id",
                        pva_ids,
                        {i: f"visibility:{i}" for i in pva_ids},
                        phase="access",
                    )
                )
        plan.steps.append(
            DeleteStep(
                "users",
                "user_id",
                user_ids,
                _labels_from_allowlist(allowlist["users"]),
                phase="users",
            )
        )

    employee_ids = [int(x["id"]) for x in allowlist["employees"]]
    if employee_ids and table_exists(conn, "employees"):
        plan.steps.append(
            DeleteStep(
                "employees",
                "employee_id",
                employee_ids,
                _labels_from_allowlist(allowlist["employees"]),
                phase="personnel",
            )
        )

    person_ids = [int(x["id"]) for x in allowlist["persons"]]
    if person_ids:
        plan.steps.append(
            DeleteStep(
                "persons",
                "person_id",
                person_ids,
                _labels_from_allowlist(allowlist["persons"]),
                phase="personnel",
            )
        )

    org_cabinet_manifest, org_cabinet_steps = discover_org_cabinet_chain(conn, allowlist)
    plan.org_cabinet_chain = org_cabinet_manifest
    plan.steps.extend(org_cabinet_steps)

    position_ids = [int(x["id"]) for x in allowlist["positions"]]
    if position_ids:
        plan.steps.append(
            DeleteStep(
                "positions",
                "position_id",
                position_ids,
                _labels_from_allowlist(allowlist["positions"]),
                phase="org",
            )
        )

    unit_ids = [int(x["id"]) for x in allowlist["units"]]
    if unit_ids:
        plan.steps.append(
            DeleteStep(
                "org_units",
                "unit_id",
                unit_ids,
                _labels_from_allowlist(allowlist["units"]),
                phase="org",
            )
        )

    for item in allowlist["roles"]:
        role_id = int(item["id"])
        refs = _role_reference_counts(conn, role_id)
        label = str(item.get("label", role_id))
        plan.steps.append(
            DeleteStep(
                "roles",
                "role_id",
                [role_id],
                {role_id: label},
                phase="roles_post_users",
                conditional="delete only if orphaned after user delete",
            )
        )
        plan.discovered[f"role_refs_{role_id}"] = refs
        if any(refs.values()):
            plan.blocked.append(
                {
                    "type": "role",
                    "id": role_id,
                    "reason": "referenced now; may become deletable after user delete",
                    "references": refs,
                }
            )

    return plan


def evaluate_roles_after_user_delete(conn: Connection, allowlist: dict[str, Any]) -> list[DeleteStep]:
    steps: list[DeleteStep] = []
    for item in allowlist["roles"]:
        role_id = int(item["id"])
        _compare_signature(
            "role",
            role_id,
            item["expected_signature"],
            conn.execute(
                text("SELECT role_id, code, name FROM public.roles WHERE role_id = :id"),
                {"id": role_id},
            ).mappings().first(),
        )
        refs = _role_reference_counts(conn, role_id)
        if not any(refs.values()):
            steps.append(
                DeleteStep(
                    "roles",
                    "role_id",
                    [role_id],
                    {role_id: str(item.get("label", role_id))},
                    phase="roles_post_users",
                )
            )
        else:
            logger.warning("BLOCKED role %s still referenced: %s", role_id, refs)
    return steps


def validate_fk_delete_plan(conn: Connection, allowlist: dict[str, Any]) -> dict[str, Any]:
    targets = allowlist_ids_by_table(allowlist)
    fk_edges = fetch_fk_catalog(conn)
    blockers = expand_blocking_children(conn, fk_edges, targets)
    allowlist_tables = set(targets.keys())
    scope_tables = allowlist_tables | {b["child_table"] for b in blockers}
    topo = topological_delete_order(fk_edges, scope_tables)
    runner_issues = compare_runner_vs_topo(topo["delete_order"], blockers)
    missing_not_in_runner = [b for b in blockers if not b["in_runner"]]
    return {
        "fk_edge_count": len(fk_edges),
        "blocking_children": blockers,
        "unresolved_blockers": missing_not_in_runner,
        "missing_tables": sorted({b["child_table"] for b in blockers if not b["in_runner"]}),
        "topological_delete_order": topo,
        "runner_issues": runner_issues,
        "execute_ready": len(missing_not_in_runner) == 0,
        "blocker_count": len(blockers),
        "missing_blocker_count": len(missing_not_in_runner),
    }


def plan_to_manifest_section(plan: Plan) -> dict[str, Any]:
    deletes_by_table: dict[str, int] = {}
    deletable_rows: list[dict[str, Any]] = []
    for step in plan.steps:
        if step.phase == "roles_post_users" and step.conditional:
            continue
        deletes_by_table[step.table] = deletes_by_table.get(step.table, 0) + len(step.ids)
        for row_id in step.ids:
            deletable_rows.append(
                {
                    "table": step.table,
                    "pk": step.pk_column,
                    "id": row_id,
                    "label": step.labels.get(row_id, str(row_id)),
                    "phase": step.phase,
                }
            )
    conditional_roles = [
        {
            "table": step.table,
            "pk": step.pk_column,
            "id": step.ids[0],
            "label": step.labels.get(step.ids[0], str(step.ids[0])),
            "phase": step.phase,
            "conditional": step.conditional,
        }
        for step in plan.steps
        if step.phase == "roles_post_users" and step.conditional
    ]
    return {
        "deletable_by_table": deletes_by_table,
        "deletable_total_rows": sum(deletes_by_table.values()),
        "deletable_rows": deletable_rows,
        "conditional_roles": conditional_roles,
        "blocked": plan.blocked,
        "protected": plan.protected,
        "discovered": plan.discovered,
        "org_cabinet_chain": plan.org_cabinet_chain,
    }


def read_alembic_version(conn: Connection) -> str | None:
    if not table_exists(conn, "alembic_version"):
        return None
    row = conn.execute(text("SELECT version_num FROM public.alembic_version LIMIT 1")).first()
    return str(row[0]) if row else None


def run_allowlist_remaining_checks(conn: Connection, allowlist: dict[str, Any]) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    table_id_map = {
        "roles": ("roles", "role_id", allowlist["roles"]),
        "employees": ("employees", "employee_id", allowlist["employees"]),
        "persons": ("persons", "person_id", allowlist["persons"]),
        "users": ("users", "user_id", allowlist["users"]),
    }
    for label, (table, pk, items) in table_id_map.items():
        ids = [int(x["id"]) for x in items]
        if not ids or not table_exists(conn, table):
            checks[f"allowlisted_{label}_remaining"] = 0
            continue
        checks[f"allowlisted_{label}_remaining"] = int(
            conn.execute(
                text(f"SELECT COUNT(*) FROM public.{table} WHERE {pk} = ANY(:ids)"),
                {"ids": ids},
            ).scalar()
            or 0
        )
    checks["ok"] = all(v == 0 for k, v in checks.items() if k.endswith("_remaining"))
    return checks


def build_verify_report(
    conn: Connection,
    allowlist: dict[str, Any],
    db_identity: dict[str, Any],
    *,
    alembic_before: str | None = None,
    before_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    alembic_now = read_alembic_version(conn)
    remaining = run_allowlist_remaining_checks(conn, allowlist)
    protected = verify_protected_entities(conn, allowlist)
    fk_validation = validate_fk_delete_plan(conn, allowlist)

    passed = remaining.get("ok", False) and all(item["status"] == "present" for item in protected)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "verify",
        "database": db_identity,
        "alembic_version": alembic_now,
        "allowlist_remaining": remaining,
        "protected_verified": protected,
        "fk_validation_after": {
            "blocker_count": fk_validation["blocker_count"],
            "execute_ready": fk_validation["execute_ready"],
        },
        "alembic_unchanged": {
            "ok": alembic_before is None or alembic_now == alembic_before,
            "before": alembic_before,
            "after": alembic_now,
        },
        "result": {"passed": passed, "cleanup_complete": remaining.get("ok", False)},
    }


def assert_execute_guards(
    *,
    confirm_phrase: str,
    confirm_database_name: str,
    expected_database_name: str,
    backup_path: Path | None,
    backup_acknowledged: bool,
) -> None:
    if confirm_phrase != EXECUTE_CONFIRM_PHRASE:
        raise SafetyAbort(f"ABORT: --confirm-phrase must be exactly {EXECUTE_CONFIRM_PHRASE!r}")
    if confirm_database_name.strip() != expected_database_name.strip():
        raise SafetyAbort(
            "ABORT: --confirm-database-name must match --expected-database-name"
        )
    if backup_path is not None:
        external = assert_external_path(backup_path, label="Backup")
        if not external.is_file():
            raise SafetyAbort(f"ABORT: backup file not found: {external}")
    elif not backup_acknowledged:
        raise SafetyAbort(
            "ABORT: provide --backup-path to an existing dump or --backup-acknowledged"
        )


def run_audit_or_dry_run(
    engine: Engine,
    allowlist: dict[str, Any],
    db_identity: dict[str, Any],
    *,
    manifest_out: Path,
    mode: str,
) -> dict[str, Any]:
    with engine.connect() as conn:
        assert_protected_not_in_delete_set(allowlist)
        signature_counts = verify_allowlist_signatures(conn, allowlist)
        protected = verify_protected_entities(conn, allowlist)
        plan = build_delete_plan(conn, allowlist)
        fk_validation = validate_fk_delete_plan(conn, allowlist)
        alembic_rev = read_alembic_version(conn)

    manifest = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "database": db_identity,
        "signature_verification": signature_counts,
        "protected_verified": protected,
        "alembic_version": alembic_rev,
        "fk_validation": fk_validation,
        **plan_to_manifest_section(plan),
    }
    out_path = save_report(manifest_out, manifest)

    print(f"DATABASE: {db_identity['url_redacted']}")
    print(f"MODE: {mode}")
    print(f"FOUND (signatures verified): {sum(signature_counts.values())} allowlist entries")
    print(f"PROTECTED: {len(protected)} entities confirmed present")
    print(f"DELETABLE rows: {manifest['deletable_total_rows']}")
    print(f"BLOCKED: {len(manifest['blocked'])}")
    print(f"FK execute_ready: {fk_validation['execute_ready']}")
    print("DELETABLE BY TABLE:")
    for table, count in sorted(manifest["deletable_by_table"].items()):
        print(f"  {table}: {count}")
    if manifest["blocked"]:
        print("BLOCKED ENTRIES:")
        for item in manifest["blocked"]:
            print(f"  {item}")
    print(f"MANIFEST: {out_path}")

    if not fk_validation["execute_ready"]:
        missing = ", ".join(fk_validation["missing_tables"])
        raise SafetyAbort(
            f"ABORT: FK blockers reference allowlist IDs but tables are missing from runner: {missing}"
        )
    return manifest


def run_execute(
    engine: Engine,
    allowlist: dict[str, Any],
    db_identity: dict[str, Any],
    *,
    manifest_out: Path,
    before_manifest_path: Path | None,
    backup_path: Path | None,
) -> dict[str, Any]:
    with engine.connect() as conn:
        alembic_before = read_alembic_version(conn)

    with engine.connect() as conn:
        assert_protected_not_in_delete_set(allowlist)
        verify_allowlist_signatures(conn, allowlist)
        verify_protected_entities(conn, allowlist)
        plan = build_delete_plan(conn, allowlist)
        fk_validation = validate_fk_delete_plan(conn, allowlist)
        if not fk_validation["execute_ready"]:
            raise SafetyAbort("ABORT: FK validation failed — execute refused")

        if before_manifest_path and before_manifest_path.is_file():
            with before_manifest_path.open(encoding="utf-8") as fh:
                prior = json.load(fh)
            if prior.get("deletable_total_rows") != sum(
                len(s.ids) for s in plan.steps if s.phase != "roles_post_users" or not s.conditional
            ):
                raise SafetyAbort("ABORT: planned row count changed since dry-run manifest")

    primary_steps = [s for s in plan.steps if s.phase != "roles_post_users"]
    actual_deletes: list[dict[str, Any]] = []
    deletes_by_table: dict[str, int] = {}
    transaction_status = "rolled_back"

    try:
        with engine.begin() as conn:
            for step in primary_steps:
                if not step.ids or not table_exists(conn, step.table):
                    continue
                result = conn.execute(
                    text(f"DELETE FROM public.{step.table} WHERE {step.pk_column} = ANY(:ids)"),
                    {"ids": step.ids},
                )
                deleted = int(result.rowcount or 0)
                deletes_by_table[step.table] = deletes_by_table.get(step.table, 0) + deleted
                for row_id in step.ids:
                    actual_deletes.append(
                        {
                            "table": step.table,
                            "id": row_id,
                            "label": step.labels.get(row_id, str(row_id)),
                            "rowcount": deleted,
                        }
                    )

            role_steps = evaluate_roles_after_user_delete(conn, allowlist)
            for step in role_steps:
                result = conn.execute(
                    text(f"DELETE FROM public.{step.table} WHERE {step.pk_column} = ANY(:ids)"),
                    {"ids": step.ids},
                )
                deleted = int(result.rowcount or 0)
                deletes_by_table[step.table] = deletes_by_table.get(step.table, 0) + deleted
                for row_id in step.ids:
                    actual_deletes.append(
                        {"table": step.table, "id": row_id, "label": step.labels.get(row_id, str(row_id)), "rowcount": deleted}
                    )
        transaction_status = "committed"
    except Exception as exc:
        logger.error("ROLLBACK: %s", exc)
        print(f"ROLLBACK: {exc}")
        raise

    with engine.connect() as conn:
        verify_report = build_verify_report(
            conn,
            allowlist,
            db_identity,
            alembic_before=alembic_before,
        )

    after_manifest = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "execute",
        "database": db_identity,
        "transaction_status": transaction_status,
        "deleted_by_table": deletes_by_table,
        "deleted_rows": actual_deletes,
        "verify": verify_report,
        "backup_path": str(backup_path) if backup_path else None,
    }
    out_path = save_report(manifest_out, after_manifest)

    print(f"EXECUTE: transaction {transaction_status}")
    print(f"DELETED rows: {sum(deletes_by_table.values())}")
    print(f"VERIFY passed: {verify_report['result']['passed']}")
    print(f"MANIFEST: {out_path}")
    return after_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local/dev Personnel test-data cleanup (dry-run by default)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--database-url", default=None, help="PostgreSQL URL or use DATABASE_URL.")
    common.add_argument(
        "--expected-database-name",
        required=True,
        help="Expected target database name (must match connected database).",
    )
    common.add_argument(
        "--allowlist",
        type=Path,
        required=True,
        help="External allowlist JSON path (outside toolkit directory).",
    )
    common.add_argument(
        "--manifest-out",
        type=Path,
        required=True,
        help="Manifest/report output path (outside toolkit directory).",
    )
    common.add_argument("-v", "--verbose", action="store_true")

    audit_parser = sub.add_parser(
        "audit",
        parents=[common],
        help="Read-only audit: signatures, FK validation, deletable/blocked report.",
    )
    dry_parser = sub.add_parser(
        "dry-run",
        parents=[common],
        help="Alias for audit (default safe mode).",
    )
    exec_parser = sub.add_parser(
        "execute",
        parents=[common],
        help="Execute deletion inside a transaction (requires confirmation and backup).",
    )
    exec_parser.add_argument(
        "--confirm-phrase",
        required=True,
        help=f"Required phrase: {EXECUTE_CONFIRM_PHRASE}",
    )
    exec_parser.add_argument(
        "--confirm-database-name",
        required=True,
        help="Must match --expected-database-name.",
    )
    exec_parser.add_argument(
        "--backup-path",
        type=Path,
        default=None,
        help="Path to an existing database backup file.",
    )
    exec_parser.add_argument(
        "--backup-acknowledged",
        action="store_true",
        help="Confirm a backup was completed when --backup-path is not supplied.",
    )
    exec_parser.add_argument(
        "--before-manifest",
        type=Path,
        default=None,
        help="Optional prior dry-run manifest for row-count consistency check.",
    )

    verify_parser = sub.add_parser(
        "verify",
        parents=[common],
        help="Post-cleanup verification against allowlist and protected entities.",
    )
    verify_parser.add_argument(
        "--before-manifest",
        type=Path,
        default=None,
        help="Optional pre-cleanup manifest for alembic comparison.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "verbose", False) else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        url = resolve_database_url(args.database_url)
        allowlist = load_allowlist(args.allowlist)
        engine, db_identity = create_engine_from_guard(
            url, expected_database_name=args.expected_database_name
        )

        if args.command in {"audit", "dry-run"}:
            run_audit_or_dry_run(
                engine,
                allowlist,
                db_identity,
                manifest_out=args.manifest_out,
                mode=args.command,
            )
            return 0

        if args.command == "verify":
            alembic_before = None
            before_manifest = None
            if args.before_manifest and args.before_manifest.is_file():
                with args.before_manifest.open(encoding="utf-8") as fh:
                    before_manifest = json.load(fh)
                alembic_before = before_manifest.get("alembic_version")
            with engine.connect() as conn:
                report = build_verify_report(
                    conn,
                    allowlist,
                    db_identity,
                    alembic_before=alembic_before,
                    before_manifest=before_manifest,
                )
            out_path = save_report(args.manifest_out, report)
            print(f"VERIFY passed={report['result']['passed']}")
            print(f"MANIFEST: {out_path}")
            return 0 if report["result"]["passed"] else 1

        if args.command == "execute":
            assert_execute_guards(
                confirm_phrase=args.confirm_phrase,
                confirm_database_name=args.confirm_database_name,
                expected_database_name=args.expected_database_name,
                backup_path=args.backup_path,
                backup_acknowledged=bool(args.backup_acknowledged),
            )
            run_execute(
                engine,
                allowlist,
                db_identity,
                manifest_out=args.manifest_out,
                before_manifest_path=args.before_manifest,
                backup_path=args.backup_path,
            )
            return 0

        raise SafetyAbort(f"Unknown command: {args.command}")
    except SafetyAbort as exc:
        print(f"ABORT: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
