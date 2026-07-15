#!/usr/bin/env python3
"""Positions and org-unit allowed-positions cleanup domain for local/dev toolkit."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from personnel_cleanup_fk_graph import SafetyAbort, save_report, table_exists

POSITION_MASKS: list[tuple[str, str]] = [
    ("pytest_bind", "name ILIKE 'pytest_bind_%'"),
    ("pilot_hire", "name ILIKE 'PILOT hire %'"),
    ("pilot_transfer", "name ILIKE 'PILOT transfer %'"),
    ("probe_allowed", "name IN ('ProbeAllowedA','ProbeAllowedB','ProbeAllowedC')"),
    ("pytest_other", "name ILIKE 'pytest%' AND name NOT ILIKE 'pytest_bind_%'"),
    (
        "pilot_other",
        "(name ILIKE 'PILOT %' OR name ILIKE 'pilot_%') "
        "AND name NOT ILIKE 'PILOT hire %' AND name NOT ILIKE 'PILOT transfer %'",
    ),
    (
        "probe_other",
        "name ILIKE 'Probe%' AND name NOT IN ('ProbeAllowedA','ProbeAllowedB','ProbeAllowedC')",
    ),
    ("e1_test", "name ILIKE 'e1_%' OR name ILIKE 'E1 %'"),
]

HR_ETALON_POSITION_NAMES = [
    "Руководитель отдела кадров",
    "Менеджер УЧР",
    "Менеджер",
    "секретарь-референт",
    "Переводчик казахского языка",
]

PROTECTED_POSITION_IDS = frozenset({1})
HR_ALLOWED_ORG_UNIT_ID = 73

# Blocked positions expected to remain after positions-only execute.
# Missing entries from this set (when listed in before_manifest) fail verify.
BLOCKED_UNEXPECTED_MISSING_POLICY = "fail"


def _column_exists(conn: Connection, table: str, column: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table
                  AND column_name = :column
                LIMIT 1
                """
            ),
            {"table": table, "column": column},
        ).scalar()
    )


