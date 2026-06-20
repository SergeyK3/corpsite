"""ADR-042 Phase B4 — enrollment queue decisions and apply."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.services.security_audit_service import write_security_event

_ACTIVE_QUEUE = ("PENDING", "APPROVED")
_TERMINAL_QUEUE = ("REJECTED", "ENROLLED", "SUPERSEDED")


def _table_exists(conn: Connection, table: str) -> bool:
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


def _serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    for key in ("detected_at", "resolved_at", "created_at", "updated_at"):
        val = out.get(key)
        if isinstance(val, datetime):
            out[key] = val.isoformat()
    return out


def _fetch_queue_item(conn: Connection, queue_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT *
            FROM public.enrollment_queue
            WHERE queue_id = :queue_id
            LIMIT 1
            """
        ),
        {"queue_id": int(queue_id)},
    ).mappings().first()
    return dict(row) if row else None


def _write_history(
    conn: Connection,
    *,
    queue_id: int,
    event_type: str,
    actor_user_id: Optional[int],
    person_id: Optional[int] = None,
    assignment_id: Optional[int] = None,
    employee_id: Optional[int] = None,
    link_id: Optional[int] = None,
    comment: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO public.enrollment_history (
                queue_id,
                event_type,
                actor_user_id,
                person_id,
                assignment_id,
                employee_id,
                link_id,
                comment,
                metadata
            )
            VALUES (
                :queue_id,
                :event_type,
                :actor_user_id,
                :person_id,
                :assignment_id,
                :employee_id,
                :link_id,
                :comment,
                CAST(:metadata AS jsonb)
            )
            """
        ),
        {
            "queue_id": int(queue_id),
            "event_type": event_type,
            "actor_user_id": actor_user_id,
            "person_id": person_id,
            "assignment_id": assignment_id,
            "employee_id": employee_id,
            "link_id": link_id,
            "comment": comment,
            "metadata": json.dumps(metadata or {}),
        },
    )


def list_enrollment_queue(
    *,
    queue_status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    filters = ["1=1"]
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    if queue_status:
        filters.append("queue_status = :queue_status")
        params["queue_status"] = queue_status.strip().upper()

    where_sql = " AND ".join(filters)

    with engine.connect() as conn:
        if not _table_exists(conn, "enrollment_queue"):
            return {"items": [], "total": 0, "limit": limit, "offset": offset}

        total = int(
            conn.execute(
                text(f"SELECT COUNT(*) FROM public.enrollment_queue WHERE {where_sql}"),
                params,
            ).scalar_one()
        )
        rows = conn.execute(
            text(
                f"""
                SELECT
                    queue_id,
                    person_id,
                    assignment_id,
                    change_event_id,
                    canonical_entry_id,
                    queue_status,
                    reason,
                    detected_at,
                    resolved_at,
                    resolved_by_user_id,
                    decision_comment,
                    idempotency_key,
                    created_at,
                    updated_at
                FROM public.enrollment_queue
                WHERE {where_sql}
                ORDER BY detected_at DESC, queue_id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings().all()

    return {
        "items": [_serialize_row(dict(r)) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def approve_enrollment(
    *,
    queue_id: int,
    actor_user_id: int,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    with engine.begin() as conn:
        item = _fetch_queue_item(conn, int(queue_id))
        if not item:
            raise ValueError(f"Queue item not found: {queue_id}")
        if item["queue_status"] != "PENDING":
            raise ValueError(f"Queue item is not PENDING: {item['queue_status']}")

        conn.execute(
            text(
                """
                UPDATE public.enrollment_queue
                SET
                    queue_status = 'APPROVED',
                    resolved_by_user_id = :actor_user_id,
                    decision_comment = :comment,
                    updated_at = now()
                WHERE queue_id = :queue_id
                """
            ),
            {
                "queue_id": int(queue_id),
                "actor_user_id": int(actor_user_id),
                "comment": comment,
            },
        )

        _write_history(
            conn,
            queue_id=int(queue_id),
            event_type="APPROVED",
            actor_user_id=int(actor_user_id),
            person_id=item.get("person_id"),
            assignment_id=item.get("assignment_id"),
            comment=comment,
            metadata={"source": "approve_enrollment"},
        )

        audit_id = write_security_event(
            event_type="ENROLLMENT_APPROVED",
            actor_user_id=int(actor_user_id),
            target_person_id=int(item["person_id"]) if item.get("person_id") else None,
            metadata={
                "queue_id": int(queue_id),
                "reason": item.get("reason"),
                "assignment_id": item.get("assignment_id"),
            },
            conn=conn,
        )

    updated = list_enrollment_queue(limit=1, offset=0)
    item_out = next((i for i in updated["items"] if i["queue_id"] == int(queue_id)), None)
    if item_out is None:
        with engine.connect() as conn:
            row = _fetch_queue_item(conn, int(queue_id))
            item_out = _serialize_row(row) if row else {"queue_id": int(queue_id), "queue_status": "APPROVED"}

    return {**item_out, "audit_id": audit_id}


def reject_enrollment(
    *,
    queue_id: int,
    actor_user_id: int,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    with engine.begin() as conn:
        item = _fetch_queue_item(conn, int(queue_id))
        if not item:
            raise ValueError(f"Queue item not found: {queue_id}")
        if item["queue_status"] not in _ACTIVE_QUEUE:
            raise ValueError(f"Queue item cannot be rejected: {item['queue_status']}")

        conn.execute(
            text(
                """
                UPDATE public.enrollment_queue
                SET
                    queue_status = 'REJECTED',
                    resolved_at = now(),
                    resolved_by_user_id = :actor_user_id,
                    decision_comment = :comment,
                    updated_at = now()
                WHERE queue_id = :queue_id
                """
            ),
            {
                "queue_id": int(queue_id),
                "actor_user_id": int(actor_user_id),
                "comment": comment,
            },
        )

        _write_history(
            conn,
            queue_id=int(queue_id),
            event_type="REJECTED",
            actor_user_id=int(actor_user_id),
            person_id=item.get("person_id"),
            assignment_id=item.get("assignment_id"),
            comment=comment,
            metadata={"source": "reject_enrollment"},
        )

        audit_id = write_security_event(
            event_type="ENROLLMENT_REJECTED",
            actor_user_id=int(actor_user_id),
            target_person_id=int(item["person_id"]) if item.get("person_id") else None,
            metadata={
                "queue_id": int(queue_id),
                "reason": item.get("reason"),
                "comment": comment,
            },
            conn=conn,
        )

    with engine.connect() as conn:
        row = _fetch_queue_item(conn, int(queue_id))
        item_out = _serialize_row(row) if row else {"queue_id": int(queue_id), "queue_status": "REJECTED"}

    return {**item_out, "audit_id": audit_id}


def approve_enrollment_bulk(
    *,
    queue_ids: List[int],
    actor_user_id: int,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    for queue_id in queue_ids:
        try:
            results.append(
                approve_enrollment(
                    queue_id=int(queue_id),
                    actor_user_id=int(actor_user_id),
                    comment=comment,
                )
            )
        except ValueError as exc:
            errors.append({"queue_id": int(queue_id), "error": str(exc)})
    return {
        "processed": len(queue_ids),
        "succeeded": len(results),
        "failed": len(errors),
        "items": results,
        "errors": errors,
    }


def reject_enrollment_bulk(
    *,
    queue_ids: List[int],
    actor_user_id: int,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    for queue_id in queue_ids:
        try:
            results.append(
                reject_enrollment(
                    queue_id=int(queue_id),
                    actor_user_id=int(actor_user_id),
                    comment=comment,
                )
            )
        except ValueError as exc:
            errors.append({"queue_id": int(queue_id), "error": str(exc)})
    return {
        "processed": len(queue_ids),
        "succeeded": len(results),
        "failed": len(errors),
        "items": results,
        "errors": errors,
    }


def _resolve_assignment_context(
    conn: Connection,
    *,
    person_id: Optional[int],
    assignment_id: Optional[int],
) -> Dict[str, Any]:
    if assignment_id is not None:
        row = conn.execute(
            text(
                """
                SELECT
                    pa.assignment_id,
                    pa.person_id,
                    pa.org_unit_id,
                    pa.position_id,
                    pa.department_id,
                    pa.rate,
                    pa.start_date,
                    pa.end_date,
                    pa.active_flag,
                    pa.is_primary,
                    p.full_name
                FROM public.person_assignments pa
                JOIN public.persons p ON p.person_id = pa.person_id
                WHERE pa.assignment_id = :assignment_id
                LIMIT 1
                """
            ),
            {"assignment_id": int(assignment_id)},
        ).mappings().first()
        if not row:
            raise ValueError(f"Assignment not found: {assignment_id}")
        return dict(row)

    if person_id is not None:
        row = conn.execute(
            text(
                """
                SELECT
                    pa.assignment_id,
                    pa.person_id,
                    pa.org_unit_id,
                    pa.position_id,
                    pa.department_id,
                    pa.rate,
                    pa.start_date,
                    pa.end_date,
                    pa.active_flag,
                    pa.is_primary,
                    p.full_name
                FROM public.person_assignments pa
                JOIN public.persons p ON p.person_id = pa.person_id
                WHERE pa.person_id = :person_id
                  AND pa.is_primary = TRUE
                  AND pa.lifecycle_status = 'active'
                ORDER BY pa.assignment_id
                LIMIT 1
                """
            ),
            {"person_id": int(person_id)},
        ).mappings().first()
        if not row:
            raise ValueError(f"No primary assignment for person: {person_id}")
        return dict(row)

    raise ValueError("person_id or assignment_id is required")


def _find_employee_for_person(conn: Connection, person_id: int) -> Optional[int]:
    row = conn.execute(
        text(
            """
            SELECT employee_id
            FROM public.employees
            WHERE person_id = :person_id
            ORDER BY employee_id
            LIMIT 1
            """
        ),
        {"person_id": int(person_id)},
    ).mappings().first()
    return int(row["employee_id"]) if row else None


def _create_employee_for_assignment(
    conn: Connection,
    *,
    ctx: Dict[str, Any],
    actor_user_id: int,
) -> int:
    cols = {
        r[0]
        for r in conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'employees'
                """
            )
        ).fetchall()
    }

    values: Dict[str, Any] = {
        "full_name": ctx.get("full_name") or "Unknown",
        "person_id": int(ctx["person_id"]),
        "org_unit_id": ctx.get("org_unit_id"),
        "position_id": ctx.get("position_id"),
        "employment_rate": ctx.get("rate") or 1.0,
        "date_from": ctx.get("start_date"),
        "date_to": ctx.get("end_date"),
        "is_active": bool(ctx.get("active_flag", True)),
        "operational_status": "active",
        "enrollment_source": "enrollment",
        "enrolled_at": datetime.now(timezone.utc),
        "enrolled_by_user_id": int(actor_user_id),
    }
    if "department_id" in cols:
        values["department_id"] = ctx.get("department_id")

    insert_cols = [k for k in values if k in cols]
    col_sql = ", ".join(insert_cols)
    bind_sql = ", ".join(f":{k}" for k in insert_cols)
    row = conn.execute(
        text(
            f"""
            INSERT INTO public.employees ({col_sql})
            VALUES ({bind_sql})
            RETURNING employee_id
            """
        ),
        {k: values[k] for k in insert_cols},
    ).first()
    return int(row[0])


def _ensure_assignment_link(
    conn: Connection,
    *,
    employee_id: int,
    assignment_id: int,
    actor_user_id: int,
    queue_id: int,
) -> int:
    existing = conn.execute(
        text(
            """
            SELECT link_id, link_status
            FROM public.employee_assignment_links
            WHERE employee_id = :employee_id
              AND assignment_id = :assignment_id
            LIMIT 1
            """
        ),
        {"employee_id": int(employee_id), "assignment_id": int(assignment_id)},
    ).mappings().first()

    if existing:
        if existing["link_status"] == "active":
            return int(existing["link_id"])
        conn.execute(
            text(
                """
                UPDATE public.employee_assignment_links
                SET
                    link_status = 'active',
                    enrolled_at = now(),
                    enrolled_by_user_id = :actor_user_id,
                    unenrolled_at = NULL,
                    unenrolled_by_user_id = NULL,
                    enrollment_queue_id = :queue_id
                WHERE link_id = :link_id
                """
            ),
            {
                "link_id": int(existing["link_id"]),
                "actor_user_id": int(actor_user_id),
                "queue_id": int(queue_id),
            },
        )
        return int(existing["link_id"])

    row = conn.execute(
        text(
            """
            INSERT INTO public.employee_assignment_links (
                employee_id,
                assignment_id,
                link_status,
                enrolled_by_user_id,
                enrollment_queue_id
            )
            VALUES (
                :employee_id,
                :assignment_id,
                'active',
                :actor_user_id,
                :queue_id
            )
            RETURNING link_id
            """
        ),
        {
            "employee_id": int(employee_id),
            "assignment_id": int(assignment_id),
            "actor_user_id": int(actor_user_id),
            "queue_id": int(queue_id),
        },
    ).first()
    return int(row[0])


def apply_enrollment(
    *,
    queue_id: int,
    actor_user_id: int,
) -> Dict[str, Any]:
    with engine.begin() as conn:
        item = _fetch_queue_item(conn, int(queue_id))
        if not item:
            raise ValueError(f"Queue item not found: {queue_id}")
        if item["queue_status"] == "ENROLLED":
            return {
                "queue_id": int(queue_id),
                "queue_status": "ENROLLED",
                "already_applied": True,
            }
        if item["queue_status"] != "APPROVED":
            raise ValueError(f"Queue item must be APPROVED before apply: {item['queue_status']}")

        if item.get("reason") == "REMOVED_ASSIGNMENT":
            raise ValueError("REMOVED_ASSIGNMENT apply is not supported in Phase B4")

        ctx = _resolve_assignment_context(
            conn,
            person_id=int(item["person_id"]) if item.get("person_id") else None,
            assignment_id=int(item["assignment_id"]) if item.get("assignment_id") else None,
        )
        person_id = int(ctx["person_id"])
        assignment_id = int(ctx["assignment_id"])

        employee_id = _find_employee_for_person(conn, person_id)
        created_employee = False
        if employee_id is None:
            employee_id = _create_employee_for_assignment(
                conn,
                ctx=ctx,
                actor_user_id=int(actor_user_id),
            )
            created_employee = True

        link_id = _ensure_assignment_link(
            conn,
            employee_id=employee_id,
            assignment_id=assignment_id,
            actor_user_id=int(actor_user_id),
            queue_id=int(queue_id),
        )

        conn.execute(
            text(
                """
                UPDATE public.enrollment_queue
                SET
                    queue_status = 'ENROLLED',
                    resolved_at = now(),
                    resolved_by_user_id = :actor_user_id,
                    person_id = COALESCE(person_id, :person_id),
                    assignment_id = COALESCE(assignment_id, :assignment_id),
                    updated_at = now()
                WHERE queue_id = :queue_id
                """
            ),
            {
                "queue_id": int(queue_id),
                "actor_user_id": int(actor_user_id),
                "person_id": person_id,
                "assignment_id": assignment_id,
            },
        )

        _write_history(
            conn,
            queue_id=int(queue_id),
            event_type="ENROLLED",
            actor_user_id=int(actor_user_id),
            person_id=person_id,
            assignment_id=assignment_id,
            employee_id=employee_id,
            link_id=link_id,
            metadata={
                "source": "apply_enrollment",
                "created_employee": created_employee,
            },
        )

        audit_id = write_security_event(
            event_type="ENROLLMENT_COMPLETED",
            actor_user_id=int(actor_user_id),
            target_person_id=person_id,
            target_employee_id=employee_id,
            metadata={
                "queue_id": int(queue_id),
                "assignment_id": assignment_id,
                "link_id": link_id,
                "created_employee": created_employee,
            },
            conn=conn,
        )

    return {
        "queue_id": int(queue_id),
        "queue_status": "ENROLLED",
        "person_id": person_id,
        "assignment_id": assignment_id,
        "employee_id": employee_id,
        "link_id": link_id,
        "created_employee": created_employee,
        "audit_id": audit_id,
    }
