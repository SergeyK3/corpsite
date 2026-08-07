"""Read/write helpers for org_unit_allowed_positions (ADR-046)."""
from __future__ import annotations


from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Tuple

from sqlalchemy import text

from app.services.security_audit_service import write_security_event


class _SortOrderOmitted:
    __slots__ = ()


SORT_ORDER_OMITTED = _SortOrderOmitted()
SortOrderInput = int | None | _SortOrderOmitted
AllowedPositionTransition = Literal["created", "reactivated", "updated", "noop"]


@dataclass(frozen=True)
class AllowedPositionMutationResult:
    link: Dict[str, Any]
    transition: AllowedPositionTransition
    previous_state: Optional[Dict[str, Any]]
    current_state: Dict[str, Any]


class AllowedPositionMutationNotFoundError(LookupError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class AllowedPositionMutationConflictError(RuntimeError):
    """A guarded write did not return the row it was required to mutate."""


class AllowedPositionAuditError(RuntimeError):
    """A mandatory allowed-position audit append did not return an audit id."""


_LINK_COLUMNS = """
    org_unit_allowed_position_id,
    org_unit_id,
    position_id,
    sort_order,
    is_active,
    created_at,
    updated_at
""".strip()

_AUDIT_EVENT_BY_TRANSITION = {
    "created": "ORG_UNIT_ALLOWED_POSITION_CREATED",
    "reactivated": "ORG_UNIT_ALLOWED_POSITION_REACTIVATED",
    "updated": "ORG_UNIT_ALLOWED_POSITION_UPDATED",
    "deactivated": "ORG_UNIT_ALLOWED_POSITION_DEACTIVATED",
}


def _link_dict(row) -> Dict[str, Any]:
    return dict(row)


def _link_state(link: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "is_active": bool(link["is_active"]),
        "sort_order": link["sort_order"],
    }


def _lock_parents(conn, *, position_id: int, org_unit_id: int) -> None:
    position = conn.execute(
        text(
            """
            SELECT position_id
            FROM public.positions
            WHERE position_id = :position_id
            FOR UPDATE
            """
        ),
        {"position_id": int(position_id)},
    ).first()
    if position is None:
        raise AllowedPositionMutationNotFoundError("POSITION_NOT_FOUND")

    org_unit = conn.execute(
        text(
            """
            SELECT unit_id
            FROM public.org_units
            WHERE unit_id = :org_unit_id
            FOR UPDATE
            """
        ),
        {"org_unit_id": int(org_unit_id)},
    ).first()
    if org_unit is None:
        raise AllowedPositionMutationNotFoundError("ORG_UNIT_NOT_FOUND")


def _lock_link(conn, *, org_unit_id: int, position_id: int):
    return conn.execute(
        text(
            f"""
            SELECT {_LINK_COLUMNS}
            FROM public.org_unit_allowed_positions
            WHERE org_unit_id = :org_unit_id
              AND position_id = :position_id
            FOR UPDATE
            """
        ),
        {"org_unit_id": int(org_unit_id), "position_id": int(position_id)},
    ).mappings().first()


def _append_required_audit(
    conn,
    *,
    transition: Literal["created", "reactivated", "updated", "deactivated"],
    actor_user_id: int,
    link: Dict[str, Any],
    previous_state: Optional[Dict[str, Any]],
    current_state: Dict[str, Any],
    request_id: Optional[str],
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> int:
    metadata: Dict[str, Any] = {
        "org_unit_allowed_position_id": int(link["org_unit_allowed_position_id"]),
        "org_unit_id": int(link["org_unit_id"]),
        "position_id": int(link["position_id"]),
        "previous_state": previous_state,
        "current_state": current_state,
    }
    if transition == "updated":
        metadata["previous_sort_order"] = previous_state["sort_order"] if previous_state else None
        metadata["new_sort_order"] = current_state["sort_order"]

    audit_id = write_security_event(
        event_type=_AUDIT_EVENT_BY_TRANSITION[transition],
        actor_user_id=int(actor_user_id),
        ip_address=ip_address,
        user_agent=user_agent,
        success=True,
        metadata=metadata,
        request_id=request_id,
        conn=conn,
    )
    if audit_id is None:
        raise AllowedPositionAuditError("MANDATORY_AUDIT_WRITE_FAILED")
    return int(audit_id)


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
    actor_user_id: int,
    sort_order: SortOrderInput = SORT_ORDER_OMITTED,
    request_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AllowedPositionMutationResult:
    """Create/reactivate/update one link while preserving caller transaction ownership."""
    with conn.begin_nested():
        _lock_parents(
            conn,
            position_id=int(position_id),
            org_unit_id=int(org_unit_id),
        )
        row = _lock_link(
            conn,
            org_unit_id=int(org_unit_id),
            position_id=int(position_id),
        )

        if row is None:
            effective_sort_order = None if sort_order is SORT_ORDER_OMITTED else sort_order
            inserted = conn.execute(
                text(
                    f"""
                    INSERT INTO public.org_unit_allowed_positions (
                        org_unit_id,
                        position_id,
                        sort_order,
                        is_active
                    )
                    VALUES (:org_unit_id, :position_id, :sort_order, TRUE)
                    ON CONFLICT (org_unit_id, position_id) DO NOTHING
                    RETURNING {_LINK_COLUMNS}
                    """
                ),
                {
                    "org_unit_id": int(org_unit_id),
                    "position_id": int(position_id),
                    "sort_order": effective_sort_order,
                },
            ).mappings().first()
            if inserted is not None:
                link = _link_dict(inserted)
                current_state = _link_state(link)
                _append_required_audit(
                    conn,
                    transition="created",
                    actor_user_id=int(actor_user_id),
                    link=link,
                    previous_state=None,
                    current_state=current_state,
                    request_id=request_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                return AllowedPositionMutationResult(
                    link=link,
                    transition="created",
                    previous_state=None,
                    current_state=current_state,
                )

            row = _lock_link(
                conn,
                org_unit_id=int(org_unit_id),
                position_id=int(position_id),
            )
            if row is None:
                raise AllowedPositionMutationConflictError(
                    "ALLOWED_POSITION_LINK_WRITE_CONFLICT"
                )

        previous_link = _link_dict(row)
        previous_state = _link_state(previous_link)
        effective_sort_order = (
            previous_link["sort_order"]
            if sort_order is SORT_ORDER_OMITTED
            else sort_order
        )

        if bool(previous_link["is_active"]):
            if previous_link["sort_order"] == effective_sort_order:
                return AllowedPositionMutationResult(
                    link=previous_link,
                    transition="noop",
                    previous_state=previous_state,
                    current_state=dict(previous_state),
                )
            transition: AllowedPositionTransition = "updated"
            event_transition: Literal["updated", "reactivated"] = "updated"
            updated = conn.execute(
                text(
                    f"""
                    UPDATE public.org_unit_allowed_positions
                    SET sort_order = :sort_order,
                        updated_at = now()
                    WHERE org_unit_allowed_position_id = :link_id
                    RETURNING {_LINK_COLUMNS}
                    """
                ),
                {
                    "link_id": int(previous_link["org_unit_allowed_position_id"]),
                    "sort_order": effective_sort_order,
                },
            ).mappings().first()
        else:
            transition = "reactivated"
            event_transition = "reactivated"
            updated = conn.execute(
                text(
                    f"""
                    UPDATE public.org_unit_allowed_positions
                    SET is_active = TRUE,
                        sort_order = :sort_order,
                        updated_at = now()
                    WHERE org_unit_allowed_position_id = :link_id
                    RETURNING {_LINK_COLUMNS}
                    """
                ),
                {
                    "link_id": int(previous_link["org_unit_allowed_position_id"]),
                    "sort_order": effective_sort_order,
                },
            ).mappings().first()

        if updated is None:
            raise AllowedPositionMutationConflictError(
                "ALLOWED_POSITION_LINK_STALE_WRITE"
            )
        link = _link_dict(updated)
        current_state = _link_state(link)
        _append_required_audit(
            conn,
            transition=event_transition,
            actor_user_id=int(actor_user_id),
            link=link,
            previous_state=previous_state,
            current_state=current_state,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return AllowedPositionMutationResult(
            link=link,
            transition=transition,
            previous_state=previous_state,
            current_state=current_state,
        )


def deactivate_allowed_position_link(
    conn,
    *,
    org_unit_id: int,
    position_id: int,
    actor_user_id: int,
    request_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """Soft-disable one existing pair and return its resulting inactive state."""
    with conn.begin_nested():
        _lock_parents(
            conn,
            position_id=int(position_id),
            org_unit_id=int(org_unit_id),
        )
        row = _lock_link(
            conn,
            org_unit_id=int(org_unit_id),
            position_id=int(position_id),
        )
        if row is None:
            raise AllowedPositionMutationNotFoundError(
                "ALLOWED_POSITION_LINK_NOT_FOUND"
            )

        previous_link = _link_dict(row)
        if not bool(previous_link["is_active"]):
            return previous_link

        previous_state = _link_state(previous_link)
        updated = conn.execute(
            text(
                f"""
                UPDATE public.org_unit_allowed_positions
                SET is_active = FALSE,
                    updated_at = now()
                WHERE org_unit_allowed_position_id = :link_id
                RETURNING {_LINK_COLUMNS}
                """
            ),
            {"link_id": int(previous_link["org_unit_allowed_position_id"])},
        ).mappings().first()
        if updated is None:
            raise AllowedPositionMutationConflictError(
                "ALLOWED_POSITION_LINK_STALE_WRITE"
            )

        link = _link_dict(updated)
        current_state = _link_state(link)
        _append_required_audit(
            conn,
            transition="deactivated",
            actor_user_id=int(actor_user_id),
            link=link,
            previous_state=previous_state,
            current_state=current_state,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return link


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
