"""ADR-042 Phase B3 — enrollment detector (queue only, no auto employee create)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.db.engine import engine

_EVENT_TO_REASON = {
    "NEW": "NEW_ASSIGNMENT",
    "REMOVED": "REMOVED_ASSIGNMENT",
    "POSITION_CHANGED": "CHANGED_ASSIGNMENT",
    "DEPARTMENT_CHANGED": "CHANGED_ASSIGNMENT",
}

_ACTIVE_QUEUE_STATUSES = ("PENDING", "APPROVED")


def _table_exists(conn, table: str) -> bool:
    return (
        conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = :table
                LIMIT 1
                """
            ),
            {"table": table},
        ).first()
        is not None
    )


def _build_idempotency_key(
    *,
    change_event_id: Optional[int],
    canonical_entry_id: Optional[int],
    reason: str,
    person_id: Optional[int],
    assignment_id: Optional[int],
) -> str:
    anchor = (
        f"ce:{change_event_id}"
        if change_event_id is not None
        else f"entry:{canonical_entry_id}"
        if canonical_entry_id is not None
        else "manual"
    )
    target = assignment_id or person_id or "none"
    return f"{anchor}|{reason}|{target}"


def _resolve_person_assignment_for_event(conn, event: Dict[str, Any]) -> Dict[str, Optional[int]]:
    person_id: Optional[int] = None
    assignment_id: Optional[int] = None

    if event.get("employee_id") is not None:
        row = conn.execute(
            text(
                """
                SELECT e.person_id, pa.assignment_id
                FROM public.employees e
                LEFT JOIN public.person_assignments pa
                  ON pa.person_id = e.person_id
                 AND pa.is_primary = TRUE
                 AND pa.lifecycle_status = 'active'
                WHERE e.employee_id = :employee_id
                LIMIT 1
                """
            ),
            {"employee_id": int(event["employee_id"])},
        ).mappings().first()
        if row:
            person_id = int(row["person_id"]) if row["person_id"] is not None else None
            assignment_id = int(row["assignment_id"]) if row["assignment_id"] is not None else None

    if person_id is None and event.get("match_key"):
        prow = conn.execute(
            text(
                """
                SELECT person_id FROM public.persons
                WHERE match_key = :match_key
                  AND person_status IN ('active', 'inactive')
                LIMIT 1
                """
            ),
            {"match_key": event["match_key"]},
        ).mappings().first()
        if prow:
            person_id = int(prow["person_id"])

    if person_id is not None and assignment_id is None and event.get("new_entry_id"):
        arow = conn.execute(
            text(
                """
                SELECT assignment_id FROM public.person_assignments
                WHERE canonical_entry_id = :entry_id
                LIMIT 1
                """
            ),
            {"entry_id": int(event["new_entry_id"])},
        ).mappings().first()
        if arow:
            assignment_id = int(arow["assignment_id"])

    return {"person_id": person_id, "assignment_id": assignment_id}


def _classify_event(event: Dict[str, Any], conn) -> Optional[str]:
    event_type = (event.get("event_type") or "").upper()
    if event_type in _EVENT_TO_REASON:
        reason = _EVENT_TO_REASON[event_type]
        if event_type == "NEW" and event.get("employee_id") is not None:
            link = conn.execute(
                text(
                    """
                    SELECT 1
                    FROM public.employees e
                    JOIN public.employee_assignment_links l
                      ON l.employee_id = e.employee_id
                     AND l.link_status = 'active'
                    WHERE e.employee_id = :employee_id
                    LIMIT 1
                    """
                ),
                {"employee_id": int(event["employee_id"])},
            ).first()
            if link:
                return None
        return reason

    if event_type == "REMOVED" and event.get("employee_id"):
        return "REMOVED_ASSIGNMENT"
    return None


