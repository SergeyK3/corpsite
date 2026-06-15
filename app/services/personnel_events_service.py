# FILE: app/services/personnel_events_service.py
"""Shared personnel event creation pipeline (ADR-036 Phase 1A)."""
from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy import text

from app.db.engine import engine
from app.services.directory_service import (
    _insert_employee_event,
    _normalize_employee_id_text,
)
from app.services.hr_event_registry import get_event_def, is_creatable_in_phase_1a


def _parse_effective_date(payload: Dict[str, Any]) -> date:
    raw = payload.get("effective_date")
    if raw is None:
        raise HTTPException(status_code=422, detail="effective_date is required.")
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="effective_date must be a valid date.") from exc
    raise HTTPException(status_code=422, detail="effective_date must be a valid date.")


def _parse_optional_rate(payload: Dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        if key in payload and payload[key] is not None:
            rate = float(payload[key])
            if rate <= 0 or rate > 2:
                raise HTTPException(status_code=422, detail="employment_rate must be > 0 and <= 2.")
            return rate
    return None


def _parse_metadata(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw = payload.get("metadata")
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    raise HTTPException(status_code=422, detail="metadata must be an object.")


def _fetch_employee_snapshot(conn, *, employee_id_text: str, for_update: bool = True) -> Dict[str, Any]:
    lock = "FOR UPDATE" if for_update else ""
    row = conn.execute(
        text(
            f"""
            SELECT
                employee_id,
                org_unit_id,
                position_id,
                employment_rate,
                is_active
            FROM public.employees
            WHERE CAST(employee_id AS TEXT) = :id_text
            {lock}
            """
        ),
        {"id_text": employee_id_text},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Employee not found.")
    return dict(row)


def _validate_position_exists(conn, position_id: int) -> None:
    pos_row = conn.execute(
        text("SELECT position_id FROM public.positions WHERE position_id = :position_id LIMIT 1"),
        {"position_id": int(position_id)},
    ).first()
    if pos_row is None:
        raise HTTPException(status_code=404, detail="Position not found.")


def _validate_org_unit_exists(conn, unit_id: int) -> None:
    org_row = conn.execute(
        text("SELECT unit_id FROM public.org_units WHERE unit_id = :unit_id LIMIT 1"),
        {"unit_id": int(unit_id)},
    ).first()
    if org_row is None:
        raise HTTPException(status_code=404, detail="Org unit not found.")


def create_personnel_event(
    *,
    employee_id: str,
    event_type: str,
    payload: Dict[str, Any],
    created_by: int,
) -> Dict[str, Any]:
    normalized_type = (event_type or "").strip().upper()
    defn = get_event_def(normalized_type)
    if defn is None:
        raise HTTPException(status_code=422, detail=f"Unknown event_type: {event_type}")

    if not is_creatable_in_phase_1a(normalized_type):
        raise HTTPException(
            status_code=422,
            detail=f"Event type {normalized_type} is not supported for creation in Phase 1A.",
        )

    target_id_text = _normalize_employee_id_text(employee_id)
    if not target_id_text:
        raise HTTPException(status_code=404, detail="Employee not found.")

    effective_date = _parse_effective_date(payload)
    order_ref = payload.get("order_ref")
    comment = payload.get("comment")
    metadata = _parse_metadata(payload)

    with engine.begin() as conn:
        snapshot = _fetch_employee_snapshot(conn, employee_id_text=target_id_text)
        emp_id = int(snapshot["employee_id"])
        is_active = snapshot.get("is_active")

        if normalized_type in {"TRANSFER", "POSITION_CHANGE", "RATE_CHANGE"} and is_active is False:
            raise HTTPException(status_code=409, detail="Employee is inactive.")

        from_org_unit_id = int(snapshot["org_unit_id"])
        from_position_raw = snapshot.get("position_id")
        from_position_id = int(from_position_raw) if from_position_raw is not None else None
        from_rate_raw = snapshot.get("employment_rate")
        from_rate = float(from_rate_raw) if from_rate_raw is not None else None

        if normalized_type == "TRANSFER":
            event_row = _handle_transfer(
                conn,
                emp_id=emp_id,
                payload=payload,
                effective_date=effective_date,
                from_org_unit_id=from_org_unit_id,
                from_position_id=from_position_id,
                from_rate=from_rate,
                order_ref=order_ref,
                comment=comment,
                metadata=metadata,
                created_by=created_by,
                defn=defn,
            )
        elif normalized_type == "POSITION_CHANGE":
            event_row = _handle_position_change(
                conn,
                emp_id=emp_id,
                payload=payload,
                effective_date=effective_date,
                from_org_unit_id=from_org_unit_id,
                from_position_id=from_position_id,
                from_rate=from_rate,
                order_ref=order_ref,
                comment=comment,
                metadata=metadata,
                created_by=created_by,
                defn=defn,
            )
        elif normalized_type == "RATE_CHANGE":
            event_row = _handle_rate_change(
                conn,
                emp_id=emp_id,
                payload=payload,
                effective_date=effective_date,
                from_org_unit_id=from_org_unit_id,
                from_position_id=from_position_id,
                from_rate=from_rate,
                order_ref=order_ref,
                comment=comment,
                metadata=metadata,
                created_by=created_by,
                defn=defn,
            )
        else:
            raise HTTPException(status_code=422, detail=f"Unsupported event_type: {normalized_type}")

    return event_row


def _handle_transfer(
    conn,
    *,
    emp_id: int,
    payload: Dict[str, Any],
    effective_date: date,
    from_org_unit_id: int,
    from_position_id: Optional[int],
    from_rate: Optional[float],
    order_ref: Optional[str],
    comment: Optional[str],
    metadata: Optional[Dict[str, Any]],
    created_by: int,
    defn,
) -> Dict[str, Any]:
    to_org_unit_raw = payload.get("to_org_unit_id")
    if to_org_unit_raw is None:
        raise HTTPException(status_code=422, detail="to_org_unit_id is required.")
    to_org_unit_id = int(to_org_unit_raw)
    _validate_org_unit_exists(conn, to_org_unit_id)

    if from_org_unit_id == to_org_unit_id:
        raise HTTPException(
            status_code=422,
            detail="to_org_unit_id must differ from current org unit for transfer.",
        )

    to_position_id = payload.get("to_position_id")
    if to_position_id is not None:
        effective_to_position_id = int(to_position_id)
        _validate_position_exists(conn, effective_to_position_id)
    elif from_position_id is not None:
        effective_to_position_id = from_position_id
    else:
        raise HTTPException(
            status_code=422,
            detail="Current position is missing; choose target position",
        )

    to_rate = _parse_optional_rate(payload, "to_rate", "to_employment_rate")
    effective_to_rate = to_rate if to_rate is not None else (from_rate if from_rate is not None else 1.0)

    conn.execute(
        text(
            """
            UPDATE public.employees
            SET org_unit_id = :org_unit_id,
                position_id = :position_id,
                employment_rate = :employment_rate
            WHERE employee_id = :employee_id
            """
        ),
        {
            "employee_id": emp_id,
            "org_unit_id": to_org_unit_id,
            "position_id": effective_to_position_id,
            "employment_rate": effective_to_rate,
        },
    )
    conn.execute(
        text(
            """
            UPDATE public.users
            SET unit_id = :unit_id
            WHERE employee_id = :employee_id
            """
        ),
        {"employee_id": emp_id, "unit_id": to_org_unit_id},
    )

    return _insert_employee_event(
        conn,
        employee_id=emp_id,
        event_type="TRANSFER",
        event_class=defn.event_class,
        lifecycle_status="APPROVED",
        metadata=metadata,
        effective_date=effective_date,
        from_org_unit_id=from_org_unit_id,
        from_position_id=from_position_id,
        from_rate=from_rate,
        to_org_unit_id=to_org_unit_id,
        to_position_id=effective_to_position_id,
        to_rate=effective_to_rate,
        order_ref=order_ref,
        comment=comment,
        created_by=created_by,
    )


def _handle_position_change(
    conn,
    *,
    emp_id: int,
    payload: Dict[str, Any],
    effective_date: date,
    from_org_unit_id: int,
    from_position_id: Optional[int],
    from_rate: Optional[float],
    order_ref: Optional[str],
    comment: Optional[str],
    metadata: Optional[Dict[str, Any]],
    created_by: int,
    defn,
) -> Dict[str, Any]:
    to_position_raw = payload.get("to_position_id")
    if to_position_raw is None:
        raise HTTPException(status_code=422, detail="to_position_id is required.")
    to_position_id = int(to_position_raw)
    _validate_position_exists(conn, to_position_id)

    if from_position_id is not None and to_position_id == from_position_id:
        raise HTTPException(
            status_code=422,
            detail="to_position_id must differ from current position.",
        )

    to_rate = _parse_optional_rate(payload, "to_rate", "to_employment_rate")
    effective_to_rate = to_rate if to_rate is not None else from_rate

    updates = ["position_id = :position_id"]
    params: Dict[str, Any] = {
        "employee_id": emp_id,
        "position_id": to_position_id,
    }
    if to_rate is not None:
        updates.append("employment_rate = :employment_rate")
        params["employment_rate"] = to_rate

    conn.execute(
        text(f"UPDATE public.employees SET {', '.join(updates)} WHERE employee_id = :employee_id"),
        params,
    )

    return _insert_employee_event(
        conn,
        employee_id=emp_id,
        event_type="POSITION_CHANGE",
        event_class=defn.event_class,
        lifecycle_status="APPROVED",
        metadata=metadata,
        effective_date=effective_date,
        from_org_unit_id=from_org_unit_id,
        from_position_id=from_position_id,
        from_rate=from_rate,
        to_org_unit_id=from_org_unit_id,
        to_position_id=to_position_id,
        to_rate=effective_to_rate,
        order_ref=order_ref,
        comment=comment,
        created_by=created_by,
    )


def _handle_rate_change(
    conn,
    *,
    emp_id: int,
    payload: Dict[str, Any],
    effective_date: date,
    from_org_unit_id: int,
    from_position_id: Optional[int],
    from_rate: Optional[float],
    order_ref: Optional[str],
    comment: Optional[str],
    metadata: Optional[Dict[str, Any]],
    created_by: int,
    defn,
) -> Dict[str, Any]:
    to_rate = _parse_optional_rate(payload, "to_rate", "to_employment_rate")
    if to_rate is None:
        raise HTTPException(status_code=422, detail="to_rate is required.")

    if from_rate is not None and to_rate == from_rate:
        raise HTTPException(
            status_code=422,
            detail="to_rate must differ from current employment rate.",
        )

    conn.execute(
        text(
            """
            UPDATE public.employees
            SET employment_rate = :employment_rate
            WHERE employee_id = :employee_id
            """
        ),
        {"employee_id": emp_id, "employment_rate": to_rate},
    )

    return _insert_employee_event(
        conn,
        employee_id=emp_id,
        event_type="RATE_CHANGE",
        event_class=defn.event_class,
        lifecycle_status="APPROVED",
        metadata=metadata,
        effective_date=effective_date,
        from_org_unit_id=from_org_unit_id,
        from_position_id=from_position_id,
        from_rate=from_rate,
        to_org_unit_id=from_org_unit_id,
        to_position_id=from_position_id,
        to_rate=to_rate,
        order_ref=order_ref,
        comment=comment,
        created_by=created_by,
    )
