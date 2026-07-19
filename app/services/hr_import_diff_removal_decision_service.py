"""Operator decisions on hr_import_diff_removals (restore vs confirm_removal)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.hr_canonical_snapshot_service import (
    RECORD_KIND_ROSTER,
    compute_canonical_hash,
)
from app.services.hr_import_analytics_service import BatchNotFoundError, _ensure_batch_exists

DECISION_RESTORE = "restore"
DECISION_CONFIRM_REMOVAL = "confirm_removal"
DECISION_VALUES = frozenset({DECISION_RESTORE, DECISION_CONFIRM_REMOVAL})


class DiffRemovalNotFoundError(LookupError):
    def __init__(self, removal_id: int) -> None:
        super().__init__(f"diff removal {removal_id} not found")
        self.removal_id = removal_id


class DiffRemovalAlreadyDecidedError(RuntimeError):
    def __init__(self, removal_id: int, *, decision: str) -> None:
        super().__init__(f"diff removal {removal_id} already decided as {decision}")
        self.removal_id = removal_id
        self.decision = decision


class InvalidDiffRemovalDecisionError(ValueError):
    pass


class DiffRemovalNotDecidedError(RuntimeError):
    def __init__(self, removal_id: int) -> None:
        super().__init__(f"diff removal {removal_id} has no decision to revert")
        self.removal_id = removal_id


class DiffRemovalRevertBlockedError(RuntimeError):
    def __init__(self, removal_id: int, *, reason: str) -> None:
        super().__init__(reason)
        self.removal_id = removal_id
        self.reason = reason


def diff_removal_decisions_available(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'hr_import_diff_removals'
              AND column_name = 'decision'
            """
        ),
    ).first()
    return row is not None


def _serialize_removal_row(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row.get("payload") or {})
    return {
        "removal_id": int(row["removal_id"]),
        "batch_id": int(row["batch_id"]),
        "canonical_entry_id": int(row["canonical_entry_id"]),
        "match_key": str(row["match_key"]),
        "record_kind": str(row["record_kind"]),
        "canonical_hash": str(row.get("canonical_hash") or ""),
        "payload": payload,
        "diff_status": str(row.get("diff_status") or "REMOVED"),
        "diff_computed_at": row.get("diff_computed_at").isoformat()
        if row.get("diff_computed_at") is not None
        else None,
        "decision": row.get("decision"),
        "decided_at": row.get("decided_at").isoformat() if row.get("decided_at") is not None else None,
        "decided_by": int(row["decided_by"]) if row.get("decided_by") is not None else None,
        "decision_basis": row.get("decision_basis"),
    }


def count_pending_diff_removals(conn: Connection, batch_id: int) -> int:
    if not diff_removal_decisions_available(conn):
        return int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.hr_import_diff_removals
                    WHERE batch_id = :batch_id
                    """
                ),
                {"batch_id": batch_id},
            ).scalar_one()
            or 0
        )
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.hr_import_diff_removals
                WHERE batch_id = :batch_id
                  AND decision IS NULL
                """
            ),
            {"batch_id": batch_id},
        ).scalar_one()
        or 0
    )


def stash_removal_decisions(conn: Connection, batch_id: int) -> dict[int, dict[str, Any]]:
    """Preserve operator decisions before diff recompute clears removal rows."""
    if not diff_removal_decisions_available(conn):
        return {}
    rows = conn.execute(
        text(
            """
            SELECT canonical_entry_id, decision, decided_at, decided_by, decision_basis
            FROM public.hr_import_diff_removals
            WHERE batch_id = :batch_id
              AND decision IS NOT NULL
            """
        ),
        {"batch_id": batch_id},
    ).mappings().all()
    return {int(row["canonical_entry_id"]): dict(row) for row in rows}


def restore_removal_decisions(
    conn: Connection,
    batch_id: int,
    decisions_by_entry: dict[int, dict[str, Any]],
) -> None:
    if not diff_removal_decisions_available(conn) or not decisions_by_entry:
        return
    for canonical_entry_id, decision_row in decisions_by_entry.items():
        conn.execute(
            text(
                """
                UPDATE public.hr_import_diff_removals
                SET
                    decision = :decision,
                    decided_at = :decided_at,
                    decided_by = :decided_by,
                    decision_basis = :decision_basis
                WHERE batch_id = :batch_id
                  AND canonical_entry_id = :canonical_entry_id
                """
            ),
            {
                "batch_id": batch_id,
                "canonical_entry_id": canonical_entry_id,
                "decision": decision_row["decision"],
                "decided_at": decision_row["decided_at"],
                "decided_by": decision_row["decided_by"],
                "decision_basis": decision_row.get("decision_basis"),
            },
        )


