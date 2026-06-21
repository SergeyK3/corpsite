"""ADR-044 R2.3 — User → Employee linkage review queue (decisions only, no linkage)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.user_linkage_preview_service import (
    CLASSIFICATION_AMBIGUOUS,
    CLASSIFICATION_REVIEW_REQUIRED,
    PHASE_R2,
    run_user_linkage_preview,
)

DECISION_APPROVE = "APPROVE"
DECISION_REJECT = "REJECT"
DECISION_DEFER = "DEFER"
DECISION_PENDING = "PENDING"

ALLOWED_DECISIONS = frozenset({DECISION_APPROVE, DECISION_REJECT, DECISION_DEFER})

REVIEWABLE_CLASSIFICATIONS = frozenset(
    {CLASSIFICATION_REVIEW_REQUIRED, CLASSIFICATION_AMBIGUOUS}
)


class UserLinkageReviewError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class UserLinkageReviewNotFoundError(UserLinkageReviewError):
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


def review_decisions_available(conn: Connection) -> bool:
    return _table_exists(conn, "user_linkage_review_decisions")


def _load_user_names(conn: Connection, user_ids: list[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    rows = conn.execute(
        text(
            """
            SELECT user_id, full_name
            FROM public.users
            WHERE user_id = ANY(:user_ids)
            """
        ),
        {"user_ids": user_ids},
    ).mappings().all()
    return {int(row["user_id"]): str(row.get("full_name") or "") for row in rows}


def _load_latest_decisions(conn: Connection) -> dict[int, dict[str, Any]]:
    if not review_decisions_available(conn):
        return {}
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT ON (user_id)
                decision_id,
                reviewer_user_id,
                user_id,
                proposed_employee_id,
                classification,
                match_strategy,
                decision,
                reason,
                created_at
            FROM public.user_linkage_review_decisions
            ORDER BY user_id, created_at DESC, decision_id DESC
            """
        )
    ).mappings().all()
    return {int(row["user_id"]): dict(row) for row in rows}


def _load_reviewer_logins(conn: Connection, reviewer_ids: list[int]) -> dict[int, str]:
    if not reviewer_ids:
        return {}
    rows = conn.execute(
        text(
            """
            SELECT user_id, login
            FROM public.users
            WHERE user_id = ANY(:user_ids)
            """
        ),
        {"user_ids": reviewer_ids},
    ).mappings().all()
    return {
        int(row["user_id"]): str(row.get("login") or f"user#{row['user_id']}")
        for row in rows
    }


