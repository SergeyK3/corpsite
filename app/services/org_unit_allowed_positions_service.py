"""Read/write helpers for org_unit_allowed_positions (ADR-046 F1)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from app.db.engine import engine


def build_allowed_positions_exists_sql(
    *,
    org_group_id: Optional[int],
    org_unit_id: Optional[int],
) -> Tuple[str, Dict[str, Any]]:
    """Build EXISTS filter for allowed positions on positions alias ``p``.

    Allowed links apply to the selected org unit directly — no parent-subtree inheritance.
    When org_group_id is set, filter allowed rows whose org_unit belongs to that group.
    """
    params: Dict[str, Any] = {}
    oap_filters: List[str] = ["oap.is_active = TRUE", "oap.position_id = p.position_id"]

    if org_unit_id is not None:
        params["allowed_org_unit_id"] = int(org_unit_id)
        oap_filters.append("oap.org_unit_id = :allowed_org_unit_id")

    if org_group_id is not None:
        params["allowed_org_group_id"] = int(org_group_id)
        oap_filters.append(
            """
            EXISTS (
                SELECT 1
                FROM public.org_units ou_allowed
                WHERE ou_allowed.unit_id = oap.org_unit_id
                  AND ou_allowed.group_id = :allowed_org_group_id
            )
            """.strip()
        )

    oap_where = " AND ".join(oap_filters)
    exists_sql = f"""
EXISTS (
    SELECT 1
    FROM public.org_unit_allowed_positions oap
    WHERE {oap_where}
)
""".strip()
    return exists_sql, params


def build_allowed_positions_order_sql(
    *,
    org_group_id: Optional[int],
    org_unit_id: Optional[int],
) -> Tuple[str, Dict[str, Any]]:
    """Order key: MIN sort_order for matching allowed rows, then name/id."""
    params: Dict[str, Any] = {}
    oap_filters: List[str] = ["oap_sort.is_active = TRUE", "oap_sort.position_id = p.position_id"]

    if org_unit_id is not None:
        params["allowed_sort_org_unit_id"] = int(org_unit_id)
        oap_filters.append("oap_sort.org_unit_id = :allowed_sort_org_unit_id")

    if org_group_id is not None:
        params["allowed_sort_org_group_id"] = int(org_group_id)
        oap_filters.append(
            """
            EXISTS (
                SELECT 1
                FROM public.org_units ou_sort
                WHERE ou_sort.unit_id = oap_sort.org_unit_id
                  AND ou_sort.group_id = :allowed_sort_org_group_id
            )
            """.strip()
        )

    oap_where = " AND ".join(oap_filters)
    order_sql = f"""
(
    SELECT MIN(COALESCE(oap_sort.sort_order, 2147483647))
    FROM public.org_unit_allowed_positions oap_sort
    WHERE {oap_where}
) ASC,
p.name ASC,
p.position_id ASC
""".strip()
    return order_sql, params


def upsert_allowed_position_link(
    conn,
    *,
    org_unit_id: int,
    position_id: int,
    sort_order: Optional[int] = None,
    is_active: bool = True,
) -> int:
    """Idempotently create or reactivate an allowed-position link. Returns junction PK."""
    row = conn.execute(
        text(
            """
            SELECT org_unit_allowed_position_id, is_active, sort_order
            FROM public.org_unit_allowed_positions
            WHERE org_unit_id = :org_unit_id
              AND position_id = :position_id
            LIMIT 1
            """
        ),
        {"org_unit_id": int(org_unit_id), "position_id": int(position_id)},
    ).mappings().first()

    if row:
        link_id = int(row["org_unit_allowed_position_id"])
        updates: Dict[str, Any] = {"link_id": link_id}
        set_parts = ["updated_at = now()"]
        if not bool(row["is_active"]) and is_active:
            set_parts.append("is_active = TRUE")
        if sort_order is not None and row.get("sort_order") != sort_order:
            set_parts.append("sort_order = :sort_order")
            updates["sort_order"] = int(sort_order)
        if len(set_parts) > 1 or (sort_order is not None and row.get("sort_order") != sort_order):
            conn.execute(
                text(
                    f"""
                    UPDATE public.org_unit_allowed_positions
                    SET {", ".join(set_parts)}
                    WHERE org_unit_allowed_position_id = :link_id
                    """
                ),
                updates,
            )
        return link_id

    inserted = conn.execute(
        text(
            """
            INSERT INTO public.org_unit_allowed_positions (
                org_unit_id,
                position_id,
                sort_order,
                is_active
            )
            VALUES (:org_unit_id, :position_id, :sort_order, :is_active)
            RETURNING org_unit_allowed_position_id
            """
        ),
        {
            "org_unit_id": int(org_unit_id),
            "position_id": int(position_id),
            "sort_order": sort_order,
            "is_active": bool(is_active),
        },
    ).mappings().first()
    return int(inserted["org_unit_allowed_position_id"])


def list_active_allowed_position_ids(conn, *, org_unit_id: int) -> List[int]:
    rows = conn.execute(
        text(
            """
            SELECT position_id
            FROM public.org_unit_allowed_positions
            WHERE org_unit_id = :org_unit_id
              AND is_active = TRUE
            ORDER BY COALESCE(sort_order, 2147483647), position_id
            """
        ),
        {"org_unit_id": int(org_unit_id)},
    ).mappings().all()
    return [int(r["position_id"]) for r in rows]


def allowed_link_exists(conn, *, org_unit_id: int, position_id: int) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM public.org_unit_allowed_positions
            WHERE org_unit_id = :org_unit_id
              AND position_id = :position_id
              AND is_active = TRUE
            LIMIT 1
            """
        ),
        {"org_unit_id": int(org_unit_id), "position_id": int(position_id)},
    ).first()
    return row is not None