def _entity_scope_for_removal(*, record_kind: str, match_key: str) -> str:
    if record_kind == RECORD_KIND_ROSTER:
        return match_key
    parts = match_key.split("|")
    if len(parts) >= 2:
        return f"{parts[0]}|{parts[1]}"
    return match_key


def collect_restored_removal_snapshot_entries(conn: Connection, batch_id: int) -> list[dict[str, Any]]:
    """Carry-forward entries for operator restore decisions (MRD / baseline composition)."""
    if not diff_removal_decisions_available(conn):
        return []
    rows = conn.execute(
        text(
            """
            SELECT
                removal_id,
                match_key,
                record_kind,
                canonical_hash,
                payload,
                decision
            FROM public.hr_import_diff_removals
            WHERE batch_id = :batch_id
              AND decision = :restore
            ORDER BY removal_id
            """
        ),
        {"batch_id": batch_id, "restore": DECISION_RESTORE},
    ).mappings().all()

    entries: list[dict[str, Any]] = []
    for row in rows:
        record_kind = str(row["record_kind"])
        match_key = str(row["match_key"])
        payload = dict(row.get("payload") or {})
        entity_scope = _entity_scope_for_removal(record_kind=record_kind, match_key=match_key)
        canonical_hash = str(row.get("canonical_hash") or "") or compute_canonical_hash(
            record_kind=record_kind,
            entity_scope=entity_scope,
            payload=payload,
        )
        employee_id = payload.get("employee_id")
        entries.append(
            {
                "entity_scope": entity_scope,
                "record_kind": record_kind,
                "match_key": match_key,
                "canonical_hash": canonical_hash,
                "employee_id": int(employee_id) if employee_id is not None else None,
                "iin": payload.get("iin") or None,
                "payload": payload,
                "source_row_id": None,
                "source_normalized_record_id": None,
                "carried_from_removal_id": int(row["removal_id"]),
            }
        )
    return entries


def collect_mrd_forming_entries_from_batch(conn: Connection, batch_id: int) -> list[dict[str, Any]]:
    """Public read model: import-approved entries + restore decisions (excludes confirm_removal)."""
    from app.services.hr_canonical_snapshot_service import (
        _collect_snapshot_entries,
        dedupe_snapshot_entries,
    )

    entries = _collect_snapshot_entries(conn, batch_id)
    entries.extend(collect_restored_removal_snapshot_entries(conn, batch_id))
    deduped, _merged = dedupe_snapshot_entries(entries)
    return deduped


def record_diff_removal_decision(
    conn: Connection,
    removal_id: int,
    *,
    decision: str,
    decided_by: int,
    decision_basis: Optional[str] = None,
    expected_batch_id: Optional[int] = None,
) -> dict[str, Any]:
    if not diff_removal_decisions_available(conn):
        raise RuntimeError("hr_import_diff_removals.decision column is not available")
    normalized = str(decision or "").strip().lower()
    if normalized not in DECISION_VALUES:
        raise InvalidDiffRemovalDecisionError(
            f"invalid decision {decision!r}; expected restore or confirm_removal"
        )

    row = conn.execute(
        text(
            """
            SELECT *
            FROM public.hr_import_diff_removals
            WHERE removal_id = :removal_id
            FOR UPDATE
            """
        ),
        {"removal_id": removal_id},
    ).mappings().first()
    if row is None:
        raise DiffRemovalNotFoundError(removal_id)

    batch_id = int(row["batch_id"])
    if expected_batch_id is not None and batch_id != int(expected_batch_id):
        raise DiffRemovalNotFoundError(removal_id)
    _ensure_batch_exists(conn, batch_id)

    current_decision = row.get("decision")
    if current_decision is not None:
        raise DiffRemovalAlreadyDecidedError(removal_id, decision=str(current_decision))

    decided_at = datetime.now(timezone.utc)
    conn.execute(
        text(
            """
            UPDATE public.hr_import_diff_removals
            SET
                decision = :decision,
                decided_at = :decided_at,
                decided_by = :decided_by,
                decision_basis = :decision_basis
            WHERE removal_id = :removal_id
            """
        ),
        {
            "removal_id": removal_id,
            "decision": normalized,
            "decided_at": decided_at,
            "decided_by": int(decided_by),
            "decision_basis": (decision_basis or "").strip() or None,
        },
    )

    updated = conn.execute(
        text(
            """
            SELECT *
            FROM public.hr_import_diff_removals
            WHERE removal_id = :removal_id
            """
        ),
        {"removal_id": removal_id},
    ).mappings().one()

    from app.services.hr_import_complete_review_service import maybe_auto_complete_import_review

    auto_result = maybe_auto_complete_import_review(conn, batch_id, actor_user_id=int(decided_by))
    serialized = _serialize_removal_row(dict(updated))
    serialized["auto_review"] = auto_result
    return serialized