def position_dependency_counts(conn: Connection, position_id: int) -> dict[str, int | None]:
    params = {"position_id": position_id}
    checks: dict[str, str] = {
        "employees": "SELECT COUNT(*) FROM public.employees WHERE position_id = :position_id",
        "person_assignments": (
            "SELECT COUNT(*) FROM public.person_assignments WHERE position_id = :position_id"
        ),
        "employee_events_from": (
            "SELECT COUNT(*) FROM public.employee_events WHERE from_position_id = :position_id"
        ),
        "employee_events_to": (
            "SELECT COUNT(*) FROM public.employee_events WHERE to_position_id = :position_id"
        ),
        "org_unit_allowed_positions": (
            "SELECT COUNT(*) FROM public.org_unit_allowed_positions WHERE position_id = :position_id"
        ),
    }
    out: dict[str, int | None] = {}
    for key, sql in checks.items():
        if key == "org_unit_allowed_positions" and not table_exists(conn, "org_unit_allowed_positions"):
            out[key] = None
            continue
        out[key] = int(conn.execute(text(sql), params).scalar() or 0)

    if table_exists(conn, "personnel_order_items"):
        out["personnel_order_items_payload"] = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM public.personnel_order_items poi
                    WHERE poi.payload::text LIKE '%"position_id": ' || CAST(:position_id AS text) || '%'
                       OR poi.payload::text LIKE '%"to_position_id": ' || CAST(:position_id AS text) || '%'
                       OR poi.payload::text LIKE '%"from_position_id": ' || CAST(:position_id AS text) || '%'
                    """
                ),
                params,
            ).scalar()
            or 0
        )

    for tbl, col in (
        ("org_unique_position", "catalog_position_id"),
        ("legacy_position_mapping", "catalog_position_id"),
        ("position_cabinet", "catalog_position_id"),
    ):
        if not table_exists(conn, tbl) or not _column_exists(conn, tbl, col):
            continue
        out[tbl] = int(
            conn.execute(
                text(f"SELECT COUNT(*) FROM public.{tbl} WHERE {col} = :position_id"),
                params,
            ).scalar()
            or 0
        )
    return out


def _total_ref_count(deps: dict[str, int | None]) -> int:
    return sum(v for v in deps.values() if isinstance(v, int))


def _blocked_reasons(position_id: int, deps: dict[str, int | None]) -> list[str]:
    if position_id in PROTECTED_POSITION_IDS:
        return ["protected position_id=1 (Архивариус) — never delete"]
    reasons: list[str] = []
    for key, value in deps.items():
        if isinstance(value, int) and value > 0:
            reasons.append(f"{key}={value}")
    return reasons


def discover_test_position_candidates(conn: Connection) -> dict[str, Any]:
    by_mask: dict[str, Any] = {}
    all_ids: set[int] = set()
    for label, where in POSITION_MASKS:
        rows = conn.execute(
            text(
                f"SELECT position_id, name, category FROM public.positions WHERE {where} "
                "ORDER BY position_id"
            )
        ).mappings().all()
        by_mask[label] = {"count": len(rows), "items": [dict(r) for r in rows]}
        all_ids.update(int(r["position_id"]) for r in rows)

    matrix = []
    deletable: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for pid in sorted(all_ids):
        row = conn.execute(
            text("SELECT position_id, name, category FROM public.positions WHERE position_id = :id"),
            {"id": pid},
        ).mappings().first()
        deps = position_dependency_counts(conn, pid)
        total = _total_ref_count(deps)
        item = {
            "position_id": pid,
            "name": row["name"],
            "category": row["category"],
            "dependencies": deps,
            "total_ref_count": total,
            "deletable": total == 0 and pid not in PROTECTED_POSITION_IDS,
            "blocked_reasons": _blocked_reasons(pid, deps),
        }
        matrix.append(item)
        if item["deletable"]:
            deletable.append(item)
        elif pid not in PROTECTED_POSITION_IDS:
            blocked.append(item)

    return {
        "candidates_by_mask": by_mask,
        "candidate_ids_total": len(all_ids),
        "candidate_dependency_matrix": matrix,
        "deletable_candidates": deletable,
        "blocked_candidates": blocked,
        "protected_position_ids": sorted(PROTECTED_POSITION_IDS),
        "archivist_position_id_1": {
            "name": "Архивариус",
            "dependencies": position_dependency_counts(conn, 1),
            "delete_policy": "NEVER DELETE position_id=1",
        },
    }


def audit_allowed_positions_for_unit(conn: Connection, org_unit_id: int) -> dict[str, Any]:
    if not table_exists(conn, "org_unit_allowed_positions"):
        raise SafetyAbort("org_unit_allowed_positions table is missing")

    links = [
        dict(r)
        for r in conn.execute(
            text(
                """
                SELECT ouap.org_unit_allowed_position_id AS link_id,
                       ouap.org_unit_id,
                       ou.name AS org_unit_name,
                       ouap.position_id,
                       p.name AS position_name,
                       ouap.sort_order,
                       ouap.is_active
                FROM public.org_unit_allowed_positions ouap
                JOIN public.positions p ON p.position_id = ouap.position_id
                JOIN public.org_units ou ON ou.unit_id = ouap.org_unit_id
                WHERE ouap.org_unit_id = :org_unit_id
                ORDER BY ouap.sort_order, p.name, ouap.org_unit_allowed_position_id
                """
            ),
            {"org_unit_id": int(org_unit_id)},
        ).mappings().all()
    ]

    etalon_rows = []
    etalon_ids: set[int] = set()
    for title in HR_ETALON_POSITION_NAMES:
        found = conn.execute(
            text(
                "SELECT position_id, name FROM public.positions "
                "WHERE lower(trim(name)) = lower(trim(:name))"
            ),
            {"name": title},
        ).mappings().first()
        row = {"expected_name": title, "found": dict(found) if found else None}
        etalon_rows.append(row)
        if found:
            etalon_ids.add(int(found["position_id"]))

    link_ids = {int(r["position_id"]) for r in links}
    extra_position_ids = sorted(link_ids - etalon_ids)
    missing_etalon_ids = sorted(etalon_ids - link_ids)

    extra_links = [r for r in links if int(r["position_id"]) in extra_position_ids]
    etalon_links = [r for r in links if int(r["position_id"]) in etalon_ids]

    employees = [
        dict(r)
        for r in conn.execute(
            text(
                """
                SELECT e.employee_id, e.full_name, e.position_id, p.name AS position_name
                FROM public.employees e
                JOIN public.positions p ON p.position_id = e.position_id
                WHERE e.org_unit_id = :org_unit_id
                ORDER BY e.position_id, e.employee_id
                """
            ),
            {"org_unit_id": int(org_unit_id)},
        ).mappings().all()
    ]

    proposed_link_deletes = []
    for link in extra_links:
        proposed_link_deletes.append(
            {
                "link_id": int(link["link_id"]),
                "position_id": int(link["position_id"]),
                "position_name": link["position_name"],
                "safe_to_delete_link": True,
                "note": (
                    "Deleting allowed-link only; does not change employees.position_id. "
                    "Архивариус remains in used-mode while employee_id=152 keeps position_id=1."
                    if int(link["position_id"]) == 1
                    else "Deleting probe/test allowed-link."
                ),
            }
        )

    return {
        "org_unit_id": int(org_unit_id),
        "allowed_links": links,
        "etalon_position_names": HR_ETALON_POSITION_NAMES,
        "etalon_positions": etalon_rows,
        "etalon_links": etalon_links,
        "extra_allowed_links": extra_links,
        "extra_allowed_link_position_ids": extra_position_ids,
        "missing_etalon_in_allowed": missing_etalon_ids,
        "employees_in_unit": employees,
        "proposed_link_deletes": proposed_link_deletes,
    }


def _verify_link_signatures(conn: Connection, allowlist: dict[str, Any]) -> list[dict[str, Any]]:
    items = allowlist.get("org_unit_allowed_position_links") or []
    if not items:
        raise SafetyAbort("allowlist.org_unit_allowed_position_links is required for execute")
    verified: list[dict[str, Any]] = []
    for item in items:
        link_id = int(item["id"])
        expected = item["expected_signature"]
        row = conn.execute(
            text(
                """
                SELECT ouap.org_unit_allowed_position_id AS link_id,
                       ouap.org_unit_id,
                       ouap.position_id,
                       p.name AS position_name
                FROM public.org_unit_allowed_positions ouap
                JOIN public.positions p ON p.position_id = ouap.position_id
                WHERE ouap.org_unit_allowed_position_id = :link_id
                """
            ),
            {"link_id": link_id},
        ).mappings().first()
        if row is None:
            raise SafetyAbort(f"allowed-link id={link_id} missing in database")
        for field, expected_value in expected.items():
            actual = row.get(field)
            if str(actual).strip() != str(expected_value).strip():
                raise SafetyAbort(
                    f"allowed-link id={link_id} signature mismatch on {field!r}: "
                    f"expected {expected_value!r}, got {actual!r}"
                )
        verified.append(dict(row))
    return verified


def _verify_position_signatures(conn: Connection, allowlist: dict[str, Any]) -> list[dict[str, Any]]:
    items = allowlist.get("positions") or []
    if not items:
        raise SafetyAbort("allowlist.positions is required for positions execute")
    verified: list[dict[str, Any]] = []
    for item in items:
        pid = int(item["id"])
        if pid in PROTECTED_POSITION_IDS:
            raise SafetyAbort(f"ABORT: position_id={pid} is protected and cannot be deleted")
        expected = item["expected_signature"]
        row = conn.execute(
            text("SELECT position_id, name, category FROM public.positions WHERE position_id = :id"),
            {"id": pid},
        ).mappings().first()
        if row is None:
            raise SafetyAbort(f"position id={pid} missing in database")
        for field, expected_value in expected.items():
            actual = row.get(field)
            if str(actual).strip() != str(expected_value).strip():
                raise SafetyAbort(
                    f"position id={pid} signature mismatch on {field!r}: "
                    f"expected {expected_value!r}, got {actual!r}"
                )
        deps = position_dependency_counts(conn, pid)
        if _total_ref_count(deps) > 0:
            raise SafetyAbort(
                f"ABORT: position id={pid} blocked by dependencies: "
                + ", ".join(_blocked_reasons(pid, deps))
            )
        verified.append({**dict(row), "dependencies": deps})
    return verified


def _normalize_signature_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def compute_allowlist_hash(allowlist: dict[str, Any]) -> str:
    payload = {
        "positions": allowlist.get("positions") or [],
        "protected_positions": (allowlist.get("protected") or {}).get("positions") or [],
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_positions_verify_allowlist(allowlist: dict[str, Any]) -> dict[str, Any]:
    """Validate allowlist schema for positions verify. Raises SafetyAbort on fatal issues."""
    if "positions" not in allowlist:
        raise SafetyAbort("allowlist.positions section is required for domain=positions verify")
    positions = allowlist.get("positions") or []
    if not positions:
        raise SafetyAbort(
            "allowlist.positions must contain at least one entry for domain=positions verify"
        )

    seen_ids: set[int] = set()
    for item in positions:
        if "id" not in item:
            raise SafetyAbort("allowlist.positions entry missing required field: id")
        if "expected_signature" not in item:
            raise SafetyAbort(f"allowlist.positions id={item['id']} missing expected_signature")
        pid = int(item["id"])
        if pid in seen_ids:
            raise SafetyAbort(f"allowlist.positions duplicate id={pid}")
        seen_ids.add(pid)
        if pid in PROTECTED_POSITION_IDS:
            raise SafetyAbort(f"allowlist.positions id={pid} overlaps protected position IDs")

    protected = allowlist.get("protected") or {}
    for item in protected.get("positions") or []:
        if "id" not in item or "expected_signature" not in item:
            raise SafetyAbort("protected.positions entry requires id and expected_signature")
        pid = int(item["id"])
        if pid in seen_ids:
            raise SafetyAbort(f"protected.positions id={pid} overlaps delete allowlist")

    return {
        "positions_count": len(positions),
        "position_ids": sorted(seen_ids),
        "protected_positions_count": len(protected.get("positions") or []),
    }


def _extract_blocked_from_manifest(before_manifest: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not before_manifest:
        return []
    blocked = before_manifest.get("blocked_candidates")
    if isinstance(blocked, list):
        return blocked
    return []


def _extract_deleted_from_execute_manifest(
    before_manifest: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not before_manifest:
        return []
    if before_manifest.get("mode") == "execute" and before_manifest.get("domain") == "positions":
        return before_manifest.get("deleted_positions") or []
    return []


def verify_allowlisted_positions_removed(
    conn: Connection,
    allowlist: dict[str, Any],
) -> dict[str, Any]:
    items = allowlist.get("positions") or []
    checked_ids = [int(x["id"]) for x in items]
    remaining: list[dict[str, Any]] = []
    id_reuse_failures: list[dict[str, Any]] = []

    for item in items:
        pid = int(item["id"])
        expected = item["expected_signature"]
        row = conn.execute(
            text("SELECT position_id, name, category FROM public.positions WHERE position_id = :id"),
            {"id": pid},
        ).mappings().first()
        if row is None:
            continue
        actual_name = _normalize_signature_value(row["name"])
        expected_name = _normalize_signature_value(expected.get("name"))
        if actual_name != expected_name:
            id_reuse_failures.append(
                {
                    "position_id": pid,
                    "expected_name": expected_name,
                    "actual_name": actual_name,
                    "reason": "ID reused by different position name",
                }
            )
        remaining.append(dict(row))

    return {
        "checked_ids": checked_ids,
        "remaining_count": len(remaining),
        "remaining": remaining,
        "id_reuse_failures": id_reuse_failures,
        "passed": len(remaining) == 0 and len(id_reuse_failures) == 0,
    }


def verify_protected_position_entities(
    conn: Connection,
    allowlist: dict[str, Any],
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    failures: list[str] = []

    for pid in sorted(PROTECTED_POSITION_IDS):
        row = conn.execute(
            text("SELECT position_id, name, category FROM public.positions WHERE position_id = :id"),
            {"id": pid},
        ).mappings().first()
        status = "present" if row else "missing"
        entry = {
            "position_id": pid,
            "label": "built-in protected",
            "status": status,
            "actual": dict(row) if row else None,
        }
        if status != "present":
            failures.append(f"protected position_id={pid} missing")
        results.append(entry)

    for item in (allowlist.get("protected") or {}).get("positions") or []:
        pid = int(item["id"])
        expected = item["expected_signature"]
        row = conn.execute(
            text("SELECT position_id, name, category FROM public.positions WHERE position_id = :id"),
            {"id": pid},
        ).mappings().first()
        if row is None:
            results.append(
                {
                    "position_id": pid,
                    "label": item.get("label", str(pid)),
                    "status": "missing",
                    "expected_signature": expected,
                    "actual": None,
                }
            )
            failures.append(f"protected.positions id={pid} missing")
            continue
        mismatches: list[str] = []
        for field, expected_value in expected.items():
            actual = row.get(field)
            if _normalize_signature_value(actual) != _normalize_signature_value(expected_value):
                mismatches.append(field)
        status = "present" if not mismatches else "signature_mismatch"
        if mismatches:
            failures.append(f"protected.positions id={pid} signature mismatch: {mismatches}")
        results.append(
            {
                "position_id": pid,
                "label": item.get("label", str(pid)),
                "status": status,
                "expected_signature": expected,
                "actual": dict(row),
                "mismatched_fields": mismatches,
            }
        )

    return {
        "results": results,
        "passed": len(failures) == 0,
        "failures": failures,
    }


def verify_blocked_position_entities(
    conn: Connection,
    *,
    before_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    expected_blocked = _extract_blocked_from_manifest(before_manifest)
    expected_ids = {int(x["position_id"]) for x in expected_blocked}
    results: list[dict[str, Any]] = []
    failures: list[str] = []
    warnings: list[str] = []

    for item in expected_blocked:
        pid = int(item["position_id"])
        expected_name = item.get("name")
        row = conn.execute(
            text("SELECT position_id, name, category FROM public.positions WHERE position_id = :id"),
            {"id": pid},
        ).mappings().first()
        if row is None:
            msg = f"blocked position_id={pid} ({expected_name}) unexpectedly missing"
            if BLOCKED_UNEXPECTED_MISSING_POLICY == "fail":
                failures.append(msg)
            else:
                warnings.append(msg)
            results.append(
                {
                    "position_id": pid,
                    "expected_name": expected_name,
                    "status": "missing",
                    "policy": BLOCKED_UNEXPECTED_MISSING_POLICY,
                }
            )
            continue
        deps = position_dependency_counts(conn, pid)
        results.append(
            {
                "position_id": pid,
                "expected_name": expected_name,
                "status": "present",
                "actual": dict(row),
                "dependencies": deps,
                "still_blocked": _total_ref_count(deps) > 0,
            }
        )

    return {
        "expected_blocked_ids": sorted(expected_ids),
        "results": results,
        "passed": len(failures) == 0,
        "failures": failures,
        "warnings": warnings,
    }


def verify_etalon_hr_positions(conn: Connection) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    failures: list[str] = []
    for title in HR_ETALON_POSITION_NAMES:
        row = conn.execute(
            text(
                "SELECT position_id, name, category FROM public.positions "
                "WHERE lower(trim(name)) = lower(trim(:name))"
            ),
            {"name": title},
        ).mappings().first()
        status = "present" if row else "missing"
        if status != "present":
            failures.append(f"etalon HR position missing: {title!r}")
        results.append({"expected_name": title, "status": status, "found": dict(row) if row else None})
    return {"results": results, "passed": len(failures) == 0, "failures": failures}


def verify_hr_allowed_etalon_links(
    conn: Connection,
    *,
    org_unit_id: int = HR_ALLOWED_ORG_UNIT_ID,
) -> dict[str, Any]:
    if not table_exists(conn, "org_unit_allowed_positions"):
        return {
            "status": "skipped",
            "reason": "org_unit_allowed_positions table absent",
            "passed": True,
        }
    audit = audit_allowed_positions_for_unit(conn, org_unit_id)
    extra = audit["extra_allowed_links"]
    missing = audit["missing_etalon_in_allowed"]
    failures: list[str] = []
    if extra:
        failures.append(f"extra allowed links for org_unit_id={org_unit_id}: {len(extra)}")
    if missing:
        failures.append(f"missing etalon positions in allowed links: {missing}")
    return {
        "status": "checked",
        "org_unit_id": org_unit_id,
        "allowed_links_count": len(audit["allowed_links"]),
        "etalon_links_count": len(audit["etalon_links"]),
        "extra_allowed_links": extra,
        "missing_etalon_in_allowed": missing,
        "passed": len(failures) == 0,
        "failures": failures,
    }


def verify_no_remaining_deletable_test_candidates(conn: Connection) -> dict[str, Any]:
    audit = discover_test_position_candidates(conn)
    deletable = audit["deletable_candidates"]
    failures: list[str] = []
    if deletable:
        failures.append(f"deletable test candidates remain: {len(deletable)}")
    return {
        "deletable_count": len(deletable),
        "deletable_candidates": deletable,
        "blocked_count": len(audit["blocked_candidates"]),
        "passed": len(deletable) == 0,
        "failures": failures,
    }


def verify_deleted_positions_fk_integrity(
    conn: Connection,
    allowlist: dict[str, Any],
) -> dict[str, Any]:
    deleted_ids = [int(x["id"]) for x in allowlist.get("positions") or []]
    if not deleted_ids:
        return {"checked_ids": [], "dangling_references": [], "passed": True}

    dangling: list[dict[str, Any]] = []
    fk_checks: list[tuple[str, str, str]] = [
        ("employees", "position_id", "employee_id"),
        ("person_assignments", "position_id", "assignment_id"),
        ("employee_events", "from_position_id", "event_id"),
        ("employee_events", "to_position_id", "event_id"),
    ]
    if table_exists(conn, "org_unit_allowed_positions"):
        fk_checks.append(
            ("org_unit_allowed_positions", "position_id", "org_unit_allowed_position_id")
        )

    for table, col, pk in fk_checks:
        if not table_exists(conn, table):
            continue
        rows = conn.execute(
            text(
                f"SELECT {pk} AS ref_id, {col} AS position_id "
                f"FROM public.{table} WHERE {col} = ANY(:ids) ORDER BY {pk}"
            ),
            {"ids": deleted_ids},
        ).mappings().all()
        for row in rows:
            dangling.append(
                {
                    "table": table,
                    "column": col,
                    "ref_id": int(row["ref_id"]),
                    "position_id": int(row["position_id"]),
                }
            )

    payload_dangling: list[dict[str, Any]] = []
    if table_exists(conn, "personnel_order_items"):
        for pid in deleted_ids:
            count = int(
                conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM public.personnel_order_items poi
                        WHERE poi.payload::text LIKE '%"position_id": ' || CAST(:pid AS text) || '%'
                           OR poi.payload::text LIKE '%"to_position_id": ' || CAST(:pid AS text) || '%'
                           OR poi.payload::text LIKE '%"from_position_id": ' || CAST(:pid AS text) || '%'
                        """
                    ),
                    {"pid": pid},
                ).scalar()
                or 0
            )
            if count:
                payload_dangling.append({"position_id": pid, "personnel_order_items_payload_refs": count})

    failures: list[str] = []
    if dangling:
        failures.append(f"FK dangling references to deleted positions: {len(dangling)}")
    if payload_dangling:
        failures.append(f"payload references to deleted positions: {len(payload_dangling)}")

    return {
        "checked_ids": deleted_ids,
        "dangling_references": dangling,
        "payload_references": payload_dangling,
        "passed": len(failures) == 0,
        "failures": failures,
    }


