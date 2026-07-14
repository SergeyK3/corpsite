#!/usr/bin/env python3
"""Read-only PostgreSQL FK dependency graph builder for local/dev cleanup planning.

Inspects catalog metadata only — no DDL or DML.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

TOOLKIT_DIR = Path(__file__).resolve().parent

ALLOWLIST_TABLE_MAP: dict[str, tuple[str, str]] = {
    "persons": ("persons", "person_id"),
    "employees": ("employees", "employee_id"),
    "users": ("users", "user_id"),
    "positions": ("positions", "position_id"),
    "units": ("org_units", "unit_id"),
    "assignments": ("person_assignments", "assignment_id"),
    "identities": ("employee_identities", "identity_id"),
    "batches": ("hr_import_batches", "batch_id"),
    "snapshots": ("hr_canonical_snapshots", "snapshot_id"),
    "reconciliation_items": ("identity_reconciliation_items", "item_id"),
    "reconciliation_runs": ("identity_reconciliation_runs", "run_id"),
    "roles": ("roles", "role_id"),
    "audit": ("security_audit_log", "audit_id"),
}

RUNNER_TABLES = frozenset(
    {
        "security_audit_log",
        "identity_reconciliation_items",
        "identity_reconciliation_runs",
        "hr_snapshot_effective_entries",
        "hr_canonical_snapshot_entries",
        "hr_canonical_snapshots",
        "hr_import_batches",
        "employee_identities",
        "person_assignments",
        "access_grants",
        "personnel_visibility_assignments",
        "users",
        "employees",
        "persons",
        "permission_template",
        "position_cabinet",
        "legacy_position_mapping",
        "org_unique_position",
        "positions",
        "org_units",
        "roles",
    }
)

LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
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
BLOCKED_DATABASE_NAMES = frozenset(
    {
        "prod",
        "production",
        "live",
        "master",
        "primary",
        "replica",
    }
)


class SafetyAbort(Exception):
    """Fatal safety violation — stop without side effects."""


def resolve_database_url(cli_url: str | None) -> str:
    import os

    raw = (cli_url or os.getenv("DATABASE_URL") or "").strip()
    if not raw:
        raise SafetyAbort(
            "Database URL is required. Set DATABASE_URL or pass --database-url."
        )
    return raw.replace("postgresql+psycopg2://", "postgresql://", 1)


def redact_database_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    port = parsed.port or 5432
    database = (parsed.path or "").lstrip("/")
    user = parsed.username or ""
    return f"postgresql://{user}@{host}:{port}/{database}"


def assert_local_dev_database(url: str, *, expected_database_name: str) -> dict[str, Any]:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    database = (parsed.path or "").lstrip("/")
    lowered = url.lower()

    if host not in LOCAL_HOSTS:
        raise SafetyAbort(
            f"BLOCKED: host {host!r} is not classified as local/dev. "
            "Only 127.0.0.1, localhost, and ::1 are permitted."
        )

    for marker in BLOCKED_URL_MARKERS:
        if marker in lowered:
            raise SafetyAbort(
                f"BLOCKED: database URL contains production-like marker {marker!r}."
            )

    if not expected_database_name.strip():
        raise SafetyAbort(
            "BLOCKED: --expected-database-name is required to classify the target database."
        )

    if database != expected_database_name.strip():
        raise SafetyAbort(
            f"BLOCKED: connected database {database!r} does not match "
            f"expected {expected_database_name.strip()!r}."
        )

    if database.lower() in BLOCKED_DATABASE_NAMES:
        raise SafetyAbort(
            f"BLOCKED: database name {database!r} looks production-like."
        )

    return {
        "host": host,
        "port": parsed.port,
        "database": database,
        "user": parsed.username,
        "url_redacted": redact_database_url(url),
        "classification": "local/dev",
    }


def assert_external_path(path: Path, *, label: str) -> Path:
    resolved = path.expanduser().resolve()
    toolkit = TOOLKIT_DIR.resolve()
    if resolved == toolkit or toolkit in resolved.parents:
        raise SafetyAbort(
            f"{label} must be outside the toolkit directory ({toolkit})."
        )
    return resolved


def load_allowlist(path: Path) -> dict[str, Any]:
    external = assert_external_path(path, label="Allowlist")
    if not external.is_file():
        raise SafetyAbort(f"Allowlist not found: {external}")
    with external.open(encoding="utf-8") as fh:
        data = json.load(fh)
    required_sections = (
        "persons",
        "employees",
        "users",
        "units",
        "assignments",
        "positions",
        "identities",
        "batches",
        "snapshots",
        "audit",
        "roles",
        "protected",
        "reconciliation",
    )
    for key in required_sections:
        if key not in data:
            raise SafetyAbort(f"Allowlist missing section: {key}")
    if "items" not in data["reconciliation"]:
        raise SafetyAbort("Allowlist missing reconciliation.items")
    return data


def allowlist_ids_by_table(allowlist: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for section, (table, pk) in ALLOWLIST_TABLE_MAP.items():
        if section == "reconciliation_items":
            items = allowlist["reconciliation"]["items"]
        elif section == "reconciliation_runs":
            items = allowlist["reconciliation"]["runs"]
        elif section == "units":
            items = allowlist["units"]
        else:
            items = allowlist[section]
        ids = [int(x["id"]) for x in items]
        labels = {int(x["id"]): str(x.get("label", x["id"])) for x in items}
        out[table] = {"section": section, "pk": pk, "ids": ids, "labels": labels}
    return out


def fetch_fk_catalog(conn: Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT
                con.conname AS constraint_name,
                child_ns.nspname AS child_schema,
                child.relname AS child_table,
                parent.relname AS parent_table,
                child_att.attname AS child_column,
                parent_att.attname AS parent_column,
                CASE con.confdeltype
                    WHEN 'a' THEN 'NO ACTION'
                    WHEN 'r' THEN 'RESTRICT'
                    WHEN 'c' THEN 'CASCADE'
                    WHEN 'n' THEN 'SET NULL'
                    WHEN 'd' THEN 'SET DEFAULT'
                END AS delete_rule,
                CASE con.confupdtype
                    WHEN 'a' THEN 'NO ACTION'
                    WHEN 'r' THEN 'RESTRICT'
                    WHEN 'c' THEN 'CASCADE'
                    WHEN 'n' THEN 'SET NULL'
                    WHEN 'd' THEN 'SET DEFAULT'
                END AS update_rule,
                con.condeferrable AS deferrable,
                con.condeferred AS deferred
            FROM pg_constraint con
            JOIN pg_class child ON child.oid = con.conrelid
            JOIN pg_class parent ON parent.oid = con.confrelid
            JOIN pg_namespace child_ns ON child_ns.oid = child.relnamespace
            JOIN pg_namespace parent_ns ON parent_ns.oid = parent.relnamespace
            JOIN pg_attribute child_att
              ON child_att.attrelid = child.oid
             AND child_att.attnum = ANY (con.conkey)
            JOIN pg_attribute parent_att
              ON parent_att.attrelid = parent.oid
             AND parent_att.attnum = ANY (con.confkey)
            WHERE con.contype = 'f'
              AND child_ns.nspname = 'public'
              AND parent_ns.nspname = 'public'
            ORDER BY child_table, parent_table, constraint_name
            """
        )
    ).mappings().all()
    return [dict(r) for r in rows]


