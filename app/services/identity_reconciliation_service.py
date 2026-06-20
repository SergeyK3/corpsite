"""ADR-044 B1/B2 — Identity reconciliation (R1a dry-run and execute)."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.hr_canonical_snapshot_service import (
    SOURCE_TYPE_HR_CONTROL_LIST,
    get_active_snapshot,
)
from app.services.hr_effective_canonical_service import _person_scope_key

PHASE_R1A = "R1a"
FIELD_PATH_IDENTITY_IIN = "identity.iin"

SOURCE_P1 = "P1_override"
SOURCE_P2 = "P2_effective_cache"
SOURCE_P3 = "P3_canonical_entry"
SOURCE_P4 = "P4_employee_identity"
SOURCE_P5 = "P5_change_event"

OUTCOME_APPLY = "APPLY"
OUTCOME_SKIP_ALREADY_FILLED = "SKIP_ALREADY_FILLED"
OUTCOME_SKIP_INCOMPLETE = "SKIP_INCOMPLETE"
OUTCOME_SKIP_INVALID_IIN = "SKIP_INVALID_IIN"
OUTCOME_SKIP_CONFLICT_DUPLICATE_IIN = "SKIP_CONFLICT_DUPLICATE_IIN"
OUTCOME_SKIP_CONFLICT_EXISTING_IIN = "SKIP_CONFLICT_EXISTING_IIN"
OUTCOME_SKIP_CONFLICT_EI_MISMATCH = "SKIP_CONFLICT_EI_MISMATCH"
OUTCOME_SKIP_CONFLICT_EI_GLOBAL = "SKIP_CONFLICT_EI_GLOBAL"
OUTCOME_SKIP_CONFLICT_AMBIGUOUS_SOURCE = "SKIP_CONFLICT_AMBIGUOUS_SOURCE"

OPERATIONAL_EMPLOYEE_STATUSES = ("draft", "active", "suspended")


class IdentityReconciliationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def _table_exists(conn: Connection, table: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :table
            LIMIT 1
            """
        ),
        {"table": table},
    ).first()
    return row is not None


def normalize_iin(raw: Any) -> Optional[str]:
    """Return 12-digit IIN string or None if invalid."""
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return None
    digits = re.sub(r"[^0-9]", "", str(raw).strip())
    if len(digits) != 12:
        return None
    return digits


def _extract_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("{", "[", '"')):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return stripped
        return stripped
    return value