def verify_execute_manifest_consistency(
    allowlist: dict[str, Any],
    *,
    before_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    allowlist_ids = {int(x["id"]) for x in allowlist.get("positions") or []}
    deleted_rows = _extract_deleted_from_execute_manifest(before_manifest)
    if not deleted_rows:
        return {
            "status": "skipped",
            "reason": "before_manifest is not a positions execute manifest",
            "passed": True,
        }

    deleted_ids = {int(x["position_id"]) for x in deleted_rows}
    missing_from_manifest = sorted(allowlist_ids - deleted_ids)
    extra_in_manifest = sorted(deleted_ids - allowlist_ids)
    failures: list[str] = []
    if missing_from_manifest:
        failures.append(f"allowlist IDs missing from execute manifest: {missing_from_manifest[:20]}")
    if extra_in_manifest:
        failures.append(f"execute manifest IDs not in allowlist: {extra_in_manifest[:20]}")
    if len(deleted_rows) != len(allowlist.get("positions") or []):
        failures.append(
            f"delete count mismatch: execute={len(deleted_rows)} allowlist={len(allowlist.get('positions') or [])}"
        )

    return {
        "status": "checked",
        "allowlist_count": len(allowlist_ids),
        "execute_deleted_count": len(deleted_rows),
        "missing_from_manifest": missing_from_manifest,
        "extra_in_manifest": extra_in_manifest,
        "passed": len(failures) == 0,
        "failures": failures,
    }


def build_positions_verify_report(
    conn: Connection,
    allowlist: dict[str, Any],
    db_identity: dict[str, Any],
    *,
    before_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    schema_info = validate_positions_verify_allowlist(allowlist)
    allowlist_hash = compute_allowlist_hash(allowlist)

    checks = {
        "allowlisted_positions_removed": verify_allowlisted_positions_removed(conn, allowlist),
        "protected_positions": verify_protected_position_entities(conn, allowlist),
        "blocked_positions": verify_blocked_position_entities(
            conn, before_manifest=before_manifest
        ),
        "etalon_hr_positions": verify_etalon_hr_positions(conn),
        "hr_allowed_etalon_links": verify_hr_allowed_etalon_links(conn),
        "no_deletable_test_candidates": verify_no_remaining_deletable_test_candidates(conn),
        "fk_integrity_deleted_positions": verify_deleted_positions_fk_integrity(conn, allowlist),
        "execute_manifest_consistency": verify_execute_manifest_consistency(
            allowlist, before_manifest=before_manifest
        ),
    }

    failures: list[str] = []
    warnings: list[str] = []
    skipped: list[str] = []

    for name, result in checks.items():
        if result.get("status") == "skipped":
            skipped.append(f"{name}: {result.get('reason', 'skipped')}")
            continue
        for msg in result.get("failures") or []:
            failures.append(f"{name}: {msg}")
        for msg in result.get("warnings") or []:
            warnings.append(f"{name}: {msg}")

    passed = len(failures) == 0
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "command": "verify",
        "mode": "verify",
        "domain": "positions",
        "database": db_identity,
        "allowlist_hash": allowlist_hash,
        "allowlist_summary": schema_info,
        "before_manifest_mode": (before_manifest or {}).get("mode"),
        "before_manifest_domain": (before_manifest or {}).get("domain"),
        "checks": checks,
        "skipped_checks": skipped,
        "result": {
            "passed": passed,
            "failures": failures,
            "warnings": warnings,
        },
    }


def run_positions_verify(
    engine: Engine,
    allowlist: dict[str, Any],
    db_identity: dict[str, Any],
    *,
    manifest_out,
    before_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with engine.connect() as conn:
        report = build_positions_verify_report(
            conn,
            allowlist,
            db_identity,
            before_manifest=before_manifest,
        )
    out_path = save_report(manifest_out, report)
    passed = report["result"]["passed"]
    print(f"DOMAIN: positions")
    print(f"DATABASE: {db_identity['url_redacted']}")
    print(f"VERIFY passed: {passed}")
    if report["result"]["failures"]:
        print("FAILURES:")
        for msg in report["result"]["failures"]:
            print(f"  {msg}")
    if report["result"]["warnings"]:
        print("WARNINGS:")
        for msg in report["result"]["warnings"]:
            print(f"  {msg}")
    if report["skipped_checks"]:
        print("SKIPPED:")
        for msg in report["skipped_checks"]:
            print(f"  {msg}")
    print(f"MANIFEST: {out_path}")
    return report


def run_positions_audit(engine: Engine, db_identity: dict[str, Any], *, manifest_out) -> dict[str, Any]:
    with engine.connect() as conn:
        report = discover_test_position_candidates(conn)
    manifest = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "audit",
        "domain": "positions",
        "database": db_identity,
        **report,
    }
    out_path = save_report(manifest_out, manifest)
    _print_positions_audit_summary(manifest, out_path)
    return manifest


def run_allowed_positions_audit(
    engine: Engine,
    db_identity: dict[str, Any],
    *,
    org_unit_id: int,
    manifest_out,
) -> dict[str, Any]:
    with engine.connect() as conn:
        report = audit_allowed_positions_for_unit(conn, int(org_unit_id))
    manifest = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "audit",
        "domain": "allowed-positions",
        "database": db_identity,
        **report,
    }
    out_path = save_report(manifest_out, manifest)
    _print_allowed_positions_audit_summary(manifest, out_path)
    return manifest


