"""Org scope resolution for personnel order cancel (WP-PO-LC-DEL-004)."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.directory.rbac import org_units

SCOPE_RULE_UNLIMITED = "unlimited_scope"
SCOPE_RULE_ALL_ITEMS = "all_items_in_scope"
SCOPE_RULE_AUTHOR_UNIT = "author_unit_fallback"
SCOPE_RULE_COMPOSITE_DENIED = "composite_multi_scope_denied"
SCOPE_RULE_AUTHOR_UNIT_MISSING = "author_unit_missing"


def _normalize_unit_id(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 1 else None


def _payload_org_unit_id(payload: Any) -> Optional[int]:
    if payload is None:
        return None
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return None
    if not isinstance(payload, dict):
        return None
    for key in ("org_unit_id", "to_org_unit_id", "from_org_unit_id"):
        unit_id = _normalize_unit_id(payload.get(key))
        if unit_id is not None:
            return unit_id
    return None


def resolve_order_scope_unit_ids(conn: Connection, order_id: int) -> List[int]:
    """Return authoritative org unit ids referenced by order items."""
    rows = conn.execute(
        text(
            """
            SELECT
                i.employee_id,
                i.payload,
                e.org_unit_id AS employee_org_unit_id
            FROM public.personnel_order_items i
            LEFT JOIN public.employees e ON e.employee_id = i.employee_id
            WHERE i.order_id = :order_id
            ORDER BY i.item_number ASC, i.item_id ASC
            """
        ),
        {"order_id": int(order_id)},
    ).mappings().all()

    unit_ids: List[int] = []
    for row in rows:
        employee_unit = _normalize_unit_id(row.get("employee_org_unit_id"))
        if employee_unit is not None:
            unit_ids.append(employee_unit)
            continue
        payload_unit = _payload_org_unit_id(row.get("payload"))
        if payload_unit is not None:
            unit_ids.append(payload_unit)
    return unit_ids


def _fetch_user_unit_id(conn: Connection, user_id: int) -> Optional[int]:
    row = conn.execute(
        text(
            """
            SELECT unit_id
            FROM public.users
            WHERE user_id = :user_id
            LIMIT 1
            """
        ),
        {"user_id": int(user_id)},
    ).mappings().first()
    if row is None:
        return None
    return _normalize_unit_id(row.get("unit_id"))


def resolve_actor_scope_unit_ids(actor_user_id: int, *, conn: Optional[Connection] = None) -> Optional[Set[int]]:
    """Return actor org scope unit ids, or None when scope is unlimited."""
    try:
        if conn is not None:
            scope = org_units.compute_user_scope_unit_ids(int(actor_user_id), include_inactive=False)
        else:
            with engine.connect() as own_conn:
                scope = org_units.compute_user_scope_unit_ids(int(actor_user_id), include_inactive=False)
    except PermissionError:
        return set()
    if scope is None:
        return None
    return set(int(unit_id) for unit_id in scope)


def evaluate_order_cancel_scope(
    conn: Connection,
    *,
    order_id: int,
    created_by: int,
    actor_user_id: int,
) -> Tuple[bool, str]:
    """Return whether order is within actor cancel scope and the rule applied."""
    actor_scope = resolve_actor_scope_unit_ids(int(actor_user_id), conn=conn)
    if actor_scope is None:
        return True, SCOPE_RULE_UNLIMITED

    item_unit_ids = resolve_order_scope_unit_ids(conn, int(order_id))
    if not item_unit_ids:
        author_unit_id = _fetch_user_unit_id(conn, int(created_by))
        if author_unit_id is None:
            return False, SCOPE_RULE_AUTHOR_UNIT_MISSING
        if author_unit_id in actor_scope:
            return True, SCOPE_RULE_AUTHOR_UNIT
        return False, SCOPE_RULE_AUTHOR_UNIT

    unique_units = sorted(set(item_unit_ids))
    if len(unique_units) > 1:
        all_in_scope = all(unit_id in actor_scope for unit_id in unique_units)
        if all_in_scope:
            return True, SCOPE_RULE_ALL_ITEMS
        return False, SCOPE_RULE_COMPOSITE_DENIED

    if unique_units[0] in actor_scope:
        return True, SCOPE_RULE_ALL_ITEMS
    return False, SCOPE_RULE_ALL_ITEMS