def table_pk_column(conn: Connection, table: str) -> str | None:
    row = conn.execute(
        text(
            """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = 'public'
              AND tc.table_name = :t
              AND tc.constraint_type = 'PRIMARY KEY'
            ORDER BY kcu.ordinal_position
            LIMIT 1
            """
        ),
        {"t": table},
    ).scalar()
    return str(row) if row else None


def table_exists(conn: Connection, table: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = :t LIMIT 1
                """
            ),
            {"t": table},
        ).scalar()
    )


def count_refs(
    conn: Connection,
    child_table: str,
    child_column: str,
    parent_ids: list[int],
) -> tuple[int, list[dict[str, Any]]]:
    if not parent_ids or not table_exists(conn, child_table):
        return 0, []
    pk = table_pk_column(conn, child_table)
    if not pk:
        return 0, []
    count = int(
        conn.execute(
            text(
                f"SELECT COUNT(*) FROM public.{child_table} "
                f"WHERE {child_column} = ANY(:ids)"
            ),
            {"ids": parent_ids},
        ).scalar()
        or 0
    )
    if count == 0:
        return 0, []
    samples = [
        dict(r)
        for r in conn.execute(
            text(
                f"""
                SELECT {pk} AS pk_value, {child_column} AS ref_value
                FROM public.{child_table}
                WHERE {child_column} = ANY(:ids)
                ORDER BY {child_column}
                LIMIT 3
                """
            ),
            {"ids": parent_ids},
        ).mappings().all()
    ]
    return count, samples


def build_incoming_outgoing(
    fk_edges: list[dict[str, Any]],
    focus_tables: set[str],
) -> dict[str, Any]:
    incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in fk_edges:
        parent = edge["parent_table"]
        child = edge["child_table"]
        outgoing[parent].append(edge)
        incoming[child].append(edge)
    return {
        "focus_tables": sorted(focus_tables),
        "incoming": {t: incoming.get(t, []) for t in sorted(focus_tables)},
        "outgoing": {t: outgoing.get(t, []) for t in sorted(focus_tables)},
        "by_delete_rule": {
            rule: [e for e in fk_edges if e["delete_rule"] == rule]
            for rule in ("RESTRICT", "NO ACTION", "CASCADE", "SET NULL", "SET DEFAULT")
        },
    }


def expand_blocking_children(
    conn: Connection,
    fk_edges: list[dict[str, Any]],
    targets: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    queue: deque[tuple[str, str, list[int]]] = deque()
    for table, meta in targets.items():
        if meta["ids"]:
            queue.append((table, meta["pk"], meta["ids"]))

    while queue:
        parent_table, _parent_pk, parent_ids = queue.popleft()
        for edge in fk_edges:
            if edge["parent_table"] != parent_table:
                continue
            if edge["delete_rule"] in {"CASCADE", "SET NULL", "SET DEFAULT"}:
                continue
            key = (edge["child_table"], edge["child_column"], parent_table)
            if key in seen:
                continue
            seen.add(key)
            count, samples = count_refs(conn, edge["child_table"], edge["child_column"], parent_ids)
            if count == 0:
                continue
            child_pk = table_pk_column(conn, edge["child_table"])
            entry = {
                "child_table": edge["child_table"],
                "child_column": edge["child_column"],
                "parent_table": parent_table,
                "parent_column": edge["parent_column"],
                "constraint_name": edge["constraint_name"],
                "delete_rule": edge["delete_rule"],
                "blocking_count": count,
                "sample_refs": samples,
                "in_runner": edge["child_table"] in RUNNER_TABLES,
                "child_pk": child_pk,
            }
            blockers.append(entry)
            if child_pk and samples:
                child_ids = [int(s["pk_value"]) for s in samples if s.get("pk_value") is not None]
                if child_ids:
                    queue.append((edge["child_table"], child_pk, child_ids))

    blockers.sort(key=lambda x: (-x["blocking_count"], x["child_table"]))
    return blockers


def topological_delete_order(
    fk_edges: list[dict[str, Any]],
    tables_in_scope: set[str],
) -> dict[str, Any]:
    adj: dict[str, set[str]] = defaultdict(set)
    indegree: dict[str, int] = {t: 0 for t in tables_in_scope}
    for edge in fk_edges:
        child, parent = edge["child_table"], edge["parent_table"]
        if child not in tables_in_scope or parent not in tables_in_scope:
            continue
        if parent not in adj[child]:
            adj[child].add(parent)
            indegree[parent] = indegree.get(parent, 0) + 1
        indegree.setdefault(child, indegree.get(child, 0))

    queue = deque(sorted(t for t in tables_in_scope if indegree.get(t, 0) == 0))
    order: list[str] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for parent in sorted(adj.get(node, [])):
            indegree[parent] -= 1
            if indegree[parent] == 0:
                queue.append(parent)

    cyclic_nodes = [t for t in tables_in_scope if t not in order]
    cycle_edges: list[dict[str, Any]] = []
    if cyclic_nodes:
        cyclic_set = set(cyclic_nodes)
        for edge in fk_edges:
            if edge["child_table"] in cyclic_set and edge["parent_table"] in cyclic_set:
                cycle_edges.append(edge)

    return {
        "tables_in_scope": sorted(tables_in_scope),
        "delete_order": order,
        "cyclic_tables": sorted(cyclic_nodes),
        "cycle_edges": cycle_edges,
        "cycle_break_strategy": (
            "No table-only cycles detected in scope."
            if not cyclic_nodes
            else (
                "Break cycles by deleting conditional edges first (for example roles after users), "
                "or delete junction/child rows discovered via catalog before parents."
            )
        ),
    }


def trace_dependency_paths(
    fk_edges: list[dict[str, Any]],
    start_table: str,
    *,
    direction: str,
    max_depth: int = 8,
) -> list[list[str]]:
    if direction not in {"incoming", "outgoing"}:
        raise ValueError("direction must be incoming or outgoing")

    paths: list[list[str]] = []
    stack: list[tuple[str, list[str], set[str]]] = [(start_table, [start_table], {start_table})]

    while stack:
        table, path, visited = stack.pop()
        if len(path) > max_depth:
            continue
        neighbors: list[str] = []
        for edge in fk_edges:
            if direction == "incoming" and edge["child_table"] == table:
                neighbors.append(edge["parent_table"])
            elif direction == "outgoing" and edge["parent_table"] == table:
                neighbors.append(edge["child_table"])
        if not neighbors:
            if len(path) > 1:
                paths.append(path)
            continue
        extended = False
        for neighbor in sorted(set(neighbors)):
            if neighbor in visited:
                paths.append(path + [neighbor, "<cycle>"])
                continue
            extended = True
            stack.append((neighbor, path + [neighbor], visited | {neighbor}))
        if not extended and len(path) > 1:
            paths.append(path)

    return paths[:50]


def runner_phase_order() -> list[dict[str, Any]]:
    return [
        {"phase": "audit_chain", "tables": ["security_audit_log"]},
        {"phase": "reconciliation", "tables": ["identity_reconciliation_items", "identity_reconciliation_runs"]},
        {
            "phase": "hr_chain",
            "tables": [
                "hr_snapshot_effective_entries",
                "hr_canonical_snapshot_entries",
                "hr_canonical_snapshots",
                "hr_import_batches",
            ],
        },
        {"phase": "personnel", "tables": ["employee_identities", "person_assignments"]},
        {"phase": "access", "tables": ["access_grants", "personnel_visibility_assignments"]},
        {"phase": "users", "tables": ["users"]},
        {"phase": "personnel", "tables": ["employees", "persons"]},
        {
            "phase": "org_cabinet_chain",
            "tables": [
                "permission_template",
                "position_cabinet",
                "legacy_position_mapping",
                "org_unique_position",
            ],
        },
        {"phase": "org", "tables": ["positions", "org_units"]},
        {"phase": "roles_post_users", "tables": ["roles"]},
    ]


def compare_runner_vs_topo(
    topo_order: list[str],
    blockers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    runner_flat: list[str] = []
    for phase in runner_phase_order():
        runner_flat.extend(phase["tables"])
    missing_in_runner = sorted({b["child_table"] for b in blockers if not b["in_runner"]})
    for table in missing_in_runner:
        refs = [b for b in blockers if b["child_table"] == table]
        issues.append(
            {
                "table": table,
                "issue": "missing_from_runner",
                "blocking_count": sum(b["blocking_count"] for b in refs),
            }
        )
    for blocker in blockers:
        if blocker["in_runner"]:
            continue
        parent = blocker["parent_table"]
        if parent in runner_flat:
            issues.append(
                {
                    "table": blocker["child_table"],
                    "issue": "must_delete_before_parent",
                    "parent_table": parent,
                    "blocking_count": blocker["blocking_count"],
                }
            )
    return issues


def build_fk_graph_report(
    conn: Connection,
    allowlist: dict[str, Any],
    *,
    db_identity: dict[str, Any],
    focus_tables: list[str] | None = None,
) -> dict[str, Any]:
    targets = allowlist_ids_by_table(allowlist)
    allowlist_tables = set(targets.keys())
    if focus_tables:
        focus = {t for t in focus_tables if t in allowlist_tables or table_exists(conn, t)}
    else:
        focus = allowlist_tables

    fk_edges = fetch_fk_catalog(conn)
    graph = build_incoming_outgoing(fk_edges, focus)
    blockers = expand_blocking_children(conn, fk_edges, targets)
    scope_tables = allowlist_tables | {b["child_table"] for b in blockers}
    topo = topological_delete_order(fk_edges, scope_tables)
    runner_issues = compare_runner_vs_topo(topo["delete_order"], blockers)
    missing_tables = sorted({b["child_table"] for b in blockers if not b["in_runner"]})

    paths: dict[str, Any] = {}
    for table in sorted(focus):
        paths[table] = {
            "incoming_paths": trace_dependency_paths(fk_edges, table, direction="incoming"),
            "outgoing_paths": trace_dependency_paths(fk_edges, table, direction="outgoing"),
        }

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "fk-graph",
        "database": db_identity,
        "allowlist_targets": {
            k: {"pk": v["pk"], "id_count": len(v["ids"])} for k, v in targets.items()
        },
        "fk_edge_count": len(fk_edges),
        "fk_graph": graph,
        "dependency_paths": paths,
        "blocking_children": blockers,
        "missing_tables": missing_tables,
        "topological_delete_order": topo,
        "runner_phase_order": runner_phase_order(),
        "runner_issues": runner_issues,
        "summary": {
            "blocking_child_tables": len(blockers),
            "missing_from_runner": len(missing_tables),
            "has_cycles": bool(topo["cyclic_tables"]),
            "execute_ready": len(blockers) == 0 or all(b["in_runner"] for b in blockers),
        },
    }


def create_engine_from_guard(url: str, *, expected_database_name: str) -> tuple[Engine, dict[str, Any]]:
    identity = assert_local_dev_database(url, expected_database_name=expected_database_name)
    engine = create_engine(url, pool_pre_ping=True)
    return engine, identity


def save_report(path: Path, payload: dict[str, Any]) -> Path:
    external = assert_external_path(path, label="Report/manifest output")
    external.parent.mkdir(parents=True, exist_ok=True)
    with external.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, default=str)
    return external


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only FK dependency graph for local/dev cleanup planning."
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="PostgreSQL URL (otherwise DATABASE_URL environment variable).",
    )
    parser.add_argument(
        "--expected-database-name",
        required=True,
        help="Expected target database name (must match the connected database).",
    )
    parser.add_argument(
        "--allowlist",
        type=Path,
        required=True,
        help="Path to external cleanup allowlist JSON (outside this toolkit directory).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path for FK graph JSON report (outside this toolkit directory).",
    )
    parser.add_argument(
        "--tables",
        nargs="*",
        default=None,
        help="Optional subset of tables to focus on (defaults to allowlist tables).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        url = resolve_database_url(args.database_url)
        allowlist = load_allowlist(args.allowlist)
        engine, identity = create_engine_from_guard(
            url, expected_database_name=args.expected_database_name
        )
        with engine.connect() as conn:
            report = build_fk_graph_report(
                conn,
                allowlist,
                db_identity=identity,
                focus_tables=args.tables,
            )
        out_path = save_report(args.output, report)
    except SafetyAbort as exc:
        print(f"ABORT: {exc}", file=sys.stderr)
        return 2

    print(f"DATABASE: {identity['url_redacted']}")
    print(f"FK edges: {report['fk_edge_count']}")
    print(f"Blocking child tables: {report['summary']['blocking_child_tables']}")
    print(f"Missing from runner: {report['summary']['missing_from_runner']}")
    print(f"Cycles: {report['topological_delete_order']['cyclic_tables']}")
    print(f"REPORT: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