def run_allowed_positions_execute(
    engine: Engine,
    allowlist: dict[str, Any],
    db_identity: dict[str, Any],
    *,
    manifest_out,
) -> dict[str, Any]:
    deleted: list[dict[str, Any]] = []
    with engine.begin() as conn:
        verified = _verify_link_signatures(conn, allowlist)
        for row in verified:
            link_id = int(row["link_id"])
            result = conn.execute(
                text(
                    "DELETE FROM public.org_unit_allowed_positions "
                    "WHERE org_unit_allowed_position_id = :link_id"
                ),
                {"link_id": link_id},
            )
            deleted.append(
                {
                    "link_id": link_id,
                    "org_unit_id": int(row["org_unit_id"]),
                    "position_id": int(row["position_id"]),
                    "position_name": row["position_name"],
                    "rowcount": int(result.rowcount or 0),
                }
            )
    manifest = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "execute",
        "domain": "allowed-positions",
        "database": db_identity,
        "transaction_status": "committed",
        "deleted_links": deleted,
    }
    out_path = save_report(manifest_out, manifest)
    print(f"EXECUTE allowed-links: deleted {len(deleted)} link(s)")
    print(f"MANIFEST: {out_path}")
    return manifest


def run_positions_execute(
    engine: Engine,
    allowlist: dict[str, Any],
    db_identity: dict[str, Any],
    *,
    manifest_out,
) -> dict[str, Any]:
    deleted: list[dict[str, Any]] = []
    with engine.begin() as conn:
        verified = _verify_position_signatures(conn, allowlist)
        for row in verified:
            pid = int(row["position_id"])
            result = conn.execute(
                text("DELETE FROM public.positions WHERE position_id = :position_id"),
                {"position_id": pid},
            )
            deleted.append(
                {
                    "position_id": pid,
                    "name": row["name"],
                    "rowcount": int(result.rowcount or 0),
                }
            )
    manifest = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "execute",
        "domain": "positions",
        "database": db_identity,
        "transaction_status": "committed",
        "deleted_positions": deleted,
    }
    out_path = save_report(manifest_out, manifest)
    print(f"EXECUTE positions: deleted {len(deleted)} position(s)")
    print(f"MANIFEST: {out_path}")
    return manifest


