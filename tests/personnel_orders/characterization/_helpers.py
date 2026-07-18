"""Shared helpers for Personnel Orders characterization tests (UDE-007)."""
from __future__ import annotations

from typing import Any, Dict
from uuid import uuid4

from sqlalchemy import text

from app.db.engine import engine
from app.ppr.domain.models import HR_RELATIONSHIP_CANDIDATE
from tests.conftest import table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_person
from tests.test_wp_po_003_personnel_orders_schema import (
    _delete_personnel_order_audit_rows,
    _pick_employee_id,
)
from tests.test_wp_po_edit_002_migration import _require_schema as _require_edit_002_schema
from tests.test_wp_po_lc_del_005_archive_api import (
    _archive_payload,
    _cleanup_order,
    _create_draft_order,
    _set_order_status,
)


def require_edit_002_schema() -> None:
    _require_edit_002_schema()


def cancel_payload(**overrides: Any) -> Dict[str, Any]:
    payload = {"reason_code": "created_by_mistake", "reason_text": "Characterization cancel"}
    payload.update(overrides)
    return payload


def create_draft_order(
    client,
    headers,
    *,
    suffix: str | None = None,
    created_by: int | None = None,
) -> int:
    order_id = _create_draft_order(client, headers, suffix=suffix)
    if created_by is not None:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE public.personnel_orders
                    SET created_by = :created_by
                    WHERE order_id = :order_id
                    """
                ),
                {"created_by": int(created_by), "order_id": order_id},
            )
    return order_id


def cleanup_order(order_id: int | None) -> None:
    if order_id is None:
        return
    _cleanup_order_with_person_graph(order_id, editorial=False)


def set_order_status(order_id: int, status: str, *, void_reason: str | None = None) -> None:
    _set_order_status(order_id, status, void_reason=void_reason)


def archive_payload(**overrides: Any) -> Dict[str, Any]:
    return _archive_payload(**overrides)


def unique_suffix() -> str:
    return uuid4().hex[:8]


def create_hire_candidate_person(conn, *, suffix: str) -> int:
    person_id = insert_person(
        conn,
        full_name=f"Char Hire Candidate {suffix}",
        prefix="po-char",
    )
    if table_exists(conn, "personnel_record_metadata"):
        conn.execute(
            text(
                """
                INSERT INTO public.personnel_record_metadata (
                    person_id, ppr_lifecycle_state, hr_relationship_context, version
                )
                VALUES (:person_id, 'CREATED', :ctx, 1)
                ON CONFLICT (person_id) DO UPDATE
                SET hr_relationship_context = EXCLUDED.hr_relationship_context,
                    updated_at = now()
                """
            ),
            {"person_id": person_id, "ctx": HR_RELATIONSHIP_CANDIDATE},
        )
    return person_id


def build_hire_item_payload(
    *,
    person_id: int | None = None,
    org_unit_id: int | None = None,
    position_id: int | None = None,
    employment_rate: float = 1.0,
    org_unit_name: str = "Synthetic Unit",
    position_name: str = "Synthetic Position",
    **overrides: Any,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "employment_rate": employment_rate,
        "org_unit_name": org_unit_name,
        "position_name": position_name,
    }
    if person_id is not None:
        payload["person_id"] = int(person_id)
    if org_unit_id is not None:
        payload["org_unit_id"] = int(org_unit_id)
    if position_id is not None:
        payload["position_id"] = int(position_id)
    payload.update(overrides)
    return payload


def post_order_item(
    client,
    headers,
    order_id: int,
    *,
    item_type_code: str,
    employee_id: int | None = None,
    effective_date: str = "2026-07-12",
    payload: Dict[str, Any] | None = None,
):
    body: Dict[str, Any] = {
        "item_type_code": item_type_code,
        "effective_date": effective_date,
        "payload": payload or {},
    }
    if employee_id is not None:
        body["employee_id"] = employee_id
    return client.post(
        f"/directory/personnel-orders/{order_id}/items",
        json=body,
        headers=headers,
    )


def create_hire_item(
    client,
    headers,
    order_id: int,
    *,
    employee_id: int | None = None,
    person_id: int | None = None,
    item_type: str = "HIRE",
    payload_overrides: Dict[str, Any] | None = None,
    auto_person_for_hire: bool = True,
) -> int:
    """Create an order item using the canonical identity contract.

    HIRE: requires employee_id or payload.person_id. When both are omitted and
    auto_person_for_hire is True, a CANDIDATE person is created for characterization.
    Non-HIRE types require employee_id.
    """
    if (
        item_type == "HIRE"
        and employee_id is None
        and person_id is None
        and auto_person_for_hire
    ):
        with engine.begin() as conn:
            person_id = create_hire_candidate_person(conn, suffix=unique_suffix())

    item_payload = build_hire_item_payload(person_id=person_id)
    if payload_overrides:
        item_payload.update(payload_overrides)

    item_resp = post_order_item(
        client,
        headers,
        order_id,
        item_type_code=item_type,
        employee_id=employee_id,
        payload=item_payload,
    )
    assert item_resp.status_code == 200, item_resp.text
    return int(item_resp.json()["items"][0]["item_id"])


def create_draft_with_item(
    client,
    headers,
    *,
    order_type: str = "HIRE",
    employee_id: int | None = None,
    person_id: int | None = None,
    suffix: str | None = None,
) -> tuple[int, int]:
    order_id = create_draft_order(client, headers, suffix=suffix)
    try:
        if employee_id is None and order_type != "HIRE" and person_id is None:
            with engine.begin() as conn:
                employee_id = _pick_employee_id(conn)
        item_id = create_hire_item(
            client,
            headers,
            order_id,
            employee_id=employee_id,
            person_id=person_id,
            item_type=order_type,
            auto_person_for_hire=order_type == "HIRE" and person_id is None and employee_id is None,
        )
        return order_id, item_id
    except Exception:
        cleanup_order_with_editorial(order_id)
        raise


def _person_ids_from_order(conn, order_id: int) -> list[int]:
    if not table_exists(conn, "personnel_order_items"):
        return []
    rows = conn.execute(
        text(
            """
            SELECT payload->>'person_id' AS person_id
            FROM public.personnel_order_items
            WHERE order_id = :order_id
              AND payload ? 'person_id'
            """
        ),
        {"order_id": order_id},
    ).scalars().all()
    person_ids: list[int] = []
    for raw in rows:
        if raw is None:
            continue
        try:
            person_ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    return person_ids


def _cleanup_order_with_person_graph(order_id: int, *, editorial: bool) -> None:
    with engine.begin() as conn:
        exists = conn.execute(
            text(
                """
                SELECT 1 FROM public.personnel_orders
                WHERE order_id = :order_id
                LIMIT 1
                """
            ),
            {"order_id": order_id},
        ).first()
        if not exists:
            return
        person_ids = _person_ids_from_order(conn, order_id)
        _delete_personnel_order_audit_rows(conn, order_id)
        conn.execute(
            text("DELETE FROM public.employee_events WHERE order_id = :order_id"),
            {"order_id": order_id},
        )
        if editorial:
            editorial_exists = conn.execute(
                text(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = 'personnel_order_editorial_blocks'
                    LIMIT 1
                    """
                )
            ).first()
            if editorial_exists:
                conn.execute(
                    text(
                        """
                        DELETE FROM public.personnel_order_item_editorial_blocks
                        WHERE order_item_id IN (
                            SELECT item_id FROM public.personnel_order_items WHERE order_id = :order_id
                        )
                        """
                    ),
                    {"order_id": order_id},
                )
                conn.execute(
                    text(
                        """
                        DELETE FROM public.personnel_order_item_bases
                        WHERE order_item_id IN (
                            SELECT item_id FROM public.personnel_order_items WHERE order_id = :order_id
                        )
                        """
                    ),
                    {"order_id": order_id},
                )
                conn.execute(
                    text(
                        "DELETE FROM public.personnel_order_editorial_blocks WHERE order_id = :order_id"
                    ),
                    {"order_id": order_id},
                )
        conn.execute(
            text("DELETE FROM public.personnel_order_localized_texts WHERE order_id = :order_id"),
            {"order_id": order_id},
        )
        conn.execute(
            text("DELETE FROM public.personnel_order_items WHERE order_id = :order_id"),
            {"order_id": order_id},
        )
        conn.execute(
            text("DELETE FROM public.personnel_orders WHERE order_id = :order_id"),
            {"order_id": order_id},
        )
        if person_ids and table_exists(conn, "persons"):
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def cleanup_order_with_editorial(order_id: int | None) -> None:
    if order_id is None:
        return
    _cleanup_order_with_person_graph(order_id, editorial=True)