def explain_candidate(*, queue_id: int) -> Dict[str, Any]:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                    q.*,
                    ce.event_type AS change_event_type,
                    ce.match_key,
                    ce.full_name AS change_full_name,
                    p.full_name AS person_full_name,
                    p.iin AS person_iin,
                    pa.org_unit_id,
                    pa.position_id,
                    ou.name AS org_unit_name,
                    pos.name AS position_name
                FROM public.enrollment_queue q
                LEFT JOIN public.hr_change_events ce
                  ON ce.change_event_id = q.change_event_id
                LEFT JOIN public.persons p
                  ON p.person_id = q.person_id
                LEFT JOIN public.person_assignments pa
                  ON pa.assignment_id = q.assignment_id
                LEFT JOIN public.org_units ou
                  ON ou.unit_id = pa.org_unit_id
                LEFT JOIN public.positions pos
                  ON pos.position_id = pa.position_id
                WHERE q.queue_id = :queue_id
                LIMIT 1
                """
            ),
            {"queue_id": int(queue_id)},
        ).mappings().first()
        if not row:
            raise ValueError(f"Queue item not found: {queue_id}")

        item = dict(row)
        reason_code = str(item.get("reason") or "")
        reason_labels = {
            "NEW_PERSON": "Новый person",
            "NEW_ASSIGNMENT": "Новое назначение",
            "CHANGED_ASSIGNMENT": "Изменение назначения",
            "REMOVED_ASSIGNMENT": "Удаление назначения",
            "RE_ENROLLMENT": "Повторное enrollment",
            "HR_CHANGE": "Событие HR change",
        }
        steps = [
            f"Queue #{item['queue_id']} status={item['queue_status']} reason={item['reason']}",
            f"Причина: {reason_labels.get(reason_code, reason_code or '—')}",
            f"Idempotency key: {item['idempotency_key']}",
        ]
        if item.get("change_event_id"):
            steps.append(
                f"Источник: hr_change_event #{item['change_event_id']} "
                f"type={item.get('change_event_type')}"
            )
        if item.get("person_id"):
            steps.append(f"Person #{item['person_id']}: {item.get('person_full_name') or '—'}")
        if item.get("person_iin"):
            steps.append(f"IIN: {item['person_iin']}")
        if item.get("assignment_id"):
            org = item.get("org_unit_name") or item.get("org_unit_id") or "—"
            pos = item.get("position_name") or item.get("position_id") or "—"
            steps.append(
                f"Assignment #{item['assignment_id']}: подразделение={org}, должность={pos}"
            )
        steps.append("Auto employee creation: disabled until apply.")

        item["explanation"] = {
            "steps": steps,
            "reason_label": reason_labels.get(reason_code, reason_code),
            "person": {
                "person_id": item.get("person_id"),
                "full_name": item.get("person_full_name"),
                "iin": item.get("person_iin"),
            },
            "assignment": {
                "assignment_id": item.get("assignment_id"),
                "org_unit_id": item.get("org_unit_id"),
                "org_unit_name": item.get("org_unit_name"),
                "position_id": item.get("position_id"),
                "position_name": item.get("position_name"),
            },
            "source": {
                "change_event_id": item.get("change_event_id"),
                "change_event_type": item.get("change_event_type"),
            },
        }
        return item


def supersede_stale_queue_items(
    *,
    person_id: Optional[int] = None,
    assignment_id: Optional[int] = None,
    superseded_by_queue_id: Optional[int] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    if person_id is None and assignment_id is None:
        raise ValueError("person_id or assignment_id is required")

    filters = ["queue_status IN ('PENDING', 'APPROVED')"]
    params: Dict[str, Any] = {}
    if person_id is not None:
        filters.append("person_id = :person_id")
        params["person_id"] = int(person_id)
    if assignment_id is not None:
        filters.append("assignment_id = :assignment_id")
        params["assignment_id"] = int(assignment_id)
    if superseded_by_queue_id is not None:
        filters.append("queue_id <> :keep_id")
        params["keep_id"] = int(superseded_by_queue_id)

    where_sql = " AND ".join(filters)

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                f"""
                SELECT queue_id, queue_status, reason, idempotency_key
                FROM public.enrollment_queue
                WHERE {where_sql}
                """
            ),
            params,
        ).mappings().all()

    if dry_run:
        return {"dry_run": True, "would_supersede": [dict(r) for r in rows], "count": len(rows)}

    with engine.begin() as conn:
        for row in rows:
            conn.execute(
                text(
                    """
                    UPDATE public.enrollment_queue
                    SET
                        queue_status = 'SUPERSEDED',
                        resolved_at = now(),
                        superseded_by_queue_id = :superseded_by,
                        updated_at = now()
                    WHERE queue_id = :queue_id
                    """
                ),
                {
                    "queue_id": int(row["queue_id"]),
                    "superseded_by": superseded_by_queue_id,
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO public.enrollment_history (
                        queue_id, event_type, comment, metadata
                    )
                    VALUES (
                        :queue_id, 'SUPERSEDED', :comment, CAST(:metadata AS jsonb)
                    )
                    """
                ),
                {
                    "queue_id": int(row["queue_id"]),
                    "comment": "Superseded by newer candidate",
                    "metadata": '{"source": "supersede_stale_queue_items"}',
                },
            )

    return {"dry_run": False, "superseded_count": len(rows)}