def _print_positions_audit_summary(manifest: dict[str, Any], out_path) -> None:
    print(f"DOMAIN: positions")
    print(f"DATABASE: {manifest['database']['url_redacted']}")
    print("CANDIDATES BY MASK:")
    for label, block in manifest["candidates_by_mask"].items():
        print(f"  {label}: {block['count']}")
    print(f"TOTAL UNIQUE CANDIDATES: {manifest['candidate_ids_total']}")
    print(f"DELETABLE: {len(manifest['deletable_candidates'])}")
    print(f"BLOCKED: {len(manifest['blocked_candidates'])}")
    if manifest["blocked_candidates"]:
        print("BLOCKED SAMPLE (first 10):")
        for item in manifest["blocked_candidates"][:10]:
            print(
                f"  id={item['position_id']} name={item['name']} "
                f"reasons={'; '.join(item['blocked_reasons'])}"
            )
    print(f"MANIFEST: {out_path}")


def _print_allowed_positions_audit_summary(manifest: dict[str, Any], out_path) -> None:
    print(f"DOMAIN: allowed-positions")
    print(f"DATABASE: {manifest['database']['url_redacted']}")
    print(f"ORG UNIT: {manifest['org_unit_id']}")
    print(f"ALLOWED LINKS: {len(manifest['allowed_links'])}")
    print(f"ETALON LINKS: {len(manifest['etalon_links'])}")
    print(f"EXTRA LINKS TO DELETE: {len(manifest['extra_allowed_links'])}")
    for link in manifest["extra_allowed_links"]:
        print(
            f"  link_id={link['link_id']} position_id={link['position_id']} "
            f"name={link['position_name']}"
        )
    print(f"MANIFEST: {out_path}")