def _payload_iin(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                return None
        else:
            return None
    return normalize_iin(payload.get("iin"))


def _resolve_snapshot_id(conn: Connection, snapshot_id: Optional[int]) -> int:
    if snapshot_id is not None:
        return int(snapshot_id)
    active = get_active_snapshot(conn, source_type=SOURCE_TYPE_HR_CONTROL_LIST)
    if not active:
        raise IdentityReconciliationError("no active canonical snapshot (G5)")
    return int(active["snapshot_id"])


def _load_linked_employees(conn: Connection, person_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT employee_id, person_id, full_name, operational_status, is_active
            FROM public.employees
            WHERE person_id = :person_id
              AND operational_status = ANY(:statuses)
            ORDER BY employee_id
            """
        ),
        {"person_id": int(person_id), "statuses": list(OPERATIONAL_EMPLOYEE_STATUSES)},
    ).mappings().all()
    return [dict(row) for row in rows]


def resolve_canonical_person_key(
    conn: Connection,
    *,
    person_id: int,
    match_key: str,
    employee_ids: list[int],
    snapshot_id: int,
) -> tuple[str, list[str]]:
    """Return (canonical_person_key, warnings)."""
    warnings: list[str] = []
    if len(employee_ids) == 1:
        return f"emp:{int(employee_ids[0])}", warnings
    if len(employee_ids) > 1:
        warnings.append(
            f"person_id={person_id}: multiple operational employees {employee_ids}; using emp:{employee_ids[0]}"
        )
        return f"emp:{int(employee_ids[0])}", warnings

    key = (match_key or "").strip()
    if key:
        row = conn.execute(
            text(
                """
                SELECT match_key
                FROM public.hr_canonical_snapshot_entries
                WHERE snapshot_id = :snapshot_id
                  AND record_kind = 'roster'
                  AND match_key = :match_key
                LIMIT 1
                """
            ),
            {"snapshot_id": int(snapshot_id), "match_key": key},
        ).mappings().first()
        if row:
            return str(row["match_key"]), warnings

    if key:
        warnings.append(f"person_id={person_id}: no employee link; using persons.match_key={key!r} for lookup")
        return key, warnings

    warnings.append(f"person_id={person_id}: cannot derive canonical person_key")
    return "", warnings


def _resolve_p1_override_iin(
    conn: Connection,
    *,
    canonical_person_key: str,
) -> Optional[tuple[str, Any]]:
    if not canonical_person_key or not _table_exists(conn, "hr_review_overrides"):
        return None
    scope_key = _person_scope_key(canonical_person_key)
    row = conn.execute(
        text(
            """
            SELECT override_value
            FROM public.hr_review_overrides
            WHERE status = 'active'
              AND field_path = :field_path
              AND scope_key = :scope_key
            ORDER BY override_id DESC
            LIMIT 1
            """
        ),
        {"field_path": FIELD_PATH_IDENTITY_IIN, "scope_key": scope_key},
    ).mappings().first()
    if not row:
        return None
    raw = _extract_scalar(row["override_value"])
    iin = normalize_iin(raw)
    if iin is None:
        return None
    return iin, raw


def _resolve_p2_effective_iin(
    conn: Connection,
    *,
    snapshot_id: int,
    canonical_person_key: str,
) -> Optional[tuple[str, Any]]:
    if not canonical_person_key or not _table_exists(conn, "hr_snapshot_effective_entries"):
        return None
    row = conn.execute(
        text(
            """
            SELECT effective_payload
            FROM public.hr_snapshot_effective_entries
            WHERE snapshot_id = :snapshot_id
              AND match_key = :match_key
              AND record_kind = 'roster'
            LIMIT 1
            """
        ),
        {"snapshot_id": int(snapshot_id), "match_key": canonical_person_key},
    ).mappings().first()
    if not row:
        return None
    payload = row["effective_payload"]
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = {}
    iin = _payload_iin(payload)
    if iin is None:
        return None
    return iin, payload.get("iin") if isinstance(payload, dict) else None


def _resolve_p3_canonical_iin(
    conn: Connection,
    *,
    snapshot_id: int,
    canonical_person_key: str,
    employee_id: Optional[int],
) -> Optional[tuple[str, Any]]:
    row = None
    if canonical_person_key:
        row = conn.execute(
            text(
                """
                SELECT iin, payload
                FROM public.hr_canonical_snapshot_entries
                WHERE snapshot_id = :snapshot_id
                  AND record_kind = 'roster'
                  AND match_key = :match_key
                LIMIT 1
                """
            ),
            {"snapshot_id": int(snapshot_id), "match_key": canonical_person_key},
        ).mappings().first()
    if row is None and employee_id is not None:
        row = conn.execute(
            text(
                """
                SELECT iin, payload
                FROM public.hr_canonical_snapshot_entries
                WHERE snapshot_id = :snapshot_id
                  AND record_kind = 'roster'
                  AND employee_id = :employee_id
                LIMIT 1
                """
            ),
            {"snapshot_id": int(snapshot_id), "employee_id": int(employee_id)},
        ).mappings().first()
    if not row:
        return None
    iin = normalize_iin(row.get("iin")) or _payload_iin(row.get("payload"))
    if iin is None:
        return None
    raw = row.get("iin") or (_payload_iin(row.get("payload")) and row.get("payload"))
    return iin, raw


def _resolve_p4_employee_identity_iin(
    conn: Connection,
    *,
    employee_id: Optional[int],
) -> Optional[tuple[str, Any]]:
    if employee_id is None or not _table_exists(conn, "employee_identities"):
        return None
    row = conn.execute(
        text(
            """
            SELECT identity_value
            FROM public.employee_identities
            WHERE employee_id = :employee_id
              AND identity_type = 'IIN'
              AND valid_to IS NULL
            ORDER BY is_primary DESC NULLS LAST, identity_id
            LIMIT 1
            """
        ),
        {"employee_id": int(employee_id)},
    ).mappings().first()
    if not row:
        return None
    iin = normalize_iin(row["identity_value"])
    if iin is None:
        return None
    return iin, row["identity_value"]


def _resolve_p5_change_event_iin(
    conn: Connection,
    *,
    canonical_person_key: str,
    employee_id: Optional[int],
) -> Optional[tuple[str, Any]]:
    if not _table_exists(conn, "hr_change_events"):
        return None
    row = conn.execute(
        text(
            """
            SELECT iin
            FROM public.hr_change_events
            WHERE (
                    (:employee_id IS NOT NULL AND employee_id = :employee_id)
                 OR (:match_key <> '' AND match_key = :match_key)
                  )
              AND iin IS NOT NULL
            ORDER BY event_at DESC, change_event_id DESC
            LIMIT 1
            """
        ),
        {
            "employee_id": int(employee_id) if employee_id is not None else None,
            "match_key": canonical_person_key or "",
        },
    ).mappings().first()
    if not row:
        return None
    iin = normalize_iin(row["iin"])
    if iin is None:
        return None
    return iin, row["iin"]


def resolve_iin_for_person(
    conn: Connection,
    *,
    snapshot_id: int,
    canonical_person_key: str,
    employee_id: Optional[int],
) -> dict[str, Any]:
    """Resolve IIN using P1→P5 precedence. Read-only."""
    chain: list[dict[str, Any]] = []

    p1 = _resolve_p1_override_iin(conn, canonical_person_key=canonical_person_key)
    if p1:
        chain.append({"source": SOURCE_P1, "iin": p1[0], "raw": p1[1]})
        return {
            "iin": p1[0],
            "source": SOURCE_P1,
            "raw_value": p1[1],
            "chain": chain,
            "ambiguous": False,
        }

    p2 = _resolve_p2_effective_iin(
        conn, snapshot_id=snapshot_id, canonical_person_key=canonical_person_key
    )
    if p2:
        chain.append({"source": SOURCE_P2, "iin": p2[0], "raw": p2[1]})
        return {
            "iin": p2[0],
            "source": SOURCE_P2,
            "raw_value": p2[1],
            "chain": chain,
            "ambiguous": False,
        }

    for source, resolver in (
        (SOURCE_P3, lambda: _resolve_p3_canonical_iin(
            conn,
            snapshot_id=snapshot_id,
            canonical_person_key=canonical_person_key,
            employee_id=employee_id,
        )),
        (SOURCE_P4, lambda: _resolve_p4_employee_identity_iin(
            conn, employee_id=employee_id
        )),
        (SOURCE_P5, lambda: _resolve_p5_change_event_iin(
            conn,
            canonical_person_key=canonical_person_key,
            employee_id=employee_id,
        )),
    ):
        hit = resolver()
        if hit:
            chain.append({"source": source, "iin": hit[0], "raw": hit[1]})
            return {
                "iin": hit[0],
                "source": source,
                "raw_value": hit[1],
                "chain": chain,
                "ambiguous": False,
            }

    return {"iin": None, "source": None, "raw_value": None, "chain": chain, "ambiguous": False}


def _load_active_ei(conn: Connection, employee_id: int) -> Optional[dict[str, Any]]:
    if not _table_exists(conn, "employee_identities"):
        return None
    row = conn.execute(
        text(
            """
            SELECT identity_id, identity_value
            FROM public.employee_identities
            WHERE employee_id = :employee_id
              AND identity_type = 'IIN'
              AND valid_to IS NULL
            ORDER BY is_primary DESC NULLS LAST, identity_id
            LIMIT 1
            """
        ),
        {"employee_id": int(employee_id)},
    ).mappings().first()
    return dict(row) if row else None


def _holder_person_id_for_iin(conn: Connection, iin: str, *, exclude_person_id: int) -> Optional[int]:
    row = conn.execute(
        text(
            """
            SELECT person_id
            FROM public.persons
            WHERE iin = :iin
              AND person_status = 'active'
              AND person_id <> :exclude_person_id
            LIMIT 1
            """
        ),
        {"iin": iin, "exclude_person_id": int(exclude_person_id)},
    ).mappings().first()
    return int(row["person_id"]) if row else None


def _holder_employee_id_for_iin(conn: Connection, iin: str, *, exclude_employee_id: Optional[int]) -> Optional[int]:
    if not _table_exists(conn, "employee_identities"):
        return None
    row = conn.execute(
        text(
            """
            SELECT employee_id
            FROM public.employee_identities
            WHERE identity_type = 'IIN'
              AND valid_to IS NULL
              AND regexp_replace(COALESCE(identity_value, ''), '[^0-9]', '', 'g') = :iin
              AND (:exclude_employee_id IS NULL OR employee_id <> :exclude_employee_id)
            LIMIT 1
            """
        ),
        {"iin": iin, "exclude_employee_id": exclude_employee_id},
    ).mappings().first()
    return int(row["employee_id"]) if row else None


def classify_candidate(
    conn: Connection,
    *,
    person: dict[str, Any],
    resolved: dict[str, Any],
    employee_id: Optional[int],
    active_ei: Optional[dict[str, Any]],
    canonical_person_key: str,
) -> dict[str, Any]:
    """Classify a single reconciliation candidate (dry-run only)."""
    return _classify_with_conn(
        conn,
        person=person,
        resolved=resolved,
        employee_id=employee_id,
        active_ei=active_ei,
        canonical_person_key=canonical_person_key,
    )


def _classify_with_conn(
    conn: Connection,
    *,
    person: dict[str, Any],
    resolved: dict[str, Any],
    employee_id: Optional[int],
    active_ei: Optional[dict[str, Any]],
    canonical_person_key: str,
) -> dict[str, Any]:
    person_id = int(person["person_id"])
    existing_iin = normalize_iin(person.get("iin"))
    resolved_iin = resolved.get("iin")
    match_key = str(person.get("match_key") or "")

    base = {
        "person_id": person_id,
        "full_name": person.get("full_name"),
        "match_key": match_key,
        "canonical_person_key": canonical_person_key,
        "employee_id": employee_id,
        "resolved_iin": resolved_iin,
        "source": resolved.get("source"),
        "source_chain": resolved.get("chain") or [],
        "would_update_person_iin": False,
        "would_insert_employee_identity": False,
    }

    if existing_iin is not None:
        if resolved_iin and existing_iin != resolved_iin:
            return {
                **base,
                "outcome": OUTCOME_SKIP_CONFLICT_EXISTING_IIN,
                "error_code": "CONFLICT_EXISTING_IIN",
                "message": f"persons.iin={existing_iin} differs from resolved {resolved_iin}",
            }
        return {
            **base,
            "outcome": OUTCOME_SKIP_ALREADY_FILLED,
            "resolved_iin": existing_iin,
            "source": None,
            "message": "persons.iin already set",
        }

    if resolved.get("ambiguous"):
        return {
            **base,
            "outcome": OUTCOME_SKIP_CONFLICT_AMBIGUOUS_SOURCE,
            "error_code": "CONFLICT_AMBIGUOUS_SOURCE",
            "message": f"conflicting P3/P4/P5 sources: {resolved.get('conflict_sources')}",
        }

    if resolved_iin is None:
        return {
            **base,
            "outcome": OUTCOME_SKIP_INCOMPLETE,
            "error_code": "IDENTITY_INCOMPLETE",
            "message": "no resolvable IIN in P1→P5 chain",
        }

    holder_person = _holder_person_id_for_iin(conn, resolved_iin, exclude_person_id=person_id)
    if holder_person is not None:
        return {
            **base,
            "outcome": OUTCOME_SKIP_CONFLICT_DUPLICATE_IIN,
            "error_code": "CONFLICT_DUPLICATE_IIN",
            "message": f"IIN {resolved_iin} already on active person_id={holder_person}",
            "holder_person_id": holder_person,
        }

    if active_ei is not None:
        ei_iin = normalize_iin(active_ei.get("identity_value"))
        if ei_iin and ei_iin != resolved_iin:
            return {
                **base,
                "outcome": OUTCOME_SKIP_CONFLICT_EI_MISMATCH,
                "error_code": "CONFLICT_EI_MISMATCH",
                "message": f"employee_identities IIN={ei_iin} differs from resolved {resolved_iin}",
            }

    if employee_id is not None:
        holder_emp = _holder_employee_id_for_iin(
            conn, resolved_iin, exclude_employee_id=employee_id
        )
        if holder_emp is not None:
            return {
                **base,
                "outcome": OUTCOME_SKIP_CONFLICT_EI_GLOBAL,
                "error_code": "CONFLICT_EI_GLOBAL",
                "message": f"IIN {resolved_iin} already on employee_id={holder_emp}",
                "holder_employee_id": holder_emp,
            }

    would_insert_ei = employee_id is not None and active_ei is None
    return {
        **base,
        "outcome": OUTCOME_APPLY,
        "would_update_person_iin": True,
        "would_insert_employee_identity": would_insert_ei,
        "message": "eligible for R1a materialization",
    }


def build_reconciliation_candidates(
    conn: Connection,
    *,
    snapshot_id: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Scan persons and classify R1a candidates. Read-only."""
    sid = _resolve_snapshot_id(conn, snapshot_id)
    rows = conn.execute(
        text(
            """
            SELECT person_id, full_name, match_key, iin, person_status
            FROM public.persons
            WHERE person_status IN ('active', 'inactive')
            ORDER BY person_id
            """
        )
    ).mappings().all()

    candidates: list[dict[str, Any]] = []
    for row in rows:
        person = dict(row)
        employees = _load_linked_employees(conn, int(person["person_id"]))
        employee_ids = [int(e["employee_id"]) for e in employees]
        primary_employee_id = employee_ids[0] if employee_ids else None

        canonical_key, key_warnings = resolve_canonical_person_key(
            conn,
            person_id=int(person["person_id"]),
            match_key=str(person.get("match_key") or ""),
            employee_ids=employee_ids,
            snapshot_id=sid,
        )

        resolved = resolve_iin_for_person(
            conn,
            snapshot_id=sid,
            canonical_person_key=canonical_key,
            employee_id=primary_employee_id,
        )

        active_ei = (
            _load_active_ei(conn, primary_employee_id) if primary_employee_id is not None else None
        )

        classified = classify_candidate(
            conn,
            person=person,
            resolved=resolved,
            employee_id=primary_employee_id,
            active_ei=active_ei,
            canonical_person_key=canonical_key,
        )
        if key_warnings:
            classified["warnings"] = key_warnings
        candidates.append(classified)

    return candidates


def _gate_result(
    gate_id: str,
    *,
    severity: str,
    blocks: bool,
    count: int,
    violations: list[dict[str, Any]],
    message: str = "",
) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "severity": severity,
        "blocks_execute": blocks,
        "count": count,
        "violations": violations,
        "message": message,
        "passed": count == 0,
    }


def run_validation_gates(
    conn: Connection,
    *,
    candidates: list[dict[str, Any]],
    snapshot_id: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Run pre-execute validation gates G1–G10. Read-only."""
    gates: list[dict[str, Any]] = []

    # G5 — active snapshot
    try:
        sid = _resolve_snapshot_id(conn, snapshot_id)
        g5_violations: list[dict[str, Any]] = []
    except IdentityReconciliationError as exc:
        gates.append(
            _gate_result(
                "G5",
                severity="CRITICAL",
                blocks=True,
                count=1,
                violations=[{"error": exc.message}],
                message="No active canonical snapshot",
            )
        )
        return gates
    else:
        gates.append(
            _gate_result(
                "G5",
                severity="CRITICAL",
                blocks=False,
                count=0,
                violations=[],
                message=f"active snapshot_id={sid}",
            )
        )

    # G1 — duplicate active IIN in existing data
    g1_rows = conn.execute(
        text(
            """
            SELECT iin, COUNT(*) AS cnt, array_agg(person_id ORDER BY person_id) AS person_ids
            FROM public.persons
            WHERE iin IS NOT NULL AND person_status = 'active'
            GROUP BY iin
            HAVING COUNT(*) > 1
            """
        )
    ).mappings().all()
    g1_violations = [
        {"iin": r["iin"], "count": int(r["cnt"]), "person_ids": list(r["person_ids"] or [])}
        for r in g1_rows
    ]
    gates.append(
        _gate_result(
            "G1",
            severity="CRITICAL",
            blocks=len(g1_violations) > 0,
            count=len(g1_violations),
            violations=g1_violations,
            message="Duplicate active IIN across persons",
        )
    )

    # G2 — apply would duplicate IIN
    g2_violations = [
        {
            "person_id": c["person_id"],
            "resolved_iin": c.get("resolved_iin"),
            "holder_person_id": c.get("holder_person_id"),
        }
        for c in candidates
        if c.get("outcome") == OUTCOME_SKIP_CONFLICT_DUPLICATE_IIN
    ]
    gates.append(
        _gate_result(
            "G2",
            severity="CRITICAL",
            blocks=False,
            count=len(g2_violations),
            violations=g2_violations,
            message="Candidate would create duplicate active IIN",
        )
    )

    # G3 — invalid IIN in resolved values
    g3_violations = [
        {"person_id": c["person_id"], "source": c.get("source"), "raw": c.get("source_chain")}
        for c in candidates
        if c.get("outcome") == OUTCOME_SKIP_INVALID_IIN
    ]
    gates.append(
        _gate_result(
            "G3",
            severity="CRITICAL",
            blocks=False,
            count=len(g3_violations),
            violations=g3_violations,
            message="Invalid resolved IIN format",
        )
    )

    # G4 — multiple persons same canonical IIN
    g4_rows = conn.execute(
        text(
            """
            SELECT c.iin, COUNT(DISTINCT p.person_id) AS person_count,
                   array_agg(DISTINCT p.person_id ORDER BY p.person_id) AS person_ids
            FROM public.persons p
            JOIN public.employees e ON e.person_id = p.person_id
            JOIN public.hr_canonical_snapshot_entries c
              ON c.employee_id = e.employee_id AND c.record_kind = 'roster'
            WHERE p.iin IS NULL
              AND c.iin IS NOT NULL
              AND p.person_status = 'active'
              AND c.snapshot_id = :snapshot_id
            GROUP BY c.iin
            HAVING COUNT(DISTINCT p.person_id) > 1
            """
        ),
        {"snapshot_id": sid},
    ).mappings().all()
    g4_violations = [
        {
            "canonical_iin": r["iin"],
            "person_count": int(r["person_count"]),
            "person_ids": list(r["person_ids"] or []),
        }
        for r in g4_rows
    ]
    gates.append(
        _gate_result(
            "G4",
            severity="CRITICAL",
            blocks=len(g4_violations) > 0,
            count=len(g4_violations),
            violations=g4_violations,
            message="Multiple persons share same canonical IIN",
        )
    )

    # G6 — existing persons.iin != resolved
    g6_violations = [
        {
            "person_id": c["person_id"],
            "message": c.get("message"),
        }
        for c in candidates
        if c.get("outcome") == OUTCOME_SKIP_CONFLICT_EXISTING_IIN
    ]
    gates.append(
        _gate_result(
            "G6",
            severity="HIGH",
            blocks=False,
            count=len(g6_violations),
            violations=g6_violations,
            message="Existing persons.iin inconsistent with resolved IIN",
        )
    )

    # G7 — orphan employees
    g7_rows = conn.execute(
        text(
            """
            SELECT employee_id, full_name, operational_status, is_active
            FROM public.employees
            WHERE person_id IS NULL
              AND operational_status <> 'terminated'
            ORDER BY employee_id
            """
        )
    ).mappings().all()
    g7_violations = [dict(r) for r in g7_rows]
    gates.append(
        _gate_result(
            "G7",
            severity="MEDIUM",
            blocks=False,
            count=len(g7_violations),
            violations=g7_violations[:20],
            message="Employees without person_id",
        )
    )

    # G8 — employee link but no canonical roster row
    g8_rows = conn.execute(
        text(
            """
            SELECT p.person_id, p.match_key, e.employee_id
            FROM public.persons p
            JOIN public.employees e ON e.person_id = p.person_id
            WHERE p.person_status IN ('active', 'inactive')
              AND NOT EXISTS (
                  SELECT 1
                  FROM public.hr_canonical_snapshot_entries c
                  WHERE c.snapshot_id = :snapshot_id
                    AND c.record_kind = 'roster'
                    AND (
                        c.employee_id = e.employee_id
                        OR c.match_key = 'emp:' || e.employee_id::text
                    )
              )
            ORDER BY p.person_id
            """
        ),
        {"snapshot_id": sid},
    ).mappings().all()
    g8_violations = [dict(r) for r in g8_rows]
    gates.append(
        _gate_result(
            "G8",
            severity="LOW",
            blocks=False,
            count=len(g8_violations),
            violations=g8_violations[:20],
            message="Linked employee missing canonical roster row",
        )
    )

    # G9 — EI mismatch
    g9_violations = [
        {"person_id": c["person_id"], "employee_id": c.get("employee_id"), "message": c.get("message")}
        for c in candidates
        if c.get("outcome") == OUTCOME_SKIP_CONFLICT_EI_MISMATCH
    ]
    gates.append(
        _gate_result(
            "G9",
            severity="HIGH",
            blocks=False,
            count=len(g9_violations),
            violations=g9_violations,
            message="employee_identities IIN mismatch vs resolved",
        )
    )

    # G10 — unresolved identity (incomplete)
    incomplete = [c for c in candidates if c.get("outcome") == OUTCOME_SKIP_INCOMPLETE]
    gates.append(
        _gate_result(
            "G10",
            severity="INFO",
            blocks=False,
            count=len(incomplete),
            violations=[{"person_id": c["person_id"], "match_key": c.get("match_key")} for c in incomplete[:20]],
            message="IDENTITY_INCOMPLETE — expected for persons without canonical IIN",
        )
    )

    return gates


def _compute_metrics(conn: Connection, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    total = conn.execute(
        text(
            """
            SELECT COUNT(*) FROM public.persons
            WHERE person_status IN ('active', 'inactive')
            """
        )
    ).scalar_one()
    with_iin = conn.execute(
        text(
            """
            SELECT COUNT(*) FROM public.persons
            WHERE person_status IN ('active', 'inactive') AND iin IS NOT NULL
            """
        )
    ).scalar_one()
    total_int = int(total)
    with_iin_int = int(with_iin)
    apply_candidates = [c for c in candidates if c.get("outcome") == OUTCOME_APPLY]
    incomplete = [c for c in candidates if c.get("outcome") == OUTCOME_SKIP_INCOMPLETE]
    null_iin = [c for c in candidates if normalize_iin(c.get("resolved_iin")) is None and c.get("outcome") != OUTCOME_SKIP_ALREADY_FILLED]

    coverage = (with_iin_int / total_int) if total_int else 0.0
    projected_with_iin = with_iin_int + len(apply_candidates)
    projected_coverage = (projected_with_iin / total_int) if total_int else 0.0

    return {
        "persons_total": total_int,
        "persons_with_iin_before": with_iin_int,
        "persons_iin_coverage_before_pct": round(coverage * 100, 2),
        "apply_count": len(apply_candidates),
        "projected_persons_with_iin_after": projected_with_iin,
        "projected_iin_coverage_after_pct": round(projected_coverage * 100, 2),
        "resolvable_gap_after_r1a": len(incomplete),
        "identity_incomplete_count": len(incomplete),
        "would_insert_employee_identity_count": sum(
            1 for c in apply_candidates if c.get("would_insert_employee_identity")
        ),
    }


def build_reconciliation_report(
    conn: Connection,
    *,
    snapshot_id: Optional[int] = None,
) -> dict[str, Any]:
    """Build full R1a dry-run report. Read-only."""
    try:
        sid = _resolve_snapshot_id(conn, snapshot_id)
    except IdentityReconciliationError as exc:
        gates = [
            _gate_result(
                "G5",
                severity="CRITICAL",
                blocks=True,
                count=1,
                violations=[{"error": exc.message}],
                message="No active canonical snapshot",
            )
        ]
        return {
            "phase": PHASE_R1A,
            "dry_run": True,
            "snapshot_id": snapshot_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "blocking": True,
            "execute_allowed": False,
            "summary": {"candidates_total": 0, "by_outcome": {}},
            "gates": gates,
            "apply_preview": [],
            "conflicts": [],
            "incomplete": [],
            "already_filled": [],
            "employee_identity_gaps": [],
            "candidates": [],
            "warnings": [],
            "errors": [exc.message],
        }

    candidates = build_reconciliation_candidates(conn, snapshot_id=sid)
    gates = run_validation_gates(conn, candidates=candidates, snapshot_id=sid)
    metrics = _compute_metrics(conn, candidates)

    by_outcome: dict[str, int] = {}
    for c in candidates:
        outcome = str(c.get("outcome") or "UNKNOWN")
        by_outcome[outcome] = by_outcome.get(outcome, 0) + 1

    apply_preview = [c for c in candidates if c.get("outcome") == OUTCOME_APPLY]
    conflicts = [
        c
        for c in candidates
        if str(c.get("outcome", "")).startswith("SKIP_CONFLICT")
    ]
    incomplete = [c for c in candidates if c.get("outcome") == OUTCOME_SKIP_INCOMPLETE]
    already_filled = [c for c in candidates if c.get("outcome") == OUTCOME_SKIP_ALREADY_FILLED]
    employee_identity_gaps = [
        c for c in apply_preview if c.get("would_insert_employee_identity")
    ]

    blocking = any(g.get("blocks_execute") and g.get("count", 0) > 0 for g in gates)

    warnings: list[str] = []
    for c in candidates:
        for w in c.get("warnings") or []:
            warnings.append(str(w))

    return {
        "phase": PHASE_R1A,
        "dry_run": True,
        "snapshot_id": sid,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "blocking": blocking,
        "execute_allowed": not blocking,
        "summary": {
            "candidates_total": len(candidates),
            "by_outcome": by_outcome,
            **metrics,
        },
        "gates": gates,
        "apply_preview": apply_preview,
        "conflicts": conflicts,
        "incomplete": incomplete,
        "already_filled": already_filled,
        "employee_identity_gaps": employee_identity_gaps,
        "candidates": candidates,
        "warnings": warnings,
        "errors": [],
    }


def run_r1a_dry_run(
    conn: Connection,
    *,
    snapshot_id: Optional[int] = None,
) -> dict[str, Any]:
    """Entry point for R1a dry-run analysis."""
    return build_reconciliation_report(conn, snapshot_id=snapshot_id)


def run_r1a_dry_run_tx(*, snapshot_id: Optional[int] = None) -> dict[str, Any]:
    """Convenience wrapper using engine connection."""
    from app.db.engine import engine

    with engine.connect() as conn:
        return run_r1a_dry_run(conn, snapshot_id=snapshot_id)


RUN_STATUS_RUNNING = "running"
RUN_STATUS_COMPLETED = "completed"
RUN_STATUS_FAILED = "failed"

ITEM_STATUS_PLANNED = "planned"
ITEM_STATUS_APPLIED = "applied"
ITEM_STATUS_SKIPPED = "skipped"
ITEM_STATUS_FAILED = "failed"

ACTION_UPDATE_PERSON_IIN = "UPDATE_PERSON_IIN"
ACTION_INSERT_EMPLOYEE_IDENTITY = "INSERT_EMPLOYEE_IDENTITY"
ACTION_NOOP = "NOOP"
ACTION_SKIP = "SKIP"


def reconciliation_tables_available(conn: Connection) -> bool:
    return _table_exists(conn, "identity_reconciliation_runs") and _table_exists(
        conn, "identity_reconciliation_items"
    )


def _insert_employee_identity_iin(
    conn: Connection,
    *,
    employee_id: int,
    iin: str,
    created_by: int,
) -> Optional[int]:
    """Insert active IIN row if missing. Returns identity_id or None if already exists."""
    existing = conn.execute(
        text(
            """
            SELECT identity_id
            FROM public.employee_identities
            WHERE employee_id = :employee_id
              AND identity_type = 'IIN'
              AND valid_to IS NULL
            LIMIT 1
            """
        ),
        {"employee_id": int(employee_id)},
    ).mappings().first()
    if existing:
        return None
    row = conn.execute(
        text(
            """
            INSERT INTO public.employee_identities (
                employee_id,
                identity_type,
                identity_value,
                is_primary,
                created_by
            )
            VALUES (:employee_id, 'IIN', :iin, TRUE, :created_by)
            RETURNING identity_id
            """
        ),
        {"employee_id": int(employee_id), "iin": iin, "created_by": int(created_by)},
    ).mappings().first()
    return int(row["identity_id"]) if row else None


def _reclassify_person_candidate(
    conn: Connection,
    *,
    person_id: int,
    snapshot_id: int,
) -> dict[str, Any]:
    """Re-scan and classify a single person (race-safe re-validation)."""
    row = conn.execute(
        text(
            """
            SELECT person_id, full_name, match_key, iin, person_status
            FROM public.persons
            WHERE person_id = :person_id
            """
        ),
        {"person_id": int(person_id)},
    ).mappings().first()
    if not row:
        raise IdentityReconciliationError(f"person_id={person_id} not found")
    person = dict(row)
    employees = _load_linked_employees(conn, int(person_id))
    employee_ids = [int(e["employee_id"]) for e in employees]
    primary_employee_id = employee_ids[0] if employee_ids else None
    canonical_key, key_warnings = resolve_canonical_person_key(
        conn,
        person_id=int(person_id),
        match_key=str(person.get("match_key") or ""),
        employee_ids=employee_ids,
        snapshot_id=int(snapshot_id),
    )
    resolved = resolve_iin_for_person(
        conn,
        snapshot_id=int(snapshot_id),
        canonical_person_key=canonical_key,
        employee_id=primary_employee_id,
    )
    active_ei = (
        _load_active_ei(conn, primary_employee_id) if primary_employee_id is not None else None
    )
    classified = classify_candidate(
        conn,
        person=person,
        resolved=resolved,
        employee_id=primary_employee_id,
        active_ei=active_ei,
        canonical_person_key=canonical_key,
    )
    if key_warnings:
        classified["warnings"] = key_warnings
    return classified


def _create_reconciliation_run(
    conn: Connection,
    *,
    actor_user_id: int,
    snapshot_id: Optional[int],
    dry_run: bool,
) -> int:
    row = conn.execute(
        text(
            """
            INSERT INTO public.identity_reconciliation_runs (
                phase, dry_run, actor_user_id, snapshot_id, status
            )
            VALUES (:phase, :dry_run, :actor_user_id, :snapshot_id, :status)
            RETURNING run_id
            """
        ),
        {
            "phase": PHASE_R1A,
            "dry_run": dry_run,
            "actor_user_id": int(actor_user_id),
            "snapshot_id": snapshot_id,
            "status": RUN_STATUS_RUNNING,
        },
    ).mappings().first()
    return int(row["run_id"])


def _insert_reconciliation_item(
    conn: Connection,
    *,
    run_id: int,
    person_id: int,
    employee_id: Optional[int],
    previous_iin: Optional[str],
    resolved_iin: Optional[str],
    source: Optional[str],
    outcome: str,
    action: str,
    status: str,
    error: Optional[str] = None,
    rollback_payload: Optional[dict[str, Any]] = None,
) -> int:
    row = conn.execute(
        text(
            """
            INSERT INTO public.identity_reconciliation_items (
                run_id, person_id, employee_id, previous_iin, resolved_iin,
                source, outcome, action, status, error, rollback_payload
            )
            VALUES (
                :run_id, :person_id, :employee_id, :previous_iin, :resolved_iin,
                :source, :outcome, :action, :status, :error, CAST(:rollback_payload AS jsonb)
            )
            RETURNING item_id
            """
        ),
        {
            "run_id": int(run_id),
            "person_id": int(person_id),
            "employee_id": employee_id,
            "previous_iin": previous_iin,
            "resolved_iin": resolved_iin,
            "source": source,
            "outcome": outcome,
            "action": action,
            "status": status,
            "error": error,
            "rollback_payload": json.dumps(rollback_payload or {}),
        },
    ).mappings().first()
    return int(row["item_id"])


def _finalize_reconciliation_run(
    conn: Connection,
    *,
    run_id: int,
    status: str,
    summary: dict[str, Any],
) -> None:
    conn.execute(
        text(
            """
            UPDATE public.identity_reconciliation_runs
            SET status = :status,
                finished_at = now(),
                summary = CAST(:summary AS jsonb)
            WHERE run_id = :run_id
            """
        ),
        {
            "run_id": int(run_id),
            "status": status,
            "summary": json.dumps(summary),
        },
    )


def apply_candidate(
    conn: Connection,
    *,
    candidate: dict[str, Any],
    snapshot_id: int,
    actor_user_id: int,
    run_id: int,
) -> dict[str, Any]:
    """Apply R1a materialization for one person within the caller transaction."""
    from app.services.security_audit_service import write_security_event

    person_id = int(candidate["person_id"])
    match_key_before = str(candidate.get("match_key") or "")

    locked = conn.execute(
        text(
            """
            SELECT person_id, full_name, match_key, iin, person_status
            FROM public.persons
            WHERE person_id = :person_id
              AND iin IS NULL
            FOR UPDATE
            """
        ),
        {"person_id": person_id},
    ).mappings().first()

    if not locked:
        fresh = conn.execute(
            text(
                """
                SELECT person_id, match_key, iin
                FROM public.persons
                WHERE person_id = :person_id
                """
            ),
            {"person_id": person_id},
        ).mappings().first()
        outcome = OUTCOME_SKIP_ALREADY_FILLED
        if fresh and normalize_iin(fresh.get("iin")) is None:
            outcome = OUTCOME_SKIP_INCOMPLETE
        _insert_reconciliation_item(
            conn,
            run_id=run_id,
            person_id=person_id,
            employee_id=candidate.get("employee_id"),
            previous_iin=normalize_iin(fresh.get("iin")) if fresh else None,
            resolved_iin=candidate.get("resolved_iin"),
            source=candidate.get("source"),
            outcome=outcome,
            action=ACTION_SKIP,
            status=ITEM_STATUS_SKIPPED,
            error="person iin already set or row missing",
            rollback_payload={"person_id": person_id, "match_key": match_key_before},
        )
        return {
            "person_id": person_id,
            "outcome": outcome,
            "status": ITEM_STATUS_SKIPPED,
            "person_updated": False,
            "ei_inserted": False,
        }

    previous_iin = normalize_iin(locked.get("iin"))
    match_key_before = str(locked.get("match_key") or match_key_before)

    classified = _reclassify_person_candidate(
        conn, person_id=person_id, snapshot_id=int(snapshot_id)
    )
    if classified.get("outcome") != OUTCOME_APPLY:
        _insert_reconciliation_item(
            conn,
            run_id=run_id,
            person_id=person_id,
            employee_id=classified.get("employee_id"),
            previous_iin=previous_iin,
            resolved_iin=classified.get("resolved_iin"),
            source=classified.get("source"),
            outcome=str(classified.get("outcome") or ACTION_SKIP),
            action=ACTION_SKIP,
            status=ITEM_STATUS_SKIPPED,
            error=classified.get("message"),
            rollback_payload={
                "person_id": person_id,
                "match_key": match_key_before,
                "previous_iin": previous_iin,
            },
        )
        return {
            "person_id": person_id,
            "outcome": classified.get("outcome"),
            "status": ITEM_STATUS_SKIPPED,
            "person_updated": False,
            "ei_inserted": False,
        }

    resolved_iin = str(classified["resolved_iin"])
    employee_id = classified.get("employee_id")
    source = classified.get("source")
    would_insert_ei = bool(classified.get("would_insert_employee_identity"))

    conn.execute(
        text(
            """
            UPDATE public.persons
            SET iin = :iin, updated_at = now()
            WHERE person_id = :person_id
              AND iin IS NULL
            """
        ),
        {"person_id": person_id, "iin": resolved_iin},
    )

    after_row = conn.execute(
        text(
            """
            SELECT match_key, iin
            FROM public.persons
            WHERE person_id = :person_id
            """
        ),
        {"person_id": person_id},
    ).mappings().first()
    match_key_after = str(after_row["match_key"] or "") if after_row else match_key_before
    if match_key_after != match_key_before:
        raise IdentityReconciliationError(
            f"match_key drift detected for person_id={person_id}: "
            f"{match_key_before!r} -> {match_key_after!r}"
        )

    ei_identity_id: Optional[int] = None
    ei_inserted = False
    if would_insert_ei and employee_id is not None:
        ei_identity_id = _insert_employee_identity_iin(
            conn,
            employee_id=int(employee_id),
            iin=resolved_iin,
            created_by=int(actor_user_id),
        )
        ei_inserted = ei_identity_id is not None

    rollback_payload: dict[str, Any] = {
        "person_id": person_id,
        "match_key": match_key_before,
        "previous_iin": previous_iin,
        "resolved_iin": resolved_iin,
        "employee_id": employee_id,
        "person_updated": True,
        "ei_inserted": ei_inserted,
    }
    if ei_identity_id is not None:
        rollback_payload["ei_identity_id"] = ei_identity_id

    action = ACTION_UPDATE_PERSON_IIN

    item_id = _insert_reconciliation_item(
        conn,
        run_id=run_id,
        person_id=person_id,
        employee_id=int(employee_id) if employee_id is not None else None,
        previous_iin=previous_iin,
        resolved_iin=resolved_iin,
        source=source,
        outcome=OUTCOME_APPLY,
        action=action,
        status=ITEM_STATUS_APPLIED,
        rollback_payload=rollback_payload,
    )

    write_security_event(
        event_type="PERSON_IIN_RECONCILED",
        actor_user_id=int(actor_user_id),
        target_person_id=person_id,
        target_employee_id=int(employee_id) if employee_id is not None else None,
        metadata={
            "run_id": run_id,
            "item_id": item_id,
            "previous_iin": previous_iin,
            "resolved_iin": resolved_iin,
            "source": source,
            "match_key": match_key_before,
            "ei_inserted": ei_inserted,
            "phase": PHASE_R1A,
        },
        conn=conn,
    )

    return {
        "person_id": person_id,
        "outcome": OUTCOME_APPLY,
        "status": ITEM_STATUS_APPLIED,
        "person_updated": True,
        "ei_inserted": ei_inserted,
        "resolved_iin": resolved_iin,
        "item_id": item_id,
        "match_key": match_key_after,
    }


def run_r1a_execute(
    conn: Connection,
    *,
    actor_user_id: int,
    snapshot_id: Optional[int] = None,
    person_id: Optional[int] = None,
    limit: Optional[int] = None,
) -> dict[str, Any]:
    """Execute R1a identity materialization for APPLY candidates."""
    from app.db.engine import engine

    preview = build_reconciliation_report(conn, snapshot_id=snapshot_id)
    if not preview.get("execute_allowed"):
        raise IdentityReconciliationError(
            "execute blocked by validation gates: "
            + ", ".join(
                g["gate_id"]
                for g in preview.get("gates", [])
                if g.get("blocks_execute") and g.get("count", 0) > 0
            )
            or "blocking condition"
        )

    sid = int(preview["snapshot_id"])
    if not reconciliation_tables_available(conn):
        raise IdentityReconciliationError(
            "identity_reconciliation tables missing — run alembic upgrade head"
        )

    apply_candidates = list(preview.get("apply_preview") or [])
    if person_id is not None:
        apply_candidates = [c for c in apply_candidates if int(c["person_id"]) == int(person_id)]
    if limit is not None:
        apply_candidates = apply_candidates[: max(0, int(limit))]

    with engine.begin() as run_conn:
        run_id = _create_reconciliation_run(
            run_conn,
            actor_user_id=int(actor_user_id),
            snapshot_id=sid,
            dry_run=False,
        )

    item_results: list[dict[str, Any]] = []
    applied = 0
    skipped = 0
    failed = 0
    ei_inserted = 0

    for candidate in apply_candidates:
        try:
            with engine.begin() as person_conn:
                result = apply_candidate(
                    person_conn,
                    candidate=candidate,
                    snapshot_id=sid,
                    actor_user_id=int(actor_user_id),
                    run_id=run_id,
                )
            item_results.append(result)
            if result.get("status") == ITEM_STATUS_APPLIED:
                applied += 1
                if result.get("ei_inserted"):
                    ei_inserted += 1
            else:
                skipped += 1
        except Exception as exc:
            failed += 1
            err_msg = str(exc)
            try:
                with engine.begin() as err_conn:
                    _insert_reconciliation_item(
                        err_conn,
                        run_id=run_id,
                        person_id=int(candidate["person_id"]),
                        employee_id=candidate.get("employee_id"),
                        previous_iin=None,
                        resolved_iin=candidate.get("resolved_iin"),
                        source=candidate.get("source"),
                        outcome=OUTCOME_APPLY,
                        action=ACTION_SKIP,
                        status=ITEM_STATUS_FAILED,
                        error=err_msg,
                        rollback_payload={
                            "person_id": int(candidate["person_id"]),
                            "match_key": candidate.get("match_key"),
                        },
                    )
            except Exception:
                pass
            item_results.append(
                {
                    "person_id": int(candidate["person_id"]),
                    "status": ITEM_STATUS_FAILED,
                    "error": err_msg,
                }
            )

    execute_summary = {
        "candidates_selected": len(apply_candidates),
        "applied": applied,
        "skipped": skipped,
        "failed": failed,
        "ei_inserted": ei_inserted,
        "preview_apply_count": preview.get("summary", {}).get("apply_count", 0),
    }

    run_status = RUN_STATUS_FAILED if failed and not applied else RUN_STATUS_COMPLETED
    with engine.begin() as final_conn:
        _finalize_reconciliation_run(
            final_conn,
            run_id=run_id,
            status=run_status,
            summary=execute_summary,
        )

    post_preview = build_reconciliation_report(conn, snapshot_id=sid)
    return {
        **post_preview,
        "dry_run": False,
        "run_id": run_id,
        "execute_summary": execute_summary,
        "item_results": item_results,
    }


def run_r1a_execute_tx(
    *,
    actor_user_id: int,
    snapshot_id: Optional[int] = None,
    person_id: Optional[int] = None,
    limit: Optional[int] = None,
) -> dict[str, Any]:
    """Convenience wrapper using engine connection."""
    from app.db.engine import engine

    with engine.connect() as conn:
        return run_r1a_execute(
            conn,
            actor_user_id=actor_user_id,
            snapshot_id=snapshot_id,
            person_id=person_id,
            limit=limit,
        )