def enqueue_enrollment_candidate(
    *,
    reason: str,
    person_id: Optional[int] = None,
    assignment_id: Optional[int] = None,
    change_event_id: Optional[int] = None,
    canonical_entry_id: Optional[int] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    normalized_reason = (reason or "").strip().upper()
    allowed = {
        "NEW_ASSIGNMENT",
        "CHANGED_ASSIGNMENT",
        "REMOVED_ASSIGNMENT",
        "RE_ENROLL",
        "MANUAL_REQUEST",
    }
    if normalized_reason not in allowed:
        raise ValueError(f"Invalid enrollment reason: {reason}")

    if person_id is None and assignment_id is None and canonical_entry_id is None:
        raise ValueError("person_id, assignment_id, or canonical_entry_id is required")

    idempotency_key = _build_idempotency_key(
        change_event_id=change_event_id,
        canonical_entry_id=canonical_entry_id,
        reason=normalized_reason,
        person_id=person_id,
        assignment_id=assignment_id,
    )

    with engine.connect() as conn:
        existing = conn.execute(
            text(
                """
                SELECT queue_id, queue_status
                FROM public.enrollment_queue
                WHERE idempotency_key = :key
                  AND queue_status IN ('PENDING', 'APPROVED', 'ENROLLED')
                LIMIT 1
                """
            ),
            {"key": idempotency_key},
        ).mappings().first()
        if existing:
            return {
                "queue_id": int(existing["queue_id"]),
                "queue_status": existing["queue_status"],
                "idempotent_hit": True,
                "idempotency_key": idempotency_key,
            }

        rejected = conn.execute(
            text(
                """
                SELECT queue_id FROM public.enrollment_queue
                WHERE idempotency_key = :key AND queue_status = 'REJECTED'
                LIMIT 1
                """
            ),
            {"key": idempotency_key},
        ).first()
        if rejected and change_event_id is None:
            return {
                "skipped": True,
                "reason": "rejected_not_reopened_without_new_event",
                "idempotency_key": idempotency_key,
            }

    if dry_run:
        return {
            "dry_run": True,
            "would_enqueue": True,
            "reason": normalized_reason,
            "idempotency_key": idempotency_key,
            "person_id": person_id,
            "assignment_id": assignment_id,
        }

    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO public.enrollment_queue (
                    person_id,
                    assignment_id,
                    change_event_id,
                    canonical_entry_id,
                    queue_status,
                    reason,
                    idempotency_key
                )
                VALUES (
                    :person_id,
                    :assignment_id,
                    :change_event_id,
                    :canonical_entry_id,
                    'PENDING',
                    :reason,
                    :idempotency_key
                )
                RETURNING queue_id
                """
            ),
            {
                "person_id": person_id,
                "assignment_id": assignment_id,
                "change_event_id": change_event_id,
                "canonical_entry_id": canonical_entry_id,
                "reason": normalized_reason,
                "idempotency_key": idempotency_key,
            },
        ).first()
        queue_id = int(row[0])

        conn.execute(
            text(
                """
                INSERT INTO public.enrollment_history (
                    queue_id, event_type, person_id, assignment_id, metadata
                )
                VALUES (
                    :queue_id, 'DETECTED', :person_id, :assignment_id,
                    CAST(:metadata AS jsonb)
                )
                """
            ),
            {
                "queue_id": queue_id,
                "person_id": person_id,
                "assignment_id": assignment_id,
                "metadata": '{"source": "enqueue_enrollment_candidate"}',
            },
        )

    return {
        "queue_id": queue_id,
        "queue_status": "PENDING",
        "idempotent_hit": False,
        "idempotency_key": idempotency_key,
    }


def detect_enrollment_candidates(
    *,
    batch_id: Optional[int] = None,
    dry_run: bool = True,
    limit: int = 500,
) -> Dict[str, Any]:
    limit = max(1, min(int(limit), 2000))

    with engine.connect() as conn:
        if not _table_exists(conn, "hr_change_events") or not _table_exists(conn, "enrollment_queue"):
            return {"candidates": [], "enqueued": [], "dry_run": dry_run, "skipped": 0}

        filters = ["ce.record_kind = 'roster'"]
        params: Dict[str, Any] = {"limit": limit}

        if batch_id is not None:
            filters.append(
                """
                ce.new_snapshot_id IN (
                    SELECT s.snapshot_id
                    FROM public.hr_canonical_snapshots s
                    WHERE s.source_batch_id = :batch_id
                )
                """
            )
            params["batch_id"] = int(batch_id)

        filters.append(
            """
            NOT EXISTS (
                SELECT 1 FROM public.enrollment_queue q
                WHERE q.change_event_id = ce.change_event_id
                  AND q.queue_status IN ('PENDING', 'APPROVED', 'ENROLLED')
            )
            """
        )
        filters.append("ce.event_type IN ('NEW', 'REMOVED', 'POSITION_CHANGED', 'DEPARTMENT_CHANGED')")

        where_sql = " AND ".join(f"({f})" for f in filters)

        events = conn.execute(
            text(
                f"""
                SELECT
                    ce.change_event_id,
                    ce.event_type,
                    ce.employee_id,
                    ce.match_key,
                    ce.new_entry_id,
                    ce.prior_entry_id,
                    ce.full_name,
                    ce.iin
                FROM public.hr_change_events ce
                WHERE {where_sql}
                ORDER BY ce.event_at DESC, ce.change_event_id DESC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()

    candidates: List[Dict[str, Any]] = []
    enqueued: List[Dict[str, Any]] = []

    for raw in events:
        event = dict(raw)
        with engine.connect() as conn:
            reason = _classify_event(event, conn)
            if not reason:
                continue

            targets = _resolve_person_assignment_for_event(conn, event)

            if event["event_type"] == "NEW" and event.get("employee_id") is None:
                reason = "NEW_ASSIGNMENT"
            elif event["event_type"] == "REMOVED":
                reason = "REMOVED_ASSIGNMENT"
            elif event["event_type"] in ("POSITION_CHANGED", "DEPARTMENT_CHANGED"):
                reason = "CHANGED_ASSIGNMENT" if event.get("employee_id") else "NEW_ASSIGNMENT"

        candidate = {
            "change_event_id": int(event["change_event_id"]),
            "event_type": event["event_type"],
            "reason": reason,
            "person_id": targets["person_id"],
            "assignment_id": targets["assignment_id"],
            "match_key": event.get("match_key"),
        }
        candidates.append(candidate)

        if not dry_run:
            result = enqueue_enrollment_candidate(
                reason=reason,
                person_id=targets["person_id"],
                assignment_id=targets["assignment_id"],
                change_event_id=int(event["change_event_id"]),
                canonical_entry_id=int(event["new_entry_id"]) if event.get("new_entry_id") else None,
                dry_run=False,
            )
            enqueued.append(result)

    return {
        "dry_run": dry_run,
        "batch_id": batch_id,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "enqueued": enqueued,
    }
