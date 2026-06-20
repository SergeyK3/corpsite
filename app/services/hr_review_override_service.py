"""ADR-043 Phase B3 — persistent review override lifecycle service."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.services.hr_override_stewardship_service import (
    StewardshipRuleNotFoundError,
    validate_stewardship_for_override,
)

STATUS_PENDING = "pending_approval"
STATUS_ACTIVE = "active"
STATUS_REJECTED = "rejected"
STATUS_EXPIRED = "expired"
STATUS_REVOKED = "revoked"
STATUS_SUPERSEDED = "superseded"

TERMINAL_STATUSES = frozenset({STATUS_REJECTED, STATUS_EXPIRED, STATUS_REVOKED, STATUS_SUPERSEDED})

EVENT_CREATED = "CREATED"
EVENT_VALUE_CHANGED = "VALUE_CHANGED"
EVENT_APPROVED = "APPROVED"
EVENT_REJECTED = "REJECTED"
EVENT_RECONFIRMED = "RECONFIRMED"
EVENT_MARKED_STALE = "MARKED_STALE"
EVENT_EXPIRED = "EXPIRED"
EVENT_REVOKED = "REVOKED"
EVENT_SUPERSEDED = "SUPERSEDED"

_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    STATUS_PENDING: frozenset({STATUS_ACTIVE, STATUS_REJECTED}),
    STATUS_ACTIVE: frozenset({STATUS_REVOKED, STATUS_EXPIRED, STATUS_SUPERSEDED}),
}


class ReviewOverrideError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ReviewOverrideNotFoundError(ReviewOverrideError):
    pass


class InvalidOverrideTransitionError(ReviewOverrideError):
    pass


def _table_exists(conn: Connection, table: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :table
            LIMIT 1
            """
        ),
        {"table": table},
    ).first()
    return row is not None


def review_overrides_available(conn: Connection) -> bool:
    return _table_exists(conn, "hr_review_overrides") and _table_exists(conn, "hr_review_override_history")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _parse_scope_key(scope_key: str) -> tuple[str, str]:
    if ":" not in scope_key:
        raise ReviewOverrideError(f"invalid scope_key format: {scope_key!r}")
    scope_type, remainder = scope_key.split(":", 1)
    return scope_type, remainder


def _validate_status_transition(from_status: str, to_status: str) -> None:
    allowed = _ALLOWED_TRANSITIONS.get(from_status)
    if allowed is None or to_status not in allowed:
        raise InvalidOverrideTransitionError(
            f"status transition {from_status!r} -> {to_status!r} is not allowed"
        )