def _load_diff_removals_for_batch(
    conn: Connection,
    batch_id: int,
    *,
    decision: Optional[str] = None,
) -> list[dict[str, Any]]:
    if not diff_removal_decisions_available(conn):
        return []
    params: dict[str, Any] = {"batch_id": batch_id}
    decision_filter = ""
    if decision is None:
        decision_filter = "AND decision IS NULL"
    else:
        decision_filter = "AND decision = :decision"
        params["decision"] = decision
    rows = conn.execute(
        text(
            f"""
            SELECT
                removal_id,
                batch_id,
                canonical_entry_id,
                match_key,
                record_kind,
                canonical_hash,
                payload,
                diff_status,
                diff_computed_at,
                decision,
                decided_at,
                decided_by,
                decision_basis
            FROM public.hr_import_diff_removals
            WHERE batch_id = :batch_id
              {decision_filter}
            ORDER BY removal_id
            """
        ),
        params,
    ).mappings().all()
    return [_serialize_removal_row(dict(row)) for row in rows]


def list_pending_diff_removals(conn: Connection, batch_id: int) -> list[dict[str, Any]]:
    return _load_diff_removals_for_batch(conn, batch_id, decision=None)


def list_restored_diff_removals(conn: Connection, batch_id: int) -> list[dict[str, Any]]:
    return _load_diff_removals_for_batch(conn, batch_id, decision=DECISION_RESTORE)


def list_confirmed_diff_removals(conn: Connection, batch_id: int) -> list[dict[str, Any]]:
    return _load_diff_removals_for_batch(conn, batch_id, decision=DECISION_CONFIRM_REMOVAL)


def revert_diff_removal_decision(
    conn: Connection,
    removal_id: int,
    *,
    reverted_by: int,
    expected_batch_id: Optional[int] = None,
) -> dict[str, Any]:
    if not diff_removal_decisions_available(conn):
        raise RuntimeError("hr_import_diff_removals.decision column is not available")

    row = conn.execute(
        text(
            """
            SELECT *
            FROM public.hr_import_diff_removals
            WHERE removal_id = :removal_id
            FOR UPDATE
            """
        ),
        {"removal_id": removal_id},
    ).mappings().first()
    if row is None:
        raise DiffRemovalNotFoundError(removal_id)

    batch_id = int(row["batch_id"])
    if expected_batch_id is not None and batch_id != int(expected_batch_id):
        raise DiffRemovalNotFoundError(removal_id)
    _ensure_batch_exists(conn, batch_id)

    if row.get("decision") is None:
        raise DiffRemovalNotDecidedError(removal_id)

    from app.services.hr_baseline_service import _get_baseline_by_batch

    if _get_baseline_by_batch(conn, batch_id) is not None:
        raise DiffRemovalRevertBlockedError(
            removal_id,
            reason="Нельзя отменить решение после публикации эталона по этому импорту.",
        )

    conn.execute(
        text(
            """
            UPDATE public.hr_import_diff_removals
            SET
                decision = NULL,
                decided_at = NULL,
                decided_by = NULL,
                decision_basis = NULL
            WHERE removal_id = :removal_id
            """
        ),
        {"removal_id": removal_id},
    )

    updated = conn.execute(
        text(
            """
            SELECT *
            FROM public.hr_import_diff_removals
            WHERE removal_id = :removal_id
            """
        ),
        {"removal_id": removal_id},
    ).mappings().one()

    from app.services.hr_import_complete_review_service import maybe_reopen_import_review

    reopen_result = maybe_reopen_import_review(conn, batch_id, actor_user_id=int(reverted_by))
    serialized = _serialize_removal_row(dict(updated))
    serialized["reopen_review"] = reopen_result
    return serialized