def _normalize_search(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    trimmed = value.strip().lower()
    return trimmed or None


def _matches_search(candidate: dict[str, Any], *, search: Optional[str]) -> bool:
    if not search:
        return True
    haystacks = [
        str(candidate.get("login") or "").lower(),
        str(candidate.get("user_full_name") or "").lower(),
        str(candidate.get("employee_name") or "").lower(),
    ]
    return any(search in haystack for haystack in haystacks if haystack)


def _build_review_summary(candidates: list[dict[str, Any]]) -> dict[str, int]:
    summary = {
        "review_required": 0,
        "ambiguous": 0,
        "approved": 0,
        "rejected": 0,
        "deferred": 0,
        "pending": 0,
    }
    for candidate in candidates:
        classification = candidate["classification"]
        if classification == CLASSIFICATION_REVIEW_REQUIRED:
            summary["review_required"] += 1
        elif classification == CLASSIFICATION_AMBIGUOUS:
            summary["ambiguous"] += 1

        decision_state = candidate.get("decision_state") or DECISION_PENDING
        if decision_state == DECISION_APPROVE:
            summary["approved"] += 1
        elif decision_state == DECISION_REJECT:
            summary["rejected"] += 1
        elif decision_state == DECISION_DEFER:
            summary["deferred"] += 1
        elif decision_state == DECISION_PENDING:
            summary["pending"] += 1
    return summary


def _enrich_candidates(
    conn: Connection,
    preview: dict[str, Any],
    latest_decisions: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates = list(preview.get("candidates") or [])
    user_ids = [int(item["user_id"]) for item in candidates]
    user_names = _load_user_names(conn, user_ids)

    reviewer_ids = [
        int(row["reviewer_user_id"])
        for row in latest_decisions.values()
        if row.get("reviewer_user_id") is not None
    ]
    reviewer_logins = _load_reviewer_logins(conn, reviewer_ids)

    enriched: list[dict[str, Any]] = []
    for candidate in candidates:
        user_id = int(candidate["user_id"])
        latest = latest_decisions.get(user_id)
        decision_state = (
            str(latest["decision"]) if latest and latest.get("decision") else DECISION_PENDING
        )
        reviewer_user_id = int(latest["reviewer_user_id"]) if latest else None
        enriched.append(
            {
                **candidate,
                "user_full_name": user_names.get(user_id, ""),
                "decision_state": decision_state,
                "latest_decision_id": int(latest["decision_id"]) if latest else None,
                "latest_decision_at": (
                    latest["created_at"].isoformat()
                    if latest and latest.get("created_at")
                    else None
                ),
                "reviewer_user_id": reviewer_user_id,
                "reviewer_login": (
                    reviewer_logins.get(reviewer_user_id) if reviewer_user_id else None
                ),
                "decision_reason": latest.get("reason") if latest else None,
            }
        )
    return enriched


def _apply_filters(
    candidates: list[dict[str, Any]],
    *,
    classification: Optional[str],
    strategy: Optional[str],
    decision_state: Optional[str],
    search: Optional[str],
) -> list[dict[str, Any]]:
    login_search = _normalize_search(search)

    filtered: list[dict[str, Any]] = []
    for candidate in candidates:
        if classification and candidate.get("classification") != classification:
            continue
        if strategy and candidate.get("match_strategy") != strategy:
            continue
        if decision_state:
            state = candidate.get("decision_state") or DECISION_PENDING
            if state != decision_state:
                continue
        if login_search and not _matches_search(candidate, search=login_search):
            continue
        filtered.append(candidate)
    return filtered


def list_user_linkage_review_queue(
    conn: Connection,
    *,
    classification: Optional[str] = None,
    strategy: Optional[str] = None,
    decision_state: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Read-only review queue built from preview + persisted decisions."""
    preview = run_user_linkage_preview(conn)
    latest_decisions = _load_latest_decisions(conn)
    enriched = _enrich_candidates(conn, preview, latest_decisions)
    filtered = _apply_filters(
        enriched,
        classification=classification,
        strategy=strategy,
        decision_state=decision_state,
        search=search,
    )
    total = len(filtered)
    page = filtered[offset : offset + limit]
    return {
        "phase": PHASE_R2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": _build_review_summary(enriched),
        "candidates": page,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def _candidate_from_preview(conn: Connection, user_id: int) -> dict[str, Any]:
    preview = run_user_linkage_preview(conn)
    for candidate in preview.get("candidates") or []:
        if int(candidate["user_id"]) == int(user_id):
            return dict(candidate)
    raise UserLinkageReviewNotFoundError(f"review candidate user_id={user_id} not found")


def _assert_employee_id_unchanged(conn: Connection, user_id: int) -> None:
    row = conn.execute(
        text(
            """
            SELECT employee_id
            FROM public.users
            WHERE user_id = :user_id
            """
        ),
        {"user_id": user_id},
    ).mappings().first()
    if not row:
        raise UserLinkageReviewNotFoundError(f"user_id={user_id} not found")
    if row.get("employee_id") is not None:
        raise UserLinkageReviewError(
            f"user_id={user_id} already has employee_id set; review decisions do not apply"
        )


def record_user_linkage_review_decision(
    conn: Connection,
    *,
    actor_user_id: int,
    user_id: int,
    decision: str,
    reason: Optional[str] = None,
) -> dict[str, Any]:
    """Persist reviewer intent only. Never updates users.employee_id."""
    if not review_decisions_available(conn):
        raise UserLinkageReviewError("user_linkage_review_decisions table is not available")

    normalized_decision = str(decision or "").strip().upper()
    if normalized_decision not in ALLOWED_DECISIONS:
        raise UserLinkageReviewError(f"invalid decision: {decision!r}")

    candidate = _candidate_from_preview(conn, user_id)
    classification = str(candidate.get("classification") or "")

    if normalized_decision == DECISION_APPROVE:
        if classification not in REVIEWABLE_CLASSIFICATIONS:
            raise UserLinkageReviewError(
                f"approve is not allowed for classification {classification!r}"
            )
        if candidate.get("proposed_employee_id") is None:
            raise UserLinkageReviewError("approve requires a proposed_employee_id")

    _assert_employee_id_unchanged(conn, user_id)

    row = conn.execute(
        text(
            """
            INSERT INTO public.user_linkage_review_decisions (
                reviewer_user_id,
                user_id,
                proposed_employee_id,
                classification,
                match_strategy,
                decision,
                reason
            ) VALUES (
                :reviewer_user_id,
                :user_id,
                :proposed_employee_id,
                :classification,
                :match_strategy,
                :decision,
                :reason
            )
            RETURNING
                decision_id,
                reviewer_user_id,
                user_id,
                proposed_employee_id,
                classification,
                match_strategy,
                decision,
                reason,
                created_at
            """
        ),
        {
            "reviewer_user_id": int(actor_user_id),
            "user_id": int(user_id),
            "proposed_employee_id": candidate.get("proposed_employee_id"),
            "classification": classification,
            "match_strategy": candidate.get("match_strategy"),
            "decision": normalized_decision,
            "reason": (reason or "").strip() or None,
        },
    ).mappings().one()

    _assert_employee_id_unchanged(conn, user_id)

    return {
        "decision_id": int(row["decision_id"]),
        "reviewer_user_id": int(row["reviewer_user_id"]),
        "user_id": int(row["user_id"]),
        "proposed_employee_id": row.get("proposed_employee_id"),
        "classification": str(row["classification"]),
        "match_strategy": row.get("match_strategy"),
        "decision": str(row["decision"]),
        "reason": row.get("reason"),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


def list_user_linkage_review_audit(
    conn: Connection,
    *,
    user_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    if not review_decisions_available(conn):
        return {"items": [], "total": 0, "limit": limit, "offset": offset}

    params: dict[str, Any] = {"limit": limit, "offset": offset}
    where_clause = ""
    if user_id is not None:
        where_clause = "WHERE d.user_id = :user_id"
        params["user_id"] = int(user_id)

    total = int(
        conn.execute(
            text(
                f"""
                SELECT COUNT(*) AS cnt
                FROM public.user_linkage_review_decisions d
                {where_clause}
                """
            ),
            params,
        ).scalar_one()
    )

    rows = conn.execute(
        text(
            f"""
            SELECT
                d.decision_id,
                d.reviewer_user_id,
                d.user_id,
                u.login AS user_login,
                u.full_name AS user_full_name,
                d.proposed_employee_id,
                e.full_name AS employee_name,
                d.classification,
                d.match_strategy,
                d.decision,
                d.reason,
                d.created_at,
                r.login AS reviewer_login
            FROM public.user_linkage_review_decisions d
            JOIN public.users u ON u.user_id = d.user_id
            LEFT JOIN public.employees e ON e.employee_id = d.proposed_employee_id
            LEFT JOIN public.users r ON r.user_id = d.reviewer_user_id
            {where_clause}
            ORDER BY d.created_at DESC, d.decision_id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()

    items = [
        {
            "decision_id": int(row["decision_id"]),
            "reviewer_user_id": int(row["reviewer_user_id"]),
            "reviewer_login": row.get("reviewer_login"),
            "user_id": int(row["user_id"]),
            "user_login": row.get("user_login"),
            "user_full_name": row.get("user_full_name"),
            "proposed_employee_id": row.get("proposed_employee_id"),
            "employee_name": row.get("employee_name"),
            "classification": str(row["classification"]),
            "match_strategy": row.get("match_strategy"),
            "decision": str(row["decision"]),
            "reason": row.get("reason"),
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        }
        for row in rows
    ]
    return {"items": items, "total": total, "limit": limit, "offset": offset}