def _fetch_override(conn: Connection, override_id: int) -> dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT *
            FROM public.hr_review_overrides
            WHERE override_id = :override_id
            """
        ),
        {"override_id": override_id},
    ).mappings().first()
    if not row:
        raise ReviewOverrideNotFoundError(f"override {override_id} not found")
    return dict(row)


def _write_history(
    conn: Connection,
    *,
    override_id: int,
    scope_key: str,
    field_path: str,
    event_type: str,
    actor_user_id: Optional[int],
    from_status: Optional[str],
    to_status: Optional[str],
    old_value: Any = None,
    new_value: Any = None,
    reason: Optional[str] = None,
    evidence_url: Optional[str] = None,
    basis_diff: Any = None,
    source_batch_id: Optional[int] = None,
    source_snapshot_id: Optional[int] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> int:
    return conn.execute(
        text(
            """
            INSERT INTO public.hr_review_override_history (
                override_id, scope_key, event_type, actor_user_id,
                from_status, to_status, field_path,
                old_value, new_value, reason, evidence_url, basis_diff,
                source_batch_id, source_snapshot_id, metadata
            ) VALUES (
                :override_id, :scope_key, :event_type, :actor_user_id,
                :from_status, :to_status, :field_path,
                CAST(:old_value AS jsonb), CAST(:new_value AS jsonb),
                :reason, :evidence_url, CAST(:basis_diff AS jsonb),
                :source_batch_id, :source_snapshot_id, CAST(:metadata AS jsonb)
            )
            RETURNING history_id
            """
        ),
        {
            "override_id": override_id,
            "scope_key": scope_key,
            "event_type": event_type,
            "actor_user_id": actor_user_id,
            "from_status": from_status,
            "to_status": to_status,
            "field_path": field_path,
            "old_value": _serialize_json(old_value) if old_value is not None else None,
            "new_value": _serialize_json(new_value) if new_value is not None else None,
            "reason": reason,
            "evidence_url": evidence_url,
            "basis_diff": _serialize_json(basis_diff) if basis_diff is not None else None,
            "source_batch_id": source_batch_id,
            "source_snapshot_id": source_snapshot_id,
            "metadata": _serialize_json(metadata or {}),
        },
    ).scalar_one()


def _serialize_override(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "override_id": int(row["override_id"]),
        "scope_type": row["scope_type"],
        "scope_key": row["scope_key"],
        "field_path": row["field_path"],
        "status": row["status"],
        "tier": int(row["tier"]),
        "owner_domain": row["owner_domain"],
        "override_value": row["override_value"],
        "canonical_value": row.get("canonical_value"),
        "stale_flag": bool(row.get("stale_flag")),
        "supersedes_override_id": row.get("supersedes_override_id"),
        "superseded_by_override_id": row.get("superseded_by_override_id"),
    }


def _initial_status_for_tier(
    *,
    tier: int,
    requires_second_approval: bool,
    supersedes_override_id: Optional[int] = None,
) -> str:
    if supersedes_override_id is not None:
        # Pending coexists with active under separate partial unique indexes.
        return STATUS_PENDING
    if tier >= 2 or requires_second_approval:
        return STATUS_PENDING
    return STATUS_ACTIVE


def _mark_superseded(
    conn: Connection,
    *,
    old_override_id: int,
    new_override_id: int,
    actor_user_id: Optional[int],
    reason: Optional[str] = None,
) -> None:
    old = _fetch_override(conn, old_override_id)
    if old["status"] != STATUS_ACTIVE:
        return
    _validate_status_transition(STATUS_ACTIVE, STATUS_SUPERSEDED)
    now = _utcnow()
    conn.execute(
        text(
            """
            UPDATE public.hr_review_overrides
            SET status = :status,
                superseded_by_override_id = :new_id,
                superseded_at = :now,
                updated_at = :now
            WHERE override_id = :override_id
            """
        ),
        {
            "status": STATUS_SUPERSEDED,
            "new_id": new_override_id,
            "now": now,
            "override_id": old_override_id,
        },
    )
    _write_history(
        conn,
        override_id=old_override_id,
        scope_key=old["scope_key"],
        field_path=old["field_path"],
        event_type=EVENT_SUPERSEDED,
        actor_user_id=actor_user_id,
        from_status=STATUS_ACTIVE,
        to_status=STATUS_SUPERSEDED,
        old_value=old["override_value"],
        new_value=old["override_value"],
        reason=reason,
        metadata={"superseded_by_override_id": new_override_id},
    )


def create_override(
    conn: Connection,
    *,
    scope_type: str,
    scope_key: str,
    field_path: str,
    override_value: Any,
    created_by_user_id: int,
    tier: int,
    owner_domain: str,
    creation_channel: str = "override_registry",
    canonical_value: Any = None,
    justification: Optional[str] = None,
    evidence_url: Optional[str] = None,
    person_key: Optional[str] = None,
    assignment_key: Optional[str] = None,
    person_id: Optional[int] = None,
    assignment_id: Optional[int] = None,
    normalized_record_id: Optional[int] = None,
    record_kind: Optional[str] = None,
    source_batch_id: Optional[int] = None,
    source_row_id: Optional[int] = None,
    source_normalized_record_id: Optional[int] = None,
    source_snapshot_id: Optional[int] = None,
    basis_diff: Any = None,
    supersedes_override_id: Optional[int] = None,
    metadata: Optional[dict[str, Any]] = None,
    skip_duplicate_check: bool = False,
) -> dict[str, Any]:
    """Create a persistent override; writes CREATED history row."""
    if not review_overrides_available(conn):
        raise ReviewOverrideError("hr_review_overrides is not available")

    scope_type = scope_type.strip()
    scope_key = scope_key.strip()
    field_path = field_path.strip()

    parsed_type, _ = _parse_scope_key(scope_key)
    if parsed_type != scope_type:
        raise ReviewOverrideError(f"scope_type {scope_type!r} does not match scope_key prefix {parsed_type!r}")

    rule = validate_stewardship_for_override(
        conn,
        field_path=field_path,
        scope_type=scope_type,
        tier=tier,
        owner_domain=owner_domain,
        evidence_url=evidence_url,
        justification=justification,
        for_status=STATUS_ACTIVE,
    )

    initial_status = _initial_status_for_tier(
        tier=tier,
        requires_second_approval=bool(rule["requires_second_approval"]),
        supersedes_override_id=supersedes_override_id,
    )

    if initial_status == STATUS_PENDING:
        validate_stewardship_for_override(
            conn,
            field_path=field_path,
            scope_type=scope_type,
            tier=tier,
            owner_domain=owner_domain,
            evidence_url=evidence_url,
            justification=justification,
            for_status=STATUS_PENDING,
        )

    if supersedes_override_id is not None:
        prior = _fetch_override(conn, int(supersedes_override_id))
        if prior["status"] != STATUS_ACTIVE:
            raise ReviewOverrideError("supersedes_override_id must reference an active override")
        if prior["scope_key"] != scope_key or prior["field_path"] != field_path:
            raise ReviewOverrideError("supersedes override scope/field_path mismatch")

    if not skip_duplicate_check and supersedes_override_id is None:
        existing = conn.execute(
            text(
                """
                SELECT override_id, status
                FROM public.hr_review_overrides
                WHERE scope_key = :scope_key
                  AND field_path = :field_path
                  AND status IN ('active', 'pending_approval')
                LIMIT 1
                """
            ),
            {"scope_key": scope_key, "field_path": field_path},
        ).mappings().first()
        if existing:
            raise ReviewOverrideError(
                f"active or pending override already exists: override_id={existing['override_id']}"
            )

    now = _utcnow()
    approved_by_user_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    if initial_status == STATUS_ACTIVE:
        approved_by_user_id = created_by_user_id
        approved_at = now

    override_id = conn.execute(
        text(
            """
            INSERT INTO public.hr_review_overrides (
                scope_type, scope_key, person_key, assignment_key,
                person_id, assignment_id, normalized_record_id, record_kind,
                field_path, canonical_value, override_value,
                tier, owner_domain, status, persistence_policy,
                created_by_user_id, creation_channel,
                justification, evidence_url,
                source_batch_id, source_row_id, source_normalized_record_id,
                source_snapshot_id, basis_diff,
                approved_by_user_id, approved_at,
                supersedes_override_id, metadata
            ) VALUES (
                :scope_type, :scope_key, :person_key, :assignment_key,
                :person_id, :assignment_id, :normalized_record_id, :record_kind,
                :field_path, CAST(:canonical_value AS jsonb), CAST(:override_value AS jsonb),
                :tier, :owner_domain, :status, :persistence_policy,
                :created_by_user_id, :creation_channel,
                :justification, :evidence_url,
                :source_batch_id, :source_row_id, :source_normalized_record_id,
                :source_snapshot_id, CAST(:basis_diff AS jsonb),
                :approved_by_user_id, :approved_at,
                :supersedes_override_id, CAST(:metadata AS jsonb)
            )
            RETURNING override_id
            """
        ),
        {
            "scope_type": scope_type,
            "scope_key": scope_key,
            "person_key": person_key,
            "assignment_key": assignment_key,
            "person_id": person_id,
            "assignment_id": assignment_id,
            "normalized_record_id": normalized_record_id,
            "record_kind": record_kind,
            "field_path": field_path,
            "canonical_value": _serialize_json(canonical_value) if canonical_value is not None else None,
            "override_value": _serialize_json(override_value),
            "tier": tier,
            "owner_domain": owner_domain,
            "status": initial_status,
            "persistence_policy": rule["persistence_policy_default"],
            "created_by_user_id": created_by_user_id,
            "creation_channel": creation_channel,
            "justification": justification,
            "evidence_url": evidence_url,
            "source_batch_id": source_batch_id,
            "source_row_id": source_row_id,
            "source_normalized_record_id": source_normalized_record_id,
            "source_snapshot_id": source_snapshot_id,
            "basis_diff": _serialize_json(basis_diff) if basis_diff is not None else None,
            "approved_by_user_id": approved_by_user_id,
            "approved_at": approved_at,
            "supersedes_override_id": supersedes_override_id,
            "metadata": _serialize_json(metadata or {}),
        },
    ).scalar_one()

    _write_history(
        conn,
        override_id=int(override_id),
        scope_key=scope_key,
        field_path=field_path,
        event_type=EVENT_CREATED,
        actor_user_id=created_by_user_id,
        from_status=None,
        to_status=initial_status,
        new_value=override_value,
        reason=justification,
        evidence_url=evidence_url,
        basis_diff=basis_diff,
        source_batch_id=source_batch_id,
        source_snapshot_id=source_snapshot_id,
        metadata=metadata,
    )

    return _serialize_override(_fetch_override(conn, int(override_id)))


def approve_override(
    conn: Connection,
    *,
    override_id: int,
    approved_by_user_id: int,
    approval_comment: Optional[str] = None,
) -> dict[str, Any]:
    """Approve a pending Tier 2 override; may supersede prior active override."""
    row = _fetch_override(conn, override_id)
    from_status = row["status"]
    if from_status != STATUS_PENDING:
        raise InvalidOverrideTransitionError(f"approve requires pending_approval, got {from_status!r}")

    if int(row["tier"]) >= 2 and int(approved_by_user_id) == int(row["created_by_user_id"]):
        raise ReviewOverrideError("Tier 2 override requires a different approver than creator")

    _validate_status_transition(from_status, STATUS_ACTIVE)
    now = _utcnow()

    if row.get("supersedes_override_id") is not None:
        _mark_superseded(
            conn,
            old_override_id=int(row["supersedes_override_id"]),
            new_override_id=override_id,
            actor_user_id=approved_by_user_id,
            reason="superseded on approve",
        )

    conn.execute(
        text(
            """
            UPDATE public.hr_review_overrides
            SET status = :status,
                approved_by_user_id = :approved_by,
                approved_at = :approved_at,
                approval_comment = :approval_comment,
                updated_at = :updated_at
            WHERE override_id = :override_id
            """
        ),
        {
            "status": STATUS_ACTIVE,
            "approved_by": approved_by_user_id,
            "approved_at": now,
            "approval_comment": approval_comment,
            "updated_at": now,
            "override_id": override_id,
        },
    )

    _write_history(
        conn,
        override_id=override_id,
        scope_key=row["scope_key"],
        field_path=row["field_path"],
        event_type=EVENT_APPROVED,
        actor_user_id=approved_by_user_id,
        from_status=from_status,
        to_status=STATUS_ACTIVE,
        old_value=row["override_value"],
        new_value=row["override_value"],
        reason=approval_comment,
    )

    return _serialize_override(_fetch_override(conn, override_id))


def reject_override(
    conn: Connection,
    *,
    override_id: int,
    rejected_by_user_id: int,
    reject_reason: str,
) -> dict[str, Any]:
    row = _fetch_override(conn, override_id)
    from_status = row["status"]
    if from_status != STATUS_PENDING:
        raise InvalidOverrideTransitionError(f"reject requires pending_approval, got {from_status!r}")

    _validate_status_transition(from_status, STATUS_REJECTED)
    now = _utcnow()

    conn.execute(
        text(
            """
            UPDATE public.hr_review_overrides
            SET status = :status,
                rejected_by_user_id = :rejected_by,
                rejected_at = :rejected_at,
                reject_reason = :reject_reason,
                updated_at = :updated_at
            WHERE override_id = :override_id
            """
        ),
        {
            "status": STATUS_REJECTED,
            "rejected_by": rejected_by_user_id,
            "rejected_at": now,
            "reject_reason": reject_reason,
            "updated_at": now,
            "override_id": override_id,
        },
    )

    _write_history(
        conn,
        override_id=override_id,
        scope_key=row["scope_key"],
        field_path=row["field_path"],
        event_type=EVENT_REJECTED,
        actor_user_id=rejected_by_user_id,
        from_status=from_status,
        to_status=STATUS_REJECTED,
        old_value=row["override_value"],
        reason=reject_reason,
    )

    return _serialize_override(_fetch_override(conn, override_id))


def revoke_override(
    conn: Connection,
    *,
    override_id: int,
    revoked_by_user_id: int,
    revoke_reason: str,
) -> dict[str, Any]:
    row = _fetch_override(conn, override_id)
    from_status = row["status"]
    if from_status != STATUS_ACTIVE:
        raise InvalidOverrideTransitionError(f"revoke requires active, got {from_status!r}")
    if not revoke_reason or len(revoke_reason.strip()) < 10:
        raise ReviewOverrideError("revoke_reason must be at least 10 characters")

    _validate_status_transition(from_status, STATUS_REVOKED)
    now = _utcnow()

    conn.execute(
        text(
            """
            UPDATE public.hr_review_overrides
            SET status = :status,
                revoked_by_user_id = :revoked_by,
                revoked_at = :revoked_at,
                revoke_reason = :revoke_reason,
                updated_at = :updated_at
            WHERE override_id = :override_id
            """
        ),
        {
            "status": STATUS_REVOKED,
            "revoked_by": revoked_by_user_id,
            "revoked_at": now,
            "revoke_reason": revoke_reason,
            "updated_at": now,
            "override_id": override_id,
        },
    )

    _write_history(
        conn,
        override_id=override_id,
        scope_key=row["scope_key"],
        field_path=row["field_path"],
        event_type=EVENT_REVOKED,
        actor_user_id=revoked_by_user_id,
        from_status=from_status,
        to_status=STATUS_REVOKED,
        old_value=row["override_value"],
        reason=revoke_reason,
    )

    return _serialize_override(_fetch_override(conn, override_id))


def expire_override(
    conn: Connection,
    *,
    override_id: int,
    expire_reason: str,
    actor_user_id: Optional[int] = None,
) -> dict[str, Any]:
    row = _fetch_override(conn, override_id)
    from_status = row["status"]
    if from_status != STATUS_ACTIVE:
        raise InvalidOverrideTransitionError(f"expire requires active, got {from_status!r}")

    _validate_status_transition(from_status, STATUS_EXPIRED)
    now = _utcnow()

    conn.execute(
        text(
            """
            UPDATE public.hr_review_overrides
            SET status = :status,
                expired_at = :expired_at,
                expire_reason = :expire_reason,
                updated_at = :updated_at
            WHERE override_id = :override_id
            """
        ),
        {
            "status": STATUS_EXPIRED,
            "expired_at": now,
            "expire_reason": expire_reason,
            "updated_at": now,
            "override_id": override_id,
        },
    )

    _write_history(
        conn,
        override_id=override_id,
        scope_key=row["scope_key"],
        field_path=row["field_path"],
        event_type=EVENT_EXPIRED,
        actor_user_id=actor_user_id,
        from_status=from_status,
        to_status=STATUS_EXPIRED,
        old_value=row["override_value"],
        reason=expire_reason,
    )

    return _serialize_override(_fetch_override(conn, override_id))


def mark_stale(
    conn: Connection,
    *,
    override_id: int,
    stale_reason: str,
    actor_user_id: Optional[int] = None,
) -> dict[str, Any]:
    row = _fetch_override(conn, override_id)
    if row["status"] != STATUS_ACTIVE:
        raise InvalidOverrideTransitionError("mark_stale requires active override")
    if not stale_reason or not stale_reason.strip():
        raise ReviewOverrideError("stale_reason is required")

    now = _utcnow()
    conn.execute(
        text(
            """
            UPDATE public.hr_review_overrides
            SET stale_flag = TRUE,
                stale_reason = :stale_reason,
                stale_since = :stale_since,
                updated_at = :updated_at
            WHERE override_id = :override_id
            """
        ),
        {
            "stale_reason": stale_reason,
            "stale_since": now,
            "updated_at": now,
            "override_id": override_id,
        },
    )

    _write_history(
        conn,
        override_id=override_id,
        scope_key=row["scope_key"],
        field_path=row["field_path"],
        event_type=EVENT_MARKED_STALE,
        actor_user_id=actor_user_id,
        from_status=STATUS_ACTIVE,
        to_status=STATUS_ACTIVE,
        old_value=row["override_value"],
        new_value=row["override_value"],
        reason=stale_reason,
        metadata={"stale_reason": stale_reason},
    )

    return _serialize_override(_fetch_override(conn, override_id))


def reconfirm_override(
    conn: Connection,
    *,
    override_id: int,
    reconfirmed_by_user_id: int,
    reason: Optional[str] = None,
) -> dict[str, Any]:
    row = _fetch_override(conn, override_id)
    if row["status"] != STATUS_ACTIVE:
        raise InvalidOverrideTransitionError("reconfirm requires active override")

    now = _utcnow()
    conn.execute(
        text(
            """
            UPDATE public.hr_review_overrides
            SET stale_flag = FALSE,
                stale_reason = NULL,
                stale_since = NULL,
                last_reconfirmed_at = :reconfirmed_at,
                last_reconfirmed_by_user_id = :reconfirmed_by,
                updated_at = :updated_at
            WHERE override_id = :override_id
            """
        ),
        {
            "reconfirmed_at": now,
            "reconfirmed_by": reconfirmed_by_user_id,
            "updated_at": now,
            "override_id": override_id,
        },
    )

    _write_history(
        conn,
        override_id=override_id,
        scope_key=row["scope_key"],
        field_path=row["field_path"],
        event_type=EVENT_RECONFIRMED,
        actor_user_id=reconfirmed_by_user_id,
        from_status=STATUS_ACTIVE,
        to_status=STATUS_ACTIVE,
        old_value=row["override_value"],
        new_value=row["override_value"],
        reason=reason,
    )

    return _serialize_override(_fetch_override(conn, override_id))


def supersede_override(
    conn: Connection,
    *,
    old_override_id: int,
    new_override_value: Any,
    created_by_user_id: int,
    justification: Optional[str] = None,
    evidence_url: Optional[str] = None,
    approval_comment: Optional[str] = None,
    approved_by_user_id: Optional[int] = None,
) -> dict[str, Any]:
    """Replace an active override with a new row (may be pending for Tier 2)."""
    old = _fetch_override(conn, old_override_id)
    if old["status"] != STATUS_ACTIVE:
        raise ReviewOverrideError("supersede requires an active override")

    created = create_override(
        conn,
        scope_type=old["scope_type"],
        scope_key=old["scope_key"],
        field_path=old["field_path"],
        override_value=new_override_value,
        created_by_user_id=created_by_user_id,
        tier=int(old["tier"]),
        owner_domain=old["owner_domain"],
        creation_channel=old["creation_channel"],
        canonical_value=old.get("canonical_value"),
        justification=justification or old.get("justification"),
        evidence_url=evidence_url or old.get("evidence_url"),
        person_key=old.get("person_key"),
        assignment_key=old.get("assignment_key"),
        person_id=old.get("person_id"),
        assignment_id=old.get("assignment_id"),
        normalized_record_id=old.get("normalized_record_id"),
        record_kind=old.get("record_kind"),
        source_batch_id=old.get("source_batch_id"),
        source_snapshot_id=old.get("source_snapshot_id"),
        basis_diff=old.get("basis_diff"),
        supersedes_override_id=old_override_id,
    )

    if created["status"] == STATUS_PENDING:
        approver = approved_by_user_id
        if approver is None and int(old["tier"]) < 2:
            approver = created_by_user_id
        if approver is not None:
            return approve_override(
                conn,
                override_id=int(created["override_id"]),
                approved_by_user_id=approver,
                approval_comment=approval_comment,
            )

    return created


# ---------------------------------------------------------------------------
# Connection helpers (optional standalone transactions)
# ---------------------------------------------------------------------------


def create_override_tx(**kwargs: Any) -> dict[str, Any]:
    with engine.begin() as conn:
        return create_override(conn, **kwargs)


def approve_override_tx(**kwargs: Any) -> dict[str, Any]:
    with engine.begin() as conn:
        return approve_override(conn, **kwargs)


def reject_override_tx(**kwargs: Any) -> dict[str, Any]:
    with engine.begin() as conn:
        return reject_override(conn, **kwargs)


def revoke_override_tx(**kwargs: Any) -> dict[str, Any]:
    with engine.begin() as conn:
        return revoke_override(conn, **kwargs)


def expire_override_tx(**kwargs: Any) -> dict[str, Any]:
    with engine.begin() as conn:
        return expire_override(conn, **kwargs)


def mark_stale_tx(**kwargs: Any) -> dict[str, Any]:
    with engine.begin() as conn:
        return mark_stale(conn, **kwargs)


def reconfirm_override_tx(**kwargs: Any) -> dict[str, Any]:
    with engine.begin() as conn:
        return reconfirm_override(conn, **kwargs)


def supersede_override_tx(**kwargs: Any) -> dict[str, Any]:
    with engine.begin() as conn:
        return supersede_override(conn, **kwargs)
